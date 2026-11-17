"""Generate build pages from CSV data under builds/."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from pathlib import Path

from sitegen.common import (
    GITHUB_BLOB,
    IMAGE_EXTENSIONS,
    NAV_SCRIPT,
    ROOT,
    auto_tier,
    cell,
    find_column_image,
    find_image,
    html_document,
    image_url,
    is_present,
    list_remote_image_names,
    load_csv_rows,
    local_image_dir,
    normalize_key,
    parse_kill_time,
    present_tiers,
    primary_nav_html,
    tier_class,
    tier_id,
    weapon_image_stem,
)

# Row/Column screenshot swap on build cards (mid/early when companion exists).
IMAGE_SWAP_SCRIPT = """\
<script>
(function () {
  function activate(root, view) {
    root.querySelectorAll(".build-image-toggle [data-show]").forEach(function (btn) {
      var on = btn.getAttribute("data-show") === view;
      btn.classList.toggle("is-active", on);
      btn.setAttribute("aria-pressed", on ? "true" : "false");
    });
    root.querySelectorAll("img[data-view]").forEach(function (img) {
      if (img.getAttribute("data-view") === view) img.removeAttribute("hidden");
      else img.setAttribute("hidden", "");
    });
  }

  document.querySelectorAll(".build-image-swap").forEach(function (root) {
    var toggle = root.querySelector(".build-image-toggle");
    if (toggle) {
      toggle.addEventListener("click", function (e) {
        var btn = e.target.closest("[data-show]");
        if (!btn || !toggle.contains(btn)) return;
        activate(root, btn.getAttribute("data-show"));
      });
    }

    var col = root.querySelector('img[data-view="column"]');
    if (col) {
      col.addEventListener("error", function onColError() {
        col.removeEventListener("error", onColError);
        if (toggle) toggle.remove();
        col.remove();
        root.classList.remove("build-image-swap");
        var row = root.querySelector('img[data-view="row"]');
        if (row) {
          row.removeAttribute("hidden");
          row.removeAttribute("data-view");
        }
      });
    }
  });
})();
</script>
"""

# Discord-style lightbox for build screenshots (all build pages).
IMAGE_LIGHTBOX_SCRIPT = """\
<script>
(function () {
  var overlay = null;
  var panelImg = null;
  var lastFocus = null;

  function ensure() {
    if (overlay) return overlay;
    overlay = document.createElement("div");
    overlay.id = "image-lightbox";
    overlay.className = "image-lightbox";
    overlay.hidden = true;
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");
    overlay.setAttribute("aria-label", "Enlarged screenshot");
    overlay.innerHTML =
      '<button type="button" class="image-lightbox-close" aria-label="Close">' +
      "&times;</button>" +
      '<div class="image-lightbox-stage">' +
      '<img class="image-lightbox-img" alt="">' +
      "</div>";
    document.body.appendChild(overlay);
    panelImg = overlay.querySelector(".image-lightbox-img");

    overlay.addEventListener("click", function (e) {
      if (e.target === overlay || e.target.classList.contains("image-lightbox-stage")) {
        close();
      }
    });
    overlay.querySelector(".image-lightbox-close").addEventListener("click", function (e) {
      e.stopPropagation();
      close();
    });
    panelImg.addEventListener("click", function (e) {
      e.stopPropagation();
    });
    return overlay;
  }

  function open(src, alt) {
    if (!src) return;
    ensure();
    lastFocus = document.activeElement;
    panelImg.src = src;
    panelImg.alt = alt || "";
    overlay.hidden = false;
    document.body.classList.add("lightbox-open");
    overlay.querySelector(".image-lightbox-close").focus();
  }

  function close() {
    if (!overlay || overlay.hidden) return;
    overlay.hidden = true;
    document.body.classList.remove("lightbox-open");
    if (panelImg) {
      panelImg.removeAttribute("src");
      panelImg.alt = "";
    }
    if (lastFocus && typeof lastFocus.focus === "function") {
      try { lastFocus.focus(); } catch (err) {}
    }
    lastFocus = null;
  }

  document.addEventListener("click", function (e) {
    // Gear field buttons (Primary/Secondary/Grenade/Employee test shots)
    var trigger = e.target.closest("[data-lightbox-src]");
    if (trigger) {
      var tsrc = trigger.getAttribute("data-lightbox-src");
      if (!tsrc) return;
      e.preventDefault();
      open(
        tsrc,
        trigger.getAttribute("data-lightbox-alt") ||
          (trigger.textContent || "").trim()
      );
      return;
    }

    var img = e.target.closest(".build-image img");
    if (!img || img.hasAttribute("hidden")) return;
    // Don't treat missing/broken as openable if no src
    if (!img.getAttribute("src")) return;
    e.preventDefault();
    open(img.currentSrc || img.src, img.alt || "");
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") close();
  });
})();
</script>
"""

# Companion gear / employee screenshots (image repo folder).
TEST_BUILD_IMAGE_FOLDER = "test_build_images"

# lowercased filename -> real casing; None = not loaded yet; {} = empty/failed
_test_build_name_map: dict[str, str] | None = None


def _test_build_filename_map() -> dict[str, str]:
    """Map lowercased filename -> real name for test_build_images."""
    global _test_build_name_map
    if _test_build_name_map is not None:
        return _test_build_name_map

    image_dir = local_image_dir(TEST_BUILD_IMAGE_FOLDER)
    if image_dir.is_dir():
        local = {
            p.name.lower(): p.name
            for p in image_dir.iterdir()
            if p.is_file()
        }
        if local:
            _test_build_name_map = local
            return _test_build_name_map

    remote = list_remote_image_names(TEST_BUILD_IMAGE_FOLDER)
    _test_build_name_map = dict(remote) if remote else {}
    return _test_build_name_map


def _gear_stem_candidates(gear_name: str) -> list[str]:
    """Normalized stems used to match a CSV gear name to test image files."""
    ordered: list[str] = []
    seen: set[str] = set()
    for raw in (normalize_key(gear_name), weapon_image_stem(gear_name)):
        if raw and raw not in seen:
            seen.add(raw)
            ordered.append(raw)
    return ordered


def find_test_build_image(gear_name: str) -> str | None:
    """First test_build_images filename for this gear name, or None.

    Match rule (gear name only; build suffix ignored):
    - exact stem match (``swarm_launcher.PNG``), else
    - stem prefix (``swarm_launcher_munition_siphon.PNG``).
    When several prefix hits exist, prefer the shortest stem.
    """
    if not is_present(gear_name):
        return None

    name_map = _test_build_filename_map()
    if not name_map:
        return None

    stems = _gear_stem_candidates(gear_name)
    if not stems:
        return None

    # Exact stem + extension
    for stem in stems:
        for ext in IMAGE_EXTENSIONS:
            hit = name_map.get(f"{stem}{ext}".lower())
            if hit:
                return hit

    # Prefix: gear_…
    best: str | None = None
    best_key: tuple[int, str] | None = None
    for fname in name_map.values():
        fstem = Path(fname).stem.lower()
        for stem in stems:
            if fstem == stem or fstem.startswith(stem + "_"):
                key = (len(fstem), fstem)
                if best_key is None or key < best_key:
                    best_key = key
                    best = fname
                break
    return best





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


def write_gear_field_html(label: str, value: str) -> str:
    """Field row; value opens test-build lightbox when a screenshot exists."""
    if not is_present(value):
        return ""
    value = re.sub(r"\s*\n\s*", ", ", value).strip()
    img_name = find_test_build_image(value)
    if not img_name:
        return write_field_html(label, value)

    src = html.escape(
        image_url(TEST_BUILD_IMAGE_FOLDER, img_name), quote=True
    )
    alt = html.escape(value, quote=True)
    label_esc = html.escape(label)
    value_esc = html.escape(value)
    return (
        f"    <p><strong>{label_esc}:</strong> "
        f'<button type="button" class="gear-test-trigger" '
        f'data-lightbox-src="{src}" data-lightbox-alt="{alt}" '
        f'title="View test build screenshot">'
        f"{value_esc}</button></p>\n"
    )


# Rarity letter codes in the Upgrades CSV cell.
# O Oddity, X Exotic, E Epic, R Rare, S Standard. Missing letter → Other.
RARITY_CODES: dict[str, str] = {
    "O": "Oddity",
    "X": "Exotic",
    "E": "Epic",
    "R": "Rare",
    "S": "Standard",
}
RARITY_ORDER: tuple[str, ...] = (
    "Oddity",
    "Exotic",
    "Epic",
    "Rare",
    "Standard",
    "Other",
)
RARITY_SLUG: dict[str, str] = {
    "Oddity": "oddity",
    "Exotic": "exotic",
    "Epic": "epic",
    "Rare": "rare",
    "Standard": "standard",
    "Other": "other",
}

# One upgrade token, e.g. "O Boundary Incursion (Cyclotron) x2"
# All of rarity / infusion / stack are optional.
_UPGRADE_TOKEN_RE = re.compile(
    r"""
    ^\s*
    (?:(?P<rarity>[OXERS])\s+)?          # optional rarity letter
    (?P<name>.+?)                         # upgrade name (required)
    (?:\s*\(\s*(?P<infusion>[^)]*?)\s*\))?  # optional (infusion)
    (?:\s*[x×]\s*(?P<count>\d+))?        # optional xN / ×N
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)


@dataclass(frozen=True)
class UpgradeEntry:
    rarity: str  # display label; "Other" if unspecified
    name: str
    infusion: str  # may be ""
    count: int  # >= 1


def parse_upgrade_token(token: str) -> UpgradeEntry | None:
    """Parse one comma-separated upgrade fragment. None if no usable name."""
    text = token.strip()
    if not text:
        return None

    m = _UPGRADE_TOKEN_RE.match(text)
    if not m:
        # Last resort: treat the whole token as a nameless-rarity upgrade.
        if text:
            return UpgradeEntry(rarity="Other", name=text, infusion="", count=1)
        return None

    raw_name = (m.group("name") or "").strip()
    # Name group is non-greedy and may absorb trailing junk; strip again.
    raw_name = re.sub(r"\s+", " ", raw_name).strip(" ,;")
    if not raw_name:
        return None

    rarity_letter = (m.group("rarity") or "").upper()
    rarity = RARITY_CODES.get(rarity_letter, "Other")

    infusion = (m.group("infusion") or "").strip()
    count_raw = m.group("count")
    try:
        count = int(count_raw) if count_raw else 1
    except ValueError:
        count = 1
    if count < 1:
        count = 1

    return UpgradeEntry(
        rarity=rarity, name=raw_name, infusion=infusion, count=count
    )


def parse_upgrades(value: str) -> list[UpgradeEntry] | None:
    """Parse an Upgrades cell into entries.

    Returns:
      - None if the cell is empty / N/A (caller skips the block)
      - [] only unused; non-empty list on success
      - If nothing tokenizes usefully, returns a single Other entry with the
        raw cell text so plain notes still show (caller may also plain-fallback)
    """
    if not is_present(value):
        return None

    # Normalize newlines to commas so multi-line cells still split.
    normalized = re.sub(r"\s*\n\s*", ", ", value).strip()
    parts = [p.strip() for p in normalized.split(",") if p.strip()]
    if not parts:
        return None

    entries: list[UpgradeEntry] = []
    for part in parts:
        entry = parse_upgrade_token(part)
        if entry is not None:
            entries.append(entry)

    if not entries:
        # Entire cell as one opaque note.
        return [UpgradeEntry(rarity="Other", name=normalized, infusion="", count=1)]
    return entries


def _format_upgrade_item(entry: UpgradeEntry) -> str:
    """HTML for one upgrade chip (name, optional infusion, optional ×N)."""
    bits: list[str] = [html.escape(entry.name)]
    if entry.infusion:
        bits.append(
            f'<span class="upgrade-infusion">'
            f"({html.escape(entry.infusion)})</span>"
        )
    if entry.count > 1:
        bits.append(
            f'<span class="upgrade-count">×{entry.count}</span>'
        )
    return (
        '<span class="upgrade-item">'
        + " ".join(bits)
        + "</span>"
    )


def upgrades_html(value: str) -> str:
    """Rarity table for an Upgrades cell, or plain paragraph fallback."""
    entries = parse_upgrades(value)
    if entries is None:
        return ""

    # Group while preserving first-seen order within each rarity.
    grouped: dict[str, list[UpgradeEntry]] = {r: [] for r in RARITY_ORDER}
    for entry in entries:
        key = entry.rarity if entry.rarity in grouped else "Other"
        grouped[key].append(entry)

    rows_html: list[str] = []
    for rarity in RARITY_ORDER:
        items = grouped[rarity]
        if not items:
            continue
        slug = RARITY_SLUG.get(rarity, "other")
        cells = " ".join(_format_upgrade_item(e) for e in items)
        rows_html.append(
            f'      <tr class="upgrade-row rarity-{slug}">\n'
            f'        <th scope="row" class="upgrade-rarity">{html.escape(rarity)}</th>\n'
            f'        <td class="upgrade-list">{cells}</td>\n'
            f"      </tr>\n"
        )

    if not rows_html:
        return write_field_html("Upgrades", value)

    parts: list[str] = []
    parts.append('    <div class="build-upgrades">\n')
    parts.append('      <p class="build-upgrades-label"><strong>Upgrades</strong></p>\n')
    parts.append(
        '      <table class="upgrade-table" '
        'aria-label="Upgrades by rarity">\n'
    )
    parts.append("        <tbody>\n")
    parts.extend(rows_html)
    parts.append("        </tbody>\n")
    parts.append("      </table>\n")
    parts.append("    </div>\n")
    return "".join(parts)


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
        parts.append(write_gear_field_html("Primary", cell(row, "Primary")))
        parts.append(
            write_gear_field_html("Secondary", cell(row, "Secondary"))
        )
        parts.append(write_gear_field_html("Grenade", cell(row, "Grenade")))
        parts.append(
            write_gear_field_html("Employee", cell(row, "Employee"))
        )
        parts.append(
            write_field_html(
                "Elemental Cocktail", cell(row, "Elemental Cocktail")
            )
        )
        parts.append(upgrades_html(cell(row, "Upgrades")))
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
        label = f"{weapon} {build}".strip()
        alt_row = html.escape(f"{label} row" if build else label)

        # Column companions are used on mid/early (slim) pages; late game has none.
        col_name = None
        if page.mode == "slim" and build:
            col_name = find_column_image(page.image_dir, img_name)

        if col_name:
            col_src = html.escape(remote_image_src(page, col_name), quote=True)
            alt_col = html.escape(f"{label} column")
            parts.append('  <div class="build-image build-image-swap">\n')
            parts.append(
                '    <div class="build-image-toggle" role="group" '
                'aria-label="Screenshot layout">\n'
            )
            parts.append(
                '      <button type="button" class="is-active" '
                'data-show="row" aria-pressed="true">Row</button>\n'
            )
            parts.append(
                '      <button type="button" data-show="column" '
                'aria-pressed="false">Column</button>\n'
            )
            parts.append("    </div>\n")
            parts.append(
                f'    <img data-view="row" src="{src}" alt="{alt_row}" '
                f'loading="lazy">\n'
            )
            parts.append(
                f'    <img data-view="column" src="{col_src}" alt="{alt_col}" '
                f'loading="lazy" hidden>\n'
            )
            parts.append("  </div>\n")
        else:
            parts.append('  <div class="build-image">\n')
            parts.append(
                f'    <img src="{src}" alt="{alt_row}" loading="lazy">\n'
            )
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
    if page.mode == "slim":
        body += IMAGE_SWAP_SCRIPT
    body += IMAGE_LIGHTBOX_SCRIPT
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
