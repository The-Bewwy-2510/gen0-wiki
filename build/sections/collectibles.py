"""World > Collectibles and Keys & barcodes.

Pages
    world/collectibles.html            every collectible type of markers.json (collectibles, schematic points,
                                       house photos) with counts per region and the challenges that count them
    world/collectibles/<sub key>.html  one page per type: a map of every pickup and a filterable table
    world/keys.html                    keys.json: command bunker barcodes, facility keycards, door keys and
                                       mission items, with their content pack and the missions that use them

Kinds registered
    collectible-type   key = markers.json sub key ('gnomes'), aliases = display name
    key                key = keys.json name, aliases = internal name and item hash

Data: markers.json (subs + items: s = sub key, n = name, x/z = world position in metres, l = the game's internal
scene / place name, r = map region, d = Alpine Unrest flag), map_locations.json (named locations, for "nearest"),
gamedata.json (challenges, schematic point currencies, stats), schematics.json, keys.json, loot.json (the four keys
that lie loose in the world), missions.json (to show which mission uses a key), vanity.json (dance emotes, gnome
masks).
"""
import collections
import math
import re

from wiki.site import esc, slug, norm, fmt, table, infobox, bar, note, cards, kv, tag, REGIONS

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
    "sovietdolls": "Soviet dolls, numbered <i>Soviet Doll 01</i> to <i>10</i>, all of them in the Marshlands. "
                   "They lie in named locations (scenes <code>R6 N…</code>) and in the open world between them "
                   "(<code>R6 W…</code>).",
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


def coords(p):
    return f'<span class="mono" data-v="{p["x"]:.0f}">{p["x"]:.0f}, {p["z"]:.0f}</span>'


def dlc_tag(region):
    return tag(REGION_DLC[region], "dlc") if region in REGION_DLC else ""


def page_path(key):
    return f"world/collectibles/{key}.html"


def plural(n, one, many=None):
    return f"{n} {one if n == 1 else (many or one + 's')}"


def and_list(parts):
    parts = list(parts)
    if len(parts) <= 1:
        return "".join(parts)
    return ", ".join(parts[:-1]) + " and " + parts[-1]


# ---------------------------------------------------------------------------------------------------------------
# the data model, computed once
# ---------------------------------------------------------------------------------------------------------------
class Model:
    def __init__(self, site):
        mk = site.data("markers")
        self.mains = {m["key"]: m["name"] for m in mk["mains"]}
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
        self.scene_regions = self._scene_regions()

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

    def dlc_trees(self, key):
        """[(challenge, expansion name)] for the challenges counting `key` that belong to an expansion's tree."""
        return [(ch, self.tree_dlc[tree["name"]]) for tree, ch in self.challenges.get(key, [])
                if self.tree_dlc.get(tree["name"])]

    def _scene_regions(self):
        """[(code, region)] for the short scene codes (R1, R2 ... Island01) in the markers' place names: the region
        most of the markers with that code lie in."""
        seen = collections.defaultdict(collections.Counter)
        for key in self.items:
            for i in self.pickups(key):
                for code in re.findall(r"\b(R\d+|Island\d+)\b", i["l"]):
                    seen[code][i["r"]] += 1
        order = lambda c: (c.startswith("Island"), int(re.sub(r"\D", "", c)))
        return [(c, seen[c].most_common(1)[0][0]) for c in sorted(seen, key=order)]

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
                      aliases=[s["name"]], desc=f"{GROUP_ONE[s['main']]} · {count}. "
                      + re.sub("<[^>]+>", "", BLURB.get(s["key"], "")),
                      keywords=f"collectible collectable {s['key']} {s['main']} location map")
    k = site.data("keys")
    for e in k["items"]:
        # "Storage key" and "Storage Key" are two different keys: the second one is registered by internal name
        key = e["n"] if not site.find("key", e["n"]) else e["r"]
        site.register("key", key, f"world/keys.html#{key_anchor(e)}", e["n"], icon=f"img/keys/{e['i']}",
                      aliases=[e["r"], str(e["h"])], desc=f"{section_name(k, e['s'])} · {strip_desc(e['d'])}",
                      keywords=f"key {e['r']} {e['s']}")


def key_anchor(e):
    return "k-" + slug(e["r"])


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


def challenge_links(site, m, key):
    return ", ".join(site.link("challenge", ch["name"]) for _, ch in m.challenges.get(key, []))


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
    heads = ["Type", "Total"] + [REGION_SHORT[r] + (" (DLC)" if r in REGION_DLC else "") for r in REGION_KEYS]
    return table(heads, rows, cls="compact ctypes", num=set(range(1, 2 + len(REGION_KEYS))))


def type_cards(site, m, main):
    items = []
    for s in m.subs:
        if s["main"] != main:
            continue
        p = m.pickups(s["key"])
        regs = sorted({i["r"] for i in p}, key=REGION_KEYS.index)
        where = REGION_SHORT[regs[0]] if len(regs) == 1 else f"{len(regs)} regions"
        if m.unplaced(s["key"]):
            where = "No map position"
        items.append({"href": "~/" + page_path(s["key"]), "title": s["name"], "img": "~/map/" + s["icon"],
                      "tag": str(len(p)), "color": "#8a6d1f" if any(r in REGION_DLC for r in regs) else "#5f4258",
                      "sub": f"<b>{esc(where)}</b><br>{esc(first_sentence(BLURB.get(s['key'], '')))}"})
    return cards(items, cls="small ccards")


def first_sentence(html):
    text = re.sub("<[^>]+>", "", html)
    return re.split(r"(?<=\.)\s", text, maxsplit=1)[0]


def single_region_types(m):
    """[(sub, region)] for the types whose pickups all lie in one region."""
    out = []
    for s in m.subs:
        rc = m.region_counts(s["key"], placed_only=True)
        if len(rc) == 1:
            out.append((s, next(iter(rc))))
    return out


def scene_region_mismatch(m):
    """One example of an item whose internal place name names another region than the map border puts it in."""
    words = {"archipelago": "archipelago", "southcoast": "southcoast", "farmlands": "farmlands",
             "forest": "forest", "mountain": "mountains", "mountains": "mountains", "marshlands": "marshlands",
             "northcoast": "northcoast"}
    for s in m.subs:
        for i in m.pickups(s["key"]):
            w = norm(i["l"].split(" ")[0])
            if w in words and words[w] != i["r"]:
                return i, words[w]
    return None, None


def photo_coverage(m):
    """(names of the safehouses that have a house photo, [safehouse markers without one])."""
    have = {i["safehouse"]["n"] for i in m.pickups("safehousehints") if i.get("safehouse")}
    return have, [s for s in m.safehouses if s["n"] not in have]


def photo_sentence(site, m):
    """How many safehouses have a house photo, from the data."""
    have, missing = photo_coverage(m)
    mainland = [s for s in m.safehouses if s["r"] not in REGION_DLC]
    miss_main = sorted((s for s in missing if s["r"] not in REGION_DLC), key=lambda s: norm(s["n"]))
    miss_dlc = [s for s in missing if s["r"] in REGION_DLC]
    text = f"{len(mainland) - len(miss_main)} of the {len(mainland)} mainland safehouses have a house photo."
    if miss_main:
        text += " " + and_list(site.link("safehouse", s["n"]) for s in miss_main) + " have none in the files"
        text += f", and neither do any of the {len(miss_dlc)} safehouses on Himfjäll." if miss_dlc else "."
    elif miss_dlc:
        text += f" The {len(miss_dlc)} safehouses on Himfjäll have none in the files."
    return text


def build_overview(site, m):
    gd = site.data("gamedata")
    total = sum(len(m.pickups(s["key"])) for s in m.subs)
    n_placed = sum(len(m.placed(s["key"])) for s in m.subs)
    unplaced = [s for s in m.subs if m.unplaced(s["key"])]
    n_col = sum(len(m.pickups(s["key"])) for s in m.subs if s["main"] == "collectibles")
    n_types = sum(1 for s in m.subs if s["main"] == "collectibles")
    body = []

    body.append(bar("All types"))
    body.append("<p>One row per marker type of the map that this section covers. <b>Total</b> is the number of "
                "entries in the game files (for audio logs without the dialogue copies, see below); the region "
                "columns split it by the region the map borders put each pickup in (Himfjäll is the Alpine Unrest "
                "island). Click a header to sort, or a name for the page with every pickup of that type on a map.</p>")
    body.append(overview_table(site, m))
    if unplaced:
        body.append('<p class="dim"><small>* ' + and_list(
            site.link("collectible-type", s["key"], s["name"]) for s in unplaced)
            + " have no position in the world: their region comes from their name, and the <b>All types</b> row "
              "leaves them out of the region totals.</small></p>")

    for main in OWN_MAINS:
        body.append(bar(GROUP_LABEL[main], right=f"{sum(len(m.pickups(s['key'])) for s in m.subs if s['main'] == main)} pickups"))
        if main == "collectibles":
            stat = next((x for x in gd["stats"] if x["key"] == "CollectablesFound"), None)
            stat_txt = (f" The game keeps a <i>{esc(stat['label'])}</i> statistic (<code>{esc(stat['key'])}</code>)."
                        if stat else "")
            n_ch = sum(1 for s in m.subs if s["main"] == main and m.challenges.get(s["key"]))
            body.append(f"<p>The {n_types} collectible series.{stat_txt} {n_ch} of the series also count for a "
                        f"challenge (see below).</p>")
        elif main == "schematics":
            body.append("<p>Schematic point pickups are not collectibles in the menu sense: each gives points of "
                        "one schematic currency, which you spend in that crafting tree. The markers don't name a "
                        "schematic; the pages list what the currency buys.</p>")
        else:
            body.append(f"<p>{photo_sentence(site, m)}</p>")
        body.append(type_cards(site, m, main))

    body.append(bar("Challenges"))
    body.append("<p>The challenges whose objectives count collectibles, with every tier. <b>From → to</b> is the "
                "running total the tier starts at and needs; the title is the reward the game names for the tier. "
                "The files flag some challenge trees as DLC; the tag names the expansion, worked out from the "
                "missions and expansion names its challenges quote. Such a challenge is part of that expansion even when "
                "the collectibles it counts lie on the base game map.</p>")
    body.append(challenge_table(site, m, [s["key"] for s in m.subs]))

    body.append(bar("Tips"))
    body.append("<ul>" + "".join(f"<li>{t}</li>" for t in overview_tips(site, m)) + "</ul>")

    body.append(bar("Reading the data"))
    item, named = scene_region_mismatch(m)
    ex = ""
    if item:
        ex = (f" For example <i>{esc(item['n'])}</i> has the place name <code>{esc(item['l'])}</code>, but lies "
              f"inside the {esc(REGION_SHORT[item['r']])} border.")
    body.append(note(
        "<p>Each marker has a <b>place name</b>: the internal name of the game scene the object sits in, such as "
        "<code>Farmlands Överby Farm Sandbo</code> or <code>R4 W045</code> (in those short codes the number is the "
        "region: " + ", ".join(f"<code>{c}</code> {esc(REGION_SHORT[r])}" for c, r in m.scene_regions) + "; "
        "<code>N</code> scenes are named locations and <code>W</code> scenes open world). The <b>region</b> "
        "column is worked out from the region borders of the map, which is what the game's own map uses." + ex
        + "</p><p>Coordinates are world metres: x grows to the east, z to the south, the same numbers as in the "
        "interactive map.</p>", "data"))
    copies = [i for i in m.items.get("audiologs", []) if i["copy"]]
    if copies:
        body.append(note(
            f"The map data has {len(m.items['audiologs'])} audio log markers, but only "
            f"{len(m.pickups('audiologs'))} audio logs: every log is also in a dialogue scene "
            f"(<code>{COPY_LABEL}</code>) at one shared spot. Lists that count {len(m.items['audiologs'])} audio "
            f"logs count each one twice.", "fix", "Audio log count"))

    stat = next((s for s in gd["stats"] if s["key"] == "CollectablesFound"), None)
    summary = kv([
        ("Collectible series", n_types),
        ("Collectibles", n_col),
        ("Schematic point pickups", sum(len(m.pickups(s["key"])) for s in m.subs if s["main"] == "schematics")),
        ("House photos", len(m.pickups("safehousehints"))),
        ("All entries", total),
        ("With a map position", n_placed),
        ("Game statistic", f"<i>{esc(stat['label'])}</i> <code>{esc(stat['key'])}</code>" if stat else None),
        ("Keys & barcodes", f'<a href="~/world/keys.html">{len(site.data("keys")["items"])} items</a>'),
    ])
    body.insert(0, summary)
    no_pos = ""
    if unplaced:
        no_pos = (f" (the {sum(len(m.pickups(s['key'])) for s in unplaced)} "
                  + and_list(esc(s["name"]) for s in unplaced) + " entries are lore with no place in the world)")
    lead = (f"<p>Generation Zero hides <b>{n_col} collectibles</b> in {n_types} series around Östertörn and "
            f"Himfjäll, from garden gnomes and Dala horses to mixtapes, machine blueprints and audio logs. This page "
            f"also covers the <b>schematic point</b> pickups and the <b>house photos</b> of the safehouses: "
            f"{total} entries in all, read from the game files, {n_placed} of them with an exact position"
            f"{no_pos}.</p>")
    site.page("world/collectibles.html", "Collectibles", "\n".join(body), "world", sub="collectibles", lead=lead,
              head_extra=CSS,
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
    tips.append(f"Counting only the collectible series (not schematic points or house photos), "
                f"{site.link('region', best[0])} holds the most: {best[1]} of the {n} collectibles with a map "
                f"position.")
    one = single_region_types(m)
    if one:
        tips.append("Some series stay in one region, so you can finish them in one trip: " + and_list(
            f"{site.link('collectible-type', s['key'], s['name'])} ({site.link('region', r, REGION_SHORT[r])})"
            for s, r in one) + ".")
    tips.append("Every type page with real positions has a map with all pickups and the nearest named location of "
                f'each one; the <a href="~/map/index.html">interactive map</a> shows them all together with '
                f"filters.")
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


def challenge_table(site, m, keys):
    """Every tier of the challenges that count any of `keys`; 'Counts' names every type the challenge counts."""
    all_keys = [s["key"] for s in m.subs]
    rows, seen = [], set()
    for key in keys:
        for tree, ch in m.challenges.get(key, []):
            if ch["key"] in seen:
                continue
            seen.add(ch["key"])
            types = [k for k in all_keys if any(c["key"] == ch["key"] for _, c in m.challenges.get(k, []))]
            what = " + ".join(site.link("collectible-type", k, m.sub[k]["name"]) for k in types)
            for n, t in enumerate(ch["tiers"], 1):
                rows.append([site.link("challenge", ch["name"]) if n == 1 else "",
                             tree_cell(site, m, tree) if n == 1 else "",
                             what if n == 1 else "", n, f'<span data-v="{t["req"]}">{t["start"]} → {t["req"]}</span>',
                             esc(t["desc"]), esc(t["title"])])
    if not rows:
        return ""
    return table(["Challenge", "Tree", "Counts", "Tier", "From → to", "Objective", "Title"], rows,
                 cls="compact", sortable=False)



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


def static_map(site, pts, link_rows=True):
    """pts: [(x, z, label, title, anchor)]. Returns the HTML of the cropped map with numbered pins."""
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
        href = f' href="#{anchor}"' if anchor else ""
        pins.append(f'<{el} class="spin"{href} title="{esc(title)}" style="left:{(u - u0) / su * 100:.3f}%;'
                    f'top:{(v - v0) / sv * 100:.3f}%">{esc(label)}</{el}>')
    many = " many" if len(pts) > MANY_PINS else ""     # collectibles.css turns these pins into dots on phones
    return (f'<div class="smap{many}" style="aspect-ratio:{su / sv:.4f}">{inner}{"".join(pins)}'
            f'<a class="mmopen" href="~/map/index.html">Open the full map</a></div>')

# ---------------------------------------------------------------------------------------------------------------
# world/collectibles/<key>.html
# ---------------------------------------------------------------------------------------------------------------
def near_cell(site, it):
    if not it["loc"]:
        return '<span class="dim">–</span>'
    d = it["ld"]
    rel = "at" if d < 40 else f"{d:,.0f} m {compass(it['loc'], it)} of"
    return f'<span data-v="{d:.0f}"><span class="dim">{rel}</span> {site.link("location", it["loc"]["name"])}</span>'


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


def coords_cell(it):
    if it["glob"]:
        return '<span class="dim">placeholder</span>'
    if it["copy"]:
        return '<span class="dim">dialogue copy</span>'
    return coords(it)


def item_table(site, m, key):
    items = m.items[key]
    heads, extra = extra_columns(site, m, key)
    rows = []
    for it in items:
        cells = [it["num"], item_name(site, key, it)] + (extra(it) if extra else []) + [
            site.link("region", it["r"], REGION_SHORT[it["r"]]) + (" " + dlc_tag(it["r"]) if it["r"] in REGION_DLC else ""),
            near_cell(site, it), f"<code>{esc(it['l'])}</code>", coords_cell(it)]
        rows.append((it, cells))
    out = ['<div class="filterbar" data-for="items"><input placeholder="Filter by name or place...">'
           '<button class="chip on" data-g="r" data-f="*">All</button>']
    regs = sorted({it["r"] for it in items}, key=REGION_KEYS.index)
    if len(regs) > 1:
        out += [f'<button class="chip" data-g="r" data-f="{r}">{esc(REGION_SHORT[r])}</button>' for r in regs]
    if any(it["copy"] for it in items):
        out.append('<button class="chip on" data-g="c" data-f="*">With dialogue copies</button>'
                   '<button class="chip" data-g="c" data-f="pick">Pickups only</button>')
    out.append('<span class="count"></span></div>')
    html = table(["#", "Name"] + heads + ["Region", "Nearest location", "Place name (internal)", "x, z"],
                 [c for _, c in rows], cls="compact citems", num={0})
    # give each row its filter tags (region) and an id to link to
    parts = html.split("<tr>")
    head, body_rows = parts[:2], parts[2:]
    tagged = [f'<tr id="i{it["num"]}" data-f="{it["r"]} {"copy" if it["copy"] else "pick"}"'
              f'{" class=copyrow" if it["copy"] else ""}>' + r for (it, _), r in zip(rows, body_rows)]
    out.append(f'<div id="items">{"<tr>".join(head)}{"".join(tagged)}</div>')
    return "".join(out)


def region_table(site, m, key):
    rc = m.region_counts(key)
    total = sum(rc.values())
    rows = [[site.link("region", r, REGION_SHORT[r]) + (" " + dlc_tag(r) if r in REGION_DLC else ""), rc[r],
             f'<span data-v="{rc[r] / total:.4f}">{rc[r] / total * 100:.0f}%</span>'
             f'<span class="sbar" style="width:{rc[r] / total * 120:.0f}px"></span>']
            for r in REGION_KEYS if rc.get(r)]
    return table(["Region", "Pickups", "Share"], rows, cls="compact cregions", num={1, 2})


def map_block(site, m, key):
    pts = [(i["x"], i["z"], str(i["num"]), f'{i["num"]}. {i["n"]}', f'i{i["num"]}')
           for i in m.pickups(key) if not i["glob"]]
    return static_map(site, pts)


def type_lead(site, m, key):
    s = m.sub[key]
    p = m.pickups(key)
    rc = m.region_counts(key)
    regs = [r for r in REGION_KEYS if rc.get(r)]
    if len(regs) == 1:
        where = f"All {len(p)} are in {site.link('region', regs[0], REGION_SHORT[regs[0]])}."
    else:
        where = f"The game files place <b>{len(p)}</b> across {len(regs)} regions, " + most_text(site, rc) + "."
    if m.unplaced(key):
        where = f"There are <b>{len(p)}</b>, one per mainland region by name."
    dlc = ""
    if any(r in REGION_DLC for r in regs):
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
        body.append(bar("Map", right=f"{plural(len(p), 'pickup')}"))
        body.append("<p>Every pickup of this type. The numbers are the <b>#</b> column of the table below: hover a "
                    "pin for its name, click it to jump to its row. The interactive map has the same pins with "
                    "zoom and filters.</p>")
        body.append(mp)
    elif key == "worldlocations":
        body.append(note(f"All {len(p)} World Location entries sit at the same spot in a global scene "
                         f"(<code>{GLOBAL_LABEL}</code>), not in the world, so there is nothing to show on a map. "
                         "Maps that put a pin for them far out west are showing that placeholder.", "warn"))

    body.append(bar(f"All {s['name'].lower()}",
                    right=plural(len(m.items[key]), "marker")))
    body.append("<p><b>Nearest location</b> is the closest named place of the map and how far and in which "
                "direction the pickup lies from it. <b>Place name</b> is the internal name of the game scene the "
                "object is in. Type in the box to filter, click a region to show only that one, click a header to "
                "sort.</p>")
    body.append(item_table(site, m, key))
    if key == "audiologs":
        body.append(note(
            f"The rows with the place name <code>{COPY_LABEL}</code> are not pickups: every audio log also exists "
            "in a dialogue scene, all at one shared spot. That is why the map data has twice as many audio log "
            f"markers as there are logs. The map above shows only the {len(p)} real pickups.", "fix"))

    if len({i["r"] for i in p}) > 1 and key != "worldlocations":
        body.append(bar("By region"))
        body.append("<p>How the pickups split over the regions.</p>")
        body.append(region_table(site, m, key))

    body.extend(type_extras(site, m, key))

    if m.challenges.get(key):
        body.append(bar("Challenge"))
        body.append("<p>The challenge that counts these, tier by tier.</p>")
        body.append(challenge_table(site, m, [key]))

    body.append(type_nav(site, m, prev_key, next_key))

    facts = type_facts(site, m, key)
    box = ""
    if extra_columns(site, m, key)[0]:
        # the item table has extra columns and needs the whole width: the facts go in a list at the top
        body.insert(0, kv([("Icon", type_icon(site, s))] + facts))
    else:
        box = infobox(s["name"], facts, image="~/map/" + s["icon"] if site.has_file("map/" + s["icon"]) else None,
                      cls="cbox")
    site.page(page_path(key), s["name"], "\n".join(body), "world", sub="collectibles",
              crumbs=[("Collectibles", "~/world/collectibles.html")], kind=f"World · {GROUP_ONE[s['main']]}",
              lead=type_lead(site, m, key), infobox_html=box, head_extra=CSS,
              desc=f"All {len(p)} {s['name']} of Generation Zero with map, region and nearest location.")


def type_facts(site, m, key):
    """The (label, html) rows of a type's infobox."""
    s = m.sub[key]
    p = m.pickups(key)
    rc = m.region_counts(key)
    regs = [r for r in REGION_KEYS if rc.get(r)]
    if any(r in REGION_DLC for r in regs):
        dlc = dlc_tag(next(r for r in regs if r in REGION_DLC))
    else:
        # on the base game map, but the challenge that counts them may belong to an expansion
        trees = sorted({d for _, d in m.dlc_trees(key)})
        dlc = ("Base game map" + "".join(f" · challenge: {dlc_badge(site, d)}" for d in trees)) if trees \
            else "Base game"
    return [
        ("Group", esc(GROUP_ONE[s["main"]])),
        ("Entries" if m.unplaced(key) else "Pickups", len(p)),
        ("Map markers", len(m.items[key]) if len(m.items[key]) != len(p) else None),
        ("Regions", ", ".join(site.link("region", r, REGION_SHORT[r]) for r in regs)),
        ("DLC", dlc),
        ("Challenge", challenge_links(site, m, key) or None),
        ("Marker key", f"<code>{esc(key)}</code>"),
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
    if key == "videotapes":
        return videotape_extras(site, m)
    return []


def schematic_extras(site, m, key):
    cur_key = key[4:]
    gd = site.data("gamedata")
    cur = next((c for c in gd["schematics"] if c["key"] == cur_key), None)
    sc = site.data("schematics")
    tree = [i for i in sc["items"] if i["t"] == cur_key]
    out = [bar("What the points buy")]
    if cur:
        icon = site.img(f"img/currencies/{cur_key}.png", cls="cur")
        out.append(kv([("Currency", icon + esc(cur["name"])), ("Internal hash", f"<code>{cur['hash']}</code>"),
                       ("How the game says you get it", esc(cur["earn"]))]))
    if cur_key == "apparel" and cur and "Rival" in cur["earn"]:
        out.append(note(f"The game's own text says Apparel Schematic Points are found as loot on Rivals, but the "
                        f"files also place these {len(m.pickups(key))} pickups in the world.", "info"))
    # one row per schematic (all ranks of a name together)
    by_name = collections.OrderedDict()
    for i in tree:
        by_name.setdefault(i["n"], []).append(i)
    rows = []
    for name, ranks in by_name.items():
        cost = sum(r["c"] for r in ranks)
        rows.append([site.link("schematic", name), len(ranks),
                     " / ".join(fmt(r["c"]) for r in sorted(ranks, key=lambda r: r["q"])), cost])
    out.append(f"<p>The markers don't name a schematic: they give points of the currency, which you spend in the "
               f"{esc(cur_key)} tree. These are the {len(by_name)} schematics of that tree ({len(tree)} ranks). "
               f"<b>Cost per rank</b> is the points each rank costs, lowest rank first.</p>")
    out.append(table(["Schematic", "Ranks", "Cost per rank", "Total cost"], rows, cls="compact", num={1, 3}))
    total = sum(r[3] for r in rows)
    out.append(f"<p>Buying every rank of the tree costs <b>{fmt(total)}</b> {esc(cur['name'] if cur else 'points')}."
               f" See {site.link('schematic', cur_key, 'the schematics page') if site.find('schematic', cur_key) else '<a href=\"~/items/schematics.html\">the schematics page</a>'}"
               f" for recipes and prerequisites.</p>")
    return out


def photo_extras(site, m):
    have, missing = photo_coverage(m)
    by_r = collections.defaultdict(list)
    for s in missing:
        by_r[s["r"]].append(s)
    out = [bar("Safehouses without a photo")]
    out.append(f"<p>{len(m.safehouses)} safehouses have a marker on the map and {len(have)} of them have a house "
               f"photo within {PHOTO_AT} m. These {len(missing)} have none in the files:</p>")
    rows = [[site.link("region", r, REGION_SHORT[r]) + " " + dlc_tag(r),
             ", ".join(site.link("safehouse", s["n"]) for s in sorted(by_r[r], key=lambda s: norm(s["n"])))]
            for r in REGION_KEYS if by_r.get(r)]
    out.append(table(["Region", "Safehouses"], rows, cls="compact", sortable=False))
    dup = collections.Counter(i["n"] for i in m.pickups("safehousehints"))
    dups = [n for n, c in dup.items() if c > 1]
    if dups:
        out.append(note("Some photos share a name although they are different pickups at different safehouses: "
                        + ", ".join(f"<i>{esc(n)}</i> ({dup[n]}×)" for n in dups) + ". Use the safehouse column to "
                        "tell them apart.", "info"))
    return out


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
    out = [bar("By machine")]
    out.append("<p>Which blueprints each machine has. The letters are the class letters in the blueprint names; "
               "click one to jump to its row. <b>Faction</b> follows the blueprint name: <i>Soviet Blueprint</i> and "
               "<i>Rival Blueprint</i> as named, the rest are the original (Swedish) machines.</p>")
    out.append(table(["Machine", "Faction", "Blueprints", "Count"], rows, cls="compact", num={3}))
    return out


def gnome_extras(site):
    masks = [v for v in site.data("vanity")["items"] if v["r"].startswith("char_part_head_gnome_reward")]
    if not masks:
        return []
    out = [bar("Gnome masks")]
    out.append(f"<p>The apparel list has {len(masks)} gnome masks whose internal names start with "
               f"<code>char_part_head_gnome_reward</code>, which points to them being the reward for the gnome hunt; the data here "
               f"doesn't say how many gnomes unlock which one.</p>")
    out.append("<ul>" + "".join(f"<li>{site.link('vanity', v['n'])} <code>{esc(v['r'])}</code></li>"
                                for v in masks) + "</ul>")
    return out


def videotape_extras(site, m):
    emotes = {norm(v["n"]): v for v in site.data("vanity")["items"] if v["g"] == "emotes"}
    rows = []
    for it in m.pickups("videotapes"):
        title = it["n"].split(" - ", 1)[-1]
        e = emotes.get(norm(title))
        if e:
            icon = site.img(f"img/vanity/{e['i']}", cls="li") if site.has_file(f"img/vanity/{e['i']}") else ""
            rows.append([esc(it["n"]), icon + site.link("vanity", e["n"]), f"<code>{esc(e['r'])}</code>"])
    if not rows:
        return []
    return [bar("Tapes and dance emotes"),
            "<p>Every tape title is also the name of a dance emote in the vanity list:</p>",
            table(["Videotape", "Dance emote", "Internal name"], rows, cls="compact")]


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
    "barcodes": "Each command bunker needs a full entry barcode, which the game splits into pieces: the files give "
                "every barcode a stack of <b>{a}</b>. You collect the pieces from destroyed machines of that region "
                "(the Warboard missions say so), and a full barcode opens that region's command bunker.",
    "access": "Barcodes and keycards for research facilities and their labs.",
    "doors": "Ordinary keys to houses, barns and storage rooms. Several open a door a mission asks you to get "
             "through; for the rest no mission text names them.",
    "mission": "Items a mission hands out or asks for. Most of them belong to FNIX Rising.",
}


def pack_info(site, k):
    """pack hash -> (display html, short label, tag class, description)."""
    sc = {i["h"]: i for i in site.data("schematics")["items"]}
    stock = {s["h"]: s for s in site.data("stock")["stock"]}
    out = {k["base_pack"]: (site.link("dlc", "Base game"), "Base game", "base", "the base game")}
    known = {363622574: "FNIX Rising", 3565103498: "Alpine Unrest"}
    for p, hs in k["pack_items"].items():
        p = int(p)
        if p in known:
            out[p] = (site.link("dlc", known[p]), known[p], "dlc", f"the {known[p]} expansion")
            continue
        n_sch = sum(1 for h in hs if h in sc)
        n_mat = sum(1 for h in hs if stock.get(h, {}).get("g") == "materials")
        if n_sch:
            label = "Apparel crafting pack"
            desc = (f"a content pack the files don't name, which also holds the {n_sch} apparel schematics and "
                    f"{n_mat} crafting materials")
        else:
            label = f"Pack {p}"
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
    idx = next((i for i, s in enumerate(lo["subs"]) if s["key"] == "loot_x_keys"), None)
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


def key_rows(site, k, packs, missions, places, locs):
    rows = []
    order = [s["key"] for s in k["sections"]]
    for e in sorted(k["items"], key=lambda e: order.index(e["s"])):
        p = packs.get(e["p"], (f"Pack {e['p']}", f"Pack {e['p']}", "base", ""))
        refs = mission_refs(site, e["r"], missions)
        used = "".join(f'<div class="kref">{site.link("mission", ms["name"])}'
                       f'<span class="dim">“{esc(line)}”</span></div>' for ms, line in refs)
        where = ""
        pl = places.get(e["n"])
        if pl:
            loc = min(locs, key=lambda l: dist(l, pl))
            d = dist(loc, pl)
            where = (f'{coords(pl)}<br><span class="dim">{d:,.0f} m {compass(loc, pl)} of</span> '
                     f'{site.link("location", loc["name"])}')
        elif e.get("x"):
            where = esc(e["x"])
        flags = [f'<a class="ksec" href="#{e["s"]}">{esc(section_name(k, e["s"]))}</a>']
        if e["s"] == "barcodes":
            reg = re.search(r"for the (.+?) Region", e["d"])
            if reg:
                rk = next((key for key, name in REGIONS if norm(name) == norm(reg.group(1))), None)
                flags.append(site.link("region", rk, reg.group(1)) if rk else esc(reg.group(1)))
        if e.get("m"):
            flags.append(tag("Mission-flagged", "main"))
        if p[2] == "dlc":
            flags.append(tag(p[1], "dlc"))
        name = (f'{key_icon(site, e)}<span class="kname"><b>{esc(e["n"])}</b><code>{esc(e["r"])}</code>'
                f'<small class="dim">{e["h"]}</small></span>')
        rows.append((e, [name, " ".join(flags), p[0], e["a"], esc(strip_desc(e["d"])) or '<span class="dim">–</span>',
                         used or '<span class="dim">–</span>', where or '<span class="dim">–</span>']))
    return rows


def keys_table(rows):
    html = table(["Key", "Kind & tags", "Pack", "Stack", "Description", "Missions that name it", "Where"],
                 [c for _, c in rows], cls="compact keys", num={3})
    parts = html.split("<tr>")
    head, body_rows = parts[:2], parts[2:]
    tagged = []
    for (e, _), r in zip(rows, body_rows):
        f = [e["s"], "m" if e.get("m") else "", "dlc" if e["p"] != 1413277686 else "base"]
        tagged.append(f'<tr id="{key_anchor(e)}" data-f="{" ".join(x for x in f if x)}">' + r)
    return "<tr>".join(head) + "".join(tagged)


def build_keys(site):
    k = site.data("keys")
    packs = pack_info(site, k)
    missions = {norm(ms["name"]): ms for ms in site.data("missions")["missions"]}
    places = key_places(site)
    locs = site.data("map_locations")["list"]
    gd = site.data("gamedata")
    by_sec = collections.Counter(e["s"] for e in k["items"])
    body = []

    body.append(bar("How keys work"))
    body.append(
        "<p>Keys, barcodes, keycards and mission items are not part of your backpack. The save keeps them in the "
        "profile's item stash (<code>Profile.ItemStash</code>), which every character of the profile shares, with "
        "an amount for each. The save has no record of opened doors: holding the key is what opens its door. "
        "<b>Stack</b> is how many of an item the game lets you hold (3 for the bunker barcode pieces, 1 for "
        "everything else). Items tagged <b>Mission-flagged</b> are flagged as mission items in the files: a mission "
        "normally hands them out or asks for them.</p>")
    body.append("<p><b>Pack</b> is the content pack (DLC) the item belongs to. An item of a pack the account doesn't "
                "own is moved aside by the game (to <code>InaccessibleItems</code>) instead of being usable. "
                "<b>Missions that name it</b> quotes the mission line that asks for the item.</p>")

    # the four kinds, then one table of every key: a filtered view never leaves empty tables behind
    body.append(bar("Kinds of keys"))
    items = []
    for s in k["sections"]:
        a = max((e["a"] for e in k["items"] if e["s"] == s["key"]), default=1)
        intro = KEY_NOTE.get(s["key"], "").format(a=a)
        if s["key"] == "barcodes":
            ch = next((c for t in gd["challenges"] for c in t["challenges"] if "Warboard" in c["tiers"][0]["desc"]), None)
            if ch:
                intro += (f" Activating the Warboards is the challenge {site.link('challenge', ch['name'])} "
                          f"({esc(ch['tiers'][-1]['desc'].lower().rstrip('.'))} for the last tier).")
        items.append(f'<li id="{s["key"]}"><b>{esc(s["name"])}</b> ({by_sec[s["key"]]}): {intro}</li>')
    body.append('<ul class="ksecs">' + "".join(items) + "</ul>")

    out = ['<div class="filterbar" data-for="keylist"><input placeholder="Filter keys...">'
           '<button class="chip on" data-g="s" data-f="*">All</button>']
    out += [f'<button class="chip" data-g="s" data-f="{s["key"]}">{esc(s["name"])}</button>' for s in k["sections"]]
    out.append('<button class="chip" data-g="t" data-f="m">Mission-flagged</button>'
               '<button class="chip" data-g="t" data-f="dlc">Not base game</button><span class="count"></span></div>')
    body.append(bar("All keys", right=f"{len(k['items'])} items"))
    body.append("<p>Every key in one table, in the order of the kinds above. Type to filter, or click a kind; "
                "<b>Mission-flagged</b> keeps the items the files flag as mission items, whatever their kind, and "
                "<b>Not base game</b> the ones from another content pack.</p>")
    body.append("".join(out))
    body.append(f'<div id="keylist">{keys_table(key_rows(site, k, packs, missions, places, locs))}</div>')

    # the keys that lie loose in the world
    pts = []
    for e in k["items"]:
        pl = places.get(e["n"])
        if pl:
            pts.append((pl["x"], pl["z"], str(len(pts) + 1), e["n"], key_anchor(e)))
    if pts:
        body.append(bar("Keys on the map"))
        body.append(f"<p>Most keys come from a mission or a container, but the files place {len(pts)} of them as "
                    f"loose loot in the world:</p>")
        body.append(static_map(site, pts))
        body.append("<ol>" + "".join(f'<li><a href="#{p[4]}">{esc(p[3])}</a></li>' for p in pts) + "</ol>")

    body.append(bar("Content packs"))
    body.append("<p>Which pack each item belongs to, by the pack's hash in the files. The base game pack has no "
                "list of its own: every item that is in no other pack is base game.</p>")
    rows = []
    cnt = collections.Counter(e["p"] for e in k["items"])
    for p, n in cnt.most_common():
        info = packs.get(p)
        rows.append([info[0] if info else f"Pack {p}", f'<code class="nowrap">{p}</code>', n,
                     esc(info[3]) if info else "", ", ".join(f'<a href="#{key_anchor(e)}">{esc(e["n"])}</a>'
                                                              for e in k["items"] if e["p"] == p and p != k["base_pack"])])
    body.append(table(["Pack", "Hash", "Keys", "What it is", "Its keys"], rows, cls="compact"))

    # no infobox: the wide key table needs the whole width; the numbers go in a small list at the top
    body.insert(0, kv([(s["name"], f'<a href="#{s["key"]}">{by_sec[s["key"]]}</a>') for s in k["sections"]] + [
        ("All items", len(k["items"])),
        ("Flagged as mission items", sum(1 for e in k["items"] if e.get("m"))),
        ("Not base game", sum(1 for e in k["items"] if e["p"] != k["base_pack"])),
    ]))
    lead = (f"<p>Every key item in the game files: the <b>{by_sec['barcodes']} command bunker barcodes</b> that open "
            f"the regions' Warboard bunkers, <b>{by_sec['access']} facility barcodes and keycards</b>, "
            f"<b>{by_sec['doors']} door keys</b> and <b>{by_sec['mission']} mission items</b>. For each one: its "
            f"description, internal name and hash, the content pack it comes from, the mission that asks for it and, "
            f"where the files place it in the world, its position.</p>")
    site.page("world/keys.html", "Keys & barcodes", "\n".join(body), "world", sub="keys", lead=lead,
              head_extra=CSS,
              desc="All keys, bunker barcodes, keycards and mission items of Generation Zero: what they open, which "
                   "mission uses them and which DLC they belong to.",
              search={"k": "World", "w": "keys barcode keycard bunker door"})
