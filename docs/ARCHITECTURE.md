# Knowledge Hub — Architecture

Self-hosted collaborative knowledge base: Obsidian-style linking + Notion-style
collaboration + AI-agent access via MCP.

## Stack

| Concern | Choice | Why |
|---|---|---|
| API | FastAPI (Python 3.12, uv) | async, typed, easy to maintain |
| DB | PostgreSQL 16 + pgvector + pg_trgm | one store for relational + FTS + vectors |
| ORM / migrations | SQLAlchemy 2 async + Alembic | standard, reviewable migrations |
| Realtime collab | Yjs CRDT — `pycrdt` server side, y-websocket wire protocol | conflict-free editing, single-language backend |
| Editor | React + TipTap v2 (ProseMirror) + yjs binding | best OSS collaborative editor stack |
| Canonical format | Markdown (stored in DB, exportable to files) | Obsidian-like, diff-able, AI-friendly |
| Search | Postgres FTS + trigram (CJK-safe) + pgvector semantic | hybrid retrieval with citations |
| Embeddings | any OpenAI-compatible endpoint (configurable) | works with internal gateways; optional |
| MCP | official `mcp` Python SDK, streamable-HTTP + stdio | Claude/Cursor/agents read the KB |
| Auth | httpOnly cookie sessions (users) + API tokens (agents/MCP) | browser + machine access |

## Content model: markdown is canonical, Yjs is the live session

- `pages.content_md` is the canonical document. Search, links, versions, MCP,
  and export all read markdown.
- While a page is open, a Yjs doc (ProseMirror XmlFragment) is the live state,
  synced over WebSocket (y-websocket protocol). Updates are persisted
  (`page_ydocs`) so sessions survive restarts.
- If the Yjs doc is empty, the first client seeds it from markdown.
- The server serializes Yjs → markdown (pure-Python converter) on debounce and
  on last-client-disconnect, writing `content_md`, creating a version row, and
  triggering the indexing pipeline.
- REST/MCP writes go straight to markdown (rejected with 409 while a live
  collab session holds the page, to keep one writer of truth).

## Indexing pipeline (orchestration/index_page.py)

On every content change:
1. Parse `[[wikilinks]]`, markdown links, `#tags`, and frontmatter metadata.
2. Upsert `page_links` (resolved + unresolved targets → unlinked mentions when
   a page with that title appears later).
3. Refresh FTS columns (generated tsvector + trigram index).
4. Chunk by headings/paragraphs, embed changed chunks → `page_chunks` (pgvector).
   Runs in-process background task; skipped when embeddings are not configured.

## Modules (src/app/modules/)

- `identity` — users, sessions, API tokens, password hashing (argon2), JWT-free
  cookie sessions.
- `workspaces` — workspaces, membership, roles (owner/admin/member/viewer), RBAC
  policy checks.
- `pages` — page tree (folders are pages with children), CRUD, versions,
  tags, metadata (typed key/values + frontmatter), attachments, comments +
  @mentions, page visibility (workspace/private + explicit shares).
- `links` — wikilink parsing (pure domain), backlinks, outgoing links, unlinked
  mentions, graph (nodes/edges incl. tag co-occurrence), related pages
  (links + shared tags + vector similarity blend), orphans.
- `search` — hybrid full-text (tsvector + trigram for CJK) + semantic (pgvector)
  with filters (tag/status/owner/project/metadata), snippet extraction.
- `collab` — Yjs room manager over FastAPI WebSocket, presence/awareness relay,
  update persistence, Yjs→markdown serializer.
- `audit` — append-only audit log of all mutations.

Interfaces: `api/` (HTTP+WS), `mcpserver/` (MCP tools, read-only v1; write-back
lands as draft-pages + review status later — the pages model already has
`status` for that).

## RBAC

Role per workspace member. viewer: read; member: create/edit pages; admin:
manage members/tags/settings; owner: delete workspace, transfer.
Page-level: `visibility=workspace|private`; private pages readable by creator +
explicit `page_shares` rows. All checks centralized in
`workspaces/services/policy.py`.

## Deployment

Deployment files live in `deploy/`. From the repo root run:

```bash
docker compose --env-file .env -f deploy/docker-compose.yml up -d --build
```

The compose stack starts `db` (PostgreSQL + pgvector) and `app` (uvicorn, API,
MCP endpoint, and built frontend). User-created system data is bind-mounted to
real host paths by default: `data/postgres/` stores pages, folders, comments,
users, workspaces, and search indexes; `data/uploads/` stores attachments. This
keeps data across service restarts and container recreates. Single origin — no
CORS in production.
