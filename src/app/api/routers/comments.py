import uuid

from fastapi import APIRouter, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DB, CurrentUser
from app.api.schemas.common import UserRef
from app.api.schemas.pages import CommentIn, CommentOut, CommentUpdateIn, MentionOut
from app.infra.db.models import Comment, User
from app.modules.pages.infra import repo as pages_repo
from app.modules.pages.services import comments as comments_service

router = APIRouter(tags=["comments"])


async def _comment_out(s: AsyncSession, comment: Comment) -> CommentOut:
    mention_ids = await pages_repo.comment_mention_user_ids(s, comment.id)
    mentions = []
    if mention_ids:
        users = await s.scalars(select(User).where(User.id.in_(mention_ids)))
        mentions = [UserRef(id=u.id, name=u.name) for u in users]
    return CommentOut(
        id=comment.id,
        author=UserRef(id=comment.author.id, name=comment.author.name) if comment.author else None,
        body_md=comment.body_md,
        anchor=comment.anchor,
        resolved=comment.resolved,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        mentions=mentions,
    )


@router.get("/pages/{page_id}/comments", response_model=list[CommentOut])
async def list_comments(page_id: uuid.UUID, user: CurrentUser, s: DB):
    comments = await comments_service.list_for_page(s, user, page_id)
    return [await _comment_out(s, c) for c in comments]


@router.post(
    "/pages/{page_id}/comments", response_model=CommentOut, status_code=status.HTTP_201_CREATED
)
async def create_comment(page_id: uuid.UUID, body: CommentIn, user: CurrentUser, s: DB):
    comment = await comments_service.create(s, user, page_id, body.body_md, body.anchor)
    return await _comment_out(s, comment)


@router.patch("/comments/{comment_id}", response_model=CommentOut)
async def update_comment(comment_id: uuid.UUID, body: CommentUpdateIn, user: CurrentUser, s: DB):
    comment = await comments_service.update(s, user, comment_id, body.body_md, body.resolved)
    return await _comment_out(s, comment)


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(comment_id: uuid.UUID, user: CurrentUser, s: DB):
    await comments_service.delete(s, user, comment_id)


@router.get("/mentions", response_model=list[MentionOut])
async def my_mentions(user: CurrentUser, s: DB):
    return await comments_service.mentions_inbox(s, user)


@router.post("/mentions/{comment_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_mention_read(comment_id: uuid.UUID, user: CurrentUser, s: DB):
    await comments_service.mark_read(s, user, comment_id)
