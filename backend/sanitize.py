"""Tiny HTML sanitiser for rich-text post bodies.

The WYSIWYG editor on the frontend emits HTML (bold / italic / underline /
links / lists). Storing and re-rendering raw user HTML is an XSS hole, so every
post body is run through ``sanitize_html`` on write. We keep an explicit tag
whitelist and strip ALL attributes except a validated ``href`` on ``<a>``.

This is intentionally dependency-free (stdlib ``html.parser``) — good enough for
the whitelist we allow. Anything not on the list is dropped; its text content is
kept and HTML-escaped, so no markup can ever leak through.
"""

from html import escape
from html.parser import HTMLParser

# Inline + simple block tags the editor can produce. Everything else is removed.
ALLOWED_TAGS = {
    "b", "strong", "i", "em", "u", "s", "a", "p", "br",
    "ul", "ol", "li", "blockquote",
}
# Tags with no closing partner — emitted self-contained, never popped.
VOID_TAGS = {"br"}

MAX_LEN = 20_000  # hard cap on stored HTML length


def _safe_href(url: str) -> bool:
    """Allow only http/https/mailto links — blocks ``javascript:`` etc."""
    u = (url or "").strip().lower()
    return u.startswith(("http://", "https://", "mailto:"))


class _Sanitizer(HTMLParser):
    """Rebuilds the input keeping only whitelisted tags, escaping all text."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []

    def handle_starttag(self, tag, attrs):
        if tag not in ALLOWED_TAGS:
            return
        if tag == "a":
            href = dict(attrs).get("href", "")
            if _safe_href(href):
                # Force safe link-out semantics; drop every other attribute.
                self.out.append(
                    f'<a href="{escape(href, quote=True)}" '
                    f'target="_blank" rel="noopener noreferrer">'
                )
            else:
                self.out.append("<a>")
        else:
            self.out.append(f"<{tag}>")

    def handle_startendtag(self, tag, attrs):
        # e.g. "<br/>" — treat like a start tag for void elements.
        if tag in ALLOWED_TAGS:
            self.out.append(f"<{tag}>")

    def handle_endtag(self, tag):
        if tag in ALLOWED_TAGS and tag not in VOID_TAGS:
            self.out.append(f"</{tag}>")

    def handle_data(self, data):
        # Text nodes are escaped so any stray "<", ">", "&" can't form markup.
        self.out.append(escape(data))


def sanitize_html(raw: str) -> str:
    """Return a safe HTML subset of ``raw`` (whitelisted tags, escaped text)."""
    if not raw:
        return ""
    parser = _Sanitizer()
    parser.feed(raw[:MAX_LEN])
    parser.close()
    return "".join(parser.out).strip()


def strip_tags(raw: str) -> str:
    """Plain-text projection of ``raw`` — used to check a post isn't empty
    once all markup is removed (e.g. an editor that only sent ``<p></p>``)."""
    if not raw:
        return ""

    class _Strip(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.text = []

        def handle_data(self, data):
            self.text.append(data)

    s = _Strip()
    s.feed(raw)
    s.close()
    return "".join(s.text).strip()
