"""World > Collectibles and Keys & barcodes.

Pages
    world/collectibles.html            every collectible type of markers.json (collectibles, schematic points,
                                       house photos): cards per group, counts per region, the challenges
    world/collectibles/<sub key>.html  one page per type: a map of every pickup and the list of pickups (per region
                                       folds for the long lists); the challenge and the region split in the rail
    world/keys.html                    keys.json: command bunker barcodes, facility keycards, door keys and
                                       mission items, one collapsed section per kind, then the content packs and a
                                       small map of the keys that lie loose in the world

Kinds registered
    collectible-type   key = markers.json sub key ('gnomes'), aliases = display name
    key                key = keys.json name, aliases = internal name and item hash (search only, never printed)

Data: markers.json (subs + items: s = sub key, n = name, x/z = world position in metres, l = the game's internal
scene name, r = map region), map_locations.json (named locations, for "nearest"), gamedata.json (challenges,
schematic point currencies), schematics.json, keys.json, loot.json (the four keys that lie loose in the world),
missions.json (to show which mission uses a key), vanity.json (dance emotes, gnome masks).

Layout v2: no internal names / hashes / scene names on the pages. Map links carry the type's filter
(show=<sub key>) and per-item links focus the marker by its exact name.
"""
import collections
import math
import re

from wiki.site import (esc, slug, norm, fmt, table, infobox, bar, fold, panel, maplink, minimap, note, cards, kv,
                       tag, REGIONS)

CSS = '<link rel="stylesheet" href="~/assets/collectibles.css">'
REGION_NAME = dict(REGIONS)
REGION_KEYS = [k for k, _ in REGIONS]
REGION_SHORT = {k: n.split(" (")[0] for k, n in REGIONS}        # 'Himfjäll' instead of 'Himfjäll (Alpine Unrest)'
REGION_DLC = {"alpine": "Alpine Unrest"}

OWN_MAINS = ("collectibles", "schematics", "housephotos")     # playersafehouses / control points / beacons: world
GROUP_LABEL = {"collectibles": "Collectibles", "schematics": "Schematic points", "housephotos": "House photos"}
GROUP_ONE = {"collectibles": "Collectible", "schematics": "Schematic points", "housephotos": "House photo"}

PHOTO_AT = 50          # m: a house photo this close to a safehouse belongs to it (the real gap is 1-29 m)
COPY_LABEL = "Island01 Dialogue"    # audio log markers that are the dialogue copy of a log, not a pickup
GLOBAL_LABEL = "Global"             # world location entries: placed in a global scene, not in the world
SKIP_LOCATIONS = {"Unknown"}        # location names that are no use as "nearest location"
FOLD_OVER = 40         # a type with more pickups than this lists them in one closed fold per region

# What each type is. Plain facts only; the counts and regions are added from the data. The first sentence is also
# the text of the type's card on the overview, so it should say something on its own.
BLURB = {
    "dalahast": "Dala horses (<i>dalahäst</i>), the carved and painted wooden horse that is the classic Swedish "
                "souvenir, each with its own paint job from <i>Classic</i> to <i>Skeleton</i> and <i>Kronor</i>.",
    "gnomes": "Garden gnomes hidden around the mainland, each one a different style: <i>Unpainted</i>, "
              "<i>Devil</i>, <i>Italian</i>, <i>Santa</i>, <i>Bronze</i> and more.",
    "mixtapes": "Cassette mixtapes, each with its own title, from <i>Chaos Rug</i> and <i>Wedding Mix</i> to "
                "<i>Pets Playtime</i>. Seven of them carry the name of a story character (<i>Char Monika</i>, "
                "<i>Char Veronika</i>, <i>Char Holberg</i>, <i>Char Von Ulmer</i>, <i>Char Emil</i>, <i>Char "
                "Anita</i>, <i>Char Ingrid</i>), and one more is <i>Emils Tape</i>.",
    "audiologs": "Recorded audio logs on Himfjäll, the island of the Alpine Unrest expansion: three each from "
                 "Svante Von Ulmer, Fredrik Holberg and Emil Sandberg.",
    "blueprints": "Machine blueprints, one per machine type and class letter, plus two Rival blueprints. They cover "
                  "the original machines, the Soviet Lynx, Wolf and Firebird, the Class D machines, and the Reaper "
                  "and Vulture of the Rivals.",
    "videotapes": "VHS videotapes whose titles are the names of dance emotes, such as <i>Twisting</i>, "
                  "<i>Spacewalk</i> and <i>Royalty</i>.",
    "biographies": "Character biographies on Himfjäll, one each for Anita, Benny, Elsa, Holberg, Ingrid, Veronika "
                   "and Von Ulmer.",
    "photos": "Vacation photos on Himfjäll, counted by the Himfjäll challenge <i>Memories of the Forgotten</i>.",
    "loveletters": "Love letters, counted together with the Survivor's Notes by the challenge "
                   "<i>What's The Skinny</i>.",
    "survivornotes": "Notes left behind by survivors, counted together with the Love Letters by the challenge "
                     "<i>What's The Skinny</i>.",
    "worldlocations": "One lore entry for each mainland region, with no place in the world. The files put all of "
                      "them in a global scene at one placeholder position, so they are not pickups you find on the "
                      "map.",
    "bottles": "Resistance bottles: the Messages in a Bottle that the DAWN challenge <i>Together in Loneliness</i> "
               "asks you to collect.",
    "newspapers": "Newspapers, all of them in the town of Östervik.",
    "sovietdolls": "Soviet dolls, numbered <i>Soviet Doll 01</i> to <i>10</i>, all of them in the Marshlands, some "
                   "inside named locations and some in the open country between them.",
    "toysoldiers": "Toy soldiers, all of them on the North Coast. They are numbered <i>Toy Soldier 01</i> to "
                   "<i>10</i>, but the files have two different pickups that are both called <i>Toy Soldier "
                   "08</i>.",
    "sch_ammo": "Pickups that give <b>Ammo Schematic Points</b>, the currency you spend in the ammo crafting "
                "tree.",
    "sch_apparel": "Pickups that give <b>Apparel Schematic Points</b>, the currency you spend in the apparel "
                   "crafting tree.",
    "sch_equipment": "Pickups that give <b>Equipment Schematic Points</b>, the currency you spend in the equipment "
                     "crafting tree.",
    "safehousehints": "House photos: a photo collectable that belongs to a safehouse. Each one lies inside or right "
                      "next to its safehouse.",
}

# collectible type -> words a challenge tier description uses for it (gamedata.json challenges)
CHALLENGE_PHRASE = {"bottles": "Messages in a Bottle", "photos": "Vacation Photos",
                    "survivornotes": "Survivor's Notes", "loveletters": "Love Letters"}


# ---------------------------------------------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------------------------------------------
def dist(a, b):
    return math.hypot(a["x"] - b["x"], a["z"] - b["z"])


def compass(a, b):
    """Direction from a to b as N, NE, E ... (+z is south on the map)."""
    ang = math.degrees(math.atan2(b["x"] - a["x"], -(b["z"] - a["z"]))) % 360
    return ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][int((ang + 22.5) // 45) % 8]


def dlc_tag(region):
    return tag(REGION_DLC[region], "dlc") if region in REGION_DLC else ""


def region_link(site, r, dlc=True):
    return site.link("region", r, REGION_SHORT[r]) + (" " + dlc_tag(r) if dlc and r in REGION_DLC else "")


def page_path(key):
    return f"world/collectibles/{key}.html"


def plural(n, one, many=None):
    return f"{n} {one if n == 1 else (many or one + 's')}"


def and_list(parts):
    parts = list(parts)
    if len(parts) <= 1:
        return "".join(parts)
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def strip_tags(h):
    return re.sub("<[^>]+>", "", h or "")


# ---------------------------------------------------------------------------------------------------------------
# the data model, computed once
# ---------------------------------------------------------------------------------------------------------------
class Model:
    def __init__(self, site):
        mk = site.data("markers")
        self.subs = [s for s in mk["subs"] if s["main"] in OWN_MAINS]
        self.sub = {s["key"]: s for s in self.subs}
        # 'Unknown' is a placeholder name some unnamed places carry; it is no help as a landmark
        self.locs = [l for l in site.data("map_locations")["list"] if l["name"] not in SKIP_LOCATIONS]
        self.safehouses = [m for m in mk["items"] if m["s"] == "playersafehouses"]
        self.items = collections.defaultdict(list)       # sub key -> [item]
        # the audio-log dialogue copies go last, so the pickups are numbered 1..n
        for m in sorted(mk["items"], key=lambda m: m["l"] == COPY_LABEL):
            if m["s"] in self.sub:
                self.items[m["s"]].append(self._item(m, len(self.items[m["s"]]) + 1))
        self.challenges = self._challenges(site.data("gamedata"))
        self.tree_dlc = {t["name"]: tree_dlc(site, t) for t in site.data("gamedata")["challenges"]}

    def _item(self, m, num):
        it = dict(m, num=num, copy=m["l"] == COPY_LABEL, glob=m["l"] == GLOBAL_LABEL, loc=None, ld=None)
        # the dialogue copies and the global entries have no real place, so no "nearest location" either
        if not it["glob"] and not it["copy"]:
            it["loc"] = min(self.locs, key=lambda l: dist(l, m))
            it["ld"] = dist(it["loc"], m)
        if m["s"] == "safehousehints":
            sh = min(self.safehouses, key=lambda s: dist(s, m))
            it["safehouse"] = sh if dist(sh, m) <= PHOTO_AT else None
            it["sd"] = dist(sh, m)
        return it

    def pickups(self, key, region=None):
        """The items you can actually pick up: without the audio-log dialogue copies."""
        return [i for i in self.items[key] if not i["copy"] and (region is None or i["r"] == region)]

    def placed(self, key):
        """The pickups that have a real position in the world (not the World Location lore entries)."""
        return [i for i in self.pickups(key) if not i["glob"]]

    def unplaced(self, key):
        """True for a type none of whose entries has a world position (World Locations)."""
        return bool(self.pickups(key)) and not self.placed(key)

    def region_counts(self, key, placed_only=False):
        return collections.Counter(i["r"] for i in (self.placed(key) if placed_only else self.pickups(key)))

    def regions(self, key):
        rc = self.region_counts(key)
        return [r for r in REGION_KEYS if rc.get(r)]

    def dlc_trees(self, key):
        """[(challenge, expansion name)] for the challenges counting `key` that belong to an expansion's tree."""
        return [(ch, self.tree_dlc[tree["name"]]) for tree, ch in self.challenges.get(key, [])
                if self.tree_dlc.get(tree["name"])]

    def _challenges(self, gd):
        """sub key -> [(tree, challenge)] for the challenges whose tiers name the collectible."""
        out = collections.defaultdict(list)
        for tree in gd["challenges"]:
            for ch in tree["challenges"]:
                text = " ".join(t["desc"] for t in ch["tiers"]).lower()
                for key, phrase in CHALLENGE_PHRASE.items():
                    if phrase.lower() in text:
                        out[key].append((tree, ch))
        return out

    def counted_by(self, ch):
        """Every type a challenge counts."""
        return [s["key"] for s in self.subs if any(c["key"] == ch["key"] for _, c in self.challenges.get(s["key"], []))]


def tree_dlc(site, tree):
    """The expansion a DLC challenge tree belongs to, or None for a base game tree. gamedata only flags a tree as
    DLC, so the name comes from what its tiers quote: mission names (SCOUT's Road Trip asks for "Tidal Wave",
    "Test Run" and "New Cycles", all FNIX Rising missions in missions.json; HIMFJÄLL's The Good Fight asks for
    Alpine Unrest missions) and pack names (Tug Of War: 'Side Missions of the "FNIX Rising" expansion')."""
    if not tree["dlc"]:
        return None
    md = site.data("missions")
    pack_name = {p["key"]: p["name"] for p in md["packs"]}
    by_pack_name = {norm(n): k for k, n in pack_name.items()}
    mission_pack = {norm(x["name"]): x["pack"] for x in md["missions"]}
    votes = collections.Counter()
    for ch in tree["challenges"]:
        for t in ch["tiers"]:
            for quoted in re.findall(r'"([^"]+)"', t["desc"]):
                pk = mission_pack.get(norm(quoted)) or by_pack_name.get(norm(quoted))
                if pk and pk != "base":
                    votes[pk] += 1
    if not votes:
        site.warn(f"collectibles: no expansion found for DLC challenge tree {tree['name']}")
        return "DLC"
    return pack_name[votes.most_common(1)[0][0]]


def dlc_badge(site, name):
    """A DLC tag that links to the DLC page."""
    url = site.url("dlc", name)
    return f'<a href="{url}">{tag(name, "dlc")}</a>' if url else tag(name, "dlc")


_MODEL = None


def model(site):
    global _MODEL
    if _MODEL is None or _MODEL.site is not site:
        _MODEL = Model(site)
        _MODEL.site = site
    return _MODEL


# ---------------------------------------------------------------------------------------------------------------
def collect(site):
    m = model(site)
    for s in m.subs:
        n = len(m.pickups(s["key"]))
        count = f"{n} entries (no map position)" if m.unplaced(s["key"]) else f"{n} on the map"
        site.register("collectible-type", s["key"], page_path(s["key"]), s["name"], icon="map/" + s["icon"],
                      aliases=[s["name"]], desc=f"{GROUP_ONE[s['main']]} · {count}. " + strip_tags(BLURB.get(s["key"], "")),
                      keywords=f"collectible collectable {s['key']} {s['main']} location map")
    k = site.data("keys")
    anchors = key_anchors(k)
    for e in k["items"]:
        # "Storage key" and "Storage Key" are two different keys: the second one is registered by internal name
        key = e["n"] if not site.find("key", e["n"]) else e["r"]
        site.register("key", key, f"world/keys.html#{anchors[e['h']]}", e["n"], icon=f"img/keys/{e['i']}",
                      aliases=[e["r"], str(e["h"])], desc=f"{section_name(k, e['s'])} · {strip_desc(e['d'])}",
                      keywords=f"key {e['r']} {e['s']}")


def key_anchors(k):
    """item hash -> the id of its row on keys.html, made from the name ('k-storage-key', 'k-storage-key-2')."""
    out, seen = {}, collections.Counter()
    for e in k["items"]:
        a = "k-" + slug(e["n"])
        seen[a] += 1
        out[e["h"]] = a if seen[a] == 1 else f"{a}-{seen[a]}"
    return out


def section_name(k, key):
    return next((s["name"] for s in k["sections"] if s["key"] == key), key)


def strip_desc(d):
    return re.sub(r"\s+", " ", d or "").strip()


def build(site):
    m = model(site)
    build_overview(site, m)
    keys = [s["key"] for s in m.subs]
    for i, key in enumerate(keys):
        build_type(site, m, key, keys[i - 1] if i else None, keys[i + 1] if i + 1 < len(keys) else None)
    build_keys(site)


# ---------------------------------------------------------------------------------------------------------------
# world/collectibles.html
# ---------------------------------------------------------------------------------------------------------------
def type_icon(site, s, cls="cic"):
    return site.img("map/" + s["icon"], cls=cls, alt="")


def region_cell(n, unplaced):
    if not n:
        return '<span class="dim" data-v="0">–</span>'
    if unplaced:     # the region of a World Location entry comes from its name, not from a position
        return f'<span class="dim" data-v="{n}" title="by name, not by position">{n}*</span>'
    return n


def overview_table(site, m):
    rows = []
    for s in m.subs:
        rc = m.region_counts(s["key"])
        rows.append([type_icon(site, s) + site.link("collectible-type", s["key"], s["name"]),
                     len(m.pickups(s["key"]))]
                    + [region_cell(rc.get(r), m.unplaced(s["key"])) for r in REGION_KEYS])
    tot = collections.Counter()
    for s in m.subs:
        tot.update(m.region_counts(s["key"], placed_only=True))
    rows.append(["<b>All types</b>", sum(len(m.pickups(s["key"])) for s in m.subs)]
                + [tot.get(r, 0) for r in REGION_KEYS])
    heads = ["Type", "Total"] + [REGION_SHORT[r] for r in REGION_KEYS]
    return table(heads, rows, cls="compact ctypes", num=set(range(1, 2 + len(REGION_KEYS))))


def type_cards(site, m, main):
    items = []
    for s in m.subs:
        if s["main"] != main:
            continue
        p = m.pickups(s["key"])
        regs = m.regions(s["key"])
        where = REGION_SHORT[regs[0]] if len(regs) == 1 else f"{len(regs)} regions"
        if m.unplaced(s["key"]):
            where = "No map position"
        items.append({"href": "~/" + page_path(s["key"]), "title": s["name"], "img": "~/map/" + s["icon"],
                      "tag": str(len(p)), "color": "#8a6d1f" if any(r in REGION_DLC for r in regs) else "#5f4258",
                      "sub": f"<b>{esc(where)}</b><br>{esc(first_sentence(BLURB.get(s['key'], '')))}"})
    return cards(items, cls="small ccards")


def first_sentence(html):
    text = strip_tags(html)
    return re.split(r"(?<=\.)\s", text, maxsplit=1)[0]


def single_region_types(m):
    """[(sub, region)] for the types whose pickups all lie in one region."""
    out = []
    for s in m.subs:
        rc = m.region_counts(s["key"], placed_only=True)
        if len(rc) == 1:
            out.append((s, next(iter(rc))))
    return out


def photo_coverage(m):
    """(names of the safehouses that have a house photo, [safehouse markers without one])."""
    have = {i["safehouse"]["n"] for i in m.pickups("safehousehints") if i.get("safehouse")}
    return have, [s for s in m.safehouses if s["n"] not in have]


def photo_sentence(site, m):
    """How many safehouses have a house photo, from the data."""
    have, missing = photo_coverage(m)
    mainland = [s for s in m.safehouses if s["r"] not in REGION_DLC]
    miss_main = [s for s in missing if s["r"] not in REGION_DLC]
    miss_dlc = [s for s in missing if s["r"] in REGION_DLC]
    text = f"{len(mainland) - len(miss_main)} of the {len(mainland)} mainland safehouses have a house photo"
    if miss_dlc:
        text += f"; the {len(miss_dlc)} safehouses on Himfjäll have none in the files"
    return text + (f" (the {site.link('collectible-type', 'safehousehints', 'House photos')} page lists the ones "
                   f"without)." if miss_main else ".")


def all_collectibles_map(m):
    return maplink(show=[s["key"] for s in m.subs if s["main"] == "collectibles" and not m.unplaced(s["key"])])


def build_overview(site, m):
    total = sum(len(m.pickups(s["key"])) for s in m.subs)
    n_placed = sum(len(m.placed(s["key"])) for s in m.subs)
    unplaced = [s for s in m.subs if m.unplaced(s["key"])]
    n_col = sum(len(m.pickups(s["key"])) for s in m.subs if s["main"] == "collectibles")
    n_types = sum(1 for s in m.subs if s["main"] == "collectibles")
    n_group = {g: sum(len(m.pickups(s["key"])) for s in m.subs if s["main"] == g) for g in OWN_MAINS}
    body = []

    for main in OWN_MAINS:
        body.append(bar(GROUP_LABEL[main], right=plural(n_group[main], "pickup")))
        if main == "collectibles":
            n_ch = sum(1 for s in m.subs if s["main"] == main and m.challenges.get(s["key"]))
            body.append(f"<p>The {n_types} collectible series. The game counts them in its <i>Collectables "
                        f"found</i> statistic, and {n_ch} of the series also count for a challenge.</p>")
        elif main == "schematics":
            body.append("<p>Each of these pickups gives points of one schematic currency, which you spend in that "
                        "crafting tree. They don't unlock a particular schematic.</p>")
        else:
            body.append(f"<p>{photo_sentence(site, m)}</p>")
        body.append(type_cards(site, m, main))

    body.append(bar("By region"))
    body.append("<p>How many pickups of each type lie in each region (by the region borders of the map; Himfjäll is "
                "the Alpine Unrest island). Click a header to sort.</p>")
    body.append(overview_table(site, m))
    if unplaced:
        body.append('<p class="dim"><small>* ' + and_list(
            site.link("collectible-type", s["key"], s["name"]) for s in unplaced)
            + " have no position in the world: their region comes from their name, and the <b>All types</b> row "
              "leaves them out.</small></p>")

    ch_table = challenge_overview(site, m)
    if ch_table:
        body.append(bar("Challenges"))
        body.append("<p>The challenges that count collectibles. Each type's page has the tiers.</p>")
        body.append(ch_table)

    body.append(bar("Tips"))
    body.append("<ul>" + "".join(f"<li>{t}</li>" for t in overview_tips(site, m)) + "</ul>")
    copies = [i for i in m.items.get("audiologs", []) if i["copy"]]
    if copies:
        body.append(note(
            f"The map data has {len(m.items['audiologs'])} audio log markers, but there are only "
            f"{len(m.pickups('audiologs'))} audio logs: every log is also placed in a dialogue scene at one shared "
            f"spot. Lists that count {len(m.items['audiologs'])} audio logs count each one twice.",
            "fix", "Audio log count"))

    box = infobox("Collectibles", [
        ("Collectible series", n_types),
        ("Collectibles", n_col),
        ("Schematic point pickups", n_group["schematics"]),
        ("House photos", n_group["housephotos"]),
        ("All entries", total),
        ("With a map position", n_placed),
        ("Map", f'<a href="{all_collectibles_map(m)}">All collectibles on the map</a>'),
        ("Keys & barcodes", f'<a href="~/world/keys.html">{len(site.data("keys")["items"])} items</a>'),
    ], image="~/map/" + m.sub["gnomes"]["icon"] if site.has_file("map/" + m.sub["gnomes"]["icon"]) else None,
        cls="cbox")
    lead = (f"<p>Generation Zero hides <b>{n_col} collectibles</b> in {n_types} series around Östertörn and "
            f"Himfjäll, from garden gnomes and Dala horses to mixtapes, machine blueprints and audio logs. This "
            f"section also covers the <b>schematic point</b> pickups and the <b>house photos</b> of the safehouses: "
            f"{total} entries in all, {n_placed} of them with an exact position. Pick a type for its map and the "
            f"place of every pickup.</p>")
    site.page("world/collectibles.html", "Collectibles", "\n".join(body), "world", sub="collectibles", lead=lead,
              head_extra=CSS, infobox_html=box,
              desc=f"All {total} collectibles, schematic point pickups and house photos of Generation Zero: counts "
                   f"per region, maps and challenges.",
              search={"k": "World", "w": "collectibles collectables gnomes dalahast mixtapes"})


def overview_tips(site, m):
    """Practical tips worked out from the counts. Only pickups with a world position count."""
    tips = []
    regs = collections.Counter()
    for s in m.subs:
        if s["main"] == "collectibles":
            regs.update(m.region_counts(s["key"], placed_only=True))
    n = sum(regs.values())
    best = regs.most_common(1)[0]
    tips.append(f"Counting only the collectible series, {site.link('region', best[0])} holds the most: {best[1]} "
                f"of the {n} collectibles with a map position.")
    one = single_region_types(m)
    if one:
        tips.append("Some series stay in one region, so you can finish them in one trip: " + and_list(
            f"{site.link('collectible-type', s['key'], s['name'])} ({site.link('region', r, REGION_SHORT[r])})"
            for s, r in one) + ".")
    tips.append(f'The <a href="{all_collectibles_map(m)}">interactive map</a> shows every collectible at once; '
                f"each type page links to a map with only that type.")
    dlc_ch = {(ch["name"], d) for s in m.subs for ch, d in m.dlc_trees(s["key"])
              if not any(r in REGION_DLC for r in m.region_counts(s["key"]))}
    for name, d in sorted(dlc_ch):
        tips.append(f"{site.link('challenge', name)} counts pickups that are on the base game map, but the "
                    f"challenge itself is part of {site.link('dlc', d)}.")
    tips.append("House photos sit inside their safehouse, so you pick them up as you unlock safehouses.")
    return tips


def tree_cell(site, m, tree):
    d = m.tree_dlc.get(tree["name"])
    return esc(tree["name"].title()) + (" " + dlc_badge(site, d) if d else "")


def challenge_overview(site, m):
    """One row per challenge that counts collectibles (the tiers are on the type pages)."""
    rows, seen = [], set()
    for s in m.subs:
        for tree, ch in m.challenges.get(s["key"], []):
            if ch["key"] in seen:
                continue
            seen.add(ch["key"])
            what = " + ".join(site.link("collectible-type", k, m.sub[k]["name"]) for k in m.counted_by(ch))
            rows.append([site.link("challenge", ch["name"]), tree_cell(site, m, tree), what, len(ch["tiers"]),
                         ch["tiers"][-1]["req"], esc(ch["tiers"][-1]["title"])])
    if not rows:
        return ""
    return table(["Challenge", "Tree", "Counts", "Tiers", "Last tier", "Last title"], rows, cls="compact",
                 num={3, 4})


def challenge_panel(site, m, key):
    """Side panel of a type page: the challenge(s) that count it, tier by tier."""
    out = []
    for tree, ch in m.challenges.get(key, []):
        other = [k for k in m.counted_by(ch) if k != key]
        head = f'<p class="chead2"><b>{site.link("challenge", ch["name"])}</b><br><span class="dim">' \
               f'{tree_cell(site, m, tree)} challenge tree</span></p>'
        if other:
            head += "<p>Counts these together with " + and_list(
                site.link("collectible-type", k, m.sub[k]["name"]) for k in other) + ".</p>"
        rows = [[n, f'<span data-v="{t["req"]}">{t["start"]} → {t["req"]}</span>', esc(t["title"])]
                for n, t in enumerate(ch["tiers"], 1)]
        out.append(head + table(["Tier", "Collect", "Title"], rows, cls="compact ctiers", sortable=False))
    if not out:
        return ""
    return panel("Challenge", "".join(out), cls="cchal")


def region_panel(site, m, key):
    """Side panel: pickups per region, each with a map link showing only that type in that region."""
    rc = m.region_counts(key)
    regs = m.regions(key)
    if len(regs) < 2 or m.unplaced(key):
        return ""
    body = kv([(REGION_SHORT[r], f'<a href="{maplink(show=[key], region=[r])}" title="Show on the map">{rc[r]}</a>')
               for r in regs])
    return panel("By region", body + '<p class="dim"><small>Click a number for the map of that region.</small></p>',
                 cls="cregs")


# ---------------------------------------------------------------------------------------------------------------
# a static map of many points: the interactive minimap can't zoom out far enough to show a type that is spread
# over the whole world, so this draws the map tiles and numbered pins with plain HTML (no script), cropped to the
# points. Positions are fractions of the full map: world x/z in metres -> level-3 pixel 8192 + x / 2 of 16384.
# ---------------------------------------------------------------------------------------------------------------
MAP_PX = 16384
MANY_PINS = 25      # more pins than this overlap at phone width, so they are drawn as plain dots there


def map_frac(x, z):
    return (8192 + x / 2) / MAP_PX, (8192 + z / 2) / MAP_PX


def _span(lo, hi, want):
    """Grow [lo, hi] around its middle to at least `want`, kept inside 0..1."""
    if hi - lo < want:
        mid = (lo + hi) / 2
        lo, hi = mid - want / 2, mid + want / 2
    if lo < 0:
        lo, hi = 0, hi - lo
    if hi > 1:
        lo, hi = lo - (hi - 1), 1
    return max(0.0, lo), min(1.0, hi)


def static_map(site, pts, href):
    """pts: [(x, z, label, title, anchor)]; href: the 'Open the full map' link (with the page's filters)."""
    if not pts:
        return ""
    us, vs = zip(*(map_frac(p[0], p[1]) for p in pts))
    pad = 0.025
    u0, u1 = _span(min(us) - pad, max(us) + pad, 0.045)
    v0, v1 = _span(min(vs) - pad, max(vs) + pad, 0.045)
    # keep the box between 5:4 and 11:5 (width:height) so it neither towers over the page nor becomes a strip
    su, sv = u1 - u0, v1 - v0
    if su < 1.25 * sv:
        u0, u1 = _span(u0, u1, 1.25 * sv)
    elif su > 2.2 * sv:
        v0, v1 = _span(v0, v1, su / 2.2)
    su, sv = u1 - u0, v1 - v0
    level = 1 if su > 0.3 else 2 if su > 0.12 else 3
    n = {1: 2, 2: 4, 3: 8}[level]
    tiles = []
    for i in range(int(u0 * n), min(n - 1, int(u1 * n)) + 1):
        for j in range(int(v0 * n), min(n - 1, int(v1 * n)) + 1):
            path = f"map/map/tiles/{level}/{i}_{j}.webp"
            if site.has_file(path):
                tiles.append(f'<img src="~/{path}" alt="" style="left:{i / n * 100:.3f}%;'
                             f'top:{j / n * 100:.3f}%;width:{100 / n:.3f}%;height:{100 / n:.3f}%">')
    inner = (f'<div class="smtiles" style="width:{100 / su:.3f}%;height:{100 / sv:.3f}%;'
             f'left:{-u0 / su * 100:.3f}%;top:{-v0 / sv * 100:.3f}%">{"".join(tiles)}</div>')
    pins = []
    for (x, z, label, title, anchor), u, v in zip(pts, us, vs):
        el = "a" if anchor else "span"
        ref = f' href="#{anchor}"' if anchor else ""
        pins.append(f'<{el} class="spin"{ref} title="{esc(title)}" style="left:{(u - u0) / su * 100:.3f}%;'
                    f'top:{(v - v0) / sv * 100:.3f}%">{esc(label)}</{el}>')
    many = " many" if len(pts) > MANY_PINS else ""     # collectibles.css turns these pins into dots on phones
    # the width is also capped so the map's height stays within three quarters of the window
    return (f'<div class="smap{many}" style="aspect-ratio:{su / sv:.4f};max-width:min(1100px,calc(75vh * '
            f'{su / sv:.4f}))">{inner}{"".join(pins)}'
            f'<a class="mmopen" href="{href}">Open the full map</a></div>')


# ---------------------------------------------------------------------------------------------------------------
# world/collectibles/<key>.html
# ---------------------------------------------------------------------------------------------------------------
def near_cell(site, it):
    if not it["loc"]:
        return '<span class="dim">–</span>'
    d = it["ld"]
    rel = "at" if d < 40 else f"{d:,.0f} m {compass(it['loc'], it)} of"
    return f'<span data-v="{d:.0f}"><span class="dim">{rel}</span> {site.link("location", it["loc"]["name"])}</span>'


def map_cell(key, it):
    """The pickup's coordinates, linked to the interactive map with only this type shown and its popup open."""
    href = maplink(show=[key], at=(it["x"], it["z"]), focus=it["n"])
    return (f'<a class="mono" href="{href}" title="Show {esc(it["n"])} on the map" data-v="{it["x"]:.0f}">'
            f'{it["x"]:.0f}, {it["z"]:.0f}</a>', round(it["x"]))


def item_name(site, key, it):
    """The name cell, with a link where the item is also something else on the wiki."""
    n = esc(it["n"])
    if key == "videotapes":
        title = it["n"].split(" - ", 1)[-1]
        if site.find("vanity", title):
            n += f'<br><small class="dim">dance emote {site.link("vanity", title)}</small>'
    return n


def machine_of(name):
    """'Soviet Blueprint - Lynx Class A' -> ('Lynx', 'Class A', 'Soviet'); 'Rival Blueprint - Reaper (Tank)'."""
    m = re.match(r"^(?:(Soviet|Rival) )?Blueprint - (.+?)(?: (Class [A-Z]))?$", name)
    if not m:
        return None, None, None
    kind, rest, cls = m.groups()
    machine = re.sub(r"\s*\(.*\)$", "", rest)
    return machine, cls or "", kind or "Swedish"


def extra_columns(site, m, key):
    """Type-specific (headers, cell function) added to the item table."""
    if key == "blueprints":
        def cells(it):
            mach, cls, kind = machine_of(it["n"])
            return [site.link("machine", mach, mach) if mach else "", esc(cls.replace("Class ", "")), esc(kind)]
        return ["Machine", "Class", "Faction"], cells
    if key == "safehousehints":
        def cells(it):
            sh = it.get("safehouse")
            return [site.link("safehouse", sh["n"]) + f' <span class="dim">({it["sd"]:.0f} m)</span>' if sh else "–"]
        return ["Safehouse"], cells
    return [], None


def item_rows(site, m, key, items, with_region):
    heads, extra = extra_columns(site, m, key)
    unplaced = m.unplaced(key)
    cols = ["#", "Name"] + heads + (["Region"] if with_region else []) + \
        ([] if unplaced else ["Nearest location", "Map (x, z)"])
    rows = []
    for it in items:
        cells = [it["num"], item_name(site, key, it)] + (extra(it) if extra else [])
        if with_region:
            cells.append(region_link(site, it["r"]))
        if not unplaced:
            cells += [near_cell(site, it), map_cell(key, it)]
        rows.append(cells)
    html = table(cols, rows, cls="compact citems", num={0})
    # give each row its filter tags (region) and an id to link to (the pins of the map)
    parts = html.split("<tr>")
    head, body_rows = parts[:2], parts[2:]
    tagged = [f'<tr id="i{it["num"]}" data-f="{it["r"]}">' + r for it, r in zip(items, body_rows)]
    return "<tr>".join(head) + "".join(tagged)


def item_list(site, m, key):
    """The list of pickups: one table with region chips, or one closed fold per region for the long lists."""
    items = m.pickups(key)
    regs = m.regions(key)
    out = []
    if len(items) > FOLD_OVER and len(regs) > 1:
        out.append('<div class="filterbar" data-for="items"><input placeholder="Filter by name or place...">'
                   '<span class="count"></span></div><div class="foldall" data-for="items"></div>')
        folds = []
        for r in regs:
            its = [i for i in items if i["r"] == r]
            link = (f'<p class="foldmap"><a href="{maplink(show=[key], region=[r])}">Show these {len(its)} on the '
                    f'map</a> · {site.link("region", r, "About " + REGION_SHORT[r])}</p>')
            folds.append(fold(REGION_NAME[r], link + item_rows(site, m, key, its, False), level=3,
                              id=f"r-{r}", right=str(len(its))))
        out.append(f'<div id="items">{"".join(folds)}</div>')
        return "".join(out)
    if len(items) > 8:
        out.append('<div class="filterbar" data-for="items"><input placeholder="Filter by name or place...">')
        if len(regs) > 1:
            out.append('<button class="chip on" data-g="r" data-f="*">All</button>')
            out += [f'<button class="chip" data-g="r" data-f="{r}">{esc(REGION_SHORT[r])}</button>' for r in regs]
        out.append('<span class="count"></span></div>')
    out.append(f'<div id="items">{item_rows(site, m, key, items, len(regs) > 1 or m.unplaced(key))}</div>')
    return "".join(out)


def map_block(site, m, key):
    pts = [(i["x"], i["z"], str(i["num"]), f'{i["num"]}. {i["n"]}', f'i{i["num"]}') for i in m.placed(key)]
    return static_map(site, pts, maplink(show=[key]))


def type_lead(site, m, key):
    p = m.pickups(key)
    rc = m.region_counts(key)
    regs = m.regions(key)
    if m.unplaced(key):
        where = f"There are <b>{len(p)}</b>, one per mainland region by name."
    elif len(regs) == 1:
        where = f"All <b>{len(p)}</b> are in {site.link('region', regs[0], REGION_SHORT[regs[0]])}."
    else:
        where = f"The game files place <b>{len(p)}</b> across {len(regs)} regions, " + most_text(site, rc) + "."
    dlc = ""
    if any(r in REGION_DLC for r in regs) and "Alpine Unrest" not in BLURB.get(key, ""):
        dlc = f" Himfjäll is the island of the {site.link('dlc', 'Alpine Unrest')} expansion."
    elif m.dlc_trees(key):
        ch, d = m.dlc_trees(key)[0]
        dlc = (f" They lie on the base game map, but the challenge that counts them, "
               f"{site.link('challenge', ch['name'])}, is part of the {site.link('dlc', d)} expansion.")
    return f"<p>{BLURB.get(key, '')} {where}{dlc}</p>"


def most_text(site, rc):
    """'the most in South Coast and North Coast (4 each)', or 'one in each' / '3 in each' when all are equal."""
    top_n = max(rc.values())
    top = [r for r in REGION_KEYS if rc.get(r) == top_n]
    if len(top) == len(rc):
        return "one in each" if top_n == 1 else f"{top_n} in each"
    names = and_list(site.link("region", r, REGION_SHORT[r]) for r in top)
    return f"the most in {names} ({top_n}{' each' if len(top) > 1 else ''})"


def build_type(site, m, key, prev_key, next_key):
    s = m.sub[key]
    p = m.pickups(key)
    body = []
    mp = map_block(site, m, key)
    if mp:
        body.append(bar("Map", right=plural(len(p), "pickup")))
        body.append("<p>The numbers are the <b>#</b> of the list below: hover a pin for its name, click it to jump "
                    "to it. <b>Open the full map</b> shows only this type on the interactive map; the coordinates "
                    "in the list open it on that pickup.</p>")
        body.append(mp)
    elif key == "worldlocations":
        body.append(note(f"All {len(p)} World Location entries sit at the same spot in a global scene, not in the "
                         "world, so there is nothing to show on a map. Maps that put a pin for them far out west are "
                         "showing that placeholder.", "warn"))

    title = f"All {s['name'].lower()}"
    if len(p) > FOLD_OVER and len(m.regions(key)) > 1:
        body.append(bar(title, right="by region"))
        body.append("<p>One section per region; type in the box to search all of them. <b>Nearest location</b> is "
                    "the closest named place and how far and in which direction the pickup lies from it.</p>")
    else:
        body.append(bar(title, right=plural(len(p), "entry", "entries") if m.unplaced(key) else ""))
        if not m.unplaced(key):
            body.append("<p><b>Nearest location</b> is the closest named place and how far and in which direction "
                        "the pickup lies from it. Click a header to sort.</p>")
    body.append(item_list(site, m, key))
    if key == "audiologs":
        body.append(note(
            f"The map data has {len(m.items[key])} audio log markers for these {len(p)} logs: every audio log also "
            "exists in a dialogue scene, all at one shared spot. Only the real pickups are listed here.", "fix"))

    body.extend(type_extras(site, m, key))
    body.append(type_nav(site, m, prev_key, next_key))

    box = infobox(s["name"], type_facts(site, m, key),
                  image="~/map/" + s["icon"] if site.has_file("map/" + s["icon"]) else None, cls="cbox")
    site.page(page_path(key), s["name"], "\n".join(body), "world", sub="collectibles",
              crumbs=[("Collectibles", "~/world/collectibles.html")], kind=f"World · {GROUP_ONE[s['main']]}",
              lead=type_lead(site, m, key), infobox_html=box, head_extra=CSS,
              side=[challenge_panel(site, m, key), region_panel(site, m, key)],
              desc=f"All {len(p)} {s['name']} of Generation Zero with map, region and nearest location.")


def type_facts(site, m, key):
    """The (label, html) rows of a type's infobox."""
    s = m.sub[key]
    p = m.pickups(key)
    regs = m.regions(key)
    if any(r in REGION_DLC for r in regs):
        dlc = dlc_badge(site, REGION_DLC[next(r for r in regs if r in REGION_DLC)])
    else:
        # on the base game map, but the challenge that counts them may belong to an expansion
        trees = sorted({d for _, d in m.dlc_trees(key)})
        dlc = ("Base game map" + "".join(f"<br>challenge: {dlc_badge(site, d)}" for d in trees)) if trees \
            else "Base game"
    regions = (site.link("region", regs[0], REGION_SHORT[regs[0]]) if len(regs) == 1 else
               f"{len(regs)} regions")
    return [
        ("Group", f'<a href="~/world/collectibles.html#{slug(GROUP_LABEL[s["main"]])}">{esc(GROUP_ONE[s["main"]])}</a>'),
        ("Entries" if m.unplaced(key) else "Pickups", len(p)),
        ("Map markers", len(m.items[key]) if len(m.items[key]) != len(p) else None),
        ("Regions" if len(regs) > 1 else "Region", regions),
        ("Content", dlc),
        ("Map", None if m.unplaced(key) else f'<a href="{maplink(show=[key])}">Show all on the map</a>'),
    ]


def type_nav(site, m, prev_key, next_key):
    out = ['<div class="pnav cnav">']
    out.append(f'<a href="~/{page_path(prev_key)}">← {esc(m.sub[prev_key]["name"])}</a>' if prev_key else "<span></span>")
    out.append('<a href="~/world/collectibles.html">All collectibles</a>')
    out.append(f'<a href="~/{page_path(next_key)}">{esc(m.sub[next_key]["name"])} →</a>' if next_key else "<span></span>")
    return "".join(out) + "</div>"


# ---------------------------------------------------------------------------------------------------------------
# type-specific sections
# ---------------------------------------------------------------------------------------------------------------
def type_extras(site, m, key):
    if key.startswith("sch_"):
        return schematic_extras(site, m, key)
    if key == "safehousehints":
        return photo_extras(site, m)
    if key == "blueprints":
        return blueprint_extras(site, m)
    if key == "gnomes":
        return gnome_extras(site)
    return []


def schematics_link(site, text):
    return site.link("schematic", "Schematics", text) if site.find("schematic", "Schematics") else \
        f'<a href="~/items/schematics.html">{esc(text)}</a>'


def schematic_extras(site, m, key):
    cur_key = key[4:]
    gd = site.data("gamedata")
    cur = next((c for c in gd["schematics"] if c["key"] == cur_key), None)
    tree = [i for i in site.data("schematics")["items"] if i["t"] == cur_key]
    by_name = collections.OrderedDict()
    for i in tree:
        by_name.setdefault(i["n"], []).append(i)
    rows = [[site.link("schematic", name, name), len(ranks), sum(r["c"] for r in ranks)] for name, ranks in by_name.items()]
    total = sum(r[2] for r in rows)
    cname = esc(cur["name"]) if cur else "points"
    out = []
    if cur:
        icon = site.img(f"img/currencies/{cur_key}.png", cls="cur")
        out.append(f"<p>{icon}<b>{cname}</b>. The game's own text: <i>{esc(cur['earn'])}</i></p>")
        if cur_key == "apparel" and "Rival" in cur["earn"]:
            out.append(note(f"The game's text only names Rivals, but the files also place these {len(m.pickups(key))} "
                            f"pickups in the world.", "info"))
    out.append(f"<p>The {esc(cur_key)} tree has {len(by_name)} schematics ({len(tree)} ranks); buying every rank "
               f"costs <b>{fmt(total)}</b> {cname}. See {schematics_link(site, 'the schematics page')} for the cost "
               f"of each rank, recipes and prerequisites.</p>")
    out.append(table(["Schematic", "Ranks", "Total cost"], rows, cls="compact", num={1, 2}))
    return [fold("What the points buy", "".join(out), right=plural(len(by_name), "schematic"))]


def photo_extras(site, m):
    have, missing = photo_coverage(m)
    by_r = collections.defaultdict(list)
    for s in missing:
        by_r[s["r"]].append(s)
    out = [f"<p>{len(m.safehouses)} safehouses have a marker on the map and {len(have)} of them have a house photo "
           f"within {PHOTO_AT} m. These {len(missing)} have none in the files:</p>"]
    rows = [[region_link(site, r),
             ", ".join(site.link("safehouse", s["n"]) for s in sorted(by_r[r], key=lambda s: norm(s["n"])))]
            for r in REGION_KEYS if by_r.get(r)]
    out.append(table(["Region", "Safehouses"], rows, cls="compact", sortable=False))
    dup = collections.Counter(i["n"] for i in m.pickups("safehousehints"))
    dups = [n for n, c in dup.items() if c > 1]
    if dups:
        out.append(note("Some photos share a name although they are different pickups at different safehouses: "
                        + ", ".join(f"<i>{esc(n)}</i> ({dup[n]}×)" for n in dups) + ". Use the safehouse column to "
                        "tell them apart.", "info"))
    return [fold("Safehouses without a photo", "".join(out), right=str(len(missing)))]


def blueprint_extras(site, m):
    by = collections.OrderedDict()
    for it in m.pickups("blueprints"):
        mach, cls, kind = machine_of(it["n"])
        if mach:
            by.setdefault((kind, mach), []).append((cls, it))
    rows = []
    for (kind, mach), lst in by.items():
        rows.append([site.link("machine", mach, mach), esc(kind),
                     " ".join(f'<a href="#i{it["num"]}">{esc(cls.replace("Class ", "") or "Rival")}</a>'
                              for cls, it in lst), len(lst)])
    body = ("<p>Which blueprints each machine has. The letters are the class letters in the blueprint names; click "
            "one to jump to it. <b>Faction</b> follows the blueprint name: <i>Soviet Blueprint</i> and <i>Rival "
            "Blueprint</i> as named, the rest are the original (Swedish) machines.</p>"
            + table(["Machine", "Faction", "Blueprints", "Count"], rows, cls="compact", num={3}))
    return [fold("By machine", body, right=plural(len(rows), "machine"))]


def gnome_extras(site):
    masks = [v for v in site.data("vanity")["items"] if v["r"].startswith("char_part_head_gnome_reward")]
    if not masks:
        return []
    kind = lambda v: "apparel" if site.find("apparel", v["n"]) else "vanity"
    link = lambda v: site.link(kind(v), v["n"])
    body = (f"<p>The apparel list has {len(masks)} gnome masks that the files name as gnome rewards, so they are "
            f"most likely the prize for the gnome hunt; the data doesn't say how many gnomes unlock which one.</p>")
    urls = {site.url(kind(v), v["n"]) for v in masks}
    if len(urls) == 1 and None not in urls:
        # the apparel page lists the colours as variants of one mask: one link, the variants named
        base = min(masks, key=lambda v: len(v["n"]))
        variants = [v["n"].split(", ", 1)[1] for v in masks if ", " in v["n"]]
        body += (f"<p>{link(base)}, plain and in {len(variants)} variants: "
                 f"{esc(and_list(variants))}.</p>")
    else:
        body += "<ul>" + "".join(f"<li>{link(v)}</li>" for v in masks) + "</ul>"
    return [fold("Gnome masks", body, right=str(len(masks)))]


# ---------------------------------------------------------------------------------------------------------------
# world/keys.html
# ---------------------------------------------------------------------------------------------------------------
# Missions whose text names the key, by internal key name: (mission name, words of the mission text that show it).
# The build checks that the words are in that mission's summary, description or steps, and quotes that line.
KEY_MISSIONS = {
    "key_bunkerkey_hermelinen": [("Warboard - Hermelinen Bunker", "entry barcode")],
    "key_bunkerkey_kaseberg": [("Warboard - Minken Bunker", "entry barcode")],
    "key_bunkerkey_marden": [("Warboard - Mården Bunker", "entry barcode")],
    "key_bunkerkey_skvadern": [("Warboard - Skvadern Bunker", "entry barcode")],
    "key_bunkerkey_sorken": [("Warboard - Sorken Bunker", "entry barcode")],
    "key_bunkerkey_uttern": [("Warboard - Uttern Bunker", "entry barcode")],
    "key_bunkerkey_vesslan": [("The Home Team", "barcode keycards to unlock")],
    "key_bunkerkey_foav2": [("Behind the Curtain", "FOA bunker doors")],
    "key_bunkerkey_foa": [("Behind the Curtain", "FOA 53 lab")],
    "key_bunkerkey_evilfoa": [("The Hellmouth", "keycard to Bergfinken")],
    "key_doorkey_snusskey": [("A Wrench in the Works", "prototype lab")],
    "key_doorkey_veronika": [("The Girl Who Cried Wolf", "key to Veronika's study")],
    "key_doorkey_ingrid": [("Flying Objects", "spare key")],
    "key_doorkey_vonulmer": [("Science of Deduction", "keys to his house")],
    "key_doorkey_vonulmer2": [("Empty Spaces", "keycard to Von Ulmer's study")],
    "key_doorkey_wm22b": [("Colonists", "Open the barn")],
    "key_doorkey_wm17": [("Hogging Supplies", "stables")],
    "key_doorkey_wm39": [("Emergency Supplies", "old man Björn")],
    # Woodcutter: "Find the lumberyard manager's office" at the lumberyard near Lerberget; this key opens "the
    # office cabin at the Hjortqvarns Sågverk (sawmill) lumberyard", 373 m from Lerberget. (The unflagged
    # key_doorkey_lumbercamp "Office key" has nothing in its text that ties it to the mission.)
    "key_doorkey_wm27a": [("Woodcutter", "lumberyard manager's office")],
    "key_doorkey_wm19": [("Total Defense", "barn at Östra Mark")],
    "exp02_mm100_key": [("Good Night", "vision module")],
    "fnix_tracking_device": [("Death from above", "tracking device")],
    "key_rivkey_key01": [("Piece by Piece", "armor")],
    "key_rivkey_key02": [("Piece by Piece", "armor")],
    "key_rivkey_key03": [("Piece by Piece", "armor")],
    "exp02_sm090_ammo": [("Fuel to the Fire", "convoy")],
    "exp02_sm080_document": [("The Hatches", "dumping station")],
    "exp02_sm080_rope": [("The Hatches", "dumping station")],
    "exp02_sm080_log": [("The Hatches", "dumping station")],
}

KEY_NOTE = {
    "barcodes": "Each command bunker needs a full entry barcode, which the game splits into pieces: you can hold "
                "<b>{a}</b> pieces of each. You collect them from destroyed machines of that region (the Warboard "
                "missions say so), and a full barcode opens that region's command bunker.",
    "access": "Barcodes and keycards for research facilities and their labs.",
    "doors": "Ordinary keys to houses, barns and storage rooms. Several open a door a mission asks you to get "
             "through; for the rest no mission text names them.",
    "mission": "Items a mission hands out or asks for. Most of them belong to FNIX Rising.",
}
KNOWN_PACKS = {363622574: "FNIX Rising", 3565103498: "Alpine Unrest"}
LOOSE_KEYS = "loot_x_keys"      # loot.json sub of the keys that lie loose in the world


def pack_info(site, k):
    """pack hash -> (display html, short label, tag class, description). No hashes in the text."""
    sc = {i["h"]: i for i in site.data("schematics")["items"]}
    stock = {s["h"]: s for s in site.data("stock")["stock"]}
    out = {k["base_pack"]: (site.link("dlc", "Base game"), "Base game", "base", "the base game")}
    for p, hs in k["pack_items"].items():
        p = int(p)
        if p in KNOWN_PACKS:
            out[p] = (site.link("dlc", KNOWN_PACKS[p]), KNOWN_PACKS[p], "dlc", f"the {KNOWN_PACKS[p]} expansion")
            continue
        n_rank = sum(1 for h in hs if h in sc)                       # schematics.json has one entry per rank
        n_sch = len({sc[h]["n"] for h in hs if h in sc})
        n_mat = sum(1 for h in hs if stock.get(h, {}).get("g") == "materials")
        reg = site.find("pack", str(p))
        named = reg["title"] if reg and reg["title"] not in ("Item pack", "") else None
        if n_sch:
            label = named or "Apparel crafting pack"
            free = next((d.get("free") for d in site.data("steam")["dlc"] if named and norm(d["name"]) == norm(named)),
                        None)
            what = (f"the {'free ' if free else ''}{named} update" if named
                    else "a content pack the files don't name")
            desc = (f"{what}, which also holds the {n_sch} apparel schematics ({n_rank} ranks) and {n_mat} crafting "
                    f"materials")
        else:
            label = "Single-item pack"      # (its only item names it; a tag with the same words says nothing)
            desc = "a content pack of its own that holds only this item"
        out[p] = (site.link("pack", str(p), label), label, "base", desc)
    return out


def mission_refs(site, raw, missions):
    """[(mission, quoted line)] for KEY_MISSIONS[raw], checked against the mission text."""
    out = []
    for name, words in KEY_MISSIONS.get(raw, []):
        ms = missions.get(norm(name))
        if not ms:
            site.warn(f"collectibles: key {raw}: no mission {name!r}")
            continue
        lines = [s["name"] for s in ms["steps"]] + [ms.get("summary") or "", ms.get("description") or ""]
        line = next((l for l in lines if words.lower() in l.lower()), None)
        if not line:
            site.warn(f"collectibles: key {raw}: {words!r} not in mission {name!r}")
            continue
        line = re.sub(r"\s+", " ", line)
        if len(line) > 150:   # a description: quote the sentence with the words
            sent = next((s for s in re.split(r"(?<=[.!?])\s+", line) if words.lower() in s.lower()), line)
            line = sent[:150] + ("…" if len(sent) > 150 else "")
        out.append((ms, line))
    return out


def key_places(site):
    """Key name -> position of the keys that lie loose in the world (loot.json, sub loot_x_keys)."""
    lo = site.data("loot")
    idx = next((i for i, s in enumerate(lo["subs"]) if s["key"] == LOOSE_KEYS), None)
    out = {}
    for row in lo["items"]:
        if row[0] == idx:
            out[lo["names"][row[3]]] = {"x": row[1], "z": row[2], "r": lo["regions"][row[4]]}
    return out


def key_icon(site, e):
    for d in ("keys", "stock"):
        if site.has_file(f"img/{d}/{e['i']}"):
            return site.img(f"img/{d}/{e['i']}", cls="kic", alt="")
    return ""


def key_map_link(e, pl):
    return maplink(show=[LOOSE_KEYS], at=(pl["x"], pl["z"]), focus=e["n"])


def where_cell(site, e, pl, locs):
    loc = min(locs, key=lambda l: dist(l, pl))
    d = dist(loc, pl)
    rel = "at" if d < 40 else f"{d:,.0f} m {compass(loc, pl)} of"
    return (f'<span class="dim">{rel}</span> {site.link("location", loc["name"])}<br>'
            f'<a href="{key_map_link(e, pl)}">Show on the map</a>')


def key_table(site, k, items, packs, missions, places, locs, anchors):
    """One kind's table. The Missions / Where columns only appear when a key of the kind has them."""
    rows = []
    for e in items:
        refs = mission_refs(site, e["r"], missions)
        used = "".join(f'<div class="kref">{site.link("mission", ms["name"])}'
                       f'<span class="dim">“{esc(line)}”</span></div>' for ms, line in refs)
        pl = places.get(e["n"])
        tags = []
        if e["s"] == "barcodes":
            reg = re.search(r"for the (.+?) Region", e["d"])
            if reg:
                rk = next((key for key, name in REGIONS if norm(name) == norm(reg.group(1))), None)
                tags.append(site.link("region", rk, reg.group(1)) if rk else esc(reg.group(1)))
        p = packs.get(e["p"])
        if p and e["p"] != k["base_pack"]:
            e_ = site.find("dlc", p[1]) if p[2] == "dlc" else site.find("pack", str(e["p"]))
            tags.append(f'<a href="{"~/" + e_["path"] if e_ else "#packs"}">'
                        f'{tag(p[1], "dlc" if p[2] == "dlc" else "")}</a>')
        if e.get("m"):
            tags.append(tag("Mission item", "main"))
        name = (f'<span class="kcell">{key_icon(site, e)}<span class="kname"><b>{esc(e["n"])}</b>'
                f'{"<span>" + " ".join(tags) + "</span>" if tags else ""}</span></span>')
        rows.append((e, name, esc(strip_desc(e["d"])) or '<span class="dim">–</span>', used, pl))
    has_used = any(r[3] for r in rows)
    has_where = any(r[4] for r in rows)
    heads = ["Key", "Description"] + (["Missions that name it"] if has_used else []) + (["Where"] if has_where else [])
    cells = []
    for e, name, desc, used, pl in rows:
        c = [name, desc]
        if has_used:
            c.append(used or '<span class="dim">–</span>')
        if has_where:
            c.append(where_cell(site, e, pl, locs) if pl else '<span class="dim">–</span>')
        cells.append(c)
    html = table(heads, cells, cls="compact keys")
    parts = html.split("<tr>")
    head, body_rows = parts[:2], parts[2:]
    tagged = [f'<tr id="{anchors[e["h"]]}">' + r for (e, *_), r in zip(rows, body_rows)]
    return "<tr>".join(head) + "".join(tagged)


def build_keys(site):
    k = site.data("keys")
    anchors = key_anchors(k)
    packs = pack_info(site, k)
    missions = {norm(ms["name"]): ms for ms in site.data("missions")["missions"]}
    places = key_places(site)
    locs = [l for l in site.data("map_locations")["list"] if l["name"] not in SKIP_LOCATIONS]
    gd = site.data("gamedata")
    by_sec = collections.Counter(e["s"] for e in k["items"])
    body = []

    body.append(bar("How keys work"))
    body.append(
        "<p>Keys, barcodes, keycards and mission items don't take up space in your backpack. The game keeps them "
        "in your profile's item stash, which every character of the profile shares. There is no record of opened "
        "doors: holding the key is what opens its door. Items tagged <b>Mission item</b> are flagged as such in "
        "the files: a mission normally hands them out or asks for them.</p>"
        "<p>Items of a DLC the account doesn't own are set aside by the game, so you can't use them. <b>Missions that name it</b> quotes "
        "the mission line that asks for the item.</p>")

    body.append(bar("All keys", right=f"{len(k['items'])} items"))
    body.append("<p>One section per kind of key; open one, or type in the box to search all of them.</p>")
    body.append('<div class="filterbar" data-for="keylist"><input placeholder="Filter keys...">'
                '<span class="count"></span></div><div class="foldall" data-for="keylist"></div>')
    folds = []
    for s in k["sections"]:
        items = [e for e in k["items"] if e["s"] == s["key"]]
        a = max((e["a"] for e in items), default=1)
        intro = KEY_NOTE.get(s["key"], "").format(a=a)
        if s["key"] == "barcodes":
            ch = next((c for t in gd["challenges"] for c in t["challenges"] if "Warboard" in c["tiers"][0]["desc"]), None)
            if ch:
                intro += (f" Activating the Warboards is the challenge {site.link('challenge', ch['name'])} "
                          f"({esc(ch['tiers'][-1]['desc'].lower().rstrip('.'))} for the last tier).")
        folds.append(fold(s["name"], f"<p>{intro}</p>" + key_table(site, k, items, packs, missions, places, locs,
                                                                  anchors),
                          level=3, id=s["key"], right=str(len(items))))
    body.append(f'<div id="keylist">{"".join(folds)}</div>')

    # content packs
    rows = []
    cnt = collections.Counter(e["p"] for e in k["items"])
    for p, n in cnt.most_common():
        info = packs.get(p)
        its = ", ".join(f'<a href="#{anchors[e["h"]]}">{esc(e["n"])}</a>' for e in k["items"] if e["p"] == p) \
            if p != k["base_pack"] else '<span class="dim">every other key</span>'
        rows.append([info[0] if info else "Other pack", n, esc(info[3]) if info else "", its])
    body.append(fold("Content packs", "<p>Which content pack (DLC) each item belongs to. The base game has no list "
                                      "of its own: every item that is in no other pack is base game.</p>"
                     + table(["Pack", "Keys", "What it is", "Its keys"], rows, cls="compact", num={1}),
                     id="packs", right=plural(len(rows), "pack")))

    # the keys that lie loose in the world: a small map, last
    loose = [(e, places[e["n"]]) for e in k["items"] if e["n"] in places]
    if loose:
        body.append(bar("Keys on the map", right=str(len(loose))))
        text = (f"<p>Most keys come from a mission or a container, but the files place {len(loose)} of them as "
                f"loose loot in the world (the numbers of the little map):</p><ol class=\"kloose\">"
                + "".join(f'<li><a href="#{anchors[e["h"]]}">{esc(e["n"])}</a> · {region_link(site, pl["r"])} · '
                          f'<a href="{key_map_link(e, pl)}">map</a></li>' for e, pl in loose) + "</ol>")
        (e0, p0), rest = loose[0], loose[1:]
        # short number labels: the full names overlap on a map this small (the list beside it names them).
        # wiki.js fits the points with almost no margin, so the outer pins sat on the map's edge: two unlabelled
        # points just outside the keys' box (hidden by collectibles.css) give the fit a margin.
        xs, zs = [pl["x"] for _, pl in loose], [pl["z"] for _, pl in loose]
        pad = 0.11 * max(max(xs) - min(xs), max(zs) - min(zs))
        pads = [(min(xs) - pad, min(zs) - pad, ""), (max(xs) + pad, max(zs) + pad, "")]
        body.append('<div class="kmap">' + minimap(p0["x"], p0["z"], "1", markers=[
            (pl["x"], pl["z"], str(i)) for i, (e, pl) in enumerate(rest, 2)] + pads, show=[LOOSE_KEYS],
            small=True, text=text) + "</div>")

    box = infobox("Keys & barcodes", [(s["name"], f'<a href="#{s["key"]}">{by_sec[s["key"]]}</a>')
                                      for s in k["sections"]] + [
        ("All items", len(k["items"])),
        ("Flagged as mission items", sum(1 for e in k["items"] if e.get("m"))),
        ("From a DLC", f'<a href="#packs">{sum(1 for e in k["items"] if e["p"] != k["base_pack"])}</a>'),
        ("Loose in the world", f'<a href="{maplink(show=[LOOSE_KEYS])}">{len(loose)} on the map</a>' if loose else None),
    ], image=key_icon_url(site, k), cls="cbox")
    lead = (f"<p>Every key item in the game files: the <b>{by_sec['barcodes']} command bunker barcodes</b> that open "
            f"the regions' Warboard bunkers, <b>{by_sec['access']} facility barcodes and keycards</b>, "
            f"<b>{by_sec['doors']} door keys</b> and <b>{by_sec['mission']} mission items</b>, with what they open, "
            f"the mission that asks for them and the DLC they come from.</p>")
    site.page("world/keys.html", "Keys & barcodes", "\n".join(body), "world", sub="keys", lead=lead,
              head_extra=CSS, infobox_html=box,
              desc="All keys, bunker barcodes, keycards and mission items of Generation Zero: what they open, which "
                   "mission uses them and which DLC they belong to.",
              search={"k": "World", "w": "keys barcode keycard bunker door"})


def key_icon_url(site, k):
    e = next((e for e in k["items"] if e["s"] == "barcodes"), None)
    if e and site.has_file(f"img/keys/{e['i']}"):
        return f"~/img/keys/{e['i']}"
    return None
