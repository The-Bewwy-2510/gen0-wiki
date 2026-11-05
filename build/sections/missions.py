"""Missions tab: the list of all missions, one page per mission, and the challenges page.

Data (build/data):
  missions.json  packs     base / alpine (Alpine Unrest) / fnix (FNIX Rising) / dlc03 (missions of a third expansion
                           that is in the files but was never released)
                 missions  in the order of the game's mission table (missions/missions.group.hpmissionsc):
                           id, name, type (main / side), pack, region (a region key, or "global" when the mission is
                           not tied to one), arc (the Warboard sub type Answers / Payback / Safety, base game only),
                           unreleased, summary, description (the mission log briefing), steps (the objectives the
                           game shows: id, name, deps = objective ids that must be done first, opt = optional,
                           count = how many times it has to be done). Hidden script steps (no on-screen text) are
                           not in the list, so a dependency can point at an objective id that isn't shown.
  gamedata.json  challenges  six challenge trees -> challenges -> tiers (start / req = the challenge's progress
                             counter at the start / end of the tier, desc, title = the title the tier awards)
                 locations   every map location (name, type, kind, region, x, z): we search the mission texts for
                             these names and link them
  markers.json   collectible counts for the challenges that ask you to collect things

Kinds registered: 'mission' (name; aliases the mission id as a string), 'challenge' (challenge name, alias its key
like '02_03'; also the tree names 'TRUTH' ... as anchors on the challenges page).
"""
import collections
import re

from wiki.site import esc, slug, norm, fmt, table, infobox, bar, note, kv, minimap, tag, REGIONS

CSS = '<link rel="stylesheet" href="~/assets/missions.css">'
REGION_NAME = dict(REGIONS)
REGION_NAME["global"] = "Across regions"
REGION_ORDER = [k for k, _ in REGIONS] + ["global"]
# the plain region names as the mission and challenge texts spell them ("... in the South Coast Region")
REGION_TEXT = {k: ("Himfjäll" if k == "alpine" else n) for k, n in REGIONS}

PACK_NAME = {"base": "Base game", "alpine": "Alpine Unrest", "fnix": "FNIX Rising", "dlc03": "Unreleased"}
PACK_TAG_CLS = {"base": "base", "alpine": "dlc", "fnix": "dlc", "dlc03": "unreleased"}
# content keys of the mission table (the extraction maps these to the packs); base-game missions come from several
# keys (the base game and its free updates), so we only name the expansion ones
CONTENT_KEY = {"alpine": "island01", "fnix": "expansion02", "dlc03": "expansion03"}
PACK_BLURB = {
    "base": "The missions of Generation Zero itself, including everything added by free updates. Main missions are "
            "listed region by region, in the order the game's mission table has them, followed by the FNIX "
            "storyline from the end of the table; the Warboard arc each one belongs to is shown where the files "
            "give one.",
    "alpine": "The Alpine Unrest expansion's missions, all set on the island of Himfjäll. They are listed in the order "
              "of the game's mission table, which follows the expansion's story.",
    "fnix": "The FNIX Rising expansion's missions, spread over the Archipelago, Farmlands and South Coast. Listed in "
            "the order of the game's mission table.",
    "dlc03": "Six missions of a third expansion (content key <code>expansion03</code>) that are in the current game "
             "files but are not part of the released game. They have no region of their own in the files.",
}
ARCS = ["Answers", "Payback", "Safety"]
TYPE_NAME = {"main": "Main missions", "side": "Side missions"}

# machine types linked when an objective names them (singular or plural)
MACHINE_WORDS = {"Runner": "Runner", "Runners": "Runner", "Tick": "Tick", "Ticks": "Tick", "Seeker": "Seeker",
                 "Seekers": "Seeker", "Hunter": "Hunter", "Hunters": "Hunter", "Harvester": "Harvester",
                 "Harvesters": "Harvester", "Tank": "Tank", "Tanks": "Tank", "Firebird": "Firebird",
                 "Firebirds": "Firebird", "Lynx": "Lynx", "Wolf": "Wolf", "Wolves": "Wolf"}
LOCATION_SKIP = {"Unknown"}   # location names too generic to look for in the texts
# The base game's FNIX storyline (Network Infiltration ... Launch Site Bravo) sits at the end of the mission table and
# each briefing picks up where the previous one ends, so these keep table order instead of being sorted by region.
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
        for i, m in enumerate(md["missions"]):
            m = dict(m)
            m["idx"] = i + 1                                   # position in the game's mission table
            m["path"] = f"missions/{slug(m['name'])}.html"
            self.missions.append(m)
        self.by_name = {norm(m["name"]): m for m in self.missions}
        self.trees = gd["challenges"]
        self.locs = [l for l in gd["locations"]["list"] if l["name"] not in LOCATION_SKIP]
        self.loc_by_name = {l["name"]: l for l in self.locs}
        self.markers = site.data("markers")
        self._groups()
        self._text_patterns()
        self._challenge_links()

    # ------------------------------------------------------------ order and groups
    @staticmethod
    def order_key(m):
        """Base game: region by region (the game's map order), then table order. Expansions: table order, which
        follows their story (the SCOUT challenges name FNIX Rising's main missions in exactly this order)."""
        if is_late_story(m):
            return (len(REGION_ORDER), m["idx"])
        if m["pack"] == "base":
            return (REGION_ORDER.index(m["region"]), m["idx"])
        return (0, m["idx"])

    def _groups(self):
        """(pack, type) -> missions in list order; arc -> missions; each mission's neighbours in both."""
        self.groups = collections.OrderedDict()
        for p in PACK_NAME:
            for t in ("main", "side"):
                ms = sorted((m for m in self.missions if m["pack"] == p and m["type"] == t), key=self.order_key)
                if ms:
                    self.groups[(p, t)] = ms
        self.arcs = {a: sorted((m for m in self.missions if m.get("arc") == a), key=self.order_key) for a in ARCS}
        for seq_name, seqs in (("list", self.groups.values()), ("arc", self.arcs.values())):
            for seq in seqs:
                for i, m in enumerate(seq):
                    m[seq_name + "_prev"] = seq[i - 1] if i else None
                    m[seq_name + "_next"] = seq[i + 1] if i + 1 < len(seq) else None

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


def collect(site):
    ms = model(site)
    for m in ms.missions:
        words = [m["type"], m["pack"], PACK_NAME[m["pack"]], REGION_NAME[m["region"]], m.get("arc", ""), "mission"]
        site.register("mission", m["name"], m["path"], m["name"], icon="img/locations/mission_objective.png",
                      desc=f"{'Main' if m['type'] == 'main' else 'Side'} mission · {REGION_NAME[m['region']]}"
                           f" · {PACK_NAME[m['pack']]}. {m.get('summary', '')}",
                      aliases=[str(m["id"])], keywords=" ".join(w for w in words if w))
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


# ---------------------------------------------------------------------------------------------------------------
# small shared bits
# ---------------------------------------------------------------------------------------------------------------
def pack_tag(p):
    return tag(PACK_NAME[p], PACK_TAG_CLS[p])


def type_tag(t):
    return tag("Main" if t == "main" else "Side", t)


def region_link(site, key):
    if key == "global":
        return '<span class="dim">Across regions</span>'
    return site.link("region", key, REGION_NAME[key])


def mlink(m):
    """Link to one of our own mission pages (always exists, so no registry lookup needed)."""
    return f'<a href="~/{m["path"]}">{esc(m["name"])}</a>'


def linkify(site, ms, text, linked, machines=False):
    """Escape text and turn location names, '<Region> region' and (optionally) machine types into links. Each
    target is linked once per `linked` set (the caller decides the scope: briefing, objectives ...)."""
    pats = [("loc", ms.loc_re), ("region", ms.region_re), ("region", ms.island_re)] + ([("machine", ms.machine_re)] if machines else [])
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


# ---------------------------------------------------------------------------------------------------------------
def build(site):
    ms = model(site)
    build_index(site, ms)
    for m in ms.missions:
        build_mission(site, ms, m)
    build_challenges(site, ms)


# ---------------------------------------------------------------------------------------------------------------
# missions/index.html
# ---------------------------------------------------------------------------------------------------------------
def build_index(site, ms):
    n = len(ms.missions)
    count = collections.Counter((m["pack"], m["type"]) for m in ms.missions)
    lead = (f"<p>Every one of the <b>{n} missions</b> in the current game files: "
            f"{sum(v for (p, t), v in count.items() if t == 'main')} main and "
            f"{sum(v for (p, t), v in count.items() if t == 'side')} side missions across the base game, the "
            f"{site.link('dlc', 'Alpine Unrest')} and {site.link('dlc', 'FNIX Rising')} expansions, plus "
            f"{sum(v for (p, t), v in count.items() if p == 'dlc03')} missions of an unreleased third expansion. "
            f"Each mission has its own page with the full briefing, every objective in order, the places it "
            f"sends you and the challenges it counts towards.</p>")
    body = [overview_tables(site, ms, count), arcs_section(ms), list_section(site, ms)]
    body.append(note("Mission names, summaries, briefings and objectives are the game's own English text, read from "
                     "<code>missions/missions.group.hpmissionsc</code>. A mission's region comes from the "
                     "<i>Location</i> line of its briefing or, without one, from the map files the mission uses. "
                     "The objective lists show what the game's mission log shows; some missions also run hidden "
                     "script steps in between, which have no text and are left out.", "data"))
    site.page("missions/index.html", "Missions", "\n".join(body), "missions", lead=lead, head_extra=CSS, wide=True,
              desc=f"All {n} Generation Zero missions by pack, type and region, with briefings and objectives.")


def overview_tables(site, ms, count):
    """Counts per pack and type, and per region and pack."""
    rows = []
    for p in PACK_NAME:
        rows.append([pack_tag(p), count[(p, "main")], count[(p, "side")], count[(p, "main")] + count[(p, "side")],
                     sum(1 for m in ms.missions if m["pack"] == p and m.get("arc")) or None])
    rows.append(["<b>All</b>", sum(count[(p, "main")] for p in PACK_NAME),
                 sum(count[(p, "side")] for p in PACK_NAME), len(ms.missions),
                 sum(1 for m in ms.missions if m.get("arc"))])
    by_region = collections.Counter((m["region"], m["pack"]) for m in ms.missions)
    rrows = []
    for k in REGION_ORDER:
        total = sum(v for (r, p), v in by_region.items() if r == k)
        if not total:
            continue
        mains = sum(1 for m in ms.missions if m["region"] == k and m["type"] == "main")
        rrows.append([region_link(site, k)] + [by_region[(k, p)] or None for p in PACK_NAME] + [mains, total])
    return (bar("Overview", right=f"{len(ms.missions)} missions") +
            "<p>How many missions each content pack adds, and how they spread over the map. <i>In an arc</i> "
            "counts the base-game main missions the files place in one of the three Warboard arcs.</p>" +
            table(["Pack", "Main", "Side", "Total", "In an arc"], rows, sortable=False, cls="compact counts",
                  num={1, 2, 3, 4}) +
            "<p>Missions per region. <i>Across regions</i> holds the missions the files don't tie to one region: "
            "The Command Bunker Network and the unreleased missions.</p>" +
            table(["Region"] + list(PACK_NAME.values()) + ["Main", "Total"], rrows, cls="compact ovtable counts",
                  num=set(range(1, len(PACK_NAME) + 3))))


def arcs_section(ms):
    cols = []
    for a in ARCS:
        items = "".join(f'<li><a href="~/{m["path"]}">{esc(m["name"])}</a>'
                        f'<small>{esc(REGION_NAME[m["region"]])}</small></li>' for m in ms.arcs[a])
        cols.append(f'<div class="arccol"><h3 id="arc-{slug(a)}">{esc(a)} <small class="dim">'
                    f'{len(ms.arcs[a])} missions</small></h3><ol class="arclist">{items}</ol></div>')
    return (bar("Warboard arcs", right=" · ".join(f"{a} {len(ms.arcs[a])}" for a in ARCS), id="arcs") +
            "<p>The game files sort 25 of the base game's main missions into three Warboard arcs: "
            "<b>Answers</b>, <b>Payback</b> and <b>Safety</b> (the <code>WarboardSubType</code> of each mission). "
            "The Command Bunker Warboards hand these missions out. Within an arc the missions are listed region by "
            "region in the order of the game's mission table; that is not necessarily the order you will play "
            "them in.</p>"
            f'<div class="arcs">{"".join(cols)}</div>')


def list_section(site, ms):
    """The filterable list: one block per pack, a table per type inside it."""
    chips = ['<button class="chip on" data-g="p" data-f="*">All packs</button>'] + \
        [f'<button class="chip" data-g="p" data-f="p-{p}">{esc(n)}</button>' for p, n in PACK_NAME.items()]
    chips += ['<button class="chip on" data-g="t" data-f="*">Main &amp; side</button>',
              '<button class="chip" data-g="t" data-f="t-main">Main</button>',
              '<button class="chip" data-g="t" data-f="t-side">Side</button>']
    chips += ['<button class="chip on" data-g="r" data-f="*">All regions</button>'] + \
        [f'<button class="chip" data-g="r" data-f="r-{k}">{esc(REGION_NAME[k])}</button>' for k in REGION_ORDER]
    fb = (f'<div class="filterbar msfilter" data-for="mslist"><input placeholder="Filter by name, place, '
          f'objective...">{"".join(chips)}<span class="count"></span></div>')
    blocks = []
    for p in PACK_NAME:
        inner = []
        for t in ("main", "side"):
            group = ms.groups.get((p, t))
            if group:
                inner.append(f'<section class="msgroup"><h3>{TYPE_NAME[t]} <small class="dim">{len(group)}'
                             f'</small></h3>{group_tables(site, group, p)}</section>')
        n = sum(len(ms.groups.get((p, t), [])) for t in ("main", "side"))
        blocks.append(f'<section class="mspack">{bar(PACK_NAME[p], right=f"{n} missions", id="pack-" + p)}'
                      f'<p>{PACK_BLURB[p]}</p>{"".join(inner)}</section>')
    return (bar("All missions", right=f"{len(ms.missions)}", id="list") +
            "<p>Filter by pack, type and region (the chips of one row combine with <i>or</i>, the rows with "
            "<i>and</i>), or type part of a name, a place or an objective. <b>#</b> is the mission's position in "
            "the game's mission table; <b>Obj.</b> counts the objectives shown in the mission log (optional ones in "
            "brackets). Click a column title to sort a table.</p>" + fb +
            f'<div id="mslist">{"".join(blocks)}</div>')


def group_tables(site, group, pack):
    """A group's table; the base game's later FNIX storyline gets its own table under a sub-heading."""
    early = [m for m in group if not is_late_story(m)]
    late = [m for m in group if is_late_story(m)]
    out = mission_table(site, early, pack)
    if late:
        out += (f'<div class="mssub"><h4>FNIX storyline (later update) <small class="dim">{len(late)}</small></h4>'
                f'<p>The five main missions at the end of the mission table, after the expansion missions, form '
                f'one story, each briefing continuing the last, so they are listed in table order rather than by '
                f'region.</p>'
                f'{mission_table(site, late, pack)}</div>')
    return out


def mission_table(site, group, pack):
    """One group's table. Written by hand (not wiki.site.table) because the rows need data-f / data-w for the
    filter bar."""
    show_arc = pack == "base"
    head = ["#", "Mission", "Region"] + (["Arc"] if show_arc else []) + ["Obj.", "Summary"]
    num = {0, len(head) - 2}
    out = ['<div class="tablewrap"><table class="wt sortable mstable"><thead><tr>']
    out += [f'<th{" class=n" if i in num else ""}>{esc(h)}</th>' for i, h in enumerate(head)]
    out.append("</tr></thead><tbody>")
    for m in group:
        steps = m.get("steps", [])
        nopt = sum(1 for s in steps if s.get("opt"))
        tags = f"p-{m['pack']} t-{m['type']} r-{m['region']}"
        words = " ".join(s["name"] for s in steps) + " " + m.get("description", "")
        obj = f'{len(steps) - nopt}{f" <small>(+{nopt})</small>" if nopt else ""}'
        cells = [f'<td class="n" data-v="{m["idx"]}">{m["idx"]}</td>',
                 f'<td class="mname">{mlink(m)}{tag("Unreleased", "unreleased") if m.get("unreleased") and pack != "dlc03" else ""}</td>',
                 f"<td>{region_link(site, m['region'])}</td>"]
        if show_arc:
            cells.append(f"<td>{esc(m.get('arc', '')) or '<span class=dim>–</span>'}</td>")
        cells += [f'<td class="n" data-v="{len(steps) - nopt}.{nopt:02d}">{obj}</td>', f'<td class="msum">{esc(m.get("summary", ""))}</td>']
        out.append(f'<tr data-f="{tags}" data-w="{esc(words)}">{"".join(cells)}</tr>')
    out.append("</tbody></table></div>")
    return "".join(out)


# ---------------------------------------------------------------------------------------------------------------
# missions/<slug>.html
# ---------------------------------------------------------------------------------------------------------------
def build_mission(site, ms, m):
    steps = m.get("steps", [])
    nopt = sum(1 for s in steps if s.get("opt"))
    places = ms.places_in(m)
    lead_linked = set()
    lead = f'<p class="mslead">{linkify(site, ms, m.get("summary", ""), lead_linked)}</p>'
    if m.get("unreleased"):
        lead += note("This mission is in the current game files (content key <code>expansion03</code>) but is not "
                     "part of the released game, so you can't play it. The text below is as the files have it."
                     + garble_note(m), "warn", "Unreleased")
    body = []
    if m.get("description"):
        body.append(bar("Briefing"))
        body.append("<p class=\"dim small\">" + ("The unreleased mission log text from the files." if
                    m.get("unreleased") else "The mission log text, as the game shows it.") + "</p>")
        body.append(briefing_html(site, ms, m["description"], set()))
    if steps:
        body.append(bar("Objectives", right=f"{len(steps) - nopt} required" + (f" · {nopt} optional" if nopt else "")))
        body.append(objectives_html(site, ms, m))
    if places:
        body.append(places_html(site, m, places))
    chs = challenges_for(site, ms, m)
    if chs:
        body.append(chs)
    body.append(neighbours_html(m))

    rows = [("Type", type_tag(m["type"]) + ("Main mission" if m["type"] == "main" else "Side mission")),
            ("Pack", site.link("dlc", m["pack"], PACK_NAME[m["pack"]]) if m["pack"] != "dlc03"
             else tag("Unreleased", "unreleased")),
            ("Region", region_link(site, m["region"])),
            ("Briefing places it in", ", ".join(region_link(site, k) for k in ms.regions_named(m))
             if m["region"] == "global" else None),
            ("Warboard arc", f'<a href="~/missions/index.html#arc-{slug(m["arc"])}">{esc(m["arc"])}</a>'
             if m.get("arc") else None),
            ("Objectives", f"{len(steps) - nopt}" + (f" + {nopt} optional" if nopt else "")),
            ("Places named", str(len(places)) if places else None),
            (None, "Game files"),
            ("Mission id", f"<code>{m['id']}</code>"),
            ("Table position", f"{m['idx']} of {len(ms.missions)}"),
            ("Content key", f"<code>{CONTENT_KEY[m['pack']]}</code>" if m["pack"] in CONTENT_KEY else None)]
    ib = infobox(m["name"], rows, subtitle=tag(m["arc"] + " arc", "arc") if m.get("arc") else None)
    kind = f"{'Main' if m['type'] == 'main' else 'Side'} mission · {PACK_NAME[m['pack']]}"
    site.page(m["path"], m["name"], "\n".join(body), "missions", sub="missions",
              crumbs=[(PACK_NAME[m["pack"]], f"~/missions/index.html#pack-{m['pack']}")], infobox_html=ib,
              kind=kind, lead=lead, head_extra=CSS,
              desc=f"{m['name']}: {kind.lower()} in {REGION_NAME[m['region']]}. {m.get('summary', '')}")


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
    """The map locations a mission's texts name, with a mini map."""
    where_name = {"summary": "Summary", "briefing": "Briefing", "objectives": "Objectives"}
    rows = []
    for l, where in places:
        rows.append([site.link("location", l["name"], icon=True), esc(l.get("type") or l["kind"]),
                     region_link(site, l["region"]), ", ".join(where_name[w] for w in where)])
    pts = [(l["x"], l["z"], l["name"]) for l, _ in places]
    out = [bar("Places", right=f"{len(places)} named"),
           "<p>The map locations the summary, briefing or objectives mention by name, in order of first mention. "
           "They are where the mission sends you or what it talks about; the exact objective markers are not in "
           "the data.</p>",
           table(["Location", "Type", "Region", "Named in"], rows, cls="compact")]
    out += outside_region_notes(site, m, places)
    out.append(minimap(pts[0][0], pts[0][1], pts[0][2], zoom=2, height=340, markers=pts[1:]))
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
    """Previous / next links in the mission list and, for arc missions, in the arc."""
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
# missions/challenges.html
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
    (r"Relay Beacons", ("collectible-type", "relaybeacons", "Relay Beacons")),
]
# Map data counts we can show next to a challenge: challenge key -> (marker sub keys, what)
MARKER_COUNTS = {"08_04": (["bottles"], "Messages in a Bottle (Resistance Bottles)"),
                 "03_03": (["photos"], "Vacation Photos"),
                 "05_03": (["loveletters", "survivornotes"], "Love Letters and Survivor's Notes"),
                 "01_07": (["relaybeacons"], "Relay Beacons")}


def build_challenges(site, ms):
    trees = ms.trees
    n_ch = sum(len(t["challenges"]) for t in trees)
    n_tiers = sum(len(c["tiers"]) for t in trees for c in t["challenges"])
    lead = (f"<p>Challenges are Generation Zero's long-term goals: <b>{n_ch} challenges</b> in {len(trees)} trees, "
            f"each a chain of tiers ({n_tiers} tiers in all). Every tier you complete awards a <b>title</b> for your "
            f"character. This page lists every challenge with its tiers, the exact numbers the game counts and the "
            f"title of each tier, straight from the game files.</p>")
    body = [bar("Challenge trees", right=f"{n_ch} challenges · {n_tiers} tiers", id="trees"),
            "<p>The six trees as the game's challenge screen shows them. The two expansion trees only appear with "
            "their DLC.</p>",
            table(["Tree", "Internal no.", "Pack", "Challenges", "Tiers", "About"],
                  [[f'<a href="#{tree_anchor(t)}">{esc(t["name"])}</a>', f"<code>{esc(t['tree'])}</code>",
                    tag(TREE_PACK[t["name"]], "dlc") if t["dlc"] else tag("Base game", "base"),
                    len(t["challenges"]), sum(len(c["tiers"]) for c in t["challenges"]),
                    esc(TREE_BLURB.get(t["name"], ""))] for t in trees], cls="compact trees", num={3, 4}),
            bar("How to read the tiers", id="reading"),
            "<p>A challenge keeps <b>one progress counter</b> for all its tiers. <b>From → to</b> is the counter "
            "at the start and end of a tier, so <b>Needed</b> (to minus from) is how far that tier moves the "
            "counter, and the last tier's <i>to</i> is the challenge's total. For most challenges that is what "
            "the tier asks for. A few (Combat Perfectionist, Eagle Eye and the ones that name missions) count "
            "completed tiers instead, one per tier; there the requirement text gives the real number, and where "
            "it asks for more than one kill <b>Needed</b> shows that number with <i>tier +1</i>. The tiers come one after another and each has "
            "its own condition: later tiers often ask for a tougher machine class (for example \"Military or FNIX "
            "class only\") or a harder feat than the first ones.</p>",
            '<div id="region-note">' +
            note("The tier descriptions are the game's own text. Where they say \"the last N missions\" of a region, "
                 "the total is what the challenge counts; the region may hold more missions than that today, since "
                 "the expansions and later updates added missions. The descriptions don't say whether those count, "
                 "so we list both numbers below.", "data") + "</div>"]
    for t in trees:
        body.append(tree_html(site, ms, t))
    site.page("missions/challenges.html", "Challenges", "\n".join(body), "missions", lead=lead, head_extra=CSS,
              desc=f"All {n_ch} Generation Zero challenges in {len(trees)} trees: every tier, requirement and title.")


def tree_html(site, ms, t):
    tiers = sum(len(c["tiers"]) for c in t["challenges"])
    out = [bar(t["name"], right=f"{len(t['challenges'])} challenges · {tiers} tiers", id=tree_anchor(t))]
    pk = f" {tag(TREE_PACK[t['name']], 'dlc')} Needs the {site.link('dlc', TREE_PACK[t['name']])} expansion." \
        if t["dlc"] else ""
    out.append(f"<p>{esc(TREE_BLURB.get(t['name'], ''))}{pk}</p>")
    for c in t["challenges"]:
        out.append(challenge_html(site, ms, t, c))
    return "\n".join(out)


def challenge_html(site, ms, t, c):
    last = c["tiers"][-1]
    head = (f'<h3 id="{challenge_anchor(c)}" class="chh">{esc(c["name"])} <small class="dim">'
            f'<code>{esc(c["key"])}</code> · {len(c["tiers"])} tiers · total {fmt(last["req"])}</small></h3>')
    rows = []
    for n, tier in enumerate(c["tiers"], 1):
        rows.append([n, f"{fmt(tier['start'])} → {fmt(tier['req'])}", needed_html(tier),
                     tier_desc_html(ms, tier["desc"]), f'<span class="title">{esc(tier.get("title") or "–")}</span>'])
    tbl = table(["Tier", "From → to", "Needed", "Requirement", "Title awarded"], rows, sortable=False,
                cls="chtable", num={1, 2})
    return head + tbl + challenge_extras(site, ms, c)


def needed_html(tier):
    """How far a tier moves the counter. Combat Perfectionist moves it by one per tier although each tier asks for
    several kills ('Destroy 3 Prototype Class Runners ...'): show the number from the text there."""
    step = tier["req"] - tier["start"]
    asked = re.match(r"(?:Destroy|Kill) (\d+) ", tier["desc"])
    if step == 1 and asked and int(asked.group(1)) > 1:
        return f'{asked.group(1)} <small class="dim">tier +1</small>'
    return step


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
        paras.append("<div>" + "".join(html) + "</div>")
    return "".join(paras)


def warboard_codes(ms):
    """Command Bunker code names in the order The Command Bunker Network's objectives list them
    ('Find the Warboard in the Vesslan Bunker' ...)."""
    net = ms.by_name.get(norm("The Command Bunker Network"))
    steps = " ".join(s["name"] for s in net.get("steps", [])) if net else ""
    return sorted(ms.loc_alias, key=lambda code: steps.find(code) if code in steps else len(steps))


def challenge_extras(site, ms, c):
    """Cross-links and map-data counts under a challenge's table."""
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
            bits.append(("Region", f"{region_link(site, k)}: the game files list {len(base)} base-game missions "
                                   f"here{more}; the challenge counts to {fmt(c['tiers'][-1]['req'])}" +
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
        bits.append(("On the map", f"the map data has {len(items)} {esc(what)} ({where}); the challenge counts to "
                                   f"{fmt(c['tiers'][-1]['req'])}."))
    if c["key"] == "03_04":
        n = sum(1 for l in ms.locs if l["region"] == "alpine")
        bits.append(("On the map", f"the map data has {n} named locations on {region_link(site, 'alpine')}; the "
                                   f"challenge counts to {fmt(c['tiers'][-1]['req'])}."))
    if c["key"] == "05_04":
        outposts = [l for l in ms.locs if l.get("type") == "FNIX Outpost"]
        regions = collections.Counter(l["region"] for l in outposts)
        bits.append(("On the map", f"the map data has {len(outposts)} FNIX Outposts (" +
                     ", ".join(f"{n} in {region_link(site, r)}" for r, n in regions.most_common()) +
                     "); tier 1 asks you to discover 5."))
    if not bits:
        return ""
    return kv(bits)
