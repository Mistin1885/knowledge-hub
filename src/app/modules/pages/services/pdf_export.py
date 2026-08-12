"""Render one knowledge-base page as a self-contained PDF."""

import html
import io
import re
import uuid
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlparse

from markdown_it import MarkdownIt
from markdown_it.token import Token
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.models import User
from app.modules.pages.services import attachments as attachments_service
from app.modules.pages.services import pages as pages_service
from app.modules.pages.services import vault

_md = MarkdownIt("commonmark", {"html": True}).enable(["strikethrough", "table"])
_INTERNAL_IMAGE_RE = re.compile(
    r"^/api/v1/(?:files/([0-9a-f-]{36})/preview|"
    r"attachments/([0-9a-f-]{36})(?:/[^\s]+)?)$",
    re.IGNORECASE,
)
_STYLE_OPEN_RE = re.compile(r"^<span\s+style=[\"']([^\"']*)[\"']\s*>$", re.IGNORECASE)
_STYLE_CLOSE_RE = re.compile(r"^</span\s*>$", re.IGNORECASE)
_STYLE_VALUE_RE = re.compile(
    r"(?:^|;)\s*(color|background-color)\s*:\s*(#[0-9a-f]{6})\s*(?=;|$)",
    re.IGNORECASE,
)

pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))


def _styles():
    base = getSampleStyleSheet()
    body = ParagraphStyle(
        "KnowledgeBody",
        parent=base["BodyText"],
        fontName="STSong-Light",
        fontSize=10.5,
        leading=16,
        textColor=colors.HexColor("#37352f"),
        spaceAfter=7,
        allowWidows=0,
        allowOrphans=0,
    )
    return {
        "body": body,
        "title": ParagraphStyle(
            "KnowledgeTitle",
            parent=body,
            fontSize=24,
            leading=31,
            spaceAfter=13,
            textColor=colors.HexColor("#1f2937"),
        ),
        "h1": ParagraphStyle(
            "KnowledgeH1", parent=body, fontSize=19, leading=25, spaceBefore=12, spaceAfter=7
        ),
        "h2": ParagraphStyle(
            "KnowledgeH2", parent=body, fontSize=16, leading=22, spaceBefore=10, spaceAfter=6
        ),
        "h3": ParagraphStyle(
            "KnowledgeH3", parent=body, fontSize=13.5, leading=19, spaceBefore=8, spaceAfter=5
        ),
        "quote": ParagraphStyle(
            "KnowledgeQuote",
            parent=body,
            leftIndent=12,
            borderColor=colors.HexColor("#a5b4fc"),
            borderWidth=1.5,
            borderPadding=(2, 0, 2, 8),
            textColor=colors.HexColor("#52525b"),
        ),
        "code": ParagraphStyle(
            "KnowledgeCode",
            parent=body,
            fontName="Courier",
            fontSize=8.5,
            leading=12,
            leftIndent=7,
            rightIndent=7,
            borderColor=colors.HexColor("#e5e7eb"),
            borderWidth=0.5,
            borderPadding=7,
            backColor=colors.HexColor("#f5f5f5"),
            spaceBefore=5,
            spaceAfter=9,
        ),
        "caption": ParagraphStyle(
            "KnowledgeCaption",
            parent=body,
            fontSize=8,
            leading=11,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#737373"),
            spaceBefore=3,
            spaceAfter=9,
        ),
    }


async def _local_images(s: AsyncSession, user: User, content: str) -> dict[str, Path]:
    sources = set(re.findall(r"!\[[^\]]*\]\(([^)]+)\)", content))
    result: dict[str, Path] = {}
    for raw_source in sources:
        source = raw_source.strip("<>")
        match = _INTERNAL_IMAGE_RE.match(urlparse(source).path)
        if not match:
            continue
        try:
            if match.group(1):
                _node, _asset, path, preview_kind = await vault.get_file(
                    s, user, uuid.UUID(match.group(1))
                )
                if preview_kind == "image":
                    result[source] = path
            else:
                attachment_id = uuid.UUID(match.group(2))
                migrated = await vault.get_legacy_file(s, user, attachment_id)
                if migrated is not None:
                    _node, _asset, path, preview_kind = migrated
                    if preview_kind == "image":
                        result[source] = path
                else:
                    attachment, path = await attachments_service.open_for_read(
                        s, user, attachment_id
                    )
                    if attachment.content_type.startswith("image/"):
                        result[source] = path
        except Exception:
            # A stale, missing, or newly private image should not abort export.
            continue
    return result


def _inline_markup(children: list[Token], image_paths: dict[str, Path]) -> list[tuple[str, str]]:
    """Return ordered (kind, value) chunks where kind is text or image."""
    chunks: list[tuple[str, str]] = []
    text: list[str] = []
    style_depth = 0

    def flush() -> None:
        if text:
            chunks.append(("text", "".join(text)))
            text.clear()

    for child in children:
        kind = child.type
        if kind == "text":
            text.append(html.escape(child.content))
        elif kind in {"softbreak", "hardbreak"}:
            text.append("<br/>")
        elif kind == "strong_open":
            text.append("<b>")
        elif kind == "strong_close":
            text.append("</b>")
        elif kind == "em_open":
            text.append("<i>")
        elif kind == "em_close":
            text.append("</i>")
        elif kind == "s_open":
            text.append("<strike>")
        elif kind == "s_close":
            text.append("</strike>")
        elif kind == "code_inline":
            text.append(f'<font name="Courier">{html.escape(child.content)}</font>')
        elif kind == "link_open":
            href = html.escape(dict(child.attrs or {}).get("href", ""), quote=True)
            text.append(f'<a href="{href}" color="#4f46e5">')
        elif kind == "link_close":
            text.append("</a>")
        elif kind == "html_inline":
            open_match = _STYLE_OPEN_RE.match(child.content.strip())
            if open_match:
                values = {
                    key.lower(): value.lower()
                    for key, value in _STYLE_VALUE_RE.findall(open_match.group(1))
                }
                attrs = []
                if color := values.get("color"):
                    attrs.append(f'color="{color}"')
                if background := values.get("background-color"):
                    attrs.append(f'backColor="{background}"')
                if attrs:
                    text.append(f"<font {' '.join(attrs)}>")
                    style_depth += 1
            elif _STYLE_CLOSE_RE.match(child.content.strip()) and style_depth:
                text.append("</font>")
                style_depth -= 1
        elif kind == "image":
            flush()
            source = dict(child.attrs or {}).get("src", "")
            path = image_paths.get(source)
            if path:
                chunks.append(("image", f"{path}\0{child.content or ''}"))
            else:
                text.append(f"[{html.escape(child.content or 'Image')}]")
    flush()
    return chunks


def _scaled_image(path: Path, max_width: float, max_height: float) -> Image:
    image = Image(str(path))
    ratio = min(max_width / image.imageWidth, max_height / image.imageHeight, 1)
    image.drawWidth = image.imageWidth * ratio
    image.drawHeight = image.imageHeight * ratio
    image.hAlign = "CENTER"
    return image


def _story(content: str, image_paths: dict[str, Path], page_title: str):
    styles = _styles()
    story = [Paragraph(html.escape(page_title or "Untitled"), styles["title"])]
    tokens = _md.parse(content or "")
    heading_level: int | None = None
    quote_depth = 0
    list_stack: list[dict[str, int | str]] = []
    list_prefix = ""
    table_rows: list[list[str]] | None = None
    table_row: list[str] | None = None

    for token in tokens:
        kind = token.type
        if kind == "heading_open":
            heading_level = int(token.tag[1])
        elif kind == "heading_close":
            heading_level = None
        elif kind == "blockquote_open":
            quote_depth += 1
        elif kind == "blockquote_close":
            quote_depth = max(0, quote_depth - 1)
        elif kind == "bullet_list_open":
            list_stack.append({"kind": "bullet", "number": 0})
        elif kind == "ordered_list_open":
            start = int(dict(token.attrs or {}).get("start", 1))
            list_stack.append({"kind": "ordered", "number": start - 1})
        elif kind in {"bullet_list_close", "ordered_list_close"}:
            if list_stack:
                list_stack.pop()
        elif kind == "list_item_open" and list_stack:
            current = list_stack[-1]
            if current["kind"] == "ordered":
                current["number"] = int(current["number"]) + 1
                list_prefix = f"{current['number']}. "
            else:
                list_prefix = "• "
        elif kind == "list_item_close":
            list_prefix = ""
        elif kind == "table_open":
            table_rows = []
        elif kind == "tr_open" and table_rows is not None:
            table_row = []
        elif kind == "tr_close" and table_rows is not None and table_row is not None:
            table_rows.append(table_row)
            table_row = None
        elif kind == "table_close" and table_rows:
            paragraph_rows = [
                [Paragraph(cell or "&nbsp;", styles["body"]) for cell in row] for row in table_rows
            ]
            table = Table(paragraph_rows, repeatRows=1, hAlign="LEFT")
            table.setStyle(
                TableStyle(
                    [
                        ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
                        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d1d5db")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ]
                )
            )
            story.extend([table, Spacer(1, 8)])
            table_rows = None
        elif kind == "inline":
            chunks = _inline_markup(token.children or [], image_paths)
            if table_row is not None:
                table_row.append(
                    "".join(value for chunk_kind, value in chunks if chunk_kind == "text")
                )
                continue
            style = (
                styles[f"h{min(heading_level, 3)}"]
                if heading_level
                else styles["quote"]
                if quote_depth
                else styles["body"]
            )
            prefix = "&nbsp;" * max(0, len(list_stack) - 1) * 4 + html.escape(list_prefix)
            first_text = True
            for chunk_kind, value in chunks:
                if chunk_kind == "text":
                    markup = (prefix if first_text else "") + value
                    story.append(Paragraph(markup or "&nbsp;", style))
                    first_text = False
                else:
                    path_value, alt = value.split("\0", 1)
                    try:
                        image = _scaled_image(Path(path_value), 166 * mm, 205 * mm)
                        flowables = [image]
                        if alt:
                            flowables.append(Paragraph(html.escape(alt), styles["caption"]))
                        story.append(KeepTogether(flowables))
                    except Exception:
                        story.append(Paragraph(f"[{html.escape(alt or 'Image')}]", style))
        elif kind in {"fence", "code_block"}:
            story.append(Preformatted(token.content.rstrip("\n"), styles["code"]))
        elif kind == "hr":
            story.extend(
                [
                    HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#d4d4d8")),
                    Spacer(1, 7),
                ]
            )
    return story


def _page_decorator(title: str) -> Callable:
    def draw(canvas, document) -> None:
        canvas.saveState()
        canvas.setFont("STSong-Light", 8)
        canvas.setFillColor(colors.HexColor("#737373"))
        canvas.drawString(document.leftMargin, A4[1] - 13 * mm, title[:80])
        canvas.drawRightString(A4[0] - document.rightMargin, 10 * mm, str(document.page))
        canvas.setStrokeColor(colors.HexColor("#e5e7eb"))
        canvas.setLineWidth(0.4)
        canvas.line(
            document.leftMargin, A4[1] - 15 * mm, A4[0] - document.rightMargin, A4[1] - 15 * mm
        )
        canvas.restoreState()

    return draw


async def export_page_pdf(s: AsyncSession, user: User, page_id: uuid.UUID) -> tuple[str, bytes]:
    page = await pages_service.get_for_read(s, user, page_id)
    image_paths = await _local_images(s, user, page.content_md or "")
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=22 * mm,
        rightMargin=22 * mm,
        topMargin=23 * mm,
        bottomMargin=18 * mm,
        title=page.title,
        author=user.name,
    )
    decorator = _page_decorator(page.title or "Untitled")
    document.build(
        _story(page.content_md or "", image_paths, page.title),
        onFirstPage=decorator,
        onLaterPages=decorator,
    )
    from app.modules.pages.services.export import safe_filename

    return f"{safe_filename(page.title)}.pdf", buffer.getvalue()
