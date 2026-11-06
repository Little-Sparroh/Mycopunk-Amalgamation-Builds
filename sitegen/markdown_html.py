"""Minimal Markdown → HTML for guide pages (stdlib only).

Supports the subset used by guides/*.md:
headings, paragraphs, lists (nested), tables, hr, images/video
figures, and inline bold / italic / code / links.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_HR_RE = re.compile(r"^(-{3,}|\*{3,}|_{3,})\s*$")
_FENCE_RE = re.compile(r"^```")
_OL_RE = re.compile(r"^(\s*)(\d+)\.\s+(.*)$")
_UL_RE = re.compile(r"^(\s*)([-*+])\s+(.*)$")
_TABLE_SEP_RE = re.compile(
    r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$"
)
# ![alt](src) or ![alt](src "caption")
_IMAGE_RE = re.compile(
    r'^!\[([^\]]*)\]\(\s*([^)\s]+)\s*(?:\"([^\"]*)\"|\'([^\']*)\')?\s*\)$'
)
_ITALIC_LINE_RE = re.compile(r"^\*(?!\*)(.+?)\*$")
_VIDEO_EXTS = (".mp4", ".webm", ".ogg")
# youtu.be/ID, youtube.com/watch?v=ID, youtube.com/embed/ID, youtube-nocookie
_YOUTUBE_RE = re.compile(
    r"(?:https?://)?(?:www\.)?"
    r"(?:youtube\.com/(?:watch\?(?:[^#\s]*&)?v=|embed/|shorts/)|youtu\.be/|"
    r"youtube-nocookie\.com/embed/)"
    r"([A-Za-z0-9_-]{6,})"
    r"(?:[?&#].*)?$",
    re.IGNORECASE,
)
_INLINE_TOKEN_RE = re.compile(

    r"(\*\*.+?\*\*"
    r"|\*[^*\n]+?\*"
    r"|`[^`\n]+?`"
    r"|\[[^\]]+\]\([^)]+\))"
)


def slugify(text: str) -> str:
    """GitHub-ish anchor id from heading text."""
    s = text.strip().lower()
    s = s.replace("'", "").replace("'", "").replace("'", "")
    s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE)
    s = re.sub(r"[-\s]+", "-", s).strip("-")
    return s or "section"


def inline_html(text: str) -> str:
    """Escape text and apply a small set of inline markdown markers."""
    parts: list[str] = []
    pos = 0
    for m in _INLINE_TOKEN_RE.finditer(text):
        if m.start() > pos:
            parts.append(html.escape(text[pos : m.start()]))
        token = m.group(0)
        if token.startswith("**") and token.endswith("**"):
            parts.append(f"<strong>{inline_html(token[2:-2])}</strong>")
        elif token.startswith("*") and token.endswith("*"):
            parts.append(f"<em>{inline_html(token[1:-1])}</em>")
        elif token.startswith("`") and token.endswith("`"):
            parts.append(f"<code>{html.escape(token[1:-1])}</code>")
        elif token.startswith("["):
            link_m = re.match(r"\[([^\]]+)\]\(([^)]+)\)", token)
            if link_m:
                label, href = link_m.group(1), link_m.group(2)
                parts.append(
                    f'<a href="{html.escape(href, quote=True)}">'
                    f"{inline_html(label)}</a>"
                )
            else:
                parts.append(html.escape(token))
        else:
            parts.append(html.escape(token))
        pos = m.end()
    if pos < len(text):
        parts.append(html.escape(text[pos:]))
    return "".join(parts)


def _is_pending_src(src: str) -> bool:
    key = src.strip().lower()
    return key in {"", "#", "#pending", "pending", "todo", "placeholder"}


def youtube_video_id(src: str) -> str | None:
    """Return a YouTube video id from a watch/short/embed/youtu.be URL, or None."""
    m = _YOUTUBE_RE.match(src.strip())
    return m.group(1) if m else None


def figure_html(
    alt: str,
    src: str,
    *,
    caption: str | None = None,
    overview: bool = False,
) -> str:
    """Render a guide figure, file video, YouTube embed, or pending placeholder."""
    classes = ["guide-figure"]
    if overview:
        classes.append("guide-figure-overview")
    if _is_pending_src(src):
        classes.append("guide-figure-pending")
        label = caption or alt or "Image pending"
        return (
            f'<figure class="{" ".join(classes)}">'
            f'<div class="guide-figure-pending-frame" role="img" '
            f'aria-label="{html.escape(label, quote=True)}">'
            f'<span class="guide-figure-pending-label">'
            f"{inline_html(label)}"
            f"</span>"
            f"</div>"
            f"</figure>\n"
        )

    safe_src = html.escape(src, quote=True)
    safe_alt = html.escape(alt)
    lower = src.lower().split("?", 1)[0]
    yt_id = youtube_video_id(src)
    is_file_video = lower.endswith(_VIDEO_EXTS)
    is_video = bool(yt_id) or is_file_video

    if yt_id:
        embed = html.escape(
            f"https://www.youtube.com/embed/{yt_id}", quote=True
        )
        title = safe_alt or "YouTube video"
        media = (
            f'<div class="guide-youtube">'
            f'<iframe class="guide-youtube-frame" src="{embed}" '
            f'title="{title}" '
            f'allow="accelerometer; autoplay; clipboard-write; '
            f"encrypted-media; gyroscope; picture-in-picture; web-share\" "
            f'allowfullscreen loading="lazy" '
            f'referrerpolicy="strict-origin-when-cross-origin">'
            f"</iframe>"
            f"</div>"
        )
        classes.append("guide-figure-video")
        classes.append("guide-figure-youtube")
    elif is_file_video:
        media = (
            f'<video class="guide-video" controls preload="metadata" '
            f'playsinline src="{safe_src}">'
            f"<a href=\"{safe_src}\">Download video</a>"
            f"</video>"
        )
        classes.append("guide-figure-video")
    else:
        media = (
            f'<img src="{safe_src}" alt="{safe_alt}" loading="lazy" '
            f'decoding="async">'
        )

    cap_html = ""
    if caption:
        cap_html = f"<figcaption>{inline_html(caption)}</figcaption>"
    elif alt and is_video:
        cap_html = f"<figcaption>{inline_html(alt)}</figcaption>"

    return (
        f'<figure class="{" ".join(classes)}">'
        f"{media}"
        f"{cap_html}"
        f"</figure>\n"
    )



def _split_table_row(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]


def _is_table_header_pair(header: str, sep: str) -> bool:
    if "|" not in header:
        return False
    return bool(_TABLE_SEP_RE.match(sep))


@dataclass
class _ListItem:
    ordered: bool
    indent: int
    text_lines: list[str]
    children: list[_ListItem]


def _list_indent_level(ws: str) -> int:
    # Count indent in rough nesting steps (2 spaces or 1 tab).
    expanded = ws.replace("\t", "  ")
    return len(expanded) // 2


def _render_list_items(items: list[_ListItem]) -> str:
    if not items:
        return ""
    ordered = items[0].ordered
    tag = "ol" if ordered else "ul"
    parts = [f"<{tag}>"]
    for item in items:
        body = inline_html(" ".join(item.text_lines).strip())
        child_html = _render_list_items(item.children)
        if child_html:
            parts.append(f"<li>{body}{child_html}</li>")
        else:
            parts.append(f"<li>{body}</li>")
    parts.append(f"</{tag}>")
    return "".join(parts)


def _flush_paragraph(buf: list[str], out: list[str]) -> None:
    if not buf:
        return
    text = " ".join(line.strip() for line in buf if line.strip())
    buf.clear()
    if text:
        out.append(f"<p>{inline_html(text)}</p>\n")


def _flush_list(stack: list[_ListItem], out: list[str]) -> None:
    if not stack:
        return
    # stack holds roots only when we keep a parallel roots list — see parse loop.
    pass


def markdown_to_html(source: str) -> str:
    """Convert a markdown document to an HTML fragment."""
    lines = source.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out: list[str] = []
    i = 0
    n = len(lines)
    para: list[str] = []
    list_roots: list[_ListItem] = []
    # Stack of (indent, item) for nesting
    list_stack: list[tuple[int, _ListItem]] = []
    in_fence = False
    fence_lang = ""
    fence_lines: list[str] = []

    def end_list() -> None:
        nonlocal list_roots, list_stack
        if list_roots:
            out.append(_render_list_items(list_roots) + "\n")
        list_roots = []
        list_stack = []

    def end_para() -> None:
        _flush_paragraph(para, out)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if in_fence:
            if _FENCE_RE.match(stripped):
                code = html.escape("\n".join(fence_lines))
                lang_attr = (
                    f' class="language-{html.escape(fence_lang)}"'
                    if fence_lang
                    else ""
                )
                out.append(f"<pre><code{lang_attr}>{code}</code></pre>\n")
                in_fence = False
                fence_lang = ""
                fence_lines = []
            else:
                fence_lines.append(line)
            i += 1
            continue

        if stripped.startswith("```"):
            end_para()
            end_list()
            in_fence = True
            fence_lang = stripped[3:].strip()
            fence_lines = []
            i += 1
            continue

        if not stripped:
            end_para()
            end_list()
            i += 1
            continue

        if _HR_RE.match(stripped) and not stripped.startswith("#"):
            end_para()
            end_list()
            out.append("<hr>\n")
            i += 1
            continue

        hm = _HEADING_RE.match(stripped)
        if hm:
            end_para()
            end_list()
            level = len(hm.group(1))
            text = hm.group(2).strip()
            sid = slugify(text)
            out.append(
                f'<h{level} id="{html.escape(sid, quote=True)}">'
                f"{inline_html(text)}</h{level}>\n"
            )
            i += 1
            continue

        # Block image / video: ![alt](src) with optional italic caption line
        im = _IMAGE_RE.match(stripped)
        if im:
            end_para()
            end_list()
            alt = im.group(1).strip()
            src = im.group(2).strip()
            caption = (im.group(3) or im.group(4) or "").strip() or None
            overview = "overview" in alt.lower() or "minimap" in alt.lower()
            i += 1
            # Following italic-only line becomes figcaption when no title attr
            if caption is None and i < n:
                next_stripped = lines[i].strip()
                cap_m = _ITALIC_LINE_RE.match(next_stripped)
                if cap_m:
                    caption = cap_m.group(1).strip()
                    i += 1
            out.append(
                figure_html(alt, src, caption=caption, overview=overview)
            )
            continue

        # Table: header + separator + body rows
        if (
            i + 1 < n
            and "|" in line
            and _is_table_header_pair(line, lines[i + 1])
        ):
            end_para()
            end_list()
            headers = _split_table_row(line)
            i += 2
            rows: list[list[str]] = []
            while i < n and "|" in lines[i] and lines[i].strip():
                if _TABLE_SEP_RE.match(lines[i]):
                    i += 1
                    continue
                rows.append(_split_table_row(lines[i]))
                i += 1
            out.append('<div class="guide-table-wrap">\n')
            out.append("<table class=\"guide-table\">\n<thead><tr>")
            for h in headers:
                out.append(f"<th>{inline_html(h)}</th>")
            out.append("</tr></thead>\n<tbody>\n")
            for row in rows:
                # Pad/truncate to header width
                cells = row + [""] * max(0, len(headers) - len(row))
                out.append("<tr>")
                for c in cells[: len(headers)]:
                    out.append(f"<td>{inline_html(c)}</td>")
                out.append("</tr>\n")
            out.append("</tbody>\n</table>\n</div>\n")
            continue

        om = _OL_RE.match(line)
        um = _UL_RE.match(line)
        lm = om or um
        if lm:
            end_para()
            ordered = om is not None
            indent_ws = lm.group(1)
            level = _list_indent_level(indent_ws)
            text = lm.group(3)
            item = _ListItem(
                ordered=ordered, indent=level, text_lines=[text], children=[]
            )

            if not list_stack:
                list_roots.append(item)
                list_stack.append((level, item))
            else:
                while list_stack and level < list_stack[-1][0]:
                    list_stack.pop()
                if not list_stack:
                    list_roots.append(item)
                    list_stack.append((level, item))
                elif level > list_stack[-1][0]:
                    list_stack[-1][1].children.append(item)
                    list_stack.append((level, item))
                else:
                    # same level — sibling under same parent
                    list_stack.pop()
                    if list_stack:
                        list_stack[-1][1].children.append(item)
                    else:
                        list_roots.append(item)
                    list_stack.append((level, item))
            i += 1
            # continuation lines of list item (indented text without marker)
            while i < n:
                cont = lines[i]
                if not cont.strip():
                    break
                if _OL_RE.match(cont) or _UL_RE.match(cont):
                    break
                if _HEADING_RE.match(cont.strip()) or _HR_RE.match(cont.strip()):
                    break
                if cont.startswith(" ") or cont.startswith("\t"):
                    item.text_lines.append(cont.strip())
                    i += 1
                    continue
                break
            continue

        # Paragraph text
        end_list()
        para.append(line)
        i += 1

    end_para()
    end_list()
    if in_fence:
        code = html.escape("\n".join(fence_lines))
        out.append(f"<pre><code>{code}</code></pre>\n")

    return "".join(out)


def split_title_from_markdown(source: str) -> tuple[str | None, str]:
    """If doc starts with a single H1, return (title_text, rest_md)."""
    lines = source.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i >= len(lines):
        return None, source
    m = _HEADING_RE.match(lines[i].strip())
    if not m or len(m.group(1)) != 1:
        return None, source
    title = m.group(2).strip()
    rest = "\n".join(lines[i + 1 :]).lstrip("\n")
    return title, rest
