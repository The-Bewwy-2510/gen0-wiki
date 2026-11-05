"""Home tab: the main page, game basics, DLC & content packs, and about this wiki."""
import collections

from wiki.site import esc, slug, fmt, table, bar, note, cards, kv, tag, REGIONS, NAV

BASE_PACK = 1413277686
PACKS = [  # key, name, content-pack hash, css class, one-line description
    ("base", "Base game", BASE_PACK, "base", "Everything that comes with Generation Zero itself, including all free updates."),
    ("alpine", "Alpine Unrest", 3565103498, "alpine",
     "Expansion that adds the mountain region Himfjäll with its own story missions, side missions and challenges."),
    ("fnix", "FNIX Rising", 363622574, "fnix",
     "Story expansion about FNIX, the rogue machine-building company, with its own missions and gear."),
    ("dlc03", "Unreleased", None, "unreleased",
     "Missions that are in the game files under a third DLC slot but are not part of the released game."),
]


def weapon_packs(site):
    """Paid weapon / equipment packs named in stats.json (pack field without the ' (DLC)' suffix) -> weapon names."""
    packs = collections.OrderedDict()
    for cat, ws in site.data("stats")["player_weapons"].items():
        for name, w in ws.items():
            p = (w.get("pack") or "")
            if p.endswith(" (DLC)"):
                packs.setdefault(p[:-6], []).append((cat, name))
    return packs


def collect(site):
    for key, name, h, cls, desc in PACKS:
        aliases = [key] + ([str(h)] if h else [])
        site.register("dlc", name, f"dlc.html#{slug(name)}", name, desc=desc, aliases=aliases, search=False)
    for name, ws in weapon_packs(site).items():
        site.register("dlc", name, f"dlc.html#{slug(name)}", name, aliases=[name + " (DLC)"],
                      desc="Paid pack: " + ", ".join(n for c, n in ws), keywords="dlc weapon pack")


# ---------------------------------------------------------------------------------------------------------------
def counts(site):
    """Headline numbers for the main page, straight from the data."""
    st = site.data("stats")
    weapons = sum(len(v) for v in st["player_weapons"].values())
    lo = site.data("loadouts")
    types, layouts = set(), 0
    for fac in ("Swedish", "Soviet"):
        for cl in lo[fac].values():
            for t, tv in cl["types"].items():
                types.add((fac, t))
                layouts += len(tv["layouts"])
    gd = site.data("gamedata")
    mk = site.data("markers")
    collectible_subs = [s for s in mk["subs"] if s["main"] == "collectibles"]
    return {
        "weapons": weapons,
        "ammo": sum(1 for s in site.data("stock")["stock"] if s["g"] == "ammo"),
        "augments": len(site.data("augments")["augments"]),
        "machine_layouts": layouts,
        "machine_weapons": len(st["machine_weapons"]),
        "locations": len(site.data("map_locations")["list"]),
        "regions": len(gd["regions"]),
        "safehouses": sum(len(r["list"]) for r in gd["safehouses"]["regions"]),
        "collectibles": sum(s["count"] for s in collectible_subs),
        "collectible_types": len(collectible_subs),
        "missions": len(site.data("missions")["missions"]),
        "schematics": len(site.data("schematics")["items"]),
        "skills": len(gd["skills"]["list"]),
        "vanity": len(site.data("vanity")["items"]),
        "items": len(site.data("stock")["stock"]),
        "loot": len(site.data("loot")["items"]),
    }


def build(site):
    c = counts(site)
    build_main(site, c)
    build_basics(site, c)
    build_dlc(site)
    build_about(site, c)


# ---------------------------------------------------------------------------------------------------------------
def build_main(site, c):
    lead = (f"<p>A fan-made reference for <b>Generation Zero</b>, built from the game's own files. Every number on "
            f"these pages – damage per ammo type and weapon quality, the hit points of each machine component, how "
            f"far machines see and hear you, where every collectible lies – was read out of the current game data "
            f"with the <a href=\"~/modding/tools.html\">Gen0 tools</a>, not copied from older guides.</p>")
    sec = [
        {"href": "~/weapons/index.html", "title": "Weapons", "tag": "WPN", "color": "#2f4d5e",
         "img": "~/img/items/weapons/weapon_rifle_assault_556_01_alpha.png",
         "sub": f"{c['weapons']} weapons with damage for every ammo type and quality, {c['ammo']} ammo types, "
                f"attachments, {c['augments']} augments and every skin."},
        {"href": "~/machines/index.html", "title": "Machines", "tag": "MCH", "color": "#7a2a26",
         "sub": f"Every machine class and its {c['machine_layouts']} weapon layouts, component hit points, "
                f"{c['machine_weapons']} machine weapons, detection ranges and difficulty scaling."},
        {"href": "~/world/index.html", "title": "World", "tag": "MAP", "color": "#5f4258",
         "img": "~/img/locations/location_church.png",
         "sub": f"{c['regions']} regions, {c['locations']} locations with mini maps, {c['safehouses']} safehouses, "
                f"{c['collectibles']} collectibles in {c['collectible_types']} sets."},
        {"href": "~/missions/index.html", "title": "Missions", "tag": "MIS", "color": "#1d4039",
         "sub": f"All {c['missions']} main and side missions with briefings and every objective, plus the "
                f"challenge trees and the titles they award."},
        {"href": "~/items/index.html", "title": "Items & crafting", "tag": "ITM", "color": "#4d4a2c",
         "img": "~/img/stock/equipment_consumable_firstaid_advanced_01_alpha.png",
         "sub": f"{c['items']} inventory items, materials, all {c['schematics']} schematics with costs and recipes, "
                f"and the companion."},
        {"href": "~/character/skills.html", "title": "Character", "tag": "CHR", "color": "#47545a",
         "sub": f"All {c['skills']} skills, and {fmt(c['vanity'])} apparel items, emotes, vehicles and other "
                f"cosmetics."},
        {"href": "~/map/index.html", "title": "Interactive map", "tag": "MAP", "color": "#5f4258",
         "sub": f"Filter collectibles, schematics, safehouses, control points and {fmt(c['loot'])} pieces of "
                f"placed loot on the full world map."},
        {"href": "~/modding/index.html", "title": "Modding", "tag": "MOD", "color": "#33393f",
         "sub": "The save editor, mod maker, extractor, console / VR mod and map editor, and the game's item IDs."},
    ]
    body = [bar("Browse the wiki"), cards(sec)]
    body.append(bar("What you'll find here that older wikis don't have"))
    body.append("""<ul>
<li><b>Exact damage tables</b> for every weapon: each ammo type's damage, armour and component multipliers, damage
falloff and range, multiplied out for every quality from Dilapidated to Experimental.</li>
<li><b>Machine anatomy</b>: the hit points of every component and armour plate on every machine class and weapon
layout, and the weapons each layout carries.</li>
<li><b>Stealth numbers</b>: how far each machine can see and hear you crouched, prone, standing or running, by day
and by night, and how fast it notices you.</li>
<li><b>Difficulty and co-op scaling</b> as the game applies it, per difficulty and number of players.</li>
<li><b>Which augment fits which weapon</b> at which quality, and how to research each one.</li>
<li><b>Every location</b> with its own page and mini map, the collectibles, house photos and loot around it.</li>
<li><b>Internal names and item IDs</b> for modders and save editing.</li>
</ul>""")
    body.append(note("Generation Zero has had many updates since release. Where the current game files disagree "
                     "with numbers that are still repeated in older guides, the page says so in a green "
                     "<b>Corrected</b> box.", "fix", "Up to date"))
    body.append(bar("Start here"))
    links = [
        ("New to the game?", "~/basics.html", "Game basics: the setting, regions, machines, gear and progression."),
        ("Choosing ammo", "~/weapons/ammo.html", "Armour-piercing, hollow-point, HEAT and the rest compared."),
        ("Fighting machines", "~/machines/index.html", "Classes, layouts and where to shoot them."),
        ("Staying hidden", "~/machines/detection.html", "Sight and hearing ranges per stance."),
        ("Missions", "~/missions/index.html", "The story in order, with every objective."),
        ("DLC", "~/dlc.html", "What Alpine Unrest and FNIX Rising add."),
    ]
    body.append('<div class="cols">' + "".join(
        f'<div class="panel"><h3 style="margin-top:0"><a href="{u}">{esc(t)}</a></h3><p class="small">{esc(d)}</p></div>'
        for t, u, d in links) + "</div>")
    body.append(bar("Regions"))
    body.append('<div class="cols">' + "".join(
        f'<div class="panel"><h3 style="margin-top:0">{site.link("region", k, n)}</h3></div>' for k, n in REGIONS)
                + "</div>")
    site.page("index.html", "Generation Zero Wiki", "\n".join(body), "home", lead=lead, toc=False,
              desc="Generation Zero wiki built from the game files: weapons, machines, locations, missions, "
                   "collectibles, schematics and modding.", search=False)


# ---------------------------------------------------------------------------------------------------------------
def build_basics(site, c):
    gd = site.data("gamedata")
    lead = ("<p>Generation Zero is an open-world shooter for one to four players, made by Systemic Reaction "
            "(Avalanche Studios Group). It is set in an alternative-history Sweden in the late 1980s: you return "
            "from a weekend away to find the country deserted and patrolled by hostile machines. This page is a "
            "quick tour of how the game works, with links to the detailed pages.</p>")
    b = []
    b.append(bar("The world"))
    b.append(f"<p>The map is one continuous world split into {len(gd['regions'])} regions. You start on the "
             f"islands of the {site.link('region', 'archipelago', 'Archipelago')} and work your way north. "
             f"<b>Himfjäll</b>, the snowy mountain region, comes with the "
             f"{site.link('dlc', 'Alpine Unrest')} expansion.</p>")
    rows = []
    for k, n in REGIONS:
        rows.append([site.link("region", k, n)])
    b.append(table(["Region"], rows, sortable=False))
    b.append(f"<p>The world is dotted with {c['locations']} named <a href=\"~/world/locations.html\">locations</a> "
             f"(farms, churches, bunkers, military bases and more). "
             f"<a href=\"~/world/safehouses.html\">Safehouses</a> are where you respawn and fast travel; "
             f"you unlock them by finding them. <a href=\"~/world/control-points.html\">Control points</a> are "
             f"resistance bases that machines attack, and that you can capture and fortify.</p>")
    b.append(bar("The machines"))
    b.append("<p>The machines are the enemies. The Swedish-built types (Ticks, Seekers, Runners, Hunters, "
             "Harvesters and Tanks) come in classes that get tougher and better armed: <b>Prototype</b>, "
             "<b>Military</b>, <b>FNIX</b> and <b>Apocalypse</b>. Soviet machines (Firebirds, Lynxes and Wolves) "
             "use the classes Scout, Soldier and Spetsnaz. <b>Rivals</b> are named machines that level up each "
             "time they beat you, and the Reaper and Vulture are special rival machines.</p>")
    b.append("<p>Machines are not one health bar: each one is made of components (weapons, joints, fuel tanks, "
             "sensors) and armour plates, each with its own hit points. Shooting off a weapon disarms it; hitting "
             "a fuel tank can set it on fire. The <a href=\"~/machines/index.html\">machine pages</a> list every "
             "component of every layout.</p>")
    b.append(bar("Weapons, ammo and quality"))
    b.append("<p>Each weapon comes in up to five qualities you can find (Dilapidated, Worn, Good, Exceptional, "
             "Special); a higher quality does more damage and is more accurate. <b>Experimental</b> weapons are a "
             "sixth tier with unique ammo. Ammo types matter as much as the gun: armour-piercing rounds hit "
             "armour harder, hollow-points tear up components, and special rounds burn, shock or explode. See "
             "<a href=\"~/weapons/quality.html\">quality</a> and <a href=\"~/weapons/ammo.html\">ammo</a>.</p>")
    b.append("<p><a href=\"~/weapons/attachments.html\">Attachments</a> (scopes, silencers, compensators, "
             "extended magazines) and <a href=\"~/weapons/augments.html\">augments</a> (perks you unlock by "
             "research) change how a weapon handles.</p>")
    b.append(bar("Progression"))
    trees = [t["name"].title() for t in gd["skills"]["trees"]]
    b.append(f"<p>You earn experience by fighting and exploring. Each level gives a skill point to spend in "
             f"the {len(trees)} <a href=\"~/character/skills.html\">skill trees</a> ({', '.join(trees)}). "
             f"<a href=\"~/items/schematics.html\">Schematics</a> let you craft ammo, equipment and apparel "
             f"from <a href=\"~/items/materials.html\">materials</a>; each schematic tree has its own points that "
             f"you earn by doing related things.</p>")
    cur = [[site.img(s["icon"].replace("assets/", "img/"), "", "li") + esc(s["name"]), esc(s["earn"])]
           for s in gd["schematics"]]
    b.append(table(["Schematic points", "How you earn them"], cur, sortable=False))
    b.append(bar("Difficulty and co-op"))
    b.append("<p>Difficulty and the number of players in the game scale how much damage you do to machines and "
             "how much they do to you. The full table, with worked examples, is on "
             "<a href=\"~/machines/difficulty.html\">Difficulty &amp; co-op</a>.</p>")
    rows = []
    for diff, lst in site.data("stats")["difficulty"].items():
        for r in lst:
            rows.append([esc(diff), r["players"], f'{fmt(r["player_damage_to_machines"])}×',
                         f'{fmt(r["machine_damage_to_players"])}×'])
    b.append(table(["Difficulty", "Players", "Your damage to machines", "Machine damage to you"], rows,
                   num={1, 2, 3}))
    site.page("basics.html", "Game basics", "\n".join(b), "home", lead=lead,
              desc="How Generation Zero works: the world, machines, weapons, progression and difficulty.")


# ---------------------------------------------------------------------------------------------------------------
def pack_contents(site):
    """Per content pack: missions, challenge trees, keys/items and cosmetics found in the data."""
    out = collections.defaultdict(lambda: collections.defaultdict(list))
    for m in site.data("missions")["missions"]:
        out[m["pack"]]["missions"].append(m)
    hash_to_key = {h: k for k, n, h, cls, d in PACKS if h}
    for it in site.data("vanity")["items"]:
        k = hash_to_key.get(it.get("p"))
        if k:
            out[k]["vanity"].append(it)
    for it in site.data("keys")["items"]:
        k = hash_to_key.get(it.get("p"))
        if k:
            out[k]["keys"].append(it)
    return out


def build_dlc(site):
    content = pack_contents(site)
    gd = site.data("gamedata")
    lead = ("<p>Generation Zero has paid expansions on top of the base game, plus many cosmetic packs. The game "
            "files group all content into <b>content packs</b>; this page lists what each expansion adds, "
            "counted from the game data. Content from an expansion is tagged on every page of this wiki, like "
            f"{tag('Alpine Unrest', 'alpine')} or {tag('FNIX Rising', 'fnix')}.</p>")
    b = []
    rows = []
    for key, name, h, cls, desc in PACKS:
        ms = content[key]["missions"]
        rows.append([f'<a href="#{slug(name)}">{tag(name, cls)}</a>', sum(1 for m in ms if m["type"] == "main"),
                     sum(1 for m in ms if m["type"] == "side"), len(content[key]["keys"]),
                     len(content[key]["vanity"])])
    b.append(bar("Overview"))
    b.append(table(["Content", "Main missions", "Side missions", "Keys & quest items", "Cosmetics"], rows,
                   num={1, 2, 3, 4}, sortable=False))
    dlc_trees = [ch for ch in gd["challenges"] if ch["dlc"]]
    for key, name, h, cls, desc in PACKS:
        b.append(bar(name, f"content pack {h}" if h else "", id=slug(name)))
        b.append(f"<p>{esc(desc)}</p>")
        if key == "alpine":
            b.append(f"<p>Region: {site.link('region', 'alpine', 'Himfjäll')}.</p>")
        if key == "dlc03":
            b.append(note("These missions exist in the mission files but are not offered in the released game. "
                          "They are listed for completeness and may never be released in this form.", "warn"))
        if key == "base":
            b.append("<p>Free updates since launch added, among other things, the FNIX and Apocalypse machine "
                     "classes, Rivals, the Soviet machines, the companion, research and augments; they are part "
                     "of the base game, so they're tagged as base game here.</p>")
        ms = content[key]["missions"]
        if ms:
            for typ in ("main", "side"):
                lst = [m for m in ms if m["type"] == typ]
                if lst:
                    b.append(f"<h3>{'Main' if typ == 'main' else 'Side'} missions ({len(lst)})</h3>")
                    b.append("<p>" + ", ".join(site.link("mission", m["name"]) for m in lst) + "</p>")
        if key in ("alpine", "fnix"):
            ks = content[key]["keys"]
            if ks:
                b.append(f"<h3>Keys and quest items ({len(ks)})</h3>")
                b.append("<p>" + ", ".join(site.link("key", k["n"]) for k in ks) + "</p>")
            vs = content[key]["vanity"]
            if vs:
                groups = collections.Counter(v["g"] for v in vs)
                b.append(f"<h3>Cosmetics ({len(vs)})</h3><p>" + ", ".join(
                    f"{n} {esc(g)}" for g, n in groups.most_common()) +
                         f'. See <a href="~/character/packs.html#pack-{h}">the pack contents</a>.</p>')
    b.append(bar("Weapon and equipment packs"))
    b.append("<p>These paid packs each add a few weapons (and their ammo, attachments and skins) to the loot pool "
             "of the base game; they come with no missions. The weapons, by pack, as the game's item table "
             "groups them:</p>")
    for name, ws in weapon_packs(site).items():
        b.append(f'<h3 id="{slug(name)}">{esc(name)}</h3>')
        b.append("<ul>" + "".join(f"<li>{site.link('weapon', n, icon=True)} <span class=\"dim\">{esc(c)}</span></li>"
                                  for c, n in ws) + "</ul>")
    b.append(bar("DLC challenge trees"))
    b.append("<p>Two of the challenge trees are marked as DLC content in the game data: " + ", ".join(
        f"<b>{esc(t['name'].title())}</b> ({len(t['challenges'])} challenges)" for t in dlc_trees) +
             ". See <a href=\"~/missions/challenges.html\">Challenges</a>.</p>")
    b.append(bar("Cosmetic packs"))
    b.append("<p>Besides the expansions there are many cosmetic packs (apparel sets, weapon skins, bike paint jobs, "
             "emotes, companion kits). Their contents are listed on <a href=\"~/character/packs.html\">Item "
             "packs</a>.</p>")
    site.page("dlc.html", "DLC & content packs", "\n".join(b), "home", lead=lead,
              desc="What the Generation Zero expansions Alpine Unrest and FNIX Rising add, counted from the game data.")


# ---------------------------------------------------------------------------------------------------------------
def build_about(site, c):
    lead = ("<p>This wiki is generated from data extracted from Generation Zero's own files, and styled after the "
            "Gen0 tools (the save editor, mod maker, extractor and map). It is a fan project and is not "
            "affiliated with Systemic Reaction or Avalanche Studios Group.</p>")
    b = []
    b.append(bar("Where the numbers come from"))
    st = site.data("stats")["_about"]
    b.append(f"<p>{esc(st['source'])}</p>")
    b.append("<p>Item names, mission texts, skills, schematics, apparel and locations come from the game's item "
             "tables, text tables, mission files and map location files, read by the "
             "<a href=\"~/modding/tools.html\">Gen0 Editor and Extractor</a>. Map positions are the game's own "
             "world coordinates (metres).</p>")
    files = [
        ("stats.json", "Machine & weapon stats: damage, component health, detection, difficulty"),
        ("loadouts.json", "Machine layouts and the weapons on each"),
        ("gamedata.json", "Skills, research, regions, rivals, challenges, safehouses, locations"),
        ("augments.json", "Which augment fits which weapon"),
        ("schematics.json", "Schematic trees, costs and recipes"),
        ("stock.json", "Inventory items, ammo and materials"),
        ("missions.json", "Missions, briefings and objectives"),
        ("keys.json", "Keys, barcodes and quest items"),
        ("vanity.json", "Apparel, skins, emotes, vehicles and companion cosmetics"),
        ("IDs.json", "Item IDs per quality (save editing)"),
        ("markers.json", "Collectibles, safehouses, control points and beacons on the map"),
        ("map_locations.json", "Every map location with its position"),
        ("loot.json", "Placed loot in the world"),
    ]
    b.append(table(["File (build/data)", "Contents"], [[f"<code>{f}</code>", esc(d)] for f, d in files],
                   sortable=False))
    b.append(note("Some effects aren't in the files the extractor reads – for example the special effect of "
                  "some experimental ammo lives in a separate effect file. Pages say so where it matters.", "data"))
    b.append(bar("Corrections"))
    b.append("<p>When a value here disagrees with an older guide, the game files win: they are what the game "
             "actually uses. Green <b>Corrected</b> boxes point out the most common outdated numbers. If you find "
             "a mistake on this wiki, open an issue or pull request on "
             "<a href=\"https://github.com/The-Bewwy-2510/gen0-wiki\">GitHub</a>.</p>")
    b.append(bar("Updating the wiki"))
    b.append("""<p>The site is plain HTML generated by a Python script (no dependencies):</p>
<ol>
<li>Re-extract the data with the Gen0 tools after a game update.</li>
<li><code>python build/import_sources.py --tools ../gen0-tools --mapping ../gen0-mapping --stats "Machine &amp; Weapon Stats.json" --loadouts "Machine Loadouts.json"</code></li>
<li><code>python build/build.py</code> — writes the site into <code>docs/</code> and checks every link.</li>
<li>Commit and push; GitHub Pages publishes <code>docs/</code>.</li>
</ol>""")
    b.append(bar("Credits"))
    b.append("<p>Fonts: Open Sans (SIL Open Font License, see <code>assets/OFL.txt</code>). Icons, item art and "
             "map images are from Generation Zero and belong to their owners; they are shown here for reference. "
             "Generation Zero is a trademark of Systemic Reaction / Avalanche Studios Group.</p>")
    site.page("about.html", "About this wiki", "\n".join(b), "home", lead=lead,
              desc="Where the Gen0 Wiki's data comes from, how it is built and how to correct it.")
