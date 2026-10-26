import csv
from pathlib import Path

csv_path = Path("patterned_builds.csv")
images_dir = Path("patterned_build_images")
output_path = Path("patterned_builds.md")

def find_image(weapon, build):
    base = f"{weapon}_{build}".lower().replace(" ", "_").replace("'", "")
    for ext in (".PNG", ".png", ".jpg", ".jpeg"):
        candidate = images_dir / f"{base}{ext}"
        if candidate.exists():
            return candidate.name
    return None

with csv_path.open(newline="", encoding="utf-8") as f, output_path.open("w", encoding="utf-8") as out:
    reader = csv.DictReader(f)
    
    # Force the stylesheet to load
    out.write('<link rel="stylesheet" href="/Mycopunk-Amalgamation-Builds/style.css">\n\n')
    out.write("# Patterned Builds (Threat 6 Amalgamation)\n\n")
    
    current_tier = None
    for row in reader:
        tier = row["Tier"].strip()
        if tier and tier != current_tier:
            out.write(f"## {tier} Tier\n\n")
            current_tier = tier
        
        weapon = row["Weapon"].strip()
        build = row["Build"].strip()
        if not weapon:
            continue
        
        img_name = find_image(weapon, build)
        
        out.write('<div class="build">\n')
        out.write('  <div class="build-text">\n')
        out.write(f"    <h3>{weapon} – {build}</h3>\n")
        out.write(f"    <p><strong>Kill Time:</strong> {row['Kill Time']}</p>\n")
        
        if row.get("Secondary"):
            out.write(f"    <p><strong>Secondary:</strong> {row['Secondary']}</p>\n")
        if row.get("Grenade"):
            out.write(f"    <p><strong>Grenade:</strong> {row['Grenade']}</p>\n")
        if row.get("Elemental Cocktail"):
            out.write(f"    <p><strong>Elemental Cocktail:</strong> {row['Elemental Cocktail']}</p>\n")
        
        upgrades = row["Upgrades"].replace("\n", ", ").strip()
        out.write(f"    <p><strong>Upgrades:</strong> {upgrades}</p>\n")
        
        comments = row["Comments"].strip()
        if comments:
            out.write(f"    <p><strong>Comments:</strong> {comments}</p>\n")
        
        out.write("  </div>\n")
        
        if img_name:
            out.write('  <div class="build-image">\n')
            out.write(f'    <img src="patterned_build_images/{img_name}" alt="{weapon} {build}">\n')
            out.write("  </div>\n")
        
        out.write("</div>\n\n")

print(f"Wrote {output_path}")
