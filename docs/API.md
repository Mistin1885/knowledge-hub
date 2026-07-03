# API Contract (v1)

Base URL: `/api/v1`. JSON everywhere. Auth via httpOnly session cookie `km_session`
(set by login) or `Authorization: Bearer <api-token>`. All errors:
`{"detail": string}` with proper status codes (401/403/404/409/422).

IDs are UUID strings. Timestamps are ISO-8601 UTC.

## Auth

- `POST /auth/register` `{email, name, password}` → `201 {user}` (first user becomes instance admin)
- `POST /auth/login` `{email, password}` → `200 {user}` + sets cookie
- `POST /auth/logout` → `204`, clears cookie
- `GET /auth/me` → `{user}` — `user = {id, email, name, is_admin, created_at}`
- `GET /auth/tokens` → `[{id, name, prefix, created_at, last_used_at}]`
- `POST /auth/tokens` `{name}` → `201 {id, name, token}` (token shown once, format `kmt_...`)
- `DELETE /auth/tokens/{id}` → `204`

## Workspaces

`workspace = {id, name, slug, description, icon, created_at, my_role}`
`role ∈ owner|admin|member|viewer`

- `GET /workspaces` → `[workspace]` (mine)
- `POST /workspaces` `{name, slug?, description?, icon?}` → `201 {workspace}`
- `GET /workspaces/{id}` → `{workspace}`
- `PATCH /workspaces/{id}` (admin) → `{workspace}`
- `DELETE /workspaces/{id}` (owner) → `204`
- `GET /workspaces/{id}/members` → `[{user_id, email, name, role, joined_at}]`
- `POST /workspaces/{id}/members` (admin) `{email, role}` → `201` (user must exist)
- `PATCH /workspaces/{id}/members/{user_id}` (admin) `{role}` → `200`
- `DELETE /workspaces/{id}/members/{user_id}` (admin, or self-leave) → `204`
- `GET /workspaces/{id}/audit?limit=&cursor=` (admin) → `{items: [{id, actor: {id,name}, action, target_type, target_id, target_title, detail, created_at}], next_cursor}`

## Pages

```
page = {id, workspace_id, parent_id, title, icon, status, visibility,
        position, is_folder, owner: {id, name}, tags: [string],
        metadata: {k: v}, created_by, updated_by, created_at, updated_at}
pageDetail = page + {content_md, backlink_count, outgoing_count}
status ∈ draft|published|archived   visibility ∈ workspace|private
```

- `GET /workspaces/{wid}/pages` → flat `[page]` (client builds tree from parent_id+position)
- `POST /workspaces/{wid}/pages` `{title, parent_id?, content_md?, is_folder?, status?, visibility?, tags?, metadata?}` → `201 {pageDetail}`
- `GET /pages/{id}` → `{pageDetail}`
- `PATCH /pages/{id}` any of `{title, content_md, parent_id, position, icon, status, visibility, tags, metadata, owner_id}` → `{pageDetail}`. Content patch returns `409` if a live collab session is active.
- `DELETE /pages/{id}` → `204` (recursive; requires member+)
- `GET /pages/{id}/versions` → `[{id, version, title, created_by: {id,name}, created_at, summary}]`
- `GET /pages/{id}/versions/{vid}` → `{id, version, title, content_md, created_at}`
- `POST /pages/{id}/versions/{vid}/restore` → `{pageDetail}`
- `GET /pages/{id}/shares` / `POST {user_id}` / `DELETE /pages/{id}/shares/{user_id}` — private-page shares

### Comments

- `GET /pages/{id}/comments` → `[{id, author: {id,name}, body_md, anchor, resolved, created_at, updated_at, mentions: [{id,name}]}]`
- `POST /pages/{id}/comments` `{body_md, anchor?}` → `201 {comment}` (`@name` in body creates mentions)
- `PATCH /comments/{id}` `{body_md?, resolved?}` → `{comment}`
- `DELETE /comments/{id}` → `204`
- `GET /mentions` → `[{comment_id, page_id, page_title, author, body_md, created_at, read}]`, `POST /mentions/{comment_id}/read` → `204`

### Attachments

- `POST /pages/{id}/attachments` multipart `file` → `201 {id, filename, content_type, size, url}` (`url = /api/v1/attachments/{id}/{filename}`)
- `GET /attachments/{id}/{filename}` → binary (auth required)
- `GET /pages/{id}/attachments` → `[attachment]`

### Tags & metadata

- `GET /workspaces/{wid}/tags` → `[{name, page_count}]`
- `GET /workspaces/{wid}/metadata-keys` → `[{key, values: [string]}]` (distinct, for filter UI)

## Links & graph

- `GET /pages/{id}/backlinks` → `[{page, context}]` (context = surrounding line)
- `GET /pages/{id}/links` → `{outgoing: [{page?, target_title, resolved, context}], unresolved: [...] }`
- `GET /pages/{id}/related?limit=10` → `[{page, score, reasons: ["links","tags","semantic"]}]`
- `GET /pages/{id}/mentions` → unlinked mentions `[{page, context}]` (title appears w/o link)
- `GET /workspaces/{wid}/graph?tags=1` → `{nodes: [{id, title, icon, status, tag_count, link_count, is_tag?}], edges: [{source, target, kind: link|tag}]}`
- `GET /workspaces/{wid}/orphans` → `[page]` (no in/out links)

## Search

- `GET /workspaces/{wid}/search?q=&tags=a,b&status=&owner_id=&meta.project=X&mode=hybrid|fulltext|semantic&limit=20`
  → `{results: [{page, score, snippets: [{text, heading}]}], mode_used}`
  (`mode_used` falls back to `fulltext` when embeddings are off)
- `POST /workspaces/{wid}/ask` `{question, limit?}` → `{chunks: [{page: {id,title}, heading, text, score}]}` — retrieval w/ citations for agents/UI

## Collaboration (WebSocket)

- `WS /collab/{page_id}` — y-websocket protocol (sync + awareness). Auth via
  session cookie on handshake; closes 4401 unauthenticated / 4403 forbidden.
  Awareness user state: `{name, color}` set by client.
- `GET /pages/{id}/presence` → `[{user_id, name, color}]` (who's live)

## Frontend routes (SPA, served at /)

`/login`, `/register`, `/w/{workspaceSlug}` (home), `/w/{slug}/p/{pageId}` (editor),
`/w/{slug}/graph`, `/w/{slug}/search?q=`, `/w/{slug}/tags/{tag}`,
`/w/{slug}/settings` (members/audit), `/settings/tokens`.

Dev: Vite on :5173 proxies `/api` and `/collab` (ws) → `http://localhost:8000`.
