import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.models import User
from app.modules.links.infra import repo
from app.modules.pages.infra import repo as pages_repo
from app.modules.workspaces.services import policy
from app.shared.constants import Role


async def workspace_graph(
    s: AsyncSession, user: User, workspace_id: uuid.UUID, include_tags: bool = True
) -> dict:
    await policy.require_role(s, user, workspace_id, Role.VIEWER)
    visible = await pages_repo.list_workspace(
        s, workspace_id, policy.visible_pages_filter(user.id)
    )
    visible_ids = {p.id for p in visible}
    degree = await repo.link_degree(s, workspace_id)

    nodes = [
        {
            "id": str(p.id),
            "title": p.title,
            "icon": p.icon,
            "status": p.status,
            "is_tag": False,
            "link_count": degree.get(p.id, 0),
        }
        for p in visible
        if not p.is_folder or degree.get(p.id, 0) > 0
    ]
    edges = [
        {"source": str(link.source_page_id), "target": str(link.target_page_id), "kind": "link"}
        for link in await repo.workspace_links(s, workspace_id)
        if link.source_page_id in visible_ids and link.target_page_id in visible_ids
    ]

    if include_tags:
        tag_pages = await repo.workspace_tag_edges(s, workspace_id)
        tag_counts: dict[str, int] = {}
        for page_id, tag_name in tag_pages:
            if page_id in visible_ids:
                tag_counts[tag_name] = tag_counts.get(tag_name, 0) + 1
        for tag_name, count in tag_counts.items():
            nodes.append(
                {
                    "id": f"tag:{tag_name}",
                    "title": f"#{tag_name}",
                    "icon": None,
                    "status": None,
                    "is_tag": True,
                    "link_count": count,
                }
            )
        for page_id, tag_name in tag_pages:
            if page_id in visible_ids:
                edges.append({"source": str(page_id), "target": f"tag:{tag_name}", "kind": "tag"})

    return {"nodes": nodes, "edges": edges}
