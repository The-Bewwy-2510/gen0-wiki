"""Machines tab: the machine overview (factions and types, classes, comparison table), one page per machine type
with every class and layout, and the detection & stealth page.

Data (build/data):
  stats.json          machine_health     faction -> class -> type -> layout -> components (HP each, count,
                                         component or armour) and total_component_health
                      machine_detection  faction -> class -> type -> unaware / alerted senses per stance
                      machine_weapons    colloquial name -> damage, kind, used_by (machine names like
                                         'Tank (Prototype)'); the keys of the 'machine-weapon' kind
                      _about.reading_the_numbers  the caveats we pass on to the reader
  loadouts.json       faction -> class -> type -> layout -> in-game name, weapons, deployment notes
  machine_images.json type -> class -> picture (from the Fandom wiki, CC BY-SA: credited under each picture)
  markers.json        the machine blueprints (collectibles, sub 'blueprints') shown on a small map on each type page

Layout v2: no internal names, file names or hashes are printed (they stay search aliases). The 'Class X' Tick in
the files is unused and left out; the Gnome Tick class is shown as the green 'Event' class.

Kinds registered: 'machine' -- type pages ('Tank', 'Reaper', ... plus internal names like 'dreadnought'), class
anchors ('Tank (Prototype)' -> machines/tank.html#prototype, as spelled in stats.json used_by), 'Machines',
'Detection', and the class names ('Scout class', 'Spetsnaz', ... -> machines/index.html#the-class-system).

Name clash: the Seeker's internal name is 'scout', so site.link('machine', 'Scout') goes to the Seeker page.
For the Soviet Scout class link 'Scout class' (or a class anchor such as 'Firebird (Scout)').
"""
import re

from wiki.site import (esc, slug, norm, fmt, pct, table, bar, fold, note, kv, tag, switcher, maplink, minimap,
                       REGIONS)

CSS = '<link rel="stylesheet" href="~/assets/machines.css?v=2">'
STANCES = ("prone", "crouch", "stand", "run")
STANCE_NAME = {"prone": "Prone", "crouch": "Crouched", "stand": "Standing", "run": "Running"}
REGION_NAME = dict(REGIONS)

# Faction colours. The Rival of a faction is a more saturated version of the faction colour; the Event class
# (the Gnome Tick) is green. The same colours are the .mf-* classes in machines.css.
FACTION_COLOR = {"Swedish": "#2f5e7a", "Soviet": "#8b2a20", "Swedish Rival": "#0b6fb8", "Soviet Rival": "#cc1a08",
                 "Event": "#2e8b3e"}
FACTION_CLS = {"Swedish": "mf-swe", "Soviet": "mf-sov", "Swedish Rival": "mf-swer", "Soviet Rival": "mf-sovr",
               "Event": "mf-event"}

# The unique Rival-class machines get their own page instead of a class section on their base type's page.
BOSSES = {("Swedish", "Tank"): "Reaper", ("Soviet", "Firebird"): "Vulture"}
SKIP_CLASSES = {"Class X (unidentified)"}   # in the files, but unused in the game (owner: leave it out)

# Page order and the short hand-written introduction of each machine type. Everything with a number in it is
# computed from the data on the page itself; these blurbs only say what kind of machine it is.
TYPES = {
    "Tank": "The Tank is the biggest walking war machine of the Swedish (FNIX-built) robots: a heavily armoured "
            "four-class family with two heavy weapon mounts, a concussion or neurotoxin ability and a stomp for "
            "anyone who gets close.",
    "Harvester": "The Harvester is a large Swedish machine built around a single big rocket pod on its back and a "
                 "body packed with Core Drives. It backs that up with concussion pulses, neurotoxin gas and, in "
                 "the later classes, its own Ticks.",
    "Hunter": "The Hunter is the fast, agile mid-sized Swedish machine: a gun on its back, blades for jump and "
              "melee attacks, and it can be flown in as reinforcements in a rocket pod.",
    "Tick": "Ticks are the smallest machines in the game. They rush you and latch on, and some classes explode "
            "instead. Bigger machines with a Tick Storage component release them in battle. This page also "
            "covers the special Gnome Tick of the events.",
    "Seeker": "The Seeker is a small flying scout. It carries no weapons at all: its job is to spot you, and it "
              "has some of the sharpest senses of any Swedish machine.",
    "Runner": "The Runner is the small, common ground machine most players fight first: one light gun or "
              "launcher and a kick, and it often arrives as reinforcements in a rocket pod.",
    "Firebird": "The Firebird is the Soviet flying gunship: an autocannon or howitzer, two bomb bays and four "
                "vectored-thrust jets keeping it in the air.",
    "Lynx": "The Lynx is the small, quick Soviet machine with a spinning saw blade on its front and a rifle, "
            "grenade launcher or flamethrower on top.",
    "Wolf": "The Wolf is the heavy Soviet ground machine: a gatling gun, missile pods and neurotoxin, and on "
            "some layouts a field that heals the machines around it.",
    "Reaper": "The Reaper is the unique Rival-class Tank, by far the toughest machine in the game files. It "
              "carries radiated missiles, an incendiary machine gun, Ticks, neurotoxin, a shield against your "
              "weapons and a huge thermobaric blast.",
    "Vulture": "The Vulture is the unique Rival-class Firebird. Besides a rocket pod and a flamethrower it drops "
               "beacons, gas canisters and turrets from its bomb bays.",
}

FACTIONS = {
    "Swedish": "The machines that took over Sweden, built by the FNIX company. Four regular classes: Prototype, "
               "Military, FNIX and Apocalypse.",
    "Soviet": "The Soviet machines arrived later in the story. Their classes have their own names: Scout, Soldier "
              "and Spetsnaz.",
    "Swedish Rival": "The Swedish Rival class holds a single unique machine.",
    "Soviet Rival": "The Soviet Rival class holds a single unique machine.",
}

# Classes: (faction, class) -> short description. Strength comparisons are computed, not written here.
CLASSES = {
    ("Swedish", "Prototype"): "The first and weakest generation of the Swedish machines.",
    ("Swedish", "Military"): "The second generation: tougher, with more weapon choices. The only class with "
                             "'green' layout variants in the files.",
    ("Swedish", "FNIX"): "The third generation, named after the company that builds the machines. Many FNIX "
                         "machines carry Ticks.",
    ("Swedish", "Apocalypse"): "The strongest regular class, with fire, radiation and toxin weapons (Wall of Flame, "
                               "radiated blades, a contaminated submachine gun, cluster mines).",
    ("Swedish", "Rival"): "A single unique machine: the Reaper, a Tank.",
    ("Swedish", "Gnome"): "A special Tick class of the game's events, with its own senses.",
    ("Soviet", "Scout"): "The first and weakest class of the Soviet machines.",
    ("Soviet", "Soldier"): "The second Soviet class.",
    ("Soviet", "Spetsnaz"): "The strongest regular Soviet class.",
    ("Soviet", "Rival"): "A single unique machine: the Vulture, a Firebird.",
}
CLASS_TAG = {"FNIX": ("FNIX", "fnix"), "Apocalypse": ("Apocalypse", "exp")}

DASH = '<span class="dim">–</span>'
CUBE = ('<button type="button" class="swx" disabled title="3D viewer (coming soon)" aria-label="3D viewer (coming '
        'soon)"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2.5 3.5 7v10l8.5 4.5 8.5-4.5V7z"/>'
        '<path d="M3.5 7 12 11.5 20.5 7M12 11.5v10"/></svg></button>')
NOPIC = ('<div class="mnopic"><svg viewBox="0 0 64 48" aria-hidden="true"><path d="M14 30h36l-4-14H18z"/>'
         '<circle cx="32" cy="22" r="4"/><path d="M20 30l-6 14M44 30l6 14M28 30l-2 14M36 30l2 14"/></svg>'
         '<span>No picture yet</span></div>')
_CACHE = {}


# ---------------------------------------------------------------------------------------------------------------
# data model
# ---------------------------------------------------------------------------------------------------------------
def _same(a, b):
    """Two layouts are the same machine when components and weapons match (names in the files may differ)."""
    if a["health"]["components"] != b["health"]["components"]:
        return False
    wa = [(w["internal_name"], w.get("ammo_internal_name")) for w in (a["loadout"] or {}).get("weapons", [])]
    wb = [(w["internal_name"], w.get("ammo_internal_name")) for w in (b["loadout"] or {}).get("weapons", [])]
    return wa == wb


def _groups(health_layouts, loadout_layouts):
    """Layouts of one class, with '_green' variants and a 'Base' entity folded into the layout they duplicate.
    Returns [{label, health, loadout, files: [(internal name, what)], same_as}]."""
    items = [{"label": k, "health": v, "loadout": loadout_layouts.get(k)} for k, v in health_layouts.items()]
    main = [i for i in items if "(green variant)" not in i["label"] and i["label"] != "Base"]
    extra = [i for i in items if i not in main]
    groups = [dict(i, files=[(i["health"]["internal_name"], "layout")], same_as=None) for i in main]
    for e in extra:
        base = e["label"].replace(" (green variant)", "")
        target = next((g for g in groups if g["label"] == base and _same(g, e)), None)
        if target is None and e["label"] == "Base":
            target = next((g for g in groups if _same(g, e)), None)
        what = "green variant" if "green" in e["label"] else "base entity"
        if target is None:  # differs from everything: keep it as a layout of its own
            groups.append(dict(e, files=[(e["health"]["internal_name"], what)], same_as=None))
        else:
            target["files"].append((e["health"]["internal_name"], what))
    for i, g in enumerate(groups):  # two different layout files that carry exactly the same machine
        g["same_as"] = next((h["label"] for h in groups[:i] if _same(h, g)), None)
    return groups


def model(site):
    if id(site) in _CACHE:
        return _CACHE[id(site)]
    st = site.data("stats")
    lo = site.data("loadouts")
    imgs = site.data("machine_images").get("images", {})
    health, senses = st["machine_health"], st["machine_detection"]
    types = {}       # page name -> {name, faction, path, slug, internal, variants}
    variants = []    # one per (faction, class, type)
    for fac, classes in health.items():
        for cls, cd in classes.items():
            if cls in SKIP_CLASSES:
                continue
            for typ, td in cd["types"].items():
                page = BOSSES[(fac, typ)] if cls == "Rival" else typ
                lt = lo.get(fac, {}).get(cls, {}).get("types", {}).get(typ, {}).get("layouts", {})
                groups = _groups(td["layouts"], lt)
                first = groups[0]
                mach = (first["loadout"] or {}).get("machine", {})
                v = {"faction": fac, "cls": cls, "type": typ, "page": page, "internal_class": cd["internal_name"],
                     "internal_type": td["internal_name"], "machine": first["health"]["machine"],
                     "in_game": mach.get("in_game_name"), "anchor": slug(cls), "groups": groups,
                     "senses": senses.get(fac, {}).get(cls, {}).get(typ),
                     "image": imgs.get(page, {}).get(cls)}
                v["totals"] = [g["health"]["total_component_health"] for g in groups]
                v["key"] = f"{typ} ({cls})" if page == typ else f"{typ} (Rival)"
                v["alias_names"] = [v["machine"]] if v["machine"] != v["key"] else []
                v["group"] = group_of(v)
                v["weapons"] = _class_weapons(site, v)
                variants.append(v)
                t = types.setdefault(page, {"name": page, "faction": fac, "slug": slug(page),
                                            "path": f"machines/{slug(page)}.html", "internal": td["internal_name"],
                                            "variants": []})
                t["variants"].append(v)
    order = list(TYPES)
    types = {k: types[k] for k in sorted(types, key=lambda n: order.index(n) if n in order else 99)}
    for t in types.values():
        t["group"] = t["variants"][0]["group"] if t["name"] in BOSSES.values() else t["faction"]
    m = {"types": types, "variants": variants, "about": st["_about"]["reading_the_numbers"]}
    m["blueprints"] = blueprints(site, m)
    _CACHE[id(site)] = m
    return m


def group_of(v):
    """Colour group of a machine class: 'Swedish', 'Soviet', 'Swedish Rival', 'Soviet Rival' or 'Event'."""
    if v["cls"] == "Gnome":
        return "Event"
    return f"{v['faction']} Rival" if v["cls"] == "Rival" else v["faction"]


def blueprints(site, m):
    """Machine blueprint collectibles (markers.json): type page name -> [(variant or None, marker)].
    'Blueprint - Tick Class A' (A..D = classa..classd), 'Soviet Blueprint - Lynx Class B',
    'Rival Blueprint - Reaper (Tank)'; the type is matched by name or internal name ('Skirmisher' = Runner)."""
    out = {}
    by_internal = {}
    for t in m["types"].values():
        by_internal[norm(t["name"])] = t
        if t["name"] not in BOSSES.values():
            by_internal.setdefault(norm(t["internal"]), t)
    for it in site.data("markers").get("items", []):
        if it.get("s") != "blueprints":
            continue
        mt = re.match(r"^(?:(Soviet|Rival) )?Blueprint - (.+?)(?: Class ([A-Z]))?$", it["n"])
        if not mt:
            continue
        kind, name, letter = mt.groups()
        name = re.sub(r"\s*\(.*\)$", "", name)
        t = by_internal.get(norm(name))
        if not t:
            continue
        fac = "Soviet" if kind == "Soviet" else t["faction"]
        v = next((x for x in t["variants"] if x["faction"] == fac and
                  (x["internal_class"] == f"class{letter.lower()}" if letter else x["cls"] == "Rival")), None)
        out.setdefault(t["name"], []).append((v, it))
    return out


def mw_key(site, w, machine):
    """The stats.json machine_weapons key for a loadout weapon: matched by internal name, and by the machine name
    in used_by when one internal name has several entries (the Firebird autocannon's two ammo types)."""
    mws = site.data("stats")["machine_weapons"]
    cands = [k for k, d in mws.items() if d["internal_name"] == w["internal_name"]]
    if len(cands) > 1:
        cands = [k for k in cands if machine in mws[k].get("used_by", [])] or cands
    return cands[0] if cands else None


def _class_weapons(site, v):
    """Ordered unique weapons of a class: [{key: machine-weapon key or name, name, layouts: [labels]}]."""
    out = {}
    for g in v["groups"]:
        for w in (g["loadout"] or {}).get("weapons", []):
            k = mw_key(site, w, v["machine"]) or w["colloquial_name"]
            e = out.setdefault(k, {"key": k, "name": w["colloquial_name"], "layouts": []})
            if g["label"] not in e["layouts"]:
                e["layouts"].append(g["label"])
    return list(out.values())


# ---------------------------------------------------------------------------------------------------------------
# small formatting helpers
# ---------------------------------------------------------------------------------------------------------------
_IDENT = re.compile(r"\b[a-z][a-z0-9]*_[a-z0-9_]+\b")


def clean_note(site, text):
    """A note from the data without internal names: a quoted ammo name becomes the weapon it belongs to,
    parentheses holding an internal name go, and so do sentences that are only about internal names."""
    if not text:
        return ""
    def ammo(mt):
        k = mt.group(1)
        if k.endswith("_incendiary"):
            return "incendiary rounds"
        if k.endswith("_ac"):
            return "explosive rounds"
        return "different ammo"
    text = re.sub(r"'(machine_ammo_[a-z0-9_]+)'", ammo, text)
    text = re.sub(r"\s*\([^()]*\b[a-z][a-z0-9]*_[a-z0-9_]+\b[^()]*\)", "", text)
    text = text.replace("AreaDamage component", "area damage").replace("AreaDamage", "area damage")
    sents = re.split(r"(?<=[.!?])\s+", text.strip())
    keep = [s for s in sents if not _IDENT.search(s) and not s.startswith("Internal name")]
    return " ".join(keep)


def hp_range(totals):
    lo_, hi = min(totals), max(totals)
    return fmt(lo_) if lo_ == hi else f"{fmt(lo_)}–{fmt(hi)}"


def dist(x, digits=1):
    """A distance with its unit: 16.5 -> '16.5 m', 1210 -> '1.21 km'."""
    if x is None:
        return "–"
    if x >= 1000:
        return f"{fmt(x / 1000, 2)} km"
    return f"{fmt(x, digits)} m"


def deg(x):
    return "–" if x is None else f"{fmt(x)}°"


def dcell(x):
    """Sortable table cell for a distance."""
    return (dist(x), x) if x is not None else None


def class_title(v):
    if v["cls"] == "Gnome":
        return "Gnome Tick (Event)"
    return "Rival class" if v["cls"] == "Rival" else f"{v['cls']} class"


def class_label(v):
    """Short label of a class for buttons and column headers."""
    return "Event" if v["cls"] == "Gnome" else v["cls"]


def gtag(group, text=None):
    """Coloured tag of a faction group (Swedish / Soviet / Swedish Rival / Soviet Rival / Event)."""
    return f'<span class="tag {FACTION_CLS[group]}">{esc(text or group)}</span>'


def class_tags(v):
    out = gtag(v["faction"]) if v["group"] != "Event" else ""
    if v["group"] != v["faction"]:
        out += gtag(v["group"], "Rival" if v["cls"] == "Rival" else "Event")
    if v["cls"] in CLASS_TAG:
        out += tag(*CLASS_TAG[v["cls"]])
    return out


def mlink(site, v, text=None):
    """Link to a machine class anchor."""
    return site.link("machine", v["key"], text or v["machine"])


def wlink(site, w):
    return site.link("machine-weapon", w["key"], w["name"]) if w["key"] else esc(w["name"])


def page_link(site, path, text, anchor=""):
    """Link to a page another section owns, found through the registry (plain text while it doesn't exist)."""
    if any(e["path"].split("#")[0] == path for e in site.registry.values()):
        return f'<a href="~/{path}{"#" + anchor if anchor else ""}">{esc(text)}</a>'
    return esc(text)


def blast_text(b, verb="blast"):
    rp, rm = b.get("radius_vs_players_m"), b.get("radius_vs_machines_m")
    r = f"{fmt(rp)} m" if rp == rm else f"{fmt(rp)} m / {fmt(rm)} m"
    return f"{verb} {fmt(b.get('damage_to_players'))} to you, {fmt(b.get('damage_to_machines'))} to machines ({r})"


def dmg_text(d):
    """One-line summary of a machine weapon's damage block from stats.json (details on the machine weapons page)."""
    if not d:
        return '<span class="dim">no damage values</span>'
    parts = []
    dpp, pps = d.get("damage_per_projectile"), d.get("projectiles_per_shot") or 1
    if dpp:
        parts.append(f"{fmt(dpp)} per hit" + (f" × {pps} pellets" if pps > 1 else ""))
    elif pps > 1:
        parts.append(f"{pps} projectiles per shot")
    if d.get("blast"):
        parts.append(blast_text(d["blast"]))
    if d.get("submunition"):
        n = d.get("submunitions")
        sub = d["submunition"]
        parts.append((f"{n} bomblets, each " if n else "bomblets, each ") +
                     (blast_text(sub["blast"]) if sub.get("blast") else "–"))
    for dot in d.get("damage_over_time") or []:
        parts.append(f"+{fmt(dot['damage_per_tick'])} every {fmt(dot['tick_seconds'])} s for "
                     f"{fmt(dot['duration_seconds'])} s to {esc(dot.get('target', ''))}")
    if d.get("contact"):
        c = d["contact"]
        parts.append(f"{fmt(c['damage_to_players_min'])}–{fmt(c['damage_to_players_max'])} to you on contact "
                     f"({fmt(c['radius_vs_players_m'])} m), every {fmt(c['repeat_interval_seconds'])} s")
    if d.get("heal_pulse"):
        h = d["heal_pulse"]
        parts.append(f"heals machines by {fmt(h['damage_to_machines'])} within {fmt(h['radius_vs_machines_m'])} m")
    return "; ".join(parts) or '<span class="dim">no damage values</span>'


def picture(site, v, small=False):
    """The class picture (or a placeholder) with its credit line."""
    im = v.get("image")
    tag_ = site.img(im["path"], alt=v["in_game"] or v["machine"]) if im else ""
    if not tag_:
        return NOPIC if not small else ""
    if small:
        return tag_
    if im.get("source") == "render":
        return tag_ + '<span class="swcap">Rendered from the game\'s own 3D model</span>'
    return (tag_ + f'<span class="swcap">Picture: <a href="{esc(im["source"])}" rel="nofollow">Generation Zero '
                   f'Wiki</a> (CC BY-SA)</span>')


def tr_attrs(table_html, attrs):
    """table() has no row attributes: add attrs[i] (e.g. 'data-f="soviet"') to the i-th body row."""
    head, _, rest = table_html.partition("<tbody>")
    rows = rest.split("<tr>")
    out = [rows[0]] + [f"<tr {a}>" + r for a, r in zip(attrs, rows[1:])]
    return head + "<tbody>" + "".join(out)


# ---------------------------------------------------------------------------------------------------------------
# registry
# ---------------------------------------------------------------------------------------------------------------
def collect(site):
    m = model(site)
    site.register("machine", "Machines", "machines/index.html", "All machines",
                  desc="Every machine type and class in Generation Zero, compared.", aliases=["machine", "robots"],
                  keywords="machines robots classes factions")
    site.register("machine", "Detection", "machines/detection.html", "Detection & stealth",
                  desc="How far every machine sees and hears you, per stance, unaware and alerted.",
                  aliases=["stealth", "senses", "machine detection"], keywords="stealth detection sight hearing")
    for t in m["types"].values():
        v0 = t["variants"][0]
        img = next((v["image"]["path"] for v in t["variants"] if v.get("image") and site.has_file(v["image"]["path"])),
                   None)
        internal = [t["internal"]] if t["name"] not in BOSSES.values() else []
        prefix = [v0["groups"][0]["health"]["internal_name"].split("_")[0]] if internal else []
        aliases = internal + prefix + [t["name"] + "s"]
        if t["name"] in BOSSES.values():
            aliases += [v0["internal_type"] + "_" + v0["internal_class"]]
        site.register("machine", t["name"], t["path"], t["name"], aliases=aliases, icon=img,
                      desc=f"{t['faction']} machine · {len(t['variants'])} class(es) · total component health "
                           f"{hp_range([x for v in t['variants'] for x in v['totals']])}",
                      keywords=" ".join(aliases) + " machine")
    for v in m["variants"]:
        pfx = v["groups"][0]["health"]["internal_name"].rsplit("_load", 1)[0].rsplit("_base", 1)[0]
        aliases = v["alias_names"] + [f"{v['cls']} {v['type']}", pfx]
        aliases += [f for g in v["groups"] for f, _ in g["files"]]
        if v["in_game"]:
            aliases.append(v["in_game"])
        if v["cls"] == "Gnome":
            aliases += ["Event Tick", "Tick (Event)"]
        site.register("machine", v["key"], f"machines/{slug(v['page'])}.html#{v['anchor']}", v["machine"],
                      aliases=aliases, desc=f"{v['in_game'] or v['machine']} · {len(v['groups'])} layout(s) · "
                                            f"total component health {hp_range(v['totals'])}",
                      keywords=f"{v['type']} {v['cls']} {v['faction']} machine")
    register_classes(site)


def register_classes(site):
    """'Military class', 'Spetsnaz', ... -> the class table. Registered last so a bare class name never takes a
    name a machine already has; bare 'Scout' stays the Seeker (see the module docstring)."""
    for fac, cls in CLASSES:
        if (cls == "Rival" and fac == "Soviet") or cls == "Gnome":
            continue  # one 'Rival class' entry is enough; the Gnome Tick has its own anchor
        bare = [cls] if cls not in ("Scout", "Rival") else []
        site.register("machine", f"{cls} class", "machines/index.html#the-class-system", f"{cls} class",
                      aliases=bare + [f"{fac} {cls}"], search=False)
    site.register("machine", "Event class", "machines/tick.html#gnome", "Gnome Tick (Event class)",
                  aliases=["Event"], search=False)


# ---------------------------------------------------------------------------------------------------------------
# pages
# ---------------------------------------------------------------------------------------------------------------
def build(site):
    m = model(site)
    build_index(site, m)
    for t in m["types"].values():
        build_type(site, m, t)
    build_detection(site, m)


def caveat(m):
    return note(f"<p><b>Total component health</b>: {esc(m['about']['total_component_health'])}</p>", "data")


# ---------------------------------------------------------------- index
def build_index(site, m):
    vs = m["variants"]
    n_layouts = sum(len(v["groups"]) for v in vs)
    lead = ("<p>Generation Zero has two machine factions, the Swedish and the Soviet machines, and each has one "
            "unique Rival-class machine: the Reaper and the Vulture. The game files define "
            f"<b>{len(m['types'])} machine types</b> in <b>{len(vs)} type-and-class combinations</b> with "
            f"<b>{n_layouts} distinct layouts</b>. Pick a machine for its classes, weapons, component health and "
            "senses.</p>")
    b = [bar("Factions and machine types", f"{len(m['types'])} types")]
    b.append(faction_grid(site, m))
    b += class_system(site, m)
    b.append(comparison(site, m))
    b.append(bar("More about machines"))
    b.append("<ul>"
             f"<li>{page_link(site, 'machines/weapons.html', 'Machine weapons')}: the damage of every machine "
             "weapon, with the machines that use it.</li>"
             f"<li>{site.link('machine', 'Detection', 'Detection & stealth')}: sight and hearing distances per "
             "stance for every machine.</li>"
             f"<li>{page_link(site, 'machines/difficulty.html', 'Difficulty & co-op')}: how difficulty and the "
             "number of players scale machine health and damage.</li>"
             f"<li>{page_link(site, 'machines/rivals.html', 'Rivals')}: rival machines, their levels and "
             "titles.</li></ul>")
    site.page("machines/index.html", "Machines", "\n".join(b), "machines", lead=lead, head_extra=CSS,
              desc="Every Generation Zero machine type and class: factions, classes, layouts, health and weapons.")


def faction_grid(site, m):
    """2x2 grid: Swedish | Soviet / Reaper (Swedish Rival) | Vulture (Soviet Rival), each with its machine types."""
    cells = []
    for group in ("Swedish", "Soviet", "Swedish Rival", "Soviet Rival"):
        ts = [t for t in m["types"].values() if t["group"] == group]
        if not ts:
            continue
        rival = "Rival" in group
        title = ts[0]["name"] if rival else f"{group} machines"
        head = (f'<div class="mfh"><span>{esc(title)}</span>'
                f'{gtag(group, "Rival · " + group.split()[0] if rival else "Faction")}</div>')
        if rival:
            t = ts[0]
            v = t["variants"][0]
            pic = picture(site, v, small=True)
            base = site.link("machine", v["type"])
            body = (f'<a class="mfbig" href="~/{t["path"]}">{pic or NOPIC}</a>'
                    f'<p>{esc(FACTIONS[group])} The {site.link("machine", t["name"])} is a Rival-class {base}.</p>'
                    + kv([("Total health", f"{hp_range(v['totals'])} HP"),
                          ("Layouts", str(len(v["groups"]))),
                          ("Weapons", str(len(v["weapons"])))]))
        else:
            items = []
            for t in ts:
                tv = t["variants"]
                img = next((picture(site, v, small=True) for v in tv if picture(site, v, small=True)), "")
                n = sum(len(v["groups"]) for v in tv)
                cl = f"{len(tv)} classes"
                items.append(f'<li><a href="~/{t["path"]}"><span class="mfimg">{img}</span><span class="mft">'
                             f'<b>{esc(t["name"])}</b><span class="dim">{esc(cl)} · {n} layouts · '
                             f'{hp_range([x for v in tv for x in v["totals"]])} HP</span></span></a></li>')
            body = f'<p>{esc(FACTIONS[group])}</p><ul class="mftypes">{"".join(items)}</ul>'
        cells.append(f'<section class="mfcell {FACTION_CLS[group]}">{head}<div class="mfb">{body}</div></section>')
    fandom = any(isinstance(e, dict) and e.get("source", "render") != "render"
                 for cs in site.data("machine_images").get("images", {}).values() for e in cs.values())
    credit = ('<p class="small dim mcredit">Pictures rendered from the game\'s own 3D models'
              + (', a few still from the <a href="https://generation-zero.fandom.com/" rel="nofollow">Generation Zero '
                 'Wiki</a> (CC BY-SA)' if fandom else '') + '.</p>')
    return '<div class="mfgrid">' + "".join(cells) + "</div>" + credit


def class_system(site, m):
    """The class table and a type x class table of average layout health with the step from the first class."""
    b = [bar("The class system")]
    b.append("<p>Every machine type comes in classes, and a higher class is tougher, better armed and has keener "
             "senses. The in-game name shows the class after the type, for example <i>HUNTER - FNIX Class</i>.</p>")
    rows = []
    for (fac, cls), desc in CLASSES.items():
        vs = [v for v in m["variants"] if v["faction"] == fac and v["cls"] == cls]
        if not vs:
            continue
        g = vs[0]["group"]
        name = "Event" if cls == "Gnome" else cls
        rows.append([gtag(g, fac if g == fac else g),
                     f"<b>{esc(name)}</b>",
                     ", ".join(mlink(site, v, "Gnome Tick" if cls == "Gnome" else
                                     v["type"] if v["page"] == v["type"] else v["page"]) for v in vs),
                     sum(len(v["groups"]) for v in vs), esc(desc)])
    b.append(table(["Faction", "Class", "Types", "Layouts", "About"], rows, sortable=False, cls="mclass"))
    # strength steps
    body = ["<p>Average total component health of a layout, per type and class, with the factor compared with "
            "the first class of that type in brackets." + scaling_sentence(m) + "</p>"]
    for fac, classes in (("Swedish", ["Prototype", "Military", "FNIX", "Apocalypse"]),
                         ("Soviet", ["Scout", "Soldier", "Spetsnaz"])):
        rows = []
        for t in m["types"].values():
            by = {v["cls"]: v for v in t["variants"] if v["faction"] == fac}
            if not all(c in by for c in classes):
                continue
            avg = {c: sum(by[c]["totals"]) / len(by[c]["totals"]) for c in classes}
            row = [site.link("machine", t["name"])]
            for c in classes:
                f = avg[c] / avg[classes[0]]
                row.append((f'{fmt(avg[c], 1)} HP <span class="dim">(×{fmt(f, 2)})</span>' if c != classes[0]
                            else f"{fmt(avg[c], 1)} HP", round(avg[c], 2)))
            rows.append(row)
        body.append(table(["Type"] + classes, rows, num=set(range(1, len(classes) + 1)), cls="compact"))
    b.append(fold("How much tougher is each class?", "".join(body), level=3, id="class-steps"))
    return b


def scaling_sentence(m):
    """' From Prototype to Apocalypse health grows x2.4 to x3.5 (the Seeker is the exception ...)'."""
    f = {}
    for t in m["types"].values():
        by = {v["cls"]: v["totals"] for v in t["variants"]}
        if "Prototype" in by and "Apocalypse" in by:
            f[t["name"]] = (sum(by["Apocalypse"]) / len(by["Apocalypse"])) / (sum(by["Prototype"]) / len(by["Prototype"]))
    up = {k: x for k, x in f.items() if x >= 1}
    down = [k for k, x in f.items() if x < 1]
    if not up:
        return ""
    out = (f" From Prototype to Apocalypse, the Swedish types gain ×{fmt(min(up.values()), 1)} to "
           f"×{fmt(max(up.values()), 1)} in total health")
    if down:
        out += f"; the exception is the {', '.join(down)}, whose Prototype is the toughest of its classes"
    return out + "."


def comparison(site, m):
    b = ["<p>One row per machine type and class. <b>Layouts</b> counts the distinct layouts (the green variants of "
         "Military machines are counted with the layout they copy). <b>Lowest / highest</b> is the total component "
         "health of the weakest and the toughest layout, <b>armour</b> the share of the toughest layout's total "
         "that sits in armour plates, and <b>sight</b> how far it notices you standing in the open while unaware "
         f"(more in {site.link('machine', 'Detection', 'detection & stealth')}). Click a column header to sort.</p>",
         caveat(m),
         '<div class="filterbar" data-for="mcompare"><input placeholder="Filter machines..." aria-label="Filter">'
         '<button class="chip on" data-g="f" data-f="*">All</button>'
         '<button class="chip" data-g="f" data-f="swedish">Swedish</button>'
         '<button class="chip" data-g="f" data-f="soviet">Soviet</button>'
         '<button class="chip" data-g="f" data-f="rival">Rival</button><span class="count"></span></div>']
    rows, attrs = [], []
    for v in m["variants"]:
        g_hi = max(v["groups"], key=lambda g: g["health"]["total_component_health"])
        armour = sum(c["health_each"] * c["count"] for c in g_hi["health"]["components"] if c["type"] == "armour")
        share = armour / g_hi["health"]["total_component_health"]
        s = v["senses"]["unaware"]["sight_m"]["stand"]["max"] if v["senses"] else None
        rows.append([mlink(site, v), esc(class_label(v)),
                     esc(v["in_game"]) if v["in_game"] else DASH, len(v["groups"]),
                     (f"{fmt(min(v['totals']))} HP", min(v["totals"])), (f"{fmt(max(v['totals']))} HP", max(v["totals"])),
                     (pct(share), round(share, 4)),
                     ", ".join(wlink(site, w) for w in v["weapons"]) or '<span class="dim">none</span>', dcell(s)])
        f = "rival" if v["cls"] == "Rival" else v["faction"].lower()
        attrs.append(f'data-f="{f} {v["group"].lower()}"')
    t = table(["Machine", "Class", "In-game name", "Layouts", "Lowest health", "Highest health", "Armour",
               "Weapons", "Sight"], rows, num={3, 4, 5, 6, 8}, cls="mcmp")
    b.append('<div id="mcompare">' + tr_attrs(t, attrs) + "</div>")
    return fold("Every machine compared", "".join(b), right=f"{len(m['variants'])} machines", id="compared")


# ---------------------------------------------------------------- type pages
def build_type(site, m, t):
    vs = t["variants"]
    totals = [x for v in vs for x in v["totals"]]
    boss = t["name"] in BOSSES.values()
    lead = f"<p>{esc(TYPES.get(t['name'], ''))}</p>"
    n_lay = sum(len(v["groups"]) for v in vs)
    if not boss:
        lead += (f"<p>It comes in {len(vs)} classes with {n_lay} distinct layouts between them; total component "
                 f"health ranges from {fmt(min(totals))} to {fmt(max(totals))}.</p>")
    else:
        v = vs[0]
        lead += (f"<p>It is a {site.link('machine', v['type'])} of the {gtag(v['group'], 'Rival')} class, with a "
                 f"total component health of {hp_range(v['totals'])}.</p>")
    b = []
    if not boss:
        b += overview(site, m, t)
    b += type_notes(site, m, t)
    for v in vs:
        b += class_section(site, v, open_=boss)
    if not boss and len(vs) > 1:
        b += weapons_by_class(site, t)
        b += components_by_class(site, t)
    b += blueprint_map(site, m, t)
    kind = f"Machine · {t['faction']}" + (" · Rival" if boss else "")
    crumbs = [("All machines", "~/machines/index.html")]
    site.page(t["path"], t["name"], "\n".join(b), "machines", sub="machines", crumbs=crumbs,
              infobox_html=type_infobox(site, m, t), kind=kind, lead=lead, head_extra=CSS,
              desc=f"Generation Zero {t['name']}: every class and layout with weapons, component health and "
                   f"detection ranges, from the game files.")


def type_notes(site, m, t):
    """'Heads up' callouts for facts in the files that break the usual pattern (computed, so they disappear if a
    game update changes the numbers)."""
    out = []
    vs = t["variants"]
    avg = [sum(v["totals"]) / len(v["totals"]) for v in vs]
    if len(vs) > 1 and all(avg[0] > x for x in avg[1:]):
        out.append(note(f"<p>The {esc(vs[0]['cls'])} {esc(t['name'])} is the toughest of its type, not the weakest: "
                        f"{fmt(avg[0], 1)} total component health against " +
                        ", ".join(f"{fmt(a, 1)} for the {esc(class_label(v))}" for v, a in zip(vs[1:], avg[1:])) +
                        "." + biggest_drop(vs) + "</p>", "warn"))
    # every class of this type (the Rival one too, which has its own page) with the very same senses
    same = [v for v in m["variants"] if v["type"] == vs[0]["type"] and v["senses"]]
    keyed = {repr({k: v["senses"][k] for k in ("unaware", "alerted")}) for v in same}
    if len(same) > 2 and len(keyed) == 1:
        u = same[0]["senses"]["unaware"]
        out.append(note(f"<p>All {len(same)} {esc(vs[0]['type'])} classes in the files (" +
                        ", ".join(mlink(site, v, class_label(v)) for v in same) + ") have exactly the same senses: "
                        f"a higher class does not see or hear you any farther (unaware, "
                        f"{dist(u['sight_m']['stand']['max'])} standing and {dist(u['hearing_m']['run']['max'])} "
                        f"hearing you run). See {site.link('machine', 'Detection', 'detection & stealth')}.</p>",
                        "warn"))
    return out


def biggest_drop(vs):
    """' Its Engine Drives have 120 HP each, against 4.7–7.8 HP in the later classes.' The component whose HP
    falls most from the first class to the best later class."""
    def best(v, name):
        hs = [c["health_each"] for g in v["groups"] for c in g["health"]["components"]
              if c["component"] == name and c["type"] == "component"]
        return max(hs) if hs else None
    names = {c["component"] for g in vs[0]["groups"] for c in g["health"]["components"] if c["type"] == "component"}
    drops = []
    for n in names:
        first, later = best(vs[0], n), [best(v, n) for v in vs[1:]]
        if first and all(later) and first > max(later):
            drops.append((first - max(later), n, first, later))
    if not drops:
        return ""
    _, n, first, later = max(drops)
    return (f" The reason is its {esc(n)}: {fmt(first, 2)} HP each, against {hp_range(later)} HP in the later "
            "classes.")


def type_infobox(site, m, t):
    """Infobox with a class picture switcher (and the 3D viewer button, not working yet) on top."""
    vs = t["variants"]
    totals = [x for v in vs for x in v["totals"]]
    weapons = {w["key"] for v in vs for w in v["weapons"]}
    sights = [v["senses"]["unaware"]["sight_m"]["stand"]["max"] for v in vs if v["senses"]]
    views = []
    for v in vs:
        cap = (f'<span class="swcls">{class_tags(v)} <a href="#{v["anchor"]}">{esc(v["in_game"] or v["machine"])}'
               f'</a></span><span class="swfacts">{len(v["groups"])} layout{"s" if len(v["groups"]) > 1 else ""}'
               f' · {hp_range(v["totals"])} HP' +
               (f' · sees you at {dist(v["senses"]["unaware"]["sight_m"]["stand"]["max"])}' if v["senses"] else "")
               + "</span>")
        views.append((class_label(v), picture(site, v) + cap))
    rows = [("Faction", gtag(t["faction"])),
            ("Classes", ", ".join(f'<a href="#{v["anchor"]}">{esc(class_label(v))}</a>' for v in vs)),
            ("Layouts", str(sum(len(v["groups"]) for v in vs))),
            ("Total health", f"{hp_range(totals)} HP"),
            ("Weapons", f"{len(weapons)} different" if weapons else "none")]
    if sights:
        rows.append(("Sees you standing", f"{dist(min(sights))} to {dist(max(sights))}" if min(sights) != max(sights)
                     else dist(sights[0])))
    bps = m["blueprints"].get(t["name"], [])
    if bps:
        rows.append(("Blueprints", f'<a href="#blueprints">{len(bps)} on the map</a>'))
    dl = "".join(f"<dt>{esc(k)}</dt><dd>{v}</dd>" for k, v in rows if v)
    return (f'<aside class="infobox mbox"><div class="ibh">{esc(t["name"])}</div>'
            f'{switcher(views, cls="mswitch", extra=CUBE)}<dl>{dl}</dl></aside>')


def overview(site, m, t):
    """Classes at a glance: one row per class."""
    b = [bar("Classes at a glance")]
    b.append("<p>Each class in one row; open a class below for its layouts, weapons and weak points. Health is the "
             "total component health of the weakest and toughest layout; sight is how far it notices you standing "
             "and hearing how far it hears you running, both while it is unaware.</p>")
    rows = []
    for v in t["variants"]:
        s = v["senses"]["unaware"] if v["senses"] else None
        rows.append([f'<a href="#{v["anchor"]}">{esc(class_label(v))}</a>',
                     esc(v["in_game"]) if v["in_game"] else '<span class="dim">none</span>', len(v["groups"]),
                     (f"{fmt(min(v['totals']))} HP", min(v["totals"])), (f"{fmt(max(v['totals']))} HP", max(v["totals"])),
                     len(v["weapons"]),
                     dcell(s["sight_m"]["stand"]["max"]) if s else None,
                     dcell(s["hearing_m"]["run"]["max"]) if s else None])
    b.append(table(["Class", "In-game name", "Layouts", "Lowest health", "Highest health", "Weapons",
                    "Sight", "Hearing"], rows, num={2, 3, 4, 5, 6, 7}))
    rival = next(((f, ty) for (f, ty), name in BOSSES.items() if ty == t["name"] and f == t["faction"]), None)
    if rival:
        bv = m["types"][BOSSES[rival]]["variants"][0]
        b.append(f"<p>The Rival-class {esc(t['name'])} is the {site.link('machine', bv['page'])}, with a total "
                 f"component health of {hp_range(bv['totals'])}. It has its own page.</p>")
    b.append(caveat(m))
    return b


def class_section(site, v, open_=False):
    n = len(v["groups"])
    body = [f"<p>{class_tags(v)} {esc(CLASSES.get((v['faction'], v['cls']), ''))}</p>"]
    body.append(kv([("In-game name", esc(v["in_game"]) if v["in_game"] else
                     '<span class="dim">none (the game shows no name for it)</span>'),
                    ("Total component health", f"{hp_range(v['totals'])} HP"),
                    ("Weapons", ", ".join(wlink(site, w) for w in v["weapons"]) or '<span class="dim">none</span>')]))
    greens = [f for g in v["groups"] for f, what in g["files"] if what == "green variant"]
    if greens:
        body.append(note("<p>The files have a <b>green variant</b> of " +
                         ("every layout" if len(greens) == len(v["groups"]) else f"{len(greens)} of these layouts") +
                         ". Each has exactly the same components, health and weapons as the layout it copies, so the "
                         "tables below cover both. The difference is outside these stats (the name suggests a "
                         "different paint scheme).</p>", "info", "Green variants"))
    groups = v["groups"]
    if len(groups) == 1:
        body.append(layout_html(site, v, groups[0]))
    else:
        body.append('<div class="tabset"><div class="tsbtns">' + "".join(
            f"<button>{esc(g['label'])}</button>" for g in groups) + "</div>" + "".join(
            f'<div class="tspane">{layout_html(site, v, g)}</div>' for g in groups) + "</div>")
    body.append(detection_summary(site, v))
    right = f"{n} layout{'s' if n > 1 else ''} · {hp_range(v['totals'])} HP"
    return [fold(class_title(v), "".join(body), open=open_, right=right, id=v["anchor"])]


def layout_html(site, v, g):
    h, L = g["health"], g["loadout"] or {}
    out = [f'<div class="lhead"><span>{esc(g["label"])}</span>'
           f'<span>Total component health: <b>{fmt(h["total_component_health"])} HP</b></span></div>']
    if g["same_as"]:
        out.append(note(f"<p>In the files this layout has exactly the same components, health and weapons as "
                        f"{esc(g['same_as'])} (a separate layout file with identical contents).</p>", "info"))
    out.append(weapons_html(site, v, g))
    seen = set()
    for d in L.get("deployment") or []:
        txt = clean_note(site, d.get("note", ""))
        if (d["colloquial_name"], txt) in seen:
            continue
        seen.add((d["colloquial_name"], txt))
        out.append(note(f"<p><b>{esc(d['colloquial_name'])}</b>: {esc(txt)}</p>", "info", "Deployment"))
    if L.get("note") and clean_note(site, L["note"]):
        out.append(f'<p class="small dim">{esc(clean_note(site, L["note"]))}</p>')
    out.append(components_html(h))
    tips = weak_points(site, v, g)
    if tips:
        out.append('<h4>Weak points</h4><ul class="tips">' + "".join(f"<li>{t}</li>" for t in tips) + "</ul>")
    return "".join(out)


def weapons_html(site, v, g):
    L = g["loadout"] or {}
    ws = L.get("weapons") or []
    if not ws:
        return '<p class="dim">This layout carries no weapons.</p>'
    mws = site.data("stats")["machine_weapons"]
    comps = {norm(c["component"]): c for c in g["health"]["components"] if c["type"] == "component"}
    merged = {}   # the same weapon twice (two autocannons) is one row with a count
    for w in ws:
        k = (w["internal_name"], w.get("ammo_internal_name"))
        merged.setdefault(k, [w, 0])[1] += 1
    rows = []
    for w, n in merged.values():
        key = mw_key(site, w, v["machine"])
        name = site.link("machine-weapon", key, w["colloquial_name"]) if key else esc(w["colloquial_name"])
        if n > 1:
            name += f" <b>×{n}</b>"
        for n_ in dict.fromkeys([clean_note(site, w.get("note")), clean_note(site, mws[key].get("note") if key else None)]):
            if n_:
                name += f'<div class="wnote">{esc(n_)}</div>'
        comp = comps.get(norm(w["colloquial_name"])) or comps.get(norm(w.get("in_game_component_name") or "-"))
        rows.append([name, esc(w.get("in_game_component_name") or "–"), esc(w["kind"]),
                     dmg_text(mws[key].get("damage") if key else None),
                     (f"{fmt(comp['health_each'], 2)} HP", comp["health_each"]) if comp else None])
    return ("<h4>Weapons</h4><p class=\"small dim\">The label the game shows when you tag the part, the damage from "
            "the machine weapon files (before difficulty), and the HP of the part you can shoot off (– for attacks "
            "that are not a separate part).</p>" +
            table(["Weapon", "Part label", "Kind", "Damage", "Part HP"], rows, num={4}, cls="mweap"))


def components_html(h):
    comps = h["components"]
    total = h["total_component_health"]
    rows = []
    for c in comps:
        sub = c["health_each"] * c["count"]
        rows.append([esc(c["component"]), tag("Armour", "base") if c["type"] == "armour" else "Component",
                     c["health_each"], c["count"], round(sub, 2), pct(sub / total, 1) if total else "–"])
    armour = sum(c["health_each"] * c["count"] for c in comps if c["type"] == "armour")
    kinds = f"{len(comps)} kind{'s' if len(comps) > 1 else ''} of part"
    cap = f"{kinds}. Total {fmt(total)} HP = components {fmt(total - armour)} HP + armour {fmt(armour)} HP."
    return "<h4>Component health</h4>" + table(["Component", "Type", "HP each", "Count", "Total HP", "Share"], rows,
                                                num={2, 3, 4, 5}, caption=esc(cap), cls="compact")


def count_text(c):
    return f" ×{c['count']}" if c["count"] > 1 else ""


def weak_points(site, v, g):
    """Tips computed from the component list of one layout."""
    comps = g["health"]["components"]
    total = g["health"]["total_component_health"]
    parts = [c for c in comps if c["type"] == "component"]
    armour = [c for c in comps if c["type"] == "armour"]
    tips = []
    if len(parts) == 1 and not armour:
        return [f"It has a single component, the {esc(parts[0]['component'])} with {fmt(parts[0]['health_each'], 2)} "
                "HP: any hit that deals that much destroys it."]
    if parts:
        low = sorted(parts, key=lambda c: c["health_each"])[:3]
        tips.append("Cheapest components to break: " + ", ".join(
            f"{esc(c['component'])} ({fmt(c['health_each'], 2)} HP{count_text(c)})" for c in low) + ".")
    weapon_names = {norm(w["colloquial_name"]) for w in (g["loadout"] or {}).get("weapons", [])} | \
                   {norm(w.get("in_game_component_name") or "-") for w in (g["loadout"] or {}).get("weapons", [])}
    wcomps = [c for c in parts if norm(c["component"]) in weapon_names]
    if wcomps:
        tips.append("Weapons are components you can shoot off: " + ", ".join(
            f"{esc(c['component'])} {fmt(c['health_each'], 2)} HP{count_text(c)}" for c in wcomps) + ".")
    fuel = [c for c in parts if c["component"] == "Fuel Tank"]
    if fuel:
        tips.append("Fuel tank" + ("s" if sum(c["count"] for c in fuel) > 1 else "") + ": " +
                    ", ".join(f"{fmt(c['health_each'], 2)} HP{count_text(c)}" for c in fuel) +
                    ", a classic weak spot to aim for.")
    covered = sorted({a["component"] for a in armour} & {c["component"] for c in parts})
    for name in covered:
        a = next(x for x in armour if x["component"] == name)
        c = next(x for x in parts if x["component"] == name)
        tips.append(f"The {esc(name)} has an armour plate of {fmt(a['health_each'], 2)} HP over a "
                    f"{fmt(c['health_each'], 2)} HP component.")
    if armour:
        ah = sum(a["health_each"] * a["count"] for a in armour)
        n = sum(a["count"] for a in armour)
        thin = min(a["health_each"] for a in armour)
        tips.append(f"{n} armour plates hold {pct(ah / total, 0)} of the total ({fmt(ah)} HP); the thinnest are "
                    f"{fmt(thin, 2)} HP. Break plates with ammo that has a high armour multiplier, then switch to ammo "
                    "with a high component multiplier for the parts underneath (see "
                    f"{page_link(site, 'weapons/ammo.html', 'choosing ammo', 'choosing')}).")
    return tips


def detection_summary(site, v):
    s = v["senses"]
    if not s:
        return ""
    u, a = s["unaware"], s["alerted"]
    us, ah = u["sight_m"], u["hearing_m"]
    anchor = slug(v["machine"])
    night = u["night_sight_multiplier"]
    txt = (f"Unaware, it notices you at up to <b>{dist(us['stand']['max'])}</b> standing, "
           f"{dist(us['crouch']['max'])} crouched and {dist(us['prone']['max'])} prone "
           f"(running: {dist(us['run']['max'])}). Once alerted, sight grows to {dist(a['sight_m']['stand']['max'])} "
           f"standing. It hears you running at {dist(ah['run']['max'])} and walking at {dist(ah['stand']['max'])}. "
           f"Its vision cone is {deg(u['field_of_view_deg']['stand']['max'])} wide. It starts searching at a "
           f"detection score of {fmt(u['search_at'])}, attacks at {fmt(u['attack_at'])}, and the score drains by "
           f"{fmt(u['drain_per_second'])} per second")
    txt += (f"; at night sight is multiplied by {fmt(night)}." if night != 1 else "; night does not reduce its sight.")
    return (f'<div class="detsum"><h4>Detection</h4><p>{txt} '
            f'<a href="~/machines/detection.html#{anchor}">Full senses table</a>.</p></div>')


def weapons_by_class(site, t):
    vs = t["variants"]
    allw = {}
    for v in vs:
        for w in v["weapons"]:
            allw.setdefault(w["key"], w)
    if not allw:
        return []
    b = ["<p>Which class carries which weapon, and on which layouts (L1 = Layout 1). Weapon names link to their "
         "damage on the machine weapons page.</p>"]
    # Two weapons with one colloquial name (the Firebird's two autocannon rounds, the Prototype and Military Tick
    # bites) are told apart by their machine-weapon key, e.g. 'Autocannon (incendiary rounds)'.
    names = [w["name"] for w in allw.values()]
    rows = []
    for k, w in allw.items():
        if names.count(w["name"]) > 1 and w["key"]:
            w = dict(w, name=w["key"])
        row = [wlink(site, w)]
        for v in vs:
            e = next((x for x in v["weapons"] if x["key"] == k), None)
            row.append(", ".join(esc(l.replace("Layout ", "L")) for l in e["layouts"]) if e else DASH)
        rows.append(row)
    b.append(table(["Weapon"] + [class_label(v) for v in vs], rows, cls="compact"))
    return [fold("Weapons by class", "".join(b), right=f"{len(allw)} weapons")]


def components_by_class(site, t):
    """HP each of every component name across the classes (several values when one name has several sizes)."""
    vs = t["variants"]
    names = []
    vals = {}
    for i, v in enumerate(vs):
        for g in v["groups"]:
            for c in g["health"]["components"]:
                k = (c["component"], c["type"])
                if k not in names:
                    names.append(k)
                vals.setdefault((k, i), set()).add(c["health_each"])
    b = ["<p>Hit points of one component of each kind in every class, over all layouts (a component that comes in "
         "several sizes shows each value). It shows which parts grow fastest from class to class.</p>"]
    rows = []
    for k in names:
        row = [esc(k[0]) + (" " + tag("Armour", "base") if k[1] == "armour" else "")]
        for i in range(len(vs)):
            s = sorted(vals.get((k, i), ()), reverse=True)
            row.append((" / ".join(fmt(x, 2) for x in s) + " HP", s[0]) if s else None)
        rows.append(row)
    b.append(table(["Component"] + [class_label(v) for v in vs], rows, cls="compact",
                   num=set(range(1, len(vs) + 1))))
    return [fold("Components compared", "".join(b), right=f"{len(names)} parts")]


def blueprint_map(site, m, t):
    """The machine's blueprint collectibles: a small map placed last, with the list beside it."""
    bps = m["blueprints"].get(t["name"], [])
    if not bps:
        return []
    regions = sorted({it["r"] for _, it in bps if it.get("r")})
    items = []
    for v, it in bps:
        who = class_label(v) if v else it["n"]
        href = maplink(show=["blueprints"], at=(it["x"], it["z"]), zoom=0.6, focus=it["n"])
        items.append(f'<li><b>{esc(who)}</b> <span class="dim">· {esc(REGION_NAME.get(it.get("r"), it.get("r", "")))}'
                     f'</span> · <a href="{href}">show on the map</a></li>')
    coll = site.link("collectible-type", "blueprints", "blueprints")
    text = ((f"<p>The {esc(t['name'])} blueprint is a collectible ({coll}): there is one in the world.</p>"
             if len(bps) == 1 else
             f"<p>The {esc(t['name'])} {coll} are collectibles: {len(bps)} in the world, one per class.</p>")
            + f'<ul class="bplist">{"".join(items)}</ul>')
    first = bps[0][1]
    pts = [(it["x"], it["z"], class_label(v) if v else "") for v, it in bps[1:]]
    mm = minimap(first["x"], first["z"], class_label(bps[0][0]) if bps[0][0] else "", markers=pts,
                 show=["blueprints"], region=regions, small=True, text=text, zoom=1,
                 focus=first["n"] if len(bps) == 1 else None)
    return [bar("Blueprints", f"{len(bps)} on the map", id="blueprints"), mm]


# ---------------------------------------------------------------- detection page
def ratio_summary(vs, sense, stance):
    """The most common ratio of stance distance to standing distance (unaware max), and the exceptions."""
    counts = {}
    for v in vs:
        d = v["senses"]["unaware"][sense]
        if d["stand"]["max"]:
            r = round(d[stance]["max"] / d["stand"]["max"], 2)
            counts.setdefault(r, []).append(v)
    common = max(counts, key=lambda r: len(counts[r]))
    others = [v for r, l in counts.items() if r != common for v in l]
    return common, others


def alert_ratios(v):
    """Alerted / unaware sight (max) per stance, rounded: {'prone': 10.0, ...}."""
    u, a = v["senses"]["unaware"]["sight_m"], v["senses"]["alerted"]["sight_m"]
    return {st: round(a[st]["max"] / u[st]["max"], 2) for st in STANCES if u[st]["max"]}


def prone_beats_crouch(vs):
    """Machines that see you farther prone than crouched while unaware."""
    return [v for v in vs if v["senses"]["unaware"]["sight_m"]["prone"]["max"] >
            v["senses"]["unaware"]["sight_m"]["crouch"]["max"]]


def prone_warning(vs):
    out = []
    for v in prone_beats_crouch(vs):
        u = v["senses"]["unaware"]
        out.append(f" Careful with the {esc(v['machine'])}: it sees you farther prone "
                   f"({dist(u['sight_m']['prone']['max'])}, {deg(u['field_of_view_deg']['prone']['max'])} cone) "
                   f"than crouched ({dist(u['sight_m']['crouch']['max'])}), so crouch rather than go prone near it.")
    return "".join(out)


def stance_alert_note(vs):
    """' By stance: ...': machines whose alerted factor is not the same in every stance (Firebirds grow more for a
    running target)."""
    groups = {}   # ratios -> machine names, so the four identical Firebirds become one entry
    for v in vs:
        r = alert_ratios(v)
        if len(set(r.values())) > 1:
            groups.setdefault(tuple(r.items()), []).append(v)
    parts = []
    for ratios, ms in groups.items():
        who = "Firebirds (and the Vulture)" if all(x["type"] == "Firebird" for x in ms) else \
            ", ".join(esc(x["machine"]) for x in ms)
        if len(set(r for _, r in ratios)) == 2:   # one stance is the odd one out
            common = max(set(r for _, r in ratios), key=lambda x: sum(1 for _, r in ratios if r == x))
            odd = [(st, r) for st, r in ratios if r != common]
            st, r = odd[0]
            d = dist(ms[0]['senses']['alerted']['sight_m'][st]['max'])
            grow = "does not grow at all" if r == 1 else f"grows only ×{fmt(r)}"
            parts.append(f"the {who}'s {STANCE_NAME[st].lower()} sight {grow} ({d} alerted) instead of "
                         f"×{fmt(common)}")
        else:
            parts.append(f"for {who} the factor depends on your stance, from ×{fmt(ratios[0][1])} "
                         f"{STANCE_NAME[ratios[0][0]].lower()} to ×{fmt(ratios[-1][1])} "
                         f"{STANCE_NAME[ratios[-1][0]].lower()}")
    return (" By stance: " + "; ".join(parts) + ".") if parts else ""


def build_detection(site, m):
    vs = [v for v in m["variants"] if v["senses"]]
    lead = ("<p>Machines notice you with sight and hearing. Each machine class has its own distances for each "
            "stance, a vision cone, and a detection score that decides when it starts searching and when it "
            f"attacks. This page lists the senses of all {len(vs)} machines in the game files and the stealth "
            "tips that follow from them.</p>")
    b = [bar("How detection works")]
    b.append('<ul class="tips">'
             "<li><b>Max distance</b> (in metres) is the farthest a machine starts to notice you at all. Between the "
             "max distance and the <b>full-speed distance</b> the detection score builds slowly; closer than that it "
             "builds at the full rate.</li>"
             "<li>The <b>vision cone</b> works the same way: the first angle is the whole cone, the second the part "
             "of it where you are noticed at the full rate (both in degrees). Hearing ignores the cone.</li>"
             "<li>The <b>detection score</b> rises while the machine sees or hears you and drains (points per "
             "second) while it does not. It starts searching at <i>search at</i> and attacks at <i>attack "
             "at</i>.</li>"
             "<li><b>Unaware</b> is the normal state; <b>alerted</b> is while it searches or fights.</li>"
             "<li>At night (19:00 to 07:00) sight is multiplied by the machine's <b>night multiplier</b>.</li></ul>")
    b += stealth_tips(site, vs)
    b.append(bar("Senses of every machine", f"{len(vs)} machines"))
    b.append("<p>One table per machine, grouped by type. Each cell shows <b>max / full-speed distance</b>; the vision "
             "cone is <b>cone / full-speed cone</b>. <i>Night</i> is the unaware sight distance after the night "
             "multiplier.</p>")
    b.append('<div class="foldall" data-for="senses"></div><div id="senses">')
    for t in m["types"].values():
        tv = [v for v in t["variants"] if v["senses"]]
        if not tv:
            continue
        inner = "".join(senses_table(site, v, vs) for v in tv)
        inner = f'<p class="small">{site.link("machine", t["name"], "The " + t["name"] + " page")} has its ' \
                f"layouts and weapons.</p>" + inner
        b.append(fold(t["name"], inner, level=3, id="senses-" + t["slug"],
                      right=f"{len(tv)} class{'es' if len(tv) > 1 else ''}"))
    b.append("</div>")
    b.append(detection_overview(site, vs))
    site.page("machines/detection.html", "Detection & stealth", "\n".join(b), "machines", lead=lead, head_extra=CSS,
              crumbs=[("All machines", "~/machines/index.html")], kind="Machines · Senses",
              desc="How far every Generation Zero machine sees and hears you per stance, unaware and alerted, "
                   "with vision cones, detection thresholds and stealth tips.")


def stealth_tips(site, vs):
    b = [bar("Stealth tips from the numbers")]
    tips = []
    cr, cr_x = ratio_summary(vs, "sight_m", "crouch")
    pr, pr_x = ratio_summary(vs, "sight_m", "prone")
    rn, _ = ratio_summary(vs, "sight_m", "run")
    exc = sorted({"Firebirds (and the Vulture)" if v["type"] == "Firebird" else v["machine"] for v in cr_x + pr_x})
    tips.append(f"<b>Get low.</b> For almost every machine, crouching cuts the distance at which it can see you to "
                f"{pct(cr)} of the standing distance, and going prone to {pct(pr)}. Running makes it {pct(rn)}." +
                (f" Exceptions: {', '.join(esc(e) for e in exc)} (see their tables)." if exc else "") +
                prone_warning(vs))
    alert = {}
    for v in vs:
        r = round(v["senses"]["alerted"]["sight_m"]["stand"]["max"] / v["senses"]["unaware"]["sight_m"]["stand"]["max"], 1)
        alert.setdefault(r, []).append(v["machine"])
    common = max(alert, key=lambda r: len(alert[r]))
    rest = "; ".join(f"×{fmt(r)} for {', '.join(esc(n) for n in ns)}" for r, ns in alert.items() if r != common)
    ex = vs[0]  # the first machine in the files (Prototype Tank) as the worked example
    ex_u, ex_a = ex["senses"]["unaware"], ex["senses"]["alerted"]
    tips.append(f"<b>Don't be seen twice.</b> Once a machine is alerted its sight reaches {fmt(common)} times as "
                f"far (for example the {esc(ex['machine'])}: {dist(ex_u['sight_m']['stand']['max'])} becomes "
                f"{dist(ex_a['sight_m']['stand']['max'])} standing)." + (f" Exceptions: {rest}." if rest else "") +
                stance_alert_note(vs) + " Break line of sight and let it calm down before you move in the open again.")
    th = {(v["senses"]["unaware"]["search_at"], v["senses"]["unaware"]["attack_at"],
           v["senses"]["unaware"]["drain_per_second"]) for v in vs}
    usual = max(th, key=lambda x: sum(1 for v in vs if (v["senses"]["unaware"]["search_at"],
                                                        v["senses"]["unaware"]["attack_at"],
                                                        v["senses"]["unaware"]["drain_per_second"]) == x))
    s_at, a_at, dr = usual
    tips.append(f"<b>The score drains slowly.</b> Nearly every machine searches at {fmt(s_at)}, attacks at "
                f"{fmt(a_at)} and drains {fmt(dr)} per second, so a machine at the attack threshold needs "
                f"{fmt((a_at - s_at) / dr, 1)} s without seeing or hearing you to drop back below the search "
                f"threshold, and {fmt(a_at / dr, 1)} s for its detection score to drain to 0.")
    nights = {v["senses"]["unaware"]["night_sight_multiplier"] for v in vs}
    n = min(nights - {1.0}) if nights - {1.0} else 1.0
    day = ex_u["sight_m"]["stand"]["max"]
    tips.append(f"<b>Move at night.</b> From 19:00 to 07:00 sight is multiplied by {fmt(n)} for almost every "
                f"machine: the {esc(ex['machine'])} that sees you standing at {dist(day)} by day sees you at "
                f"{dist(day * ex_u['night_sight_multiplier'])}.")
    hear = sorted(vs, key=lambda v: -v["senses"]["unaware"]["hearing_m"]["run"]["max"])[:4]
    tips.append("<b>Sound carries.</b> Hearing does not care about the vision cone. The best ears in the files "
                "(running, unaware): " + ", ".join(
                    f"{mlink(site, v)} {dist(v['senses']['unaware']['hearing_m']['run']['max'])}" for v in hear) +
                ". Going prone means no machine hears you at the full rate (its full-speed distance is 0 m).")
    sight = sorted(vs, key=lambda v: -v["senses"]["unaware"]["sight_m"]["stand"]["max"])[:5]
    tips.append("<b>Know the spotters.</b> Longest unaware sight standing: " + ", ".join(
        f"{mlink(site, v)} {dist(v['senses']['unaware']['sight_m']['stand']['max'])}" for v in sight) +
        "." + seeker_note(vs))
    tips.append("<b>Stay out of the cone.</b> " + cone_tip(vs))
    b.append('<ul class="tips">' + "".join(f"<li>{t}</li>" for t in tips) + "</ul>")
    return b


def cone_tip(vs):
    """The usual ground-machine cone and the Firebirds' narrow unaware / wide alerted cones, from the data."""
    ground = [v for v in vs if v["type"] != "Firebird"]
    fire = [v for v in vs if v["type"] == "Firebird"]
    cones = {}
    for v in ground:
        f = v["senses"]["unaware"]["field_of_view_deg"]["stand"]
        cones.setdefault((f["max"], f["full_speed"]), []).append(v)
    (c, cf), lst = max(cones.items(), key=lambda kv_: len(kv_[1]))
    who = f"All {len(ground)}" if len(lst) == len(ground) else f"{len(lst)} of the {len(ground)}"
    out = (f"{who} ground machines see in a {deg(c)} cone and notice you at the full rate "
           f"only in its central {deg(cf)}.")
    if fire:
        un = [v["senses"]["unaware"]["field_of_view_deg"]["stand"]["max"] for v in fire]
        al = [v["senses"]["alerted"]["field_of_view_deg"]["stand"]["max"] for v in fire]

        def rng(xs):
            return deg(min(xs)) if min(xs) == max(xs) else f"{deg(min(xs))} to {deg(max(xs))}"
        out += (f" Firebirds that have not spotted you look through a {rng(un)} cone, which widens to {rng(al)} "
                "once alerted.")
    return out


def seeker_note(vs):
    """' The Seeker sees farthest ...' when the data says so for every regular Swedish class."""
    for cls in ("Prototype", "Military", "FNIX", "Apocalypse"):
        cv = [v for v in vs if v["faction"] == "Swedish" and v["cls"] == cls]
        best = max(cv, key=lambda v: v["senses"]["unaware"]["sight_m"]["stand"]["max"]) if cv else None
        if not best or best["type"] != "Seeker":
            return ""
    return " Within every regular Swedish class the Seeker is the one that sees farthest."


def detection_overview(site, vs):
    b = ["<p>The headline numbers of every machine (max distances). <b>Stand / Crouch / Prone</b>: how far it sees "
         "you while unaware; <b>Hear run / walk</b>: how far it hears you running or walking upright; "
         "<b>Alerted</b>: its sight of you standing once alerted; <b>Night</b>: unaware standing sight at night; "
         "<b>Cone</b>: vision cone; then the detection thresholds and how fast the score drains. Sort by any "
         "column.</p>",
         '<div class="filterbar" data-for="detcmp"><input placeholder="Filter machines..." aria-label="Filter">'
         '<button class="chip on" data-g="f" data-f="*">All</button>'
         '<button class="chip" data-g="f" data-f="swedish">Swedish</button>'
         '<button class="chip" data-g="f" data-f="soviet">Soviet</button><span class="count"></span></div>']
    rows = []
    for v in vs:
        u, a = v["senses"]["unaware"], v["senses"]["alerted"]
        rows.append([f'<a href="#{slug(v["machine"])}">{esc(v["machine"])}</a>',
                     dcell(u["sight_m"]["stand"]["max"]), dcell(u["sight_m"]["crouch"]["max"]),
                     dcell(u["sight_m"]["prone"]["max"]), dcell(u["hearing_m"]["run"]["max"]),
                     dcell(u["hearing_m"]["stand"]["max"]), dcell(a["sight_m"]["stand"]["max"]),
                     dcell(round(u["sight_m"]["stand"]["max"] * u["night_sight_multiplier"], 2)),
                     (deg(u["field_of_view_deg"]["stand"]["max"]), u["field_of_view_deg"]["stand"]["max"]),
                     u["search_at"], u["attack_at"], (f'{fmt(u["drain_per_second"])} /s', u["drain_per_second"])])
    t = table(["Machine", "Stand", "Crouch", "Prone", "Hear run", "Hear walk",
               "Alerted", "Night", "Cone", "Search at", "Attack at", "Drain"], rows,
              num=set(range(1, 12)), cls="compact detcmp")
    b.append('<div id="detcmp">' + tr_attrs(t, [f'data-f="{v["faction"].lower()}"' for v in vs]) + "</div>")
    return fold("All machines compared", "".join(b), right=f"{len(vs)} machines", id="all-machines-compared")


def senses_table(site, v, all_vs):
    s = v["senses"]
    u, a = s["unaware"], s["alerted"]

    def pair(d, st):
        x = d[st]
        return f"{dist(x['max'])} / {dist(x['full_speed_within'])}"

    def cone(d, st):
        x = d[st]
        return f"{deg(x['max'])} / {deg(x['full_speed'])}"

    rows = []
    for st in STANCES:
        rows.append([STANCE_NAME[st], pair(u["sight_m"], st), pair(u["hearing_m"], st), cone(u["field_of_view_deg"], st),
                     dist(round(u["sight_m"][st]["max"] * u["night_sight_multiplier"], 2)),
                     pair(a["sight_m"], st), pair(a["hearing_m"], st), cone(a["field_of_view_deg"], st)])
    head = (f'<div class="dethead" id="{slug(v["machine"])}"><b>{mlink(site, v)}</b>{class_tags(v)}</div>')
    thr = []
    for state, d in (("unaware", u), ("alerted", a)):
        thr.append(f"{state}: search at {fmt(d['search_at'])}, attack at {fmt(d['attack_at'])}, drain "
                   f"{fmt(d['drain_per_second'])} per second, night ×{fmt(d['night_sight_multiplier'])}")
    if thr[0].split(": ")[1] == thr[1].split(": ")[1]:
        thr = [thr[0].split(": ")[1] + " (both states)"]
    tbl = table(["Stance", "Sight", "Hearing", "Cone", "Night", "Sight", "Hearing", "Cone"], rows,
                sortable=False, cls="compact senses")
    # a second header row that says which columns are unaware and which alerted
    tbl = tbl.replace("<thead><tr>", '<thead><tr class="grp"><th></th><th colspan="4">Unaware</th>'
                                     '<th colspan="3">Alerted</th></tr><tr>', 1)
    quirks = sense_quirks(v, all_vs)
    return (head + tbl + f'<p class="small dim thr">{"; ".join(thr)}.</p>' +
            "".join(f'<p class="small quirk">{q}</p>' for q in quirks))


def sense_quirks(v, all_vs):
    """Things in a senses column that break the usual pattern, pointed out so readers don't think it's a typo here."""
    u, a = v["senses"]["unaware"], v["senses"]["alerted"]
    q = []
    h = u["hearing_m"]
    if h["crouch"]["max"] < h["prone"]["max"]:
        q.append(f"The files give a shorter unaware hearing distance crouched ({dist(h['crouch']['max'])}) than "
                 f"prone ({dist(h['prone']['max'])}); alerted, crouched is {dist(a['hearing_m']['crouch']['max'])}.")
    if u["hearing_m"] != a["hearing_m"] and a["hearing_m"]["run"]["max"] < u["hearing_m"]["run"]["max"]:
        q.append(f"Its hearing is shorter when alerted ({dist(a['hearing_m']['run']['max'])} running) than when "
                 f"unaware ({dist(u['hearing_m']['run']['max'])}).")
    fov = u["field_of_view_deg"]["prone"]
    if fov["max"] >= 360:
        q.append("It sees all around (360°) when you are prone.")
    us, as_ = u["sight_m"], a["sight_m"]
    if us["prone"]["max"] > us["crouch"]["max"]:
        only = prone_beats_crouch(all_vs) == [v]
        q.append(("Unlike every other machine it" if only else "It") +
                 f" sees you farther prone ({dist(us['prone']['max'])}) than crouched ({dist(us['crouch']['max'])})"
                 + (f", and its prone sight does not grow when alerted ({dist(as_['prone']['max'])})"
                    if as_["prone"]["max"] == us["prone"]["max"] else "") + ". Crouch, don't go prone, near it.")
    odd = [STANCE_NAME[s].lower() for s in STANCES
           if u["field_of_view_deg"][s]["full_speed"] > u["field_of_view_deg"][s]["max"]]
    if odd:
        q.append(f"Unaware and {', '.join(odd)}, the files give a full-speed cone wider than the cone itself.")
    if u["search_at"] < 0.5:
        q.append(f"Very low thresholds: it searches at {fmt(u['search_at'])} and attacks at {fmt(u['attack_at'])}, "
                 f"and the score drains only {fmt(u['drain_per_second'])} per second.")
    return q
