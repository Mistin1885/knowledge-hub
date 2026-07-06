"""Pure text sanitization for search_text — no I/O."""

import re

# Whitespace-free runs longer than this carry no search value (base64, data
# URIs, minified code) and bloat the trigram index.
MAX_TOKEN_CHARS = 200
# Defensive cap for Page.search_text; keyword search covers full content via
# page_chunks, so only excerpt/snippet/unlinked-mention helpers see this text.
MAX_SEARCH_TEXT_CHARS = 200_000

_LONG_TOKEN_RE = re.compile(rf"\S{{{MAX_TOKEN_CHARS + 1},}}")


def sanitize_for_search(text: str) -> str:
    return _LONG_TOKEN_RE.sub("", text)
