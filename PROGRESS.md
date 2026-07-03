# 開發進度追蹤（跨 session 恢復用）

> 目的：session 中斷 / rate limit / 換 session 時，讀這份檔案即可恢復完整上下文。
> **每完成一個 phase 必須更新此檔。**

## 專案是什麼

Self-hosted collaborative knowledge base（Obsidian-style `[[links]]` + Notion-style 協作 + MCP AI agent 查詢）。
設計文件：`docs/ARCHITECTURE.md`（技術選型與資料流）、`docs/API.md`（前後端 contract，前端依此開發）。

## 關鍵技術決策（勿推翻，除非使用者要求）

- Backend: FastAPI + SQLAlchemy 2 async + PostgreSQL 16 (pgvector/pg_trgm) + Alembic，uv 管理，架構遵循 `~/.claude/skills/python-fastapi-architecture/SKILL.md`（modules/{services,domain,infra,cli} 分層）
- Markdown 為 canonical 內容（`pages.content_md`）；協作時 Yjs doc 為 live state
- 協作：pycrdt（Python 端）+ y-websocket wire protocol（自行實作，訊息型別 0=sync/1=awareness/3=queryAwareness），TipTap fragment 名稱固定 `'default'`
- **Server 負責雙向轉換** md↔ProseMirror-XmlFragment（`modules/collab/domain/y_markdown.py`）：room 建立時從 md seed ydoc；debounce/斷線時 ydoc→md 存檔+版本+重新索引。Client 絕不 setContent
- Wikilink 在編輯器中是**純文字** `[[Title]]`（decoration 顯示，非 custom node）
- 搜尋：tsvector('english') + pg_trgm（CJK 靠 trigram）混合排名 + pgvector 語意搜尋（chunk 層級）
- Embeddings: OpenAI-compatible endpoint，環境變數 KM_EMBEDDINGS_BASE_URL 未設定時優雅停用（mode fallback 到 fulltext）
- 向量欄位用無維度 `Vector()`（精確掃描，公司規模夠用，不建 ANN index）
- Auth: httpOnly cookie session（hash 存 DB）+ `kmt_` API token（MCP/agent 用）
- RBAC: workspace roles owner/admin/member/viewer + page visibility workspace/private + page_shares
- 權限集中在 `modules/workspaces/services/policy.py`
- 跨模組流程放 `orchestration/`（index_page pipeline：parse links → search_text → chunks/embeddings）；routers 呼叫 orchestration 處理內容變更
- Dev DB: docker container `km-dev-pg`，port 5433，user/pass/db 都是 `km`

## 進度

### ✅ 已完成
- [x] 設計文件 docs/ARCHITECTURE.md、docs/API.md
- [x] uv 依賴安裝（fastapi/sqlalchemy/pycrdt 0.14/mcp 1.28/pgvector/markdown-it-py…）
- [x] src/app 目錄骨架（api/shared/infra/orchestration/modules×7/workers/mcpserver）
- [x] shared/config settings（env prefix `KM_`）、exceptions、constants（Role/PageStatus/…）、utils、logging
- [x] infra/db：engine、base、**models.py 全 schema（19 張表）**
- [x] Alembic async 設定 + 初始 migration（`eca98eacb3d9`）已 apply 到 dev DB（extensions vector/pg_trgm 在 env.py 自動建立）
- [x] identity 模組（accounts/api_tokens services、repo、tokens domain、cli create-user）
- [x] workspaces 模組（workspaces service、**policy.py RBAC 中心**、repo、cli）
- [x] audit 模組（record service、repo、cli tail）
- [x] pages 模組（pages/comments/attachments services、repo、mentions domain、cli export）
- [x] links 模組（**parser.py 純函式**：frontmatter/wikilink/strip、repo、links/graph/related services、cli reparse）
- [x] search 模組：chunking domain、embeddings client、search repo（hybrid rank + semantic chunks）

### ✅ 已完成（續）
- [x] search services（hybrid 查詢 + indexer + `_keywords` CJK bigram fallback for /ask）
- [x] orchestration/index_page.py（create/update/delete/restore/snapshot_from_collab）+ seed_demo.py
- [x] collab 模組全部：y_markdown.py 雙向轉換（**roundtrip 測試通過**，注意 pycrdt XmlText.insert 用 UTF-8 byte offset！）、protocol.py（y-websocket wire）、rooms.py（RoomManager + debounce + session-end version）
- [x] api/ 全部 routers + schemas + serializers（lazy-load owner 已改為 explicit s.get，asyncio 下 lazy load 會 MissingGreenlet）
- [x] main.py（SPA serving、/mcp mount + 307 redirect、lifespan wiring）+ cli.py（serve/seed/mcp-stdio + 各模組 sub-CLI）
- [x] mcpserver/ 10 tools（list_workspaces/search_pages/ask/get_page/get_backlinks/get_outgoing_links/get_related_pages/list_tags/list_pages_by_tag/get_page_context），HTTP=Bearer header、stdio=KM_MCP_TOKEN env
- [x] seed（demo1234 × admin/alice/bob@example.com，workspace `engineering` 6 頁互連）
- [x] **pytest 21 passed**（domain: parser/chunking/y_markdown/protocol；API: auth/RBAC/private+shares/links resolve/CJK search/versions/comments mentions/audit/graph/orphans/API token）
- [x] **collab e2e 通過**（scratchpad/collab_e2e.py：雙 client 收斂、409 阻擋 REST 寫入、斷線 snapshot→markdown+version、協作中打的 wikilink 有索引）
- [x] 已修 bugs：boolean cast→case()、/mcp 尾斜線 405、search CJK、pkill 自殺（用 $SP/restart.sh PID file 管理 dev server，port **8600**，8000 被別的服務佔用）

### ✅ 全部完成（2026-07-03）
- [x] Dockerfile（multi-stage npm→python，注意要 COPY README.md 否則 hatchling 炸）+ docker-compose.yml（pgvector db + app，KM_PORT 預設 8080）+ .env.example + README + .gitignore
- [x] **docker compose 全流程驗證通過**（host port 8888，8080 也被佔）：seed → collab e2e（雙 client）→ Playwright UI e2e（登入→tree→編輯器 Yjs 同步→打字含 wikilink→snapshot→backlink→graph→search，截圖在 scratchpad）
- [x] 修：編輯器 seed 時剝除 frontmatter（metadata 由 Info 面板/DB 管理，y_markdown._FRONTMATTER_RE）
- [x] pytest 22 passed / ruff clean

## 目前狀態：開發完成，未 commit

docker stack 還在跑（http://localhost:8888，demo 帳號 admin@example.com / demo1234）。
待使用者決定 commit（commit messages 已建議，見對話）。

後續可做（未承諾）：MCP write-back（draft + review flow，pages.status 已預留）、
attachment 圖片直接貼上、通知 email、SSO/OIDC、graph 篩選器。

## Task list 對照（本 session 的 TaskList 工具）
#1 scaffold ✅ / #2 identity+workspaces ✅ / #3 pages 🔄 / #4 links / #5 search / #6 collab / #7 MCP / #8 frontend（agent 進行中）/ #9 整合驗證

## 恢復指令備忘

```bash
docker start km-dev-pg                  # dev DB (port 5433)
uv run alembic upgrade head             # schema
uv run uvicorn app.main:app --reload    # 後端（完成 main.py 後）
cd frontend && npm run dev              # 前端 dev server (5173, proxy→8000)
```

## 已知風險/注意

- pgvector 無維度 Vector() 已驗證可 migrate；換 embedding model 需 reindex（cli reindex）
- alembic script.py.mako 已加 `import pgvector.sqlalchemy`
- models.py 的 FTS index 用 `text("to_tsvector('english'::regconfig, search_text)")`（literal regconfig 會炸 autogenerate）
- page_links.target_page_id FK 是 CASCADE：刪頁前 service 必須先 unresolve（links repo 有 `unresolve_links_to`）
- 空 `__init__.py` 是 touch 建的，Write 工具會拒寫 → 先 rm 再寫
