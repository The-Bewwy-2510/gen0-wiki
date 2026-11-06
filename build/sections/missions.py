"""Missions tab: the overview, the Warboard arcs, one list page per content pack, one page per mission, the
challenges browser and the Steam achievements.

Pages
  missions/index.html          overview: a short intro, cards to the sub pages, missions per region
  missions/arcs.html           the three Warboard arcs
  missions/base-game.html      one page per pack (also alpine-unrest, fnix-rising, unreleased): a "Main missions"
                               and a "Side missions" section, each with one closed fold per region
                               (ids main-<region key> / side-<region key>)
  missions/<slug>.html         one page per mission
  missions/challenges.html     the challenge trees (tiles with their tier nodes; click one for its details)
  missions/achievements.html   the 72 Steam achievements

Data (build/data):
  missions.json  packs     base / alpine (Alpine Unrest) / fnix (FNIX Rising) / dlc03 (missions of a third expansion
                           that is in the files but was never released)
                 missions  in the order of the game's mission table: id, name, type (main / side), pack, region (a
                           region key, or "global" when the mission is not tied to one), arc (the Warboard arc
                           Answers / Payback / Safety, base game only), unreleased, summary, description (the mission
                           log briefing), steps (the objectives the game shows: id, name, deps = objective ids that
                           must be done first, opt = optional, count = how many times it has to be done). Hidden
                           script steps (no on-screen text) are not in the list, so a dependency can point at an
                           objective id that isn't shown.
  gamedata.json  challenges  six challenge trees -> challenges -> tiers (start / req = the challenge's progress
                             counter at the start / end of the tier, desc, title = the title the tier awards)
                 locations   every map location (name, type, kind, region, x, z): we search the mission texts for
                             these names and link them
  markers.json   collectible counts for the challenges that ask you to collect things
  achievements.json  the Steam achievements (name, desc, icon, hidden), read from the Steam client's own copy of
                     the game's achievement schema, icons from Steam's image server (see its _about)
  steam.json     store pictures and release dates for the pack pages
  mission_starts.json  the "Mission Start" of each mission page's infobox on the Fandom wiki (place and coordinates,
                       which are the same x / z as our map), shown in a "Mission start" box in the right-hand rail of
                       the mission pages; CC BY-SA, credited there

Kinds registered: 'mission' (name; aliases the mission id as a string), 'mission-region' (region key -> the pack page
holding most of that region's main missions, #main-<key>), 'challenge' (challenge name, alias its key like '02_03';
also the tree names 'TRUTH' ... as anchors on the challenges page), 'achievement' (achievement name).
"""
import collections
import math
import re

from wiki.site import esc, slug, norm, fmt, table, infobox, bar, fold, panel, note, kv, minimap, maplink, tag, \
    cards, REGIONS

CSS = '<link rel="stylesheet" href="~/assets/missions.css">'
JS = '<script src="~/assets/missions.js" defer></script>'
REGION_NAME = dict(REGIONS)
REGION_NAME["global"] = "No region in the files"
REGION_ORDER = [k for k, _ in REGIONS] + ["global"]
# the plain region names as the mission and challenge texts spell them ("... in the South Coast Region")
REGION_TEXT = {k: ("Himfjäll" if k == "alpine" else n) for k, n in REGIONS}

PACKS = ["base", "alpine", "fnix", "dlc03"]
PACK_NAME = {"base": "Base game", "alpine": "Alpine Unrest", "fnix": "FNIX Rising", "dlc03": "Unreleased"}
PACK_PAGE = {"base": "missions/base-game.html", "alpine": "missions/alpine-unrest.html",
             "fnix": "missions/fnix-rising.html", "dlc03": "missions/unreleased.html"}
PACK_SUB = {"base": "base", "alpine": "alpine", "fnix": "fnix", "dlc03": "unreleased"}
PACK_TAG_CLS = {"base": "base", "alpine": "dlc", "fnix": "dlc", "dlc03": "unreleased"}
PACK_APPID = {"base": 704270, "alpine": 1157550, "fnix": 1301740}
PACK_BLURB = {
    "base": "The missions of Generation Zero itself, including everything added by free updates. They are grouped "
            "by region, main missions first; open a region to see its missions in the order of the game's mission "
            "table.",
    "alpine": "The Alpine Unrest expansion's missions, all set on the island of Himfjäll, in the order of the game's "
              "mission table, which follows the expansion's story.",
    "fnix": "The FNIX Rising expansion's missions, spread over the Archipelago, Farmlands and South Coast, in the order "
            "of the game's mission table.",
    "dlc03": "Six missions of a third expansion that are in the current game files but are not part of the released "
             "game, so you can't play them. The files give them no region.",
}
ARCS = ["Answers", "Payback", "Safety"]
TYPE_NAME = {"main": "Main missions", "side": "Side missions"}
RESERVED = {"index", "arcs", "base-game", "alpine-unrest", "fnix-rising", "unreleased", "challenges", "achievements"}

# machine types linked when an objective names them (singular or plural)
MACHINE_WORDS = {"Runner": "Runner", "Runners": "Runner", "Tick": "Tick", "Ticks": "Tick", "Seeker": "Seeker",
                 "Seekers": "Seeker", "Hunter": "Hunter", "Hunters": "Hunter", "Harvester": "Harvester",
                 "Harvesters": "Harvester", "Tank": "Tank", "Tanks": "Tank", "Firebird": "Firebird",
                 "Firebirds": "Firebird", "Lynx": "Lynx", "Wolf": "Wolf", "Wolves": "Wolf"}
LOCATION_SKIP = {"Unknown"}   # location names too generic to look for in the texts
# The base game's FNIX storyline (Network Infiltration ... Launch Site Bravo) sits at the end of the mission table and
# each briefing picks up where the previous one ends.
LATE_STORY_FROM = 141
# Missions after this table position come after the expansion entries in the table (later free updates); the region
# challenges' text predates them, so we don't claim they count.
ORIGINAL_TABLE_END = 125
# region names a briefing may use without the word "Region" (Forest and Mountains are also ordinary words)
PLAIN_REGION_NAMES = ["Archipelago", "Farmlands", "South Coast", "Marshlands", "North Coast"]


# ---------------------------------------------------------------------------------------------------------------
# the data model, built once per site
# ---------------------------------------------------------------------------------------------------------------
class Missions:
    def __init__(self, site):
        md = site.data("missions")
        gd = site.data("gamedata")
        self.missions = []
        used = set(RESERVED)
        for i, m in enumerate(md["missions"]):
            m = dict(m)
            m["idx"] = i + 1                                   # position in the game's mission table
            s = slug(m["name"])
            while s in used:
                s += "-mission"
            used.add(s)
            m["path"] = f"missions/{s}.html"
            self.missions.append(m)
        self.by_name = {norm(m["name"]): m for m in self.missions}
        self.trees = gd["challenges"]
        self.locs = [l for l in gd["locations"]["list"] if l["name"] not in LOCATION_SKIP]
        self.loc_by_name = {l["name"]: l for l in self.locs}
        self.markers = site.data("markers")
        # where each mission starts, from the Fandom wiki's mission infoboxes (see mission_starts.json _about)
        self.starts = site.data("mission_starts")["starts"]
        self._groups()
        self._text_patterns()
        self._challenge_links()

    @staticmethod
    def order_key(m):
        """Inside a group: the order of the game's mission table."""
        return m["idx"]

    def _groups(self):
        """(pack, type) -> missions in table order; (pack, type, region) -> missions; arc -> missions; each
        mission's neighbours in its pack / type list and in its arc."""
        self.groups = collections.OrderedDict()
        self.by_region = collections.OrderedDict()
        for p in PACKS:
            for t in ("main", "side"):
                ms = sorted((m for m in self.missions if m["pack"] == p and m["type"] == t), key=self.order_key)
                if ms:
                    self.groups[(p, t)] = ms
                for r in REGION_ORDER:
                    rs = [m for m in ms if m["region"] == r]
                    if rs:
                        self.by_region[(p, t, r)] = rs
        self.arcs = {a: sorted((m for m in self.missions if m.get("arc") == a),
                               key=lambda m: (REGION_ORDER.index(m["region"]), m["idx"])) for a in ARCS}
        # list neighbours follow the pack page: region by region, then table order
        seqs = [[m for (p2, t2, r), rs in self.by_region.items() if (p2, t2) == k for m in rs] for k in self.groups]
        for seq_name, ss in (("list", seqs), ("arc", self.arcs.values())):
            for seq in ss:
                for i, m in enumerate(seq):
                    m[seq_name + "_prev"] = seq[i - 1] if i else None
                    m[seq_name + "_next"] = seq[i + 1] if i + 1 < len(seq) else None

    def region_home(self, key):
        """The pack whose page holds most of a region's main missions (for 'mission-region' links)."""
        best = max(PACKS, key=lambda p: (len(self.by_region.get((p, "main", key), [])),
                                         len(self.by_region.get((p, "side", key), []))))
        return best if self.by_region.get((best, "main", key)) else None

    # ------------------------------------------------------------ names to link inside the texts
    def _text_patterns(self):
        word = r"(?<![\wÅÄÖåäöÉé])({})(?![\wÅÄÖåäöÉé])"
        # the texts call the Command Bunkers by their code names ("the Minken bunker", "Vesslan"), the map by
        # '<code name> Command Bunker': link the bare code name to the bunker
        self.loc_alias = {l["name"][:-len(" Command Bunker")]: l["name"] for l in self.locs
                          if l["name"].endswith(" Command Bunker")}
        names = sorted(list(self.loc_by_name) + list(self.loc_alias), key=len, reverse=True)   # longest first
        self.loc_re = re.compile(word.format("|".join(map(re.escape, names))))
        # region names only when the text says "... Region" (plain "forest" or "mountains" are ordinary words)
        reg = "|".join(re.escape(n) for k, n in REGION_TEXT.items() if k != "alpine")
        self.region_re = re.compile(r"\b(" + reg + r") [Rr]egion\b")
        self.island_re = re.compile(r"(?<!\w)(Himfjäll)(?!\w)")     # the Alpine Unrest island, named without "Region"
        self.machine_re = re.compile(word.format("|".join(sorted(MACHINE_WORDS, key=len, reverse=True))))

    def places_in(self, m):
        """Locations named in a mission's texts: [(location, where)] in order of first mention."""
        found = collections.OrderedDict()
        parts = [("summary", m.get("summary", "")), ("briefing", m.get("description", ""))] + \
                [("objectives", s["name"]) for s in m.get("steps", [])]
        for where, text in parts:
            for hit in self.loc_re.findall(text or ""):
                hit = self.loc_alias.get(hit, hit)
                found.setdefault(hit, [])
                if where not in found[hit]:
                    found[hit].append(where)
        return [(self.loc_by_name[n], w) for n, w in found.items()]

    # ------------------------------------------------------------ which challenges name which missions
    def _challenge_links(self):
        """self.ch_missions[challenge key] = [(mission, tier numbers or None, how)];
        self.mission_ch[mission id] = [(tree, challenge, tiers, how)]."""
        self.ch_missions = collections.defaultdict(list)
        self.mission_ch = collections.defaultdict(list)
        self.region_ch = {}     # region key -> (tree, challenge, excluded mission names)

        def add(tree, c, m, tiers, how):
            if any(x[0] is m for x in self.ch_missions[c["key"]]):
                return
            self.ch_missions[c["key"]].append((m, tiers, how))
            self.mission_ch[m["id"]].append((tree, c, tiers, how))

        for tree in self.trees:
            for c in tree["challenges"]:
                for n, t in enumerate(c["tiers"], 1):
                    d = t["desc"]
                    # "Complete the mission "Our New Home" on Easy difficulty."
                    for q, diff in re.findall(r'"([^"]+)"(?: on (Easy|Medium|Hard) difficulty)?', d):
                        name = f"{q} [Home Base Defense · {diff}]" if diff else q
                        m = self.by_name.get(norm(name))
                        if m and "excluding" not in d.split(f'"{q}"')[0][-25:]:
                            add(tree, c, m, [n], "named")
                    # a list of missions, one per line: "- The Enemy of my Enemy"
                    for line in re.findall(r"^- (.+)$", d, re.M):
                        m = self.by_name.get(norm(line))
                        if m:
                            add(tree, c, m, None, "listed")
                    if 'Side Missions of the "FNIX Rising" expansion' in d:
                        for m in self.missions:
                            if m["pack"] == "fnix" and m["type"] == "side":
                                add(tree, c, m, None, "pack")
                    if "Command Bunker Warboard" in d:
                        for m in self.missions:
                            if m in self.warboard_missions() or m["name"] == "The Command Bunker Network":
                                add(tree, c, m, None, "warboard")
                text = " ".join(t["desc"] for t in c["tiers"])
                for k, name in REGION_TEXT.items():
                    if f"Missions in the {name} Region" in text:
                        excluded = re.findall(r'excluding the mission "([^"]+)"', text)
                        self.region_ch[k] = (tree, c, excluded)

    def warboard_missions(self):
        """The base-game missions that activate a Command Bunker Warboard: The Home Team (Vesslan, objective
        'Examine the Vesslan Warboard') and the six 'Warboard - X Bunker' missions. (The Hellmouth's 'Warboard room'
        is in Alpine Unrest's Bergfinken, not a Command Bunker.)"""
        return [m for m in self.missions if m["pack"] == "base" and m["name"] != "The Command Bunker Network" and
                any(re.search(r"\bWarboard\b", s["name"]) for s in m.get("steps", []))]

    def regions_named(self, m):
        """Regions a mission's texts place it in: the regions of the places it names, plus region names."""
        text = " ".join([m.get("summary", ""), m.get("description", "")] + [s["name"] for s in m.get("steps", [])])
        found = {l["region"] for l, _ in self.places_in(m)}
        for k, n in REGION_TEXT.items():
            if n in PLAIN_REGION_NAMES and re.search(r"\b" + re.escape(n) + r"\b", text) or \
                    re.search(r"\b" + re.escape(n) + r" [Rr]egion\b", text):
                found.add(k)
        return [k for k in REGION_ORDER if k in found]


def is_late_story(m):
    return m["pack"] == "base" and m["type"] == "main" and m["idx"] >= LATE_STORY_FROM


_MS = None


def model(site):
    global _MS
    if _MS is None or _MS[0] is not site:
        _MS = (site, Missions(site))
    return _MS[1]


# ---------------------------------------------------------------------------------------------------------------
# registration
# ---------------------------------------------------------------------------------------------------------------
def challenge_anchor(c):
    return slug(c["name"])


def tree_anchor(tree):
    return "tree-" + slug(tree["name"])


def fold_id(t, region):
    return f"{t}-{region}"


def ach_anchor(a):
    return "ach-" + slug(a["name"])


def collect(site):
    ms = model(site)
    for m in ms.missions:
        words = [m["type"], m["pack"], PACK_NAME[m["pack"]], REGION_NAME[m["region"]], m.get("arc", ""), "mission"]
        site.register("mission", m["name"], m["path"], m["name"], icon="img/locations/mission_objective.png",
                      desc=f"{'Main' if m['type'] == 'main' else 'Side'} mission · {REGION_NAME[m['region']]}"
                           f" · {PACK_NAME[m['pack']]}. {m.get('summary', '')}",
                      aliases=[str(m["id"])], keywords=" ".join(w for w in words if w))
    for k, name in REGIONS:
        p = ms.region_home(k)
        if p:
            site.register("mission-region", k, f"{PACK_PAGE[p]}#{fold_id('main', k)}", f"Missions in {name}",
                          aliases=[name], search=False)
    for tree in ms.trees:
        site.register("challenge", tree["name"], f"missions/challenges.html#{tree_anchor(tree)}",
                      f"{tree['name'].title()} challenges", desc=f"Challenge tree with {len(tree['challenges'])} "
                      f"challenges" + (" (DLC)" if tree["dlc"] else ""), aliases=[f"tree {tree['tree']}"])
        for c in tree["challenges"]:
            last = c["tiers"][-1]
            site.register("challenge", c["name"], f"missions/challenges.html#{challenge_anchor(c)}", c["name"],
                          aliases=[c["key"]], keywords=f"challenge {tree['name']} title " +
                          " ".join(t["title"] for t in c["tiers"] if t.get("title")),
                          desc=f"{tree['name']} challenge, {len(c['tiers'])} tiers up to {fmt(last['req'])}. "
                               f"Final title: {last.get('title', '')}.")
    for a in site.data("achievements")["achievements"]:
        site.register("achievement", a["name"], f"missions/achievements.html#{ach_anchor(a)}", a["name"],
                      icon=a["icon"], desc=("Secret Steam achievement" if a["hidden"] else "Steam achievement") +
                      f": {a['desc']}", keywords="achievement steam trophy" + (" secret hidden" if a["hidden"] else ""))


# ---------------------------------------------------------------------------------------------------------------
# small shared bits
# ---------------------------------------------------------------------------------------------------------------
def pack_tag(p):
    return tag(PACK_NAME[p], PACK_TAG_CLS[p])


def type_tag(t):
    return tag("Main" if t == "main" else "Side", t)


def region_link(site, key):
    if key == "global":
        return '<span class="dim">No region</span>'
    return site.link("region", key, REGION_NAME[key])


def mlink(m):
    """Link to one of our own mission pages (always exists, so no registry lookup needed)."""
    return f'<a href="~/{m["path"]}">{esc(m["name"])}</a>'


def pack_link(p, text=None):
    return f'<a href="~/{PACK_PAGE[p]}">{esc(text or PACK_NAME[p])}</a>'


def arc_link(a):
    return f'<a href="~/missions/arcs.html#arc-{slug(a)}">{esc(a)}</a>'


def linkify(site, ms, text, linked, machines=False):
    """Escape text and turn location names, '<Region> region' and (optionally) machine types into links. Each
    target is linked once per `linked` set (the caller decides the scope: briefing, objectives ...)."""
    pats = [("loc", ms.loc_re), ("region", ms.region_re), ("region", ms.island_re)] + \
        ([("machine", ms.machine_re)] if machines else [])
    hits = []
    for kind, rx in pats:
        for mt in rx.finditer(text):
            hits.append((mt.start(), mt.end(), kind, mt.group(1), mt.group(0)))
    hits.sort(key=lambda h: (h[0], -h[1]))
    out, pos = [], 0
    for start, end, kind, key, whole in hits:
        if start < pos:          # overlaps a longer match we already used
            continue
        out.append(esc(text[pos:start]))
        if kind == "loc":
            target = ("location", ms.loc_alias.get(key, key))
        elif kind == "region":
            target = ("region", next(k for k, n in REGION_TEXT.items() if n == key))
        else:
            target = ("machine", MACHINE_WORDS[key])
        if target in linked or not site.find(*target):
            out.append(esc(whole))
        else:
            linked.add(target)
            out.append(site.link(target[0], target[1], whole))
        pos = end
    out.append(esc(text[pos:]))
    return "".join(out)


def briefing_html(site, ms, text, linked):
    """The mission log text: paragraphs, '- ' lists, and the bracketed notes some briefings start with."""
    out = []
    for para in re.split(r"\n\s*\n", text.strip()):
        lines = para.split("\n")
        if all(l.startswith("- ") for l in lines):
            out.append("<ul>" + "".join(f"<li>{linkify(site, ms, l[2:], linked)}</li>" for l in lines) + "</ul>")
        elif para.startswith("[") and para.endswith("]"):
            inner = "<br>".join(linkify(site, ms, l, linked) for l in para[1:-1].split("\n"))
            out.append(f'<p class="bnote">{inner}</p>')
        else:
            out.append("<p>" + "<br>".join(linkify(site, ms, l, linked) for l in lines) + "</p>")
    return '<div class="briefing">' + "".join(out) + "</div>"


def obj_counts(m):
    steps = m.get("steps", [])
    nopt = sum(1 for s in steps if s.get("opt"))
    return len(steps) - nopt, nopt


DATA_NOTE = ("Mission names, summaries, briefings and objectives are the game's own English text, read from its "
             "mission table. A mission's region comes from the <i>Location</i> line of its briefing or, without "
             "one, from the map files the mission uses. The objective lists show what the game's mission log shows; "
             "some missions also run hidden script steps in between, which have no text and are left out.")


# ---------------------------------------------------------------------------------------------------------------
def build(site):
    ms = model(site)
    build_index(site, ms)
    build_arcs(site, ms)
    for p in PACKS:
        build_pack(site, ms, p)
    for m in ms.missions:
        build_mission(site, ms, m)
    build_challenges(site, ms)
    build_achievements(site, ms)


# ---------------------------------------------------------------------------------------------------------------
# missions/index.html
# ---------------------------------------------------------------------------------------------------------------
def build_index(site, ms):
    n = len(ms.missions)
    count = collections.Counter((m["pack"], m["type"]) for m in ms.missions)
    mains = sum(v for (p, t), v in count.items() if t == "main")
    sides = n - mains
    n_ch = sum(len(t["challenges"]) for t in ms.trees)
    achs = site.data("achievements")["achievements"]
    lead = (f"<p>Generation Zero has <b>{n} missions</b> in the current game files: {mains} main missions that tell "
            f"the story and {sides} side missions. Missions are handed out by the people, radios and notes you find "
            f"around Östertörn, and the Command Bunker Warboards group many of the base game's main missions into "
            f"three arcs. Each mission has its own page with the briefing, every objective and the places it sends "
            f"you to.</p>")
    sb = site.data("steam")
    img = {d["appid"]: d.get("image") for d in sb["dlc"]}
    img[sb["game"]["appid"]] = sb["game"].get("image")

    def pimg(p):
        path = img.get(PACK_APPID.get(p))
        return "~/" + path if path and site.has_file(path) else None

    items = []
    for p in PACKS:
        sub = (f"{count[(p, 'main')]} main · {count[(p, 'side')]} side missions" +
               ("<br>In the files, not in the game" if p == "dlc03" else ""))
        it = {"href": "~/" + PACK_PAGE[p], "title": PACK_NAME[p], "sub": sub,
              "tag": "DLC" if p in ("alpine", "fnix") else ("Files only" if p == "dlc03" else ""),
              "color": {"base": "#1d4039", "alpine": "#2f5e7a", "fnix": "#7a2a26", "dlc03": "#6b2a5e"}[p]}
        if pimg(p):
            it["img"] = pimg(p)
        items.append(it)
    more = [
        {"href": "~/missions/arcs.html", "title": "Warboard arcs", "color": "#1f6b5c",
         "sub": f"{sum(len(v) for v in ms.arcs.values())} base-game main missions in the arcs "
                f"{', '.join(ARCS[:-1])} and {ARCS[-1]}", "img": "~/img/locations/mission_objective.png"},
        {"href": "~/missions/challenges.html", "title": "Challenges", "color": "#8a6d1f",
         "sub": f"{n_ch} challenges in {len(ms.trees)} trees; every tier awards a title"},
        {"href": "~/missions/achievements.html", "title": "Achievements", "color": "#47545a",
         "sub": f"The {len(achs)} Steam achievements, grouped by what they ask for",
         "img": next(("~/" + a["icon"] for a in achs if a["name"] == "It's The Final Countdown"
                      and site.has_file(a["icon"])), None)},
    ]
    for it in more:
        if not it.get("img"):
            it.pop("img", None)
    body = [bar("Mission lists", id="lists"),
            "<p>One page per content pack, each with the main and the side missions grouped by region.</p>",
            cards(items),
            bar("More", id="more"), cards(more)]
    # missions per region: each count opens that pack page at the region
    rrows = []
    for k in REGION_ORDER:
        cells = []
        total = 0
        for p in PACKS:
            nm = len(ms.by_region.get((p, "main", k), []))
            ns = len(ms.by_region.get((p, "side", k), []))
            total += nm + ns
            if nm or ns:
                bits = []
                if nm:
                    bits.append(f'<a href="~/{PACK_PAGE[p]}#{fold_id("main", k)}">{nm} main</a>')
                if ns:
                    bits.append(f'<a href="~/{PACK_PAGE[p]}#{fold_id("side", k)}">{ns} side</a>')
                cells.append((" · ".join(bits), nm + ns))
            else:
                cells.append(None)
        if total:
            rrows.append([region_link(site, k)] + cells + [total])
    body.append(bar("Missions by region", id="regions"))
    body.append("<p>Click a number to open that region on its pack page.</p>")
    body.append(table(["Region"] + [PACK_NAME[p] for p in PACKS] + ["Total"], rrows, cls="compact counts ovtable",
                      num={len(PACKS) + 1}))
    body.append(note(DATA_NOTE, "data"))
    ib = infobox("Missions", [
        ("Missions", f"{n}"), ("Main", f"{mains}"), ("Side", f"{sides}"),
        (None, "By pack"),
        *[(PACK_NAME[p], pack_link(p, f"{count[(p, 'main')] + count[(p, 'side')]}")) for p in PACKS],
        (None, "Progress"),
        ("Warboard arcs", f'<a href="~/missions/arcs.html">{len(ARCS)}</a>'),
        ("Challenges", f'<a href="~/missions/challenges.html">{n_ch}</a>'),
        ("Steam achievements", f'<a href="~/missions/achievements.html">{len(achs)}</a>'),
    ])
    site.page("missions/index.html", "Missions", "\n".join(body), "missions", lead=lead, head_extra=CSS,
              infobox_html=ib,
              desc=f"All {n} Generation Zero missions by pack and region, the Warboard arcs, challenges and achievements.")


# ---------------------------------------------------------------------------------------------------------------
# missions/arcs.html
# ---------------------------------------------------------------------------------------------------------------
def build_arcs(site, ms):
    n = sum(len(v) for v in ms.arcs.values())
    lead = (f"<p>The game files sort <b>{n}</b> of the base game's main missions into three Warboard arcs: "
            f"<b>Answers</b>, <b>Payback</b> and <b>Safety</b>. The Warboards in the Command Bunkers hand these "
            f"missions out.</p>")
    body = []
    for a in ARCS:
        rows = []
        for m in ms.arcs[a]:
            rows.append([mlink(m), region_link(site, m["region"]), f'<span class="msum">{esc(m.get("summary", ""))}</span>'])
        body.append(bar(f"{a}", right=f"{len(ms.arcs[a])} missions", id=f"arc-{slug(a)}"))
        body.append(table(["Mission", "Region", "Summary"], rows, cls="compact mstable"))
    body.append(note("Within an arc the missions are listed region by region in the order of the game's mission "
                     "table; that is not necessarily the order you will play them in.", "data"))
    ib = infobox("Warboard arcs", [(a, f'<a href="#arc-{slug(a)}">{len(ms.arcs[a])} missions</a>') for a in ARCS] +
                 [("Pack", pack_link("base"))])
    site.page("missions/arcs.html", "Warboard arcs", "\n".join(body), "missions", sub="arcs", lead=lead,
              head_extra=CSS, infobox_html=ib, crumbs=[("Warboard arcs", "~/missions/arcs.html")],
              desc="The three Warboard arcs of Generation Zero (Answers, Payback, Safety) and their missions.")


# ---------------------------------------------------------------------------------------------------------------
# missions/<pack>.html
# ---------------------------------------------------------------------------------------------------------------
def build_pack(site, ms, p):
    name = PACK_NAME[p]
    nmain = len(ms.groups.get((p, "main"), []))
    nside = len(ms.groups.get((p, "side"), []))
    lead = f"<p>{PACK_BLURB[p]}</p>"
    body = ['<div class="filterbar" data-for="mslist"><input placeholder="Filter missions...">'
            '<span class="count"></span></div>', '<div class="foldall" data-for="mslist"></div>',
            '<div id="mslist">']
    for t in ("main", "side"):
        regions = [r for r in REGION_ORDER if (p, t, r) in ms.by_region]
        if not regions:
            continue
        n = len(ms.groups[(p, t)])
        body.append(bar(TYPE_NAME[t], right=f"{n} missions", id=t))
        if p == "base" and t == "main":
            late = [m for m in ms.groups[(p, t)] if is_late_story(m)]
            if late:
                body.append(f'<p class="small">The base game\'s last {len(late)} main missions form one story that '
                            f'moves across regions, each briefing continuing the last: ' +
                            " → ".join(mlink(m) for m in late) + ".</p>")
        for r in regions:
            group = ms.by_region[(p, t, r)]
            inner = ""
            if r != "global" and site.find("region", r) and p != "dlc03":
                inner = (f'<p class="msreg small">About the region: {region_link(site, r)}</p>')
            inner += mission_table(site, group, p, t)
            right = f"{len(group)} mission{'s' if len(group) != 1 else ''}"
            body.append(fold(REGION_NAME[r], inner, open=False, level=3, id=fold_id(t, r), right=right))
    body.append("</div>")
    body.append(note(DATA_NOTE, "data"))

    # infobox: the pack's store picture, date and counts
    sb = site.data("steam")
    st = sb["game"] if p == "base" else next((d for d in sb["dlc"] if d["appid"] == PACK_APPID.get(p)), None)
    image = "~/" + st["image"] if st and st.get("image") and site.has_file(st["image"]) else None
    regions_all = [r for r in REGION_ORDER if any((p, t, r) in ms.by_region for t in ("main", "side")) and r != "global"]
    rows = [("Pack", pack_tag(p)),
            ("Released", esc(st["date"]) if st and st.get("date") else None),
            ("Main missions", f'<a href="#main">{nmain}</a>' if nmain else None),
            ("Side missions", f'<a href="#side">{nside}</a>' if nside else None),
            ("Regions", ", ".join(region_link(site, r) for r in regions_all) if regions_all else None),
            ("Warboard arcs", f'<a href="~/missions/arcs.html">{sum(1 for m in ms.missions if m["pack"] == p and m.get("arc"))} missions</a>'
             if p == "base" else None),
            ("DLC", site.link("dlc", name, "About this expansion") if p in ("alpine", "fnix") else None)]
    ib = infobox(name, rows, image=image, image_alt=name)
    site.page(PACK_PAGE[p], f"{name} missions" if p != "dlc03" else "Unreleased missions", "\n".join(body),
              "missions", sub=PACK_SUB[p], lead=lead, head_extra=CSS, infobox_html=ib,
              desc=f"The {nmain} main and {nside} side missions of {name if p != 'dlc03' else 'the unreleased expansion'}"
                   f", by region.")


def mission_table(site, group, pack, t):
    """One region's missions. Written by hand (not wiki.site.table) because the rows need data-w for the filter
    bar (objective and briefing text)."""
    show_arc = pack == "base" and t == "main" and any(m.get("arc") for m in group)
    head = ["Mission"] + (["Arc"] if show_arc else []) + ["Obj.", "Summary"]
    num = {len(head) - 2}
    out = ['<div class="tablewrap"><table class="wt sortable mstable"><thead><tr>']
    out += [f'<th{" class=n" if i in num else ""}>{esc(h)}</th>' for i, h in enumerate(head)]
    out.append("</tr></thead><tbody>")
    for m in group:
        steps = m.get("steps", [])
        req, nopt = obj_counts(m)
        words = " ".join(s["name"] for s in steps) + " " + m.get("description", "")
        obj = f'{req}{f" <small>(+{nopt})</small>" if nopt else ""}'
        cells = [f'<td class="mname">{mlink(m)}</td>']
        if show_arc:
            cells.append(f"<td>{arc_link(m['arc']) if m.get('arc') else '<span class=dim>–</span>'}</td>")
        cells += [f'<td class="n" data-v="{req}.{nopt:02d}">{obj}</td>',
                  f'<td class="msum">{esc(m.get("summary", ""))}</td>']
        out.append(f'<tr data-w="{esc(words)}">{"".join(cells)}</tr>')
    out.append("</tbody></table></div>")
    return "".join(out)


# ---------------------------------------------------------------------------------------------------------------
# missions/<slug>.html
# ---------------------------------------------------------------------------------------------------------------
def build_mission(site, ms, m):
    steps = m.get("steps", [])
    req, nopt = obj_counts(m)
    places = ms.places_in(m)
    lead_linked = set()
    lead = f'<p class="mslead">{linkify(site, ms, m.get("summary", ""), lead_linked)}</p>'
    if m.get("unreleased"):
        lead += note("This mission is in the current game files but is not part of the released game, so you can't "
                     "play it. The text below is as the files have it." + garble_note(m), "warn", "Unreleased")
    body = []
    if m.get("description"):
        body.append(bar("Briefing"))
        body.append("<p class=\"dim small\">" + ("The unreleased mission log text from the files." if
                    m.get("unreleased") else "The mission log text, as the game shows it.") + "</p>")
        body.append(briefing_html(site, ms, m["description"], set()))
    if steps:
        body.append(bar("Objectives", right=f"{req} required" + (f" · {nopt} optional" if nopt else "")))
        body.append(objectives_html(site, ms, m))
    if places:
        body.append(places_html(site, m, places))
    chs = challenges_for(site, ms, m)
    if chs:
        body.append(chs)
    body.append(neighbours_html(m))

    region_cell = region_link(site, m["region"])
    rows = [("Type", type_tag(m["type"]) + ("Main mission" if m["type"] == "main" else "Side mission")),
            ("Pack", pack_link(m["pack"]) + (" " + tag("DLC", "dlc") if m["pack"] in ("alpine", "fnix") else "")),
            ("Region", region_cell),
            ("Briefing places it in", ", ".join(region_link(site, k) for k in ms.regions_named(m))
             if m["region"] == "global" else None),
            ("Warboard arc", arc_link(m["arc"]) if m.get("arc") else None),
            ("Objectives", f"{req}" + (f" + {nopt} optional" if nopt else "")),
            ("Places named", str(len(places)) if places else None)]
    ib = infobox(m["name"], rows, subtitle=tag(m["arc"] + " arc", "arc") if m.get("arc") else None)
    kind = f"{'Main' if m['type'] == 'main' else 'Side'} mission · {PACK_NAME[m['pack']]}"
    crumbs = [(PACK_NAME[m["pack"]], "~/" + PACK_PAGE[m["pack"]]),
              (REGION_NAME[m["region"]] if m["region"] != "global" else TYPE_NAME[m["type"]],
               f"~/{PACK_PAGE[m['pack']]}#{fold_id(m['type'], m['region'])}")]
    site.page(m["path"], m["name"], "\n".join(body), "missions", sub=PACK_SUB[m["pack"]], crumbs=crumbs,
              infobox_html=ib, kind=kind, lead=lead, head_extra=CSS, side=[start_panel(site, ms, m)],
              desc=f"{m['name']}: {kind.lower()} in {REGION_NAME[m['region']]}. {m.get('summary', '')}")


def start_panel(site, ms, m):
    """The 'Mission start' box of the right-hand rail, from the Fandom wiki's mission infobox
    (mission_starts.json): the place (linked to its location page), Fandom's coordinates (the same x / z as our map)
    and a small map. '' when Fandom gives no start."""
    st = ms.starts.get(str(m["id"]))
    if not st:
        return ""
    loc = ms.loc_by_name.get(st.get("location") or "")
    place = st.get("place")
    if place and loc and place == loc["name"]:
        place_html = site.link("location", place)
    elif place:
        place_html = esc(place) + (f' <span class="dim">({site.link("location", loc["name"])})</span>' if loc else "")
    else:
        place_html = ""
    has_xy = st.get("x") is not None and st.get("y") is not None
    out = []
    if place_html:
        out.append(f'<p class="msstart">{place_html}</p>')
    if has_xy:
        out.append(f'<p class="msxy">Coordinates <b>{st["x"]}, {st["y"]}</b></p>')
    if st.get("note"):
        out.append(f'<p class="small dim">{esc(st["note"])}</p>')
    x, z = (st["x"], st["y"]) if has_xy else (loc["x"], loc["z"]) if loc else (None, None)
    if x is not None:
        # no pin label: the place is named just above, and a long name would be cut off in the narrow rail
        show = ["loc_" + loc["kind"]] if loc and loc.get("kind") else []
        region = [loc["region"]] if loc and loc["region"] != "global" else []
        out.append(minimap(x, z, "", zoom=2, height=200, show=show, region=region,
                           focus=loc["name"] if loc else None, map_zoom=1))
    url = "https://generation-zero.fandom.com/wiki/" + st["fandom_title"].replace(" ", "_")
    out.append(f'<p class="mscredit">From the <a href="{esc(url)}" rel="nofollow">Generation Zero Wiki on Fandom</a>'
               ' (CC BY-SA).</p>')
    return panel("Mission start", "".join(out), cls="msstartp")


def garble_note(m):
    """Words like 'esTatianae' (estate) and 'sTatianaion' (station) in some unreleased texts: a find / replace of
    'tat' with 'Tatiana' in the files. Returns a sentence naming them, or ''."""
    text = " ".join([m.get("summary", ""), m.get("description", "")] + [s["name"] for s in m.get("steps", [])])
    words = sorted(set(re.findall(r"\b(?:[a-z]+Tatiana\w*|Tatiana[a-z]+)\b", text)))
    if not words:
        return ""
    return (" Some words in it were garbled by a text replacement in the files that seems to have turned "
            "\"tat\" into \"Tatiana\": " + ", ".join(f"<i>{esc(w)}</i>" for w in words) +
            " (for example <i>esTatianae</i> for <i>estate</i>)." if "esTatianae" in words else
            " Some words in it were garbled by a text replacement in the files: " +
            ", ".join(f"<i>{esc(w)}</i>" for w in words) + ".")


def objectives_html(site, ms, m):
    """Objectives in the mission log's order, with what each one waits for (as far as the visible steps show)."""
    steps = m["steps"]
    num = {s["id"]: i for i, s in enumerate(steps, 1)}
    # steps that wait on exactly the same things open at the same time
    same = collections.defaultdict(list)
    for i, s in enumerate(steps, 1):
        if s.get("deps"):
            same[tuple(sorted(s["deps"]))].append(i)
    hidden_deps = any(d not in num for s in steps for d in s.get("deps", []))
    barcode_key = bunker_key(site, ms, m)
    linked = set()
    items = []
    for i, s in enumerate(steps, 1):
        after = [num[d] for d in s.get("deps", []) if d in num]
        together = [j for j in same.get(tuple(sorted(s.get("deps", []))), []) if j != i] if s.get("deps") else []
        meta = []
        if s.get("opt"):
            meta.append(tag("Optional", "opt"))
        if s.get("count"):
            meta.append(f'<span class="cnt">×{s["count"]}</span>')
        if barcode_key and "barcode" in s["name"]:
            meta.append(f'<span class="okey"><small>key</small> {site.link("key", barcode_key, icon=True)}</span>')
            barcode_key = None      # only next to the first barcode objective
        notes = []
        if after:
            notes.append("after " + steps_ref(after))
        if together:
            notes.append("opens with " + steps_ref(together))
        items.append(f'<li id="obj-{i}" class="{"opt" if s.get("opt") else ""}"><span class="otext">'
                     f'{linkify(site, ms, s["name"], linked, machines=True)}{"".join(meta)}</span>'
                     + (f'<small class="odeps">{" · ".join(notes)}</small>' if notes else "") + "</li>")
    expl = ("<p>The objectives in the order of the mission log. <b>After</b> names the objectives that have to be "
            "done first, <b>opens with</b> the ones that become available at the same time (they can be done in any "
            "order); <b>×N</b> is how many times the game counts the objective")
    expl += (". Some objectives also wait on hidden script steps (cut scenes, radio calls, spawns) that are not "
             "listed, so a step without an <i>after</i> may still have to wait for one of those.</p>" if hidden_deps else ".</p>")
    return expl + f'<ol class="objectives">{"".join(items)}</ol>'


def bunker_key(site, ms, m):
    """The '<code name> Bunker entry barcode' key for a mission whose objectives open a Command Bunker
    ("Use the barcode keycards to enter the Minken bunker"), or None."""
    text = " ".join(s["name"] for s in m.get("steps", []))
    if "barcode" not in text:
        return None
    for code in ms.loc_alias:
        name = f"{code} Bunker entry barcode"
        if re.search(re.escape(code) + r" [Bb]unker", text) and site.find("key", name):
            return name
    return None


def steps_ref(nums):
    """Objective numbers as linked ranges: [1, 2, 3, 5] -> '1–3, 5'."""
    nums = sorted(set(nums))
    runs, start = [], None
    for i, n in enumerate(nums):
        if start is None:
            start = n
        if i + 1 == len(nums) or nums[i + 1] != n + 1:
            runs.append((start, n))
            start = None
    a = lambda n: f'<a href="#obj-{n}">{n}</a>'
    return ", ".join(a(x) if x == y else f"{a(x)}, {a(y)}" if y == x + 1 else f"{a(x)}–{a(y)}" for x, y in runs)


def places_html(site, m, places):
    """The map locations a mission's texts name, with a mini map whose full-map button shows those kinds of
    location in those regions."""
    where_name = {"summary": "Summary", "briefing": "Briefing", "objectives": "Objectives"}
    rows = []
    for l, where in places:
        rows.append([site.link("location", l["name"], icon=True), esc(l.get("type") or l["kind"]),
                     region_link(site, l["region"]), ", ".join(where_name[w] for w in where)])
    pts = [(l["x"], l["z"], l["name"]) for l, _ in places]
    show = sorted({"loc_" + l["kind"] for l, _ in places if l.get("kind")})
    regions = sorted({l["region"] for l, _ in places if l["region"] != "global"})
    out = [bar("Places", right=f"{len(places)} named"),
           "<p>The map locations the summary, briefing or objectives mention by name, in order of first mention. "
           "They are where the mission sends you or what it talks about; the exact objective markers are not in "
           "the data.</p>",
           table(["Location", "Type", "Region", "Named in"], rows, cls="compact")]
    out += outside_region_notes(site, m, places)
    if len(pts) == 1:
        out.append(minimap(pts[0][0], pts[0][1], pts[0][2], zoom=2, height=340, show=show, region=regions,
                           focus=pts[0][2]))
    else:
        out.append(minimap(pts[0][0], pts[0][1], pts[0][2], zoom=2, height=340, markers=pts[1:], show=show,
                           region=regions))
    return "\n".join(out)


def outside_region_notes(site, m, places):
    """Notes on places outside the mission's own region: an objective naming one sends you there; a place named only
    in the summary or briefing may just be talked about."""
    if m["region"] == "global":
        return []
    outside = [(l, w) for l, w in places if l["region"] not in (m["region"], "global")]
    sent = sorted({l["region"] for l, w in outside if "objectives" in w})
    talked = sorted({l["region"] for l, w in outside if "objectives" not in w} - set(sent))
    links = lambda ks: ", ".join(region_link(site, k) for k in ks)
    out = []
    if sent:
        out.append(note(f"The objectives send you outside the mission's own region ({links(sent)}): the files put "
                        f"the mission in {region_link(site, m['region'])}, but part of it is played there."))
    if talked:
        out.append(note(f"Some places named only in the summary or briefing are outside the mission's own region "
                        f"({links(talked)}): the text mentions them, but that doesn't always mean you have to go "
                        f"there."))
    return out


def challenges_for(site, ms, m):
    """The challenges whose text names this mission, its pack, or the region it is in."""
    lines = []
    for tree, c, tiers, how in ms.mission_ch.get(m["id"], []):
        clink = f'<a href="~/missions/challenges.html#{challenge_anchor(c)}">{esc(c["name"])}</a>'
        if tiers:
            t = c["tiers"][tiers[0] - 1]
            what = f"tier {tiers[0]} of {len(c['tiers'])} is completing this mission (title: <i>{esc(t['title'])}</i>)"
        elif how == "listed":
            what = "this is one of the missions it lists"
        elif how == "pack":
            what = "it counts completed FNIX Rising side missions"
        else:
            what = "it counts activated Command Bunker Warboards"
        lines.append(f"<li>{clink} <small class=\"dim\">({esc(tree['name'])})</small>: {what}.</li>")
    rc = ms.region_ch.get(m["region"])
    if rc:
        tree, c, excluded = rc
        clink = f'<a href="~/missions/challenges.html#{challenge_anchor(c)}">{esc(c["name"])}</a>'
        total = c["tiers"][-1]["req"]
        if m["name"] in excluded:
            lines.append(f"<li>{clink} <small class=\"dim\">({esc(tree['name'])})</small>: the region challenge of "
                         f"{esc(REGION_NAME[m['region']])}, whose last tier excludes this mission by name.</li>")
        elif m["pack"] != "base" or m["idx"] > ORIGINAL_TABLE_END:
            later = f"{PACK_NAME[m['pack']]} missions" if m["pack"] != "base" else \
                "missions added after the expansions (like this one)"
            lines.append(f"<li>{clink} <small class=\"dim\">({esc(tree['name'])})</small>: the region challenge "
                         f"of {esc(REGION_NAME[m['region']])} counts main and side missions there ({fmt(total)} in "
                         f"all); the game text <a href=\"~/missions/challenges.html#region-note\">doesn't say "
                         f"whether {later} count</a>.</li>")
        else:
            lines.append(f"<li>{clink} <small class=\"dim\">({esc(tree['name'])})</small>: counts completed main "
                         f"and side missions in {esc(REGION_NAME[m['region']])} ({fmt(total)} in all).</li>")
    if not lines:
        return ""
    return (bar("Challenges") + "<p>Challenges whose description names this mission, its region or its "
            "expansion. Each tier of a challenge awards a title.</p><ul class=\"chlist\">" + "".join(lines) + "</ul>")


def neighbours_html(m):
    """Previous / next links in the pack page's list and, for arc missions, in the arc."""
    rows = [("list", f"{TYPE_NAME[m['type']]} · {PACK_NAME[m['pack']]}")]
    if m.get("arc"):
        rows.insert(0, ("arc", f"{m['arc']} arc"))
    out = ['<nav class="msnav">']
    for seq, label in rows:
        prev, nxt = m.get(seq + "_prev"), m.get(seq + "_next")
        p = f'<a class="prev" href="~/{prev["path"]}">← {esc(prev["name"])}</a>' if prev else "<span></span>"
        n = f'<a class="next" href="~/{nxt["path"]}">{esc(nxt["name"])} →</a>' if nxt else "<span></span>"
        out.append(f'<div class="msnrow"><small>{esc(label)}</small>{p}{n}</div>')
    out.append("</nav>")
    return "".join(out)


# ---------------------------------------------------------------------------------------------------------------
# missions/challenges.html: the challenge browser, after the CHALLENGES pane of the Gen0 Editor (DECA tools)
# ---------------------------------------------------------------------------------------------------------------
TREE_BLURB = {
    "TRUTH": "Story progress: completing main and side missions in each region of the base game, activating the "
             "Command Bunker Warboards and finishing a set of four main missions.",
    "RESISTANCE": "Destroying machines of each type, and Relay Beacons.",
    "SURVIVOR": "Combat feats: kills without taking damage, silent EMP takedowns, long-range shots, lures into "
                "traps and finishing shots with the .44 Magnus.",
    "DAWN": "The home base update: the base defense missions, building, crafting and the Messages in a Bottle.",
    "HIMFJÄLL": "The Alpine Unrest expansion: its main missions, Vacation Photos, named locations and Fuel Tank "
                "kills on Himfjäll.",
    "SCOUT": "The FNIX Rising expansion: its main and side missions, notes and letters, FNIX sites and melee kills.",
}
TREE_PACK = {"HIMFJÄLL": "Alpine Unrest", "SCOUT": "FNIX Rising"}

# words in the tier descriptions that we link to other sections: regex -> (kind, key, label)
CHALLENGE_LINKS = [
    (r"\.44 Magnus", ("weapon", ".44 Magnus", ".44 Magnus")),
    (r"\bboombox\b", ("item", "Boombox", "Boombox")),
    (r"\bradio\b", ("item", "Radio", "Radio")),
    (r"\bLand Mine\b", ("item", "Land Mine", "Land Mine")),
    (r"\bGas Tank\b", ("item", "Explosive Gas Tank", "Explosive Gas Tank")),
    (r"Messages? in a Bottle", ("collectible-type", "bottles", "Messages in a Bottle")),
    (r"Vacation Photos", ("collectible-type", "photos", "Vacation Photos")),
    (r"Love Letters", ("collectible-type", "loveletters", "Love Letters")),
    (r"Survivor's Notes", ("collectible-type", "survivornotes", "Survivor's Notes")),
]
# Map data counts we can show next to a challenge: challenge key -> (marker sub keys, what)
MARKER_COUNTS = {"08_04": (["bottles"], "Messages in a Bottle (Resistance Bottles)"),
                 "03_03": (["photos"], "Vacation Photos"),
                 "05_03": (["loveletters", "survivornotes"], "Love Letters and Survivor's Notes"),
                 "01_07": (["relaybeacons"], "Relay Beacons")}

# the tier nodes of the game's challenge screen (as drawn by the Gen0 Editor): a ring per tier, and the scalloped
# badge with a star for the last tier
_BADGE = "M" + "L".join(
    f"{24 + (17.2 if i % 2 else 20.4) * math.cos(i / 20 * 2 * math.pi - math.pi / 2):.2f} "
    f"{24 + (17.2 if i % 2 else 20.4) * math.sin(i / 20 * 2 * math.pi - math.pi / 2):.2f}" for i in range(20)) + "Z"
_STAR = "M" + "L".join(
    f"{24 + (3.5 if i % 2 else 8) * math.cos(i / 10 * 2 * math.pi - math.pi / 2):.2f} "
    f"{24.4 + (3.5 if i % 2 else 8) * math.sin(i / 10 * 2 * math.pi - math.pi / 2):.2f}" for i in range(10)) + "Z"
DLC_ICON = ('<svg class="dlcic" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="10.6" fill="none" '
            'stroke="currentColor" stroke-width="1.6"/><circle cx="12" cy="12" r="8" fill="currentColor"/>'
            '<path d="M10.4 6.6h3.2v5.6h2.6L12 17.4 7.8 12.2h2.6z" fill="#11161b"/></svg>')


def node_svg(n, last):
    if last:
        return (f'<svg viewBox="0 0 48 48" aria-hidden="true"><circle cx="24" cy="24" r="23" class="nb"/>'
                f'<path d="{_BADGE}" class="ns"/><circle cx="24" cy="24" r="14" class="nr1"/>'
                f'<circle cx="24" cy="24" r="11.6" class="nr2"/><circle cx="24" cy="24" r="10.2" class="nb"/>'
                f'<path d="{_STAR}" class="ns"/></svg>')
    return (f'<svg viewBox="0 0 48 48" aria-hidden="true"><circle cx="24" cy="24" r="15.6" class="nbg"/>'
            f'<circle cx="24" cy="24" r="12.6" class="nring"/>'
            f'<text x="24" y="28.6" text-anchor="middle" class="nnum">{n}</text></svg>')


def build_challenges(site, ms):
    trees = ms.trees
    n_ch = sum(len(t["challenges"]) for t in trees)
    n_tiers = sum(len(c["tiers"]) for t in trees for c in t["challenges"])
    lead = (f"<p>Challenges are Generation Zero's long-term goals: <b>{n_ch} challenges</b> in {len(trees)} trees, "
            f"each a chain of tiers ({n_tiers} tiers in all). Every tier you complete awards a <b>title</b> for your "
            f"character. Pick a tree, then click a challenge to see its tiers, the exact numbers the game counts and "
            f"the title of each tier, straight from the game files.</p>")
    tabs, lists, details = [], [], []
    for ti, t in enumerate(trees):
        tabs.append(f'<button type="button" class="chtab{" on" if ti == 0 else ""}" data-tree="{tree_anchor(t)}" '
                    f'title="{len(t["challenges"])} challenges{" · DLC" if t["dlc"] else ""}">{esc(t["name"])}'
                    f'{DLC_ICON if t["dlc"] else ""}</button>')
        tiers = sum(len(c["tiers"]) for c in t["challenges"])
        pk = (f" {tag(TREE_PACK[t['name']], 'dlc')} Needs the {site.link('dlc', TREE_PACK[t['name']])} expansion."
              if t["dlc"] else "")
        rows = []
        for ci, c in enumerate(t["challenges"]):
            track = []
            for n, tier in enumerate(c["tiers"], 1):
                if n > 1:
                    track.append('<i class="chseg"></i>')
                last = n == len(c["tiers"])
                track.append(f'<span class="chnode{" fin" if last else ""}" data-tier="{n}" '
                             f'title="Tier {n}: {esc(tier.get("title") or "")}">{node_svg(n, last)}</span>')
            rows.append(f'<div class="chrow{" sel" if ti == 0 and ci == 0 else ""}" id="{challenge_anchor(c)}" '
                        f'data-ch="{esc(c["key"])}" tabindex="0" role="button" aria-controls="chd-{esc(c["key"])}">'
                        f'<span class="chname">{esc(c["name"])}<small>{esc(c["tiers"][-1].get("title") or "")}</small>'
                        f'</span><span class="chtrack">{"".join(track)}</span></div>')
            details.append(challenge_detail(site, ms, t, c, ci, on=ti == 0 and ci == 0))
        lists.append(f'<section class="chtree{" on" if ti == 0 else ""}" id="{tree_anchor(t)}" '
                     f'data-tree="{tree_anchor(t)}"><p class="chblurb"><b>{esc(t["name"])}</b> · {len(t["challenges"])} '
                     f'challenges · {tiers} tiers. {esc(TREE_BLURB.get(t["name"], ""))}{pk}</p>{"".join(rows)}</section>')
    browser = (f'<div class="chb" id="chb"><nav class="chtabs" aria-label="Challenge trees">{"".join(tabs)}</nav>'
               f'<div class="chgrid"><div class="chlists">{"".join(lists)}</div>'
               f'<aside class="chdetail" aria-live="polite">{"".join(details)}</aside></div></div>')
    body = [bar("Challenge trees", right=f"{n_ch} challenges · {n_tiers} tiers", id="trees"),
            "<p>The six trees as the game's challenge screen shows them; the two expansion trees "
            f"(marked {DLC_ICON}) only appear with their DLC. Each circle is a tier, the star badge the last one. "
            "Click a challenge (or one of its tiers) for the details.</p>",
            browser,
            bar("How to read the tiers", id="reading"),
            "<p>A challenge keeps <b>one progress counter</b> for all its tiers. <b>From → to</b> is the counter "
            "at the start and end of a tier, so <b>Needed</b> (to minus from) is how far that tier moves the "
            "counter, and the last tier's <i>to</i> is the challenge's total. For most challenges that is what "
            "the tier asks for. A few (Combat Perfectionist, Eagle Eye and the ones that name missions) count "
            "completed tiers instead, one per tier; there the requirement text gives the real number, and where "
            "it asks for more than one kill <b>Needed</b> shows that number with <i>tier +1</i>. The tiers come one "
            "after another and each has its own condition: later tiers often ask for a tougher machine class (for "
            "example \"Military or FNIX class only\") or a harder feat than the first ones.</p>",
            '<div id="region-note">' +
            note("The tier descriptions are the game's own text. Where they say \"the last N missions\" of a region, "
                 "the total is what the challenge counts; the region may hold more missions than that today, since "
                 "the expansions and later updates added missions. The descriptions don't say whether those count, "
                 "so the region challenges' details list both numbers.", "data") + "</div>"]
    site.page("missions/challenges.html", "Challenges", "\n".join(body), "missions", lead=lead, toc=False,
              head_extra=CSS + JS,
              desc=f"All {n_ch} Generation Zero challenges in {len(trees)} trees: every tier, requirement and title.")


def challenge_detail(site, ms, t, c, ci, on=False):
    last = c["tiers"][-1]
    tiers = []
    for n, tier in enumerate(c["tiers"], 1):
        fin = n == len(c["tiers"])
        tiers.append(f'<li class="chtier" data-tier="{n}"><span class="chnode{" fin" if fin else ""}">'
                     f'{node_svg(n, fin)}</span><div><b>Tier {n}</b>'
                     f'<span class="chtv">{fmt(tier["start"])} → {fmt(tier["req"])} · needed {needed_html(tier)}</span>'
                     f'<div class="chreq">{tier_desc_html(ms, tier["desc"])}</div>'
                     f'<small>Title: <em>{esc(tier.get("title") or "–")}</em></small></div></li>')
    dlc = " · DLC" if t["dlc"] else ""
    return (f'<div class="chd{" on" if on else ""}" id="chd-{esc(c["key"])}" data-ch="{esc(c["key"])}">'
            f'<span class="chkicker">{esc(t["name"])}{dlc} · challenge {ci + 1} of {len(t["challenges"])}</span>'
            f'<div class="chdh">{esc(c["name"])}</div>'
            f'<div class="chstat">{len(c["tiers"])} tiers · counter total {fmt(last["req"])} · final title '
            f'<em>{esc(last.get("title") or "–")}</em></div>'
            f'<ol class="chtiers">{"".join(tiers)}</ol>{challenge_extras(site, ms, c)}</div>')


def needed_html(tier):
    """How far a tier moves the counter. Combat Perfectionist moves it by one per tier although each tier asks for
    several kills ('Destroy 3 Prototype Class Runners ...'): show the number from the text there."""
    step = tier["req"] - tier["start"]
    asked = re.match(r"(?:Destroy|Kill) (\d+) ", tier["desc"])
    if step == 1 and asked and int(asked.group(1)) > 1:
        return f'{asked.group(1)} <small class="dim">(tier +1)</small>'
    return fmt(step)


def tier_desc_html(ms, desc):
    """A tier's description with the missions it names linked."""
    def sub(mt):
        q, diff = mt.group(1), mt.group(2)
        m = ms.by_name.get(norm(f"{q} [Home Base Defense · {diff}]" if diff else q))
        return (f'"{mlink(m)}"' if m else f'"{esc(q)}"') + (f" on {esc(diff)} difficulty" if diff else "")

    paras = []
    for part in re.split(r"\n\s*\n", desc.strip()):
        lines = part.split("\n")
        if all(l.startswith("- ") for l in lines):
            items = "".join(f"<li>{mlink(ms.by_name[norm(l[2:])]) if norm(l[2:]) in ms.by_name else esc(l[2:])}</li>"
                            for l in lines)
            paras.append(f'<ul class="tlist">{items}</ul>')
            continue
        # escape the text around the quoted names, link the names
        html, pos = [], 0
        for mt in re.finditer(r'"([^"]+)"(?: on (Easy|Medium|Hard) difficulty)?', part):
            html.append(esc(part[pos:mt.start()]))
            html.append(sub(mt))
            pos = mt.end()
        html.append(esc(part[pos:]))
        paras.append("<p>" + "".join(html) + "</p>")
    return "".join(paras)


def warboard_codes(ms):
    """Command Bunker code names in the order The Command Bunker Network's objectives list them
    ('Find the Warboard in the Vesslan Bunker' ...)."""
    net = ms.by_name.get(norm("The Command Bunker Network"))
    steps = " ".join(s["name"] for s in net.get("steps", [])) if net else ""
    return sorted(ms.loc_alias, key=lambda code: steps.find(code) if code in steps else len(steps))


def challenge_extras(site, ms, c):
    """Cross-links and map-data counts under a challenge's tiers."""
    text = " ".join(t["desc"] for t in c["tiers"])
    bits = []
    # missions the challenge names or counts
    named = ms.ch_missions.get(c["key"], [])
    if named:
        bits.append(("Missions", ", ".join(mlink(m) for m, _, _ in named)))
    if "Command Bunker Warboard" in text:
        boards = [site.link("location", ms.loc_alias[code], code) for code in warboard_codes(ms)]
        home = ms.by_name.get(norm("The Home Team"))
        bits.append(("Warboards", f"{len(boards)}: " + ", ".join(boards) + f" (the mission "
                     f"{mlink(home) if home else 'The Home Team'} activates Vesslan's; the other six have a "
                     f"Warboard mission each)."))
    # region challenges: how many missions the region has today
    for k, (tree, rc, excluded) in ms.region_ch.items():
        if rc is c:
            in_region = [m for m in ms.missions if m["region"] == k]
            base = [m for m in in_region if m["pack"] == "base"]
            extra = collections.Counter(PACK_NAME[m["pack"]] for m in in_region if m["pack"] != "base")
            more = "".join(f", plus {n} from {p}" for p, n in extra.items())
            bits.append(("Region", f"{region_link(site, k)}: the game files list "
                                   f"<a href=\"~/{PACK_PAGE['base']}#{fold_id('main', k)}\">{len(base)} base-game "
                                   f"missions</a> here{more}; the challenge counts to {fmt(c['tiers'][-1]['req'])}" +
                                   (f" and leaves out {', '.join(mlink(ms.by_name[norm(x)]) for x in excluded)}"
                                    if excluded else "") + "."))
    # machine types; "(excluding Ticks)" and "Gas Tank" / "Fuel Tank" are not about those machines
    text_m = re.sub(r"\(?excluding Ticks\)?|\b(?:Gas|Fuel) Tanks?\b", "", text)
    machines = []
    for word, key in MACHINE_WORDS.items():
        if re.search(r"\b" + word + r"\b", text_m) and key not in machines:
            machines.append(key)
    if machines:
        bits.append(("Machines", ", ".join(site.link("machine", k) for k in machines)))
    # weapons, items and collectibles
    other = []
    for rx, (kind, key, label) in CHALLENGE_LINKS:
        if re.search(rx, text) and site.find(kind, key):
            other.append(site.link(kind, key, label))
    if other:
        bits.append(("See also", ", ".join(other)))
    # how many of the things to collect the map data has
    if c["key"] in MARKER_COUNTS:
        subs, what = MARKER_COUNTS[c["key"]]
        items = [x for x in ms.markers["items"] if x.get("s") in subs]
        regions = collections.Counter(x.get("r") for x in items)
        where = ", ".join(f"{n} in {esc(REGION_NAME.get(r, r))}" for r, n in regions.most_common())
        bits.append(("On the map", f"the map data has <a href=\"{maplink(show=subs)}\">{len(items)} {esc(what)}</a> "
                                   f"({where}); the challenge counts to {fmt(c['tiers'][-1]['req'])}."))
    if c["key"] == "03_04":
        alp = [l for l in ms.locs if l["region"] == "alpine"]
        kinds = sorted({"loc_" + l["kind"] for l in alp if l.get("kind")})
        bits.append(("On the map", f"the map data has <a href=\"{maplink(show=kinds, region=['alpine'])}\">{len(alp)} "
                                   f"named locations</a> on {region_link(site, 'alpine')}; the challenge counts to "
                                   f"{fmt(c['tiers'][-1]['req'])}."))
    if c["key"] == "05_04":
        outposts = [l for l in ms.locs if l.get("type") == "FNIX Outpost"]
        regions = collections.Counter(l["region"] for l in outposts)
        kinds = sorted({"loc_" + l["kind"] for l in outposts if l.get("kind")})
        bits.append(("On the map", f"the map data has <a href=\"{maplink(show=kinds, region=sorted(regions))}\">"
                     f"{len(outposts)} FNIX Outposts</a> (" +
                     ", ".join(f"{n} in {region_link(site, r)}" for r, n in regions.most_common()) +
                     "); tier 1 asks you to discover 5."))
    if not bits:
        return ""
    return kv(bits)


# ---------------------------------------------------------------------------------------------------------------
# missions/achievements.html
# ---------------------------------------------------------------------------------------------------------------
ACH_GROUPS = [
    ("story", "Story", "The base game's missions."),
    ("alpine", "Alpine Unrest", "Missions, secrets and collectibles of the Alpine Unrest expansion on Himfjäll."),
    ("fnix", "FNIX Rising", "Missions and collectibles of the FNIX Rising expansion."),
    ("machines", "Machines", "Destroying machines: counts per type, classes and special kills."),
    ("combat", "Weapons & combat", "Kills with each kind of weapon, lures, stealth and weapon mods."),
    ("explore", "Exploration", "Travelling Östertörn: safehouses, locations, bunkers, lighthouses and the homes."),
    ("collect", "Collectibles & loot", "Collecting things and looting the world."),
    ("people", "Characters & co-op", "Your characters and playing with others."),
]
# achievements that don't name a mission: name -> group
ACH_GROUP = {
    "Grey Dawn": "story", "Go-Getter": "story", "It's The Final Countdown": "story",
    "Vestiges": "alpine", "Here's Pauli!": "alpine", "Room 237": "alpine", "Unorthodox Skiing": "alpine",
    "The Ones That Came Before Us": "fnix",
    "First Blood": "machines", "Decimation": "machines", "You're A Disease And I'm The Cure": "machines",
    "Hasta La Vista Baby": "machines", "All Out Of Bubblegum": "machines", "Go Ahead, Make My Day": "machines",
    "Yippee-Ki-Yay": "machines", "Say Hello To My Little Friend": "machines", "Adapt and Evolve": "machines",
    "Not Today, FNIX!": "machines", "From a Distance": "machines", "One Shot": "machines", "Kill Switch": "machines",
    "Offence Is The Best Defence": "machines",
    "Marksman": "combat", "Siren Call": "combat", "Splash Damage": "combat", "Gunslinger": "combat",
    "Operator": "combat", "Gangster": "combat", "Commando": "combat", "Hunter": "combat", "Sapper": "combat",
    "Hot Property": "combat", "Real Sneaky Like": "combat", "Overkill": "combat", "Modder": "combat",
    "Lock & Load": "combat", "Running Wild": "combat",
    "Fika Club": "explore", "Gustafsloppet": "explore", "I Just Called To Say I Love You": "explore",
    "Light My Fire": "explore", "Folk Wisdom": "explore", "Explorer": "explore", "Tunnel Rat": "explore",
    "Scavenger": "collect", "Engineer": "collect", "Gardener": "collect", "DJ": "collect", "Tourist": "collect",
    "Fashionista": "collect", "Spare Parts": "collect", "I Want To Be A Mighty Pirate!": "collect",
    "Player Two": "people", "Postgraduate": "people", "Assist": "people",
}
# related wiki pages per achievement: (kind, key, label) for site.link, or ("map", [show keys], label, [regions])
ACH_RELATED = {
    "Siren Call": [("item", "Boombox", "Boombox")],
    "Hot Property": [("item", "Emergency flare", "Emergency flare")],
    "Splash Damage": [("weapon", "Granatgevär m/49", "Granatgevär m/49"), ("weapon", "Grenade", "Grenade")],
    "Overkill": [("weapon", "Granatgevär m/49", "Granatgevär m/49"), ("machine", "Seeker", "Seeker")],
    "One Shot": [("machine", "Hunter", "Hunter")],
    "Adapt and Evolve": [("machine", "Apocalypse class", "Apocalypse class")],
    "Not Today, FNIX!": [("machine", "Rival class", "Rivals")],
    "Kill Switch": [("map", ["relaybeacons"], "Relay Beacons on the map", [])],
    "Fika Club": [("map", ["playersafehouses"], "Safehouses on the map", [])],
    "Light My Fire": [("map", ["loc_lighthouse"], "Lighthouses on the map", [])],
    "Tunnel Rat": [("map", ["loc_bunker"], "Bunkers on the map", [])],
    "Engineer": [("collectible-type", "blueprints", "Blueprints"), ("map", ["blueprints"], "on the map", [])],
    "Gardener": [("collectible-type", "gnomes", "Gnomes"), ("map", ["gnomes"], "on the map", [])],
    "DJ": [("collectible-type", "mixtapes", "Mixtapes"), ("map", ["mixtapes"], "on the map", [])],
    "Vestiges": [("collectible-type", "audiologs", "Audio Logs"), ("map", ["audiologs"], "on the map", ["alpine"])],
    "The Ones That Came Before Us": [("collectible-type", "survivornotes", "Survivor's Notes"),
                                     ("collectible-type", "loveletters", "Love Letters"),
                                     ("map", ["survivornotes", "loveletters"], "on the map", [])],
    "Here's Pauli!": [("location", "Björntunet Hotel", "Björntunet Hotel")],
    "Room 237": [("location", "Björntunet Hotel", "Björntunet Hotel")],
    "It's The Final Countdown": [("page", "~/missions/arcs.html", "Warboard arcs")],
    "Grey Dawn": [("page", "~/" + PACK_PAGE["base"], "Base game missions")],
}
ACH_MACHINES = {"Ticks": "Tick", "Seekers": "Seeker", "Runners": "Runner", "Hunters": "Hunter",
                "Harvesters": "Harvester", "Tanks": "Tank"}


def build_achievements(site, ms):
    data = site.data("achievements")
    achs = data["achievements"]
    groups = collections.OrderedDict((g, []) for g, _, _ in ACH_GROUPS)
    for a in achs:
        missions = [ms.by_name[norm(q)] for q in re.findall(r'"([^"]+)"', a["desc"]) if norm(q) in ms.by_name]
        g = ACH_GROUP.get(a["name"])
        if g is None and missions:
            g = {"base": "story", "alpine": "alpine", "fnix": "fnix"}.get(missions[0]["pack"], "story")
        if g is None:
            site.warn(f"achievement without a group: {a['name']}")
            g = "people"
        groups[g].append((a, missions))
    n_secret = sum(1 for a in achs if a["hidden"])
    lead = (f"<p>Generation Zero has <b>{len(achs)} Steam achievements</b>, {n_secret} of them secret (Steam hides "
            f"them until you unlock them). Most come with the base game; the expansions "
            f"{site.link('dlc', 'Alpine Unrest')} and {site.link('dlc', 'FNIX Rising')} added their own. Unlike "
            f"<a href=\"~/missions/challenges.html\">challenges</a>, achievements belong to your Steam account, not to "
            f"a character.</p>")
    body = ['<div class="filterbar" data-for="achlist"><input placeholder="Filter achievements...">'
            '<button class="chip on" data-g="s" data-f="*">All</button>'
            '<button class="chip" data-g="s" data-f="secret">Secret</button><span class="count"></span></div>',
            '<div id="achlist">']
    for g, title, blurb in ACH_GROUPS:
        items = groups[g]
        if not items:
            continue
        rows = []
        for a, missions in items:
            rows.append(ach_html(site, ms, a, missions))
        body.append(f'<section class="achgroup">{bar(title, right=f"{len(items)}", id="g-" + g)}'
                    f'<p class="small dim">{esc(blurb)}</p><div class="achs">{"".join(rows)}</div></section>')
    body.append("</div>")
    body.append(note("The achievement list (names, descriptions, icons and which ones are secret) is read from "
                     "Steam's own copy of the game's achievement list, the one the Steam client keeps for "
                     "Generation Zero, and the icons are the files it names on Steam's image server. The game "
                     "files only hold the logic that unlocks them. The global unlock percentages from Steam "
                     "aren't included.", "data", "Source"))
    rows = [("Achievements", str(len(achs))), ("Secret", str(n_secret)), (None, "Groups")]
    rows += [(title, f'<a href="#g-{g}">{len(groups[g])}</a>') for g, title, _ in ACH_GROUPS if groups[g]]
    rows += [(None, "Source"), ("List", "Steam's achievement list for the game"),
             ("Steam", '<a href="https://store.steampowered.com/app/704270/">Store page</a>')]
    top = next((a for a in achs if a["name"] == "It's The Final Countdown"), achs[0])
    ib = infobox("Steam achievements", rows,
                 image="~/" + top["icon"] if site.has_file(top["icon"]) else None)
    site.page("missions/achievements.html", "Achievements", "\n".join(body), "missions", sub="achievements",
              lead=lead, head_extra=CSS, infobox_html=ib,
              desc=f"All {len(achs)} Generation Zero Steam achievements, including the {n_secret} secret ones, "
                   f"grouped and linked to the missions and collectibles they ask for.")


def ach_desc_html(site, ms, a):
    """The description with the missions it names and the machine types linked."""
    text = a["desc"]
    out, pos = [], 0
    pat = re.compile(r'"([^"]+)"|\b(' + "|".join(ACH_MACHINES) + r')\b')
    for mt in pat.finditer(text):
        out.append(esc(text[pos:mt.start()]))
        if mt.group(1):
            m = ms.by_name.get(norm(mt.group(1)))
            out.append(f'"{mlink(m)}"' if m else esc(mt.group(0)))
        else:
            out.append(site.link("machine", ACH_MACHINES[mt.group(2)], mt.group(2)))
        pos = mt.end()
    out.append(esc(text[pos:]))
    return "".join(out)


def ach_html(site, ms, a, missions):
    rel = []
    for m in missions:
        rel.append(f"{TYPE_NAME[m['type']][:-1]} in {region_link(site, m['region'])}")
    for r in ACH_RELATED.get(a["name"], []):
        if r[0] == "map":
            rel.append(f'<a href="{maplink(show=r[1], region=r[3])}">{esc(r[2])}</a>')
        elif r[0] == "page":
            rel.append(f'<a href="{r[1]}">{esc(r[2])}</a>')     # only our own pages
        else:
            rel.append(site.link(r[0], r[1], r[2]))
    icon = site.img(a["icon"], alt="", cls="achic")
    secret = a["hidden"]
    desc = ach_desc_html(site, ms, a)
    if secret:
        desc = f'<span class="spoil" tabindex="0" title="Secret achievement: click to show">{desc}</span>'
    return (f'<div class="ach fitem" id="{ach_anchor(a)}" data-f="{"secret" if secret else "open"}">{icon}'
            f'<div class="achb"><div class="achn">{esc(a["name"])}{tag("Secret", "secret") if secret else ""}</div>'
            f'<div class="achd">{desc}</div>'
            + (f'<div class="achr">{" · ".join(rel)}</div>' if rel else "") + "</div></div>")
