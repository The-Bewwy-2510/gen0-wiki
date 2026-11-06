"""Copy the extracted game data and media from the other Gen0 repos into this one.

Run once after re-extracting data in gen0-tools / gen0-mapping (or after a game update):

    python build/import_sources.py --tools ../gen0-tools --mapping ../gen0-mapping --stats "path/to/Machine & Weapon Stats.json" --loadouts "path/to/Machine Loadouts.json"

JSON goes to build/data/ (the build reads it from there); icons, map tiles and the interactive map go to docs/.
"""
import argparse, os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(HERE, "data")
DOCS = os.path.join(ROOT, "docs")

EDITOR_JSON = ["gamedata.json", "augments.json", "schematics.json", "stock.json", "missions.json", "keys.json",
               "icons.json", "vanity.json", "location_crates.json"]
EDITOR_MEDIA = ["augments", "crowns", "currencies", "items", "keys", "locations", "schematics", "skills", "skins",
                "stock", "vanity"]


def copy(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)


def copytree(src, dst):
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tools", required=True, help="gen0-tools checkout")
    ap.add_argument("--mapping", required=True, help="gen0-mapping checkout")
    ap.add_argument("--stats", required=True, help="Machine & Weapon Stats.json (from the extractor)")
    ap.add_argument("--loadouts", required=True, help="Machine Loadouts.json (from the extractor)")
    ap.add_argument("--kinds", help="gen0-dlc data/kinds.json (optional)")
    a = ap.parse_args()
    ed = os.path.join(a.tools, "editor", "web")
    for f in EDITOR_JSON:
        copy(os.path.join(ed, "assets", f), os.path.join(DATA, f))
    copy(os.path.join(ed, "misc", "IDs.json"), os.path.join(DATA, "IDs.json"))
    copy(os.path.join(a.mapping, "map", "markers.json"), os.path.join(DATA, "markers.json"))
    copy(os.path.join(a.mapping, "map", "locations.json"), os.path.join(DATA, "map_locations.json"))
    copy(os.path.join(a.mapping, "map", "loot.json"), os.path.join(DATA, "loot.json"))
    copy(a.stats, os.path.join(DATA, "stats.json"))
    copy(a.loadouts, os.path.join(DATA, "loadouts.json"))
    if a.kinds:
        copy(a.kinds, os.path.join(DATA, "kinds.json"))
    for d in EDITOR_MEDIA:
        copytree(os.path.join(ed, "assets", d), os.path.join(DOCS, "img", d))
    # the interactive map (gen0-mapping is a static site; it runs unchanged under docs/map/)
    mp = os.path.join(DOCS, "map")
    if os.path.isdir(mp):
        shutil.rmtree(mp)
    os.makedirs(mp)
    for f in ["index.html", "map.css", "map.js"]:
        copy(os.path.join(a.mapping, f), os.path.join(mp, f))
    copytree(os.path.join(a.mapping, "assets"), os.path.join(mp, "assets"))
    copytree(os.path.join(a.mapping, "map"), os.path.join(mp, "map"))
    # inside the wiki, the map's WIKI button goes back to the wiki in the same tab
    ix = os.path.join(mp, "index.html")
    with open(ix, encoding="utf-8") as f:
        page = f.read()
    page = page.replace('href="https://the-bewwy-2510.github.io/gen0-wiki/" target="_blank" rel="noopener" '
                        'title="Open the Gen0 Wiki in a new tab"', 'href="../index.html" title="Back to the Gen0 Wiki"')
    with open(ix, "w", encoding="utf-8", newline="\n") as f:
        f.write(page)
    print("Imported. Now run: python build/build.py")


if __name__ == "__main__":
    sys.exit(main())
