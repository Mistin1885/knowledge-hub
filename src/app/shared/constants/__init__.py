from enum import StrEnum


class Role(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


ROLE_RANK: dict[Role, int] = {Role.VIEWER: 0, Role.MEMBER: 1, Role.ADMIN: 2, Role.OWNER: 3}


class Permission(StrEnum):
    """Workspace capabilities. Roles are named bundles of these:
    viewer=read, member=read+write, admin=+manage, owner=+own."""

    READ = "read"  # view pages, search, graph, comments
    WRITE = "write"  # create/edit/delete pages, upload attachments
    MANAGE = "manage"  # members, workspace settings, audit log
    OWN = "own"  # delete workspace, grant admin/owner


PERMISSION_MIN_ROLE: dict[Permission, Role] = {
    Permission.READ: Role.VIEWER,
    Permission.WRITE: Role.MEMBER,
    Permission.MANAGE: Role.ADMIN,
    Permission.OWN: Role.OWNER,
}


def role_permissions(role: Role) -> list[Permission]:
    return [p for p, min_role in PERMISSION_MIN_ROLE.items() if ROLE_RANK[role] >= ROLE_RANK[min_role]]


class PageStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class PageVisibility(StrEnum):
    WORKSPACE = "workspace"
    PRIVATE = "private"


class LinkKind(StrEnum):
    WIKI = "wiki"
    MARKDOWN = "md"
