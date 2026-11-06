"""Generate guide pages under guides/ from Markdown (or stubs)."""

from __future__ import annotations

import html
import re
from pathlib import Path

from sitegen.common import (
    GUIDE_NAV_ITEMS,
    NAV_SCRIPT,
    ROOT,
    SCAVENGER_GUIDE_STEMS,
    NavItem,
    github_md_url_for_nav_item,
    html_document,
    primary_nav_html,
)
from sitegen.markdown_html import markdown_to_html, split_title_from_markdown


# Minimum non-trivial length before we treat an .md as a full guide page.
# Short unlock checklists stay stubs until expanded.
_MIN_MD_CHARS_FOR_FULL_PAGE = 400


def guide_md_path(item: NavItem) -> Path:
    return ROOT / item.section / f"{item.page_id}.md"


def md_is_full_guide(text: str) -> bool:
    """True when markdown looks like a real guide, not a short checklist."""
    stripped = text.strip()
    if len(stripped) < _MIN_MD_CHARS_FOR_FULL_PAGE:
        return False
    # Prefer docs with at least one real heading beyond a lone title-ish line.
    headings = re.findall(r"(?m)^#{1,6}\s+\S", stripped)
    if len(headings) >= 2:
        return True
    # Or substantial prose with a single H1 + body.
    if stripped.startswith("#") and len(stripped) >= _MIN_MD_CHARS_FOR_FULL_PAGE:
        return True
    return False


def source_md_footer_html(item: NavItem) -> str:
    md_href = html.escape(github_md_url_for_nav_item(item))
    return (
        f'<p class="page-source">'
        f'<a class="page-source-external" href="{md_href}" '
        f'target="_blank" rel="noopener noreferrer" '
        f'title="Opens in a new tab" '
        f'aria-label="View Markdown on GitHub (external link)">'
        f"View Markdown"
        f'<span class="nav-external-mark" aria-hidden="true">↗</span>'
        f"</a>"
        f" — source for this page"
        f"</p>\n"
    )


def stub_page_body_html(item: NavItem) -> str:
    """Minimal section page until guide markdown is filled in."""
    parts: list[str] = []
    parts.append("<h1>Sparroh's Mycopunk Builds</h1>\n")
    parts.append(
        primary_nav_html(
            section=item.section, current_filename=item.filename
        )
    )
    parts.append(f'<h2 class="page-title">{html.escape(item.label)}</h2>\n')
    desc = item.description or "Content coming soon."
    parts.append(f"<p>{html.escape(desc)}</p>\n")
    parts.append(
        '<p class="page-placeholder"><em>Full page content will appear here '
        "once the guide markdown is filled in.</em></p>\n"
    )
    return "".join(parts)


# H2 ids that stay outside scavenger "step cards".
_SCAVENGER_INTRO_H2_IDS = frozenset(
    {
        "at-a-glance",
        "how-to-use-this-guide",
        "overview-map",
        "notes",
    }
)

_H2_OPEN_RE = re.compile(
    r'<h2\s+id="([^"]*)"[^>]*>.*?</h2\s*>',
    re.IGNORECASE | re.DOTALL,
)


def wrap_scavenger_steps(body_html: str) -> str:
    """Wrap each non-intro H2 + following blocks in <section class="guide-step">."""
    matches = list(_H2_OPEN_RE.finditer(body_html))
    if not matches:
        return body_html

    out: list[str] = []
    cursor = 0
    for idx, match in enumerate(matches):
        start = match.start()
        if start > cursor:
            out.append(body_html[cursor:start])

        h2_id = match.group(1).strip().lower()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(body_html)
        chunk = body_html[start:end]

        if h2_id in _SCAVENGER_INTRO_H2_IDS:
            out.append(chunk)
        else:
            # Split heading from body so the card chrome can style them apart.
            h2_html = match.group(0)
            rest = body_html[match.end() : end]
            out.append('<section class="guide-step">\n')
            out.append(h2_html)
            out.append('\n<div class="guide-step-body">\n')
            out.append(rest)
            if not rest.endswith("\n"):
                out.append("\n")
            out.append("</div>\n</section>\n")

        cursor = end

    if cursor < len(body_html):
        out.append(body_html[cursor:])
    return "".join(out)


def markdown_page_body_html(item: NavItem, md_text: str) -> str:
    """Full guide page from markdown source."""
    title_from_md, rest = split_title_from_markdown(md_text)
    page_title = title_from_md or item.label
    body_html = markdown_to_html(rest)
    body_class = "guide-body"
    if item.page_id in SCAVENGER_GUIDE_STEMS:
        body_class += " guide-scavenger"
        body_html = wrap_scavenger_steps(body_html)

    parts: list[str] = []
    parts.append("<h1>Sparroh's Mycopunk Builds</h1>\n")
    parts.append(
        primary_nav_html(
            section=item.section, current_filename=item.filename
        )
    )
    parts.append(f'<article class="{body_class}">\n')
    parts.append(
        f'<h2 class="page-title">{html.escape(page_title)}</h2>\n'
    )
    parts.append(body_html)
    parts.append("</article>\n")
    parts.append(source_md_footer_html(item))
    return "".join(parts)




def write_guide_page(item: NavItem) -> None:
    html_path = ROOT / item.section / item.filename
    html_path.parent.mkdir(parents=True, exist_ok=True)

    md_path = guide_md_path(item)
    mode = "stub"
    if md_path.is_file():
        md_text = md_path.read_text(encoding="utf-8")
        if md_is_full_guide(md_text):
            body = markdown_page_body_html(item, md_text) + NAV_SCRIPT
            mode = "markdown"
        else:
            body = stub_page_body_html(item) + NAV_SCRIPT
    else:
        body = stub_page_body_html(item) + NAV_SCRIPT

    doc = html_document(item.label, "../css/style.css", body)
    html_path.write_text(doc, encoding="utf-8", newline="\n")
    print(f"Wrote {html_path.relative_to(ROOT)} ({mode})")


def generate_all_guides() -> None:
    for item in GUIDE_NAV_ITEMS:
        write_guide_page(item)


def main() -> None:
    generate_all_guides()


if __name__ == "__main__":
    main()
