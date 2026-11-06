"""Shared nav, HTML shell, and helpers for site generators."""

from __future__ import annotations

import csv
import html
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GITHUB_BLOB = (
    "https://github.com/Little-Sparroh/Mycopunk-Amalgamation-Builds/blob/main"
)

# Screenshots / media live in a separate repo so site deploys stay small.
# Prefer a local assets/ tree when present (dev); else depreciated-assets cache.
IMAGE_REPO = "Little-Sparroh/Mycopunk-Abomination-Image-Repo"
IMAGE_BASE_URL = (
    f"https://raw.githubusercontent.com/{IMAGE_REPO}/main"
)
LOCAL_IMAGE_ROOTS = (
    ROOT / "assets" / "images",
    ROOT / "depreciated-assets" / "images",
)


def image_url(folder: str, filename: str) -> str:
    """Absolute raw.githubusercontent URL for a file in the image repo."""
    folder = folder.strip("/").replace("\\", "/")
    filename = filename.strip("/").replace("\\", "/")
    return f"{IMAGE_BASE_URL}/{folder}/{filename}"


def local_image_dir(folder: str) -> Path:
    """Directory used only for find_image() filename/casing lookup."""
    name = folder.strip("/").replace("\\", "/")
    for root in LOCAL_IMAGE_ROOTS:
        candidate = root / name
        if candidate.is_dir():
            return candidate
    # Default path generators historically used (may not exist yet).
    return ROOT / "assets" / "images" / name

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
    ("Modding Wiki", "https://modding.mycopunk.wiki/"),
    ("Thunderstore", "https://thunderstore.io/c/mycopunk/"),
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
    pretty = {
        "no_restriction_builds": "Late Game Builds",
        "no_infusion_builds": "Mid Game Builds",
        "no_rotation_builds": "Early Game Builds",
        "no_upgrade_times": "No Upgrade Times",
        "building_guide": "Building Guide",
        "carver_guide": "Carver Guide",
        "globbler_guide": "Globbler Guide",
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


_GUIDE_DESCRIPTIONS: dict[str, str] = {
    "building_guide": "How to think about loadouts before chasing times.",
    "carver_guide": "Quest-chain locations to unlock Carver.",
    "globbler_guide": "Light and map steps to unlock Globbler.",
    "bruisers_bears_guide": "Numbered Ice Floes bear locations.",
    "roachards_pumpkins_guide": "Singularity pumpkin locations for Roachard.",
    "terrys_pumpkins_guide": "Shipping Lane pumpkin locations for Terry.",
}

# Building Guide is long-form prose; everything else is picture-led scavenger.
SCAVENGER_GUIDE_STEMS: frozenset[str] = frozenset(
    {
        "carver_guide",
        "globbler_guide",
        "bruisers_bears_guide",
        "roachards_pumpkins_guide",
        "terrys_pumpkins_guide",
    }
)



def _guide_nav_items() -> tuple[NavItem, ...]:
    items: list[NavItem] = []
    for stem in GUIDE_CSV_STEMS:
        items.append(
            NavItem(
                label=_title_from_stem(stem),
                section="guides",
                filename=f"{stem}.html",
                description=_GUIDE_DESCRIPTIONS.get(
                    stem, "Guide content coming soon."
                ),
            )
        )
    return tuple(items)


GUIDE_NAV_ITEMS = _guide_nav_items()
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


def _image_stem_candidates(*name_parts: str) -> list[str]:
    """Ordered filename stems (no extension) for a weapon / weapon+build key."""
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
    return ordered


def _canonical_remote_filename(*name_parts: str) -> str | None:
    """Best-guess filename matching the image repo when no local cache exists.

    Build screenshots use ``weapon_build.PNG``.
    Weapon portraits (times / tierlist) use ``{stem}_render.png``.
    """
    ordered = _image_stem_candidates(*name_parts)
    if not ordered:
        return None

    if len(name_parts) >= 2:
        # e.g. jackrabbit_double_barrel.PNG
        return f"{ordered[0]}.PNG"

    # Single weapon: prefer *_render.png (no_upgrade_images / tierlist_images)
    for stem in ordered:
        if stem.endswith("_render"):
            return f"{stem}.png"
    return f"{ordered[0]}.png"


def find_image(image_dir: Path, *name_parts: str) -> str | None:
    """Return an image filename for the given name parts, or None.

    When ``image_dir`` exists locally, returns the real on-disk name (correct
    casing) so case-sensitive hosts resolve paths. Windows Path.exists() is
    case-insensitive and would otherwise let us emit wrong extensions.

    When there is no local cache (images live only in the image repo), returns
    a canonical remote filename so generators can still emit working URLs.
    """
    ordered = _image_stem_candidates(*name_parts)
    if not ordered:
        return None

    if image_dir.is_dir():
        lower_map = {
            p.name.lower(): p.name for p in image_dir.iterdir() if p.is_file()
        }
        if lower_map:
            for stem in ordered:
                for ext in IMAGE_EXTENSIONS:
                    hit = lower_map.get(f"{stem}{ext}".lower())
                    if hit:
                        return hit
            # Local folder exists but nothing matched this key.
            return None

    return _canonical_remote_filename(*name_parts)



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
    return f'  <a class="nav-link" href="{html.escape(href)}">{safe}</a>'


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


def _external_links_dropdown_html() -> str:
    """Primary-nav dropdown for off-site resources (replaces secondary nav row)."""
    lines = [
        '  <details class="nav-dropdown" data-nav-section="external">',
        '    <summary class="nav-link nav-dropdown-trigger">'
        "External Links"
        '<span class="nav-dropdown-caret" aria-hidden="true"></span>'
        "</summary>",
        '    <div class="nav-dropdown-panel" role="group" '
        'aria-label="External links">',
    ]
    for label, href in RESOURCE_NAV_ITEMS:
        safe_label = html.escape(label)
        lines.append(
            f'      <a class="nav-dropdown-link nav-dropdown-link-external" '
            f'href="{html.escape(href)}" '
            f'target="_blank" rel="noopener noreferrer" '
            f'title="Opens in a new tab" '
            f'aria-label="{safe_label} (external link)">'
            f"{safe_label}"
            f'<span class="nav-external-mark" aria-hidden="true">↗</span>'
            f"</a>"
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

    section=None (home): [Home] [Builds ▾] [Guides ▾] [Tierlists ▾] [External Links ▾]
    section=builds|guides|tierlists: [Home] + section children (flat) + [External Links ▾]
    """
    lines = ['<nav class="top-nav" aria-label="Site">']

    # Home chip
    if section is None:
        lines.append(_nav_link("Home", None, current=True))
    else:
        lines.append(_nav_link("Home", home_href(from_section=section)))

    if section is None:
        # Condensed top-level with dropdowns
        for sec_id, sec_label in NAV_SECTIONS:
            items = NAV_ITEMS_BY_SECTION[sec_id]
            lines.append(
                _nav_dropdown(sec_id, sec_label, items, from_section=None)
            )
    else:
        # In-section: show that section's children as flat chips
        items = NAV_ITEMS_BY_SECTION.get(section, ())
        for item in items:
            is_current = item.filename == current_filename
            href = None if is_current else item.href(from_section=section)
            lines.append(_nav_link(item.label, href, current=is_current))

    # External resources — always available from primary nav
    lines.append(_external_links_dropdown_html())

    lines.append("</nav>")
    return "\n".join(lines) + "\n"


def github_blob_url(*parts: str) -> str:
    """URL to a file on the main-branch GitHub blob view."""
    rel = "/".join(p.strip("/").replace("\\", "/") for p in parts if p)
    return f"{GITHUB_BLOB}/{rel}"


def github_csv_url_for_nav_item(item: NavItem) -> str:
    return github_blob_url(item.section, f"{item.page_id}.csv")


def github_md_url_for_nav_item(item: NavItem) -> str:
    return github_blob_url(item.section, f"{item.page_id}.md")


def load_csv_rows(csv_path: Path) -> list[dict]:
    """Load a CSV as a list of stripped dict rows."""
    if not csv_path.exists():
        return []
    text = csv_path.read_text(encoding="utf-8-sig").strip()
    if not text:
        return []
    with csv_path.open(newline="", encoding="utf-8-sig") as f:
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


def ensure_nojekyll() -> None:
    path = ROOT / ".nojekyll"
    if not path.exists():
        path.write_text("", encoding="utf-8")
        print("Wrote .nojekyll")
    else:
        print(".nojekyll already present")
