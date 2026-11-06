"""Generate build pages from CSV data under builds/."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from pathlib import Path

from sitegen.common import (
    GITHUB_BLOB,
    NAV_SCRIPT,
    ROOT,
    auto_tier,
    cell,
    find_image,
    html_document,
    image_url,
    is_present,
    load_csv_rows,
    local_image_dir,
    parse_kill_time,
    present_tiers,
    primary_nav_html,
    tier_class,
    tier_id,
)



@dataclass(frozen=True)
class PageConfig:
    csv_path: Path
    html_path: Path
    title: str
    image_dir: Path
    mode: str  # "full" | "slim" | "times"
    description: str = ""

    @property
    def html_name(self) -> str:
        return self.html_path.name


PAGES = [
    PageConfig(
        csv_path=ROOT / "builds" / "no_restriction_builds.csv",
        html_path=ROOT / "builds" / "no_restriction_builds.html",
        title="Late Game Builds",
        image_dir=local_image_dir("no_restriction_images"),
        mode="full",
        description=(
            "Full endgame loadouts when you have everything available."
        ),
    ),
    PageConfig(
        csv_path=ROOT / "builds" / "no_infusion_builds.csv",
        html_path=ROOT / "builds" / "no_infusion_builds.html",
        title="Mid Game Builds",
        image_dir=local_image_dir("no_infusion_images"),
        mode="slim",
        description="Solid mid-progression setups before full endgame options.",
    ),
    PageConfig(
        csv_path=ROOT / "builds" / "no_rotation_builds.csv",
        html_path=ROOT / "builds" / "no_rotation_builds.html",
        title="Early Game Builds",
        image_dir=local_image_dir("no_rotation_images"),
        mode="slim",
        description="Early-game setups with limited options still in mind.",
    ),
    PageConfig(
        csv_path=ROOT / "builds" / "no_upgrade_times.csv",
        html_path=ROOT / "builds" / "no_upgrade_times.html",
        title="No Upgrade Times",
        image_dir=local_image_dir("no_upgrade_images"),
        mode="times",
        description=(
            "Baseline weapon kill times with no upgrades on Threat 1 Amalgamation."
        ),
    ),
]


def remote_image_src(page: PageConfig, filename: str) -> str:
    """Public URL in the image repo (folder name matches local lookup dir)."""
    return image_url(page.image_dir.name, filename)



def github_csv_url(page: PageConfig) -> str:
    rel = page.csv_path.relative_to(ROOT).as_posix()
    return f"{GITHUB_BLOB}/{rel}"


def prepare_build_rows(rows: list[dict], time_key: str = "Kill Time") -> list[dict]:
    """Filter, sort by kill time, assign auto tiers. CSV Tier is ignored."""
    prepared: list[dict] = []
    for row in rows:
        weapon = cell(row, "Weapon")
        if not weapon:
            continue
        entry = dict(row)
        entry["_weapon"] = weapon
        entry["_build"] = cell(row, "Build")
        entry["_time_raw"] = cell(row, time_key, "Kill Times", "Kill Time")
        entry["_time_sec"] = parse_kill_time(entry["_time_raw"])
        prepared.append(entry)

    timed = [r for r in prepared if r["_time_sec"] is not None]
    untimed = [r for r in prepared if r["_time_sec"] is None]
    timed.sort(key=lambda r: r["_time_sec"])

    n = len(timed)
    for i, row in enumerate(timed):
        row["_tier"] = auto_tier(i, n)
        row["_sort"] = i

    for j, row in enumerate(untimed):
        row["_tier"] = "F"
        row["_sort"] = n + j

    return timed + untimed


def write_field_html(label: str, value: str) -> str:
    if not is_present(value):
        return ""
    value = re.sub(r"\s*\n\s*", ", ", value).strip()
    return (
        f"    <p><strong>{html.escape(label)}:</strong> "
        f"{html.escape(value)}</p>\n"
    )


def build_card_html(
    page: PageConfig, row: dict, include_details: bool
) -> str:
    weapon = row["_weapon"]
    build = row["_build"]
    title = f"{weapon} – {build}" if build else weapon
    time_raw = row["_time_raw"] or "—"
    tier = row.get("_tier", "F")
    tclass = tier_class(tier)

    parts: list[str] = []
    parts.append(
        f'<div class="build {tclass}" data-tier="{html.escape(tier)}">\n'
    )
    parts.append('  <div class="build-text">\n')
    parts.append(f"    <h3>{html.escape(title)}</h3>\n")
    parts.append(
        f'    <p><strong>Kill Time:</strong> '
        f'<span class="kill-time">{html.escape(time_raw)}</span></p>\n'
    )

    if include_details:
        parts.append(write_field_html("Primary", cell(row, "Primary")))
        parts.append(write_field_html("Secondary", cell(row, "Secondary")))
        parts.append(write_field_html("Grenade", cell(row, "Grenade")))
        parts.append(
            write_field_html(
                "Elemental Cocktail", cell(row, "Elemental Cocktail")
            )
        )
        parts.append(write_field_html("Upgrades", cell(row, "Upgrades")))
        parts.append(
            write_field_html("Comments", cell(row, "Comments", "Comment"))
        )

    parts.append("  </div>\n")

    img_name = None
    if build:
        img_name = find_image(page.image_dir, weapon, build)
    if not img_name:
        img_name = find_image(page.image_dir, weapon)

    if img_name:
        src = html.escape(remote_image_src(page, img_name), quote=True)
        alt = html.escape(f"{weapon} {build}".strip())
        parts.append('  <div class="build-image">\n')
        parts.append(f'    <img src="{src}" alt="{alt}" loading="lazy">\n')
        parts.append("  </div>\n")


    parts.append("</div>\n\n")
    return "".join(parts)


def times_row_html(page: PageConfig, row: dict) -> str:
    weapon = row["_weapon"]
    time_raw = row["_time_raw"] or "—"
    img_name = find_image(page.image_dir, weapon)
    tier = row.get("_tier", "F")
    tclass = tier_class(tier)

    parts: list[str] = []
    parts.append(
        f'<div class="build {tclass}" data-tier="{html.escape(tier)}">\n'
    )
    parts.append('  <div class="build-text">\n')
    parts.append(f"    <h3>{html.escape(weapon)}</h3>\n")
    parts.append(
        f'    <p><strong>Kill Time:</strong> '
        f'<span class="kill-time">{html.escape(time_raw)}</span></p>\n'
    )
    parts.append(write_field_html("Comments", cell(row, "Comment", "Comments")))
    parts.append("  </div>\n")

    if img_name:
        src = html.escape(remote_image_src(page, img_name), quote=True)
        parts.append('  <div class="build-image">\n')
        parts.append(
            f'    <img src="{src}" alt="{html.escape(weapon)}" loading="lazy">\n'
        )
        parts.append("  </div>\n")


    parts.append("</div>\n\n")
    return "".join(parts)


def tier_nav_html(tiers: list[str]) -> str:
    if not tiers:
        return ""
    lines = ['<nav class="tier-nav" aria-label="Jump to tier">']
    lines.append('  <span class="tier-nav-label">Tiers</span>')
    for tier in tiers:
        tclass = tier_class(tier)
        tid = tier_id(tier)
        lines.append(
            f'  <a class="tier-nav-link {tclass}" href="#{tid}">'
            f"{html.escape(tier)}</a>"
        )
    lines.append("</nav>")
    return "\n".join(lines) + "\n\n"


def page_body_html(page: PageConfig, prepared: list[dict]) -> str:
    parts: list[str] = []
    # Match home: site title above nav so layout doesn't jump between pages.
    parts.append("<h1>Sparroh's Mycopunk Builds</h1>\n")
    parts.append(
        primary_nav_html(
            section="builds", current_filename=page.html_name
        )
    )

    main: list[str] = []
    # Collection title is h2.page-title (site h1 is already used above).
    main.append(
        f'<h2 class="page-title">{html.escape(page.title)}</h2>\n'
    )
    if page.description:
        main.append(f"<p>{html.escape(page.description)}</p>\n")
    csv_href = html.escape(github_csv_url(page))
    main.append(
        f'<p class="page-source">'
        f'<a class="page-source-external" href="{csv_href}" '
        f'target="_blank" rel="noopener noreferrer" '
        f'title="Opens in a new tab" '
        f'aria-label="View CSV on GitHub (external link)">'
        f"View CSV"
        f'<span class="nav-external-mark" aria-hidden="true">↗</span>'
        f"</a>"
        f" — condensed table for a quick glance"
        f"</p>\n"
    )

    if not prepared:
        main.append("<p><em>No builds recorded yet.</em></p>\n")
    else:
        current_tier = None
        for row in prepared:
            tier = row["_tier"]
            if tier != current_tier:
                tclass = tier_class(tier)
                tid = tier_id(tier)
                main.append(
                    f'<h2 id="{tid}" class="tier-heading {tclass}">'
                    f"{html.escape(tier)} Tier</h2>\n\n"
                )
                current_tier = tier

            if page.mode == "times":
                main.append(times_row_html(page, row))
            else:
                # full + slim both show gear/comments; empty CSV fields are skipped
                main.append(build_card_html(page, row, include_details=True))

    tiers = present_tiers(prepared) if prepared else []
    parts.append('<div class="build-layout">\n')
    parts.append(tier_nav_html(tiers))
    parts.append('<div class="build-main">\n')
    parts.extend(main)
    parts.append("</div>\n")
    parts.append("</div>\n")

    return "".join(parts)


def write_html_page(page: PageConfig, prepared: list[dict]) -> None:
    page.html_path.parent.mkdir(parents=True, exist_ok=True)
    body = page_body_html(page, prepared) + NAV_SCRIPT
    doc = html_document(page.title, "../css/style.css", body)
    page.html_path.write_text(doc, encoding="utf-8", newline="\n")


def generate_page(page: PageConfig) -> None:
    rows = load_csv_rows(page.csv_path)
    if page.mode == "times":
        prepared = prepare_build_rows(rows, time_key="Kill Times")
    else:
        prepared = prepare_build_rows(rows, time_key="Kill Time")

    write_html_page(page, prepared)
    n = len(prepared)
    print(f"Wrote {page.html_path.relative_to(ROOT)} ({n} rows)")


def generate_all_builds() -> None:
    for page in PAGES:
        generate_page(page)


def main() -> None:
    generate_all_builds()


if __name__ == "__main__":
    main()
