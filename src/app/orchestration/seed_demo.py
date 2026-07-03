"""Demo/starter content: a workspace with interlinked pages exercising every
feature (wikilinks, tags, frontmatter metadata, statuses, comments)."""

from pwdlib import PasswordHash
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.infra import repo as identity_repo
from app.modules.pages.services import comments as comments_service
from app.modules.workspaces.infra import repo as ws_repo
from app.modules.workspaces.services import workspaces as ws_service
from app.orchestration import index_page as pipeline
from app.shared.constants import Role

PAGES = [
    ("產品總覽", None, """---
project: knowledge-map
status_note: living document
---
# 產品總覽

Knowledge Map 是公司內部的知識管理平台。相關文件：

- 系統架構請見 [[系統架構]]
- API 規格請見 [[API 設計]]
- 部署流程請見 [[部署 SOP]]

## 目標

讓專案文件、技術決策、會議紀錄可以互相連結、全文搜尋，並讓 AI agent 透過 MCP 查詢。
""", ["overview", "product"]),
    ("系統架構", None, """---
project: knowledge-map
system: backend
---
# 系統架構

後端使用 FastAPI + PostgreSQL，即時協作透過 Yjs CRDT。詳細 API 見 [[API 設計]]。

## 元件

- Web API（FastAPI）
- 協作服務（WebSocket + CRDT）
- 搜尋（全文 + 向量），設計討論在 [[搜尋設計討論]]
""", ["architecture", "backend"]),
    ("API 設計", None, """---
project: knowledge-map
system: backend
owner_note: API guild
---
# API 設計

REST API 遵循資源導向設計，參考 [[系統架構]]。

## 認證

Cookie session 給瀏覽器、Bearer token 給 agent。部署相關注意事項見 [[部署 SOP]]。
""", ["api", "backend"]),
    ("部署 SOP", None, """---
project: knowledge-map
system: infra
---
# 部署 SOP

1. `docker compose build`
2. `docker compose up -d`
3. 確認 `/healthz`

架構背景請讀 [[系統架構]]。
""", ["sop", "infra"]),
    ("搜尋設計討論", None, """# 搜尋設計討論

會議紀錄 2026-06-30：決定採用 hybrid search（全文 + 向量）。

結論已納入 [[系統架構]]。待辦：

- [ ] 評估 embedding model
- [x] pg_trgm 中文驗證
""", ["meeting-notes", "search"]),
    ("孤島頁面範例", None, """# 孤島頁面範例

這一頁沒有任何連結，會出現在 orphan pages 清單，用來示範 graph 功能。
""", []),
]


async def seed(s: AsyncSession) -> dict:
    hasher = PasswordHash.recommended()
    users = {}
    for email, name, is_admin in [
        ("admin@example.com", "Admin", True),
        ("alice@example.com", "Alice Chen", False),
        ("bob@example.com", "Bob Lin", False),
    ]:
        existing = await identity_repo.get_user_by_email(s, email)
        users[email] = existing or await identity_repo.create_user(
            s, email, name, hasher.hash("demo1234"), is_admin
        )

    if await ws_repo.get_by_slug(s, "engineering"):
        return {"skipped": "workspace 'engineering' already exists"}

    admin = users["admin@example.com"]
    ws, _ = await ws_service.create(
        s, admin, "Engineering", "engineering", "工程團隊知識庫", "🛠️"
    )
    await ws_repo.add_member(s, ws.id, users["alice@example.com"].id, Role.MEMBER)
    await ws_repo.add_member(s, ws.id, users["bob@example.com"].id, Role.MEMBER)

    created = {}
    for title, parent_title, content, tags in PAGES:
        page = await pipeline.create_page(
            s, admin, ws.id,
            title=title,
            parent_id=created[parent_title].id if parent_title else None,
            content_md=content,
            tags=tags,
        )
        created[title] = page

    await comments_service.create(
        s, users["alice@example.com"], created["API 設計"].id,
        "@bob 認證那段可以再補上 token 輪替的說明嗎？", None,
    )
    return {
        "workspace": ws.slug,
        "pages": len(created),
        "logins": {u.email: "demo1234" for u in users.values()},
    }
