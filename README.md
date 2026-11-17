# Sparroh's Mycopunk Builds

Welcome to my webpage repo for Mycopunk builds and guides.

All data is from personal testing, so it carries some bias.

## Images

Screenshots and media live in a **separate** repo so this site stays small on deploy:

**[Mycopunk-Abomination-Image-Repo](https://github.com/Little-Sparroh/Mycopunk-Abomination-Image-Repo)**

The site loads them via raw GitHub URLs, for example:

`https://raw.githubusercontent.com/Little-Sparroh/Mycopunk-Abomination-Image-Repo/main/no_restriction_images/jackrabbit_double_barrel.PNG`

### Adding or updating images

1. Commit the file under the matching folder in the image repo  
   (`no_restriction_images/`, `carver_guide_images/`, `tierlist_images/`, …).
2. Keep the same filename the generators / guide markdown already expect.
3. Rebuild this site if needed (`python generate_all.py`). Guide markdown can point straight at the raw URL.

Generators invent the usual filenames (`weapon_build.PNG`, `weapon_render.png`) when no local image folder is present. An optional local `assets/images/` or `depreciated-assets/images/` cache is only used to match real on-disk casing — it is **not** served by GitHub Pages.

Mid and early game builds can also ship a **Column** companion next to the main **Row** shot: `weapon_build_column.PNG`. Build pages show a Row / Column toggle when that file is present.

### Test build images (gear lightbox)

Companion gear shots live in `test_build_images/` (e.g. `swarm_launcher_munition_siphon.PNG`, `incendiary_grenade_internal_combustion.PNG`). On Late/Mid/Early build cards, **Primary**, **Secondary**, **Grenade**, and **Employee** values that match a file (gear name only — optional `_build` suffix ignored) become clickable and open the same screenshot lightbox. No separate page or nav entry.


## Upgrades column (build CSVs)

The `Upgrades` cell is a comma-separated list. Each entry:

```text
O Boundary Incursion (Cyclotron) x2
```

| Part | Required? | Meaning |
|------|-----------|---------|
| `O` / `X` / `E` / `R` / `S` | no | Oddity, Exotic, Epic, Rare, Standard |
| name | yes | Upgrade display name |
| `(Infusion)` | no | Pattern infusion in parentheses |
| `x2` or `×2` | no | Stack count (default 1; ×1 is hidden) |

Examples of valid partial entries:

- `O Boundary Incursion (Cyclotron) x2`
- `O Boundary Incursion`
- `Boundary Incursion x2` → listed under **Other**
- `Boundary Incursion`

Empty cells omit the upgrades block. Build pages render a small rarity table (Oddity → … → Standard, then Other).

### Videos


Prefer YouTube for long clips. In guide markdown:

```md
![Parkour course video](https://youtu.be/VIDEO_ID)
*Optional caption.*
```

The generator turns that into a responsive embed. Short `.mp4` files can still live in the image repo if you want self-hosted video.

## Generate pages

```bash
python generate_all.py
```

Individual sections:

```bash
python -m sitegen.generate_builds
python -m sitegen.generate_guides
python -m sitegen.generate_tierlists
```

`index.html` is maintained by hand and is not generated.
