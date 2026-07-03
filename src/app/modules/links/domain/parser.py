"""Pure markdown analysis: frontmatter, wikilinks, plain-text stripping. No I/O."""

import re
from dataclasses import dataclass

import yaml

from app.shared.constants import LinkKind

WIKILINK_RE = re.compile(r"\[\[([^\[\]|#]+)(?:#[^\[\]|]*)?(?:\|[^\[\]]*)?\]\]")
MD_LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)\s]+)\)")
FENCE_RE = re.compile(r"^(```|~~~).*?^\1\s*$", re.MULTILINE | re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
HEADING_MARK_RE = re.compile(r"^#{1,6}\s+", re.MULTILINE)
EMPHASIS_RE = re.compile(r"[*_~]{1,3}([^*_~]+)[*_~]{1,3}")


@dataclass(frozen=True)
class ParsedLink:
    target_title: str
    kind: LinkKind
    context: str


@dataclass(frozen=True)
class ParsedDocument:
    body: str
    frontmatter: dict[str, str]
    frontmatter_tags: list[str]
    links: list[ParsedLink]
    plain_text: str


def parse_frontmatter(md: str) -> tuple[dict[str, str], list[str], str]:
    """Returns (metadata, tags, body). Non-dict or invalid YAML is ignored."""
    m = FRONTMATTER_RE.match(md)
    if not m:
        return {}, [], md
    body = md[m.end():]
    try:
        data = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return {}, [], body
    if not isinstance(data, dict):
        return {}, [], body
    tags: list[str] = []
    raw_tags = data.pop("tags", None)
    if isinstance(raw_tags, str):
        tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
    elif isinstance(raw_tags, list):
        tags = [str(t).strip() for t in raw_tags if str(t).strip()]
    meta = {str(k): _scalar(v) for k, v in data.items() if v is not None}
    return meta, tags, body


def _scalar(value) -> str:
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)


def _without_code(md: str) -> str:
    md = FENCE_RE.sub("", md)
    return INLINE_CODE_RE.sub("", md)


def extract_links(md: str) -> list[ParsedLink]:
    """Wikilinks `[[Title]]`/`[[Title|alias]]`/`[[Title#section]]`, plus markdown
    links whose target is not a URL/anchor/path (treated as a page title)."""
    seen: dict[tuple[str, LinkKind], ParsedLink] = {}
    for line in _without_code(md).splitlines():
        context = line.strip()[:300]
        for m in WIKILINK_RE.finditer(line):
            title = m.group(1).strip()
            if title:
                seen.setdefault((title.lower(), LinkKind.WIKI), ParsedLink(title, LinkKind.WIKI, context))
        for m in MD_LINK_RE.finditer(line):
            href = m.group(2).strip()
            if re.match(r"^(https?:|mailto:|#|/|\.|api/)", href, re.IGNORECASE):
                continue
            title = re.sub(r"[-_]", " ", re.sub(r"\.md$", "", href)).strip()
            if title:
                seen.setdefault((title.lower(), LinkKind.MARKDOWN), ParsedLink(title, LinkKind.MARKDOWN, context))
    return list(seen.values())


def strip_markdown(md: str) -> str:
    """Markdown → searchable plain text (keeps wikilink titles, drops syntax)."""
    text = FENCE_RE.sub(" ", md)
    text = IMAGE_RE.sub(" ", text)
    text = INLINE_CODE_RE.sub(" ", text)
    text = WIKILINK_RE.sub(lambda m: m.group(1), text)
    text = MD_LINK_RE.sub(lambda m: m.group(1), text)
    text = HEADING_MARK_RE.sub("", text)
    text = EMPHASIS_RE.sub(lambda m: m.group(1), text)
    text = re.sub(r"^[>\-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\|", " ", text)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


def parse_document(md: str) -> ParsedDocument:
    meta, tags, body = parse_frontmatter(md)
    return ParsedDocument(
        body=body,
        frontmatter=meta,
        frontmatter_tags=tags,
        links=extract_links(body),
        plain_text=strip_markdown(body),
    )


def find_unlinked_context(content: str, title: str) -> str | None:
    """First line mentioning `title` without linking it, or None."""
    pattern = re.compile(re.escape(title), re.IGNORECASE)
    for line in _without_code(content).splitlines():
        if pattern.search(line) and f"[[{title.lower()}" not in line.lower():
            return line.strip()[:300]
    return None
