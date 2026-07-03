"""Pure markdown chunking for embeddings — no I/O."""

import re
from dataclasses import dataclass

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
MAX_CHUNK_CHARS = 1600
MIN_CHUNK_CHARS = 40


@dataclass(frozen=True)
class Chunk:
    ord: int
    heading: str | None
    text: str


def chunk_markdown(md: str, title: str) -> list[Chunk]:
    """Split by headings, then cap long sections by paragraph groups.
    Each chunk is prefixed contextually by the caller (title/heading kept separate)."""
    sections: list[tuple[str | None, list[str]]] = [(None, [])]
    for line in md.splitlines():
        m = HEADING_RE.match(line)
        if m:
            sections.append((m.group(2).strip(), []))
        else:
            sections[-1][1].append(line)

    chunks: list[Chunk] = []
    for heading, lines in sections:
        text = "\n".join(lines).strip()
        if not text and not heading:
            continue
        for piece in _split_long(text):
            if len(piece) >= MIN_CHUNK_CHARS or heading:
                chunks.append(Chunk(ord=len(chunks), heading=heading, text=piece))
    if not chunks and md.strip():
        chunks.append(Chunk(ord=0, heading=None, text=md.strip()[:MAX_CHUNK_CHARS]))
    return chunks


def _split_long(text: str) -> list[str]:
    if len(text) <= MAX_CHUNK_CHARS:
        return [text] if text else [""]
    pieces: list[str] = []
    current: list[str] = []
    size = 0
    for para in re.split(r"\n{2,}", text):
        if size + len(para) > MAX_CHUNK_CHARS and current:
            pieces.append("\n\n".join(current))
            current, size = [], 0
        if len(para) > MAX_CHUNK_CHARS:  # single huge paragraph: hard split
            for i in range(0, len(para), MAX_CHUNK_CHARS):
                pieces.append(para[i : i + MAX_CHUNK_CHARS])
            continue
        current.append(para)
        size += len(para)
    if current:
        pieces.append("\n\n".join(current))
    return pieces


def embedding_input(title: str, heading: str | None, text: str) -> str:
    prefix = title if not heading else f"{title} — {heading}"
    return f"{prefix}\n{text}"
