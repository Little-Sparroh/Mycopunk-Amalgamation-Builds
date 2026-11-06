"""One-off debug + regenerate guides."""
from __future__ import annotations

from pathlib import Path

from sitegen.common import GUIDE_NAV_ITEMS, ROOT, _GUIDE_DESCRIPTIONS
from sitegen.generate_guides import (
    generate_all_guides,
    guide_md_path,
    md_is_full_guide,
)

out = []
out.append(f"ROOT={ROOT}")
out.append(f"descs={_GUIDE_DESCRIPTIONS}")
for item in GUIDE_NAV_ITEMS:
    md = guide_md_path(item)
    exists = md.is_file()
    text = md.read_text(encoding="utf-8") if exists else ""
    out.append(
        f"{item.page_id} exists={exists} chars={len(text.strip())} "
        f"full={md_is_full_guide(text) if exists else False} "
        f"desc={item.description!r}"
    )

generate_all_guides()

for p in sorted((ROOT / "guides").glob("*.html")):
    t = p.read_text(encoding="utf-8")
    mode = (
        "scavenger"
        if "guide-scavenger" in t
        else ("prose" if 'class="guide-body"' in t else "stub")
    )
    out.append(
        f"HTML {p.name}: {mode} figures={t.count('guide-figure')} "
        f"steps={t.count('guide-step')} bytes={len(t)}"
    )

report = ROOT / "guides" / "_gen_report.txt"
report.write_text("\n".join(out) + "\n", encoding="utf-8")
print("\n".join(out))
