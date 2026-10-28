"""Generate the static HTML site for Mycopunk Amalgamation Builds.

GitHub Pages serves .md as raw text, so navigable pages are real .html files.
Also refreshes root README.md (repo landing) and ensures .nojekyll exists.
"""


from __future__ import annotations

import csv
import html
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GITHUB_BLOB = (
    "https://github.com/Little-Sparroh/Mycopunk-Amalgamation-Builds/blob/main"
)

# Bell-curve-ish cumulative upper bounds on rank percentile (0 = fastest).
# S ~8%, A ~15%, B ~25%, C ~25%, D ~15%, F ~12%
TIER_CUTOFFS = (
    (0.08, "S"),
    (0.23, "A"),
    (0.48, "B"),
    (0.73, "C"),
    (0.88, "D"),
    (1.00, "F"),
)
TIER_ORDER = ("S", "A", "B", "C", "D", "F")

# Short CSV weapon names -> image stem used under no_upgrade_images/
WEAPON_ALIASES = {
    "plate": "plate_launcher",
    "flinger": "lead_flinger",
    "lead flinger": "lead_flinger",
    "gunship": "gunship_cannon",
    "diffraction": "diffraction_driver",
    "swarm": "swarm_launcher",
    "laser": "laser_cannon",
    "laser cannon": "laser_cannon",
    "street sweeper": "street_sweeper",
    "last argument": "last_argument",
    "beam ripper": "beam_ripper",
    "dmlr": "dmlr",
}

IMAGE_EXTENSIONS = (".PNG", ".png", ".jpg", ".jpeg", ".webp")

RESOURCE_NAV_ITEMS = (
    ("Grid Solver", "https://coloronx.github.io/Mycopunk_UpgradeSolver/"),
    (
        "Carson's Builds",
        "https://docs.google.com/spreadsheets/d/16D7SskcxR_eVl4gwiiJHAC6Uj51Nqve1ip5ZPJP40NQ/edit?gid=1144611215#gid=1144611215",
    ),
    ("Wiki", "https://mycopunk.miraheze.org/wiki/Main_Page"),
    ("Modding", "https://thunderstore.io/c/mycopunk/"),
    ("Speedrunning", "https://www.speedrun.com/Mycopunk"),
)


@dataclass(frozen=True)
class NavItem:
    """One leaf page in the site nav tree."""

    label: str
    section: str  # builds | guides | tierlists
    filename: str  # e.g. no_restriction_builds.html
    description: str = ""

    @property
    def page_id(self) -> str:
        return self.filename.removesuffix(".html")

    def href(self, *, from_section: str | None) -> str:
        """Relative href from a page in from_section (None = site root)."""
        if from_section is None:
            return f"{self.section}/{self.filename}"
        if from_section == self.section:
            return self.filename
        return f"../{self.section}/{self.filename}"


def _title_from_stem(stem: str) -> str:
    """bruisers_bears_guide -> Bruiser's Bears Guide (light cleanup)."""
    text = stem.strip().lower()
    for suffix in ("_guide", "_tierlist", "_builds", "_times"):
        if text.endswith(suffix) and suffix != "_builds":
            # keep _builds/_times in display via explicit labels; strip guide/tierlist noise later
            pass
    # Explicit pretty names for known stems
    pretty = {
        "no_restriction_builds": "Late Game Builds",
        "no_infusion_builds": "Mid Game Builds",
        "no_rotation_builds": "Early Game Builds",
        "no_upgrade_times": "No Upgrade Times",
        "building_guide": "Building Guide",
        "carver_guide": "Carver Guide",
        "globbler_guide": "Globbler Guide",
        "modding_guide": "Modding Guide",
        "bruisers_bears_guide": "Bruiser's Bears Guide",
        "roachards_pumpkins_guide": "Roachard's Pumpkins Guide",
        "terrys_pumpkins_guide": "Terry's Pumpkins Guide",
        "weapon_tierlist": "Weapon Tierlist",
    }
    if text in pretty:
        return pretty[text]
    words = text.replace("-", "_").split("_")
    return " ".join(w.capitalize() for w in words if w)


NAV_SECTIONS: tuple[tuple[str, str], ...] = (
    ("builds", "Builds"),
    ("guides", "Guides"),
    ("tierlists", "Tierlists"),
)

# Leaf items — builds keep explicit order/labels; guides/tierlists from known files.
BUILD_NAV_ITEMS: tuple[NavItem, ...] = (
    NavItem(
        "Late Game Builds",
        "builds",
        "no_restriction_builds.html",
        "Full endgame loadouts when you have everything available.",
    ),
    NavItem(
        "Mid Game Builds",
        "builds",
        "no_infusion_builds.html",
        "Solid mid-progression setups before full endgame options.",
    ),
    NavItem(
        "Early Game Builds",
        "builds",
        "no_rotation_builds.html",
        "Early-game setups with limited options still in mind.",
    ),
    NavItem(
        "No Upgrade Times",
        "builds",
        "no_upgrade_times.html",
        "Baseline weapon kill times with no upgrades on Threat 1 Amalgamation.",
    ),
)

GUIDE_CSV_STEMS: tuple[str, ...] = (
    "building_guide",
    "carver_guide",
    "globbler_guide",
    "modding_guide",
    "bruisers_bears_guide",
    "roachards_pumpkins_guide",
    "terrys_pumpkins_guide",
)

TIERLIST_CSV_STEMS: tuple[str, ...] = ("weapon_tierlist",)


def _nav_items_for_stems(
    section: str, stems: tuple[str, ...], default_desc: str
) -> tuple[NavItem, ...]:
    items: list[NavItem] = []
    for stem in stems:
        items.append(
            NavItem(
                label=_title_from_stem(stem),
                section=section,
                filename=f"{stem}.html",
                description=default_desc,
            )
        )
    return tuple(items)


GUIDE_NAV_ITEMS = _nav_items_for_stems(
    "guides",
    GUIDE_CSV_STEMS,
    "Guide content coming soon.",
)
TIERLIST_NAV_ITEMS = _nav_items_for_stems(
    "tierlists",
    TIERLIST_CSV_STEMS,
    "Tierlist content coming soon.",
)

NAV_ITEMS_BY_SECTION: dict[str, tuple[NavItem, ...]] = {
    "builds": BUILD_NAV_ITEMS,
    "guides": GUIDE_NAV_ITEMS,
    "tierlists": TIERLIST_NAV_ITEMS,
}

ALL_NAV_ITEMS: tuple[NavItem, ...] = (
    BUILD_NAV_ITEMS + GUIDE_NAV_ITEMS + TIERLIST_NAV_ITEMS
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
        image_dir=ROOT / "assets" / "images" / "no_restriction_images",
        mode="full",
        description=(
            "Full endgame loadouts when you have everything available."
        ),
    ),
    PageConfig(
        csv_path=ROOT / "builds" / "no_infusion_builds.csv",
        html_path=ROOT / "builds" / "no_infusion_builds.html",
        title="Mid Game Builds",
        image_dir=ROOT / "assets" / "images" / "no_infusion_images",
        mode="slim",
        description="Solid mid-progression setups before full endgame options.",
    ),
    PageConfig(
        csv_path=ROOT / "builds" / "no_rotation_builds.csv",
        html_path=ROOT / "builds" / "no_rotation_builds.html",
        title="Early Game Builds",
        image_dir=ROOT / "assets" / "images" / "no_rotation_images",
        mode="slim",
        description="Early-game setups with limited options still in mind.",
    ),
    PageConfig(
        csv_path=ROOT / "builds" / "no_upgrade_times.csv",
        html_path=ROOT / "builds" / "no_upgrade_times.html",
        title="No Upgrade Times",
        image_dir=ROOT / "assets" / "images" / "no_upgrade_images",
        mode="times",
        description=(
            "Baseline weapon kill times with no upgrades on Threat 1 Amalgamation."
        ),
    ),
]





def normalize_key(*parts: str) -> str:
    text = "_".join(p.strip() for p in parts if p and p.strip())
    text = text.lower().replace("'", "").replace("'", "")
    text = text.replace("-", "_").replace(".", "").replace(" ", "_")
    text = re.sub(r"_+", "_", text)
    return text.strip("_")


def weapon_image_stem(weapon: str) -> str:
    raw = weapon.strip()
    key = raw.lower()
    if key in WEAPON_ALIASES:
        return WEAPON_ALIASES[key]
    stem = normalize_key(raw)
    if stem in WEAPON_ALIASES:
        return WEAPON_ALIASES[stem]
    return stem


def find_image(image_dir: Path, *name_parts: str) -> str | None:
    """Return the real on-disk image filename inside image_dir, or None.

    Always returns the actual filesystem name (correct casing) so GitHub Pages
    (Linux, case-sensitive) can resolve paths. Windows Path.exists() is
    case-insensitive and would otherwise let us emit wrong extensions like .PNG
    when the file is really .png.
    """
    if not image_dir.is_dir():
        return None

    # Map lower(name) -> actual name for case-correct lookups
    lower_map = {
        p.name.lower(): p.name for p in image_dir.iterdir() if p.is_file()
    }
    if not lower_map:
        return None

    base = normalize_key(*name_parts)
    candidates = [base]

    if base.startswith("swarm_launcher_"):
        candidates.append("swarmlauncher_" + base[len("swarm_launcher_") :])
    if base.startswith("swarm_"):
        candidates.append("swarmlauncher_" + base[len("swarm_") :])

    if len(name_parts) == 1:
        stem = weapon_image_stem(name_parts[0])
        candidates.append(f"{stem}_render")
        candidates.append(stem)

    seen: set[str] = set()
    ordered: list[str] = []
    for c in candidates:
        if c and c not in seen:
            seen.add(c)
            ordered.append(c)

    for stem in ordered:
        for ext in IMAGE_EXTENSIONS:
            hit = lower_map.get(f"{stem}{ext}".lower())
            if hit:
                return hit
    return None



def parse_kill_time(value: str | None) -> float | None:
    """Parse MM:SS.mmm or SS.mmm into seconds. None if missing/invalid."""
    if value is None:
        return None
    text = value.strip()
    if not text or text.lower() in {"n/a", "na", "-"}:
        return None
    text = text.replace(" ", "")
    try:
        if ":" in text:
            minutes, rest = text.split(":", 1)
            return int(minutes) * 60 + float(rest)
        return float(text)
    except ValueError:
        return None


def auto_tier(index: int, n: int) -> str:
    """Assign S–F from 0-based rank among n timed rows (0 = fastest)."""
    if n <= 0:
        return "F"
    if n == 1:
        return "S"
    percentile = (index + 0.5) / n
    for cutoff, tier in TIER_CUTOFFS:
        if percentile <= cutoff:
            return tier
    return "F"


def cell(row: dict, *keys: str) -> str:
    for key in keys:
        if key in row and row[key] is not None:
            return str(row[key]).strip()
    return ""


def is_present(value: str) -> bool:
    return bool(value) and value.lower() not in {"n/a", "na", "-"}


def rel_image_src(page: PageConfig, filename: str) -> str:
    folder = page.image_dir.name
    return f"../assets/images/{folder}/{filename}"


def github_csv_url(page: PageConfig) -> str:
    rel = page.csv_path.relative_to(ROOT).as_posix()
    return f"{GITHUB_BLOB}/{rel}"


def load_rows(page: PageConfig) -> list[dict]:
    if not page.csv_path.exists():
        return []
    text = page.csv_path.read_text(encoding="utf-8-sig").strip()
    if not text:
        return []
    with page.csv_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return []
        rows = []
        for row in reader:
            cleaned = {
                (k.strip() if isinstance(k, str) else k): (
                    v.strip() if isinstance(v, str) else v
                )
                for k, v in row.items()
                if k is not None
            }
            rows.append(cleaned)
        return rows


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


def tier_class(tier: str) -> str:
    letter = (tier or "F").strip().upper()[:1]
    if letter not in TIER_ORDER:
        letter = "F"
    return f"tier-{letter.lower()}"


def tier_id(tier: str) -> str:
    return f"tier-{(tier or 'F').strip().upper()[:1].lower()}"


def present_tiers(rows: list[dict]) -> list[str]:
    seen = {r.get("_tier", "F") for r in rows}
    return [t for t in TIER_ORDER if t in seen]


def html_document(
    title: str, css_href: str, body: str, *, extra_head: str = ""
) -> str:
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"  <title>{html.escape(title)}</title>\n"
        f'  <link rel="stylesheet" href="{html.escape(css_href)}">\n'
        f"{extra_head}"
        "</head>\n"
        "<body>\n"
        f"{body}"
        "</body>\n"
        "</html>\n"
    )


def home_href(*, from_section: str | None) -> str:
    if from_section is None:
        return "index.html"
    return "../index.html"


def _nav_link(
    label: str,
    href: str | None,
    *,
    current: bool = False,
) -> str:
    """Render a chip: link, or inert current-page span."""
    safe = html.escape(label)
    if current or href is None:
        return (
            f'  <span class="nav-link nav-link-current" aria-current="page">'
            f"{safe}</span>"
        )
    return (
        f'  <a class="nav-link" href="{html.escape(href)}">{safe}</a>'
    )


def _nav_dropdown(
    section_id: str,
    section_label: str,
    items: tuple[NavItem, ...],
    *,
    from_section: str | None,
) -> str:
    """Click-to-open dropdown of section children (used on Home)."""
    lines = [
        f'  <details class="nav-dropdown" data-nav-section="{html.escape(section_id)}">',
        f'    <summary class="nav-link nav-dropdown-trigger">'
        f"{html.escape(section_label)}"
        f'<span class="nav-dropdown-caret" aria-hidden="true"></span>'
        f"</summary>",
        '    <div class="nav-dropdown-panel" role="group" '
        f'aria-label="{html.escape(section_label)} pages">',
    ]
    for item in items:
        href = item.href(from_section=from_section)
        lines.append(
            f'      <a class="nav-dropdown-link" href="{html.escape(href)}">'
            f"{html.escape(item.label)}</a>"
        )
    lines.append("    </div>")
    lines.append("  </details>")
    return "\n".join(lines)


NAV_SCRIPT = """\
<script>
(function () {
  var nav = document.querySelector(".top-nav");
  if (!nav) return;
  var dropdowns = nav.querySelectorAll("details.nav-dropdown");
  if (!dropdowns.length) return;

  function closeAll(except) {
    dropdowns.forEach(function (d) {
      if (d !== except) d.open = false;
    });
  }

  dropdowns.forEach(function (d) {
    d.addEventListener("toggle", function () {
      if (d.open) closeAll(d);
    });
  });

  document.addEventListener("click", function (e) {
    if (!nav.contains(e.target)) closeAll(null);
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeAll(null);
  });
})();
</script>
"""


def primary_nav_html(
    *,
    section: str | None,
    current_filename: str | None = None,
) -> str:
    """Primary sticky nav.

    section=None (home): [Home] [Builds ▾] [Guides ▾] [Tierlists ▾]
    section=builds|guides|tierlists: [Home] + that section's children (flat)
    """
    lines = ['<nav class="top-nav" aria-label="Site">']

    # Home chip
    if section is None:
        lines.append(
            _nav_link("Home", None, current=True)
        )
    else:
        lines.append(_nav_link("Home", home_href(from_section=section)))

    if section is None:
        # Condensed top-level with dropdowns
        for sec_id, sec_label in NAV_SECTIONS:
            items = NAV_ITEMS_BY_SECTION[sec_id]
            lines.append(
                _nav_dropdown(
                    sec_id, sec_label, items, from_section=None
                )
            )
    else:
        # In-section: show that section's children as flat chips
        items = NAV_ITEMS_BY_SECTION.get(section, ())
        for item in items:
            is_current = item.filename == current_filename
            href = None if is_current else item.href(from_section=section)
            lines.append(
                _nav_link(item.label, href, current=is_current)
            )

    lines.append("</nav>")
    return "\n".join(lines) + "\n"


def resource_nav_html() -> str:

    lines = [
        '<nav class="top-nav top-nav-secondary" aria-label="Resources">'
    ]
    for label, href in RESOURCE_NAV_ITEMS:
        safe_label = html.escape(label)
        lines.append(
            f'  <a class="nav-link nav-link-external" '
            f'href="{html.escape(href)}" '
            f'target="_blank" rel="noopener noreferrer" '
            f'title="Opens in a new tab" '
            f'aria-label="{safe_label} (external link)">'
            f"{safe_label}"
            f'<span class="nav-external-mark" aria-hidden="true">↗</span>'
            f"</a>"
        )
    lines.append("</nav>")
    return "\n".join(lines) + "\n"



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
        parts.append(write_field_html("Comments", cell(row, "Comments")))

    parts.append("  </div>\n")

    img_name = None
    if build:
        img_name = find_image(page.image_dir, weapon, build)
    if not img_name:
        img_name = find_image(page.image_dir, weapon)

    if img_name:
        src = rel_image_src(page, img_name)
        alt = html.escape(f"{weapon} {build}".strip())
        parts.append('  <div class="build-image">\n')
        parts.append(f'    <img src="{src}" alt="{alt}">\n')
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
    parts.append("  </div>\n")

    if img_name:
        src = rel_image_src(page, img_name)
        parts.append('  <div class="build-image">\n')
        parts.append(
            f'    <img src="{src}" alt="{html.escape(weapon)}">\n'
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
            elif page.mode == "full":
                main.append(build_card_html(page, row, include_details=True))
            else:
                main.append(build_card_html(page, row, include_details=False))

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
    body = page_body_html(page, prepared)
    doc = html_document(page.title, "../css/style.css", body)
    page.html_path.write_text(doc, encoding="utf-8", newline="\n")


def generate_page(page: PageConfig) -> None:
    rows = load_rows(page)
    if page.mode == "times":
        prepared = prepare_build_rows(rows, time_key="Kill Times")
    else:
        prepared = prepare_build_rows(rows, time_key="Kill Time")

    write_html_page(page, prepared)
    n = len(prepared)
    print(f"Wrote {page.html_path.relative_to(ROOT)} ({n} rows)")



def knowledge_section_html() -> str:
    """Static knowledge block for index.html (mirrors README)."""
    return """\
<hr>

<h2>Knowledge to Give</h2>

<h3>Weapon Combos</h3>
<p>Most players use a Primary + Secondary setup.<br>
The best secondaries are <strong>Plate Launcher</strong>, <strong>Swarm Launcher</strong>, and <strong>Shocklance</strong>. Globbler is an honorable mention.</p>
<p>A dual-primary approach is also viable because dealing damage with one weapon regenerates ammo for the other.</p>

<h3>Element</h3>
<p>Choose your weapon element first.<br>
Trident has Normal, Fire, and Acid. Grenade choice follows the element (Normal is generally weaker).</p>
<p>Personal priority: <strong>Fire > Shock > Acid</strong>.<br>
Photon Disc can substitute for any element but comes with its own drawbacks and advantages.</p>

<h3>Employee</h3>
<p>All employees are viable and fill different niches:</p>
<ul>
  <li><strong>Wrangler</strong> — Very fast movement with strong 3D navigation</li>
  <li><strong>Bruiser</strong> — Good movement that depends on specific upgrades and player skill</li>
  <li><strong>Scrapper</strong> — Easiest vertical movement</li>
  <li><strong>Glider</strong> — Easiest horizontal movement</li>
  <li><strong>Mycologist</strong> — Has the most complex gameplay but offers great overall movement.</li>
</ul>
<p>Some builds prefer certain employees:</p>
<ul>
  <li>Gunship Cannon + Gunship upgrade is not ideal on Bruiser</li>
  <li>Accelerator damage scaling favors Wrangler</li>
  <li>Carver gets the most out of Scrapper</li>
</ul>

<h3>Heavy Weapons</h3>
<p>Heavy weapons are generally weak even with upgrades.<br>
They are more usable now as tools rather than main damage sources.</p>

<h3>Grenades</h3>
<p>Fire is still the strongest overall.<br>
Shock is weapon-dependent. Acid is mostly a last resort.<br>
Photon is excellent for Normal damage, ammo regen, or multi-element support.<br>
Snowball is used purely for cryo which is niche.</p>
"""


def write_index_html() -> None:
    body_parts = [
        "<h1>Sparroh's Mycopunk Builds</h1>\n",
        primary_nav_html(section=None),
        resource_nav_html(),
        knowledge_section_html(),
        NAV_SCRIPT,
    ]
    doc = html_document(
        "Sparroh's Mycopunk Builds",
        "css/style.css",
        "".join(body_parts),
    )

    path = ROOT / "index.html"
    path.write_text(doc, encoding="utf-8", newline="\n")
    print(f"Wrote {path.relative_to(ROOT)}")


def github_csv_url_for_nav_item(item: NavItem) -> str:
    rel = f"{item.section}/{item.page_id}.csv"
    return f"{GITHUB_BLOB}/{rel}"


def stub_page_body_html(item: NavItem) -> str:
    """Minimal section page until guide/tierlist content is filled in."""
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
    parts.append(
        '<p class="page-placeholder"><em>Full page content will appear here '
        "once the CSV is filled in.</em></p>\n"
    )
    return "".join(parts)


def write_stub_page(item: NavItem) -> None:
    html_path = ROOT / item.section / item.filename
    html_path.parent.mkdir(parents=True, exist_ok=True)
    # Ensure sibling CSV exists so links and future generators have a target.
    csv_path = ROOT / item.section / f"{item.page_id}.csv"
    if not csv_path.exists():
        csv_path.write_text("", encoding="utf-8", newline="\n")
    body = stub_page_body_html(item)
    doc = html_document(item.label, "../css/style.css", body)
    html_path.write_text(doc, encoding="utf-8", newline="\n")
    print(f"Wrote {html_path.relative_to(ROOT)} (stub)")


TIERLIST_IMAGE_DIR = ROOT / "assets" / "images" / "tierlist_images"

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
    if not csv_path.exists():
        return []
    text = csv_path.read_text(encoding="utf-8-sig").strip()
    if not text:
        return []
    rows: list[dict] = []
    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return []
        current_tier = ""
        for raw in reader:
            cleaned = {
                (k.strip() if isinstance(k, str) else k): (
                    v.strip() if isinstance(v, str) else (v or "")
                )
                for k, v in raw.items()
                if k is not None
            }
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
        src = f"../assets/images/{image_dir.name}/{img_name}"
        img_html = (
            f'<img class="tierlist-item-img" src="{html.escape(src)}" '
            f'alt="{safe_weapon}">'
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


def write_section_stub_pages() -> None:
    for item in GUIDE_NAV_ITEMS:
        write_stub_page(item)
    for item in TIERLIST_NAV_ITEMS:
        if item.page_id == "weapon_tierlist":
            write_weapon_tierlist_page(item)
        else:
            write_stub_page(item)



def write_readme() -> None:
    """Keep README in sync with HTML nav targets for the repo landing page."""
    lines = [
        '<link rel="stylesheet" href="css/style.css">',
        "",
        "# Sparroh's Mycopunk Builds",
        "",
        "> **GitHub Pages:** open **[index.html](index.html)** (or the Pages site root). "
        "Build guides are HTML — links below go to `.html` pages that render with CSS.",
        "",
        '<nav class="top-nav" aria-label="Site">',
        '  <span class="nav-link nav-link-current" aria-current="page">Home</span>',
    ]

    # README can't run dropdown JS reliably; list sections as nested markdown.
    lines.append("</nav>")
    lines.append("")
    for sec_id, sec_label in NAV_SECTIONS:
        lines.append(f"### {sec_label}")
        lines.append("")
        for item in NAV_ITEMS_BY_SECTION[sec_id]:
            lines.append(
                f"- [{item.label}]({item.section}/{item.filename})"
            )
        lines.append("")

    lines.append('<nav class="top-nav top-nav-secondary" aria-label="Resources">')
    for label, href in RESOURCE_NAV_ITEMS:
        lines.append(
            f'  <a class="nav-link nav-link-external" href="{href}" '
            f'target="_blank" rel="noopener noreferrer" '
            f'title="Opens in a new tab" '
            f'aria-label="{label} (external link)">'
            f"{label}"
            f'<span class="nav-external-mark" aria-hidden="true">↗</span>'
            f"</a>"
        )
    lines.append("</nav>")

    lines.append("")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Knowledge to Give")
    lines.append("")
    lines.append("### Weapon Combos")
    lines.append("Most players use a Primary + Secondary setup.  ")
    lines.append(
        "The best secondaries are **Plate Launcher**, **Swarm Launcher**, and **Shocklance**. Globbler is an honorable mention."
    )
    lines.append("")
    lines.append(
        "A dual-primary approach is also viable because dealing damage with one weapon regenerates ammo for the other."
    )
    lines.append("")
    lines.append("### Element")
    lines.append("Choose your weapon element first.  ")
    lines.append(
        "Trident has Normal, Fire, and Acid. Grenade choice follows the element (Normal is generally weaker)."
    )
    lines.append("")
    lines.append("Personal priority: **Fire > Shock > Acid**.  ")
    lines.append(
        "Photon Disc can substitute for any element but comes with its own drawbacks and advantages."
    )
    lines.append("")
    lines.append("### Employee")
    lines.append("All employees are viable and fill different niches:")
    lines.append("")
    lines.append("- **Wrangler** — Very fast movement with strong 3D navigation")
    lines.append(
        "- **Bruiser** — Good movement that depends on specific upgrades and player skill"
    )
    lines.append("- **Scrapper** — Easiest vertical movement")
    lines.append("- **Glider** — Easiest horizontal movement")
    lines.append(
        "- **Mycologist** — Has the most complex gameplay but offers great overall movement."
    )
    lines.append("")
    lines.append("Some builds prefer certain employees:")
    lines.append("- Gunship Cannon + Gunship upgrade is not ideal on Bruiser")
    lines.append("- Accelerator damage scaling favors Wrangler")
    lines.append("- Carver gets the most out of Scrapper")
    lines.append("")
    lines.append("### Heavy Weapons")
    lines.append("Heavy weapons are generally weak even with upgrades.  ")
    lines.append(
        "They are more usable now as tools rather than main damage sources."
    )
    lines.append("")
    lines.append("### Grenades")
    lines.append("Fire is still the strongest overall.  ")
    lines.append("Shock is weapon-dependent. Acid is mostly a last resort.  ")
    lines.append(
        "Photon is excellent for Normal damage, ammo regen, or multi-element support.  "
    )
    lines.append("Snowball is used purely for cryo which is niche.")
    lines.append("")

    path = ROOT / "README.md"
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"Wrote {path.relative_to(ROOT)}")


def ensure_nojekyll() -> None:
    path = ROOT / ".nojekyll"
    if not path.exists():
        path.write_text("", encoding="utf-8")
        print("Wrote .nojekyll")
    else:
        print(".nojekyll already present")


def main() -> None:
    ensure_nojekyll()
    write_index_html()
    write_readme()
    write_section_stub_pages()
    for page in PAGES:
        generate_page(page)


if __name__ == "__main__":
    main()

