"""Pure @mention extraction — no I/O."""

import re

MENTION_RE = re.compile(r"@([\w.-]+)")


def handle_for(name: str, email: str) -> set[str]:
    """Candidate handles a user can be @mentioned by."""
    handles = {name.replace(" ", "").lower(), email.split("@")[0].lower()}
    first = name.split()[0].lower() if name.split() else ""
    if first:
        handles.add(first)
    return handles


def extract_mention_tokens(body: str) -> set[str]:
    return {m.group(1).lower() for m in MENTION_RE.finditer(body)}
