# Knowledge Hub

公司內部自架的協作知識庫：Obsidian 式 `[[雙向連結]]` × Notion 式即時多人協作 × MCP 讓 AI agent 直接查詢。

- **多人即時協作編輯**（Yjs CRDT，衝突自動合併、離線重連自動同步、live cursors）
- **Markdown 為本**：所有內容以 markdown 儲存，可整庫匯出成 Obsidian 相容 vault
- **雙向連結**：`[[頁面標題]]`、backlinks、unlinked mentions、related pages、graph view
- **組織能力**：workspace / page tree / folders / tags / typed metadata（frontmatter 自動同步）/ status / owner
- **搜尋**：全文（中英文皆可，tsvector + trigram）＋語意搜尋（pgvector，接任何 OpenAI-compatible embeddings endpoint）
- **權限**：workspace RBAC（owner/admin/member/viewer）＋頁面私有/指定分享＋審計日誌
- **協作周邊**：版本歷史與還原、留言與 @mention 收件匣、附件
- **MCP server**：AI agent（Claude、Cursor…）可搜尋、讀取、追蹤引用關係、帶引文回答

架構詳見 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)，API contract 見 [docs/API.md](docs/API.md)。

## 快速開始（Docker）

Docker 相關檔案集中在 `deploy/`。Compose 預設會把系統資料 bind-mount 到 repo 根目錄的 `data/`：

- `data/postgres/`：PostgreSQL/pgvector（使用者建立的 pages、folders、comments、workspaces、users、indexes）
- `data/uploads/`：附件/上傳檔案

因此服務重啟或 container 重建時，使用者建立的資料不會遺失。

```bash
cp .env.example .env          # 至少改 KM_DB_PASSWORD
mkdir -p data/postgres data/uploads
docker compose --env-file .env -f deploy/docker-compose.yml up -d --build
# 開 http://localhost:8080 ，註冊第一個帳號（自動成為 instance admin）
```

（可選）灌入示範資料：

```bash
docker compose --env-file .env -f deploy/docker-compose.yml exec app uv run km seed
# 登入 admin@example.com / demo1234
```

若要改資料落地位置，設定 `.env` 的 `KM_DATA_DIR`。因為 compose file 位於 `deploy/`，預設值是 `../data`（也就是 repo 根目錄的 `data/`）。

## 本機開發

需求：Python 3.12 + uv、Node 20、Docker（跑 PostgreSQL）。

```bash
# 1. DB（pgvector）
docker run -d --name km-dev-pg -e POSTGRES_USER=km -e POSTGRES_HOST_AUTH_METHOD=trust \
  -e POSTGRES_DB=km -p 5433:5432 pgvector/pgvector:pg16

# 2. 後端
uv sync
uv run alembic upgrade head
uv run km seed                      # 示範資料（可省略）
uv run km serve --reload            # http://localhost:8000

# 3. 前端（另一個終端）
cd src/frontend && npm install
npm run dev                         # http://localhost:5173（proxy 到 :8000）
# 後端不在 8000 時：VITE_BACKEND=localhost:8600 npm run dev
```

測試：`uv run pytest`（需要 dev DB 容器在跑）。

## MCP（AI agent 接入）

每位使用者可在 **Settings → API Tokens** 建立 `kmt_` token，權限與該使用者相同（read-only tools）。

**HTTP transport**（推薦，`claude mcp add` 或任何支援 streamable HTTP 的 client）：

```bash
claude mcp add knowledge-hub --transport http http://your-host:8080/mcp \
  --header "Authorization: Bearer kmt_..."
```

**stdio transport**（Claude Desktop 等）：

```json
{
  "mcpServers": {
    "knowledge-hub": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/knowledge-hub", "km", "mcp-stdio"],
      "env": { "KM_MCP_TOKEN": "kmt_...", "KM_DATABASE_URL": "postgresql+asyncpg://..." }
    }
  }
}
```

提供的 tools：`list_workspaces`、`search_pages`、`ask`（帶引文的知識檢索）、`get_page`、`get_page_context`、`get_backlinks`、`get_outgoing_links`、`get_related_pages`、`list_tags`、`list_pages_by_tag`。

## 營運指令

```bash
uv run km --help                    # 全部指令
uv run km identity create-user ...  # 建帳號（繞過註冊開關）
uv run km pages export <ws-slug>    # 匯出整個 workspace 為 markdown vault
uv run km search reindex <ws-id>    # 重建 chunks + embeddings（換 embedding model 後）
uv run km collab show-md <page-id>  # 檢視協作 doc 目前的 markdown（除錯）
```

## 設定

所有設定透過環境變數（`KM_` 前綴）或 `.env`，完整清單見 [.env.example](.env.example) 與 `src/app/shared/config/settings.py`。語意搜尋為選配：未設定 `KM_EMBEDDINGS_BASE_URL` 時自動退回全文搜尋，設定後跑 `km search reindex` 補齊向量。

> Note: repo/package/display name 已改為 **Knowledge Hub**；CLI 與環境變數前綴仍保留 `km` / `KM_`，避免破壞既有 deployment script。

## 專案結構

```
deploy/
├── Dockerfile             # multi-stage frontend build + backend runtime image
└── docker-compose.yml     # pgvector + app，bind-mount data/postgres 與 data/uploads
src/
├── app/                   # FastAPI backend / MCP server / domain modules
│   ├── api/               # HTTP/WS 介面層（routers、schemas、deps）
│   ├── mcpserver/         # MCP tools（AI agent 介面層）
│   ├── orchestration/     # 跨模組流程（內容變更 → links/search/embeddings 索引管線）
│   ├── infra/db/          # 共用 DB engine 與 schema
│   ├── shared/            # config / exceptions / constants / utils / logging
│   └── modules/           # identity/workspaces/pages/links/search/collab/audit
└── frontend/              # React SPA（TipTap + Yjs 協作編輯器、graph view）
```
