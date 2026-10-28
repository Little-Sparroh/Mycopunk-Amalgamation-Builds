"""Generate builds/*.md pages from builds/*.csv for the Mycopunk Amalgamation Builds site."""

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


@dataclass(frozen=True)
class PageConfig:
    csv_path: Path
    md_path: Path
    title: str
    image_dir: Path
    mode: str  # "full" | "slim" | "times"
    description: str = ""


PAGES = [
    PageConfig(
        csv_path=ROOT / "builds" / "no_restriction_builds.csv",
        md_path=ROOT / "builds" / "no_restriction_builds.md",
        title="No Restriction Builds (Threat 6 Amalgamation)",
        image_dir=ROOT / "assets" / "images" / "no_restriction_images",
        mode="full",
        description=(
            "Full loadouts with no self-imposed restrictions. "
            "Tiers are assigned automatically from kill time (bell-curve split)."
        ),
    ),
    PageConfig(
        csv_path=ROOT / "builds" / "no_infusion_builds.csv",
        md_path=ROOT / "builds" / "no_infusion_builds.md",
        title="No Infusion Builds (Threat 6 Amalgamation)",
        image_dir=ROOT / "assets" / "images" / "no_infusion_images",
        mode="slim",
        description=(
            "Builds without infusion. "
            "Tiers are assigned automatically from kill time (bell-curve split)."
        ),
    ),
    PageConfig(
        csv_path=ROOT / "builds" / "no_rotation_builds.csv",
        md_path=ROOT / "builds" / "no_rotation_builds.md",
        title="No Rotation Builds (Threat 6 Amalgamation)",
        image_dir=ROOT / "assets" / "images" / "no_rotation_images",
        mode="slim",
        description=(
            "Builds without rotation. "
            "Tiers are assigned automatically from kill time (bell-curve split)."
        ),
    ),
    PageConfig(
        csv_path=ROOT / "builds" / "no_upgrade_times.csv",
        md_path=ROOT / "builds" / "no_upgrade_times.md",
        title="No Upgrade Times (Threat 6 Amalgamation)",
        image_dir=ROOT / "assets" / "images" / "no_upgrade_images",
        mode="times",
        description=(
            "Baseline weapon kill times with no upgrades. "
            "Tiers are assigned automatically from kill time (bell-curve split)."
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
    # Also try without trailing words already normalized
    stem = normalize_key(raw)
    if stem in WEAPON_ALIASES:
        return WEAPON_ALIASES[stem]
    return stem


def find_image(image_dir: Path, *name_parts: str) -> str | None:
    """Return image filename inside image_dir, or None."""
    if not image_dir.is_dir():
        return None

    base = normalize_key(*name_parts)
    candidates = [base]

    # swarm launcher mitosis sometimes stored as swarmlauncher_mitosis
    if base.startswith("swarm_launcher_"):
        candidates.append("swarmlauncher_" + base[len("swarm_launcher_") :])
    if base.startswith("swarm_"):
        candidates.append("swarmlauncher_" + base[len("swarm_") :])

    # times-page style: weapon_render
    if len(name_parts) == 1:
        stem = weapon_image_stem(name_parts[0])
        candidates.append(f"{stem}_render")
        candidates.append(stem)

    # de-dupe preserving order
    seen: set[str] = set()
    ordered: list[str] = []
    for c in candidates:
        if c and c not in seen:
            seen.add(c)
            ordered.append(c)

    for stem in ordered:
        for ext in IMAGE_EXTENSIONS:
            path = image_dir / f"{stem}{ext}"
            if path.exists():
                return path.name

    # Case-insensitive directory scan fallback
    lower_map = {p.name.lower(): p.name for p in image_dir.iterdir() if p.is_file()}
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
    # Use midpoint of the rank slot so edges don't all collapse into S/F oddly
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
    # md lives in builds/; images in assets/images/<folder>/
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
            # Normalize keys (strip BOM/spaces)
            cleaned = {
                (k.strip() if isinstance(k, str) else k): (v.strip() if isinstance(v, str) else v)
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


def write_header(out, page: PageConfig) -> None:
    out.write('<link rel="stylesheet" href="../css/style.css">\n\n')
    out.write(f"# {page.title}\n\n")
    if page.description:
        out.write(f"{page.description}\n\n")
    out.write(f"[Source CSV]({github_csv_url(page)})\n\n")


def write_empty_page(page: PageConfig) -> None:
    with page.md_path.open("w", encoding="utf-8") as out:
        write_header(out, page)
        out.write("_No builds recorded yet._\n")


def write_field(out, label: str, value: str) -> None:
    if not is_present(value):
        return
    # Collapse newlines inside CSV cells
    value = re.sub(r"\s*\n\s*", ", ", value).strip()
    out.write(
        f"    <p><strong>{html.escape(label)}:</strong> {html.escape(value)}</p>\n"
    )


def write_build_card(out, page: PageConfig, row: dict, include_details: bool) -> None:
    weapon = row["_weapon"]
    build = row["_build"]
    title = f"{weapon} – {build}" if build else weapon
    time_raw = row["_time_raw"] or "—"

    out.write('<div class="build">\n')
    out.write('  <div class="build-text">\n')
    out.write(f"    <h3>{html.escape(title)}</h3>\n")
    out.write(
        f"    <p><strong>Kill Time:</strong> {html.escape(time_raw)}</p>\n"
    )

    if include_details:
        write_field(out, "Primary", cell(row, "Primary"))
        write_field(out, "Secondary", cell(row, "Secondary"))
        write_field(out, "Grenade", cell(row, "Grenade"))
        write_field(out, "Elemental Cocktail", cell(row, "Elemental Cocktail"))
        write_field(out, "Upgrades", cell(row, "Upgrades"))
        write_field(out, "Comments", cell(row, "Comments"))

    out.write("  </div>\n")

    img_name = None
    if build:
        img_name = find_image(page.image_dir, weapon, build)
    if not img_name:
        img_name = find_image(page.image_dir, weapon)

    if img_name:
        src = rel_image_src(page, img_name)
        alt = html.escape(f"{weapon} {build}".strip())
        out.write('  <div class="build-image">\n')
        out.write(f'    <img src="{src}" alt="{alt}">\n')
        out.write("  </div>\n")

    out.write("</div>\n\n")


def write_times_row(out, page: PageConfig, row: dict) -> None:
    weapon = row["_weapon"]
    time_raw = row["_time_raw"] or "—"
    img_name = find_image(page.image_dir, weapon)

    out.write('<div class="build">\n')
    out.write('  <div class="build-text">\n')
    out.write(f"    <h3>{html.escape(weapon)}</h3>\n")
    out.write(
        f"    <p><strong>Kill Time:</strong> {html.escape(time_raw)}</p>\n"
    )
    out.write("  </div>\n")

    if img_name:
        src = rel_image_src(page, img_name)
        out.write('  <div class="build-image">\n')
        out.write(
            f'    <img src="{src}" alt="{html.escape(weapon)}">\n'
        )
        out.write("  </div>\n")

    out.write("</div>\n\n")


def generate_page(page: PageConfig) -> None:
    page.md_path.parent.mkdir(parents=True, exist_ok=True)
    rows = load_rows(page)

    if page.mode == "times":
        prepared = prepare_build_rows(rows, time_key="Kill Times")
    else:
        prepared = prepare_build_rows(rows, time_key="Kill Time")

    if not prepared:
        write_empty_page(page)
        print(f"Wrote {page.md_path.relative_to(ROOT)} (empty)")
        return

    with page.md_path.open("w", encoding="utf-8") as out:
        write_header(out, page)

        current_tier = None
        for row in prepared:
            tier = row["_tier"]
            if tier != current_tier:
                out.write(f"## {tier} Tier\n\n")
                current_tier = tier

            if page.mode == "times":
                write_times_row(out, page, row)
            elif page.mode == "full":
                write_build_card(out, page, row, include_details=True)
            else:
                write_build_card(out, page, row, include_details=False)

    print(f"Wrote {page.md_path.relative_to(ROOT)} ({len(prepared)} rows)")


def main() -> None:
    for page in PAGES:
        generate_page(page)


if __name__ == "__main__":
    main()
