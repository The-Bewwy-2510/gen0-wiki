"""Machines tab: the machine overview (factions, classes, comparison table), one page per machine type with every
class and layout, and the detection & stealth page.

Data (build/data):
  stats.json     machine_health     faction -> class -> type -> layout -> components (HP each, count, component or
                                    armour) and total_component_health
                 machine_detection  faction -> class -> type -> unaware / alerted senses per stance
                 machine_weapons    colloquial name -> damage, kind, used_by (machine names like 'Tank (Prototype)');
                                    these names are the keys of the 'machine-weapon' kind (machine_weapons section)
                 _about.reading_the_numbers  the caveats we pass on to the reader
  loadouts.json  faction -> class -> type -> layout -> in-game name, weapons (internal names, in-game component
                 labels, kind, notes) and deployment notes

Kinds registered: 'machine' -- type pages ('Tank', 'Reaper', ... plus internal names like 'dreadnought'), class
anchors ('Tank (Prototype)' -> machines/tank.html#prototype, as spelled in stats.json used_by), 'Machines',
'Detection', and the class names ('Scout class', 'Spetsnaz', ... -> machines/index.html#the-class-system).

Name clash: the Seeker's internal name is 'scout', so site.link('machine', 'Scout') goes to the Seeker page.
For the Soviet Scout class link 'Scout class' (or a class anchor such as 'Firebird (Scout)').
"""
from wiki.site import esc, slug, norm, fmt, pct, table, infobox, bar, note, cards, kv, tag

CSS = '<link rel="stylesheet" href="~/assets/machines.css">'
STANCES = ("prone", "crouch", "stand", "run")
STANCE_NAME = {"prone": "Prone", "crouch": "Crouched", "stand": "Standing", "run": "Running"}

FACTION_COLOR = {"Swedish": "#2f5e7a", "Soviet": "#8b2a20", "Rival": "#9c4a1a"}  # Rival = .tag.rival in machines.css

# The unique Rival-class machines get their own page instead of a class section on their base type's page.
BOSSES = {("Swedish", "Tank"): "Reaper", ("Soviet", "Firebird"): "Vulture"}

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
            "covers the two special Tick classes in the files, the Gnome Tick and the unidentified Class X Tick.",
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
    ("Swedish", "Gnome"): "A special Tick class with its own senses. The Gen0 tools list it as an event machine.",
    ("Swedish", "Class X (unidentified)"): "A Tick class with no in-game name. It is in the files with unusual "
                                           "senses, but we could not tie it to anything in the released game.",
    ("Soviet", "Scout"): "The first and weakest class of the Soviet machines.",
    ("Soviet", "Soldier"): "The second Soviet class.",
    ("Soviet", "Spetsnaz"): "The strongest regular Soviet class.",
    ("Soviet", "Rival"): "A single unique machine: the Vulture, a Firebird.",
}
CLASS_TAG = {"FNIX": ("FNIX", "fnix"), "Apocalypse": ("Apocalypse", "exp"), "Rival": ("Rival", "rival"),
             "Gnome": ("Event", "green"), "Class X (unidentified)": ("Unidentified", "base")}

DASH = '<span class="dim">–</span>'
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
    health, senses = st["machine_health"], st["machine_detection"]
    types = {}       # page name -> {name, faction, path, slug, internal, variants}
    variants = []    # one per (faction, class, type)
    for fac, classes in health.items():
        for cls, cd in classes.items():
            for typ, td in cd["types"].items():
                page = BOSSES[(fac, typ)] if cls == "Rival" else typ
                lt = lo.get(fac, {}).get(cls, {}).get("types", {}).get(typ, {}).get("layouts", {})
                groups = _groups(td["layouts"], lt)
                first = groups[0]
                mach = (first["loadout"] or {}).get("machine", {})
                v = {"faction": fac, "cls": cls, "type": typ, "page": page, "internal_class": cd["internal_name"],
                     "internal_type": td["internal_name"], "machine": first["health"]["machine"],
                     "in_game": mach.get("in_game_name"), "text_key": mach.get("in_game_name_text_key"),
                     "anchor": slug(cls), "groups": groups, "senses": senses.get(fac, {}).get(cls, {}).get(typ)}
                v["totals"] = [g["health"]["total_component_health"] for g in groups]
                v["key"] = f"{typ} ({cls})" if page == typ else f"{typ} (Rival)"
                if v["machine"] not in (v["key"],):
                    v["alias_names"] = [v["machine"]]
                else:
                    v["alias_names"] = []
                v["weapons"] = _class_weapons(site, v)
                variants.append(v)
                t = types.setdefault(page, {"name": page, "faction": fac, "slug": slug(page),
                                            "path": f"machines/{slug(page)}.html", "internal": td["internal_name"],
                                            "variants": []})
                t["variants"].append(v)
    order = list(TYPES)
    types = {k: types[k] for k in sorted(types, key=lambda n: order.index(n) if n in order else 99)}
    m = {"types": types, "variants": variants, "about": st["_about"]["reading_the_numbers"]}
    _CACHE[id(site)] = m
    return m


def mw_key(site, w, machine):
    """The stats.json machine_weapons key for a loadout weapon: matched by internal name, and by the machine name
    in used_by when one internal name has several entries (the Firebird autocannon's two ammo types)."""
    mws = site.data("stats")["machine_weapons"]
    cands = [k for k, d in mws.items() if d["internal_name"] == w["internal_name"]]
    if len(cands) > 1:
        cands = [k for k in cands if machine in mws[k].get("used_by", [])] or cands
    return cands[0] if cands else None


def _class_weapons(site, v):
    """Ordered unique weapons of a class: [(machine-weapon key or None, display name, [layout labels])]."""
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
def code(s):
    return f"<code>{esc(s)}</code>" if s else "–"


def hp_range(totals):
    lo_, hi = min(totals), max(totals)
    return fmt(lo_) if lo_ == hi else f"{fmt(lo_)}–{fmt(hi)}"


def class_title(v):
    if v["cls"] == "Gnome":
        return "Gnome Tick"
    return "Rival class" if v["cls"] == "Rival" else (v["cls"] if "Class X" in v["cls"] else f"{v['cls']} class")


def class_tags(v):
    out = tag(v["faction"], "soviet" if v["faction"] == "Soviet" else "base")
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
        internal = [t["internal"]] if t["name"] not in BOSSES.values() else []
        prefix = [v0["groups"][0]["health"]["internal_name"].split("_")[0]] if internal else []
        aliases = internal + prefix + [t["name"] + "s"]
        if t["name"] in BOSSES.values():
            aliases += [v0["internal_type"] + "_" + v0["internal_class"]]
        site.register("machine", t["name"], t["path"], t["name"], aliases=aliases,
                      desc=f"{t['faction']} machine · {len(t['variants'])} class(es) · total component health "
                           f"{hp_range([x for v in t['variants'] for x in v['totals']])}",
                      keywords=" ".join(aliases) + " machine")
    for v in m["variants"]:
        pfx = v["groups"][0]["health"]["internal_name"].rsplit("_load", 1)[0].rsplit("_base", 1)[0]
        aliases = v["alias_names"] + [f"{v['cls']} {v['type']}", pfx]
        aliases += [f for g in v["groups"] for f, _ in g["files"]]
        if v["in_game"]:
            aliases.append(v["in_game"])
        if v["key"] == v["page"]:
            continue  # never happens: Rival keys are 'Tank (Rival)'
        site.register("machine", v["key"], f"machines/{slug(v['page'])}.html#{v['anchor']}", v["machine"],
                      aliases=aliases, desc=f"{v['in_game'] or v['machine']} · {len(v['groups'])} layout(s) · "
                                            f"total component health {hp_range(v['totals'])}",
                      keywords=f"{v['type']} {v['cls']} {v['faction']} machine")
    register_classes(site)


def register_classes(site):
    """'Military class', 'Spetsnaz', ... -> the class table. Registered last so a bare class name never takes a
    name a machine already has; bare 'Scout' stays the Seeker (see the module docstring)."""
    for fac, cls in CLASSES:
        if (cls == "Rival" and fac == "Soviet") or cls == "Gnome" or "Class X" in cls:
            continue  # one 'Rival class' entry is enough; the special Tick classes have their own anchors
        bare = [cls] if cls not in ("Scout", "Rival") else []
        site.register("machine", f"{cls} class", "machines/index.html#the-class-system", f"{cls} class",
                      aliases=bare + [f"{fac} {cls}"], search=False)


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
    lead = ("<p>Generation Zero has two machine factions: the Swedish machines (Ticks, Seekers, Runners, Hunters, "
            "Harvesters and Tanks) and the Soviet machines (Lynxes, Wolves and Firebirds), plus two unique Rival "
            f"machines, the Reaper and the Vulture. The game files define <b>{len(m['types'])} machine types</b> in "
            f"<b>{len(vs)} type-and-class combinations</b> with <b>{n_layouts} distinct layouts</b>. Every "
            "number on these pages is read from the game's own layout, loadout and senses files.</p>")
    b = [bar("Factions")]
    for fac, desc in (("Swedish", "The machines that took over Sweden, built by the FNIX company. They come in four "
                                  "regular classes, Prototype, Military, FNIX and Apocalypse, plus the Rival Reaper."),
                      ("Soviet", "The Soviet machines arrived later in the story. Their classes have their own names, "
                                 "Scout, Soldier and Spetsnaz, plus the Rival Vulture.")):
        ts = [t for t in m["types"].values() if t["faction"] == fac]
        b.append(f"<h3>{esc(fac)} machines</h3><p>{esc(desc)} Types: " +
                 ", ".join(site.link("machine", t["name"]) for t in ts) + ".</p>")
    b.append(bar("Machine types", f"{len(m['types'])} types"))
    b.append("<p>Pick a machine type for its classes, every layout with its weapons, the health of each "
             "component and how far it can see and hear you.</p>")
    b.append(cards([type_card(site, t) for t in m["types"].values()]))
    b += class_system(site, m)
    b += comparison(site, m)
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
    site.page("machines/index.html", "Machines", "\n".join(b), "machines", lead=lead, head_extra=CSS, wide=False,
              desc="Every Generation Zero machine type and class: factions, classes, layouts, health and weapons.")


def type_card(site, t):
    vs = t["variants"]
    totals = [x for v in vs for x in v["totals"]]
    classes = ", ".join(v["cls"].replace(" (unidentified)", "") for v in vs)
    n = sum(len(v["groups"]) for v in vs)
    sub = (f"{esc(classes)}<br>{n} layout{'s' if n != 1 else ''} · "
           f"{hp_range(totals)} HP<br><code>{esc(t['internal'])}</code>")
    fac = "Rival" if t["name"] in BOSSES.values() else t["faction"]
    return {"href": "~/" + t["path"], "title": t["name"], "sub": sub, "tag": fac, "color": FACTION_COLOR[fac]}


def class_system(site, m):
    """The class table and a type x class table of average layout health with the step from the first class."""
    b = [bar("The class system")]
    b.append("<p>Every machine type comes in classes, and a higher class is tougher, better armed and has keener "
             "senses. The class is part of each machine's internal name (<code>classa</code>, <code>classb</code>, "
             "...), and the in-game name shows it after the type, for example <i>HUNTER - FNIX Class</i>. The "
             "table lists every class in the files.</p>")
    rows = []
    for (fac, cls), desc in CLASSES.items():
        vs = [v for v in m["variants"] if v["faction"] == fac and v["cls"] == cls]
        if not vs:
            continue
        rows.append([tag(fac, "soviet" if fac == "Soviet" else "base"), f"<b>{esc(cls)}</b>",
                     code(vs[0]["internal_class"]), ", ".join(mlink(site, v, v["type"] if v["page"] == v["type"]
                                                                    else v["page"]) for v in vs),
                     sum(len(v["groups"]) for v in vs), esc(desc)])
    b.append(table(["Faction", "Class", "Internal", "Types", "Layouts", "About"], rows, sortable=False))
    # strength steps
    b.append("<h3>How much tougher is each class?</h3>")
    b.append("<p>Average total component health of a layout, per type and class, with the factor compared with "
             "the first class of that type in brackets. It shows how fast machines scale from class to class."
             + scaling_sentence(m) + "</p>")
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
                row.append(f'{fmt(avg[c], 1)} <span class="dim">(×{fmt(f, 2)})</span>' if c != classes[0]
                           else fmt(avg[c], 1))
            rows.append(row)
        b.append(table(["Type"] + classes, rows, num=set(range(1, len(classes) + 1)), cls="compact"))
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
        if down == ["Seeker"]:
            out += " (its two Engine Drives have 120 HP each, against under 10 HP in the later classes)"
    return out + "."


def comparison(site, m):
    b = [bar("Every machine compared", f"{len(m['variants'])} machines")]
    b.append("<p>One row per machine type and class. <b>Layouts</b> counts the distinct layouts (the green "
             "variants of Military machines are counted with the layout they copy). <b>Lowest / highest health</b> "
             "is the total component health of the weakest and the toughest layout, <b>armour (toughest)</b> is the "
             "share of the toughest layout's total that sits in armour plates (other layouts of the same class can "
             "have a different share, see the component tables on the type pages), and <b>weapons</b> lists "
             "everything any layout of that class carries. Click a column header to sort.</p>")
    b.append(caveat(m))
    b.append('<div class="filterbar" data-for="mcompare"><input placeholder="Filter machines..." aria-label="Filter">'
             '<button class="chip on" data-g="f" data-f="*">All</button>'
             '<button class="chip" data-g="f" data-f="swedish">Swedish</button>'
             '<button class="chip" data-g="f" data-f="soviet">Soviet</button>'
             '<button class="chip" data-g="f" data-f="rival">Rival</button><span class="count"></span></div>')
    rows = []
    for v in m["variants"]:
        g_hi = max(v["groups"], key=lambda g: g["health"]["total_component_health"])
        armour = sum(c["health_each"] * c["count"] for c in g_hi["health"]["components"] if c["type"] == "armour")
        s = v["senses"]["unaware"]["sight_m"]["stand"]["max"] if v["senses"] else None
        rows.append((v, [mlink(site, v), esc(v["cls"]), code(v["in_game"]) if not v["in_game"] else esc(v["in_game"]),
                         len(v["groups"]), min(v["totals"]), max(v["totals"]),
                         pct(armour / g_hi["health"]["total_component_health"]),
                         ", ".join(wlink(site, w) for w in v["weapons"]) or '<span class="dim">none</span>', s]))
    html_rows = table(["Machine", "Class", "In-game name", "Layouts", "Lowest health", "Highest health", "Armour (toughest)",
                       "Weapons", "Sight (m)"], [r for _, r in rows], num={3, 4, 5, 6, 8}, cls="mcmp")
    # add the filter tags to each row (table() has no row attributes, so patch the <tr>s in order)
    parts = html_rows.split("<tr>")
    out = [parts[0], "<tr>" + parts[1]]  # header row
    for (v, _), p in zip(rows, parts[2:]):
        f = "rival" if v["cls"] == "Rival" else v["faction"].lower()
        out.append(f'<tr data-f="{f}">' + p)
    b.append('<div id="mcompare">' + "".join(out) + "</div>")
    b.append('<p class="small dim">Sight = how far the machine notices you standing in the open while it is '
             f"unaware; see {site.link('machine', 'Detection', 'detection & stealth')} for every stance.</p>")
    return b


# ---------------------------------------------------------------- type pages
def build_type(site, m, t):
    vs = t["variants"]
    totals = [x for v in vs for x in v["totals"]]
    boss = t["name"] in BOSSES.values()
    lead = f"<p>{esc(TYPES.get(t['name'], ''))}</p>"
    if not boss:
        lead += (f"<p>The game files call it <code>{esc(t['internal'])}</code>. It comes in {len(vs)} "
                 f"classes with {sum(len(v['groups']) for v in vs)} distinct layouts between them; total component "
                 f"health ranges from {fmt(min(totals))} to {fmt(max(totals))}.</p>")
    else:
        v = vs[0]
        lead += (f"<p>Internally it is the <code>{esc(v['internal_type'])}</code> in class "
                 f"<code>{esc(v['internal_class'])}</code>, a {site.link('machine', v['type'])} of the Rival class. "
                 f"Its total component health is {hp_range(v['totals'])}.</p>")
    b = []
    if not boss:
        b += overview(site, t)
    b.append(caveat(m))
    b += type_notes(site, m, t)
    for v in vs:
        b += class_section(site, v)
    rival = next(((f, ty) for (f, ty), name in BOSSES.items() if ty == t["name"] and f == t["faction"]), None)
    if rival:
        bv = m["types"][BOSSES[rival]]["variants"][0]
        b.append(bar("Rival version"))
        b.append(f"<p>The Rival-class {esc(t['name'])} is the {site.link('machine', bv['page'])}, with a total "
                 f"component health of {hp_range(bv['totals'])}. It has its own page.</p>")
    if not boss and len(vs) > 1:
        b += weapons_by_class(site, t)
        b += components_by_class(site, t)
    ib = type_infobox(site, t)
    kind = f"Machine · {t['faction']}" + (" · Rival" if boss else "")
    crumbs = [("All machines", "~/machines/index.html")]
    site.page(t["path"], t["name"], "\n".join(b), "machines", sub="machines", crumbs=crumbs, infobox_html=ib,
              kind=kind, lead=lead, head_extra=CSS,
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
                        ", ".join(f"{fmt(a, 1)} for the {esc(v['cls'])}" for v, a in zip(vs[1:], avg[1:])) +
                        "." + biggest_drop(vs) + "</p>", "warn"))
    # every class of this type (the Rival one too, which has its own page) with the very same senses
    same = [v for v in m["variants"] if v["type"] == vs[0]["type"] and v["senses"]]
    keyed = {repr({k: v["senses"][k] for k in ("unaware", "alerted")}) for v in same}
    if len(same) > 2 and len(keyed) == 1:
        u = same[0]["senses"]["unaware"]
        out.append(note(f"<p>All {len(same)} {esc(vs[0]['type'])} classes in the files (" +
                        ", ".join(mlink(site, v, v["cls"]) for v in same) + ") have exactly the same senses: a "
                        f"higher class does not see or hear you any farther (unaware, {fmt(u['sight_m']['stand']['max'])} "
                        f"m standing and {fmt(u['hearing_m']['run']['max'])} m hearing you run). See "
                        f"{site.link('machine', 'Detection', 'detection & stealth')}.</p>", "warn"))
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


def type_infobox(site, t):
    vs = t["variants"]
    totals = [x for v in vs for x in v["totals"]]
    weapons = {w["key"] for v in vs for w in v["weapons"]}
    sights = [v["senses"]["unaware"]["sight_m"]["stand"]["max"] for v in vs if v["senses"]]
    rows = [("Faction", esc(t["faction"])), ("Internal name", code(vs[0]["internal_type"]))]
    rows.append((None, "Classes"))
    for v in vs:
        rows.append((v["cls"].replace(" (unidentified)", ""), mlink(site, v, f"{len(v['groups'])} layout"
                                                                   f"{'s' if len(v['groups']) > 1 else ''}")))
    rows.append((None, "Numbers"))
    rows.append(("Total health", hp_range(totals)))
    rows.append(("Different weapons", str(len(weapons)) if weapons else "none"))
    if sights:
        rows.append(("Sees you standing", f"{fmt(min(sights))}–{fmt(max(sights))} m" if min(sights) != max(sights)
                     else f"{fmt(sights[0])} m"))
    return infobox(t["name"], rows, subtitle=class_tags(vs[0]) if t["name"] in BOSSES.values() else None)


def overview(site, t):
    """Classes at a glance: one row per class."""
    b = [bar("Classes at a glance")]
    b.append("<p>Each class in one row. Lowest and highest HP are the total component health of the weakest and "
             "toughest layout; sight is how far it notices you standing and hearing how far it hears you running, "
             "both while it is unaware.</p>")
    rows = []
    for v in t["variants"]:
        s = v["senses"]["unaware"] if v["senses"] else None
        rows.append([f'<a href="#{v["anchor"]}">{esc(v["cls"])}</a>',
                     esc(v["in_game"]) if v["in_game"] else '<span class="dim">none</span>', len(v["groups"]),
                     min(v["totals"]), max(v["totals"]), len(v["weapons"]),
                     s["sight_m"]["stand"]["max"] if s else None, s["hearing_m"]["run"]["max"] if s else None])
    b.append(table(["Class", "In-game name", "Layouts", "Lowest HP", "Highest HP", "Weapons",
                    "Sight (m)", "Hearing (m)"], rows, num={2, 3, 4, 5, 6, 7}))
    return b


def class_section(site, v):
    b = [bar(class_title(v), f"{len(v['groups'])} layout{'s' if len(v['groups']) > 1 else ''}", id=v["anchor"])]
    b.append(f"<p>{class_tags(v)} {esc(CLASSES.get((v['faction'], v['cls']), ''))}</p>")
    b.append(kv([("In-game name", esc(v["in_game"]) if v["in_game"] else
                  '<span class="dim">none (this layout has no in-game name text key)</span>'),
                 ("Name in these tables", esc(v["machine"])),
                 ("Internal class", code(v["internal_class"])),
                 ("Name text key", code(v["text_key"]) if v["text_key"] else None),
                 ("Total component health", hp_range(v["totals"])),
                 ("Weapons", ", ".join(wlink(site, w) for w in v["weapons"]) or '<span class="dim">none</span>')]))
    greens = [f for g in v["groups"] for f, what in g["files"] if what == "green variant"]
    if greens:
        b.append(note("<p>The files have a <b>green variant</b> of " +
                      ("every layout" if len(greens) == len(v["groups"]) else f"{len(greens)} of these layouts") +
                      " (" + ", ".join(code(f) for f in greens) + "). Each has exactly the same components, "
                      "health and weapons as the layout it copies, so the tables below cover both. The difference "
                      "is outside these stats (the name suggests a different paint scheme).</p>", "info",
                      "Green variants"))
    bases = [f for g in v["groups"] for f, what in g["files"] if what == "base entity"]
    if bases:
        b.append(note("<p>The files also have a base entity " + ", ".join(code(f) for f in bases) +
                      " with exactly the same components and weapons as the layout below.</p>", "info"))
    groups = v["groups"]
    if len(groups) == 1:
        b.append(layout_html(site, v, groups[0]))
    else:
        b.append('<div class="tabset"><div class="tsbtns">' + "".join(
            f"<button>{esc(g['label'])}</button>" for g in groups) + "</div>" + "".join(
            f'<div class="tspane">{layout_html(site, v, g)}</div>' for g in groups) + "</div>")
    b.append(detection_summary(site, v))
    return b


def layout_html(site, v, g):
    h, L = g["health"], g["loadout"] or {}
    files = ", ".join(code(f) + (f' <span class="dim">({esc(w)})</span>' if w != "layout" else "")
                      for f, w in g["files"])
    out = [f'<div class="lhead"><span>Layout file: {files}</span>'
           f'<span>Total component health: <b>{fmt(h["total_component_health"])}</b></span></div>']
    if g["same_as"]:
        out.append(note(f"<p>In the files this layout has exactly the same components, health and weapons as "
                        f"{esc(g['same_as'])} (a separate layout file with identical contents).</p>", "info"))
    out.append(weapons_html(site, v, g))
    for d in L.get("deployment") or []:
        out.append(note(f"<p><b>{esc(d['colloquial_name'])}</b> ({code(d['internal_name'])}, ammo "
                        f"{code(d.get('ammo_internal_name'))}, slot {code(d.get('slot'))}): {esc(d.get('note', ''))}"
                        "</p>", "info", "Deployment"))
    if L.get("note"):
        out.append(f'<p class="small dim">{esc(L["note"])}</p>')
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
        internal = code(w["internal_name"])
        if w.get("ammo_internal_name"):
            internal += f' · ammo {code(w["ammo_internal_name"])}'
        name += f'<div class="wint">{internal}</div>'
        for n_ in dict.fromkeys([w.get("note"), mws[key].get("note") if key else None]):
            if n_:
                name += f'<div class="wnote">{esc(n_)}</div>'
        comp = comps.get(norm(w["colloquial_name"])) or comps.get(norm(w.get("in_game_component_name") or "-"))
        rows.append([name, esc(w.get("in_game_component_name") or "–"), esc(w["kind"]),
                     dmg_text(mws[key].get("damage") if key else None),
                     comp["health_each"] if comp else None])
    return ("<h4>Weapons</h4><p class=\"small dim\">Weapon and internal names; the label the game shows when you "
            "tag the part; the damage from the machine weapon files; and the HP of the component you can shoot "
            "off (– for attacks that are not a separate part).</p>" +
            table(["Weapon", "Component label", "Kind", "Damage (before difficulty)", "Part HP"], rows, num={4},
                  cls="mweap"))


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
    cap = f"{kinds}. Total {fmt(total)} = components {fmt(total - armour)} + armour {fmt(armour)}."
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
    txt = (f"Unaware, it notices you at up to <b>{fmt(us['stand']['max'])} m</b> standing, "
           f"{fmt(us['crouch']['max'])} m crouched and {fmt(us['prone']['max'])} m prone "
           f"(running: {fmt(us['run']['max'])} m). Once alerted, sight grows to {fmt(a['sight_m']['stand']['max'])} m "
           f"standing. It hears you running at {fmt(ah['run']['max'])} m and walking at {fmt(ah['stand']['max'])} m. "
           f"It starts searching at a detection score of {fmt(u['search_at'])}, attacks at {fmt(u['attack_at'])}, "
           f"and the score drains by {fmt(u['drain_per_second'])} per second")
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
    b = [bar("Weapons by class")]
    b.append("<p>Which class carries which weapon, and on which layouts (L1 = Layout 1). Weapon names link to "
             "their damage on the machine weapons page.</p>")
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
    b.append(table(["Weapon"] + [v["cls"].replace(" (unidentified)", "") for v in vs], rows, cls="compact"))
    return b


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
    b = [bar("Components compared")]
    b.append("<p>Hit points of one component of each kind in every class, over all layouts (a component that "
             "comes in several sizes shows each value). It shows which parts grow fastest from class to class.</p>")
    rows = []
    for k in names:
        row = [esc(k[0]) + (" " + tag("Armour", "base") if k[1] == "armour" else "")]
        for i in range(len(vs)):
            s = sorted(vals.get((k, i), ()), reverse=True)
            row.append(" / ".join(fmt(x, 2) for x in s) if s else None)
        rows.append(row)
    b.append(table(["Component"] + [v["cls"].replace(" (unidentified)", "") for v in vs], rows, cls="compact",
                   num=set(range(1, len(vs) + 1))))
    return b


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
    """Machines that see you farther prone than crouched while unaware (only the Class X Tick in the files)."""
    return [v for v in vs if v["senses"]["unaware"]["sight_m"]["prone"]["max"] >
            v["senses"]["unaware"]["sight_m"]["crouch"]["max"]]


def prone_warning(vs):
    out = []
    for v in prone_beats_crouch(vs):
        u = v["senses"]["unaware"]
        out.append(f" Careful with the {esc(v['machine'])}: it sees you farther prone "
                   f"({fmt(u['sight_m']['prone']['max'])} m, {fmt(u['field_of_view_deg']['prone']['max'])}° cone) "
                   f"than crouched ({fmt(u['sight_m']['crouch']['max'])} m), so crouch rather than go prone near it.")
    return "".join(out)


def stance_alert_note(vs):
    """' The factor also depends on your stance for ...': machines whose alerted factor is not the same in every
    stance (Firebirds grow more for a running target, the Class X Tick's prone sight doesn't grow at all)."""
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
            dist = fmt(ms[0]['senses']['alerted']['sight_m'][st]['max'])
            grow = "does not grow at all" if r == 1 else f"grows only ×{fmt(r)}"
            parts.append(f"the {who}'s {STANCE_NAME[st].lower()} sight {grow} ({dist} m alerted) instead of "
                         f"×{fmt(common)}")
        else:
            parts.append(f"for {who} the factor depends on your stance, from ×{fmt(ratios[0][1])} "
                         f"{STANCE_NAME[ratios[0][0]].lower()} to ×{fmt(ratios[-1][1])} "
                         f"{STANCE_NAME[ratios[-1][0]].lower()}")
    return (" By stance: " + "; ".join(parts) + ".") if parts else ""


def build_detection(site, m):
    vs = [v for v in m["variants"] if v["senses"]]
    about = m["about"]["detection"]
    lead = ("<p>Machines notice you with sight and hearing. Each machine class has its own distances for each "
            "stance, a vision cone, and a detection score that decides when it starts searching and when it "
            f"attacks. This page lists the senses of all {len(vs)} machines in the game files and the stealth "
            "tips that follow from them.</p>")
    b = [bar("How detection works")]
    b.append(note(f"<p>{esc(about)}</p>", "data"))
    b.append("<ul>"
             "<li><b>Max</b> is the farthest distance at which a machine starts to notice you at all. Between "
             "<b>max</b> and <b>full speed within</b> the detection score builds slowly; inside the full-speed "
             "distance it builds at the full rate.</li>"
             "<li>The <b>vision cone</b> works the same way: the first angle is the full cone, the second the part "
             "of it where you are noticed at the full rate (both in degrees).</li>"
             "<li>The <b>detection score</b> rises while the machine sees or hears you and drains while it does "
             "not. It starts searching at <i>search at</i> and attacks at <i>attack at</i>.</li>"
             "<li><b>Unaware</b> is the normal state; <b>alerted</b> is while it searches or fights.</li></ul>")
    b += stealth_tips(site, vs)
    b += detection_overview(site, vs)
    b.append(bar("Senses of every machine"))
    b.append("<p>One table per machine. Each cell shows <b>max / full speed within</b> in metres; the vision cone "
             "is <b>cone / full-speed cone</b> in degrees. <i>Night</i> is the unaware sight distance after the "
             "night multiplier (19:00 to 07:00).</p>")
    for t in m["types"].values():
        tv = [v for v in t["variants"] if v["senses"]]
        if not tv:
            continue
        b.append(f'<h3 class="dettype">{site.link("machine", t["name"])}</h3>')
        for v in tv:
            b.append(senses_table(site, v, vs))
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
                f"{pct(cr)} of the standing distance, and going prone to {pct(pr)}. Running makes it {pct(rn)}. "
                f"Exceptions: {', '.join(esc(e) for e in exc)} (see their tables)." + prone_warning(vs))
    alert = {}
    for v in vs:
        r = round(v["senses"]["alerted"]["sight_m"]["stand"]["max"] / v["senses"]["unaware"]["sight_m"]["stand"]["max"], 1)
        alert.setdefault(r, []).append(v["machine"])
    common = max(alert, key=lambda r: len(alert[r]))
    rest = "; ".join(f"×{fmt(r)} for {', '.join(esc(n) for n in ns)}" for r, ns in alert.items() if r != common)
    ex = vs[0]  # the first machine in the files (Prototype Tank) as the worked example
    ex_u, ex_a = ex["senses"]["unaware"], ex["senses"]["alerted"]
    tips.append(f"<b>Don't be seen twice.</b> Once a machine is alerted its sight reaches {fmt(common)} times as "
                f"far (for example the {esc(ex['machine'])}: {fmt(ex_u['sight_m']['stand']['max'])} m becomes "
                f"{fmt(ex_a['sight_m']['stand']['max'])} m standing). Exceptions: {rest}." + stance_alert_note(vs) +
                " Break line of sight and let it calm down before you move in the open again.")
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
                f"machine: the {esc(ex['machine'])} that sees you standing at {fmt(day)} m by day sees you at "
                f"{fmt(day * ex_u['night_sight_multiplier'])} m.")
    hear = sorted(vs, key=lambda v: -v["senses"]["unaware"]["hearing_m"]["run"]["max"])[:4]
    tips.append("<b>Sound carries.</b> Hearing does not care about the vision cone. The best ears in the files "
                "(running, unaware): " + ", ".join(
                    f"{mlink(site, v)} {fmt(v['senses']['unaware']['hearing_m']['run']['max'])} m" for v in hear) +
                ". Going prone means no machine hears you at the full rate (its full-speed distance is 0 m).")
    sight = sorted(vs, key=lambda v: -v["senses"]["unaware"]["sight_m"]["stand"]["max"])[:5]
    tips.append("<b>Know the spotters.</b> Longest unaware sight standing: " + ", ".join(
        f"{mlink(site, v)} {fmt(v['senses']['unaware']['sight_m']['stand']['max'])} m" for v in sight) +
        "." + seeker_note(vs))
    tips.append("<b>Stay out of the cone.</b> Nearly all ground machines see in a 90° cone and notice you at the full rate "
                "only in its central 45°. Firebirds that have not spotted you look through a narrow 10° to 25° cone, "
                "which widens to 60° to 180° once alerted.")
    b.append('<ul class="tips">' + "".join(f"<li>{t}</li>" for t in tips) + "</ul>")
    return b


def seeker_note(vs):
    """' The Seeker sees farthest ...' when the data says so for every regular Swedish class."""
    for cls in ("Prototype", "Military", "FNIX", "Apocalypse"):
        cv = [v for v in vs if v["faction"] == "Swedish" and v["cls"] == cls]
        best = max(cv, key=lambda v: v["senses"]["unaware"]["sight_m"]["stand"]["max"]) if cv else None
        if not best or best["type"] != "Seeker":
            return ""
    return " Within every regular Swedish class the Seeker is the one that sees farthest."


def detection_overview(site, vs):
    b = [bar("All machines compared", f"{len(vs)} machines")]
    b.append("<p>The headline numbers of every machine, as max distances in metres. <b>Stand / Crouch / "
             "Prone</b>: how far it sees you while unaware; <b>Hear run / walk</b>: how far it hears you running "
             "or walking upright; <b>Alerted</b>: its sight of you standing once alerted; <b>Night</b>: unaware "
             "standing sight at night; <b>Cone</b>: vision cone; then the detection thresholds and the drain per "
             "second. Sort by any column.</p>")
    b.append('<div class="filterbar" data-for="detcmp"><input placeholder="Filter machines..." aria-label="Filter">'
             '<button class="chip on" data-g="f" data-f="*">All</button>'
             '<button class="chip" data-g="f" data-f="swedish">Swedish</button>'
             '<button class="chip" data-g="f" data-f="soviet">Soviet</button><span class="count"></span></div>')
    rows = []
    for v in vs:
        u, a = v["senses"]["unaware"], v["senses"]["alerted"]
        rows.append([f'<a href="#{slug(v["machine"])}">{esc(v["machine"])}</a>',
                     u["sight_m"]["stand"]["max"], u["sight_m"]["crouch"]["max"], u["sight_m"]["prone"]["max"],
                     u["hearing_m"]["run"]["max"], u["hearing_m"]["stand"]["max"], a["sight_m"]["stand"]["max"],
                     round(u["sight_m"]["stand"]["max"] * u["night_sight_multiplier"], 2),
                     f'{fmt(u["field_of_view_deg"]["stand"]["max"])}°', u["search_at"], u["attack_at"],
                     u["drain_per_second"]])
    t = table(["Machine", "Stand", "Crouch", "Prone", "Hear run", "Hear walk",
               "Alerted", "Night", "Cone", "Search", "Attack", "Drain/s"], rows,
              num=set(range(1, 12)), cls="compact detcmp")
    parts = t.split("<tr>")
    out = [parts[0], "<tr>" + parts[1]]
    for v, p in zip(vs, parts[2:]):
        out.append(f'<tr data-f="{v["faction"].lower()}">' + p)
    b.append('<div id="detcmp">' + "".join(out) + "</div>")
    return b


def senses_table(site, v, all_vs):
    s = v["senses"]
    u, a = s["unaware"], s["alerted"]

    def pair(d, st, k2="full_speed_within", unit=""):
        x = d[st]
        return f"{fmt(x['max'])}{unit} / {fmt(x[k2])}{unit}"

    rows = []
    for st in STANCES:
        rows.append([STANCE_NAME[st], pair(u["sight_m"], st), pair(u["hearing_m"], st),
                     pair(u["field_of_view_deg"], st, "full_speed", "°"),
                     fmt(round(u["sight_m"][st]["max"] * u["night_sight_multiplier"], 2)),
                     pair(a["sight_m"], st), pair(a["hearing_m"], st),
                     pair(a["field_of_view_deg"], st, "full_speed", "°")])
    head = (f'<div class="dethead" id="{slug(v["machine"])}"><b>{mlink(site, v)}</b>'
            f'<span class="dim">{code(s.get("senses_column"))}</span></div>')
    thr = []
    for state, d in (("unaware", u), ("alerted", a)):
        thr.append(f"{state}: search at {fmt(d['search_at'])}, attack at {fmt(d['attack_at'])}, drain "
                   f"{fmt(d['drain_per_second'])}/s, night ×{fmt(d['night_sight_multiplier'])}")
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
        q.append(f"The files give a shorter unaware hearing distance crouched ({fmt(h['crouch']['max'])} m) than "
                 f"prone ({fmt(h['prone']['max'])} m); alerted, crouched is {fmt(a['hearing_m']['crouch']['max'])} m.")
    if u["hearing_m"] != a["hearing_m"] and a["hearing_m"]["run"]["max"] < u["hearing_m"]["run"]["max"]:
        q.append(f"Its hearing is shorter when alerted ({fmt(a['hearing_m']['run']['max'])} m running) than when "
                 f"unaware ({fmt(u['hearing_m']['run']['max'])} m).")
    fov = u["field_of_view_deg"]["prone"]
    if fov["max"] >= 360:
        q.append("It sees all around (360°) when you are prone.")
    us, as_ = u["sight_m"], a["sight_m"]
    if us["prone"]["max"] > us["crouch"]["max"]:
        only = prone_beats_crouch(all_vs) == [v]
        q.append(("Unlike every other machine it" if only else "It") +
                 f" sees you farther prone ({fmt(us['prone']['max'])} m) than crouched ({fmt(us['crouch']['max'])} m)"
                 + (f", and its prone sight does not grow when alerted ({fmt(as_['prone']['max'])} m)"
                    if as_["prone"]["max"] == us["prone"]["max"] else "") + ". Crouch, don't go prone, near it.")
    odd = [STANCE_NAME[s].lower() for s in STANCES
           if u["field_of_view_deg"][s]["full_speed"] > u["field_of_view_deg"][s]["max"]]
    if odd:
        q.append(f"Unaware and {', '.join(odd)}, the files give a full-speed cone wider than the cone itself.")
    if u["search_at"] < 0.5:
        q.append(f"Very low thresholds: it searches at {fmt(u['search_at'])} and attacks at {fmt(u['attack_at'])}, "
                 f"and the score drains only {fmt(u['drain_per_second'])} per second.")
    return q
