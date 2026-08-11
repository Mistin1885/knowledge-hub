"""API-level tests: auth, RBAC, pages, links, search, versions, comments."""

from tests.conftest import make_workspace, register_and_login


async def test_register_login_me(client):
    await register_and_login(client, "u1@test.com", "U One")
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "u1@test.com"
    assert body["is_admin"] is True  # first user becomes instance admin


async def test_new_users_receive_read_only_demo_access(client):
    await register_and_login(client, "owner@test.com", "Owner")
    demo = await make_workspace(client, "demo")

    await register_and_login(client, "reader@test.com", "Reader")
    workspaces = (await client.get("/api/v1/workspaces")).json()

    membership = next(item for item in workspaces if item["id"] == demo["id"])
    assert membership["slug"] == "demo"
    assert membership["my_role"] == "viewer"
    assert (
        await client.post(
            f"/api/v1/workspaces/{demo['id']}/pages",
            json={"title": "Cannot create"},
        )
    ).status_code == 403


async def test_me_unauthenticated(client):
    assert (await client.get("/api/v1/auth/me")).status_code == 401


async def test_page_lifecycle_links_and_search(client, alice):
    ws = await make_workspace(client)
    wid = ws["id"]

    a = (
        await client.post(
            f"/api/v1/workspaces/{wid}/pages",
            json={"title": "架構決策", "content_md": "# 架構決策\n\n參考 [[部署指南]] 進行部署。"},
        )
    ).json()
    # link is unresolved until the target exists
    links = (await client.get(f"/api/v1/pages/{a['id']}/links")).json()["outgoing"]
    assert links[0]["target_title"] == "部署指南" and links[0]["resolved"] is False

    b = (
        await client.post(
            f"/api/v1/workspaces/{wid}/pages",
            json={"title": "部署指南", "content_md": "# 部署指南\n\n步驟一。"},
        )
    ).json()
    # creating the target resolves the pending link
    links = (await client.get(f"/api/v1/pages/{a['id']}/links")).json()["outgoing"]
    assert links[0]["resolved"] is True and links[0]["page"]["id"] == b["id"]
    backlinks = (await client.get(f"/api/v1/pages/{b['id']}/backlinks")).json()
    assert [x["page"]["id"] for x in backlinks] == [a["id"]]

    # CJK fulltext search
    hits = (await client.get(f"/api/v1/workspaces/{wid}/search?q=部署")).json()
    titles = [r["page"]["title"] for r in hits["results"]]
    assert "部署指南" in titles and hits["mode_used"] == "fulltext"

    # frontmatter tags/metadata merge on update
    resp = await client.patch(
        f"/api/v1/pages/{b['id']}",
        json={"content_md": "---\ntags: [sop]\nsystem: infra\n---\n# 部署指南\n\n更新。"},
    )
    detail = resp.json()
    assert "sop" in detail["tags"] and detail["metadata"]["system"] == "infra"

    # version history + restore
    versions = (await client.get(f"/api/v1/pages/{b['id']}/versions")).json()
    assert len(versions) == 2
    first = versions[-1]
    restored = (
        await client.post(f"/api/v1/pages/{b['id']}/versions/{first['id']}/restore")
    ).json()
    assert "步驟一" in restored["content_md"]

    # delete keeps inbound links as unresolved backreferences
    assert (await client.delete(f"/api/v1/pages/{b['id']}")).status_code == 204
    links = (await client.get(f"/api/v1/pages/{a['id']}/links")).json()["outgoing"]
    assert links[0]["resolved"] is False


async def test_rbac_and_private_pages(client, alice):
    ws = await make_workspace(client)
    wid = ws["id"]
    secret = (
        await client.post(
            f"/api/v1/workspaces/{wid}/pages",
            json={"title": "Secret", "visibility": "private", "content_md": "hidden"},
        )
    ).json()
    public = (
        await client.post(f"/api/v1/workspaces/{wid}/pages", json={"title": "Public"})
    ).json()

    await register_and_login(client, "viewer@test.com", "Viewer")  # switches session
    # not a member yet: workspace hidden
    assert (await client.get(f"/api/v1/workspaces/{wid}")).status_code == 404

    # re-login as alice to invite viewer
    await client.post(
        "/api/v1/auth/login", json={"email": "alice@test.com", "password": "password123"}
    )
    resp = await client.post(
        f"/api/v1/workspaces/{wid}/members", json={"email": "viewer@test.com", "role": "viewer"}
    )
    assert resp.status_code == 201

    await client.post(
        "/api/v1/auth/login", json={"email": "viewer@test.com", "password": "password123"}
    )
    # viewer sees public page but not the private one
    titles = [p["title"] for p in (await client.get(f"/api/v1/workspaces/{wid}/pages")).json()]
    assert "Public" in titles and "Secret" not in titles
    assert (await client.get(f"/api/v1/pages/{secret['id']}")).status_code == 404
    # viewer cannot edit
    resp = await client.patch(f"/api/v1/pages/{public['id']}", json={"title": "Nope"})
    assert resp.status_code == 403
    # viewer cannot invite
    resp = await client.post(
        f"/api/v1/workspaces/{wid}/members", json={"email": "x@test.com", "role": "member"}
    )
    assert resp.status_code == 403

    # share the private page with viewer -> now visible
    await client.post(
        "/api/v1/auth/login", json={"email": "alice@test.com", "password": "password123"}
    )
    viewer_id = next(
        m["user_id"]
        for m in (await client.get(f"/api/v1/workspaces/{wid}/members")).json()
        if m["email"] == "viewer@test.com"
    )
    await client.post(f"/api/v1/pages/{secret['id']}/shares", json={"user_id": viewer_id})
    await client.post(
        "/api/v1/auth/login", json={"email": "viewer@test.com", "password": "password123"}
    )
    assert (await client.get(f"/api/v1/pages/{secret['id']}")).status_code == 200


async def test_comments_mentions_audit(client, alice):
    ws = await make_workspace(client)
    wid = ws["id"]
    page = (
        await client.post(f"/api/v1/workspaces/{wid}/pages", json={"title": "Notes"})
    ).json()

    await register_and_login(client, "bob@test.com", "Bob Wu")
    await client.post(
        "/api/v1/auth/login", json={"email": "alice@test.com", "password": "password123"}
    )
    await client.post(f"/api/v1/workspaces/{wid}/members", json={"email": "bob@test.com", "role": "member"})

    comment = (
        await client.post(
            f"/api/v1/pages/{page['id']}/comments", json={"body_md": "@bob 請看一下"}
        )
    ).json()
    assert [m["name"] for m in comment["mentions"]] == ["Bob Wu"]

    # bob sees the mention in his inbox
    await client.post(
        "/api/v1/auth/login", json={"email": "bob@test.com", "password": "password123"}
    )
    inbox = (await client.get("/api/v1/mentions")).json()
    assert len(inbox) == 1 and inbox[0]["read"] is False
    await client.post(f"/api/v1/mentions/{comment['id']}/read")
    assert (await client.get("/api/v1/mentions")).json()[0]["read"] is True

    # audit log requires admin; alice (owner) can read it and sees actions
    await client.post(
        "/api/v1/auth/login", json={"email": "alice@test.com", "password": "password123"}
    )
    audit = (await client.get(f"/api/v1/workspaces/{wid}/audit")).json()
    actions = {item["action"] for item in audit["items"]}
    assert {"workspace.create", "page.create", "member.add", "comment.create"} <= actions
    # bob (member) cannot
    await client.post(
        "/api/v1/auth/login", json={"email": "bob@test.com", "password": "password123"}
    )
    assert (await client.get(f"/api/v1/workspaces/{wid}/audit")).status_code == 403


async def test_audit_supports_system_actor_and_structured_detail(client, alice):
    from uuid import UUID

    from app.infra.db.engine import session_factory
    from app.infra.db.models import AuditLog

    ws = await make_workspace(client)
    async with session_factory() as session:
        session.add_all(
            [
                AuditLog(
                    workspace_id=UUID(ws["id"]),
                    actor_id=None,
                    action="system.repair" if index == 0 else "system.event",
                    target_type="workspace",
                    target_id=UUID(ws["id"]),
                    target_title=ws["name"],
                    detail={"fields": ["role", "joined_at"], "count": index + 2},
                )
                for index in range(25)
            ]
        )
        await session.commit()

    first = await client.get(
        f"/api/v1/workspaces/{ws['id']}/audit", params={"page": 1, "page_size": 20}
    )
    second = await client.get(
        f"/api/v1/workspaces/{ws['id']}/audit", params={"page": 2, "page_size": 20}
    )
    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["total"] == 26
    assert first.json()["page"] == 1 and first.json()["page_size"] == 20
    assert len(first.json()["items"]) == 20 and len(second.json()["items"]) == 6
    ids = [item["id"] for item in [*first.json()["items"], *second.json()["items"]]]
    assert len(ids) == len(set(ids)) == 26
    entry = next(
        item
        for item in [*first.json()["items"], *second.json()["items"]]
        if item["action"] == "system.repair"
    )
    assert entry["actor"] is None
    assert entry["detail"] == {"fields": ["role", "joined_at"], "count": 2}


async def test_member_directory_paginates_all_users_and_persists_last_login(client, alice):
    from datetime import UTC, datetime

    from app.infra.db.engine import session_factory
    from app.infra.db.models import User

    ws = await make_workspace(client)
    wid = ws["id"]

    await register_and_login(client, "directory-user@test.com", "Directory User")
    await client.post("/api/v1/auth/logout")
    await client.post(
        "/api/v1/auth/login", json={"email": "alice@test.com", "password": "password123"}
    )

    async with session_factory() as session:
        session.add_all(
            [
                User(
                    email=f"user-{index:02d}@test.com",
                    name=f"User {index:02d}",
                    password_hash="not-used-in-this-test",
                    is_admin=False,
                    last_login_at=datetime(2026, 1, index + 1, tzinfo=UTC),
                )
                for index in range(20)
            ]
        )
        await session.commit()

    first = (
        await client.get(
            f"/api/v1/workspaces/{wid}/member-directory", params={"page": 1, "page_size": 20}
        )
    ).json()
    second = (
        await client.get(
            f"/api/v1/workspaces/{wid}/member-directory", params={"page": 2, "page_size": 20}
        )
    ).json()
    assert first["total"] == 22
    assert first["page"] == 1 and first["page_size"] == 20 and len(first["items"]) == 20
    assert len(second["items"]) == 2
    assert first["items"][0]["role"] == "owner"

    directory_user = next(
        item
        for item in [*first["items"], *second["items"]]
        if item["email"] == "directory-user@test.com"
    )
    assert directory_user["role"] is None and directory_user["joined_at"] is None
    assert directory_user["last_login_at"] is not None

    added = await client.post(
        f"/api/v1/workspaces/{wid}/members",
        json={"email": directory_user["email"], "role": "viewer"},
    )
    assert added.status_code == 201
    directory_user = next(
        item
        for item in (
            await client.get(f"/api/v1/workspaces/{wid}/member-directory")
        ).json()["items"]
        if item["email"] == "directory-user@test.com"
    )
    assert directory_user["role"] == "viewer" and directory_user["joined_at"] is not None

    await client.post(
        "/api/v1/auth/login",
        json={"email": "directory-user@test.com", "password": "password123"},
    )
    assert (
        await client.get(f"/api/v1/workspaces/{wid}/member-directory")
    ).status_code == 403

    await client.post(
        "/api/v1/auth/login", json={"email": "alice@test.com", "password": "password123"}
    )
    changed = await client.patch(
        f"/api/v1/workspaces/{wid}/members/{directory_user['user_id']}",
        json={"role": "admin"},
    )
    assert changed.status_code == 200
    directory_user = next(
        item
        for item in (
            await client.get(f"/api/v1/workspaces/{wid}/member-directory")
        ).json()["items"]
        if item["email"] == "directory-user@test.com"
    )
    assert directory_user["role"] == "admin"

    removed = await client.delete(
        f"/api/v1/workspaces/{wid}/members/{directory_user['user_id']}"
    )
    assert removed.status_code == 204
    all_entries = []
    for page in (1, 2):
        all_entries.extend(
            (
                await client.get(
                    f"/api/v1/workspaces/{wid}/member-directory", params={"page": page}
                )
            ).json()["items"]
        )
    directory_user = next(
        item for item in all_entries if item["email"] == "directory-user@test.com"
    )
    assert directory_user["role"] is None and directory_user["joined_at"] is None
    assert directory_user["last_login_at"] is not None


async def test_graph_related_orphans(client, alice):
    ws = await make_workspace(client)
    wid = ws["id"]
    hub = (
        await client.post(
            f"/api/v1/workspaces/{wid}/pages",
            json={"title": "Hub", "content_md": "[[Spoke]]", "tags": ["core"]},
        )
    ).json()
    spoke = (
        await client.post(
            f"/api/v1/workspaces/{wid}/pages",
            json={"title": "Spoke", "content_md": "back to [[Hub]]", "tags": ["core"]},
        )
    ).json()
    await client.post(f"/api/v1/workspaces/{wid}/pages", json={"title": "Lonely"})

    graph = (await client.get(f"/api/v1/workspaces/{wid}/graph")).json()
    ids = {n["id"] for n in graph["nodes"]}
    assert {hub["id"], spoke["id"], "tag:core"} <= ids
    assert any(e["kind"] == "link" for e in graph["edges"])
    assert any(e["kind"] == "tag" for e in graph["edges"])

    limited = (await client.get(f"/api/v1/workspaces/{wid}/graph?limit=2")).json()
    limited_ids = {node["id"] for node in limited["nodes"]}
    assert len(limited_ids) == 2
    assert all(
        edge["source"] in limited_ids and edge["target"] in limited_ids
        for edge in limited["edges"]
    )
    assert (await client.get(f"/api/v1/workspaces/{wid}/graph?limit=0")).status_code == 422

    other_ws = await make_workspace(client, "Other graph")
    other_wid = other_ws["id"]
    other_spoke = (
        await client.post(
            f"/api/v1/workspaces/{other_wid}/pages", json={"title": "Other Spoke"}
        )
    ).json()
    other_hub = (
        await client.post(
            f"/api/v1/workspaces/{other_wid}/pages",
            json={"title": "Other Hub", "content_md": "[[Other Spoke]]"},
        )
    ).json()
    first_workspace_graph = (
        await client.get(f"/api/v1/workspaces/{wid}/graph?limit=1000")
    ).json()
    assert {other_hub["id"], other_spoke["id"]}.isdisjoint(
        {node["id"] for node in first_workspace_graph["nodes"]}
    )
    other_workspace_graph = (
        await client.get(f"/api/v1/workspaces/{other_wid}/graph?limit=1000")
    ).json()
    assert {other_hub["id"], other_spoke["id"]} <= {
        node["id"] for node in other_workspace_graph["nodes"]
    }

    orphans = (await client.get(f"/api/v1/workspaces/{wid}/orphans")).json()
    assert [p["title"] for p in orphans] == ["Lonely"]

    related = (await client.get(f"/api/v1/pages/{hub['id']}/related")).json()
    assert related[0]["page"]["id"] == spoke["id"]
    assert set(related[0]["reasons"]) == {"links", "tags"}


async def test_api_token_auth(client, alice):
    created = (await client.post("/api/v1/auth/tokens", json={"name": "agent"})).json()
    token = created["token"]
    assert token.startswith("kmt_")

    # fresh client without cookies, bearer only
    import httpx

    from app.main import app

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as agent_client:
        me = await agent_client.get("/api/v1/auth/me")
        assert me.status_code == 200 and me.json()["email"] == "alice@test.com"

    # revoke kills it
    await client.delete(f"/api/v1/auth/tokens/{created['id']}")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as agent_client:
        assert (await agent_client.get("/api/v1/auth/me")).status_code == 401


async def test_folder_children_with_preview(client, alice):
    ws = await make_workspace(client)
    wid = ws["id"]
    folder = (
        await client.post(
            f"/api/v1/workspaces/{wid}/pages", json={"title": "Specs", "is_folder": True}
        )
    ).json()
    await client.post(
        f"/api/v1/workspaces/{wid}/pages",
        json={
            "title": "Login API",
            "parent_id": folder["id"],
            "content_md": "# Login API\n\n使用 cookie session 進行認證，詳見規格。",
            "metadata": {"note": "reviewed by alice"},
        },
    )
    # private child of another member must not appear for alice
    await register_and_login(client, "other@test.com", "Other")
    await client.post(
        "/api/v1/auth/login", json={"email": "alice@test.com", "password": "password123"}
    )
    await client.post(
        f"/api/v1/workspaces/{wid}/members", json={"email": "other@test.com", "access": "write"}
    )
    await client.post(
        "/api/v1/auth/login", json={"email": "other@test.com", "password": "password123"}
    )
    await client.post(
        f"/api/v1/workspaces/{wid}/pages",
        json={"title": "Other's secret", "parent_id": folder["id"], "visibility": "private"},
    )
    await client.post(
        "/api/v1/auth/login", json={"email": "alice@test.com", "password": "password123"}
    )

    children = (await client.get(f"/api/v1/pages/{folder['id']}/children")).json()
    titles = [c["page"]["title"] for c in children]
    assert "Login API" in titles and "Other's secret" not in titles
    login_api = next(c for c in children if c["page"]["title"] == "Login API")
    assert "cookie session" in login_api["preview"]
    assert "Login API" not in login_api["preview"]  # title line stripped
    assert login_api["page"]["metadata"]["note"] == "reviewed by alice"


async def test_export_page_folder_and_workspace(client, alice):
    import io
    import zipfile

    ws = await make_workspace(client)
    wid = ws["id"]
    folder = (
        await client.post(
            f"/api/v1/workspaces/{wid}/pages", json={"title": "Guides", "is_folder": True}
        )
    ).json()
    page = (
        await client.post(
            f"/api/v1/workspaces/{wid}/pages",
            json={"title": "Setup", "parent_id": folder["id"], "content_md": "# Setup\nSteps."},
        )
    ).json()
    await client.post(
        f"/api/v1/workspaces/{wid}/pages", json={"title": "Root note", "content_md": "hello"}
    )

    # single page -> markdown file
    resp = await client.get(f"/api/v1/pages/{page['id']}/export")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/markdown")
    assert 'filename="Setup.md"' in resp.headers["content-disposition"]
    assert resp.text == "# Setup\nSteps."

    # folder -> zip of its subtree
    resp = await client.get(f"/api/v1/pages/{folder['id']}/export")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    assert "Setup.md" in zf.namelist()
    assert zf.read("Setup.md").decode() == "# Setup\nSteps."

    # workspace -> zip preserving folder structure
    resp = await client.get(f"/api/v1/workspaces/{wid}/export")
    assert resp.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = zf.namelist()
    assert "Guides/Setup.md" in names
    assert "Root note.md" in names


async def test_move_page_between_levels(client, alice):
    ws = await make_workspace(client)
    wid = ws["id"]
    folder = (
        await client.post(
            f"/api/v1/workspaces/{wid}/pages", json={"title": "F", "is_folder": True}
        )
    ).json()
    page = (
        await client.post(f"/api/v1/workspaces/{wid}/pages", json={"title": "P"})
    ).json()

    # root -> folder
    resp = await client.patch(f"/api/v1/pages/{page['id']}", json={"parent_id": folder["id"]})
    assert resp.status_code == 200 and resp.json()["parent_id"] == folder["id"]

    # folder -> root (explicit null must clear the parent)
    resp = await client.patch(f"/api/v1/pages/{page['id']}", json={"parent_id": None})
    assert resp.status_code == 200 and resp.json()["parent_id"] is None

    # cycle guard: folder cannot move under its own descendant
    await client.patch(f"/api/v1/pages/{page['id']}", json={"parent_id": folder["id"]})
    resp = await client.patch(f"/api/v1/pages/{folder['id']}", json={"parent_id": page["id"]})
    assert resp.status_code == 422


async def test_attachment_upload_roundtrip(client, alice):
    ws = await make_workspace(client)
    wid = ws["id"]
    page = (
        await client.post(f"/api/v1/workspaces/{wid}/pages", json={"title": "Pics"})
    ).json()

    png = b"\x89PNG\r\n\x1a\n" + b"0" * 32
    resp = await client.post(
        f"/api/v1/pages/{page['id']}/attachments",
        files={"file": ("shot.png", png, "image/png")},
    )
    assert resp.status_code == 201, resp.text
    att = resp.json()
    assert att["url"].startswith("/api/v1/attachments/")

    resp = await client.get(att["url"])
    assert resp.status_code == 200
    assert resp.content == png
    listed = (await client.get(f"/api/v1/pages/{page['id']}/attachments")).json()
    assert [item["id"] for item in listed] == [att["id"]]
    assert listed[0]["created_at"]


async def test_vault_file_nodes_preview_download_move_and_alias(client, alice):
    ws = await make_workspace(client)
    wid = ws["id"]
    folder = (
        await client.post(
            f"/api/v1/workspaces/{wid}/pages",
            json={"title": "Design", "is_folder": True},
        )
    ).json()

    pdf = b"%PDF-1.7\n" + b"vault-pdf" * 8
    resp = await client.post(
        f"/api/v1/workspaces/{wid}/files?parent_id={folder['id']}",
        files={"file": ("spec.pdf", pdf, "application/octet-stream")},
    )
    assert resp.status_code == 201, resp.text
    node = resp.json()
    assert node["node_type"] == "file"
    assert node["parent_id"] == folder["id"]
    assert node["content_type"] == "application/pdf"
    assert node["size"] == len(pdf)
    assert node["preview_kind"] == "pdf"
    assert node["created_at"]

    preview = await client.get(node["preview_url"])
    assert preview.status_code == 200
    assert preview.content == pdf
    assert preview.headers["content-disposition"].startswith("inline")
    assert preview.headers["x-content-type-options"] == "nosniff"

    download = await client.get(node["download_url"])
    assert download.status_code == 200
    assert download.content == pdf
    assert download.headers["content-disposition"].startswith("attachment")

    resolved = await client.get(
        f"/api/v1/workspaces/{wid}/resolve", params={"title": "Design/spec.pdf"}
    )
    assert resolved.status_code == 200
    assert resolved.json()["id"] == node["id"]

    # Folder rename records aliases for the whole subtree, so old links stay valid.
    renamed = await client.patch(f"/api/v1/pages/{folder['id']}", json={"title": "Product"})
    assert renamed.status_code == 200
    old_path = await client.get(
        f"/api/v1/workspaces/{wid}/resolve", params={"title": "Design/spec.pdf"}
    )
    assert old_path.json()["id"] == node["id"]
    new_path = await client.get(
        f"/api/v1/workspaces/{wid}/resolve", params={"title": "Product/spec.pdf"}
    )
    assert new_path.json()["id"] == node["id"]


async def test_idempotent_obsidian_import_counts_images_and_persisted_order(client, alice):
    ws = await make_workspace(client)
    wid = ws["id"]
    png_v1 = b"\x89PNG\r\n\x1a\n" + b"first-image"

    imported = await client.post(
        f"/api/v1/workspaces/{wid}/import",
        params={"relative_path": "Team Vault/assets/pic.png"},
        files={"file": ("pic.png", png_v1, "image/png")},
    )
    assert imported.status_code == 200, imported.text
    first = imported.json()
    assert first["action"] == "created"
    assert first["folders_created"] == 2
    file_id = first["page"]["id"]

    long_name = ("長檔名" * 40) + ".png"
    long_file = await client.post(
        f"/api/v1/workspaces/{wid}/import",
        params={"relative_path": f"Long names/{long_name}"},
        files={"file": (long_name, png_v1, "image/png")},
    )
    assert long_file.status_code == 200, long_file.text
    assert long_file.json()["action"] == "created"

    duplicate_name = await client.post(
        f"/api/v1/workspaces/{wid}/import",
        params={"relative_path": "Other Vault/pic.png"},
        files={"file": ("pic.png", png_v1, "image/png")},
    )
    assert duplicate_name.status_code == 200, duplicate_name.text

    repeated = await client.post(
        f"/api/v1/workspaces/{wid}/import",
        params={"relative_path": "Team Vault/assets/pic.png"},
        files={"file": ("pic.png", png_v1, "image/png")},
    )
    assert repeated.json()["action"] == "skipped"
    assert repeated.json()["page"]["id"] == file_id

    png_v2 = b"\x89PNG\r\n\x1a\n" + b"updated-image"
    updated = await client.post(
        f"/api/v1/workspaces/{wid}/import",
        params={"relative_path": "Team Vault/assets/pic.png"},
        files={"file": ("pic.png", png_v2, "image/png")},
    )
    assert updated.json()["action"] == "updated"
    assert updated.json()["page"]["id"] == file_id
    assert (await client.get(f"/api/v1/files/{file_id}/preview")).content == png_v2

    note_content = (
        b"# Guide\n\n"
        b"| Name | Value |\n"
        b"| --- | --- |\n"
        b"| first | second |\n\n"
        b"![[pic.png]]\n\n"
        b"![[missing-image.png]]\n\n"
        b'![legacy](../missing/legacy.png "caption")\n'
        b"![orphan](/api/v1/files/22222222-2222-2222-2222-222222222222/preview)\n"
    )
    note = await client.post(
        f"/api/v1/workspaces/{wid}/import",
        params={"relative_path": "Team Vault/notes/Guide.md"},
        files={"file": ("Guide.md", note_content, "text/markdown")},
    )
    assert note.status_code == 200, note.text
    assert note.json()["action"] == "created"
    detail = (await client.get(f"/api/v1/pages/{note.json()['page']['id']}")).json()
    assert f"![pic](/api/v1/files/{file_id}/preview)" in detail["content_md"]
    assert "![[missing-image.png]]" in detail["content_md"]
    assert '![legacy](../missing/legacy.png "caption")' in detail["content_md"]
    assert "Image not found: missing-image.png" in note.json()["warnings"]
    assert "Image not found: ../missing/legacy.png" in note.json()["warnings"]

    repeated_note = await client.post(
        f"/api/v1/workspaces/{wid}/import",
        params={"relative_path": "Team Vault/notes/Guide.md"},
        files={"file": ("Guide.md", note_content, "text/markdown")},
    )
    assert repeated_note.json()["action"] == "skipped"

    # The sidebar endpoint returns only one lightweight level at a time.
    root_tree = (await client.get(f"/api/v1/workspaces/{wid}/tree")).json()
    root_titles = {node["title"] for node in root_tree}
    assert {"Team Vault", "Long names", "Other Vault"} <= root_titles
    assert "assets" not in root_titles and "Guide" not in root_titles
    tree_vault = next(node for node in root_tree if node["title"] == "Team Vault")
    assert tree_vault["file_count"] == 2 and tree_vault["has_children"] is True
    assert "tags" not in tree_vault and "metadata" not in tree_vault and "owner" not in tree_vault

    vault_children = (
        await client.get(
            f"/api/v1/workspaces/{wid}/tree", params={"parent_id": tree_vault["id"]}
        )
    ).json()
    assert {node["title"] for node in vault_children} == {"assets", "notes"}
    assert {node["title"]: node["file_count"] for node in vault_children} == {
        "assets": 1,
        "notes": 1,
    }

    isolated = await make_workspace(client, "Isolated")
    await client.post(
        f"/api/v1/workspaces/{isolated['id']}/pages", json={"title": "Only elsewhere"}
    )
    assert "Only elsewhere" not in {
        node["title"] for node in (await client.get(f"/api/v1/workspaces/{wid}/tree")).json()
    }

    # ZIP exports carry binaries and portable relative paths. Unresolved links
    # remain exactly as the user wrote them instead of disappearing.
    import io
    import zipfile

    exported = await client.get(f"/api/v1/workspaces/{wid}/export")
    assert exported.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(exported.content))
    exported_note = zf.read("Team Vault/notes/Guide.md").decode()
    assert "![pic](<../assets/pic.png>)" in exported_note
    assert "![[missing-image.png]]" in exported_note
    assert '![legacy](../missing/legacy.png "caption")' in exported_note
    assert (
        "![orphan](/api/v1/files/22222222-2222-2222-2222-222222222222/preview)"
        in exported_note
    )
    assert "| Name | Value |\n| --- | --- |\n| first | second |" in exported_note
    assert zf.read("Team Vault/assets/pic.png") == png_v2

    single_export = await client.get(f"/api/v1/pages/{note.json()['page']['id']}/export")
    assert "![[pic.png]]" in single_export.text
    assert "![[missing-image.png]]" in single_export.text

    # An external re-import must invalidate stale Yjs state; otherwise opening
    # the editor can overwrite the corrected Markdown with an older snapshot.
    from uuid import UUID

    from app.infra.db.engine import session_factory
    from app.infra.db.models import PageYDoc

    note_id = UUID(note.json()["page"]["id"])
    async with session_factory() as session:
        session.add(PageYDoc(page_id=note_id, state=b"stale"))
        await session.commit()
    changed_content = note_content + b"\nUpdated externally.\n"
    changed_note = await client.post(
        f"/api/v1/workspaces/{wid}/import",
        params={"relative_path": "Team Vault/notes/Guide.md"},
        files={"file": ("Guide.md", changed_content, "text/markdown")},
    )
    assert changed_note.json()["action"] == "updated"
    async with session_factory() as session:
        assert await session.get(PageYDoc, note_id) is None

    pages = (await client.get(f"/api/v1/workspaces/{wid}/pages")).json()
    vault_folder = next(page for page in pages if page["title"] == "Team Vault")
    assets_folder = next(page for page in pages if page["title"] == "assets")
    notes_folder = next(page for page in pages if page["title"] == "notes")
    assert vault_folder["file_count"] == 2
    assert assets_folder["file_count"] == 1
    assert notes_folder["file_count"] == 1

    a = (await client.post(f"/api/v1/workspaces/{wid}/pages", json={"title": "A"})).json()
    await client.post(f"/api/v1/workspaces/{wid}/pages", json={"title": "B"})
    c = (await client.post(f"/api/v1/workspaces/{wid}/pages", json={"title": "C"})).json()
    moved = await client.patch(
        f"/api/v1/pages/{c['id']}/move",
        json={"parent_id": None, "before_id": a["id"]},
    )
    assert moved.status_code == 200, moved.text
    roots = [
        page["title"]
        for page in (await client.get(f"/api/v1/workspaces/{wid}/pages")).json()
        if page["parent_id"] is None
    ]
    assert roots.index("C") < roots.index("A") < roots.index("B")

    assert (await client.delete(f"/api/v1/pages/{file_id}")).status_code == 204
    pages = (await client.get(f"/api/v1/workspaces/{wid}/pages")).json()
    vault_folder = next(page for page in pages if page["title"] == "Team Vault")
    assert vault_folder["file_count"] == 1


async def test_non_previewable_vault_file_metadata_and_download(client, alice):
    ws = await make_workspace(client)
    payload = b"PK\x03\x04not-really-a-zip"
    resp = await client.post(
        f"/api/v1/workspaces/{ws['id']}/files",
        files={"file": ("archive.zip", payload, "application/zip")},
    )
    assert resp.status_code == 201, resp.text
    node = resp.json()
    assert node["preview_kind"] is None
    assert node["preview_url"] is None
    assert node["size"] == len(payload)
    assert (await client.get(f"/api/v1/files/{node['id']}/preview")).status_code == 422
    assert (await client.get(node["download_url"])).content == payload


async def test_huge_document_write_and_tail_search(client, alice):
    ws = await make_workspace(client)
    wid = ws["id"]

    # ~2 MB of unique words: a page-level tsvector index would reject this
    # (>1 MB serialized tsvector); chunk-level FTS must accept it and still
    # find a term that only appears at the very end of the document
    body = " ".join(f"unique{i}word" for i in range(200_000))
    content = f"# Huge\n\n{body}\n\nzebrafinch conclusion here."
    resp = await client.post(
        f"/api/v1/workspaces/{wid}/pages",
        json={"title": "Huge Doc", "content_md": content},
    )
    assert resp.status_code == 201, resp.text

    hits = (await client.get(f"/api/v1/workspaces/{wid}/search?q=zebrafinch")).json()
    assert "Huge Doc" in [r["page"]["title"] for r in hits["results"]]


async def test_title_only_page_still_searchable(client, alice):
    ws = await make_workspace(client)
    wid = ws["id"]
    await client.post(f"/api/v1/workspaces/{wid}/pages", json={"title": "Roadmap 2027"})

    hits = (await client.get(f"/api/v1/workspaces/{wid}/search?q=Roadmap")).json()
    assert "Roadmap 2027" in [r["page"]["title"] for r in hits["results"]]


async def test_oversized_token_sanitized_from_preview(client, alice):
    ws = await make_workspace(client)
    wid = ws["id"]
    folder = (
        await client.post(
            f"/api/v1/workspaces/{wid}/pages", json={"title": "F", "is_folder": True}
        )
    ).json()

    blob = "Zm9vYmFy" * 50  # 400-char whitespace-free run (e.g. pasted base64)
    resp = await client.post(
        f"/api/v1/workspaces/{wid}/pages",
        json={
            "title": "Blobby",
            "parent_id": folder["id"],
            "content_md": f"{blob}\n\nreadable summary text follows the blob.",
        },
    )
    assert resp.status_code == 201, resp.text

    children = (await client.get(f"/api/v1/pages/{folder['id']}/children")).json()
    preview = next(c["preview"] for c in children if c["page"]["title"] == "Blobby")
    assert blob[:50] not in preview
    assert "readable summary text" in preview
