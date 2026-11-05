"""World tab: the regions, every map location (one page each), safehouses, control points and beacons.

Data (build/data):
  gamedata.json       locations.list  every map location: id (internal name), hash (the save's key), name, type (the
                                      subtitle the game shows), kind (the map filter group), icon, region, x, z,
                                      spawns (loot crate spawn points known)
                      safehouses      per region: id, name, start (the safehouse a new character starts with)
                      regions         region name + hash; challenges (region mission challenges, Kill Switch ...)
  map_locations.json  the same locations (kinds with their plural names)
  markers.json        map markers: items {s: sub key, n: name, x, z, l: internal place label, d: 1 = Alpine
                      Unrest DLC, r: region (from the region borders)}; subs (collectible types, schematic points,
                      house photos, safehouses, control points, relay / Soviet beacons)
  location_crates.json  location hash -> object ids of its loot crate spawn points
  loot.json           placed loot: items [sub index, x, z, name index, region index, height]
  missions.json       missions with region, pack and text (we search the text for location names)

World units are metres; +x is east and +z is south (the North Coast has the most negative z).

Kinds registered: 'region' (key archipelago ...; aliases the display names), 'location' (name; aliases hash and
internal id), 'safehouse' (name; alias object id), 'controlpoint' (name).
"""
import collections
import math
import re

from wiki.site import esc, slug, norm, fmt, table, infobox, bar, note, cards, kv, minimap, qbadge, tag, REGIONS, QUALITY

CSS = '<link rel="stylesheet" href="~/assets/world.css">'
REGION_NAME = dict(REGIONS)
REGION_KEYS = [k for k, _ in REGIONS]

# Short hand-written introductions. They only name places that are in the location list of the region; every number
# on the pages is computed from the data.
REGION_BLURB = {
    "archipelago": "The islands where the game begins: Iboholmen, where you come ashore at Yttervik, and Norra and "
                   "Södra Saltholmen with the Saltholmen naval base, its bunkers and the Vesslan Command Bunker.",
    "southcoast": "The Hisinganäset peninsula and the Sävered area: fishing villages, farms and Torsberga Fort, and "
                  "the heart of FNIX territory with its data centres, generators and cable nodes.",
    "farmlands": "Open farm country around Överby, Boo and Dyrbo, with the F23 Överby Air Base, the Boo Bruk AB "
                 "works, old stone ships and the densest ring of control points in the game.",
    "forest": "The town of Östervik with its old town, harbour and neighbourhoods, surrounded by forest, lumber "
              "yards, hunting camps and readiness storage bunkers.",
    "mountains": "Rugged high ground with the village of Klinte and its harbour, the Redovisningskansli Öst military "
                 "compound and its Muskudden port complex, and many cabins and mountain bunkers.",
    "marshlands": "Wet lowland around the Norrmyra Artillery Base and its military area, with the Soviet camps and the "
                  "six Soviet hovercraft landing zones.",
    "northcoast": "The northern shore with the walled town of Hagaboda, the FOA Facility, castle ruins and the Soviet "
                  "positions: command quarters, research lab and trenches.",
    "alpine": "Himfjäll, the mountain island of the Alpine Unrest expansion: resort villages, hotels and slope "
              "cabins, readiness storage bunkers, the Digerhällen Artillery Base and the FOA 4 bunker "
              "\"Bergfinken\".",
}
REGION_DLC = {"alpine": "Alpine Unrest"}
REGION_SHORT = {   # one line for the region cards
    "archipelago": "Iboholmen and the Saltholmen islands, where the game begins.",
    "southcoast": "The Hisinganäset peninsula, Sävered and FNIX's outposts.",
    "farmlands": "Överby, Boo and Dyrbo, the F23 air base and many control points.",
    "forest": "The town of Östervik and the forests around it.",
    "mountains": "Klinte and the Redovisningskansli Öst military compound.",
    "marshlands": "Norrmyra's military area and the Soviet landing zones.",
    "northcoast": "Hagaboda, the FOA Facility and the Soviet positions.",
    "alpine": "The mountain island of the Alpine Unrest expansion.",
}

# singular names of the location kinds (map_locations.json only has the plural filter names)
KIND_ONE = {
    "settlement": "Settlement", "farm": "Farm", "church": "Church", "bunker": "Bunker", "military": "Military base",
    "airport": "Airport", "port": "Port", "radar": "Radar station", "lighthouse": "Lighthouse",
    "campsite": "Campsite", "tourist": "Tourist attraction", "industry": "Industry", "controlpoint": "Control point",
    "fnix": "FNIX site", "soviet": "Soviet site", "other": "Other",
}

PACK_TAG = {"alpine": ("Alpine Unrest", "dlc"), "fnix": ("FNIX Rising", "dlc"), "dlc03": ("Unreleased", "unreleased")}

NEAR_MARKERS = 300      # m: collectibles, schematic points, house photos and beacons listed on a location page
LOOT_RADIUS = 200       # m: placed loot counts for the nearest location when it is at most this far away
NEARBY_COUNT = 10       # nearest other locations listed on a location page
SAFEHOUSE_AT = 150      # m: a safehouse this close to a location (or with its name) belongs to it
PHOTO_AT = 50           # m: a house photo this close to a safehouse is that safehouse's photo
BEACON_SITE = 100       # m: beacon markers closer than this to each other are one site
MISSION_SKIP = {"Unknown"}  # location names too generic to search for in mission texts

MARKER_GROUPS = ("collectibles", "schematics", "housephotos", "beacons", "controlpoints")


# ---------------------------------------------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------------------------------------------
def dist(a, b):
    return math.hypot(a["x"] - b["x"], a["z"] - b["z"])


def compass(a, b):
    """Direction from a to b as N, NE, E ... (+z is south)."""
    ang = math.degrees(math.atan2(b["x"] - a["x"], -(b["z"] - a["z"]))) % 360
    return ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][int((ang + 22.5) // 45) % 8]


COMPASS_WORD = {"N": "north", "NE": "north-east", "E": "east", "SE": "south-east", "S": "south", "SW": "south-west",
                "W": "west", "NW": "north-west"}


def coords(p):
    return f'<span class="mono">{p["x"]:.0f}, {p["z"]:.0f}</span>'


def metres(d):
    return f"{d:,.0f} m"


def a_an(word):
    return "an" if word[:1].lower() in "aeiou" else "a"


PROPER_WORDS = {"Soviet", "Resistance", "FNIX", "FOA"}     # stay capitalised inside a sentence
TYPE_WORDS = {"Soviet Hovercraft": "Soviet hovercraft landing zone",   # the type names the vehicle, not the place
              "Other": "place"}


def type_phrase(loc):
    """'a homestead', 'an FNIX outpost', 'a Soviet camp' ... for the location's in-game type (falls back to the
    kind)."""
    t = loc["type"]
    if not t or t in ("Unknown", loc["name"]):
        t = KIND_ONE[loc["kind"]]
    t = TYPE_WORDS.get(t, t)
    words = [w if w.isupper() or w in PROPER_WORDS else w.lower() for w in t.split()]
    t = " ".join(words)
    art = "an" if t.startswith(("FNIX", "FOA")) else a_an(t)
    return f"{art} {esc(t)}"


def pack_tags(m):
    out = tag("Main", "main") if m["type"] == "main" else tag("Side", "side")
    if m["pack"] in PACK_TAG:
        out += " " + tag(*PACK_TAG[m["pack"]])
    if m.get("unreleased") and m["pack"] != "dlc03":
        out += " " + tag("Unreleased", "unreleased")
    return out


def region_tag(key):
    return tag(REGION_DLC[key], "dlc") if key in REGION_DLC else ""


def loc_icon(site, loc, cls="lic"):
    return site.img(f"img/locations/{loc['icon']}.png", cls=cls, alt="")


def marker_icon(site, sub, cls="lic"):
    """markers.json icon 'map/icons/x.png' lives at docs/map/map/icons/x.png."""
    return site.img("map/" + sub["icon"], cls=cls, alt="") if sub.get("icon") else ""


# ---------------------------------------------------------------------------------------------------------------
# whole-world overview map (inline SVG). minimap() is a zoomable piece of the map and cannot zoom out far enough
# to show all regions at once, so pages that need the whole world draw this instead.
# ---------------------------------------------------------------------------------------------------------------
OV_TILE = 16384         # world units covered by one level-1 tile of the interactive map (2 x 2 tiles = the world)
OV_PAD = 250            # m of margin around the region borders
REGION_COLOR = {"archipelago": "#4b9be0", "southcoast": "#5bbf4e", "farmlands": "#e8bd3f", "forest": "#2f9e6e",
                "mountains": "#a4a7aa", "marshlands": "#a463e0", "northcoast": "#e2507f", "alpine": "#d6c776"}


def overview_box(w):
    """x, z, width, height (world units) that hold every region border and Himfjäll's box."""
    pts = [p for b in w.borders.values() for p in b] + [(r[0], r[1]) for r in w.alpine_box()]
    x0, x1 = min(p[0] for p in pts) - OV_PAD, max(p[0] for p in pts) + OV_PAD
    z0, z1 = min(p[1] for p in pts) - OV_PAD, max(p[1] for p in pts) + OV_PAD
    return x0, z0, x1 - x0, z1 - z0


def overview_map(site, w, dots=(), caption="", label_regions=True):
    """The whole world: the interactive map's level-1 tiles, every region outline (a link to its region page) and
    optional dots [(x, z, title, href or None, css class)]. Always fits the width of the page."""
    x0, z0, bw, bh = overview_box(w)
    u = bw / 100                                  # 1 % of the map width, the unit for sizes below
    out = [f'<figure class="ovmap"><svg viewBox="{x0:.0f} {z0:.0f} {bw:.0f} {bh:.0f}" role="img" '
           f'aria-label="Map of the world">']
    for i in (0, 1):
        for j in (0, 1):
            out.append(f'<image href="~/map/map/tiles/1/{i}_{j}.webp" x="{i * OV_TILE - OV_TILE}" '
                       f'y="{j * OV_TILE - OV_TILE}" width="{OV_TILE + 24}" height="{OV_TILE + 24}"/>')
    for key in REGION_KEYS:
        col = REGION_COLOR[key]
        out.append(f'<a href="~/world/{key}.html" class="ovreg"><title>{esc(REGION_NAME[key])}</title>')
        if key in w.borders:
            pts = " ".join(f"{x:.0f},{z:.0f}" for x, z in w.borders[key])
            out.append(f'<polygon points="{pts}" style="--c:{col}" stroke-width="{u * .25:.0f}"/>')
        else:   # Himfjäll has no border in the map data: a box around its locations
            (ax0, az0), (ax1, az1) = w.alpine_box()
            out.append(f'<rect x="{ax0:.0f}" y="{az0:.0f}" width="{ax1 - ax0:.0f}" height="{az1 - az0:.0f}" '
                       f'rx="{u * 2:.0f}" style="--c:{col}" stroke-width="{u * .25:.0f}" stroke-dasharray="{u:.0f}"/>')
        out.append("</a>")
    for x, z, title, href, cls in dots:
        dot = f'<circle cx="{x:.0f}" cy="{z:.0f}" r="{u * (.9 if cls == "main" else .6):.0f}" class="{cls}">' \
              f'<title>{esc(title)}</title></circle>'
        out.append(f'<a href="{href}">{dot}</a>' if href else dot)
    if label_regions:
        for key in REGION_KEYS:
            c = w.centre[key]
            out.append(f'<text x="{c["x"]:.0f}" y="{c["z"]:.0f}" font-size="{u * (2.6 if not dots else 1.8):.0f}" '
                       f'stroke-width="{u * .5:.0f}" class="ovlabel{" faint" if dots else ""}">'
                       f'{esc(REGION_NAME[key].split(" (")[0])}</text>')
    out.append("</svg>")
    if caption:
        out.append(f"<figcaption>{caption}</figcaption>")
    out.append("</figure>")
    return "".join(out)


# ---------------------------------------------------------------------------------------------------------------
# the world model: everything the pages need, computed once
# ---------------------------------------------------------------------------------------------------------------
class World:
    def __init__(self, site):
        gd = site.data("gamedata")
        mk = site.data("markers")
        self.kinds = [k["key"] for k in site.data("map_locations")["kinds"]]
        self.kind_plural = {k["key"]: k["name"] for k in site.data("map_locations")["kinds"]}
        self.locs = sorted(gd["locations"]["list"], key=lambda l: norm(l["name"]))
        self.by_hash = {l["hash"]: l for l in self.locs}
        self.region_hash = {norm(r["name"]): r["hash"] for r in gd["regions"]}
        self.marker_region_name = {r["key"]: r["name"] for r in mk["regions"]}
        self.borders = {r["key"]: r["border"] for r in mk["regions"] if r.get("border")}
        self._slugs()
        self.subs = {s["key"]: s for s in mk["subs"]}
        self.mains = {m["key"]: m["name"] for m in mk["mains"]}
        self.markers = mk["items"]
        self.crates = site.data("location_crates")["crates"]
        self._safehouses(gd, mk)
        self._control_points()
        self._beacons()
        self._loot(site.data("loot"))
        self._missions(site.data("missions"))
        self._challenges(gd)
        self.centre = {r: self._centre([l for l in self.locs if l["region"] == r]) for r in REGION_KEYS}
        self.world_centre = self._centre(self.locs)

    @staticmethod
    def _centre(pts):
        return {"x": sum(p["x"] for p in pts) / len(pts), "z": sum(p["z"] for p in pts) / len(pts)}

    def _slugs(self):
        """world/locations/<slug>.html; a name whose slug is taken gets its region added."""
        seen = set()
        for l in self.locs:
            s = slug(l["name"])
            if s in seen:
                s = f"{s}-{l['region']}"
            n = 2
            while s in seen:
                s = f"{slug(l['name'])}-{n}"
                n += 1
            seen.add(s)
            l["slug"] = s
            l["path"] = f"world/locations/{s}.html"

    def in_region(self, key):
        return [l for l in self.locs if l["region"] == key]

    def alpine_box(self, pad=400):
        """Himfjäll has no region border in markers.json: the box around its locations (corners (x, z))."""
        a = self.in_region("alpine")
        return ((min(l["x"] for l in a) - pad, min(l["z"] for l in a) - pad),
                (max(l["x"] for l in a) + pad, max(l["z"] for l in a) + pad))

    def crate_ids(self, locs):
        """The distinct crate spawn point ids of these locations. A few ids are listed under two neighbouring
        locations (the lists are 'own file first, nearest first'), so summing the list lengths would count them
        twice."""
        return set().union(*(self.crates.get(str(l["hash"]), []) for l in locs))

    def markers_of(self, sub=None, main=None, region=None):
        out = self.markers
        if sub:
            out = [m for m in out if m["s"] == sub]
        if main:
            out = [m for m in out if self.subs[m["s"]]["main"] == main]
        if region:
            out = [m for m in out if m["r"] == region]
        return out

    def nearest_loc(self, p, exclude=None):
        best, bd = None, 1e18
        for l in self.locs:
            if l is exclude:
                continue
            d = dist(l, p)
            if d < bd:
                best, bd = l, d
        return best, bd

    # ------------------------------------------------------------ safehouses
    def _safehouses(self, gd, mk):
        """gamedata safehouses (id, name, start) + the playersafehouses marker with the same name (coordinates),
        the location they belong to and their house photo."""
        pos = {m["n"]: m for m in mk["items"] if m["s"] == "playersafehouses"}
        photos = [m for m in mk["items"] if m["s"] == "safehousehints"]
        loc_by_name = {norm(l["name"]): l for l in self.locs}
        self.start_ids = gd["safehouses"].get("start", [])
        self.safehouses = []
        for reg in gd["safehouses"]["regions"]:
            for s in reg["list"]:
                m = pos.get(s["name"])
                sh = dict(s, region=reg["key"], x=m["x"] if m else None, z=m["z"] if m else None,
                          map_region=m["r"] if m else None, slug="sh-" + slug(s["name"]))
                sh["loc"], sh["photo"] = None, None
                if m:
                    same = loc_by_name.get(norm(s["name"]))
                    near, d = self.nearest_loc(sh)
                    if same and dist(same, sh) < 600:
                        sh["loc"] = same
                    elif d <= SAFEHOUSE_AT:
                        sh["loc"] = near
                    ph = min(photos, key=lambda p: dist(p, sh))
                    if dist(ph, sh) <= PHOTO_AT:
                        sh["photo"] = ph
                self.safehouses.append(sh)
        self.safehouses_at = collections.defaultdict(list)
        for sh in self.safehouses:
            if sh["loc"]:
                self.safehouses_at[sh["loc"]["hash"]].append(sh)

    def nearest_safehouse(self, p):
        best = min((s for s in self.safehouses if s["x"] is not None), key=lambda s: dist(s, p))
        return best, dist(best, p)

    # ------------------------------------------------------------ control points and beacons
    def _control_points(self):
        """Control point markers (the map's base markers) joined with the control point locations of the same
        name; three markers in the Mountains have no location of their own."""
        locs = {l["name"]: l for l in self.locs if l["kind"] == "controlpoint"}
        self.cps = []
        for m in sorted(self.markers_of("controlpoints"), key=lambda m: norm(m["n"])):
            loc = locs.get(m["n"])
            near, d = self.nearest_loc(m, exclude=loc)
            self.cps.append(dict(m, loc=loc, near=near, near_d=d, slug="cp-" + slug(m["n"]),
                                 region=loc["region"] if loc else m["r"]))

    def _beacons(self):
        """Beacon markers with their nearest location, and the same markers grouped into sites: markers within
        BEACON_SITE m of each other (seven bounty-nest markers sit together at the Vesslan Command Bunker)."""
        self.beacons, self.beacon_sites = {}, {}
        for sub in ("relaybeacons", "sovietbeacons"):
            rows = []
            for m in self.markers_of(sub):
                near, d = self.nearest_loc(m)
                rows.append(dict(m, near=near, near_d=d))
            rows.sort(key=lambda b: (REGION_KEYS.index(b["r"]), norm(b["near"]["name"])))
            self.beacons[sub] = rows
            self.beacon_sites[sub] = self._group(rows, BEACON_SITE)

    @staticmethod
    def _group(rows, radius):
        """Single-linkage groups of points closer than radius to one another (list of lists, first-seen order)."""
        groups = []
        for r in rows:
            touching = [g for g in groups if any(dist(r, o) <= radius for o in g)]
            merged = [r] + [o for g in touching for o in g]
            groups = [g for g in groups if g not in touching] + [merged]
        order = {id(r): i for i, r in enumerate(rows)}
        groups = [sorted(g, key=lambda r: order[id(r)]) for g in groups]
        return sorted(groups, key=lambda g: order[id(g[0])])

    # ------------------------------------------------------------ placed loot
    def _loot(self, loot):
        """Every placed loot row counts for its nearest location when that is within LOOT_RADIUS. A 400 m grid keeps
        this fast (45,000 rows x 359 locations)."""
        self.loot_subs = loot["subs"]
        self.loot_mains = {m["key"]: m["name"] for m in loot["mains"]}
        self.loot_names = loot["names"]
        self.loot_regions = loot["regions"]
        cell = 2 * LOOT_RADIUS
        grid = collections.defaultdict(list)
        for l in self.locs:
            grid[(int(l["x"] // cell), int(l["z"] // cell))].append(l)
        self.loot_at = collections.defaultdict(list)       # location hash -> [(sub, name)]
        self.loot_by_region = collections.defaultdict(collections.Counter)   # region -> Counter(sub key)
        self.loot_rare = collections.defaultdict(list)       # region -> [(q, name, x, z)] Q4+ weapons
        for si, x, z, ni, ri, _y in loot["items"]:
            sub = self.loot_subs[si]
            self.loot_by_region[self.loot_regions[ri]][sub["key"]] += 1
            if sub["main"] == "loot_weapons" and sub["q"] >= 4:
                self.loot_rare[self.loot_regions[ri]].append((sub["q"], self.loot_names[ni], x, z))
            gx, gz = int(x // cell), int(z // cell)
            best, bd = None, LOOT_RADIUS
            for i in (gx - 1, gx, gx + 1):
                for j in (gz - 1, gz, gz + 1):
                    for l in grid.get((i, j), ()):
                        d = math.hypot(l["x"] - x, l["z"] - z)
                        if d <= bd:
                            best, bd = l, d
            if best:
                self.loot_at[best["hash"]].append((sub, self.loot_names[ni]))

    # ------------------------------------------------------------ missions
    def _missions(self, md):
        """Missions per region, and the locations each mission's text names. A name inside a longer location name
        ('Måsskär' in 'Måsskär Radar Station') only counts where the longer one doesn't match."""
        self.missions = md["missions"]
        self.missions_in = collections.defaultdict(list)
        for m in self.missions:
            self.missions_in[m["region"]].append(m)
        pats = [(l, re.compile(r"(?<!\w)(?:" + "|".join(map(re.escape, self.mission_names(l))) + r")(?!\w)"))
                for l in self.locs if l["name"] not in MISSION_SKIP]
        self.missions_naming = collections.defaultdict(list)
        for m in self.missions:
            text = "\n".join([m["name"], m.get("summary") or "", m.get("description") or ""]
                             + [s.get("name") or "" for s in m["steps"]])
            spans = [(mt.start(), mt.end(), l) for l, p in pats for mt in p.finditer(text)]
            hit = set()
            for a, b, l in spans:
                if not any(a2 <= a and b <= b2 and (b2 - a2) > (b - a) for a2, b2, _ in spans):
                    hit.add(l["hash"])
            for h in hit:
                self.missions_naming[h].append(m)

    def mission_names(self, l):
        """The names a mission text may use for a location, longest first: its own name and, for the seven
        Command Bunkers, the code name ('Sorken') and '<Region> Command Bunker' ('Farmlands Command Bunker'), which
        is how the Warboard missions refer to them."""
        names = [l["name"]]
        if l["name"].endswith(" Command Bunker"):
            region = self.marker_region_name.get(l["region"], "").replace(" Region", "")
            names += [f"{region} Command Bunker", l["name"][:-len(" Command Bunker")]]
        return names

    # ------------------------------------------------------------ challenges
    def _challenges(self, gd):
        """The challenge whose tiers say 'Missions in the <Region> Region' (or 'on Himfjäll') belongs to that region;
        Kill Switch counts relay beacons."""
        self.region_challenge, self.beacon_challenge = {}, None
        for tree in gd["challenges"]:
            for c in tree["challenges"]:
                text = " ".join(t["desc"] for t in c["tiers"])
                for k, name in REGIONS:
                    if f"in the {name} Region" in text:
                        self.region_challenge[k] = (c, tree)
                if "on Himfjäll" in text:
                    self.region_challenge["alpine"] = (c, tree)
                if "Relay Beacons" in text:
                    self.beacon_challenge = (c, tree)


_WORLD = None


def world(site):
    global _WORLD
    if _WORLD is None or _WORLD[0] is not site:
        _WORLD = (site, World(site))
    return _WORLD[1]


# ---------------------------------------------------------------------------------------------------------------
# registration
# ---------------------------------------------------------------------------------------------------------------
def region_aliases(w, key):
    name = REGION_NAME[key]
    al = [key, name, f"{name} Region", w.marker_region_name.get(key, "")]
    if key == "alpine":
        al += ["Alpine Unrest", "Himfjäll", "Himfjall", "Alpine Unrest Island"]
    h = w.region_hash.get(norm("Alpine Unrest" if key == "alpine" else name))
    if h:
        al.append(str(h))
    return al


def collect(site):
    w = world(site)
    for key, name in REGIONS:
        site.register("region", key, f"world/{key}.html", name, aliases=region_aliases(w, key),
                      desc=f"Region: {len(w.in_region(key))} locations. " + REGION_BLURB[key],
                      keywords="region map " + key)
    for l in w.locs:
        site.register("location", l["name"], l["path"], l["name"], icon=f"img/locations/{l['icon']}.png",
                      aliases=[str(l["hash"]), l["id"]],
                      desc=f"{l['type'] or KIND_ONE[l['kind']]} · {REGION_NAME[l['region']]}",
                      keywords=f"location {KIND_ONE[l['kind']]} {l['region']} {l['id']}")
    for sh in w.safehouses:
        site.register("safehouse", sh["name"], f"world/safehouses.html#{sh['slug']}", sh["name"],
                      aliases=[sh["id"]], icon="map/map/icons/safehouses.png",
                      desc=f"Safehouse · {REGION_NAME[sh['region']]}" + (" · starting safehouse" if sh["start"] else ""),
                      keywords="safehouse spawn fast travel")
    for cp in w.cps:
        site.register("controlpoint", cp["n"], f"world/control-points.html#{cp['slug']}", cp["n"],
                      icon="img/locations/cp_resistance.png", search=cp["loc"] is None,
                      desc=f"Control point · {REGION_NAME[cp['region']]}", keywords="control point home base")


# ---------------------------------------------------------------------------------------------------------------
# shared bits of the pages
# ---------------------------------------------------------------------------------------------------------------
def loc_link(site, l):
    return f'<a class="ll" href="~/{l["path"]}">{loc_icon(site, l)}{esc(l["name"])}</a>'


def sh_link(sh):
    return f'<a href="~/world/safehouses.html#{sh["slug"]}">{esc(sh["name"])}</a>'


def mission_rows(site, missions):
    rows = []
    for m in sorted(missions, key=lambda m: (m["type"] != "main", norm(m["name"]))):
        rows.append([site.link("mission", m["name"]), pack_tags(m),
                     site.link("region", m["region"]) if m["region"] in REGION_NAME else "Anywhere",
                     esc(m.get("summary") or "")])
    return rows


def marker_counts_table(site, w, region=None):
    """Collectibles, schematic points and house photos per type (markers.json)."""
    rows = []
    for key, sub in w.subs.items():
        if sub["main"] not in ("collectibles", "schematics", "housephotos"):
            continue
        n = len(w.markers_of(key, region=region))
        if not n:
            continue
        dlc = sum(1 for m in w.markers_of(key, region=region) if m["d"])
        rows.append([marker_icon(site, sub) + site.link("collectible-type", key, sub["name"]),
                     esc(w.mains[sub["main"]]), n, sub["count"],
                     tag(f"{dlc} Alpine Unrest", "dlc") if dlc else ""])
    return table(["Type", "Group", "Here" if region else "Markers", "Whole map", "DLC"], rows, cls="compact")


def loot_summary_rows(site, w, counter):
    """counter: Counter(loot sub key). One row per loot category with the per-quality / per-type breakdown."""
    by_main = collections.defaultdict(list)
    for sub in w.loot_subs:
        if counter.get(sub["key"]):
            by_main[sub["main"]].append(sub)
    rows = []
    for main, subs in by_main.items():
        total = sum(counter[s["key"]] for s in subs)
        if main in ("loot_weapons", "loot_attachments"):
            parts = " ".join(f'{qbadge(s["q"], short=True)} {fmt(counter[s["key"]])}' for s in subs)
        else:
            parts = ", ".join(f'{esc(s["name"])} {fmt(counter[s["key"]])}'
                              for s in sorted(subs, key=lambda s: -counter[s["key"]]))
        # the crates of the map layer are named apart from the location files' crate spawn points (see CRATE_NOTE)
        label = "Crate spots (map layer)" if main == "loot_crates" else w.loot_mains[main]
        rows.append([esc(label), total, parts])
    return rows


CRATE_NOTE = ("<b>Two crate numbers.</b> The <i>crate spawn points</i> are the <code>CLootCrateSpawnPoint</code> objects "
              "listed in the location files: what your save tracks for a location's loot progress. The <i>crate spots "
              "(map layer)</i> are every crate spot of the interactive map's loot layer {where}, whichever game file "
              "it comes from, so the two numbers rarely match. Neither means a crate is always there: the game may "
              "leave a spot empty.")


# ---------------------------------------------------------------------------------------------------------------
# world/index.html
# ---------------------------------------------------------------------------------------------------------------
def region_counts(w, key):
    locs = w.in_region(key)
    ms = w.missions_in.get(key, [])
    return {
        "locations": len(locs),
        "safehouses": sum(1 for s in w.safehouses if s["region"] == key),
        "controlpoints": sum(1 for c in w.cps if c["region"] == key),
        "collectibles": len(w.markers_of(main="collectibles", region=key)),
        "schematics": len(w.markers_of(main="schematics", region=key)),
        "photos": len(w.markers_of(main="housephotos", region=key)),
        "relay": len(w.markers_of("relaybeacons", region=key)),
        "main": sum(1 for m in ms if m["type"] == "main"),
        "side": sum(1 for m in ms if m["type"] == "side"),
        "crates": len(w.crate_ids(locs)),
        "kinds": collections.Counter(l["kind"] for l in locs),
    }


def unreleased_note(w):
    """' (6 of them unreleased, in the files only)' for the mission total."""
    n = sum(1 for m in w.missions if m.get("unreleased") or m["pack"] == "dlc03")
    return f" ({n} of them unreleased, in the files only)" if n else ""


def cp_region_note(w):
    """Footnote: the control points without a map location get their region from the region borders."""
    nol = [cp for cp in w.cps if not cp["loc"]]
    if not nol:
        return ""
    names = ", ".join(esc(cp["n"].replace(" Control Point", "")) for cp in nol)
    regs = sorted({cp["region"] for cp in nol}, key=REGION_KEYS.index)
    txt = (f"Control points include {len(nol)} {' and '.join(esc(REGION_NAME[r]) for r in regs)} markers ({names}) "
           "that are not map locations, which is why the Locations by kind table below doesn't count them. Their "
           "region comes from the map's region borders")
    odd = [cp for cp in nol if cp["near"]["region"] != cp["region"]]
    for cp in odd:
        txt += (f", so {esc(cp['n'].replace(' Control Point', ''))} counts as {esc(REGION_NAME[cp['region']])} "
                f"although it sits next to {esc(cp['near']['name'])} ({esc(REGION_NAME[cp['near']['region']])}, "
                f"{metres(cp['near_d'])} away)")
    return note(txt + ".", "data")


def build_index(site, w):
    body = []
    total_m = len(w.missions)
    body.append("<p>Each card below opens a region page with every location in it, its safehouses, control points, "
                "missions and collectibles. The counts come straight from the game files: locations are the named "
                "places the map marks as discovered, missions are counted by the region in their briefing.</p>")
    items = []
    for key, name in REGIONS:
        c = region_counts(w, key)
        sub = (f"{c['locations']} locations · {c['safehouses']} safehouses<br>{c['main'] + c['side']} missions · "
               f"{c['collectibles']} collectibles<br>{esc(REGION_SHORT[key])}")
        items.append({"href": f"~/world/{key}.html", "title": name, "sub": sub,
                      "tag": "DLC" if key in REGION_DLC else "", "color": "#5f4258" if key not in REGION_DLC else "#8a6d1f"})
    body.append(cards(items))

    body.append(bar("Map of the regions"))
    body.append("<p>The coloured outlines are the region borders from the map data; click a region to open its "
                "page. Each name sits at the middle of the region (the average position of its locations). "
                "Himfjäll has no border in the map data, so the dashed box simply frames its locations. For every "
                'marker, open the <a href="~/map/index.html">interactive map</a>.</p>')
    body.append(overview_map(site, w))

    body.append(bar("Regions compared"))
    body.append("<p>One row per region. <b>Main</b> and <b>Side</b> are missions, <b>Schematics</b> the schematic "
                "points, <b>Photos</b> the house photos and <b>Beacons</b> the relay beacon markers. <b>Crate spawn "
                "points</b> are the distinct loot crate spawn points the region's location files list (the game may "
                "not fill every one). <b>Collectibles</b> counts the map markers of the collectible types. Click a "
                "header to sort.</p>")
    rows = []
    for key, name in REGIONS:
        c = region_counts(w, key)
        rows.append([site.link("region", key) + " " + region_tag(key), c["locations"], c["safehouses"],
                     c["controlpoints"], c["main"], c["side"], c["collectibles"], c["schematics"], c["photos"],
                     c["relay"], c["crates"]])
    glob = [m for m in w.missions if m["region"] not in REGION_NAME]
    body.append(table(["Region", "Locations", "Safehouses", "Control points", "Main", "Side",
                       "Collectibles", "Schematics", "Photos", "Beacons", "Crate spawn points"], rows))
    body.append(cp_region_note(w))
    if glob:
        body.append(f"<p>{len(glob)} of the {total_m} missions have no single region (their briefing names none):</p>")
        body.append(table(["Mission", "Type", "Summary"], [[r[0], r[1], r[3]] for r in mission_rows(site, glob)],
                          cls="missions"))

    body.append(bar("Locations by kind"))
    body.append("<p>How many locations of each kind every region has. The kinds are the groups of the map's location "
                "filter; the icon is the one the in-game map uses. Click a kind's name in the "
                f'<a href="~/world/locations.html">full location list</a> to filter by it.</p>')
    rows = []
    per = {k: region_counts(w, k)["kinds"] for k in REGION_KEYS}
    for kind in w.kinds:
        ex = next((l for l in w.locs if l["kind"] == kind), None)
        if not ex:
            continue
        rows.append([loc_icon(site, ex) + esc(w.kind_plural[kind])]
                    + [per[k].get(kind, 0) or '<span class="dim" data-v="0">–</span>' for k in REGION_KEYS]
                    + [sum(per[k].get(kind, 0) for k in REGION_KEYS)])
    rows.append(["<b>All</b>"] + [len(w.in_region(k)) for k in REGION_KEYS] + [len(w.locs)])
    body.append(table(["Kind"] + [REGION_NAME[k].split(" (")[0] for k in REGION_KEYS] + ["Total"], rows,
                      cls="compact kinds", num=set(range(1, len(REGION_KEYS) + 2))))

    body.append(bar("More about the world"))
    body.append("<ul>"
                f'<li><a href="~/world/locations.html">All {len(w.locs)} locations</a> in one filterable table.</li>'
                f'<li><a href="~/world/safehouses.html">All {len(w.safehouses)} safehouses</a> with their positions '
                "and house photos.</li>"
                f'<li><a href="~/world/control-points.html">Control points and beacons</a>: the {len(w.cps)} bases '
                f'you can take, {len(w.beacons["relaybeacons"])} relay beacon markers and the Soviet beacons.</li>'
                "<li>The Collectibles and Keys pages of this tab, and the "
                '<a href="~/map/index.html">interactive map</a> with every marker.</li></ul>')
    lead = (f"<p>Generation Zero is set in Östertörn, a fictional part of Sweden, in 1989. The game files split the "
            f"world into <b>{len(REGIONS)} regions</b> with <b>{len(w.locs)} named locations</b>, "
            f"<b>{len(w.safehouses)} safehouses</b> and <b>{total_m} missions</b>{unreleased_note(w)}. Seven regions are on the mainland "
            f"and its islands; the eighth, Himfjäll, comes with the {site.link('dlc', 'Alpine Unrest')} "
            f"expansion.</p>")
    site.page("world/index.html", "The world", "\n".join(body), "world", sub="regions", lead=lead, head_extra=CSS,
              desc="The regions of Generation Zero: locations, safehouses, control points, missions and "
                   "collectibles per region.", search={"k": "World", "w": "regions map world"})


# ---------------------------------------------------------------------------------------------------------------
# world/<region>.html
# ---------------------------------------------------------------------------------------------------------------
def region_lead(site, w, key):
    c = region_counts(w, key)
    top = [k for k, _ in c["kinds"].most_common(3)]
    pos = w.centre[key]
    d = dist(pos, w.world_centre)
    where = "in the middle of the map" if d < 1200 else f"in the {COMPASS_WORD[compass(w.world_centre, pos)]} of the map"
    dlc = (f" It is the {site.link('dlc', REGION_DLC[key])} region: you need that expansion to go there."
           if key in REGION_DLC else "")
    return (f"<p>{esc(REGION_BLURB[key])}</p>"
            f"<p>The {esc(REGION_NAME[key])} region lies {where}. The game files place <b>{c['locations']} "
            f"locations</b> here, most of them {', '.join(esc(w.kind_plural[k].lower()) for k in top)}, with "
            f"<b>{c['safehouses']} safehouses</b>, {c['controlpoints'] or 'no'} control points and "
            f"<b>{c['main'] + c['side']} missions</b>.{dlc}</p>")


def build_region(site, w, key):
    name = REGION_NAME[key]
    c = region_counts(w, key)
    locs = w.in_region(key)
    body = []

    body.append(bar("Map"))
    body.append("<p>Every location in the region (yellow pins; hover for the name). Drag to pan and zoom with the "
                "buttons or the mouse wheel.</p>")
    cen = w.centre[key]
    body.append(minimap(cen["x"], cen["z"], name, zoom=2, height=560,
                        markers=[(l["x"], l["z"], l["name"]) for l in locs]))

    # ---- locations by kind
    body.append(bar("Locations", f"{len(locs)} in total"))
    body.append("<p>Grouped by the kind the map filters by. The small line under each name is the type the game "
                "shows for it; <b>crates</b> is the number of loot crate spawn points in its files, and "
                "<b>safehouse</b> marks a location with a safehouse.</p>")
    for kind in w.kinds:
        group = [l for l in locs if l["kind"] == kind]
        if not group:
            continue
        body.append(f'<h3>{loc_icon(site, group[0], "lic big")}{esc(w.kind_plural[kind])} <small class="dim">'
                    f"{len(group)}</small></h3>")
        body.append('<ul class="loclist">')
        for l in group:
            n = len(w.crates.get(str(l["hash"]), []))
            extra = []
            if n:
                extra.append(f"{n} crate{'s' if n != 1 else ''}")
            if w.safehouses_at.get(l["hash"]):
                extra.append('<span class="shmark">safehouse</span>')
            body.append(f'<li><a href="~/{l["path"]}">{loc_icon(site, l)}<span><b>{esc(l["name"])}</b>'
                        f'<small>{esc(l["type"] or KIND_ONE[l["kind"]])}{" · " if extra else ""}{" · ".join(extra)}'
                        f"</small></span></a></li>")
        body.append("</ul>")

    # ---- safehouses
    shs = [s for s in w.safehouses if s["region"] == key]
    body.append(bar("Safehouses", f"{len(shs)}"))
    body.append("<p>Safehouses are where you can respawn and fast travel to once they are unlocked. "
                f'See <a href="~/world/safehouses.html">all safehouses</a> for the whole map.</p>')
    body.append(safehouse_table(site, w, shs))

    # ---- control points
    cps = [cp for cp in w.cps if cp["region"] == key]
    if cps:
        body.append(bar("Control points", f"{len(cps)}"))
        body.append('<p>Bases you can capture and make your home base. How they work is explained on the '
                    '<a href="~/world/control-points.html">control points page</a>.</p>')
        body.append(table(["Control point", "Nearest other location", "Coordinates"],
                          [[cp_name(site, cp), loc_link(site, cp["near"]) + f' <span class="dim">{metres(cp["near_d"])}'
                            f"</span>", coords(cp)] for cp in cps], cls="compact"))

    # ---- missions
    ms = w.missions_in.get(key, [])
    body.append(bar("Missions", f"{c['main']} main · {c['side']} side"))
    body.append("<p>Missions whose briefing places them in this region, main missions first.</p>")
    if ms:
        rows = [[r[0], r[1], r[3]] for r in mission_rows(site, ms)]   # the region column is this page
        body.append(table(["Mission", "Type", "Summary"], rows, cls="missions"))
    else:
        body.append("<p>No missions are listed for this region.</p>")
    ch = w.region_challenge.get(key)
    if ch:
        c0, tree = ch
        last = c0["tiers"][-1]
        body.append(note(f"The challenge {site.link('challenge', c0['name'])} ({esc(tree['name'].title())} tree) "
                         f"has {len(c0['tiers'])} tiers here; the last one reads: “{esc(last['desc'])}”."))

    # ---- collectibles
    body.append(bar("Collectibles"))
    body.append("<p>Map markers of each collectible type, schematic point and house photo in this region. "
                "<b>Here</b> is the count in this region, <b>whole map</b> the total of that type. The region of a "
                "marker comes from the region borders of the map.</p>")
    body.append(marker_counts_table(site, w, region=key))

    # ---- loot overview
    counter = w.loot_by_region.get(key, {})
    if counter:
        body.append(bar("Placed loot"))
        body.append("<p>Loot that the game files put at fixed spots in this region (the <i>Extra Locations</i> layer "
                    "of the interactive map). Weapons and attachments are split by quality.</p>")
        body.append(table(["Category", "Count", "Breakdown"], loot_summary_rows(site, w, counter), cls="compact"))
        body.append(note(CRATE_NOTE.format(where="in this region") +
                         f" This region's location files list {fmt(c['crates'])} distinct crate spawn points.", "data"))
    rare = w.loot_rare.get(key)
    if rare:
        body.append("<p>The Exceptional and Special quality weapons placed in the region, with the location each one "
                    "is nearest to. These are the best fixed weapon pickups here, worth a detour early on.</p>")
        body.append(rare_table(site, w, rare))

    ib = infobox(name, [
        ("Internal key", f"<code>{esc(key)}</code>"),
        ("Region hash", f"<code>{w.region_hash.get(norm('Alpine Unrest' if key == 'alpine' else name), '')}</code>"),
        ("Map name", esc(w.marker_region_name.get(key, ""))),
        ("Locations", fmt(c["locations"])),
        ("Safehouses", fmt(c["safehouses"])),
        ("Control points", fmt(c["controlpoints"])),
        ("Missions", f"{c['main']} main, {c['side']} side"),
        ("Collectibles", fmt(c["collectibles"])),
        ("Relay beacon markers", fmt(c["relay"])),
        ("Crate spawn points", fmt(c["crates"])),
        ("Content", region_tag(key) or "Base game"),
    ], subtitle="Region")
    nav = region_nav(key)
    site.page(f"world/{key}.html", name, "\n".join(body) + nav, "world", sub="regions",
              crumbs=[("Regions", "~/world/index.html")], lead=region_lead(site, w, key), infobox_html=ib,
              kind="Region", head_extra=CSS, desc=f"{name}: {c['locations']} locations, {c['safehouses']} safehouses, "
                                                  f"{c['main'] + c['side']} missions.")


def rare_table(site, w, rare):
    """Q4+ placed weapons [(q, name, x, z)]: where each one is."""
    rows = []
    for q, name, x, z in sorted(rare, key=lambda r: (-r[0], norm(r[1]))):
        p = {"x": x, "z": z}
        near, d = w.nearest_loc(p)
        rows.append([loot_item_link(site, "loot_weapons", name), qbadge(q),
                     loc_link(site, near) + f' <span class="dim">{metres(d)} {compass(near, p)}</span>', coords(p)])
    return table(["Weapon", "Quality", "Nearest location (distance, direction from it)", "Coordinates"], rows,
                 cls="compact")


def region_nav(key):
    i = REGION_KEYS.index(key)
    prev_k, next_k = REGION_KEYS[i - 1], REGION_KEYS[(i + 1) % len(REGION_KEYS)]
    return (f'<div class="pnav"><a href="~/world/{prev_k}.html">← {esc(REGION_NAME[prev_k])}</a>'
            f'<a href="~/world/{next_k}.html">{esc(REGION_NAME[next_k])} →</a></div>')


# ---------------------------------------------------------------------------------------------------------------
# world/locations.html
# ---------------------------------------------------------------------------------------------------------------
def build_locations(site, w):
    body = []
    chips_k = "".join(f'<button class="chip" data-g="kind" data-f="{k}">{esc(w.kind_plural[k])}</button>'
                      for k in w.kinds if any(l["kind"] == k for l in w.locs))
    chips_r = "".join(f'<button class="chip" data-g="region" data-f="{k}">{esc(n.split(" (")[0])}</button>'
                      for k, n in REGIONS)
    body.append("<p>Type to filter by name, type or internal id, and use the chips to pick kinds and regions (several "
                "chips of one row can be on at once). Coordinates are world positions in metres as the interactive "
                "map shows them: x grows to the east, z to the south. <b>Crates</b> is the number of loot crate "
                "spawn points in the location's files.</p>")
    body.append('<div class="filterbar" data-for="loctable"><input placeholder="Filter locations...">'
                '<button class="chip on" data-g="kind" data-f="*">All kinds</button>' + chips_k + "</div>")
    body.append('<div class="filterbar" data-for="loctable"><button class="chip on" data-g="region" data-f="*">'
                'All regions</button>' + chips_r + '<span class="count"></span></div>')
    rows = []
    for l in w.locs:
        rows.append((l, [loc_link(site, l), esc(KIND_ONE[l["kind"]]), esc(l["type"]),
                         site.link("region", l["region"], REGION_NAME[l["region"]].split(" (")[0]),
                         round(l["x"]), round(l["z"]), len(w.crates.get(str(l["hash"]), [])),
                         f'<code>{esc(l["id"])}</code>']))
    html = table(["Location", "Kind", "In-game type", "Region", "X", "Z", "Crates", "Internal id"], [r for _, r in rows],
                 cls="compact loctable")
    # data-f on each row for the chips (table() has no row attributes, so add them afterwards in order)
    parts = html.split("<tr>")
    out = [parts[0], "<tr>" + parts[1]]       # parts[1] is the header row
    for (l, _), p in zip(rows, parts[2:]):
        out.append(f'<tr data-f="{l["kind"]} {l["region"]}" data-w="{esc(l["id"])}">' + p)
    body.append('<div id="loctable">' + "".join(out) + "</div>")
    lead = (f"<p>All <b>{len(w.locs)}</b> named locations of the map in one table: farms, villages, bunkers, military "
            f"bases, FNIX and Soviet sites and the control points. Each name opens the location's own page with a map, "
            f"the locations around it, collectibles, loot and missions.</p>")
    site.page("world/locations.html", "All locations", "\n".join(body), "world", sub="locations", lead=lead,
              wide=True, head_extra=CSS, desc=f"Every one of the {len(w.locs)} locations in Generation Zero with "
                                              "kind, region and coordinates.", search={"k": "World", "w": "locations"})


# ---------------------------------------------------------------------------------------------------------------
# world/locations/<slug>.html
# ---------------------------------------------------------------------------------------------------------------
def location_lead(site, w, l, nearby):
    reg = site.link("region", l["region"], REGION_NAME[l["region"]])
    out = f"<p><b>{esc(l['name'])}</b> is {type_phrase(l)} in the {reg} region"
    if l["region"] in REGION_DLC:
        out += f" (part of the {site.link('dlc', REGION_DLC[l['region']])} expansion)"
    out += "."
    if nearby:
        o, d = nearby[0]
        out += (f" The nearest other location is {site.link('location', o['name'])}, {metres(d)} to the "
                f"{COMPASS_WORD[compass(l, o)]}.")
    n = len(w.crates.get(str(l["hash"]), []))
    if n:
        out += f" Its files hold <b>{n}</b> loot crate spawn point{'s' if n != 1 else ''}."
    out += "</p>"
    if l["name"] == "Unknown":
        out += note("“Unknown” is the name the game files themselves give this location.", "data")
    return out


def build_location(site, w, l):
    others = sorted(((o, dist(l, o)) for o in w.locs if o is not l), key=lambda x: x[1])
    nearby = others[:NEARBY_COUNT]
    body = []

    # ---- map
    body.append(bar("Map"))
    close = [(o, d) for o, d in nearby if d <= 1000][:6]
    body.append(minimap(l["x"], l["z"], l["name"], zoom=3, height=320,
                        markers=[(o["x"], o["z"], o["name"]) for o, _ in close]))

    # ---- nearby locations
    body.append(bar("Nearby locations"))
    body.append(f"<p>The {len(nearby)} closest locations, measured in a straight line between the map markers "
                "(1 world unit is 1 metre), with the direction to go from here.</p>")
    body.append(table(["Location", "Kind", "Region", "Distance", "Direction"],
                      [[loc_link(site, o), esc(KIND_ONE[o["kind"]]), site.link("region", o["region"],
                        REGION_NAME[o["region"]].split(" (")[0]), f'<span data-v="{d:.0f}">{metres(d)}</span>',
                        compass(l, o)] for o, d in nearby], cls="compact", num={3}))

    # ---- safehouse
    body.append(bar("Safehouse"))
    here = w.safehouses_at.get(l["hash"], [])
    sh, d = w.nearest_safehouse(l)
    if here:
        s = here[0]
        txt = f"<p>There is a safehouse here: {sh_link(s)}"
        if s["start"]:
            txt += ", the safehouse every new character starts with"
        txt += f" ({metres(dist(s, l))} from the location marker)."
        if s["photo"]:
            txt += f" Its {site.link('collectible-type', 'safehousehints', 'house photo')} lies next to it."
        body.append(txt + "</p>")
    else:
        body.append(f"<p>No safehouse here. The nearest one is {sh_link(sh)} ({site.link('region', sh['region'], REGION_NAME[sh['region']])}), "
                    f"{metres(d)} to the {COMPASS_WORD[compass(l, sh)]}.</p>")

    # ---- map markers within NEAR_MARKERS
    near_m = sorted(((m, dist(l, m)) for m in w.markers if w.subs[m["s"]]["main"] in MARKER_GROUPS
                     and dist(l, m) <= NEAR_MARKERS), key=lambda x: x[1])
    body.append(bar("Collectibles and markers nearby"))
    if near_m:
        body.append(f"<p>Collectibles, schematic points, house photos, control points and beacons within "
                    f"{NEAR_MARKERS} m of the location marker, nearest first. The last column is the internal place "
                    f"name the game files give the marker.</p>")
        rows = []
        for m, dm in near_m:
            sub = w.subs[m["s"]]
            name = esc(m["n"])
            if m["s"] == "controlpoints":
                name = cp_name(site, next(c for c in w.cps if c["n"] == m["n"]))
            rows.append([marker_icon(site, sub) + site.link("collectible-type", m["s"], sub["name"])
                         if sub["main"] in ("collectibles", "schematics", "housephotos") else
                         marker_icon(site, sub) + f'<a href="~/world/control-points.html">{esc(sub["name"])}</a>',
                         name + (" " + tag("Alpine Unrest", "dlc") if m["d"] else ""),
                         f'<span data-v="{dm:.0f}">{metres(dm)}</span>', compass(l, m),
                         f'<span class="dim">{esc(m["l"])}</span>' if m["l"] else ""])
        body.append(table(["Type", "Name", "Distance", "Direction", "Place"], rows, cls="compact", num={2}))
    else:
        body.append(f"<p>No collectibles, schematic points, house photos or beacons within {NEAR_MARKERS} m.</p>")

    # ---- loot
    body.append(bar("Loot"))
    n = len(w.crates.get(str(l["hash"]), []))
    loot = w.loot_at.get(l["hash"], [])
    txt = (f"<p>The location's files list <b>{n}</b> loot crate spawn point{'s' if n != 1 else ''} "
           f"(<code>CLootCrateSpawnPoint</code>). These are the crates your save counts for this location's loot "
           f"progress. </p>" if n else
           "<p>The location's files list no loot crate spawn points of their own.</p>")
    body.append(txt)
    if loot:
        counter = collections.Counter(s["key"] for s, _ in loot)
        body.append(f"<p>Placed loot within {LOOT_RADIUS} m that is closer to {esc(l['name'])} than to any other "
                    "location (from the interactive map's <i>Extra Locations</i> layer).</p>")
        body.append(table(["Category", "Count", "Breakdown"], loot_summary_rows(site, w, counter), cls="compact"))
        if counter.keys() & {s["key"] for s in w.loot_subs if s["main"] == "loot_crates"}:
            body.append(note(CRATE_NOTE.format(where=f"within {LOOT_RADIUS} m that is nearer to this location than "
                                                     "to any other"), "data"))
        fixed = collections.Counter((s["main"], s.get("q", 0), name) for s, name in loot
                                    if s["main"] in ("loot_weapons", "loot_attachments", "loot_misc"))
        if fixed:
            body.append("<p>Weapons, attachments and other single items placed here:</p>")
            body.append(table(["Item", "Quality", "Count"],
                              [[loot_item_link(site, main, name), qbadge(q) if q else "", cnt]
                               for (main, q, name), cnt in sorted(fixed.items(), key=lambda x: (-x[0][1], x[0][2]))],
                              cls="compact"))
    else:
        body.append(f"<p>No placed loot within {LOOT_RADIUS} m is assigned to this location.</p>")

    # ---- missions
    ms = w.missions_naming.get(l["hash"], [])
    body.append(bar("Missions"))
    if ms:
        alt = w.mission_names(l)[1:]
        also = f" (or {' or '.join('“' + esc(a) + '”' for a in alt)}, as the missions also call it)" if alt else ""
        body.append(f"<p>Missions whose name, briefing or steps mention {esc(l['name'])}{also}.</p>")
        body.append(table(["Mission", "Type", "Region", "Summary"], mission_rows(site, ms), cls="missions"))
    else:
        body.append(f"<p>No mission text mentions {esc(l['name'])} by name. See the "
                    f"{site.link('region', l['region'], REGION_NAME[l['region']] + ' region page')} for the missions "
                    "of the region.</p>")

    body.append(note(f"Distances are straight lines on the map between marker positions. A location's area in the game "
                     f"is not a circle, so the {NEAR_MARKERS} m and {LOOT_RADIUS} m radii above are a practical "
                     f"approximation, not the game's own borders.", "data"))

    ib_rows = [
        ("Kind", esc(KIND_ONE[l["kind"]])),
        ("In-game type", esc(l["type"]) or "–"),
        ("Region", site.link("region", l["region"], REGION_NAME[l["region"]]) + " " + region_tag(l["region"])),
        ("Coordinates", coords(l)),
        ("Internal id", f"<code>{esc(l['id'])}</code>"),
        ("Hash", f"<code>{l['hash']}</code>"),
        ("Crate spawn points", fmt(n)),
        ("Safehouse", sh_link(here[0]) if here else f"Nearest: {sh_link(sh)}, {metres(d)}"),
        ("Map icon", f"<code>{esc(l['icon'])}</code>"),
    ]
    cp = next((c for c in w.cps if c["loc"] is l), None)
    if cp:
        ib_rows.insert(3, ("Control point", cp_name(site, cp)))
    ib = infobox(l["name"], ib_rows, image=f"~/img/locations/{l['icon']}.png", subtitle=esc(l["type"] or KIND_ONE[l["kind"]]),
                 cls="locbox")
    site.page(l["path"], l["name"], "\n".join(body), "world", sub="locations",
              crumbs=[("Locations", "~/world/locations.html"),
                      (REGION_NAME[l["region"]], f"~/world/{l['region']}.html")],
              lead=location_lead(site, w, l, nearby), infobox_html=ib, toc=False,
              kind=f"Location · {KIND_ONE[l['kind']]}", head_extra=CSS,
              desc=f"{l['name']}: {l['type'] or KIND_ONE[l['kind']]} in {REGION_NAME[l['region']]}, Generation Zero.")


def loot_item_link(site, main, name):
    """A placed weapon 'Möller PP (Worn)' links to its weapon page; the rest stays text."""
    if main == "loot_weapons":
        base = re.sub(r"\s*\([^)]*\)$", "", name)
        return site.link("weapon", base, name)
    if main == "loot_attachments":
        base = re.sub(r"\s*\([^)]*\)$", "", name)
        return site.link("attachment", base, name)
    return esc(name)


# ---------------------------------------------------------------------------------------------------------------
# world/safehouses.html
# ---------------------------------------------------------------------------------------------------------------
def safehouse_table(site, w, shs):
    rows = []
    for s in sorted(shs, key=lambda s: norm(s["name"])):
        name = f'<span id="{s["slug"]}"></span><b>{esc(s["name"])}</b>'
        if s["start"]:
            name += " " + tag("Start", "green")
        rows.append([name, loc_link(site, s["loc"]) if s["loc"] else '<span class="dim">–</span>',
                     "Yes" if s["photo"] else '<span class="dim">No</span>',
                     coords(s) if s["x"] is not None else "–", f'<code>{esc(s["id"])}</code>'])
    return table(["Safehouse", "Location", "House photo", "Coordinates", "Object id"], rows, cls="compact")


def build_safehouses(site, w):
    body = []
    start = [s for s in w.safehouses if s["start"]]
    photos = sum(1 for s in w.safehouses if s["photo"])
    body.append(bar("Map of all safehouses"))
    body.append("<p>Every safehouse on one map; hover a dot for its name and click it to jump to its row. "
                "Click inside a region to open the region page. The maps further down zoom in on each region.</p>")
    dots = [(s["x"], s["z"], s["name"] + (" (starting safehouse)" if s["start"] else ""), f'#{s["slug"]}',
             "main" if s["start"] else "dot") for s in w.safehouses if s["x"] is not None]
    body.append(overview_map(site, w, dots=sorted(dots, key=lambda d: d[4] == "main"),
                             caption=f"Large pink dot: {', '.join(esc(s['name']) for s in start)}, the starting "
                                     "safehouse."))

    body.append(bar("How safehouses work"))
    body.append("<ul>"
                "<li>An unlocked safehouse is a respawn point and a fast travel destination.</li>"
                f"<li>Your save keeps the list of unlocked safehouses (the <i>Safe houses unlocked</i> stat counts "
                f"them). {', '.join(sh_link(s) for s in start)} is unlocked on a new character.</li>"
                f"<li>{photos} of the {len(w.safehouses)} safehouses have a "
                f"{site.link('collectible-type', 'safehousehints', 'house photo')} collectible placed right next to "
                f"them (within {PHOTO_AT} m); the Himfjäll safehouses have none.</li>"
                "<li>The <b>Location</b> column links the map location the safehouse sits in (same name, or within "
                f"{SAFEHOUSE_AT} m); hidden camps and caves are often not a named location of their own.</li></ul>")
    others = [i for i in w.start_ids if i not in {s["id"] for s in w.safehouses}]
    if others:
        body.append(note("The game data lists one more start spawn point, " + ", ".join(f"<code>{esc(i)}</code>" for i in others)
                         + ", that is not one of the map's safehouses.", "data"))

    for key, name in REGIONS:
        shs = [s for s in w.safehouses if s["region"] == key]
        body.append(bar(name, f"{len(shs)} safehouses", id=key))
        body.append(table_intro(site, key, shs))
        body.append(safehouse_table(site, w, shs))
        body.append(region_safehouse_map(w, key, shs))
    lead = (f"<p>Generation Zero has <b>{len(w.safehouses)} safehouses</b> in {len(REGIONS)} regions. This page lists "
            f"them all with their positions, the location they belong to, whether a house photo marks them and the "
            f"object id the save uses. The starting safehouse is {', '.join(esc(s['name']) for s in start)} in the "
            f"Archipelago.</p>")
    site.page("world/safehouses.html", "Safehouses", "\n".join(body), "world", sub="safehouses", lead=lead,
              head_extra=CSS, desc=f"All {len(w.safehouses)} safehouses in Generation Zero by region, with coordinates.",
              search={"k": "World", "w": "safehouses fast travel respawn"})


def region_safehouse_map(w, key, shs):
    """A region's safehouses; the pink first pin is the starting safehouse if the region has it, otherwise the
    safehouse nearest the middle of the region."""
    placed = [s for s in shs if s["x"] is not None]
    if not placed:
        return ""
    first = next((s for s in placed if s["start"]), None) or min(placed, key=lambda s: dist(s, w.centre[key]))
    why = "the starting safehouse" if first["start"] else "the safehouse nearest the middle of the region"
    pts = [(s["x"], s["z"], s["name"]) for s in [first] + [s for s in placed if s is not first]]
    return (minimap(pts[0][0], pts[0][1], pts[0][2], zoom=2, height=460, markers=pts[1:])
            + f'<p class="dim mmcap">Pink pin: {esc(first["name"])}, {why}. Yellow pins: the other safehouses.</p>')


def table_intro(site, key, shs):
    return (f"<p>{len(shs)} safehouses in the {site.link('region', key, REGION_NAME[key])} region"
            f"{' (' + tag(REGION_DLC[key], 'dlc') + ')' if key in REGION_DLC else ''}.</p>")


# ---------------------------------------------------------------------------------------------------------------
# world/control-points.html
# ---------------------------------------------------------------------------------------------------------------
def cp_name(site, cp):
    if cp["loc"]:
        return site.link("location", cp["loc"]["name"])
    return f'<a href="~/world/control-points.html#{cp["slug"]}">{esc(cp["n"])}</a>'


def build_control_points(site, w):
    body = []
    relay, soviet = w.beacons["relaybeacons"], w.beacons["sovietbeacons"]
    bb = site.find("mission", "Building Blocks")

    # ---- control points
    body.append(bar("Control points", f"{len(w.cps)}"))
    body.append("<p>A control point is a base you can take. Once it is yours it can become a <b>home base</b>: every "
                "control point has a player spawn point on top of it, and you can build defences there. The save "
                "records who holds each one: you and the Resistance, FNIX, or nobody (neutral). A control point FNIX "
                "holds is a FNIX base and has to be taken back.</p>")
    if bb:
        body.append(f"<p>Base building starts with the main mission {site.link('mission', 'Building Blocks')}, "
                    "whose last steps are “Claim the Control Point” and “Start building your own base”. "
                    f"The defence missions of the {site.link('mission', 'Our New Home [Home Base Defense · Easy]', 'Our New Home')} "
                    "series take place at a home base.</p>")
    cnt = collections.Counter(cp["region"] for cp in w.cps)
    body.append("<p>By region: " + ", ".join(f"{site.link('region', k, REGION_NAME[k])} {cnt[k]}"
                                            for k in REGION_KEYS if cnt[k]) + ". "
                + ", ".join(esc(REGION_NAME[k]) for k in REGION_KEYS if not cnt[k]) + " have none.</p>")
    body.append(overview_map(site, w, dots=[(cp["x"], cp["z"], cp["n"], f'#{cp["slug"]}', "dot") for cp in w.cps],
                             caption="Every control point; hover a dot for its name and click it to jump to its row."))
    rows = []
    for cp in w.cps:
        sh, d = w.nearest_safehouse(cp)
        rows.append([f'<span id="{cp["slug"]}"></span>' + (loc_link(site, cp["loc"]) if cp["loc"] else
                     f'{site.img("img/locations/cp_resistance.png", cls="lic")}<b>{esc(cp["n"])}</b>'),
                     site.link("region", cp["region"], REGION_NAME[cp["region"]]),
                     loc_link(site, cp["near"]) + f' <span class="dim">{metres(cp["near_d"])}</span>',
                     sh_link(sh) + f' <span class="dim">{metres(d)}</span>', coords(cp)])
    body.append("<p>The <b>nearest location</b> column helps you find each one; the nearest safehouse is where you "
                "would fast travel to before an attack.</p>")
    body.append(table(["Control point", "Region", "Nearest location", "Nearest safehouse", "Coordinates"], rows,
                      cls="compact"))
    nol = [cp for cp in w.cps if not cp["loc"]]
    if nol:
        body.append(note(f"{len(nol)} control points ({', '.join(esc(c['n']) for c in nol)}) have a map marker but no "
                         f"map location of their own, so they don't count as locations to discover. The region of "
                         f"these comes from the map's region borders.", "data"))

    # ---- relay beacons
    bounty = [b for b in relay if "Bounty" in b["l"]]
    body.append(bar("Relay beacons", f"{len(relay)}"))
    body.append("<p>Relay beacons are machine nests: machine-built transmitters that show on the map as <i>Unknown "
                "signal interference</i>. Destroying one disables the nest; the save then marks that nest location "
                "as switched off, and the <i>Relay Beacons disabled</i> stat goes up.</p>")
    if w.beacon_challenge:
        c0, tree = w.beacon_challenge
        body.append(f"<p>The challenge {site.link('challenge', c0['name'])} ({esc(tree['name'].title())} tree) "
                    f"rewards destroying them: {'; '.join(esc(t['desc']) for t in c0['tiers'])}.</p>")
    sites = w.beacon_sites["relaybeacons"]
    body.append(f"<p>The map data has <b>{len(relay)} relay beacon markers</b> at <b>{len(sites)} sites</b>: markers "
                f"within {BEACON_SITE} m of each other are counted as one site below. {len(bounty)} of the markers come "
                "from the bounty nest files (marked <b>Bounty</b>). The sites are listed by region, with the nearest "
                "location to help you find them.</p>")
    mc = collections.Counter(b["r"] for b in relay)
    sc = collections.Counter(g[0]["r"] for g in sites)
    body.append("<p>Markers by region (sites in brackets where they differ): " + ", ".join(
        f"{site.link('region', k, REGION_NAME[k])} {mc[k]}" + (f" ({sc[k]} sites)" if sc[k] != mc[k] else "")
        for k in REGION_KEYS if mc[k]) + ".</p>")
    body.append(overview_map(site, w, dots=[(b["x"], b["z"], "Relay beacon" + (" (bounty nest)" if "Bounty" in b["l"]
                                                                                 else ""), None,
                                             "main" if "Bounty" in b["l"] else "dot") for b in relay],
                             caption="Every relay beacon marker. Large pink dots: bounty nests."))
    body.append(beacon_table(site, w, sites, bounty=True))
    for g in sites:
        if len(g) > 1:
            span = max(dist(a, b) for a in g for b in g)
            body.append(note(f"{len(g)} {'bounty-nest ' if all('Bounty' in b['l'] for b in g) else ''}markers sit "
                             f"within {span:.0f} m of each other at {site.link('location', g[0]['near']['name'])}: on "
                             "the ground that is one nest site, so the table shows it as one row.", "data"))

    # ---- soviet beacons
    body.append(bar("Soviet beacons", f"{len(soviet)}"))
    dfa = site.find("mission", "Death from above")
    body.append(f"<p>Three Soviet beacons on the North Coast are marked <i>Broadcasting to Soviet forces</i>. "
                + (f"The side mission {site.link('mission', 'Death from above')} has the step “Take out the Soviet "
                   "beacons”, right after reaching the planned landing point of Firebird reinforcements. " if dfa
                   else "") + "</p>")
    pts = [(b["x"], b["z"], "") for b in soviet]
    body.append(minimap(pts[0][0], pts[0][1], "Soviet beacon", zoom=3, height=300, markers=pts[1:]))
    body.append(beacon_table(site, w, w.beacon_sites["sovietbeacons"]))

    lead = ("<p>Control points are the bases of the Resistance war against FNIX: places you capture, turn into a home "
            "base and defend. Beacons are the machines' own markers on the map: relay beacons (machine nests) you "
            "destroy, and the Soviet beacons on the North Coast. This page lists every one from the game files, with "
            "maps.</p>")
    site.page("world/control-points.html", "Control points & beacons", "\n".join(body), "world", sub="controlpoints",
              lead=lead, head_extra=CSS, desc="Every control point, relay beacon and Soviet beacon in Generation Zero.",
              search={"k": "World", "w": "control points home base relay beacons nests soviet beacons"})


def beacon_table(site, w, sites, bounty=False):
    """One row per beacon site (a list of markers; the first one gives the position)."""
    out = []
    for g in sites:
        b = g[0]
        r = [site.link("region", b["r"], REGION_NAME[b["r"]]), loc_link(site, b["near"]) +
             f' <span class="dim">{metres(b["near_d"])} {compass(b["near"], b)}</span>', coords(b), len(g)]
        if bounty:
            r.append(tag("Bounty", "soviet") if "Bounty" in b["l"] else "")
        out.append(r)
    return table(["Region", "Nearest location (distance, direction from it)", "Coordinates", "Markers"] +
                 (["Nest"] if bounty else []), out, cls="compact")


# ---------------------------------------------------------------------------------------------------------------
def build(site):
    w = world(site)
    build_index(site, w)
    for key in REGION_KEYS:
        build_region(site, w, key)
    build_locations(site, w)
    for l in w.locs:
        build_location(site, w, l)
    build_safehouses(site, w)
    build_control_points(site, w)
