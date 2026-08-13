"""Bidirectional markdown <-> Yjs XmlFragment (ProseMirror/TipTap schema).

The fragment mirrors what y-prosemirror produces for TipTap StarterKit +
Link/Image/TaskList/Table: block elements are XmlElements tagged with the node name,
inline content is XmlText with mark-name formatting attributes, and inline
atoms (hardBreak) are XmlElements between text runs.

Wikilinks `[[Title]]` are plain text by design — the editor decorates them.
"""

import re
from urllib.parse import quote

from markdown_it import MarkdownIt
from markdown_it.token import Token
from pycrdt import XmlElement, XmlFragment, XmlText

_md = MarkdownIt("commonmark", {"html": True}).enable(["strikethrough", "table"])

TASK_PREFIXES = {"[ ] ": False, "[x] ": True, "[X] ": True}

# metadata lives in the DB (edited via the Info panel); the editor doc holds
# only the body, so frontmatter never round-trips through collab sessions
_FRONTMATTER_RE = re.compile(r"\A---\s*\n.*?\n---\s*\n?", re.DOTALL)
_STYLE_SPAN_OPEN_RE = re.compile(r"^<span\s+style=[\"']([^\"']*)[\"']\s*>$", re.IGNORECASE)
_STYLE_SPAN_CLOSE_RE = re.compile(r"^</span\s*>$", re.IGNORECASE)
_ALLOWED_STYLE_RE = re.compile(
    r"(?:^|;)\s*(color|background-color)\s*:\s*(#[0-9a-f]{6})\s*(?=;|$)",
    re.IGNORECASE,
)
_INTERNAL_IMAGE_START_RE = re.compile(
    r"/api/v1/(?:files/[0-9a-f-]{36}/preview|attachments/[0-9a-f-]{36}(?:/|(?=\)))?)",
    re.IGNORECASE,
)


def normalize_internal_image_markdown(markdown: str) -> str:
    """Encode internal image destinations so spaces/parentheses stay valid Markdown."""
    output: list[str] = []
    cursor = 0
    while True:
        image_start = markdown.find("![", cursor)
        if image_start < 0:
            output.append(markdown[cursor:])
            break
        destination_start = markdown.find("](", image_start + 2)
        if destination_start < 0 or "\n" in markdown[image_start:destination_start]:
            output.append(markdown[cursor : image_start + 2])
            cursor = image_start + 2
            continue

        source_start = destination_start + 2
        if not _INTERNAL_IMAGE_START_RE.match(markdown, source_start):
            output.append(markdown[cursor : image_start + 2])
            cursor = image_start + 2
            continue

        depth = 0
        source_end = source_start
        while source_end < len(markdown):
            char = markdown[source_end]
            if char in "\r\n":
                break
            if char == "(":
                depth += 1
            elif char == ")":
                if depth == 0:
                    break
                depth -= 1
            source_end += 1
        if source_end >= len(markdown) or markdown[source_end] != ")":
            output.append(markdown[cursor : image_start + 2])
            cursor = image_start + 2
            continue

        source = markdown[source_start:source_end]
        safe_source = quote(source, safe="/:?#[]@!$&'*+,;=%~._-")
        output.append(markdown[cursor:source_start])
        output.append(safe_source)
        cursor = source_end
    return "".join(output)


def _image_to_md(alt: str, source: str) -> str:
    safe_source = quote(source, safe="/:?#[]@!$&'*+,;=%~._-")
    return f"![{alt}]({safe_source})"


# --- markdown -> fragment ---------------------------------------------------


def md_to_fragment(md: str, frag: XmlFragment) -> None:
    """Populate an (empty) fragment from markdown (frontmatter stripped)."""
    body = normalize_internal_image_markdown(_FRONTMATTER_RE.sub("", md or "", count=1))
    tokens = _md.parse(body)
    _render_blocks(tokens, 0, len(tokens), frag)
    if len(frag.children) == 0:
        frag.children.append(XmlElement("paragraph"))


def _render_blocks(tokens: list[Token], start: int, end: int, parent) -> None:
    i = start
    while i < end:
        tok = tokens[i]
        if tok.type == "heading_open":
            close = _find_close(tokens, i, "heading_close")
            el = parent.children.append(XmlElement("heading", {"level": int(tok.tag[1])}))
            _render_inline(tokens[i + 1], el)
            i = close + 1
        elif tok.type == "paragraph_open":
            close = _find_close(tokens, i, "paragraph_close")
            el = parent.children.append(XmlElement("paragraph"))
            _render_inline(tokens[i + 1], el)
            i = close + 1
        elif tok.type in ("bullet_list_open", "ordered_list_open"):
            i = _render_list(tokens, i, parent)
        elif tok.type == "table_open":
            i = _render_table(tokens, i, parent)
        elif tok.type == "blockquote_open":
            close = _find_close(tokens, i, "blockquote_close")
            el = parent.children.append(XmlElement("blockquote"))
            _render_blocks(tokens, i + 1, close, el)
            i = close + 1
        elif tok.type in ("fence", "code_block"):
            attrs = {}
            if tok.type == "fence" and tok.info.strip():
                attrs["language"] = tok.info.strip().split()[0]
            el = parent.children.append(XmlElement("codeBlock", attrs or None))
            el.children.append(XmlText(tok.content.rstrip("\n")))
            i += 1
        elif tok.type == "hr":
            parent.children.append(XmlElement("horizontalRule"))
            i += 1
        elif tok.type == "html_block":
            el = parent.children.append(XmlElement("paragraph"))
            el.children.append(XmlText(tok.content.rstrip("\n")))
            i += 1
        else:
            i += 1


def _render_table(tokens: list[Token], i: int, parent) -> int:
    close = _find_close(tokens, i, "table_close")
    table = parent.children.append(XmlElement("table"))
    row = None
    j = i + 1
    while j < close:
        token = tokens[j]
        if token.type == "tr_open":
            row = table.children.append(XmlElement("tableRow"))
        elif token.type in ("th_open", "td_open") and row is not None:
            close_type = "th_close" if token.type == "th_open" else "td_close"
            cell_close = _find_close(tokens, j, close_type)
            cell_tag = "tableHeader" if token.type == "th_open" else "tableCell"
            cell = row.children.append(XmlElement(cell_tag))
            paragraph = cell.children.append(XmlElement("paragraph"))
            inline = next(
                (
                    candidate
                    for candidate in tokens[j + 1 : cell_close]
                    if candidate.type == "inline"
                ),
                None,
            )
            if inline is not None:
                _render_inline(inline, paragraph)
            j = cell_close
        j += 1
    return close + 1


def _render_list(tokens: list[Token], i: int, parent) -> int:
    open_tok = tokens[i]
    ordered = open_tok.type == "ordered_list_open"
    close = _find_close(tokens, i, "ordered_list_close" if ordered else "bullet_list_close")
    # peek first item to detect a task list
    is_task = _list_is_tasklist(tokens, i + 1, close)
    if is_task:
        list_el = parent.children.append(XmlElement("taskList"))
    elif ordered:
        attrs = {"start": int(dict(open_tok.attrs or {}).get("start", 1))}
        list_el = parent.children.append(XmlElement("orderedList", attrs))
    else:
        list_el = parent.children.append(XmlElement("bulletList"))

    j = i + 1
    while j < close:
        if tokens[j].type == "list_item_open":
            item_close = _find_close(tokens, j, "list_item_close")
            if is_task:
                checked = _item_task_state(tokens, j + 1, item_close)
                item_el = list_el.children.append(
                    XmlElement("taskItem", {"checked": bool(checked)})
                )
                _strip_task_prefix(tokens, j + 1, item_close)
            else:
                item_el = list_el.children.append(XmlElement("listItem"))
            _render_blocks(tokens, j + 1, item_close, item_el)
            j = item_close + 1
        else:
            j += 1
    return close + 1


def _list_is_tasklist(tokens: list[Token], start: int, end: int) -> bool:
    state = _item_task_state(tokens, start, end)
    return state is not None


def _item_task_state(tokens: list[Token], start: int, end: int) -> bool | None:
    for k in range(start, end):
        if tokens[k].type == "inline":
            content = tokens[k].content
            for prefix, checked in TASK_PREFIXES.items():
                if content.startswith(prefix):
                    return checked
            return None
    return None


def _strip_task_prefix(tokens: list[Token], start: int, end: int) -> None:
    for k in range(start, end):
        tok = tokens[k]
        if tok.type == "inline":
            for prefix in TASK_PREFIXES:
                if tok.content.startswith(prefix) and tok.children:
                    first = tok.children[0]
                    if first.type == "text" and first.content.startswith(prefix):
                        first.content = first.content[len(prefix) :]
                    return
            return


def _find_close(tokens: list[Token], i: int, close_type: str) -> int:
    depth = 0
    open_type = tokens[i].type
    for j in range(i, len(tokens)):
        if tokens[j].type == open_type:
            depth += 1
        elif tokens[j].type == close_type:
            depth -= 1
            if depth == 0:
                return j
    return len(tokens) - 1


def _render_inline(inline_tok: Token, parent) -> None:
    marks: dict[str, dict] = {}
    text_node: XmlText | None = None
    text_len = 0  # pycrdt XmlText.insert indexes by UTF-8 bytes

    def emit(text: str) -> None:
        nonlocal text_node, text_len
        if not text:
            return
        if text_node is None:
            text_node = parent.children.append(XmlText())
            text_len = 0
        text_node.insert(text_len, text, dict(marks) or None)
        text_len += len(text.encode())

    for child in inline_tok.children or []:
        t = child.type
        if t == "text":
            emit(child.content)
        elif t == "code_inline":
            saved = dict(marks)
            marks.clear()
            marks["code"] = {}
            emit(child.content)
            marks.clear()
            marks.update(saved)
        elif t == "strong_open":
            marks["bold"] = {}
        elif t == "strong_close":
            marks.pop("bold", None)
        elif t == "em_open":
            marks["italic"] = {}
        elif t == "em_close":
            marks.pop("italic", None)
        elif t == "s_open":
            marks["strike"] = {}
        elif t == "s_close":
            marks.pop("strike", None)
        elif t == "link_open":
            marks["link"] = {"href": dict(child.attrs or {}).get("href", "")}
        elif t == "link_close":
            marks.pop("link", None)
        elif t == "image":
            attrs = dict(child.attrs or {})
            parent.children.append(
                XmlElement("image", {"src": attrs.get("src", ""), "alt": child.content or ""})
            )
            text_node = None
        elif t == "softbreak":
            emit(" ")
        elif t == "hardbreak":
            parent.children.append(XmlElement("hardBreak"))
            text_node = None
        elif t == "html_inline":
            span_match = _STYLE_SPAN_OPEN_RE.match(child.content.strip())
            if span_match:
                style = {
                    key.lower(): value.lower()
                    for key, value in _ALLOWED_STYLE_RE.findall(span_match.group(1))
                }
                attrs = {}
                if color := style.get("color"):
                    attrs["color"] = color
                if background := style.get("background-color"):
                    attrs["backgroundColor"] = background
                if attrs:
                    marks["textStyle"] = attrs
            elif _STYLE_SPAN_CLOSE_RE.match(child.content.strip()):
                marks.pop("textStyle", None)
            else:
                emit(child.content)


# --- fragment -> markdown ---------------------------------------------------


def fragment_to_md(frag: XmlFragment) -> str:
    blocks = [_block_to_md(child, "") for child in frag.children]
    md = "\n\n".join(b for b in blocks if b is not None)
    return md.strip("\n") + ("\n" if md.strip() else "")


def _block_to_md(node, indent: str) -> str | None:
    if isinstance(node, XmlText):  # stray inline at top level
        return indent + _text_to_md(node)
    tag = node.tag
    if tag == "paragraph":
        return indent + _inline_children_to_md(node)
    if tag == "heading":
        level = int(float(dict(node.attributes).get("level", 1)))
        return indent + "#" * max(1, min(level, 6)) + " " + _inline_children_to_md(node)
    if tag == "codeBlock":
        lang = dict(node.attributes).get("language", "") or ""
        code = "".join(str(c) for c in node.children)
        body = "\n".join(indent + line for line in code.split("\n"))
        return f"{indent}```{lang}\n{body}\n{indent}```"
    if tag == "blockquote":
        inner = "\n\n".join(
            b for b in (_block_to_md(c, "") for c in node.children) if b is not None
        )
        return "\n".join(indent + "> " + line for line in inner.split("\n"))
    if tag == "horizontalRule":
        return indent + "---"
    if tag == "image":
        attrs = dict(node.attributes)
        return indent + _image_to_md(attrs.get("alt", ""), attrs.get("src", ""))
    if tag in ("bulletList", "orderedList", "taskList"):
        return _list_to_md(node, indent)
    if tag == "table":
        return _table_to_md(node, indent)
    # unknown node: render children as blocks
    inner = [_block_to_md(c, indent) for c in node.children]
    return "\n\n".join(b for b in inner if b is not None) or None


def _list_to_md(node, indent: str) -> str:
    tag = node.tag
    start = int(float(dict(node.attributes).get("start", 1))) if tag == "orderedList" else 1
    lines: list[str] = []
    for idx, item in enumerate(node.children):
        if tag == "orderedList":
            bullet = f"{start + idx}. "
        elif tag == "taskList":
            checked = str(dict(item.attributes).get("checked", "false")).lower() in (
                "true",
                "1",
                "1.0",
            )
            bullet = f"- [{'x' if checked else ' '}] "
        else:
            bullet = "- "
        child_indent = indent + " " * len(bullet)
        parts: list[str] = []
        for child in node_children(item):
            rendered = _block_to_md(child, child_indent if parts else "")
            if rendered is None:
                continue
            if not parts:
                parts.append(indent + bullet + rendered)
            else:
                parts.append(rendered)
        lines.append("\n".join(parts) if parts else indent + bullet.rstrip())
    return "\n".join(lines)


def _table_to_md(node, indent: str) -> str:
    rows: list[list[str]] = []
    for row in node.children:
        cells: list[str] = []
        for cell in row.children:
            blocks = [
                rendered
                for rendered in (_block_to_md(child, "") for child in cell.children)
                if rendered is not None
            ]
            value = "<br>".join(blocks).replace("\n", "<br>").replace("|", r"\|")
            cells.append(value)
        rows.append(cells)
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    normalized = [row + [""] * (width - len(row)) for row in rows]

    def line(cells: list[str]) -> str:
        return indent + "| " + " | ".join(cells) + " |"

    return "\n".join(
        [line(normalized[0]), line(["---"] * width), *(line(row) for row in normalized[1:])]
    )


def node_children(node):
    return list(node.children)


def _inline_children_to_md(node) -> str:
    out: list[str] = []
    for child in node.children:
        if isinstance(child, XmlText):
            out.append(_text_to_md(child))
        elif getattr(child, "tag", None) == "hardBreak":
            out.append("  \n")
        elif getattr(child, "tag", None) == "image":
            attrs = dict(child.attributes)
            out.append(_image_to_md(attrs.get("alt", ""), attrs.get("src", "")))
        else:
            out.append(
                "".join(
                    _text_to_md(c) for c in getattr(child, "children", []) if isinstance(c, XmlText)
                )
            )
    return "".join(out)


def _text_to_md(text: XmlText) -> str:
    out: list[str] = []
    for run, attrs in text.diff():
        piece = run
        marks = attrs or {}
        if "code" in marks:
            piece = f"`{piece}`"
        else:
            if "bold" in marks and marks["bold"] is not None:
                piece = f"**{piece}**"
            if "italic" in marks and marks["italic"] is not None:
                piece = f"*{piece}*"
            if "strike" in marks and marks["strike"] is not None:
                piece = f"~~{piece}~~"
        if "link" in marks and marks["link"] is not None:
            href = (marks["link"] or {}).get("href", "")
            piece = f"[{piece}]({href})"
        if "textStyle" in marks and marks["textStyle"] is not None:
            style = marks["textStyle"] or {}
            declarations = []
            if color := style.get("color"):
                if re.fullmatch(r"#[0-9a-fA-F]{6}", str(color)):
                    declarations.append(f"color: {str(color).lower()}")
            if background := style.get("backgroundColor"):
                if re.fullmatch(r"#[0-9a-fA-F]{6}", str(background)):
                    declarations.append(f"background-color: {str(background).lower()}")
            if declarations:
                piece = f'<span style="{"; ".join(declarations)}">{piece}</span>'
        out.append(piece)
    return "".join(out)
