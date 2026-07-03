import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.infra.db.models import (
    Attachment,
    Comment,
    CommentMention,
    Page,
    PageMetadata,
    PageShare,
    PageTag,
    PageVersion,
    Tag,
)

# --- pages ---


async def get(s: AsyncSession, page_id: uuid.UUID) -> Page | None:
    return await s.get(Page, page_id, options=[joinedload(Page.owner)])


async def list_workspace(s: AsyncSession, workspace_id: uuid.UUID, visibility_filter) -> list[Page]:
    return list(
        await s.scalars(
            select(Page)
            .options(joinedload(Page.owner))
            .where(Page.workspace_id == workspace_id, visibility_filter)
            .order_by(Page.position, Page.created_at)
        )
    )


async def children_count(s: AsyncSession, page_id: uuid.UUID) -> int:
    return (await s.scalar(select(func.count()).where(Page.parent_id == page_id))) or 0


async def list_children(
    s: AsyncSession, page_id: uuid.UUID, visibility_filter
) -> list[Page]:
    return list(
        await s.scalars(
            select(Page)
            .options(joinedload(Page.owner))
            .where(Page.parent_id == page_id, visibility_filter)
            .order_by(Page.position, Page.created_at)
        )
    )


async def max_sibling_position(s: AsyncSession, workspace_id: uuid.UUID, parent_id: uuid.UUID | None) -> float:
    q = select(func.max(Page.position)).where(Page.workspace_id == workspace_id)
    q = q.where(Page.parent_id == parent_id) if parent_id else q.where(Page.parent_id.is_(None))
    return (await s.scalar(q)) or 0.0


async def is_descendant(s: AsyncSession, ancestor_id: uuid.UUID, maybe_descendant_id: uuid.UUID) -> bool:
    """True if maybe_descendant is in the subtree of ancestor (cycle guard for moves)."""
    current = maybe_descendant_id
    for _ in range(100):
        if current == ancestor_id:
            return True
        parent = await s.scalar(select(Page.parent_id).where(Page.id == current))
        if parent is None:
            return False
        current = parent
    return True


# --- versions ---


async def latest_version(s: AsyncSession, page_id: uuid.UUID) -> PageVersion | None:
    return await s.scalar(
        select(PageVersion)
        .where(PageVersion.page_id == page_id)
        .order_by(PageVersion.version.desc())
        .limit(1)
    )


async def add_version(
    s: AsyncSession, page: Page, created_by: uuid.UUID | None, summary: str | None = None
) -> PageVersion:
    page.version += 1
    row = PageVersion(
        page_id=page.id,
        version=page.version,
        title=page.title,
        content_md=page.content_md,
        summary=summary,
        created_by=created_by,
    )
    s.add(row)
    await s.flush()
    return row


async def list_versions(s: AsyncSession, page_id: uuid.UUID) -> list[PageVersion]:
    return list(
        await s.scalars(
            select(PageVersion)
            .options(joinedload(PageVersion.author))
            .where(PageVersion.page_id == page_id)
            .order_by(PageVersion.version.desc())
        )
    )


async def get_version(s: AsyncSession, page_id: uuid.UUID, version_id: uuid.UUID) -> PageVersion | None:
    return await s.scalar(
        select(PageVersion).where(PageVersion.id == version_id, PageVersion.page_id == page_id)
    )


# --- tags ---


async def get_page_tags(s: AsyncSession, page_id: uuid.UUID) -> list[str]:
    return list(
        await s.scalars(
            select(Tag.name)
            .join(PageTag, PageTag.tag_id == Tag.id)
            .where(PageTag.page_id == page_id)
            .order_by(Tag.name)
        )
    )


async def set_page_tags(s: AsyncSession, page: Page, names: list[str]) -> None:
    wanted = {n.strip() for n in names if n.strip()}
    await s.execute(delete(PageTag).where(PageTag.page_id == page.id))
    for name in sorted(wanted):
        tag = await s.scalar(
            select(Tag).where(Tag.workspace_id == page.workspace_id, Tag.name == name)
        )
        if tag is None:
            tag = Tag(workspace_id=page.workspace_id, name=name)
            s.add(tag)
            await s.flush()
        s.add(PageTag(page_id=page.id, tag_id=tag.id))
    await s.flush()


async def list_workspace_tags(s: AsyncSession, workspace_id: uuid.UUID) -> list[tuple[str, int]]:
    rows = await s.execute(
        select(Tag.name, func.count(PageTag.page_id))
        .outerjoin(PageTag, PageTag.tag_id == Tag.id)
        .where(Tag.workspace_id == workspace_id)
        .group_by(Tag.name)
        .order_by(func.count(PageTag.page_id).desc(), Tag.name)
    )
    return list(rows.all())


async def page_ids_with_tag(s: AsyncSession, workspace_id: uuid.UUID, tag: str) -> list[uuid.UUID]:
    return list(
        await s.scalars(
            select(PageTag.page_id)
            .join(Tag, Tag.id == PageTag.tag_id)
            .where(Tag.workspace_id == workspace_id, func.lower(Tag.name) == tag.lower())
        )
    )


# --- metadata ---


async def get_page_metadata(s: AsyncSession, page_id: uuid.UUID) -> dict[str, str]:
    rows = await s.execute(
        select(PageMetadata.key, PageMetadata.value).where(PageMetadata.page_id == page_id)
    )
    return dict(rows.all())


async def set_page_metadata(s: AsyncSession, page_id: uuid.UUID, meta: dict[str, str]) -> None:
    await s.execute(delete(PageMetadata).where(PageMetadata.page_id == page_id))
    for key, value in meta.items():
        key = key.strip()
        if key:
            s.add(PageMetadata(page_id=page_id, key=key, value=str(value)))
    await s.flush()


async def merge_page_metadata(s: AsyncSession, page_id: uuid.UUID, meta: dict[str, str]) -> None:
    current = await get_page_metadata(s, page_id)
    current.update(meta)
    await set_page_metadata(s, page_id, current)


async def workspace_metadata_keys(
    s: AsyncSession, workspace_id: uuid.UUID
) -> dict[str, list[str]]:
    rows = await s.execute(
        select(PageMetadata.key, PageMetadata.value)
        .join(Page, Page.id == PageMetadata.page_id)
        .where(Page.workspace_id == workspace_id)
        .distinct()
        .order_by(PageMetadata.key, PageMetadata.value)
    )
    result: dict[str, list[str]] = {}
    for key, value in rows:
        result.setdefault(key, [])
        if len(result[key]) < 50:
            result[key].append(value)
    return result


# --- shares ---


async def list_shares(s: AsyncSession, page_id: uuid.UUID) -> list[PageShare]:
    return list(
        await s.scalars(
            select(PageShare).options(joinedload(PageShare.user)).where(PageShare.page_id == page_id)
        )
    )


async def add_share(s: AsyncSession, page_id: uuid.UUID, user_id: uuid.UUID) -> None:
    if not await s.get(PageShare, (page_id, user_id)):
        s.add(PageShare(page_id=page_id, user_id=user_id))
        await s.flush()


async def remove_share(s: AsyncSession, page_id: uuid.UUID, user_id: uuid.UUID) -> None:
    await s.execute(
        delete(PageShare).where(PageShare.page_id == page_id, PageShare.user_id == user_id)
    )


# --- comments & mentions ---


async def list_comments(s: AsyncSession, page_id: uuid.UUID) -> list[Comment]:
    return list(
        await s.scalars(
            select(Comment)
            .options(joinedload(Comment.author))
            .where(Comment.page_id == page_id)
            .order_by(Comment.created_at)
        )
    )


async def get_comment(s: AsyncSession, comment_id: uuid.UUID) -> Comment | None:
    return await s.get(Comment, comment_id, options=[joinedload(Comment.author)])


async def comment_mention_user_ids(s: AsyncSession, comment_id: uuid.UUID) -> list[uuid.UUID]:
    return list(
        await s.scalars(
            select(CommentMention.user_id).where(CommentMention.comment_id == comment_id)
        )
    )


async def set_mentions(s: AsyncSession, comment_id: uuid.UUID, user_ids: set[uuid.UUID]) -> None:
    await s.execute(delete(CommentMention).where(CommentMention.comment_id == comment_id))
    for uid in user_ids:
        s.add(CommentMention(comment_id=comment_id, user_id=uid))
    await s.flush()


async def list_mentions_for_user(s: AsyncSession, user_id: uuid.UUID) -> list[tuple]:
    from app.infra.db.models import WorkspaceMember

    rows = await s.execute(
        select(CommentMention, Comment, Page.id, Page.title)
        .join(Comment, Comment.id == CommentMention.comment_id)
        .join(Page, Page.id == Comment.page_id)
        # only workspaces the user can still access — old mentions must not
        # leak content after access is revoked
        .join(
            WorkspaceMember,
            (WorkspaceMember.workspace_id == Page.workspace_id)
            & (WorkspaceMember.user_id == user_id),
        )
        .options(joinedload(Comment.author))
        .where(CommentMention.user_id == user_id)
        .order_by(CommentMention.created_at.desc())
        .limit(100)
    )
    return list(rows.all())


async def mark_mention_read(s: AsyncSession, user_id: uuid.UUID, comment_id: uuid.UUID) -> None:
    mention = await s.get(CommentMention, (comment_id, user_id))
    if mention:
        mention.read = True


# --- attachments ---


async def add_attachment(s: AsyncSession, **kwargs) -> Attachment:
    att = Attachment(**kwargs)
    s.add(att)
    await s.flush()
    return att


async def get_attachment(s: AsyncSession, attachment_id: uuid.UUID) -> Attachment | None:
    return await s.get(Attachment, attachment_id)


async def list_attachments(s: AsyncSession, page_id: uuid.UUID) -> list[Attachment]:
    return list(
        await s.scalars(
            select(Attachment).where(Attachment.page_id == page_id).order_by(Attachment.created_at)
        )
    )
