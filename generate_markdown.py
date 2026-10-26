import csv
from pathlib import Path

csv_path = Path("patterned_builds.csv")
images_dir = Path("patterned_build_images")
output_path = Path("patterned_builds.md")

def make_image_name(weapon, build):
    name = f"{weapon}_{build}".lower().replace(" ", "_").replace("'", "")
    return f"{name}.PNG"   # uppercase extension to match your files

with csv_path.open(newline="", encoding="utf-8") as f, output_path.open("w", encoding="utf-8") as out:
    reader = csv.DictReader(f)
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
            
        out.write(f"### {weapon} – {build}\n")
        out.write(f"**Kill Time:** {row['Kill Time']}\n\n")
        
        if row.get("Secondary"):
            out.write(f"**Secondary:** {row['Secondary']}\n")
        if row.get("Grenade"):
            out.write(f"**Grenade:** {row['Grenade']}\n")
        if row.get("Elemental Cocktail"):
            out.write(f"**Elemental Cocktail:** {row['Elemental Cocktail']}\n")
        out.write("\n")
        
        img = make_image_name(weapon, build)
        if (images_dir / img).exists():
            out.write(f"![{weapon} {build}](patterned_build_images/{img})\n\n")
        
        upgrades = row["Upgrades"].replace("\n", " ").strip()
        out.write(f"**Upgrades:** {upgrades}\n\n")
        
        comments = row["Comments"].strip()
        if comments:
            out.write(f"**Comments:**  \n{comments}\n\n")
        
        out.write("---\n\n")

print(f"Wrote {output_path}")
