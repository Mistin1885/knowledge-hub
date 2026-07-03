"""API-level tests: auth, RBAC, pages, links, search, versions, comments."""

from tests.conftest import make_workspace, register_and_login


async def test_register_login_me(client):
    await register_and_login(client, "u1@test.com", "U One")
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "u1@test.com"
    assert body["is_admin"] is True  # first user becomes instance admin


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
