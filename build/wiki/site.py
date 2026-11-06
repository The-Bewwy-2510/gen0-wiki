"""The wiki's page framework: navigation, the page template, cross-links, the search index and the build.

Every section module in build/sections/ has two functions:

    collect(site)   register the pages it will make (site.register) so other sections can link to them
    build(site)     write its pages (site.page)

All internal URLs in the HTML a section writes start with "~/" (the site root), for example
'<a href="~/weapons/n9-handgun.html">'. site.page() turns them into relative links, so the site works from any
folder: GitHub Pages (https://<user>.github.io/gen0-wiki/), a local server, or opened from disk.
Use site.link() / site.url() for links to other sections' pages; they never break the build when a target is
missing (they fall back to plain text and are listed in the build report).
"""
import html
import json
import os
import re
import shutil
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.dirname(HERE)
ROOT = os.path.dirname(BUILD)
DATA = os.path.join(BUILD, "data")
STATIC = os.path.join(BUILD, "static")
DOCS = os.path.join(ROOT, "docs")

SITE_NAME = "Generation Zero Wiki"
GAME = "Generation Zero"

# ---------------------------------------------------------------------------------------------------------------
# Navigation. Top tabs (with the top bar colour, like the tabs of the game menu and the Gen0 tools) and their sub
# tabs. A page names its tab and sub tab with section= and sub=. Paths are relative to the site root.
# ---------------------------------------------------------------------------------------------------------------
NAV = [
    {"id": "home", "label": "Home", "color": "#1c5777", "path": "index.html", "subs": [
        {"id": "home", "label": "Main page", "path": "index.html"},
        {"id": "basics", "label": "Game basics", "path": "basics.html"},
        {"id": "dlc", "label": "DLC", "path": "dlc.html"},
        {"id": "about", "label": "About this wiki", "path": "about.html"},
    ]},
    {"id": "weapons", "label": "Weapons", "color": "#2f4d5e", "path": "weapons/index.html", "subs": [
        {"id": "weapons", "label": "All weapons", "path": "weapons/index.html"},
        {"id": "ammo", "label": "Ammo", "path": "weapons/ammo.html"},
        {"id": "attachments", "label": "Attachments", "path": "weapons/attachments.html"},
        {"id": "augments", "label": "Augments & research", "path": "weapons/augments.html"},
        {"id": "skins", "label": "Weapon skins", "path": "weapons/skins.html"},
        {"id": "experimental", "label": "Experimental", "path": "weapons/experimental.html"},
    ]},
    {"id": "machines", "label": "Machines", "color": "#7a2a26", "path": "machines/index.html", "subs": [
        {"id": "machines", "label": "All machines", "path": "machines/index.html"},
        {"id": "mweapons", "label": "Machine weapons", "path": "machines/weapons.html"},
        {"id": "detection", "label": "Detection & stealth", "path": "machines/detection.html"},
        {"id": "difficulty", "label": "Difficulty & co-op", "path": "machines/difficulty.html"},
        {"id": "rivals", "label": "Rivals", "path": "machines/rivals.html"},
    ]},
    {"id": "world", "label": "World", "color": "#5f4258", "path": "world/index.html", "subs": [
        {"id": "regions", "label": "Regions", "path": "world/index.html"},
        {"id": "locations", "label": "Locations", "path": "world/locations.html"},
        {"id": "safehouses", "label": "Safehouses", "path": "world/safehouses.html"},
        {"id": "controlpoints", "label": "Control points & beacons", "path": "world/control-points.html"},
        {"id": "collectibles", "label": "Collectibles", "path": "world/collectibles.html"},
        {"id": "keys", "label": "Keys & barcodes", "path": "world/keys.html"},
        {"id": "map", "label": "Interactive map", "path": "map/index.html"},
    ]},
    {"id": "missions", "label": "Missions", "color": "#1d4039", "path": "missions/index.html", "subs": [
        {"id": "missions", "label": "Overview", "path": "missions/index.html"},
        {"id": "arcs", "label": "Warboard arcs", "path": "missions/arcs.html"},
        {"id": "base", "label": "Base game", "path": "missions/base-game.html"},
        {"id": "alpine", "label": "Alpine Unrest", "path": "missions/alpine-unrest.html"},
        {"id": "fnix", "label": "FNIX Rising", "path": "missions/fnix-rising.html"},
        {"id": "unreleased", "label": "Unreleased", "path": "missions/unreleased.html"},
        {"id": "challenges", "label": "Challenges", "path": "missions/challenges.html"},
        {"id": "achievements", "label": "Achievements", "path": "missions/achievements.html"},
    ]},
    {"id": "items", "label": "Items & crafting", "color": "#4d4a2c", "path": "items/index.html", "subs": [
        {"id": "items", "label": "Equipment", "path": "items/index.html"},
        {"id": "materials", "label": "Materials", "path": "items/materials.html"},
        {"id": "schematics", "label": "Schematics", "path": "items/schematics.html"},
        {"id": "companion", "label": "Companion", "path": "items/companion.html"},
    ]},
    {"id": "character", "label": "Character", "color": "#47545a", "path": "character/skills.html", "subs": [
        {"id": "skills", "label": "Skills", "path": "character/skills.html"},
        {"id": "apparel", "label": "Apparel", "path": "character/apparel.html"},
        {"id": "emotes", "label": "Emotes & face paint", "path": "character/emotes.html"},
        {"id": "vehicles", "label": "Vehicles", "path": "character/vehicles.html"},
    ]},
    # turned off for now (not in the menus and not built: build.py DISABLED); the module stays in build/sections
    {"id": "modding", "label": "Modding", "color": "#33393f", "path": "modding/index.html", "hidden": True, "subs": [
        {"id": "modding", "label": "Overview", "path": "modding/index.html"},
        {"id": "tools", "label": "Gen0 tools", "path": "modding/tools.html"},
        {"id": "console", "label": "Console & VR mod", "path": "modding/console.html"},
        {"id": "mapeditor", "label": "Map editor", "path": "modding/map-editor.html"},
        {"id": "data", "label": "Game data & IDs", "path": "modding/data.html"},
    ]},
]
NAV_BY_ID = {n["id"]: n for n in NAV}

QUALITY = {
    1: ("Dilapidated", "q1"), 2: ("Worn", "q2"), 3: ("Good", "q3"), 4: ("Exceptional", "q4"), 5: ("Special", "q5"),
    6: ("Experimental", "q6"),
}

REGIONS = [  # key, name (as the game shows it)
    ("archipelago", "Archipelago"), ("southcoast", "South Coast"), ("farmlands", "Farmlands"), ("forest", "Forest"),
    ("mountains", "Mountains"), ("marshlands", "Marshlands"), ("northcoast", "North Coast"),
    ("alpine", "Himfjäll (Alpine Unrest)"),
]


# ---------------------------------------------------------------------------------------------------------------
# small helpers (also used by the sections through `from wiki.site import esc, ...`)
# ---------------------------------------------------------------------------------------------------------------
def esc(s):
    return html.escape("" if s is None else str(s), quote=True)


def slug(s):
    """URL-safe file name: 'Älgstudsare Hunting Rifle' -> 'algstudsare-hunting-rifle'."""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s.lower()).strip("-")
    return s or "page"


def norm(s):
    """Lookup key for names that are spelled differently in different game files: case, accents, quotes, dots and
    spacing don't matter ('M/46 "Kpist" SMG' == 'M/46 Kpist SMG' == 'm-46 kpist smg')."""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", s)


def fmt(n, digits=2):
    """Number without useless decimals: 1.0 -> '1', 0.625 -> '0.63', 12000 -> '12,000'."""
    if n is None or n == "":
        return "–"
    if isinstance(n, bool):
        return "Yes" if n else "No"
    if isinstance(n, int) or (isinstance(n, float) and n.is_integer()):
        return f"{int(n):,}"
    if isinstance(n, float):
        return f"{round(n, digits):,.{digits}f}".rstrip("0").rstrip(".")
    return esc(n)


def pct(x, digits=0):
    if x is None:
        return "–"
    return f"{x * 100:.{digits}f}%"


def qbadge(q, short=False):
    """Quality badge: q is 1..6."""
    q = int(q)
    name, cls = QUALITY.get(q, (f"Q{q}", "q0"))
    return f'<span class="qb {cls}" title="Quality {q}: {esc(name)}">{"Q" + str(q) if short else esc(name)}</span>'


def tag(text, cls=""):
    return f'<span class="tag {cls}">{esc(text)}</span>'


def table(headers, rows, cls="", sortable=True, caption=None, num=None, raw_headers=False):
    """headers: list of str (escaped) ; rows: list of lists of *HTML* cells (escape plain text yourself or pass
    numbers, or a (html, sort_value) tuple to sort a formatted cell by a number). num: set of column indexes that are numeric (right aligned, sorted as numbers); numbers in rows are
    detected automatically."""
    num = set(num or [])
    out = [f'<div class="tablewrap"><table class="wt {cls}{" sortable" if sortable else ""}">']
    if caption:
        out.append(f"<caption>{caption}</caption>")
    out.append("<thead><tr>")
    for i, h in enumerate(headers):
        c = ' class="n"' if i in num else ""
        out.append(f"<th{c}>{h if raw_headers else esc(h)}</th>")
    out.append("</tr></thead><tbody>")
    for r in rows:
        out.append("<tr>")
        for i, cell in enumerate(r):
            if isinstance(cell, tuple):        # (html, sort_value): shown as html, sorted by the value
                html_, v = cell
                c = "n" if i in num or isinstance(v, (int, float)) else ""
                out.append(f'<td class="{c}" data-v="{esc(v)}">{html_}</td>')
            elif isinstance(cell, (int, float)) and not isinstance(cell, bool):
                out.append(f'<td class="n" data-v="{cell}">{fmt(cell)}</td>')
            elif cell is None:
                out.append('<td class="n0">–</td>')
            else:
                c = ' class="n"' if i in num else ""
                out.append(f"<td{c}>{cell}</td>")
        out.append("</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def infobox(title, rows, image=None, image_alt="", subtitle=None, cls=""):
    """Right-hand summary box. rows: list of (label, html) — a row with label None is a full-width sub header."""
    out = [f'<aside class="infobox {cls}"><div class="ibh">{esc(title)}</div>']
    if subtitle:
        out.append(f'<div class="ibs">{subtitle}</div>')
    if image:
        out.append(f'<div class="ibimg"><img src="{esc(image)}" alt="{esc(image_alt or title)}" loading="lazy"></div>')
    out.append("<dl>")
    for label, value in rows:
        if label is None:
            out.append(f'<dt class="sub">{value}</dt>')
        elif value not in (None, ""):
            out.append(f"<dt>{esc(label)}</dt><dd>{value}</dd>")
    out.append("</dl></aside>")
    return "".join(out)


def bar(title, right="", id=None, level=2):
    """The white header bar of the game's menus ('EXPERIMENTAL SCHEMATIC TREE  ...  5 / 24 unlocked')."""
    i = f' id="{esc(id or slug(title))}"'
    return f'<h{level} class="wbar"{i}><span>{esc(title)}</span>{f"<small>{right}</small>" if right else ""}</h{level}>'


def fold(title, body, open=False, right="", id=None, level=2, cls=""):
    """A collapsible section: the white bar (level 2, listed in the contents bar) or a smaller sub bar (level 3)
    that opens and closes the body. Closed by default. A contents-bar link or a #link to it opens it."""
    i = esc(id or slug(title))
    head = (f'<h2 class="wbar" id="{i}"><span>{esc(title)}</span>{f"<small>{right}</small>" if right else ""}</h2>'
            if level == 2 else
            f'<h3 class="wbar3" id="{i}"><span>{esc(title)}</span>{f"<small>{right}</small>" if right else ""}</h3>')
    return (f'<details class="fold l{level} {cls}"{" open" if open else ""}><summary>{head}</summary>'
            f'<div class="foldbody">{body}</div></details>')


def panel(title, body, cls=""):
    """A box for the right-hand column, under the infobox (site.page(side=[...]))."""
    return f'<section class="sidepanel {cls}"><div class="ibh">{esc(title)}</div><div class="spb">{body}</div></section>'


def switcher(views, cls="", extra=""):
    """Picture (or any HTML) you can switch between with buttons: views = [(label, html)]; extra = HTML added to the
    button row (e.g. a disabled 3D viewer button)."""
    panes = "".join(f'<div class="swpane{" on" if i == 0 else ""}">{h}</div>' for i, (l, h) in enumerate(views))
    btns = "".join(f'<button type="button" class="{"on" if i == 0 else ""}">{esc(l)}</button>'
                   for i, (l, h) in enumerate(views))
    return f'<div class="switcher {cls}"><div class="swpanes">{panes}</div><div class="swbtns">{btns}{extra}</div></div>'


def maplink(show=(), region=(), at=None, zoom=None, focus=None):
    """URL of the interactive map showing only these categories / regions, centred on at=(x, z), with the popup
    of the marker named focus open. show: markers.json sub keys ('gnomes', 'sch_ammo', 'playersafehouses',
    'controlpoints', 'relaybeacons' ...), 'loc_<kind>' for locations ('loc_church'), loot.json sub keys
    ('loot_w_q5' ...). region: region keys."""
    from urllib.parse import quote
    q = []
    if show:
        q.append("show=" + ",".join(show))
    if region:
        q.append("region=" + ",".join(region))
    if at:
        q.append(f"at={round(at[0], 1)},{round(at[1], 1)}")
    if zoom:
        q.append(f"zoom={zoom}")
    if focus:
        q.append("focus=" + quote(str(focus)))
    return "~/map/index.html" + ("?" + "&amp;".join(q) if q else "")


def note(html_text, kind="info", title=None):
    """Callout. kind: info | warn | fix (a correction of outdated info) | data (about where numbers come from)."""
    t = {"info": "Note", "warn": "Heads up", "fix": "Corrected", "data": "From the game files"}.get(kind, kind)
    return f'<div class="callout {kind}"><b>{esc(title or t)}</b><div>{html_text}</div></div>'


def cards(items, cls=""):
    """Grid of link cards. items: dicts with href, title, and optional img, sub (html), tag, color."""
    out = [f'<div class="cards {cls}">']
    for it in items:
        img = f'<img src="{esc(it["img"])}" alt="" loading="lazy">' if it.get("img") else ""
        tg = f'<span class="ctag" style="background:{esc(it.get("color", "#47545a"))}">{esc(it["tag"])}</span>' \
            if it.get("tag") else ""
        sub = f'<span class="csub">{it["sub"]}</span>' if it.get("sub") else ""
        out.append(f'<a class="card" href="{esc(it["href"])}" style="--c:{esc(it.get("color", "#47545a"))}">'
                   f'<span class="chead"><span class="ctitle">{esc(it["title"])}</span>{tg}</span>'
                   f'<span class="cbody">{img}{sub}</span></a>')
    out.append("</div>")
    return "".join(out)


def kv(rows):
    """Small two-column definition list inside the text."""
    return '<dl class="kv">' + "".join(f"<dt>{esc(k)}</dt><dd>{v}</dd>" for k, v in rows if v not in (None, "")) + "</dl>"


def minimap(x, z, label="", zoom=3, height=260, markers=None, show=(), region=(), focus=None, small=False,
            text="", map_zoom=None):
    """A small piece of the world map centred on world coordinates x, z (the same units as the interactive map and
    the game's own coordinates). markers: optional extra [(x, z, label)]. Drawn by wiki.js from docs/map tiles.
    show / region / focus: the filters the 'Open the full map' button applies (see maplink()), so the full map
    shows the same markers. small=True: a compact square map with `text` (HTML) to its right - for a map that is
    only an overview, placed at the end of a page."""
    pts = [(x, z, label)] + list(markers or [])
    data = esc(json.dumps([[round(a, 1), round(b, 1), c] for a, b, c in pts]))
    one = not markers
    href = maplink(show, region, at=(x, z) if one else None, zoom=map_zoom or (0.6 if one else None),
                   focus=focus if focus is not None else (label if one and show else None))
    if small:
        size = min(height, 240)
        return (f'<div class="mmrow"><div class="minimap small" data-pts="{data}" data-zoom="{zoom}" '
                f'style="height:{size}px;width:{size}px"><a class="mmopen" href="{href}">Full map</a></div>'
                f'<div class="mmtext">{text}</div></div>')
    return (f'<div class="minimap" data-pts="{data}" data-zoom="{zoom}" style="height:{height}px">'
            f'<a class="mmopen" href="{href}">Open the full map</a></div>')


# ---------------------------------------------------------------------------------------------------------------
class Site:
    def __init__(self, out=DOCS):
        self.out = out
        self._data = {}
        self.registry = {}      # (kind, norm(key)) -> entry
        self.pages = {}         # path -> True (written)
        self.search = []        # search index entries
        self.missing = {}       # (kind, key) -> count (links to things nobody registered)
        self.warnings = []
        self.only = None        # set of section names to build (for quick iteration)

    # ---------------------------------------------------------------- data
    def data(self, name):
        """Parsed JSON from build/data/<name>.json (cached)."""
        if name not in self._data:
            with open(os.path.join(DATA, name if name.endswith(".json") else name + ".json"), encoding="utf-8") as f:
                self._data[name] = json.load(f)
        return self._data[name]

    def warn(self, msg):
        self.warnings.append(msg)

    # ---------------------------------------------------------------- registry and links
    def register(self, kind, key, path, title, icon=None, desc=None, aliases=(), search=True, keywords=""):
        """Announce a page (or an anchor: path may contain '#...'). key and aliases are matched with norm().
        Registered pages go into the search index with their kind as the label."""
        e = {"kind": kind, "key": key, "path": path, "title": title, "icon": icon, "desc": desc}
        for k in [key, title, *aliases]:
            if k is None or k == "":
                continue
            nk = (kind, norm(k))
            if nk in self.registry and self.registry[nk]["path"] != path:
                # the first registration wins; a duplicate name with another target is worth knowing about
                if norm(k) == norm(key):
                    self.warn(f"duplicate {kind} key {k!r}: {self.registry[nk]['path']} vs {path}")
                continue
            self.registry[nk] = e
        if search:
            self.search.append({"t": title, "k": kind, "u": path, "d": (desc or "")[:140], "w": keywords,
                                "i": icon or ""})
        return e

    def find(self, kind, key):
        if key is None:
            return None
        return self.registry.get((kind, norm(key)))

    def url(self, kind, key, default=None):
        e = self.find(kind, key)
        if e:
            return "~/" + e["path"]
        self.missing[(kind, str(key))] = self.missing.get((kind, str(key)), 0) + 1
        return default

    def link(self, kind, key, text=None, cls="", icon=False):
        """<a> to a registered page, or plain text when there's none (recorded in the build report)."""
        e = self.find(kind, key)
        label = esc(text if text is not None else (e["title"] if e else key))
        if not e:
            self.missing[(kind, str(key))] = self.missing.get((kind, str(key)), 0) + 1
            return f'<span class="nolink">{label}</span>'
        ic = f'<img class="li" src="~/{esc(e["icon"])}" alt="" loading="lazy">' if icon and e.get("icon") else ""
        c = f' class="{cls}"' if cls else ""
        return f'<a href="~/{esc(e["path"])}"{c}>{ic}{label}</a>'

    def img(self, path, alt="", cls="", title=None):
        """<img> for a file under docs/ (path relative to the site root, e.g. 'img/items/weapons/x.png').
        Returns '' (and warns) when the file doesn't exist, so a missing icon never shows as a broken image."""
        if not path:
            return ""
        if not os.path.exists(os.path.join(self.out, path)):
            self.warn(f"missing image {path}")
            return ""
        t = f' title="{esc(title)}"' if title else ""
        return f'<img class="{esc(cls)}" src="~/{esc(path)}" alt="{esc(alt)}"{t} loading="lazy">'

    def has_file(self, path):
        return os.path.exists(os.path.join(self.out, path))

    # ---------------------------------------------------------------- pages
    def page(self, path, title, body, section, sub=None, crumbs=None, desc="", infobox_html="", toc=True,
             kind=None, search=None, wide=False, head_extra="", lead="", side=None):
        """Write one page.

        path      file path relative to the site root, e.g. 'weapons/n9-handgun.html'
        title     page title (h1)
        body      the page's HTML (use "~/" for site-root links)
        section   top tab id from NAV; sub: sub tab id (defaults to the first one whose path == path)
        crumbs    [(label, '~/path')] shown above the title (the section is added automatically)
        desc      one-line description (meta description, search result text)
        infobox_html  the right-hand box (wiki.site.infobox())
        toc       build a table of contents from the h2 bars when there are 3 or more
        kind      label shown above the title (e.g. 'Weapon · Handgun')
        search    False to keep the page out of the search index (pages registered with site.register are
                  already in it); or a dict(k=kind, w=keywords) to add it
        wide      no max width for the text column (big tables)
        lead      intro paragraph(s) shown under the title
        side      HTML (or a list of HTML blocks, e.g. panel()) for the right-hand column, under the infobox.
                  The contents bar (every h2 bar and level-2 fold of the body) sits at the bottom of that column
                  and stays on screen while you scroll.
        """
        nav = NAV_BY_ID[section]
        if sub is None:
            sub = next((s["id"] for s in nav["subs"] if s["path"] == path), None)
        depth = path.count("/")
        root = "../" * depth
        heads = re.findall(r'<h2 class="wbar" id="([^"]+)"><span>(.*?)</span>', body)
        toc_html = ""
        if toc and len(heads) >= 2:
            toc_html = '<nav class="toc" aria-label="Contents"><div class="toch">Contents</div>' + "".join(
                f'<a href="#{i}">{t}</a>' for i, t in heads) + "</nav>"
        if isinstance(side, (list, tuple)):
            side = "".join(x for x in side if x)
        side = side or ""
        has_rail = bool(infobox_html or side or toc_html)
        crumbs = [(nav["label"], "~/" + nav["path"])] + list(crumbs or [])
        crumb_html = '<div class="crumbs">' + " <span>/</span> ".join(
            f'<a href="{esc(u)}">{esc(l)}</a>' for l, u in crumbs) + "</div>"
        tabs = "".join(
            f'<a class="tab{" on" if n["id"] == section else ""}" href="~/{n["path"]}">{esc(n["label"])}</a>'
            for n in NAV if not n.get("hidden"))
        subs = "".join(
            f'<a class="stab{" on" if s["id"] == sub else ""}" href="~/{s["path"]}">{esc(s["label"])}</a>'
            for s in nav["subs"])
        kind_html = f'<div class="kind">{esc(kind)}</div>' if kind else ""
        doc = TEMPLATE.format(
            title=esc(title), site=SITE_NAME, desc=esc(desc or f"{title} - {GAME} wiki"), color=nav["color"],
            tabs=tabs, subs=subs, crumbs=crumb_html, kind=kind_html, h1=esc(title), lead=lead,
            infobox=infobox_html, side=side, toc=toc_html, body=body, wide=" wide" if wide else "",
            hasbox=" hasrail" if has_rail else "", head_extra=head_extra, section=section)
        doc = re.sub(r'(href|src|data-src|data-root|action)="~/', lambda m: f'{m.group(1)}="{root}', doc)
        doc = doc.replace("url(~/", f"url({root}")
        dst = os.path.join(self.out, path)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "w", encoding="utf-8", newline="\n") as f:
            f.write(doc)
        if path in self.pages:
            self.warn(f"page written twice: {path}")
        self.pages[path] = True
        if isinstance(search, dict) and not any(s["u"] == path for s in self.search):
            self.search.append({"t": title, "k": search.get("k", nav["label"]), "u": path, "d": (desc or "")[:140],
                                "w": search.get("w", ""), "i": search.get("i", "")})
        elif search is None and not any(s["u"].split("#")[0] == path for s in self.search):
            self.search.append({"t": title, "k": nav["label"], "u": path, "d": (desc or "")[:140], "w": "", "i": ""})

    # ---------------------------------------------------------------- finishing
    def write_static(self):
        dst = os.path.join(self.out, "assets")
        os.makedirs(dst, exist_ok=True)
        for f in os.listdir(STATIC):
            shutil.copy2(os.path.join(STATIC, f), os.path.join(dst, f))
        open(os.path.join(self.out, ".nojekyll"), "w").close()

    def write_search(self):
        seen, out = set(), []
        for s in self.search:
            if s["u"].split("#")[0] not in self.pages:
                continue
            k = (s["u"], s["t"])
            if k in seen:
                continue
            seen.add(k)
            out.append(s)
        with open(os.path.join(self.out, "assets", "search.json"), "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
        return len(out)

    def check_links(self):
        """Every '~/' link resolved by page() must point at a written page or an existing file."""
        bad = {}
        known = set(self.pages) | {e["path"].split("#")[0] for e in self.registry.values()}
        for path in self.pages:
            with open(os.path.join(self.out, path), encoding="utf-8") as f:
                doc = f.read()
            base = os.path.dirname(path)
            for m in re.finditer(r'(?:href|src)="([^"#?]+)', doc):
                u = m.group(1)
                if re.match(r"^[a-z]+:", u) or u.startswith("//"):
                    continue
                tgt = os.path.normpath(os.path.join(base, u)).replace("\\", "/")
                if tgt.endswith("/") or tgt == ".":
                    tgt = (tgt.rstrip("/") + "/index.html").lstrip("./")
                if tgt not in known and not os.path.exists(os.path.join(self.out, tgt)):
                    bad.setdefault(tgt, set()).add(path)
        return bad


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · {site}</title>
<meta name="description" content="{desc}">
<link rel="icon" href="~/assets/app.ico">
<link rel="preload" href="~/assets/OpenSans-Regular.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="~/assets/OpenSans-Bold.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="~/assets/wiki.css?v=2">
{head_extra}
</head>
<body data-section="{section}" style="--bar:{color}" data-root="~/">
<div class="bg"></div>
<header class="topbar">
  <a class="brand" href="~/index.html"><img src="~/assets/logo.png" alt="Generation Zero"><span>WIKI</span></a>
  <button class="menubtn" id="menuBtn" aria-label="Menu" aria-expanded="false"><svg viewBox="0 0 20 20"><path d="M2 4h16v2H2zm0 5h16v2H2zm0 5h16v2H2z"/></svg></button>
  <nav class="tabs" id="tabs">{tabs}</nav>
  <div class="search"><input id="q" type="search" placeholder="Search the wiki" autocomplete="off" aria-label="Search"><div class="results" id="results" hidden></div></div>
</header>
<nav class="subbar">{subs}</nav>
<main class="content{wide}{hasbox}">
  <div class="head">{crumbs}
  {kind}<h1>{h1}</h1>
  <div class="lead">{lead}</div></div>
  <aside class="rail"><div class="railtop">{infobox}{side}</div>{toc}</aside>
  <article class="body">
{body}
  </article>
</main>
<footer class="hintbar">
  <span><b>[/]</b> SEARCH</span><span><b>[H]</b> HOME</span><span><b>[M]</b> MAP</span>
  <span class="fine">Fan-made. All data read straight from the game files with a custom extraction tool (<a href="~/about.html">about</a>). Generation Zero is a trademark of Systemic Reaction / Avalanche Studios Group.</span>
</footer>
<script src="~/assets/wiki.js?v=2"></script>
</body>
</html>
"""
