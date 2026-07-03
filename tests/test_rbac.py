"""Permission-model tests: full lockout for non-members, read/write access
levels, `access` grant API, and revocation side effects."""

from app.shared.constants import Permission, Role, role_permissions
from tests.conftest import make_workspace, register_and_login


def test_role_permission_mapping():
    assert role_permissions(Role.VIEWER) == [Permission.READ]
    assert role_permissions(Role.MEMBER) == [Permission.READ, Permission.WRITE]
    assert Permission.MANAGE in role_permissions(Role.ADMIN)
    assert role_permissions(Role.OWNER) == list(Permission)


async def test_non_member_is_locked_out_everywhere(client, alice):
    ws = await make_workspace(client)
    wid = ws["id"]
    page = (
        await client.post(f"/api/v1/workspaces/{wid}/pages", json={"title": "Doc"})
    ).json()

    await register_and_login(client, "outsider@test.com", "Outsider")

    surfaces = [
        f"/api/v1/workspaces/{wid}",
        f"/api/v1/workspaces/{wid}/pages",
        f"/api/v1/workspaces/{wid}/search?q=doc",
        f"/api/v1/workspaces/{wid}/graph",
        f"/api/v1/workspaces/{wid}/tags",
        f"/api/v1/workspaces/{wid}/metadata-keys",
        f"/api/v1/workspaces/{wid}/orphans",
        f"/api/v1/workspaces/{wid}/audit",
        f"/api/v1/workspaces/{wid}/members",
        f"/api/v1/pages/{page['id']}",
        f"/api/v1/pages/{page['id']}/backlinks",
        f"/api/v1/pages/{page['id']}/links",
        f"/api/v1/pages/{page['id']}/related",
        f"/api/v1/pages/{page['id']}/versions",
        f"/api/v1/pages/{page['id']}/comments",
        f"/api/v1/pages/{page['id']}/attachments",
        f"/api/v1/pages/{page['id']}/presence",
    ]
    for url in surfaces:
        resp = await client.get(url)
        assert resp.status_code == 404, f"{url} -> {resp.status_code} (expected 404 lockout)"

    # writes are locked out too
    assert (
        await client.post(f"/api/v1/workspaces/{wid}/pages", json={"title": "X"})
    ).status_code == 404
    assert (
        await client.patch(f"/api/v1/pages/{page['id']}", json={"title": "X"})
    ).status_code == 404
    assert (await client.delete(f"/api/v1/pages/{page['id']}")).status_code == 404
    assert (
        await client.post(f"/api/v1/pages/{page['id']}/comments", json={"body_md": "hi"})
    ).status_code == 404

    # workspace does not appear in their list
    workspaces = (await client.get("/api/v1/workspaces")).json()
    assert wid not in [w["id"] for w in workspaces]


async def test_grant_read_and_write_via_access_param(client, alice):
    ws = await make_workspace(client)
    wid = ws["id"]
    page = (
        await client.post(f"/api/v1/workspaces/{wid}/pages", json={"title": "Doc"})
    ).json()
    await register_and_login(client, "colleague@test.com", "Colleague")
    await client.post(
        "/api/v1/auth/login", json={"email": "alice@test.com", "password": "password123"}
    )

    # grant READ
    resp = await client.post(
        f"/api/v1/workspaces/{wid}/members",
        json={"email": "colleague@test.com", "access": "read"},
    )
    assert resp.status_code == 201
    members = (await client.get(f"/api/v1/workspaces/{wid}/members")).json()
    colleague = next(m for m in members if m["email"] == "colleague@test.com")
    assert colleague["role"] == "viewer" and colleague["permissions"] == ["read"]

    await client.post(
        "/api/v1/auth/login", json={"email": "colleague@test.com", "password": "password123"}
    )
    assert (await client.get(f"/api/v1/pages/{page['id']}")).status_code == 200  # can read
    resp = await client.patch(f"/api/v1/pages/{page['id']}", json={"title": "Nope"})
    assert resp.status_code == 403  # cannot write
    assert (
        await client.post(f"/api/v1/workspaces/{wid}/pages", json={"title": "New"})
    ).status_code == 403

    # upgrade to WRITE
    await client.post(
        "/api/v1/auth/login", json={"email": "alice@test.com", "password": "password123"}
    )
    resp = await client.patch(
        f"/api/v1/workspaces/{wid}/members/{colleague['user_id']}", json={"access": "write"}
    )
    assert resp.status_code == 200
    members = (await client.get(f"/api/v1/workspaces/{wid}/members")).json()
    assert next(m for m in members if m["email"] == "colleague@test.com")["permissions"] == [
        "read",
        "write",
    ]

    await client.post(
        "/api/v1/auth/login", json={"email": "colleague@test.com", "password": "password123"}
    )
    assert (
        await client.patch(f"/api/v1/pages/{page['id']}", json={"title": "Renamed"})
    ).status_code == 200
    # write does not include manage
    assert (
        await client.post(
            f"/api/v1/workspaces/{wid}/members", json={"email": "x@test.com", "access": "read"}
        )
    ).status_code == 403
    assert (await client.get(f"/api/v1/workspaces/{wid}/audit")).status_code == 403


async def test_revocation_cuts_access_and_mentions(client, alice):
    ws = await make_workspace(client)
    wid = ws["id"]
    page = (
        await client.post(f"/api/v1/workspaces/{wid}/pages", json={"title": "Doc"})
    ).json()
    await register_and_login(client, "temp@test.com", "Temp Person")
    await client.post(
        "/api/v1/auth/login", json={"email": "alice@test.com", "password": "password123"}
    )
    await client.post(
        f"/api/v1/workspaces/{wid}/members", json={"email": "temp@test.com", "access": "write"}
    )
    await client.post(f"/api/v1/pages/{page['id']}/comments", json={"body_md": "@temp 機密內容"})

    await client.post(
        "/api/v1/auth/login", json={"email": "temp@test.com", "password": "password123"}
    )
    assert len((await client.get("/api/v1/mentions")).json()) == 1

    # revoke membership
    await client.post(
        "/api/v1/auth/login", json={"email": "alice@test.com", "password": "password123"}
    )
    members = (await client.get(f"/api/v1/workspaces/{wid}/members")).json()
    temp_id = next(m["user_id"] for m in members if m["email"] == "temp@test.com")
    assert (
        await client.delete(f"/api/v1/workspaces/{wid}/members/{temp_id}")
    ).status_code == 204

    await client.post(
        "/api/v1/auth/login", json={"email": "temp@test.com", "password": "password123"}
    )
    assert (await client.get(f"/api/v1/pages/{page['id']}")).status_code == 404
    # revoked access also hides old mentions (no content leak)
    assert (await client.get("/api/v1/mentions")).json() == []
