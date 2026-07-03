"""y-websocket wire protocol (lib0 encoding) — pure functions, no I/O.

Message layout: varuint msg_type, then payload.
  0 = sync    (varuint subtype: 0 step1 / 1 step2 / 2 update, then var-bytes)
  1 = awareness (var-bytes: awareness update)
  3 = query awareness
Awareness update payload: varuint N, then N × (varuint client_id, varuint clock,
var-string state_json). state_json "null" clears the client.
"""

import json
from dataclasses import dataclass

MSG_SYNC = 0
MSG_AWARENESS = 1
MSG_AUTH = 2
MSG_QUERY_AWARENESS = 3

SYNC_STEP1 = 0
SYNC_STEP2 = 1
SYNC_UPDATE = 2


def write_varuint(value: int) -> bytes:
    out = bytearray()
    while value > 127:
        out.append(128 | (value & 127))
        value >>= 7
    out.append(value)
    return bytes(out)


def read_varuint(data: bytes, pos: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while True:
        byte = data[pos]
        pos += 1
        value |= (byte & 127) << shift
        if byte < 128:
            return value, pos
        shift += 7


def write_varbytes(payload: bytes) -> bytes:
    return write_varuint(len(payload)) + payload


def read_varbytes(data: bytes, pos: int) -> tuple[bytes, int]:
    length, pos = read_varuint(data, pos)
    return data[pos : pos + length], pos + length


def encode_sync_step1(state_vector: bytes) -> bytes:
    return write_varuint(MSG_SYNC) + write_varuint(SYNC_STEP1) + write_varbytes(state_vector)


def encode_sync_step2(update: bytes) -> bytes:
    return write_varuint(MSG_SYNC) + write_varuint(SYNC_STEP2) + write_varbytes(update)


def encode_sync_update(update: bytes) -> bytes:
    return write_varuint(MSG_SYNC) + write_varuint(SYNC_UPDATE) + write_varbytes(update)


def encode_awareness(payload: bytes) -> bytes:
    return write_varuint(MSG_AWARENESS) + write_varbytes(payload)


@dataclass(frozen=True)
class AwarenessEntry:
    client_id: int
    clock: int
    state_json: str  # "null" when cleared


def decode_awareness_update(payload: bytes) -> list[AwarenessEntry]:
    entries: list[AwarenessEntry] = []
    count, pos = read_varuint(payload, 0)
    for _ in range(count):
        client_id, pos = read_varuint(payload, pos)
        clock, pos = read_varuint(payload, pos)
        raw, pos = read_varbytes(payload, pos)
        entries.append(AwarenessEntry(client_id, clock, raw.decode()))
    return entries


def encode_awareness_update(entries: list[AwarenessEntry]) -> bytes:
    out = bytearray(write_varuint(len(entries)))
    for entry in entries:
        out += write_varuint(entry.client_id)
        out += write_varuint(entry.clock)
        raw = entry.state_json.encode()
        out += write_varuint(len(raw)) + raw
    return bytes(out)


def parse_state(entry: AwarenessEntry) -> dict | None:
    try:
        state = json.loads(entry.state_json)
    except json.JSONDecodeError:
        return None
    return state if isinstance(state, dict) else None
