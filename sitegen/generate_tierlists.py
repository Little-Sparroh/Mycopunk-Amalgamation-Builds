"""Generate tierlist pages from CSV data under tierlists/."""

from __future__ import annotations

import html
from pathlib import Path

from sitegen.common import (
    NAV_SCRIPT,
    ROOT,
    TIER_ORDER,
    TIERLIST_NAV_ITEMS,
    NavItem,
    cell,
    find_image,
    github_csv_url_for_nav_item,
    html_document,
    image_url,
    is_present,
    load_csv_rows,
    local_image_dir,
    primary_nav_html,
    tier_class,
)

TIERLIST_IMAGE_FOLDER = "tierlist_images"
TIERLIST_IMAGE_DIR = local_image_dir(TIERLIST_IMAGE_FOLDER)


TIERLIST_ITEM_SCRIPT = """\
<script>
(function () {
  var root = document.querySelector(".tierlist");
  if (!root) return;
  var items = root.querySelectorAll("details.tierlist-item");
  if (!items.length) return;

  function closeAll(except) {
    items.forEach(function (d) {
      if (d !== except) d.open = false;
    });
  }

  items.forEach(function (d) {
    d.addEventListener("toggle", function () {
      if (d.open) closeAll(d);
    });
  });

  document.addEventListener("click", function (e) {
    if (!root.contains(e.target)) closeAll(null);
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeAll(null);
  });
})();
</script>
"""


def load_tierlist_rows(csv_path: Path) -> list[dict]:
    """Load tierlist CSV; forward-fill blank Tier cells."""
    rows_raw = load_csv_rows(csv_path)
    if not rows_raw:
        return []

    rows: list[dict] = []
    current_tier = ""
    for cleaned in rows_raw:
        weapon = cell(cleaned, "Weapon")
        if not weapon:
            continue
        tier_raw = cell(cleaned, "Tier")
        if tier_raw:
            letter = tier_raw.strip().upper()[:1]
            if letter in TIER_ORDER:
                current_tier = letter
        if not current_tier:
            current_tier = "F"
        rows.append(
            {
                "tier": current_tier,
                "weapon": weapon,
                "comment": cell(cleaned, "Comment", "Comments"),
            }
        )
    return rows


def tierlist_item_html(entry: dict, image_dir: Path) -> str:
    weapon = entry["weapon"]
    comment = entry["comment"]
    img_name = find_image(image_dir, weapon)
    safe_weapon = html.escape(weapon)

    img_html = ""
    if img_name:
        src = image_url(image_dir.name, img_name)
        img_html = (
            f'<img class="tierlist-item-img" '
            f'src="{html.escape(src, quote=True)}" '
            f'alt="{safe_weapon}" loading="lazy">'
        )

    else:
        img_html = (
            f'<span class="tierlist-item-img tierlist-item-img-missing" '
            f'aria-hidden="true"></span>'
        )

    name_html = f'<span class="tierlist-item-name">{safe_weapon}</span>'

    if is_present(comment):
        safe_comment = html.escape(comment)
        return (
            f'<details class="tierlist-item">\n'
            f'  <summary class="tierlist-item-summary">\n'
            f"    {img_html}\n"
            f"    {name_html}\n"
            f'    <span class="tierlist-item-caret" aria-hidden="true"></span>\n'
            f"  </summary>\n"
            f'  <div class="tierlist-item-comment">\n'
            f"    <p>{safe_comment}</p>\n"
            f"  </div>\n"
            f"</details>\n"
        )

    # No comment: static tile (not expandable)
    return (
        f'<div class="tierlist-item tierlist-item-static">\n'
        f"  {img_html}\n"
        f"  {name_html}\n"
        f"</div>\n"
    )


def tierlist_grid_html(rows: list[dict], image_dir: Path) -> str:
    if not rows:
        return "<p><em>No tierlist entries yet.</em></p>\n"

    by_tier: dict[str, list[dict]] = {t: [] for t in TIER_ORDER}
    for entry in rows:
        tier = entry["tier"] if entry["tier"] in by_tier else "F"
        by_tier[tier].append(entry)

    parts: list[str] = [
        '<section class="tierlist" aria-label="Weapon tier list">\n'
    ]
    for tier in TIER_ORDER:
        entries = by_tier[tier]
        if not entries:
            continue
        tclass = tier_class(tier)
        parts.append(f'  <div class="tierlist-row {tclass}">\n')
        parts.append(
            f'    <div class="tierlist-label" aria-label="{html.escape(tier)} tier">'
            f"{html.escape(tier)}</div>\n"
        )
        parts.append('    <div class="tierlist-items">\n')
        for entry in entries:
            item = tierlist_item_html(entry, image_dir)
            # indent item block
            for line in item.splitlines():
                parts.append(f"      {line}\n")
        parts.append("    </div>\n")
        parts.append("  </div>\n")
    parts.append("</section>\n")
    return "".join(parts)


def weapon_tierlist_body_html(item: NavItem) -> str:
    csv_path = ROOT / item.section / f"{item.page_id}.csv"
    rows = load_tierlist_rows(csv_path)
    parts: list[str] = []
    parts.append("<h1>Sparroh's Mycopunk Builds</h1>\n")
    parts.append(
        primary_nav_html(
            section=item.section, current_filename=item.filename
        )
    )
    parts.append(f'<h2 class="page-title">{html.escape(item.label)}</h2>\n')
    parts.append(
        "<p>Overall weapon rankings. Click a weapon for notes.</p>\n"
    )
    csv_href = html.escape(github_csv_url_for_nav_item(item))
    parts.append(
        f'<p class="page-source">'
        f'<a class="page-source-external" href="{csv_href}" '
        f'target="_blank" rel="noopener noreferrer" '
        f'title="Opens in a new tab" '
        f'aria-label="View CSV on GitHub (external link)">'
        f"View CSV"
        f'<span class="nav-external-mark" aria-hidden="true">↗</span>'
        f"</a>"
        f" — source data for this page"
        f"</p>\n"
    )
    parts.append(tierlist_grid_html(rows, TIERLIST_IMAGE_DIR))
    parts.append(NAV_SCRIPT)
    parts.append(TIERLIST_ITEM_SCRIPT)
    return "".join(parts)


def write_weapon_tierlist_page(item: NavItem) -> None:
    html_path = ROOT / item.section / item.filename
    html_path.parent.mkdir(parents=True, exist_ok=True)
    body = weapon_tierlist_body_html(item)
    doc = html_document(item.label, "../css/style.css", body)
    html_path.write_text(doc, encoding="utf-8", newline="\n")
    n = len(load_tierlist_rows(ROOT / item.section / f"{item.page_id}.csv"))
    print(f"Wrote {html_path.relative_to(ROOT)} (tierlist, {n} weapons)")


def write_stub_page(item: NavItem) -> None:
    """Fallback stub for non-weapon tierlists."""
    from sitegen.generate_guides import write_stub_page as _write_stub

    _write_stub(item)


def generate_all_tierlists() -> None:
    for item in TIERLIST_NAV_ITEMS:
        if item.page_id == "weapon_tierlist":
            write_weapon_tierlist_page(item)
        else:
            write_stub_page(item)


def main() -> None:
    generate_all_tierlists()


if __name__ == "__main__":
    main()
