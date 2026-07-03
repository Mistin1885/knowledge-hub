import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.models import Comment, User
from app.modules.audit.services import audit
from app.modules.pages.domain import mentions as mention_rules
from app.modules.pages.infra import repo
from app.modules.pages.services import pages as pages_service
from app.modules.workspaces.infra import repo as ws_repo
from app.shared.exceptions import NotFoundError, PermissionDeniedError


async def _resolve_mentions(
    s: AsyncSession, workspace_id: uuid.UUID, body: str
) -> set[uuid.UUID]:
    tokens = mention_rules.extract_mention_tokens(body)
    if not tokens:
        return set()
    matched: set[uuid.UUID] = set()
    for member in await ws_repo.list_members(s, workspace_id):
        if mention_rules.handle_for(member.user.name, member.user.email) & tokens:
            matched.add(member.user_id)
    return matched


async def list_for_page(s: AsyncSession, user: User, page_id: uuid.UUID) -> list[Comment]:
    await pages_service.get_for_read(s, user, page_id)
    return await repo.list_comments(s, page_id)


async def create(
    s: AsyncSession, user: User, page_id: uuid.UUID, body_md: str, anchor: str | None
) -> Comment:
    page = await pages_service.get_for_read(s, user, page_id)
    comment = Comment(page_id=page_id, author_id=user.id, body_md=body_md, anchor=anchor)
    s.add(comment)
    await s.flush()
    mentioned = await _resolve_mentions(s, page.workspace_id, body_md)
    mentioned.discard(user.id)
    await repo.set_mentions(s, comment.id, mentioned)
    await audit.record(
        s, workspace_id=page.workspace_id, actor_id=user.id, action="comment.create",
        target_type="page", target_id=page.id, target_title=page.title,
    )
    return await repo.get_comment(s, comment.id)


async def update(
    s: AsyncSession, user: User, comment_id: uuid.UUID, body_md: str | None, resolved: bool | None
) -> Comment:
    comment = await repo.get_comment(s, comment_id)
    if comment is None:
        raise NotFoundError("Comment not found")
    page = await pages_service.get_for_read(s, user, comment.page_id)
    if body_md is not None:
        if comment.author_id != user.id:
            raise PermissionDeniedError("Only the author can edit a comment")
        comment.body_md = body_md
        mentioned = await _resolve_mentions(s, page.workspace_id, body_md)
        mentioned.discard(user.id)
        await repo.set_mentions(s, comment.id, mentioned)
    if resolved is not None:
        comment.resolved = resolved
    return comment


async def delete(s: AsyncSession, user: User, comment_id: uuid.UUID) -> None:
    comment = await repo.get_comment(s, comment_id)
    if comment is None:
        raise NotFoundError("Comment not found")
    page = await pages_service.get_for_read(s, user, comment.page_id)
    if comment.author_id != user.id:
        from app.modules.workspaces.services import policy
        from app.shared.constants import Permission

        await policy.require_permission(s, user, page.workspace_id, Permission.MANAGE)
    await s.delete(comment)


async def mentions_inbox(s: AsyncSession, user: User) -> list[dict]:
    items = []
    for mention, comment, page_id, page_title in await repo.list_mentions_for_user(s, user.id):
        items.append(
            {
                "comment_id": comment.id,
                "page_id": page_id,
                "page_title": page_title,
                "author": {"id": comment.author_id, "name": comment.author.name if comment.author else "?"},
                "body_md": comment.body_md,
                "created_at": mention.created_at,
                "read": mention.read,
            }
        )
    return items


async def mark_read(s: AsyncSession, user: User, comment_id: uuid.UUID) -> None:
    await repo.mark_mention_read(s, user.id, comment_id)
