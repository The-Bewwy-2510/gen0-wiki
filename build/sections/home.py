"""Home tab: the main page, game basics, the DLC page and about this wiki.

Pages
    index.html    main page: what the game is (steam.json game entry + counts from the game files), the sections
    basics.html   a quick tour of how the game works
    dlc.html      the 23 Steam DLC (steam.json), grouped by type, each with what it adds according to the game files
                  (vanity.json items by content pack, keys.json pack_items, weapon packs named in stats.json);
                  then the item packs in the game files that are not a Steam DLC (free updates, rewards, events)
    about.html    short, non-technical: where the information comes from, credits, fan-made disclaimer

Kinds registered
    dlc     DLC name as on Steam (alias: the stats.json pack name 'US Weapons Pack (DLC)', the Steam app id), plus
            'Base game' / 'Unreleased' and the mission pack keys (base, alpine, fnix, dlc03)
    pack    content pack hash as a string (alias: pack name) -> its entry on dlc.html (#pack-<hash>)
"""
import collections
import datetime
import re

from wiki.site import (esc, slug, norm, fmt, table, bar, fold, panel, note, cards, tag, infobox, minimap,
                       REGIONS)

CSS = '<link rel="stylesheet" href="~/assets/home.css">'
DLC_PAGE = "dlc.html"

# Steam DLC (app id) -> the content pack in the game files that holds its items, matched by content (the vanity
# sets, emotes, skins, vehicles and companion parts the Steam description lists). DLC not listed here add no
# vanity items (weapon, equipment and base-building packs, the Rivals update).
DLC_PACK = {
    1062400: 175186114,    # Tubular Vanity Pack: Timeless, Swedish Easter, Workout and Rainproof sets, 6 emotes
    1062420: 1275017523,   # Schweet Vanity Pack: Adventurer, Miami, Midsummer and Tourist sets, 5 emotes
    1099600: 157725165,    # Blockbuster Vanity Pack: Interceptor, Ecto-Scientist, Xeno-Specialist, Annihilator
    1103830: 1125639235,   # Bikes: the Cykel and its six colours
    1157550: 3565103498,   # Alpine Unrest (named in missions.json)
    1252740: 3867371168,   # Apparel Crafting: apparel schematics, materials, crafting container key
    1301740: 363622574,    # FNIX Rising (named in missions.json)
    2144761: 2781443650,   # Motorbikes Pack: Dirt Bike, Military Motorcycle, Resistance bike paint jobs
    2144760: 3559300629,   # Camo Weapon Skins Pack
    2473770: 1081059118,   # Companion Accessories Pack: modules, plate armour, paint jobs, light kits, voice boxes
    2591100: 532636854,    # Advanced Intelligence Cosmetics Pack: FNIX-class weapon skins, Apocalypse companion kit
    2689180: 3835143588,   # Reinforced Flakmoped Pack: Stridsflak, Terrängflak, Bruksflak
}

# Inventory items (stock.json names) that a DLC's Steam description lists and that are not weapons in stats.json.
DLC_ITEMS = {
    2009530: ["Remote-Controlled Explosive", "Portable Machine Gun Turret", "Portable Cover",
              "Explosive Toy Lure"],
    2334430: ["Toy Car Lure", "Sensory Jammer", "Hacking Dart", "Remote-Controlled Tick", "Portable Homing Turret"],
}

# The base weapons whose experimental versions came with the Rivals & Experimental Weapons update (Steam text).
EXPERIMENTAL_UPDATE = ["Klaucke 17", "Automatgevär 4", "Pansarvärnsgevär 90", "12G Pump-Action",
                       'M/46 "Kpist" SMG', "Granatgevär m/49"]

GROUPS = [  # id, title, intro, app ids (release order is kept inside a group)
    ("story", "Story expansions",
     "The two paid expansions add a story campaign, new places and their own gear.",
     [1157550, 1301740]),
    ("free", "Free updates",
     "These are listed as DLC on Steam but are free: you add them to your library from the store page.",
     [1062400, 1103830, 1099600, 1173930, 1252740]),
    ("weapons", "Weapon packs",
     "Each pack adds a few weapons, with their ammo and attachments, to the loot of the whole map.",
     [1450340, 1580920, 1610690, 1771050, 2200740, 2955520]),
    ("equipment", "Equipment and base packs",
     "New throwables, gadgets and turrets, or new structures for your bases.",
     [2009530, 2334430, 1610720, 1850670]),
    ("vehicles", "Vehicle packs",
     "Motorbikes and three-wheeled flakmopeds, each in six colours.",
     [2144761, 2689180]),
    ("cosmetics", "Cosmetic packs",
     "Outfits, emotes, weapon skins and companion cosmetics. They change how you look, not how you play.",
     [1062420, 2144760, 2473770, 2591100]),
]

# Item packs in the game files that no Steam DLC lists: (name, what it is). Names describe the contents; the files
# don't name these packs.
OTHER_PACKS = {
    1413277686: ("Base game", "Everything that comes with the game itself."),
    2276382681: ("Machine Companion", "The companion's basic parts, paint jobs, voice boxes and tricks."),
    1694085061: ("Story outfits", "Clothing from the story: the hazard suit, FNIX machine pieces, Child of the "
                                  "Apocalypse and more."),
    741473295: ("Autumn outfits", "Slayer's, Elegant, Antarctic and Worn outfits, face paint and emotes."),
    403227705: ("Soviet outfits", "Soviet Soldier and Soviet Exosuit clothing."),
    4059682403: ("Experimental outfit", "The Experimental helmet, jacket, pants and more."),
    2503864856: ("Rewards", "Reward hats, the varsity jacket, backpacks and two weapon skins."),
    2403426898: ("Street Art", "Street Art weapon skins and two companion voice boxes."),
    3513538084: ("Retro casual", "Band tees, bomber jacket, rolled-up jeans and more."),
    3080402858: ("Sporty", "Puffy sport jacket, tights and cyclist cap."),
    3516781347: ("Cyberpunk", "The Cyberpunk outfit."),
    419370957: ("Varsity jacket", "A single Generation Zero varsity jacket."),
    2713648062: ("Flakmoped", "Flakmoped paint jobs."),
    941601146: ("Tuned Moped", "Tuned Moped paint jobs."),
    485717896: ("Tracking device", "A single mission item."),
}

GROUP_ORDER = ["apparel", "facepaint", "emotes", "skins", "companion", "vehicles"]
MISSION_PAGE = {"alpine": "missions/alpine-unrest.html", "fnix": "missions/fnix-rising.html"}


# ---------------------------------------------------------------------------------------------------------------
# data helpers
# ---------------------------------------------------------------------------------------------------------------
def steam(site):
    return site.data("steam")


def dlc_list(site):
    return steam(site)["dlc"]


def dlc_by_id(site):
    return {d["appid"]: d for d in dlc_list(site)}


def date_of(d):
    try:
        return datetime.datetime.strptime(d["date"], "%b %d, %Y").date()
    except (ValueError, KeyError):
        return None


def nice_date(d):
    dt = date_of(d)
    return f"{dt.day} {dt.strftime('%B %Y')}" if dt else esc(d.get("date", ""))


def dlc_anchor(d):
    return slug(d["name"])


def pack_names(site):
    """Content pack hash -> display name: the DLC it belongs to, or OTHER_PACKS."""
    by = dlc_by_id(site)
    out = {h: by[a]["name"] for a, h in DLC_PACK.items() if a in by}
    for h, (n, _) in OTHER_PACKS.items():
        out.setdefault(h, n)
    return out


def all_pack_hashes(site):
    v = site.data("vanity")
    return ({v["base_pack"]} | {i["p"] for i in v["items"]} | {int(h) for h in v["packs"]}
            | {int(h) for h in site.data("keys")["pack_items"]})


def weapon_packs(site):
    """Paid weapon packs named in stats.json ('US Weapons Pack (DLC)' -> 'US Weapons Pack') -> [(category, name)]."""
    packs = collections.OrderedDict()
    for cat, ws in site.data("stats")["player_weapons"].items():
        for name, w in ws.items():
            p = (w.get("pack") or "") if isinstance(w, dict) else ""
            if p.endswith(" (DLC)"):
                packs.setdefault(p[:-6], []).append((cat, name))
    return packs


def mission_packs(site):
    """mission pack key -> (name, content pack hash or None)."""
    return {p["key"]: (p["name"], p.get("dlc")) for p in site.data("missions")["packs"]}


# ---------------------------------------------------------------------------------------------------------------
def collect(site):
    by = dlc_by_id(site)
    pk_of = {a: h for a, h in DLC_PACK.items()}
    mp = mission_packs(site)
    mp_by_hash = {h: k for k, (n, h) in mp.items() if h}
    for d in dlc_list(site):
        aliases = [d["name"] + " (DLC)", str(d["appid"])]
        h = pk_of.get(d["appid"])
        if h in mp_by_hash:
            aliases.append(mp_by_hash[h])
        site.register("dlc", d["name"], f"{DLC_PAGE}#{dlc_anchor(d)}", d["name"],
                      icon=d.get("image"), desc=f"{'Free' if d['free'] else 'Paid'} DLC, {nice_date(d)}. "
                                                f"{d.get('short', '')}",
                      aliases=aliases, keywords="dlc steam pack expansion")
    base = site.data("vanity")["base_pack"]
    site.register("dlc", "Base game", f"{DLC_PAGE}#pack-{base}", "Base game", aliases=["base"], search=False)
    if site.find("dlc", "Unreleased") is None:
        site.register("dlc", "Unreleased", "missions/unreleased.html", "Unreleased missions", aliases=["dlc03"],
                      search=False)
    # item packs: every content pack hash lands on its DLC entry or on its 'other packs' entry
    names = pack_names(site)
    for h in sorted(all_pack_hashes(site)):
        name = names.get(h)
        site.register("pack", str(h), f"{DLC_PAGE}#pack-{h}", name or "Item pack", aliases=[name] if name else [],
                      search=False)
    for d in dlc_list(site):      # pack names without a vanity pack (weapon packs ...) -> the DLC entry
        e = site.find("pack", d["name"])
        if e and e["path"].startswith(DLC_PAGE):
            continue
        site.register("pack", d["name"], f"{DLC_PAGE}#{dlc_anchor(d)}", d["name"], aliases=[d["name"] + " (DLC)"],
                      search=False)


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
        "main_missions": sum(1 for m in site.data("missions")["missions"]
                             if m["type"] == "main" and m["pack"] != "dlc03"),
        "schematics": len(site.data("schematics")["items"]),
        "skills": len(gd["skills"]["list"]),
        "vanity": len(site.data("vanity")["items"]),
        "items": len(site.data("stock")["stock"]),
        "loot": len(site.data("loot")["items"]),
        "dlc": len(dlc_list(site)),
    }


def build(site):
    c = counts(site)
    build_main(site, c)
    build_basics(site, c)
    build_dlc(site)
    build_about(site, c)


# ---------------------------------------------------------------------------------------------------------------
def clean(s):
    return re.sub(r"[™®]", "", s or "").strip()


def game_infobox(site):
    g = steam(site)["game"]
    plat = [n.title() for n, on in g.get("platforms", {}).items() if on]
    rows = [
        ("Developer", esc(", ".join(clean(x) for x in g.get("developers", [])))),
        ("Publisher", esc(", ".join(clean(x) for x in g.get("publishers", [])))),
        ("Released", nice_date(g)),
        ("Genre", "Open-world stealth-action shooter"),
        ("Steam genres", esc(", ".join(g.get("genres", [])))),
        ("Players", "1 to 4 (online co-op)"),
        ("Setting", "Östertörn, Sweden, 1989"),
        ("Platforms", esc(", ".join(plat)) + " (Steam), PlayStation 4, Xbox One"),
        ("DLC", f'<a href="~/{DLC_PAGE}">{len(dlc_list(site))} on Steam</a>'),
        ("Store", f'<a href="{esc(g["url"])}" rel="noopener">Steam store page</a>'),
    ]
    return infobox(g["name"], rows, image=site_img_url(site, g.get("image")), image_alt="Generation Zero")


def site_img_url(site, path):
    return "~/" + path if path and site.has_file(path) else None


def build_main(site, c):
    g = steam(site)["game"]
    lead = (f"<p><b>Generation Zero</b> is an open-world stealth-action shooter by Systemic Reaction, released on "
            f"{nice_date(g)}. You explore Östertörn, a region of Sweden in 1989 that has been taken over by hostile "
            f"machines, alone or with up to three friends.</p>"
            f"<p>This fan-made wiki is built straight from the game's own files, so its numbers are the ones the "
            f"game actually uses.</p>")
    sec = [
        {"href": "~/weapons/index.html", "title": "Weapons", "tag": "WPN", "color": "#2f4d5e",
         "img": "~/img/items/weapons/weapon_rifle_assault_556_01_alpha.png",
         "sub": f"{c['weapons']} weapons with damage for every ammo type and quality, {c['ammo']} ammo types, "
                f"attachments, {c['augments']} augments and every skin."},
        {"href": "~/machines/index.html", "title": "Machines", "tag": "MCH", "color": "#7a2a26",
         "img": site_img_url(site, "img/machines/hunter_military.webp"),
         "sub": f"Every machine class and its {c['machine_layouts']} weapon layouts, component hit points, "
                f"{c['machine_weapons']} machine weapons, detection ranges and difficulty scaling."},
        {"href": "~/world/index.html", "title": "World", "tag": "MAP", "color": "#5f4258",
         "img": "~/img/locations/location_church.png",
         "sub": f"{c['regions']} regions, {c['locations']} locations with mini maps, {c['safehouses']} safehouses, "
                f"{c['collectibles']} collectibles in {c['collectible_types']} sets."},
        {"href": "~/missions/index.html", "title": "Missions", "tag": "MIS", "color": "#1d4039",
         "img": site_img_url(site, "img/locations/mission_objective.png"),
         "sub": f"All {c['missions']} main and side missions with briefings and every objective, plus the "
                f"challenge trees and the titles they award."},
        {"href": "~/items/index.html", "title": "Items & crafting", "tag": "ITM", "color": "#4d4a2c",
         "img": "~/img/stock/equipment_consumable_firstaid_advanced_01_alpha.png",
         "sub": f"{c['items']} inventory items, materials, all {c['schematics']} schematics with costs and recipes, "
                f"and the companion."},
        {"href": "~/character/skills.html", "title": "Character", "tag": "CHR", "color": "#47545a",
         "img": site_img_url(site, "img/skills/skill_01_01.png"),
         "sub": f"All {c['skills']} skills, and {fmt(c['vanity'])} apparel items, emotes, vehicles and other "
                f"cosmetics."},
        {"href": "~/map/index.html", "title": "Interactive map", "tag": "MAP", "color": "#5f4258",
         "img": site_img_url(site, "map/map/icons/gnomes.png"),
         "sub": f"Filter collectibles, schematics, safehouses, control points and {fmt(c['loot'])} pieces of "
                f"placed loot on the full world map."},
        {"href": f"~/{DLC_PAGE}", "title": "DLC", "tag": "DLC", "color": "#1c5777",
         "img": site_img_url(site, "img/dlc/1301740.jpg"),
         "sub": f"All {c['dlc']} DLC: the Alpine Unrest and FNIX Rising expansions, free updates, and the weapon, "
                f"equipment, vehicle and cosmetic packs."},
    ]
    for s in sec:
        if not s.get("img"):
            s.pop("img", None)
    body = []
    body.append(bar("About the game"))
    body.append(f"""<p>It is late 1989. You come back from a trip to the islands of the
{site.link('region', 'archipelago', 'Archipelago')} and find Östertörn empty: the people are gone, and the towns,
farms and forests are patrolled by machines. You scavenge weapons, ammo and gear, find out what happened, and fight
back.</p>
<ul>
<li><b>Open world.</b> One big map of {c['regions']} regions with {c['locations']} named places to explore: villages,
farms, churches, bunkers and military bases.</li>
<li><b>Machines, not a health bar.</b> Every machine is built from parts and armour plates you can shoot off one by
one. Use stealth, the right ammo and traps to take them on.</li>
<li><b>Co-op.</b> Play alone or with up to three friends in online co-op.</li>
<li><b>Grow stronger.</b> Earn experience for {c['skills']} skills, find better weapons, craft ammo and gear from
schematics, and build and defend your own bases.</li>
<li><b>Story.</b> {c['main_missions']} main missions and many side missions tell what happened to Östertörn; two
expansions, {site.link('dlc', 'Alpine Unrest')} and {site.link('dlc', 'FNIX Rising')}, continue the story.</li>
</ul>""")
    if g.get("about"):
        body.append(fold("From the Steam store page", store_text(g["about"]) +
                         f'<p><a href="{esc(g["url"])}" rel="noopener">Open the Steam store page</a></p>',
                         level=3, id="steam-about"))
    body.append(bar("Browse the wiki"))
    body.append(cards(sec))
    body.append(bar("What's special about this wiki"))
    body.append("""<ul>
<li><b>Exact damage tables</b> for every weapon: each ammo type's damage, armour and component multipliers, damage
falloff and range, worked out for every quality from Dilapidated to Experimental.</li>
<li><b>Machine anatomy</b>: the hit points of every component and armour plate on every machine class and weapon
layout, and the weapons each layout carries.</li>
<li><b>Stealth numbers</b>: how far each machine can see and hear you crouched, prone, standing or running, by day
and by night, and how fast it notices you.</li>
<li><b>Difficulty and co-op scaling</b> as the game applies it, per difficulty and number of players.</li>
<li><b>Which augment fits which weapon</b> at which quality, and how to research each one.</li>
<li><b>Every location</b> with its own page and mini map, and the collectibles and loot around it.</li>
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
        ("DLC", f"~/{DLC_PAGE}", "What each expansion, update and pack adds."),
    ]
    body.append('<div class="hmlinks">' + "".join(
        f'<a class="hmlink" href="{u}"><b>{esc(t)}</b><span>{esc(d)}</span></a>' for t, u, d in links) + "</div>")
    body.append(bar("Regions"))
    body.append(regions_map(site))
    site.page("index.html", "Generation Zero Wiki", "\n".join(body), "home", lead=lead, head_extra=CSS,
              infobox_html=game_infobox(site),
              desc="Generation Zero wiki built from the game files: weapons, machines, locations, missions, "
                   "collectibles, schematics and DLC.", search=False)


def regions_map(site):
    """Small overview map of the regions (the centre of each region's map locations) with the region list beside."""
    locs = collections.defaultdict(list)
    for e in site.data("map_locations")["list"]:
        locs[e.get("region")].append((e["x"], e["z"]))
    pts = []
    for k, n in REGIONS:
        ps = locs.get(k)
        if ps:
            pts.append((sum(p[0] for p in ps) / len(ps), sum(p[1] for p in ps) / len(ps), ""))
    lst = "".join(f"<li>{site.link('region', k, n)}</li>" for k, n in REGIONS)
    text = (f"<p>The map is one continuous world. You start on the islands of the "
            f"{site.link('region', 'archipelago', 'Archipelago')} and work your way north; "
            f"{site.link('region', 'alpine', 'Himfjäll')} comes with Alpine Unrest.</p>"
            f'<ul class="hmregions">{lst}</ul>')
    if not pts:
        return text
    x, z, _ = pts[0]
    return minimap(x, z, "", markers=pts[1:], small=True, text=text)


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
             "Special); a higher quality does more damage and is more accurate. "
             "<a href=\"~/weapons/experimental.html\">Experimental</a> weapons are a sixth tier with unique ammo. "
             "Ammo types matter as much as the gun: armour-piercing rounds hit armour harder, hollow-points tear "
             "up components, and special rounds burn, shock or explode. See "
             "<a href=\"~/weapons/index.html\">all weapons</a> and <a href=\"~/weapons/ammo.html\">ammo</a>.</p>")
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
# DLC page
# ---------------------------------------------------------------------------------------------------------------
def store_text(s):
    """Steam 'about' text -> HTML: paragraphs, headings ('Timeless Set:', 'EXPANSION PACK FEATURES') and lists."""
    out, items = [], []

    def flush():
        if items:
            out.append("<ul>" + "".join(f"<li>{esc(i)}</li>" for i in items) + "</ul>")
            items.clear()

    def is_head(t):
        # 'Timeless Set:' or 'EXPANSION PACK FEATURES' (not a short code like 'HP5')
        return len(t) <= 48 and (t.endswith(":") or (t.upper() == t and len(re.findall(r"[^\W\d_]", t)) >= 6))

    def is_short(t):   # a line of a bare list: 'Kvm 59 x2', '"Älgstudsare" Hunting Rifle'
        return bool(t) and len(t) <= 40 and t[-1] not in ".!?:" and t[0] not in "•-" and not is_head(t)

    lines = []
    for raw in (s or "").split("\n"):
        raw = raw.strip()
        # a heading glued to the end of a paragraph: '... no matter what.Ecto-Scientist Set:'
        m = re.match(r"^(.*[.!?)])\s*([A-Z][^.!?]{2,46}(?::|[A-Z ]{3,}))$", raw)
        if m and len(m.group(1)) > 40 and is_head(m.group(2)):
            lines += [m.group(1), m.group(2)]
        else:
            lines.append(raw)
    lines = [t for t in lines if t]
    bare = set()   # runs of 3+ short lines without punctuation are a list
    i = 0
    while i < len(lines):
        j = i
        while j < len(lines) and is_short(lines[j]):
            j += 1
        if j - i >= 3:
            bare.update(range(i, j))
        i = max(j, i + 1)
    for n, t in enumerate(lines):
        if n in bare:
            items.append(t)
            continue
        if t[0] in "•-" and len(t) > 2:
            items.append(t.lstrip("•- ").strip())
            continue
        flush()
        nxt = lines[n + 1] if n + 1 < len(lines) else ""
        titled = (is_short(t) and len(nxt) > 60 and
                  sum(w[0].isupper() for w in t.split()) * 2 > len(t.split()))   # 'Explore a Hostile Open World'
        if is_head(t) or titled:
            out.append(f"<h4>{esc(t.rstrip(':').strip())}</h4>")
        else:
            out.append(f"<p>{esc(t)}</p>")
    flush()
    return "".join(out)


def vicon(i):
    return "img/vanity/" + i["i"] if i.get("i") else None


def icon_html(site, path, wide=False):
    return site.img(path, "", "dli wide" if wide else "dli") if path else ""


def chip(site, kind, key, text, icon=None, count=1, extra="", wide=False):
    """One item of a DLC's contents: icon, link (or plain text when nobody registered it), ×count."""
    e = site.find(kind, key) if key is not None else None
    ic = icon_html(site, icon or (e.get("icon") if e else None), wide)
    label = site.link(kind, key, text) if key is not None else esc(text)
    n = f' <span class="dim">×{count}</span>' if count > 1 else ""
    x = f' <span class="dim">{extra}</span>' if extra else ""
    return f"<li>{ic}<span>{label}{n}{x}</span></li>"


def pack_groups(site, h):
    """[(group label, [chip html])] for everything in content pack h: vanity items, keys, schematics, materials."""
    v = site.data("vanity")
    gname = {g["key"]: g["name"] for g in v["groups"]}
    skin_weapon = {s["key"]: s["name"] for g in v["groups"] if g["key"] == "skins" for s in g["subs"]}
    its = [i for i in v["items"] if i["p"] == h]
    out = []
    for g in GROUP_ORDER:
        gi = sorted((i for i in its if i["g"] == g), key=lambda i: i["n"].lower())
        if not gi:
            continue
        chips = []
        if g == "apparel":
            pieces = collections.OrderedDict()
            for i in gi:
                pieces.setdefault(i["n"].split(", ")[0], []).append(i)
            for base, ps in pieces.items():
                chips.append(chip(site, "vanity", ps[0]["r"], base, vicon(ps[0]), len(ps)))
            label = (f"Apparel ({len(pieces)} piece{'s' if len(pieces) != 1 else ''}"
                     + (f", {len(gi)} with colours)" if len(gi) > len(pieces) else ")"))
        elif g == "companion":
            seen = collections.OrderedDict()
            for i in gi:
                seen.setdefault(i["n"], []).append(i)
            for n, ps in seen.items():
                chips.append(chip(site, "item", ps[0]["r"], n, vicon(ps[0]), len(ps)))
            label = f"Companion ({len(seen)})"
        elif g == "skins":
            for i in gi:
                w = skin_weapon.get(i["s"], "")
                chips.append(chip(site, "skin", i["r"], i["n"], vicon(i),
                                  extra=esc(w) if w and norm(w) not in norm(i["n"]) else ""))
            label = f"Weapon skins ({len(gi)})"
        else:
            for i in gi:
                chips.append(chip(site, "vanity", i["r"], i["n"], vicon(i)))
            label = f"{gname.get(g, g)} ({len(gi)})"
        out.append((label, chips))
    # non-vanity items listed for the pack (keys.json pack_items)
    k = site.data("keys")
    keys = {i["h"]: i for i in k["items"]}
    stock = {i["h"]: i for i in site.data("stock")["stock"]}
    sch = {i["h"]: i for i in site.data("schematics")["items"]}
    vh = {i["h"] for i in v["items"]}
    extra = collections.defaultdict(collections.OrderedDict)
    for ih in k["pack_items"].get(str(h), []):
        if ih in vh:
            continue
        if ih in keys:
            e = keys[ih]
            extra["Keys and quest items"].setdefault(e["n"], [("key", e["n"], "img/keys/" + e["i"] if e.get("i")
                                                               else None), 0])[1] += 1
        elif ih in sch:
            e = sch[ih]
            extra["Schematics"].setdefault(e["n"], [("schematic", str(ih), "img/schematics/" + e["i"]), 0])[1] += 1
        elif ih in stock:
            e = stock[ih]
            kind = "material" if e["g"] == "materials" else "item"
            grp = "Materials" if kind == "material" else "Items"
            extra[grp].setdefault(e["name"], [(kind, e["name"], e["icon"].replace("assets/", "img/", 1)), 0])[1] += 1
    for grp in ("Keys and quest items", "Schematics", "Materials", "Items"):
        lst = extra.get(grp)
        if lst:
            chips = [chip(site, kind, key, n, icon, cnt) for n, ((kind, key, icon), cnt) in
                     sorted(lst.items(), key=lambda x: x[0].lower())]
            out.append((f"{grp} ({len(lst)})", chips))
    # keys that name this pack in keys.json items (expansion keys), not already listed
    listed = set(extra.get("Keys and quest items", {}))
    ks = [i for i in k["items"] if i.get("p") == h and i["n"] not in listed]
    if ks:
        chips = [chip(site, "key", i["n"], i["n"], "img/keys/" + i["i"] if i.get("i") else None) for i in ks]
        names = [lbl for lbl, _ in out]
        if any(n.startswith("Keys and quest items") for n in names):
            idx = next(j for j, n in enumerate(names) if n.startswith("Keys and quest items"))
            lbl, old = out[idx]
            out[idx] = (f"Keys and quest items ({len(old) + len(chips)})", old + chips)
        else:
            out.append((f"Keys and quest items ({len(chips)})", chips))
    return out


def chip_list(groups):
    return "".join(f'<div class="dlgrp"><div class="dlgh">{esc(lbl)}</div><ul class="dlitems">{"".join(ch)}</ul>'
                   f"</div>" for lbl, ch in groups if ch)


def weapon_chips(site, ws):
    out = []
    for cat, n in ws:
        c = cat_singular(cat)
        out.append(chip(site, "weapon", n, n, extra=esc(c) if c and norm(c) not in norm(n) else "", wide=True))
    return out


def cat_singular(cat):
    return {"Handguns": "handgun", "Submachine guns": "SMG", "Assault rifles": "assault rifle",
            "Machine guns": "machine gun", "Hunting rifles": "hunting rifle", "Sniper rifles": "sniper rifle",
            "Shotguns": "shotgun", "Launchers": "launcher", "Bows and flamethrowers": "",
            "Melee": "melee", "Throwables": "throwable"}.get(cat, cat.lower())


def summary_line(groups):
    """'Adds 41 apparel pieces, 5 emotes and 2 face paint.' from the group labels."""
    parts = []
    for lbl, ch in groups:
        m = re.match(r"(.+?) \((\d+)", lbl)
        if not m:
            continue
        name, n = m.group(1), int(m.group(2))
        name = {"Apparel": "apparel pieces", "Face paint": "face paints", "Emotes": "emotes",
                "Weapon skins": "weapon skins", "Companion": "companion items", "Vehicles": "vehicle paint jobs",
                "Keys and quest items": "keys and quest items", "Schematics": "schematics",
                "Materials": "materials", "Items": "items", "Weapons": "weapons",
                "Equipment": "pieces of equipment"}.get(name, name.lower())
        if n == 1:
            name = {"apparel pieces": "apparel piece", "face paints": "face paint", "emotes": "emote",
                    "weapon skins": "weapon skin", "companion items": "companion item",
                    "vehicle paint jobs": "vehicle paint job", "schematics": "schematic", "materials": "material",
                    "items": "item", "weapons": "weapon", "pieces of equipment": "piece of equipment",
                    "keys and quest items": "key or quest item"
                    }.get(name, name)
        parts.append(f"{n} {name}")
    if not parts:
        return ""
    return (", ".join(parts[:-1]) + " and " + parts[-1]) if len(parts) > 1 else parts[0]


def expansion_facts(site, h):
    """Missions, region and challenge tree of a story expansion (missions.json pack with this content pack)."""
    mp = mission_packs(site)
    key = next((k for k, (n, hh) in mp.items() if hh == h), None)
    if not key:
        return ""
    ms = [m for m in site.data("missions")["missions"] if m["pack"] == key]
    main = sum(1 for m in ms if m["type"] == "main")
    side = sum(1 for m in ms if m["type"] == "side")
    regions = collections.Counter(m["region"] for m in ms)
    rnames = dict(REGIONS)
    murl = site.url("mission-region", "alpine") if key == "alpine" else None
    murl = murl or "~/" + MISSION_PAGE.get(key, "missions/index.html")
    li = [f'<li><a href="{murl}">{main} main and {side} side missions</a> in '
          + ", ".join(site.link("region", r, rnames.get(r, r)) for r, _ in regions.most_common()) + "</li>"]
    trees = [t for t in site.data("gamedata")["challenges"] if t["dlc"] and tree_pack(site, t) == key]
    for t in trees:
        li.append(f"<li>The {site.link('challenge', t['name'], t['name'].title())} challenge tree "
                  f"({len(t['challenges'])} challenges)</li>")
    return '<ul class="dlfacts">' + "".join(li) + "</ul>"


def tree_pack(site, tree):
    """Mission pack of a DLC challenge tree, from the mission and pack names its tiers quote."""
    md = site.data("missions")
    by_pack_name = {norm(p["name"]): p["key"] for p in md["packs"]}
    mission_pack = {norm(x["name"]): x["pack"] for x in md["missions"]}
    votes = collections.Counter()
    for ch in tree["challenges"]:
        for t in ch["tiers"]:
            for q in re.findall(r'"([^"]+)"', t.get("desc", "")):
                pk = mission_pack.get(norm(q)) or by_pack_name.get(norm(q))
                if pk and pk != "base":
                    votes[pk] += 1
    return votes.most_common(1)[0][0] if votes else None


def dlc_entry(site, d, wpacks):
    a = d["appid"]
    h = DLC_PACK.get(a)
    img = site.img(d.get("image"), d["name"]) if d.get("image") else ""
    tags = (tag("Free", "green") if d["free"] else tag("Paid", "dlc")) + f' <span class="dim">{nice_date(d)}</span>'
    facts = ""
    groups = []
    if h:
        facts = expansion_facts(site, h)
        groups = pack_groups(site, h)
    if d["name"] in wpacks:
        groups = [(f"Weapons ({len(wpacks[d['name']])})", weapon_chips(site, wpacks[d["name"]]))] + groups
    if a in DLC_ITEMS:
        have = {s["name"] for s in site.data("stock")["stock"]}
        stock = {s["name"]: s for s in site.data("stock")["stock"]}
        names = [n for n in DLC_ITEMS[a] if n in have]
        groups.append((f"Equipment ({len(names)})",
                       [chip(site, "item", n, n, stock[n]["icon"].replace("assets/", "img/", 1)) for n in names]))
    if a == 1173930:   # Rivals & Experimental Weapons
        facts = ('<ul class="dlfacts"><li><a href="~/machines/rivals.html">Rivals</a>: machines that grow '
                 'stronger and get a name and title</li><li><a href="~/weapons/experimental.html">Experimental '
                 'weapons</a>, a sixth weapon quality with special ammo</li></ul>')
        groups.append(("Experimental versions of", [chip(site, "weapon", n, n, wide=True) for n in EXPERIMENTAL_UPDATE]))
    summ = summary_line(groups)
    parts = [f'<div class="dlhead"><h3>{esc(d["name"])}</h3><div class="dltags">{tags}</div></div>',
             f'<p>{esc(d.get("short", ""))}</p>', facts]
    if summ and a != 1173930:
        parts.append(f'<p class="dladds"><b>Adds</b> {esc(summ)}.</p>')
    n_chips = sum(len(ch) for _, ch in groups)
    contents = chip_list(groups)
    if contents and n_chips <= 12:
        parts.append(contents)
    elif contents:
        parts.append(fold("What's in it", contents, level=3, id=f"{dlc_anchor(d)}-items",
                          right=f"{n_chips} items"))
    if a in (1610720, 1850670):
        parts.append('<p class="small dim">These are base-building structures; the store description below lists '
                     'them.</p>')
    parts.append(fold("Store description", store_text(d.get("about")) +
                      f'<p><a href="{esc(d["url"])}" rel="noopener">Open the Steam store page</a></p>',
                      level=3, id=f"{dlc_anchor(d)}-store"))
    anchor = f'<span class="dlanchor" id="pack-{h}"></span>' if h else ""
    pic = (f'<a class="dlimg" href="{esc(d["url"])}" rel="noopener" title="Steam store page">{img}</a>'
           if img else "")
    return (f'<section class="dlentry" id="{dlc_anchor(d)}">{anchor}{pic}<div class="dlmain">{"".join(parts)}'
            f"</div></section>")


def other_pack_entry(site, h):
    name, what = OTHER_PACKS.get(h, ("Item pack", ""))
    v = site.data("vanity")
    if h == v["base_pack"]:
        n = sum(1 for i in v["items"] if i["p"] == h)
        body = (f'<span class="dlanchor" id="pack-{h}"></span><p>{esc(what)} That includes {n} cosmetic items: '
                f'see <a href="~/character/apparel.html">Apparel</a>, <a href="~/character/emotes.html">Emotes &amp; '
                f'face paint</a> and <a href="~/weapons/skins.html">Weapon skins</a>.</p>')
        return f'<div class="dlother">{body}</div>'
    groups = pack_groups(site, h)
    its = [i for i in v["items"] if i["p"] == h]
    dlc_flag = its and all(i["l"].endswith("D") for i in its)
    how = (" The game files mark these items as downloadable content." if dlc_flag else "")
    body = f"<p>{esc(what)}{how}</p>" + chip_list(groups)
    n = sum(len(ch) for _, ch in groups)
    return fold(name, body, level=3, id=f"pack-{h}", right=f"{n} item{'s' if n != 1 else ''}" if n else "")


def build_dlc(site):
    st = steam(site)
    by = dlc_by_id(site)
    wpacks = weapon_packs(site)
    dl = dlc_list(site)
    n_free = sum(1 for d in dl if d["free"])
    dates = sorted(x for x in (date_of(d) for d in dl) if x)
    lead = (f"<p>Generation Zero has {len(dl)} DLC on Steam: two story expansions, {n_free} free updates, and paid "
            f"packs with weapons, equipment, vehicles and cosmetics. Each entry below gives the store summary and "
            f"what the pack adds, read from the game files. Content from the two expansions is tagged on the "
            f"other pages of this wiki, like {tag('Alpine Unrest', 'alpine')} or {tag('FNIX Rising', 'fnix')}.</p>")
    b = []
    for gid, title, intro, ids in GROUPS:
        b.append(bar(title, f"{len(ids)} DLC", id=gid))
        b.append(f"<p>{esc(intro)}</p>")
        for a in ids:
            if a in by:
                b.append(dlc_entry(site, by[a], wpacks))
    missing = [d for d in dl if not any(d["appid"] in g[3] for g in GROUPS)]
    if missing:
        b.append(bar("More DLC", id="more"))
        b += [dlc_entry(site, d, wpacks) for d in missing]
    # item packs in the game files that no Steam DLC lists
    known = set(DLC_PACK.values())
    others = [h for h in OTHER_PACKS if h in all_pack_hashes(site) and h not in known]
    others += sorted(h for h in all_pack_hashes(site) if h not in known and h not in OTHER_PACKS)
    ob = ["<p>The game files sort items into packs. These packs are not sold as a DLC: they hold the base game, "
          "free updates such as the Machine Companion, rewards and event outfits. The names here describe what "
          "is in each pack; the files don't name them.</p>", '<div class="foldall" data-for="other-packs"></div>']
    ob += [other_pack_entry(site, h) for h in others]
    b.append(fold("Other item packs", "".join(ob), id="other-packs", right=f"{len(others)} packs"))
    g = st["game"]
    paid = len(dl) - n_free
    box = infobox("DLC", [
        ("On Steam", f"{len(dl)} DLC"),
        ("Paid", str(paid)),
        ("Free", str(n_free)),
        ("Expansions", f"{site.link('dlc', 'Alpine Unrest')}, {site.link('dlc', 'FNIX Rising')}"),
        ("First", f"{dates[0].day} {dates[0].strftime('%B %Y')}" if dates else None),
        ("Latest", f"{dates[-1].day} {dates[-1].strftime('%B %Y')}" if dates else None),
        ("Store", f'<a href="https://store.steampowered.com/dlc/{g["appid"]}/" rel="noopener">All DLC on Steam</a>'),
    ], image=site_img_url(site, g.get("image")), image_alt="Generation Zero")
    order = sorted(dl, key=lambda d: (date_of(d) or datetime.date.max))
    timeline = '<ol class="dltime">' + "".join(
        f'<li><span class="dim">{date_of(d).year if date_of(d) else ""}</span>'
        f'<span><a href="#{dlc_anchor(d)}">{esc(d["name"])}</a>{" " + tag("Free", "green") if d["free"] else ""}'
        f'</span></li>'
        for d in order) + "</ol>"
    site.page(DLC_PAGE, "DLC", "\n".join(b), "home", lead=lead, head_extra=CSS, infobox_html=box,
              side=[fold_panel("Release order", timeline)],
              desc="All Generation Zero DLC: the Alpine Unrest and FNIX Rising expansions, free updates, weapon, "
                   "equipment, vehicle and cosmetic packs, and what each adds.")


def fold_panel(title, body):
    """A side panel that starts closed (a long list that would push the contents bar down)."""
    return (f'<details class="sidepanel dlpanel"><summary class="ibh">{esc(title)}</summary>'
            f'<div class="spb">{body}</div></details>')


# ---------------------------------------------------------------------------------------------------------------
def build_about(site, c):
    lead = ("<p>The Generation Zero Wiki is a fan-made guide to Generation Zero. Everything on it comes straight from the "
            "game's own files.</p>")
    b = []
    b.append(bar("Where the information comes from"))
    b.append("<p>We made our own extraction tool that opens Generation Zero's game files and reads out the data "
             "the game itself uses: weapon damage, machine health, skills, schematics, missions, items, map "
             "positions and more. The wiki pages are built from that data automatically.</p>"
             "<p>That means the numbers here are not guesses or copied from older guides. When the game is updated, "
             "the data is read again and the pages are rebuilt.</p>")
    b.append(note("Where the current game files disagree with something older guides still say, the page points "
                  "it out in a green <b>Corrected</b> box. A few things, like some special ammo effects, aren't "
                  "stored where the tool can read them; the pages say so where it matters.", "data"))
    b.append(bar("Pictures"))
    mi = site.data("machine_images")["images"]
    srcs = []
    for typ, classes in mi.items():
        for cls, e in classes.items():
            if isinstance(e, dict) and e.get("source", "render") != "render":
                srcs.append(f'<li><a href="{esc(e["source"])}" rel="noopener">{esc(cls)} {esc(typ)}</a></li>')
    b.append("<p>Item icons, map art and other game images come from Generation Zero itself and belong to "
             "Systemic Reaction and Avalanche Studios Group; they are shown here for reference.</p>"
             "<p>The pictures of the machines were rendered for this wiki from the game's own 3D models, which the "
             "extraction tool reads out of the game files together with their animations; each machine type is shown "
             "in one of its own in-game poses.</p>"
             + ("<p>The machine pictures listed below are still from the "
                "<a href=\"https://generation-zero.fandom.com/\" rel=\"noopener\">Generation Zero Wiki on Fandom</a>, "
                "used under the <a href=\"https://creativecommons.org/licenses/by-sa/3.0/\" rel=\"noopener\">CC BY-SA</a> "
                "licence, until their renders are done.</p>" if srcs else "") +
             "<p>The DLC pictures and descriptions on the <a href=\"~/dlc.html\">DLC page</a> are from the "
             "<a href=\"https://store.steampowered.com/app/704270/\" rel=\"noopener\">Steam store</a>. The "
             "<a href=\"~/missions/achievements.html\">achievement</a> names, descriptions and icons are read from "
             "Steam's own achievement list for the game.</p>"
             "<p>The \"Mission start\" box on the mission pages (where a mission starts, with its coordinates) is from "
             "the mission pages of the <a href=\"https://generation-zero.fandom.com/\" rel=\"noopener\">Generation "
             "Zero Wiki on Fandom</a> (<a href=\"https://creativecommons.org/licenses/by-sa/3.0/\" "
             "rel=\"noopener\">CC BY-SA</a>); each box links to its source page.</p>")
    if srcs:
        b.append(fold("Machine picture sources", f'<ul class="hmsrc">{"".join(srcs)}</ul>', level=3,
                      id="picture-sources", right=f"{len(srcs)} pictures"))
    b.append(bar("Fan-made"))
    b.append("<p>This wiki is made by fans and is not affiliated with or endorsed by Systemic Reaction or Avalanche "
             "Studios Group. Generation Zero is a trademark of Systemic Reaction / Avalanche Studios Group.</p>")
    b.append(bar("Found a mistake?"))
    b.append("<p>If something looks wrong, please open an issue on "
             "<a href=\"https://github.com/The-Bewwy-2510/gen0-wiki\" rel=\"noopener\">GitHub</a>.</p>")
    b.append("<p class=\"small dim\">Font: Open Sans (SIL Open Font License).</p>")
    site.page("about.html", "About this wiki", "\n".join(b), "home", lead=lead, head_extra=CSS,
              desc="Where this wiki's information comes from, picture credits and how to report a mistake.")
