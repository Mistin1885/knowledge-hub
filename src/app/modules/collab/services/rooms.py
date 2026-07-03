"""Yjs collaboration rooms over WebSocket (y-websocket protocol).

One Room per open page. The room owns the authoritative Doc; client updates are
applied, broadcast, and periodically snapshotted back to markdown through the
injected on_snapshot callback (wired to the orchestration pipeline in main.py).
"""

import asyncio
import contextlib
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from fastapi import WebSocket
from pycrdt import Doc, XmlFragment

from app.infra.db.engine import db_session
from app.modules.collab.domain import protocol, y_markdown
from app.modules.collab.infra import ypersistence
from app.shared.config.settings import settings
from app.shared.logging import get_logger

log = get_logger(__name__)

SnapshotFn = Callable[[uuid.UUID, str, list[uuid.UUID], bool], Awaitable[None]]


@dataclass
class Connection:
    ws: WebSocket
    user_id: uuid.UUID
    can_edit: bool
    display: dict
    client_ids: set[int] = field(default_factory=set)


@dataclass
class Room:
    page_id: uuid.UUID
    doc: Doc
    frag: XmlFragment
    connections: dict[WebSocket, Connection] = field(default_factory=dict)
    awareness: dict[int, protocol.AwarenessEntry] = field(default_factory=dict)
    editor_ids: list[uuid.UUID] = field(default_factory=list)
    dirty: bool = False
    save_task: asyncio.Task | None = None

    def note_editor(self, user_id: uuid.UUID) -> None:
        if user_id in self.editor_ids:
            self.editor_ids.remove(user_id)
        self.editor_ids.append(user_id)


class RoomManager:
    def __init__(self) -> None:
        self.rooms: dict[uuid.UUID, Room] = {}
        self._lock = asyncio.Lock()
        self._on_snapshot: SnapshotFn | None = None

    def configure(self, on_snapshot: SnapshotFn) -> None:
        self._on_snapshot = on_snapshot

    def has_active_room(self, page_id: uuid.UUID) -> bool:
        room = self.rooms.get(page_id)
        return bool(room and room.connections)

    def presence(self, page_id: uuid.UUID) -> list[dict]:
        room = self.rooms.get(page_id)
        if not room:
            return []
        people = []
        for entry in room.awareness.values():
            state = protocol.parse_state(entry)
            if state and isinstance(state.get("user"), dict):
                people.append(state["user"])
        return people

    async def connect(
        self, page_id: uuid.UUID, ws: WebSocket, user_id: uuid.UUID, can_edit: bool, display: dict
    ) -> Room:
        async with self._lock:
            room = self.rooms.get(page_id)
            if room is None:
                room = await self._load_room(page_id)
                self.rooms[page_id] = room
        conn = Connection(ws=ws, user_id=user_id, can_edit=can_edit, display=display)
        room.connections[ws] = conn
        # initial handshake: our state vector + known cursors
        await ws.send_bytes(protocol.encode_sync_step1(room.doc.get_state()))
        if room.awareness:
            payload = protocol.encode_awareness_update(list(room.awareness.values()))
            await ws.send_bytes(protocol.encode_awareness(payload))
        return room

    async def _load_room(self, page_id: uuid.UUID) -> Room:
        doc = Doc()
        frag = doc.get("default", type=XmlFragment)
        async with db_session() as s:
            state = await ypersistence.load_state(s, page_id)
            if state:
                doc.apply_update(state)
            else:
                page = await ypersistence.get_page(s, page_id)
                y_markdown.md_to_fragment(page.content_md if page else "", frag)
                await ypersistence.save_state(s, page_id, doc.get_update())
        return Room(page_id=page_id, doc=doc, frag=frag)

    async def handle_message(self, room: Room, ws: WebSocket, data: bytes) -> None:
        conn = room.connections.get(ws)
        if conn is None or not data:
            return
        msg_type, pos = protocol.read_varuint(data, 0)

        if msg_type == protocol.MSG_SYNC:
            subtype, pos = protocol.read_varuint(data, pos)
            if subtype == protocol.SYNC_STEP1:
                their_sv, _ = protocol.read_varbytes(data, pos)
                update = room.doc.get_update(bytes(their_sv))
                await ws.send_bytes(protocol.encode_sync_step2(update))
            elif subtype in (protocol.SYNC_STEP2, protocol.SYNC_UPDATE):
                if not conn.can_edit:
                    return  # viewers are read-only; drop their edits
                update, _ = protocol.read_varbytes(data, pos)
                try:
                    room.doc.apply_update(bytes(update))
                except Exception as exc:  # corrupt update must not kill the room
                    log.warning("Rejected bad Yjs update for %s: %s", room.page_id, exc)
                    return
                room.note_editor(conn.user_id)
                room.dirty = True
                self._schedule_save(room)
                await self._broadcast(room, protocol.encode_sync_update(bytes(update)), exclude=ws)

        elif msg_type == protocol.MSG_AWARENESS:
            payload, _ = protocol.read_varbytes(data, pos)
            for entry in protocol.decode_awareness_update(bytes(payload)):
                conn.client_ids.add(entry.client_id)
                if entry.state_json == "null":
                    room.awareness.pop(entry.client_id, None)
                else:
                    room.awareness[entry.client_id] = entry
            await self._broadcast(room, protocol.encode_awareness(bytes(payload)), exclude=ws)

        elif msg_type == protocol.MSG_QUERY_AWARENESS:
            if room.awareness:
                payload = protocol.encode_awareness_update(list(room.awareness.values()))
                await ws.send_bytes(protocol.encode_awareness(payload))

    async def disconnect(self, room: Room, ws: WebSocket) -> None:
        conn = room.connections.pop(ws, None)
        if conn is None:
            return
        # tell everyone this client's cursors are gone
        removals = []
        for client_id in conn.client_ids:
            known = room.awareness.pop(client_id, None)
            clock = (known.clock if known else 0) + 1
            removals.append(protocol.AwarenessEntry(client_id, clock, "null"))
        if removals and room.connections:
            payload = protocol.encode_awareness_update(removals)
            await self._broadcast(room, protocol.encode_awareness(payload), exclude=None)

        if not room.connections:
            if room.save_task:
                room.save_task.cancel()
            await self._persist(room, create_version=True)
            self.rooms.pop(room.page_id, None)

    def _schedule_save(self, room: Room) -> None:
        if room.save_task and not room.save_task.done():
            room.save_task.cancel()
        room.save_task = asyncio.create_task(self._debounced_save(room))

    async def _debounced_save(self, room: Room) -> None:
        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.sleep(settings.collab_snapshot_debounce_s)
            await self._persist(room, create_version=False)

    async def _persist(self, room: Room, *, create_version: bool) -> None:
        if not room.dirty and not create_version:
            return
        room.dirty = False
        try:
            async with db_session() as s:
                await ypersistence.save_state(s, room.page_id, room.doc.get_update())
            if self._on_snapshot is not None:
                content_md = y_markdown.fragment_to_md(room.frag)
                await self._on_snapshot(
                    room.page_id, content_md, list(room.editor_ids), create_version
                )
        except Exception:
            log.exception("Failed to persist collab room %s", room.page_id)
            room.dirty = True

    async def _broadcast(self, room: Room, message: bytes, exclude: WebSocket | None) -> None:
        for ws in list(room.connections):
            if ws is exclude:
                continue
            try:
                await ws.send_bytes(message)
            except Exception:
                room.connections.pop(ws, None)


manager = RoomManager()
