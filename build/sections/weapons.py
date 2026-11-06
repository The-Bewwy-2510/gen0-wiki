"""Weapons tab: the weapon list (with a comparison table: one closed fold per category), one page per weapon, experimental
weapons, weapon skins.

Layout v2: a weapon page has the infobox on the right, then side panels with the attachments that fit and the item
IDs per quality (the one place the wiki prints item IDs). Internal names and hashes are search aliases only.

Data (build/data):
  stats.json      player_weapons: category -> weapon -> ammo damage, multipliers, quality multipliers, experimental
                  ammo overrides (the main source; its weapon names are the keys of the 'weapon' kind)
  IDs.json        Weapons (item id per quality, ToolID, nickname), Attachments (WPNCompat = ToolIDs that fit),
                  Skins (per weapon), Augments (Primary / Support groups)
  icons.json      item id -> icon path
  augments.json   which augment fits which weapon: fits = [index into augments.json weapons, quality bit mask]
  vanity.json     weapon skins (group 'skins', s = weapon internal name, p = content pack hash, l = lock / DLC flag)
  stock.json      ammo and throwables (raw internal name -> display name, calibre 'sub', item hash, icon)
  loot.json       placed loot: weapon spots carry the weapon name and quality
  map_locations   for the nearest named location of each placed weapon
"""
import math
import os
import re

from wiki.site import (esc, slug, norm, fmt, table, infobox, bar, fold, panel, maplink, note, cards, kv, minimap,
                       qbadge, tag, REGIONS, QUALITY)

CSS = '<link rel="stylesheet" href="~/assets/weapons.css?v=3">'
JS = '<script src="~/assets/weapons.js?v=1" defer></script>'   # weapons/index.html: comparison table folds
EXP_PAGE = "weapons/experimental.html"
REGION_NAME = dict(REGIONS)

# Prose name of one weapon of a category ("a handgun"), and a card colour per category.
CAT_INFO = {
    "Handguns": ("handgun", "#3b5f78"),
    "Submachine guns": ("submachine gun", "#4a5b3a"),
    "Assault rifles": ("assault rifle", "#5d4a2e"),
    "Machine guns": ("machine gun", "#6b3b2e"),
    "Hunting rifles": ("hunting rifle", "#3e5a4f"),
    "Sniper rifles": ("sniper rifle", "#4b3f66"),
    "Shotguns": ("shotgun", "#6a4a24"),
    "Launchers": ("launcher", "#7a2a26"),
    "Bows and flamethrowers": ("special weapon", "#5f4258"),
    "Melee": ("melee weapon", "#47545a"),
    "Throwables": ("throwable", "#33393f"),
}
CAT_BLURB = {
    "Handguns": "Sidearms. The two .44 guns (.44 Magnus and Iron Condor) hit hardest at 56 per bullet; only the "
                "Möller PP, Klaucke 17 and .44 Magnus take a handgun silencer.",
    "Submachine guns": "Fast-firing pistol-calibre guns for close range.",
    "Assault rifles": "All-round automatic rifles in 5.56mm, 7.62mm and 9x39mm.",
    "Machine guns": "Big magazines of 5.56mm or 7.62mm for sustained fire.",
    "Hunting rifles": "Long-range hunting rifles with 100-damage rounds (or 7.62mm for the Vintovka).",
    "Sniper rifles": "Long-range rifles. The Kotenok and S21 fire 7.62mm but have the highest quality multipliers in the game.",
    "Shotguns": "12 gauge: slugs for one heavy hit, birdshot and buckshot for many pellets at short range.",
    "Launchers": "Explosive rounds whose damage is a blast, not a bullet.",
    "Bows and flamethrowers": "The Resistance bow (plain, flare and explosive arrows whose blast grows with draw) and the flamethrower.",
    "Melee": "Bat, pitchfork and sledgehammer. The files keep only their quality multipliers, not the hit damage.",
    "Throwables": "Grenades, Molotov cocktails and snowballs: a blast (and fire) where they land.",
}
# IDs.json spells a few weapons so differently that a containment match would miss them
IDS_NAME = {"Volkov Pistol": "Volkov Handgun"}
# The Gen0 Editor's augment slot rule (inv_editor.aug_groups_for, from the in-game text): 2-3 crowns take a Primary
# augment, 4-5 crowns a Primary and a Support augment, 1 crown and Experimental take none.
AUG_SLOTS = {1: (), 2: ("Primary",), 3: ("Primary",), 4: ("Primary", "Support"), 5: ("Primary", "Support"), 6: ()}
QNAME = {q: n for q, (n, _) in QUALITY.items()}
# vanity.json 'l' flag of a skin (same labels as the character section)
SKIN_STATUS = {"U": ("Starts unlocked", "green"), "L": ("Starts locked", ""), "UD": ("DLC", "dlc"),
               "LD": ("DLC, earned", "dlc")}

_CACHE = {}


# ---------------------------------------------------------------------------------------------------------------
# data model: one dict per weapon with everything the pages need (built once per Site)
# ---------------------------------------------------------------------------------------------------------------
def model(site):
    if id(site) in _CACHE:
        return _CACHE[id(site)]
    stats = site.data("stats")["player_weapons"]
    ids = site.data("IDs")
    icons = site.data("icons")
    stock = {s["raw"]: s for s in site.data("stock")["stock"]}
    aug = site.data("augments")
    ids_flat = [(c, n, e) for c, ws in ids["Weapons"].items() for n, e in ws.items()]
    weapons = []
    for cat, ws in stats.items():
        for name, d in ws.items():
            w = {"name": name, "cat": cat, "d": d, "slug": slug(name), "internal": d.get("internal_name", ""),
                 "pack": d.get("pack", ""), "exp_name": d.get("experimental_name")}
            w["path"] = f"weapons/{w['slug']}.html"
            w["quals"] = [int(q[1:]) for q in d.get("qualities") or []]
            w["mult"] = {int(q[1:]): m for q, m in (d.get("damage_multiplier_by_quality") or {}).items()}
            ide = match_ids(name, ids_flat)
            w["ids_cat"], w["ids_name"], w["ids"] = ide if ide else (None, None, None)
            w["tool_id"] = w["ids"]["ToolID"] if w["ids"] else None
            w["nick"] = w["ids"]["Nickname"] if w["ids"] else None
            w["item_ids"] = {q: w["ids"][str(q)] for q in range(1, 7)
                             if w["ids"] and w["ids"].get(str(q)) not in (None, "N/A")}
            w["icon"], w["exp_icon"], w["q_icons"] = weapon_icons(site, w, icons, stock)
            w["calibres"] = calibres(d, stock)
            w["std"] = standard_ammo(d)
            w["aug_index"] = aug["weapons"].index(w["ids_name"]) if w["ids_name"] in aug["weapons"] else None
            weapons.append(w)
    m = {"weapons": weapons, "by_name": {norm(w["name"]): w for w in weapons}, "stock": stock,
         "by_internal": {w["internal"]: w for w in weapons}}
    m["ammo_by_name"] = {}
    for w in weapons:                       # the normal entry of every ammo, for comparing experimental overrides
        for a in w["d"].get("ammo") or []:
            m["ammo_by_name"].setdefault(ammo_name(m, a), a)
    m["skins"] = collect_skins(site, m)
    m["loot"] = collect_loot(site, m)
    _CACHE[id(site)] = m
    return m


def match_ids(name, ids_flat):
    """The IDs.json entry (category, name, entry) for a stats.json weapon name."""
    t = norm(IDS_NAME.get(name, name))
    hit = [x for x in ids_flat if norm(x[1]) == t] or [x for x in ids_flat if norm(x[1]) in t or t in norm(x[1])]
    return hit[0] if len(hit) == 1 else None


def weapon_icons(site, w, icons, stock):
    """(main icon, experimental icon, {quality: icon}) as paths under docs/ ('img/...')."""
    q_icons = {}
    for q, h in w["item_ids"].items():
        p = icons.get(h)
        if p and site.has_file("img/" + p):
            q_icons[q] = "img/" + p
    main = q_icons.get(5) or q_icons.get(1) or next(iter(q_icons.values()), None)
    if not main and w["internal"] in stock:   # throwables are stock items
        p = stock[w["internal"]]["icon"].replace("assets/", "img/", 1)
        main = p if site.has_file(p) else None
    return main, q_icons.get(6), q_icons


def calibres(d, stock):
    """Calibre names (stock.json 'sub') of the ammo a weapon fires, in order."""
    out = []
    for a in d.get("ammo") or []:
        sub = stock.get(a["internal_name"], {}).get("sub")
        if sub and sub not in out:
            out.append(sub)
    return out


def standard_ammo(d):
    """The ammo used for the comparison table: FMJ, else the plain arrow, else the high-explosive round, else the
    first non-experimental ammo."""
    ammo = [a for a in d.get("ammo") or [] if not a.get("experimental_only")]
    for test in (lambda a: "_fmj_" in a["internal_name"], lambda a: "arrow_plain" in a["internal_name"],
                 lambda a: "explosive" in a["internal_name"], lambda a: True):
        for a in ammo:
            if test(a):
                return a
    return None


def collect_skins(site, m):
    """Weapon skins from vanity.json, joined with IDs.json (nickname, item id) by internal name."""
    van = site.data("vanity")
    ids_by_raw = {}
    for c, ws in site.data("IDs")["Skins"].items():
        for wname, ss in ws.items():
            for sname, e in ss.items():
                ids_by_raw[e["EquipmentName"]] = (wname, e)
    subs = {s["key"]: s["name"] for g in van["groups"] if g["key"] == "skins" for s in g["subs"]}
    out = []
    for it in van["items"]:
        if it.get("g") != "skins":
            continue
        w = m["by_internal"].get(it["s"])
        ide = ids_by_raw.get(it["r"], (None, {}))[1]
        out.append({"name": it["n"], "raw": it["r"], "h": it["h"], "weapon": w, "sub_name": subs.get(it["s"]),
                    "pack": it["p"], "dlc": it["l"] in ("UD", "LD"), "l": it["l"], "img": "img/skins/" + it["i"],
                    "nick": ide.get("Nickname"),
                    "anchor": slug(f'{w["name"] if w else subs.get(it["s"], "")} {it["n"]}')})
    out.sort(key=lambda s: (s["weapon"]["name"] if s["weapon"] else "", s["name"]))
    return out


def collect_loot(site, m):
    """Placed weapons (and throwables) from loot.json: weapon -> list of spots {q, x, z, region}."""
    lo = site.data("loot")
    subs, names, regions = lo["subs"], lo["names"], lo["regions"]
    throw = {w["internal"]: w for w in m["weapons"] if w["cat"] == "Throwables"}
    out = {}
    for sub_i, x, z, name_i, reg_i, _h in lo["items"]:
        sub = subs[sub_i]
        w, q = None, sub.get("q")
        if sub["main"] == "loot_weapons":
            mm = re.match(r"^(.*) \((\w+)\)$", names[name_i])
            w = m["by_name"].get(norm(mm.group(1) if mm else names[name_i]))
        elif sub.get("item") in throw:
            w = throw[sub["item"]]
        if w:
            reg = regions[reg_i] if isinstance(reg_i, int) and reg_i < len(regions) else None
            # n = the marker name the map shows ('Möller PP (Worn)'), sub = the map's show key for that category
            out.setdefault(w["name"], []).append({"q": q, "x": x, "z": z, "region": reg, "n": names[name_i],
                                                  "sub": sub["key"]})
    return out


# ---------------------------------------------------------------------------------------------------------------
# small formatting helpers
# ---------------------------------------------------------------------------------------------------------------
def n1(x):
    """Damage with at most one decimal (28 x 0.62 = 17.36 -> '17.4')."""
    return fmt(round(x, 1), 1) if isinstance(x, (int, float)) else "–"


def mult_cell(x):
    return f"×{fmt(x)}" if x is not None else "–"


def pack_label(pack):
    """'US Weapons Pack (DLC)' -> ('US Weapons Pack', True); 'Base game (melee update)' -> ('Base game ...', False)."""
    if pack.endswith("(DLC)"):
        return pack[:-5].strip(), True
    return pack or "Base game", False


def pack_tag(site, pack):
    """DLC tag (linked to the DLC page when the home section registered it) or a base game tag."""
    label, dlc = pack_label(pack)
    if not dlc:
        return tag(label, "base")
    url = site.url("dlc", label)
    t = tag(label, "dlc")
    return f'<a href="{esc(url)}">{t}</a>' if url else t


def img(site, path, alt="", cls="wicon"):
    return site.img(path, alt, cls=cls) if path else ""


def wlink(site, w, icon=True):
    """Link to one of our weapon pages with its icon."""
    ic = img(site, w["icon"], cls="wicon") if icon else ""
    return f'<a href="~/{w["path"]}" class="wl">{ic}<span>{esc(w["name"])}</span></a>'


# stock.json 'sub' values that are a bucket of unrelated items rather than one calibre: name the rounds instead
GENERIC_SUBS = ("Launcher rounds", "Other ammo")


def own_ammo(w):
    """The non-experimental ammo entries of a weapon (what any copy of it can load)."""
    return [a for a in w["d"].get("ammo") or [] if not a.get("experimental_only")]


def own_ammo_raws(w):
    return {a["internal_name"] for a in own_ammo(w)}


def calibre_links(site, w, m=None):
    """Calibre links; for a catch-all sub ('Launcher rounds', 'Other ammo') the actual rounds instead (needs m)."""
    out = []
    for c in w["calibres"]:
        if c in GENERIC_SUBS and m:
            out += [site.link("ammo", ammo_name(m, a) or a["name"]) for a in own_ammo(w)
                    if m["stock"].get(a["internal_name"], {}).get("sub") == c]
        else:
            out.append(site.link("caliber", c))
    return ", ".join(out) or "–"


def qrange(w, exp_href=None):
    """'Q1–Q5' as badges, plus an experimental badge (linked to exp_href, with the experimental name as its title)."""
    qs = [q for q in w["quals"] if q != 6]
    if not qs:
        return "–"
    s = qbadge(qs[0], True) + ("–" + qbadge(qs[-1], True) if len(qs) > 1 else "")
    if 6 in w["quals"]:
        b = qbadge(6, True)
        if exp_href:
            b = f'<a href="{esc(exp_href)}" title="{esc(w["exp_name"] or "")}">{b}</a>'
        s += " " + b
    return s


def pack_short(site, pack):
    """Pack as small text for a table cell: 'Base game', or the DLC name linked to its DLC entry."""
    label, dlc = pack_label(pack)
    if not dlc:
        return f'<span class="small dim">{esc(label)}</span>'
    url = site.url("dlc", label)
    t = esc(label)
    return f'<span class="small"><a href="{esc(url)}">{t}</a></span>' if url else f'<span class="small">{t}</span>'



def ammo_name(m, a):
    """The stock.json name an ammo entry belongs to (overrides like '... (Railgun)' map to their base ammo)."""
    stock = m["stock"]
    raw = a.get("internal_name", "")
    if raw in stock:
        return stock[raw]["name"]
    for r, s in stock.items():                   # AI-76 style '<weapon>_q6_<ammo raw>'
        if s["g"] == "ammo" and raw.endswith("_" + r):
            return s["name"]
    mm = re.match(r"(equipment_ammo_\w+?_\d\d)_exp", raw)   # '<ammo raw>_exp_<something>'
    if mm and mm.group(1) in stock:
        return stock[mm.group(1)]["name"]
    names = {s["name"] for s in stock.values()}
    base = re.sub(r"\s*\(.*\)$", "", a.get("name", ""))
    if base in names:
        return base
    inner = re.search(r"\(([^)]*)\)$", a.get("name", ""))   # 'Laser (High Voltage Battery Mag)'
    if inner and inner.group(1) in names:
        return inner.group(1)
    return None


def ammo_display(m, a):
    """Readable name of an ammo entry (a few override names in the files are raw internal names)."""
    name = a.get("name", "")
    mm = re.match(r"^(equipment_ammo_\w+?_\d\d)_exp (\(.*\))$", name)
    if mm and mm.group(1) in m["stock"]:
        return f'{m["stock"][mm.group(1)]["name"]} {mm.group(2)}'
    return name


def ammo_icon(site, m, a):
    """Icon of the stock.json ammo item an ammo entry belongs to ('img/stock/...'), or None."""
    st = m["stock"].get(a.get("internal_name", ""))
    if not st:
        name = ammo_name(m, a)
        st = next((x for x in m["stock"].values() if x["name"] == name), None) if name else None
    if not st or not st.get("icon"):
        return None
    p = st["icon"].replace("assets/", "img/", 1)
    return p if site.has_file(p) else None


def ammo_cell(site, m, a, icon=True):
    """Ammo name linked to its ammo page, with the ammo item's icon."""
    base = ammo_name(m, a)
    disp = ammo_display(m, a)
    s = site.link("ammo", base, text=disp) if base else esc(disp)
    if icon:
        s = f'<span class="ammoc">{img(site, ammo_icon(site, m, a), cls="amicon")}<span>{s}</span></span>'
    if a.get("experimental_only"):
        s += " " + tag("Exp. only", "exp")
    return s


def blast_text(b):
    """'Blast 290 (8 m); players 40 (8 m)'. The players part is left out when it does nothing."""
    if not b:
        return ""
    t = f'Blast {fmt(b["damage_to_machines"])} ({fmt(b["radius_vs_machines_m"])} m)'
    if b.get("damage_to_players"):
        t += f'; players {fmt(b["damage_to_players"])} ({fmt(b["radius_vs_players_m"])} m)'
    return t


TARGETS = {"characters": "players and people", "machines/objects": "machines and objects"}


def short_dot(dots):
    """'burn 2 / 0.5 s to players, 1 / 2 s to machines' (players first)."""
    order = sorted(dots, key=lambda d: d.get("target") != "characters")
    who = {"characters": "players", "machines/objects": "machines"}
    return "burn " + ", ".join(f'{fmt(d["damage_per_tick"])} / {fmt(d["tick_seconds"])} s to '
                               f'{who.get(d.get("target"), d.get("target", ""))}' for d in order)


def effect_only(a):
    """Which non-bullet effects carry the damage of an ammo whose projectile does 0 ('blast', 'burn', 'heal'), or
    [] when the bullet itself does damage."""
    if a.get("projectile_damage"):
        return []
    oh = a.get("on_hit") or {}
    return ([k for k, v in (("blast", oh.get("blast") or a.get("on_hit_stages")), ("burn", oh.get("damage_over_time")),
                            ("heal", oh.get("heal_pulse"))) if v])


def dot_text(d):
    return (f'{fmt(d["damage_per_tick"])} every {fmt(d["tick_seconds"])} s for {fmt(d["duration_seconds"])} s '
            f'to {esc(TARGETS.get(d.get("target"), d.get("target", "")))}')


def effects(a):
    """Everything an ammo entry does besides the bullet itself, as short HTML lines."""
    out = []
    oh = a.get("on_hit") or {}
    if oh.get("blast"):
        out.append(blast_text(oh["blast"]))
    for d in oh.get("damage_over_time") or []:
        out.append("Over time: " + dot_text(d))
    if oh.get("heal_pulse"):
        h = oh["heal_pulse"]
        out.append(f'Heals {fmt(h["damage_to_players"])} ({fmt(h["radius_vs_players_m"])} m)')
    if a.get("blast"):
        out.append(blast_text(a["blast"]))
    if a.get("on_hit_stages"):
        out.append(f'Blast grows in {len(a["on_hit_stages"])} stages (table below)')
    note_txt = a.get("note")
    if not note_txt and "Medical" in a.get("name", ""):
        if oh.get("heal_pulse"):
            note_txt = "Medical rounds heal players near the impact."
        elif oh.get("blast") or a.get("on_hit_stages"):
            where = "stages table below" if a.get("on_hit_stages") else "values above"
            note_txt = f"This experimental version replaces the heal with a blast ({where})."
    if note_txt:
        out.append(f'<span class="dim">{esc(note_txt)}</span>')
    return "<br>".join(out) or '<span class="dim">–</span>'


def per_shot(a, mult):
    d, p = a.get("projectile_damage"), a.get("projectiles_per_shot") or 1
    if d is None or mult is None:
        return None
    return d * p * mult


# ---------------------------------------------------------------------------------------------------------------
# collect: register every page and anchor
# ---------------------------------------------------------------------------------------------------------------
def collect(site):
    m = model(site)
    for w in m["weapons"]:
        aliases = {w["ids_name"], w["internal"], w["nick"]}
        aliases |= {s["sub_name"] for s in m["skins"] if s["weapon"] is w}
        aliases |= {w["name"].replace('"', "")}
        aliases |= {str(h) for h in w["item_ids"].values()}       # item IDs: searchable, printed only in the IDs panel
        if w["cat"] == "Throwables":
            aliases.add(m["stock"].get(w["internal"], {}).get("name"))
        site.register("weapon", w["name"], w["path"], w["name"], icon=w["icon"], desc=weapon_desc(w),
                      aliases=[a for a in aliases if a], keywords=" ".join(
                          filter(None, [w["cat"], CAT_INFO[w["cat"]][0], " ".join(w["calibres"]), w["nick"],
                                        w["internal"], pack_label(w["pack"])[0]])))
        if w["exp_name"]:
            site.register("weapon", w["exp_name"], w["path"] + "#experimental", w["exp_name"],
                          icon=w["exp_icon"] or w["icon"], desc=f"Experimental version of the {w['name']}.",
                          keywords="experimental q6 " + w["cat"])
    # the experimental weapons page, and each experimental weapon's row on it
    site.register("experimental", "Experimental weapons", EXP_PAGE, "Experimental weapons",
                  icon="img/crowns/6.png", aliases=["experimental", "Experimental", "q6"],
                  desc="The experimental (Q6) weapons: which weapons have one and what the files change.",
                  keywords="experimental q6 sixth quality pink")
    for w in m["weapons"]:
        if w["exp_name"]:
            site.register("experimental", w["exp_name"], f"{EXP_PAGE}#{w['slug']}", w["exp_name"],
                          aliases=[w["name"]], search=False)
    for s in m["skins"]:
        wn = s["weapon"]["name"] if s["weapon"] else s["sub_name"]
        site.register("skin", s["raw"], f"weapons/skins.html#{s['anchor']}", f"{s['name']} ({wn})",
                      icon=s["img"], desc=f"Weapon skin for the {wn}.",
                      aliases=[str(s["h"]), f"{wn} {s['name']}", s["nick"]], keywords="skin camo " + wn)


def weapon_desc(w):
    one = CAT_INFO[w["cat"]][0]
    cals = [c for c in w["calibres"] if c not in GENERIC_SUBS]
    cal = f", {'/'.join(cals)}" if cals else ""
    exp = ", has an experimental version" if w["exp_name"] else ""
    return f"{one.capitalize()}{cal}. {pack_label(w['pack'])[0]}{exp}."


# ---------------------------------------------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------------------------------------------
def build(site):
    m = model(site)
    build_index(site, m)
    for w in m["weapons"]:
        build_weapon(site, m, w)
    build_experimental(site, m)
    build_skins(site, m)
    old = os.path.join(site.out, "weapons", "quality.html")    # replaced by weapons/experimental.html
    if os.path.exists(old):
        os.remove(old)


# ---------------------------------------------------------------- weapons/index.html
def compare_row(site, m, w):
    """One row of the comparison table, and its filter tags."""
    a = w["std"]
    best_q = max((q for q in w["mult"] if q != 6), key=lambda q: w["mult"][q], default=None)
    best_m = w["mult"].get(best_q)
    oh = (a or {}).get("on_hit") or {}
    blast = oh.get("blast") if a else w["d"].get("blast")
    shot = per_shot(a, best_m) if a else None
    fx = effect_only(a) if a else []
    if fx:
        shot = None          # launchers, flamethrower: the round itself does nothing, the blast / burn is the damage
    if blast:
        area = blast["damage_to_machines"]
    elif oh.get("damage_over_time"):
        area = short_dot(oh["damage_over_time"])
    else:
        area = None
    row = [
        img(site, w["icon"], cls="wicon"),
        f'<a href="~/{w["path"]}">{esc(w["name"])}</a>',
        ", ".join(site.link("caliber", c, text=c) for c in w["calibres"]) or "–",   # short: no ' ammo' suffix
        ammo_cell(site, m, a) if a else '<span class="dim">–</span>',
        a["projectile_damage"] if a and not fx else None,
        round(shot, 1) if shot is not None else None,
        area,
        qrange(w, exp_href=f"~/{EXP_PAGE}#{w['slug']}" if w["exp_name"] else None),
        pack_short(site, w["pack"]),
        index_range_cell(a) if a else None,
    ]
    fs = ["c-" + slug(w["cat"]), "dlc" if pack_label(w["pack"])[1] else "base"]
    if w["exp_name"]:
        fs.append("exp")
    return row, (" ".join(fs), f'{w["cat"]} {CAT_INFO[w["cat"]][0]} {w["exp_name"] or ""}')


def index_range_cell(a):
    """Max range first (so the column sorts roughly by range), then the falloff."""
    if "max_range_m" not in a:
        return None
    return (f'{fmt(a["max_range_m"])} m<br><span class="dim small">{esc(a.get("falloff", ""))}</span>')


def table_f(headers, rows, fs, **kw):
    """table() with a data-f attribute (filter tags) and a data-w attribute (extra words the text filter matches)
    on every body row; fs = [(tags, words)]."""
    html = table(headers, rows, **kw)
    parts = html.split("<tr>")
    out = parts[0] + "<tr>" + parts[1]
    for (f, wds), p in zip(fs, parts[2:]):
        out += f'<tr data-f="{esc(f)}" data-w="{esc(wds)}">' + p
    return out


def filterbar(target, cats=(), extra=True):
    """Text filter plus chips: one per category in cats (none when empty) and, with extra, pack / experimental."""
    chips = ('<button class="chip on" data-g="c" data-f="*">All</button>' + "".join(
        f'<button class="chip" data-g="c" data-f="c-{slug(c)}">{esc(c)}</button>' for c in cats)) if cats else ""
    if extra:
        chips += (('<span class="fsep"></span>' if cats else "") +
                  '<button class="chip on" data-g="p" data-f="*">Any pack</button>'
                  '<button class="chip" data-g="p" data-f="base">Base game</button>'
                  '<button class="chip" data-g="p" data-f="dlc">DLC</button>'
                  '<button class="chip" data-g="p" data-f="exp">Has experimental</button>')
    return (f'<div class="filterbar" data-for="{target}"><input placeholder="Filter weapons..." aria-label="Filter">'
            f'{chips}<span class="count"></span></div>')


def build_index(site, m):
    ws = m["weapons"]
    cats = list(CAT_INFO)
    n_dlc = sum(1 for w in ws if pack_label(w["pack"])[1])
    n_exp = sum(1 for w in ws if w["exp_name"])
    body = []
    for cat in cats:
        cws = [w for w in ws if w["cat"] == cat]
        body.append(bar(cat, f"{len(cws)}", id=slug(cat)))
        body.append(f"<p>{esc(CAT_BLURB[cat])}</p>")
        body.append(cards([card(site, w) for w in cws], cls="wcards"))
    # the comparison table: below the list, one small closed table per category (same columns in each)
    headers = ["", "Weapon", "Calibre", "Standard ammo", "Damage", "Best shot", "Blast / burn",
               "Qualities", "Pack", "Range / falloff"]
    groups = []
    for cat in cats:
        cws = [w for w in ws if w["cat"] == cat]
        rows, fs = zip(*(compare_row(site, m, w) for w in cws))
        groups.append(fold(cat, table_f(headers, rows, fs, cls="compact wcmp", num={4, 5}), open=False, level=3,
                           right=f"{len(cws)} weapons", id="cmp-" + slug(cat), cls="wcmpfold"))
    cmp_html = [
        "<p>Every weapon side by side, one table per category: open a category to compare its weapons. Click a "
        "column header to sort; type in the filter box to search all categories at once, or use the chips to show "
        "only base game or DLC weapons, or weapons with an experimental version.</p>",
        filterbar("wcompare"),
        '<div class="foldall" data-for="wcompare"></div>',
        '<div id="wcompare">' + "".join(groups) + "</div>",
        "<h3>How to read the columns</h3>",
        "<p>In Generation Zero the damage of a shot is set by the <b>ammunition</b>, not by the gun: every "
        "7.62mm weapon, from the AI-76 to the Kotenok, fires the same 33-damage bullet. What the gun adds is a "
        "<b>quality multiplier</b> (listed on each weapon page): a Dilapidated copy usually does ×0.5 of that, "
        "a Special one ×1.0. A few weapons have their own multipliers – the Kotenok (up to ×1.4), the S21 (up to "
        "×1.6) and the Kvm 89 (×1.1 at Special).</p>",
        kv([("Standard ammo", "FMJ where there is one, the slug for shotguns, the plain arrow for the bow, "
                              "the high-explosive round for launchers. Each weapon page lists every ammo, "
                              "including buckshot (9 pellets) and birdshot (25 pellets)."),
            ("Damage", "Base damage of one bullet, slug or arrow of the standard ammo. Empty for "
                       "rounds whose projectile does no damage itself (launchers, flamethrower)."),
            ("Best shot", "Damage × the weapon's best non-experimental quality multiplier: what one shot "
                          "of the standard ammo does at most, at close range."),
            ("Blast / burn", "Area damage to machines for explosive ammo and throwables; for the flamethrower "
                             "its burn (damage per tick / tick length)."),
            ("Qualities", "The lowest and highest quality the weapon comes in; a pink Q6 badge means it also has an "
                          "experimental version (the badge opens it on the experimental weapons page)."),
            ("Range / falloff", "Farthest the projectile flies, and how its damage drops with distance.")]),
        note("Fire rate, magazine size, recoil and reload time are not in the extracted files, so they are not "
             "in these tables. Melee hit damage isn't either – only the melee quality multipliers.", "data")]
    body.append(fold("Comparison table", "".join(cmp_html), open=True, right=f"{len(ws)} weapons",
                     id="comparison-table"))
    n_skins = len(m["skins"])
    glance = kv([("Weapons", fmt(len(ws))), ("Categories", fmt(len(cats))),
                 ("From DLC", fmt(n_dlc)),
                 ("Experimental", f'<a href="~/{EXP_PAGE}">{n_exp} weapons</a>'),
                 ("Skins", f'<a href="~/weapons/skins.html">{n_skins}</a>')])
    lead = (f"<p>Every player weapon in the game files: {len(ws)} weapons in {len(cats)} categories, "
            f"{n_dlc} of them from DLC packs and {n_exp} with an experimental version. Pick a weapon for its "
            "damage per ammo and quality, attachments, augments, skins and where it is placed in the world; the "
            '<a href="#comparison-table">comparison table</a> at the bottom puts them all side by side.</p>')
    site.page("weapons/index.html", "Weapons", "".join(body), "weapons", lead=lead, head_extra=CSS + JS,
              side=[panel("At a glance", glance)],
              desc="Every Generation Zero weapon by category, with a comparison table of damage, ammo and range.")


def card(site, w):
    a = w["std"]
    bits = []
    if w["calibres"]:
        bits.append(esc(" / ".join(w["calibres"])))
    if a and a.get("projectile_damage"):
        p = a["projectiles_per_shot"]
        bits.append(f'{fmt(a["projectile_damage"])}{"×" + str(p) if p > 1 else ""} dmg')
    blast = (a or {}).get("on_hit", {}).get("blast") if a else w["d"].get("blast")
    if blast and blast["damage_to_machines"]:
        bits.append(f'blast {fmt(blast["damage_to_machines"])}')
    bits.append(esc(pack_label(w["pack"])[0]))
    return {"href": "~/" + w["path"], "title": w["name"], "sub": " · ".join(bits),
            "img": "~/" + w["icon"] if w["icon"] else None, "color": CAT_INFO[w["cat"]][1],
            "tag": "DLC" if pack_label(w["pack"])[1] else ("EXP" if w["exp_name"] else None)}


# ---------------------------------------------------------------- weapons/<slug>.html
def build_weapon(site, m, w):
    if w["cat"] == "Throwables":
        return build_throwable(site, m, w)
    body = []
    body += section_damage(site, m, w)
    body += section_experimental(site, m, w)
    body += section_augments(site, m, w)
    body += section_skins(site, m, w)
    body += section_loot(site, m, w)
    body += section_related(site, m, w)
    site.page(w["path"], w["name"], "".join(body), "weapons", sub="weapons",
              crumbs=[("All weapons", "~/weapons/index.html"), (w["cat"], f"~/weapons/index.html#{slug(w['cat'])}")],
              desc=weapon_desc(w), infobox_html=weapon_infobox(site, m, w), kind=f"Weapon · {w['cat']}",
              lead=weapon_lead(site, m, w), head_extra=CSS,
              side=[attachments_panel(site, w), ids_panel(site, w)])


def weapon_infobox(site, m, w):
    n_skin = sum(1 for s in m["skins"] if s["weapon"] is w)
    n_placed = len(m["loot"].get(w["name"], []))
    a = w["std"]
    best = None
    if a and a.get("projectile_damage") and not effect_only(a):
        best = max((v for q, v in w["mult"].items() if q != 6), default=None)
    rows = [("Category", esc(w["cat"])),
            ("Calibre" if not set(w["calibres"]) & set(GENERIC_SUBS) else "Ammo",
             calibre_links(site, w, m) if w["calibres"] else None),
            ("Pack", pack_tag(site, w["pack"])),
            ("Qualities", " ".join(qbadge(q, True) for q in w["quals"]) or None),
            ("Best shot", n1(per_shot(a, best)) if best is not None else None),
            ("Experimental", f'<a href="#experimental">{esc(w["exp_name"])}</a>' if w["exp_name"] else "None"),
            ("Skins", f'<a href="#skins">{n_skin}</a>' if n_skin else "None"),
            ("Placed in world", f'<a href="#where-to-find-it">{n_placed}</a>' if n_placed else "None")]
    sub = esc(CAT_INFO[w["cat"]][0].capitalize())
    return infobox(w["name"], rows, image="~/" + w["icon"] if w["icon"] else None, subtitle=sub)


def weapon_lead(site, m, w):
    one = CAT_INFO[w["cat"]][0]
    if w["cat"] == "Bows and flamethrowers":
        one = "bow" if "bow" in w["internal"] else "flamethrower"
    label, dlc = pack_label(w["pack"])
    src = f"from the {esc(label)}" if dlc else "in the base game"
    cal = f" that fires {calibre_links(site, w, m)}" if w["calibres"] else ""
    qs = [q for q in w["quals"] if q != 6]
    q_txt = (f"It comes in {len(qs)} qualities, {qbadge(qs[0])} to {qbadge(qs[-1])}" if qs else "")
    exp = (f", plus an experimental version, the <a href=\"#experimental\">{esc(w['exp_name'])}</a>." if w["exp_name"]
           else ". There is no experimental version.")
    art = "an" if one[0] in "aeiou" else "a"
    return f"<p>The {esc(w['name'])} is {art} {one}{cal}{',' if cal else ''} {src}. {q_txt}{exp}</p>"


def range_cell(a):
    """Falloff and maximum range in one cell."""
    if "falloff" not in a:
        return "–"
    return f'{esc(a["falloff"])}<br><span class="dim small">max {fmt(a.get("max_range_m"))} m</span>'


def damage_table(site, m, w, ammo, quals):
    """Two tables: what each ammo is (damage, pellets, multipliers, range, effects), then one shot's damage per
    quality with the best quality's damage against armour and components."""
    with_fx = any(effects(a) != '<span class="dim">–</span>' for a in ammo)
    heads = ["Ammo", "Damage", "Pellets", "Armour", "Comp.", "Falloff / range"] + (["Effects"] if with_fx else [])
    rows = [[ammo_cell(site, m, a), a.get("projectile_damage"), a.get("projectiles_per_shot"),
             mult_cell(a.get("armour_multiplier")), mult_cell(a.get("component_multiplier")), range_cell(a)]
            + ([effects(a)] if with_fx else []) for a in ammo]
    props = table(heads, rows, num={1, 2}, cls="dmg")
    top = quals[-1]
    heads = ["Ammo"] + [qhead(site, q) for q in quals] + [f"{qbadge(top, True)} vs armour",
                                                         f"{qbadge(top, True)} vs components"]
    rows, fx_only, smoke = [], [], []
    for a in ammo:
        if effect_only(a):          # 0-damage round: a row of zeros would say it does nothing
            fx_only += [k for k in effect_only(a) if k not in fx_only]
            continue
        if not a.get("projectile_damage") and "smoke" in a["internal_name"] and not a.get("on_hit"):
            smoke.append(a)
            continue
        r = [ammo_cell(site, m, a)]
        for q in quals:
            sh = per_shot(a, w["mult"].get(q))
            r.append(f'<span class="qc{q}">{n1(sh)}</span>' if sh is not None else None)
        best = per_shot(a, w["mult"].get(top))
        r += [n1(best * a["armour_multiplier"]) if best is not None else None,
              n1(best * a["component_multiplier"]) if best is not None else None]
        rows.append(r)
    per_q = table(heads, rows, num=set(range(1, len(quals) + 3)), cls="compact perq", raw_headers=True,
                  caption="Damage of one shot (all pellets) by quality") if rows else ""
    dmg_fx = [k for k in fx_only if k != "heal"]
    if dmg_fx:
        lead = "For the rounds left out of this table, damage" if rows else "Damage"
        per_q += (f'<p class="small dim">{lead} comes from the {" / ".join(dmg_fx)} (see Effects), not the '
                  "projectile; the files don't say whether quality scales it.</p>")
    if smoke:
        per_q += (f'<p class="small dim">{esc(", ".join(ammo_display(m, a) for a in smoke))}: 0 damage in the files, at '
                  "every quality.</p>")
    if "heal" in fx_only:
        per_q += ('<p class="small dim">Rounds whose projectile does no damage and that heal (medical ammo) are left '
                  "out of this table: see Effects for the heal.</p>")
    return props + per_q


def qhead(site, q):
    """A quality column header: the crown icon over the short badge."""
    return f'<span class="qh">{img(site, f"img/crowns/{q}.png", f"{q} crowns", cls="crown")}{qbadge(q, True)}</span>'


def stages_table(a):
    """Blast stages: by bow draw (charge) or by bullet flight time (lifetime)."""
    rows = []
    for st in a["on_hit_stages"]:
        rq = st["requirement"]
        if "charge" in rq:
            cond = f"Bow drawn ≥ {round(rq['charge'] * 100)}%"
        elif "lifetime" in rq:
            cond = f"Bullet in flight ≥ {fmt(rq['lifetime'])} s"
        else:
            cond = esc(", ".join(f"{k} {v}" for k, v in rq.items()))
        b = st.get("blast") or {}
        rows.append([cond, b.get("damage_to_machines"), b.get("radius_vs_machines_m"), b.get("damage_to_players"),
                     b.get("radius_vs_players_m")])
    return table(["Condition", "Blast vs machines", "Radius (m)", "Blast vs players", "Radius (m)"], rows,
                 sortable=False, cls="compact", num={1, 2, 3, 4})


def ammo_tips(m, w, ammo):
    """A few practical notes worked out from the numbers."""
    tips = []
    qs = [q for q in w["quals"] if q != 6]
    if qs and w["mult"] and any(a.get("projectile_damage") for a in ammo):   # not for blast / burn-only weapons
        lo, hi = w["mult"][qs[0]], w["mult"][qs[-1]]
        tips.append(f"A {QNAME[qs[0]]} copy does {round(lo / hi * 100)}% of the damage of a {QNAME[qs[-1]]} one "
                    f"(×{fmt(lo)} against ×{fmt(hi)}), so upgrading quality is a straight damage increase.")
    dmg = [a for a in ammo if a.get("projectile_damage")]
    if len(dmg) > 1:
        ar = max(dmg, key=lambda a: a["armour_multiplier"])
        co = max(dmg, key=lambda a: a["component_multiplier"])
        if ar["armour_multiplier"] > 1:
            tips.append(f"Against armour plates, {esc(ammo_display(m, ar))} is best (×{fmt(ar['armour_multiplier'])}"
                        f" damage to armour).")
        if co["component_multiplier"] > 1:
            tips.append(f"Against exposed components, {esc(ammo_display(m, co))} is best "
                        f"(×{fmt(co['component_multiplier'])} damage to components).")
    multi = [a for a in dmg if a["projectiles_per_shot"] > 1]
    single = [a for a in dmg if a["projectiles_per_shot"] == 1]
    if multi and single:
        a, s = max(multi, key=lambda a: a["projectile_damage"] * a["projectiles_per_shot"]), single[0]
        tips.append(f"{esc(ammo_display(m, a))} puts {fmt(a['projectile_damage'] * a['projectiles_per_shot'])} "
                    f"damage per shot on target if all {a['projectiles_per_shot']} pellets hit, against "
                    f"{fmt(s['projectile_damage'])} for one {esc(ammo_display(m, s))}. Range is the catch: the "
                    f"pellets' damage {esc(a['falloff'])}, the single round's {esc(s['falloff'])}.")
    return "<ul>" + "".join(f"<li>{t}</li>" for t in tips) + "</ul>" if tips else ""


def section_damage(site, m, w):
    d = w["d"]
    quals = [q for q in w["quals"] if q != 6]
    if not d.get("ammo"):
        out = [bar("Damage and quality")]
        out.append(f"<p>{esc(d.get('note', 'The files hold no damage values for this weapon.'))}</p>")
        out.append(mult_table(site, w))
        return out
    out = [bar("Damage by ammo and quality")]
    std = [a for a in d["ammo"] if not a.get("experimental_only")]
    exp = [a for a in d["ammo"] if a.get("experimental_only")]
    out.append("<p>The first table lists each ammo type the weapon can load. <b>Damage</b> is one projectile at "
               "the base value (Special quality), <b>Armour</b> and <b>Comp.</b> multiply it when the projectile "
               "hits an armour plate or a component, and <b>Falloff</b> is how the damage drops over distance. "
               "The second table works out one whole shot (damage × pellets × the quality multiplier) for every "
               "quality, at close range and before the difficulty setting.</p>")
    out.append(damage_table(site, m, w, std, quals))
    out.append(mult_table(site, w))
    out.append(ammo_tips(m, w, std))
    for a in d["ammo"]:
        if a.get("on_hit_stages"):
            out.append(f"<h3>{esc(ammo_display(m, a))}: blast by stage</h3>"
                       "<p>The blast of this ammo depends on how far the bow is drawn. Each line is the minimum "
                       "draw for that blast.</p>" + stages_table(a))
    if exp:
        has6 = 6 in w["quals"]
        out.append("<h3>Experimental ammo of this calibre</h3>")
        if has6:
            out.append(f"<p>The game files flag these rounds as experimental-only: they are for the experimental "
                       f"version. The column shows one shot at the experimental multiplier "
                       f"(×{fmt(w['mult'].get(6))}).</p>")
            out.append(damage_table(site, m, w, exp, [6]))
        else:
            out.append("<p>The game files flag these rounds as experimental-only, and this weapon has no "
                       "experimental version. They are listed because they share its calibre; the damage column "
                       "uses the Special multiplier for comparison.</p>")
            out.append(damage_table(site, m, w, exp, quals[-1:]))
    if any(a.get("note", "").startswith("Special effect") for a in d["ammo"]):
        out.append(note("Rows marked “Special effect not included” have an extra effect (shock tethers, tar, "
                        "proximity bombs, radiation...) that lives in a separate effect file the extractor doesn't "
                        "read. The bullet damage shown is correct; the effect comes on top.", "data"))
    return out


def mult_table(site, w):
    qs = sorted(w["mult"])
    if not qs:
        return ""
    return table(["Quality"] + [qhead(site, q) for q in qs],
                 [["Damage multiplier"] + [f'<span class="qc{q}">×{fmt(w["mult"][q])}</span>' for q in qs]],
                 sortable=False, cls="compact", caption="Quality multipliers of this weapon", raw_headers=True)


def section_experimental(site, m, w):
    if not w["exp_name"]:
        return []
    d = w["d"]
    ov = d.get("experimental_ammo_overrides") or []
    out = [bar("Experimental version", esc(w["exp_name"]), id="experimental")]
    pic = img(site, w["exp_icon"], cls="expimg")
    out.append(f'<div class="expbox">{pic}<div><p><b>{esc(w["exp_name"])}</b> is the {qbadge(6)} version of this '
               f'weapon. Its damage multiplier is ×{fmt(w["mult"].get(6))} (Special: ×{fmt(w["mult"].get(5))}). '
               f'See <a href="~/{EXP_PAGE}">experimental weapons</a> for the other experimental weapons.</p>'
               '</div></div>')
    if not ov:
        out.append("<p>The files hold no separate ammo values for the experimental version: it fires the normal "
                   "ammo above, and its special behaviour lives in files the extractor doesn't read.</p>")
        return out
    shots = [a for a in ov if "projectile_damage" in a]
    blasts = [a for a in ov if "projectile_damage" not in a]
    if shots:
        n = len(shots)
        out.append(f"<p>The game files give the experimental version its own versions of {n} ammo "
                   f"type{'s' if n != 1 else ''}. These replace the normal values when fired from it. The damage "
                   f"column is one shot at the experimental multiplier (×{fmt(w['mult'].get(6))}).</p>")
        foreign = foreign_calibres(m, w, shots)
        if len(foreign) > 2:
            own = "" if set(w["calibres"]) & {ammo_calibre(m, a) for a in shots} else \
                f" (and none for {esc('/'.join(w['calibres']))})"
            out.append(note(f"The files give the experimental {esc(w['name'])} its own entries for {n} ammo types "
                            f"of {len(foreign)} other calibres{own}. The data doesn't say what the game does with "
                            "them.", "data"))
        cals = []
        for a in shots:
            if ammo_calibre(m, a) not in cals:
                cals.append(ammo_calibre(m, a))
        if len(cals) > 2:
            out.append('<div class="tabset"><div class="tsbtns">' + "".join(
                f"<button>{esc(c)}</button>" for c in cals) + "</div>" + "".join(
                '<div class="tspane">' + override_table(site, m, w, [a for a in shots if ammo_calibre(m, a) == c])
                + "</div>" for c in cals) + "</div>")
        else:
            out.append(override_table(site, m, w, shots))
        if any(a.get("falloff") == "drops to 0% by ~0 m" for a in shots):
            out.append(note("Some of these entries have an empty falloff curve in the files, shown as “drops to "
                            "0% by ~0 m”. The data doesn't say how the game treats that, so take those rows' "
                            "falloff with a grain of salt.", "data"))
        for a in shots:
            if a.get("on_hit_stages"):
                out.append(f"<h3>{esc(ammo_display(m, a))}: blast by flight time</h3>"
                           "<p>The longer the bullet has been in the air, the bigger its blast.</p>" + stages_table(a))
    if blasts:
        out.append("<p>Blasts that belong to the experimental version itself:</p>")
        out.append(table(["Effect", "vs machines", "Radius (m)", "vs players", "Radius (m)"],
                         [[esc(a["name"]), a["blast"]["damage_to_machines"],
                           a["blast"]["radius_vs_machines_m"], a["blast"]["damage_to_players"],
                           a["blast"]["radius_vs_players_m"]] for a in blasts], num={1, 2, 3, 4}))
        if any("stun" in a["internal_name"] for a in blasts):
            out.append("<p>The discharge and stun pairs are the three charge levels of the hammer's electric "
                       "attack: the longer it charges, the bigger the discharge.</p>")
    return out


def foreign_calibres(m, w, shots):
    """Calibres of override entries that are not the weapon's own calibre (the AI-76 has 8 of them)."""
    return {ammo_calibre(m, a) for a in shots} - set(w["calibres"])


def ammo_calibre(m, a):
    name = ammo_name(m, a)
    return next((s["sub"] for s in m["stock"].values() if s["name"] == name), name)


def effect_diff(key, b, x):
    """What changed in one on_hit effect both entries have, e.g. 'burn 6→30 per tick, 2→3 s'."""
    if b == x:
        return None
    arrow = lambda f, lab, unit="": (f"{fmt(b.get(f))}→{fmt(x.get(f))}{unit}{' ' + lab if lab else ''}"
                                     if b.get(f) != x.get(f) else None)
    if key == "damage_over_time" and len(b) == len(x) == 1:
        b, x = b[0], x[0]
        parts = [arrow("damage_per_tick", "per tick"), arrow("tick_seconds", "tick", " s"),
                 arrow("duration_seconds", "", " s")]
        return "burn " + ", ".join(p for p in parts if p) if any(parts) else "different burn values"
    if key in ("blast", "heal_pulse"):
        lab = "blast" if key == "blast" else "heal"
        parts = [arrow("damage_to_machines", "vs machines"), arrow("damage_to_players", "vs players"),
                 arrow("radius_vs_machines_m", "radius", " m")]
        return lab + " " + ", ".join(p for p in parts if p) if any(parts) else f"different {lab} values"
    return "different effect values"


def override_changes(site, m, base, a):
    """What an experimental override changes compared with the normal ammo, as short HTML lines."""
    if not base:
        rng = f"; falloff {esc(a['falloff'])}, max {fmt(a.get('max_range_m'))} m" if a.get("falloff") else ""
        nm = ammo_name(m, a)
        if nm and any(s["name"] == nm for s in m["stock"].values()):
            return "experimental-only ammo: " + site.link("ammo", nm) + rng
        return "no normal counterpart" + rng
    diff = []
    for k, lab in (("projectile_damage", "damage"), ("projectiles_per_shot", "pellets"),
                   ("armour_multiplier", "armour ×"), ("component_multiplier", "components ×"),
                   ("max_range_m", "range")):
        if base.get(k) != a.get(k):
            diff.append(f"{lab} {fmt(base.get(k))} → {fmt(a.get(k))}")
    if base.get("falloff") != a.get("falloff"):
        diff.append(f"falloff {esc(base.get('falloff'))} → {esc(a.get('falloff'))}")
    kinds = lambda x: set((x.get("on_hit") or {})) | ({"staged blast"} if x.get("on_hit_stages") else set())
    names = {"blast": "blast", "damage_over_time": "damage over time", "heal_pulse": "heal pulse",
             "staged blast": "staged blast"}
    added, dropped = kinds(a) - kinds(base), kinds(base) - kinds(a)
    diff += [f"adds {names.get(k, k)}" for k in sorted(added)] + [f"no {names.get(k, k)}" for k in sorted(dropped)]
    boh, aoh = base.get("on_hit") or {}, a.get("on_hit") or {}
    for k in ("damage_over_time", "heal_pulse", "blast"):       # effects both have: compare their values
        if k in boh and k in aoh:
            dd = effect_diff(k, boh[k], aoh[k])
            if dd:
                diff.append(dd)
    if base.get("on_hit_stages") and a.get("on_hit_stages") and base["on_hit_stages"] != a["on_hit_stages"]:
        diff.append("different blast stages")
    return "; ".join(diff) or "same as normal"


def override_table(site, m, w, ammo):
    """Experimental overrides compared with the normal ammo they replace."""
    std = dict(m["ammo_by_name"])
    std.update({ammo_name(m, a): a for a in w["d"].get("ammo") or []})   # this weapon's own entries first
    rows = []
    for a in ammo:
        s6 = per_shot(a, w["mult"].get(6))
        ch = override_changes(site, m, std.get(ammo_name(m, a)), a)
        rows.append([ammo_cell(site, m, a) + f'<div class="chg">{ch}</div>', a.get("projectile_damage"),
                     a.get("projectiles_per_shot"), f'<span class="qc6">{n1(s6)}</span>' if s6 is not None else None,
                     mult_cell(a.get("armour_multiplier")), mult_cell(a.get("component_multiplier")), effects(a)])
    return table(["Ammo (change from normal)", "Damage", "Pellets", qbadge(6, True), "Armour", "Comp.", "Effects"],
                 rows, num={1, 2, 3}, cls="dmg", raw_headers=True)


def fitting_attachments(site, w):
    """[(group, name, entry)] of IDs.json attachments whose WPNCompat lists the weapon's ToolID."""
    if not w["tool_id"]:
        return []
    out = []
    for grp, ats in site.data("IDs")["Attachments"].items():
        for name, e in ats.items():
            if w["tool_id"] in [t.strip() for t in e.get("WPNCompat", "").split(",")]:
                out.append((grp, name, e))
    return out


def attachments_panel(site, w):
    """Side panel: the attachments that fit, grouped by type, with their icons."""
    if not w["tool_id"] or w["cat"] == "Melee":
        return ""
    ats = fitting_attachments(site, w)
    if not ats:
        return panel("Attachments", '<p class="small dim">No attachment fits this weapon.</p>', cls="wside")
    icons = site.data("icons")
    out, last = [], None
    for grp, name, e in ats:
        if grp != last:
            if last is not None:
                out.append("</ul>")
            out.append(f'<div class="atg">{esc(grp)}</div><ul class="atlist">')
            last = grp
        ic = icons.get(e.get("1") or e.get("0") or "")
        out.append(f'<li>{img(site, "img/" + ic if ic else None, cls="aticon")}{site.link("attachment", name)}</li>')
    out.append("</ul>")
    return panel(f"Attachments ({len(ats)})", "".join(out), cls="wside")


def ids_panel(site, w):
    """Side panel: the item ID (item hash) of each quality, the one place the wiki prints them."""
    if not w["item_ids"]:
        return ""
    rows = "".join(f'<tr><td>{qbadge(q)}</td><td class="idv">{esc(h)}</td></tr>'
                   for q, h in sorted(w["item_ids"].items()))
    return panel("Item IDs", f'<table class="idtab">{rows}</table><p class="small dim">Each quality is a separate '
                             "item with its own ID, as save editors use them.</p>", cls="wside")


def augment_fits(site, w):
    """{augment name: (group, quality mask, restriction text)} for this weapon."""
    if w["aug_index"] is None:
        return {}
    aug = site.data("augments")["augments"]
    groups = {n: g for g, ns in site.data("IDs")["Augments"].items() for n in ns}
    out = {}
    for name, a in aug.items():
        mask = dict((i, mk) for i, mk in a["fits"]).get(w["aug_index"], 0)
        out[name] = (groups.get(name, "?"), mask, a.get("only", ""))
    return out


def section_augments(site, m, w):
    fits = augment_fits(site, w)
    if not fits:
        return []
    ids_aug = site.data("IDs")["Augments"]
    out = []
    out.append("<p>Augments go into slots that depend on quality. Following the in-game rules: Worn and Good "
               "weapons take one <b>Primary</b> augment, Exceptional and Special take a Primary and a "
               "<b>Support</b> augment, and Dilapidated and experimental weapons take none. A ✓ means the augment "
               "fits this weapon at that quality, as the game's equipment compatibility table says.</p>")
    for grp in ("Primary", "Support"):
        quals = [q for q in w["quals"] if grp in AUG_SLOTS.get(q, ())]
        rows, no = [], []
        for name in ids_aug.get(grp, {}):
            g, mask, only = fits.get(name, (grp, 0, ""))
            if not mask:
                no.append((name, only))
                continue
            ic = next(iter(ids_aug[grp][name].values())).get("Augment")
            cells = []
            for q in quals:
                ok = mask >> (q - 1) & 1
                cells.append('<span class="ok">✓</span>' if ok else '<span class="dim">–</span>')
            rows.append([img(site, "img/augments/" + ic if ic else None, cls="aicon"), site.link("augment", name)]
                        + cells + [esc(only) or '<span class="dim">–</span>'])
        out.append(f"<h3>{grp} augments</h3>")
        out.append(table(["", "Augment"] + [qhead(site, q) for q in quals] + ["Restriction"], rows, cls="compact augtab",
                         raw_headers=True))
        if no:
            out.append("<p class=\"small dim\">Don't fit: " + "; ".join(
                f"{site.link('augment', n)}{f' ({esc(o)})' if o else ''}" for n, o in no) + "</p>")
    odd = {n: mk for n, (g, mk, o) in fits.items() if mk and mk != 31}
    if odd:
        qs = sorted({q for mk in odd.values() for q in range(1, 6) if not mk >> (q - 1) & 1})
        out.append(note(f"The compatibility table leaves out {', '.join(QNAME[q] for q in qs)} for this weapon, so "
                        f"a {', '.join(QNAME[q] for q in qs)} copy can't take those augments.", "data"))
    n_fit = sum(1 for g, mk, o in fits.values() if mk)
    return [fold("Augments", "".join(out), open=False, right=f"{n_fit} of {len(fits)} fit", id="augments")]


def section_skins(site, m, w):
    sk = [s for s in m["skins"] if s["weapon"] is w]
    out = [bar("Skins", f"{len(sk)}", id="skins")]
    if not sk:
        out.append("<p>The game has no weapon skins for this weapon.</p>")
        return out
    out.append(f'<p>Skins change only the look. All skins: <a href="~/weapons/skins.html#{w["slug"]}">'
               "weapon skins</a>.</p>")
    out.append(skin_grid(site, sk))
    return out


def status_tag(s):
    label, cls = SKIN_STATUS.get(s["l"], (s["l"], ""))
    return tag(label, cls)


def skin_grid(site, sk, show_weapon=False):
    items = []
    for s in sk:
        tags = status_tag(s)
        wn = f'<span class="dim">{esc(s["weapon"]["name"])}</span>' if show_weapon and s["weapon"] else ""
        items.append(f'<a class="icon fitem" href="~/weapons/skins.html#{s["anchor"]}" style="--c:'
                     f'{"#8a6d1f" if s["dlc"] else "#3d4a50"}">{img(site, s["img"], s["name"], cls="")}'
                     f'<b>{esc(s["name"])}</b>{wn}{tags}</a>')
    return '<div class="icongrid">' + "".join(items) + "</div>"


def nearest_location(site, x, z):
    best, bd = None, None
    for loc in site.data("map_locations")["list"]:
        dd = math.hypot(loc["x"] - x, loc["z"] - z)
        if bd is None or dd < bd:
            best, bd = loc, dd
    return best, bd


def spot_link(s, zoom=1.2):
    """Map link for one placed copy: only its loot category, centred on it with its popup open."""
    return maplink(show=[s["sub"]], at=(s["x"], s["z"]), zoom=zoom, focus=s["n"])


def loot_minimap(spots, height):
    """The mini map of all placed copies. Its 'Open the full map' button shows only the loot categories these
    copies are in (placed weapons are grouped by quality on the map), centred on the best copy with its popup open."""
    top = spots[0]
    shows = sorted({s["sub"] for s in spots})
    html = minimap(top["x"], top["z"], top["n"], zoom=1, height=height, show=shows, focus=top["n"],
                   markers=[(s["x"], s["z"], s["n"]) for s in spots[1:]])
    # minimap() leaves out at= when there are several pins: centre the full map on the best copy as well
    full = maplink(show=shows, at=(top["x"], top["z"]), zoom=0.6, focus=top["n"])
    html = re.sub(r'(<a class="mmopen" href=")[^"]*', lambda mm: mm.group(1) + full, html, count=1)
    return html + map_caption(spots, height, href=full)


def coords_fold(site, spots, quals=True):
    """The list of every placed copy, closed under a 'Detailed coordinates' bar."""
    rows = []
    for s in spots:
        loc, dist = nearest_location(site, s["x"], s["z"])
        r = [qbadge(s["q"])] if quals else []
        r += [site.link("region", s["region"], text=REGION_NAME.get(s["region"], "–")) if s["region"] else "–",
              site.link("location", loc["name"]) if loc else "–", round(dist) if loc else None,
              round(s["x"]), round(s["z"]), f'<a href="{spot_link(s)}">Map</a>']
        rows.append(r)
    heads = (["Quality"] if quals else []) + ["Region", "Nearest location", "Distance (m)", "x", "z", ""]
    o = 1 if quals else 0
    body = ("<p>Every spot, with the nearest named map location and its distance. Coordinates are the game's world "
            "x / z; <b>Map</b> opens the interactive map on that spot.</p>"
            + table(heads, rows, cls="compact", num={o + 2, o + 3, o + 4}))
    return fold("Detailed coordinates", body, open=False, level=3, right=f"{len(spots)} spots",
                id="detailed-coordinates")


def loot_counts_table(site, spots, quals):
    regs = [k for k, _ in REGIONS if any(s["region"] == k for s in spots)]
    rows = []
    for r in regs:
        cnt = [sum(1 for s in spots if s["region"] == r and s["q"] == q) or None for q in quals]
        rows.append([site.link("region", r, text=REGION_NAME[r])] + cnt + [sum(c or 0 for c in cnt)])
    rows.append(["<b>Total</b>"] + [sum(1 for s in spots if s["q"] == q) or None for q in quals] + [len(spots)])
    return table(["Region"] + [QNAME[q] for q in quals] + ["Total"], rows, num=set(range(1, len(quals) + 2)),
                 cls="compact")


def map_caption(spots, height, width=640, href="~/map/index.html"):
    """A caption when the spots are too spread out for the mini map's first view. wiki.js fits the view to all
    pins but never below 1/4 scale (world units / 2 = full-size map pixels), so a wide spread opens zoomed in."""
    xs, zs = [s["x"] / 2 for s in spots], [s["z"] / 2 for s in spots]
    span_w, span_h = max(xs) - min(xs) + 200, max(zs) - min(zs) + 200
    if len(spots) < 2 or (span_w * 0.25 <= width and span_h * 0.25 <= height):
        return ""
    return (f'<p class="small dim">The map opens on part of the {len(spots)} spots; zoom out (−) or drag to see '
            f'the rest, open <a href="#detailed-coordinates">Detailed coordinates</a> below, or <a href="{href}">open '
            'the full map</a>.</p>')


def section_loot(site, m, w):
    spots = m["loot"].get(w["name"], [])
    out = [bar("Where to find it")]
    if not spots:
        out.append("<p>No copy of this weapon is placed by hand in the world files.</p>")
        out.append(crate_note(site))
        return out
    quals = sorted({s["q"] for s in spots})
    top = sorted(spots, key=lambda s: -s["q"])
    out.append(f"<p>The world files place {len(spots)} copies of the {esc(w['name'])} at fixed spots (on top of "
               "the random weapon crates). Each spot has a fixed quality; this table counts them by region.</p>")
    out.append(loot_counts_table(site, spots, quals))
    out.append(loot_minimap(top, 320))
    out.append(coords_fold(site, top))
    out.append(crate_note(site))
    return out


def crate_note(site):
    c = next((s["count"] for s in site.data("loot")["subs"] if s["key"] == "loot_c_weapon"), None)
    return note(f"Weapon boxes are random: the files have {fmt(c)} weapon box spawn points, and what a box holds "
                "is rolled by the game, so they can't be listed per weapon.", "data") if c else ""


def ammo_links(site, m, ammo):
    return ", ".join(site.link("ammo", ammo_name(m, a) or a["name"]) for a in ammo)


def section_related(site, m, w):
    """Ammo the weapon loads, weapons that load the same ammo items, same calibre family, same category.
    'Same ammo' compares internal names: the 9mm handgun rounds (*_01) and 9mm SMG rounds (*_02) are separate
    items even though stock.json files both under the '9mm' calibre."""
    out = [bar("Ammo and related weapons" if w["d"].get("ammo") else "Related weapons")]
    ammo = own_ammo(w)
    exp = [a for a in w["d"].get("ammo") or [] if a.get("experimental_only")]
    if ammo:
        out.append("<p>Ammo it loads: " + ammo_links(site, m, ammo) + ".</p>")
    if exp:
        lab = ("Experimental-only rounds (for the experimental version)" if 6 in w["quals"]
               else "Experimental-only rounds of this calibre (not usable by this weapon, which has no experimental "
                    "version)")
        out.append(f"<p>{lab}: " + ammo_links(site, m, exp) + ".</p>")
    mine = own_ammo_raws(w)
    same = [x for x in m["weapons"] if x is not w and own_ammo_raws(x) & mine]
    if same:
        out.append("<p>Other weapons that load the same ammo: "
                   + ", ".join(wlink(site, x, icon=False) for x in same) + ".</p>")
    for cal in w["calibres"]:
        if cal in GENERIC_SUBS:
            continue
        fam = [x for x in m["weapons"] if cal in x["calibres"] and x is not w and x not in same]
        if fam:
            out.append(f"<p>Same calibre family ({site.link('caliber', cal)}), different ammo items: "
                       + ", ".join(wlink(site, x, icon=False) for x in fam) + ".</p>")
    cat = [x for x in m["weapons"] if x["cat"] == w["cat"] and x is not w]
    if cat:
        out.append(f"<p>Other {esc(w['cat'].lower())}: " + ", ".join(wlink(site, x, icon=False) for x in cat)
                   + ".</p>")
    return out


# ---------------------------------------------------------------- throwables
def build_throwable(site, m, w):
    d = w["d"]
    st = m["stock"].get(w["internal"], {})
    body = [bar("Damage")]
    body.append("<p>A throwable has no quality: every grenade is the same. Its damage is a blast where it lands "
                "(and for the Molotov, fire that keeps burning).</p>")
    rows = []
    if d.get("blast"):
        b = d["blast"]
        rows.append(["Blast", b["damage_to_machines"], b["radius_vs_machines_m"], b["damage_to_players"],
                     b["radius_vs_players_m"]])
    body.append(table(["Effect", "vs machines", "Radius (m)", "vs players", "Radius (m)"], rows,
                      num={1, 2, 3, 4}, sortable=False))
    if d.get("fireball"):
        fb = d["fireball"]
        body.append("<h3>Fireball</h3><p>The files also give it a fireball projectile with these values:</p>")
        body.append(kv([("Damage / projectile", fmt(fb["projectile_damage"])),
                        ("Falloff", esc(fb["falloff"])), ("Range", f'{fmt(fb["max_range_m"])} m'),
                        ("Effects", effects(fb))]))
    if d.get("fire"):
        body.append("<h3>Fire on the ground</h3><ul>" + "".join(
            f"<li>{dot_text(x)}</li>" for x in d["fire"]["damage_over_time"]) + "</ul>")
        dots = d["fire"]["damage_over_time"]
        tot = dots[0]["damage_per_tick"] * dots[0]["duration_seconds"] / dots[0]["tick_seconds"]
        body.append(f"<p>Standing in the fire for its full {fmt(dots[0]['duration_seconds'])} seconds adds up to "
                    f"{fmt(tot)} damage per target on top of the blast.</p>")
    if d.get("blast") and d["blast"]["damage_to_machines"] == 0:
        body.append(note("The game files give the snowball's blast 0 damage: it hurts nothing.", "data"))
    sch = [x for x in site.data("schematics")["items"] if x["n"] == st.get("name", w["name"])]
    if sch:
        body.append(f"<p>It can be crafted with the {site.link('schematic', sch[0]['n'])} schematic "
                    f"({esc(sch[0]['r'])}).</p>")
    spots = m["loot"].get(w["name"], [])
    body.append(bar("Where to find it"))
    if spots:
        body.append(f"<p>The world files place {len(spots)} {esc(w['name'])} pick-ups at fixed spots:</p>")
        regs = [k for k, _ in REGIONS if any(s["region"] == k for s in spots)]
        body.append(table(["Region", "Placed"], [[site.link("region", r, text=REGION_NAME[r]),
                                                  sum(1 for s in spots if s["region"] == r)] for r in regs]
                          + [["<b>Total</b>", len(spots)]], num={1}, cls="compact"))
        body.append(loot_minimap(spots, 300))
        body.append(coords_fold(site, spots, quals=False))
    else:
        body.append("<p>No copies are placed by hand in the world files.</p>")
    others = [x for x in m["weapons"] if x["cat"] == "Throwables" and x is not w]
    body.append(bar("Related"))
    body.append("<p>Other throwables: " + ", ".join(wlink(site, x, icon=False) for x in others) + ".</p>")
    item = site.link("item", st.get("name", w["name"]), text=st.get("name", w["name"]))
    ib = infobox(w["name"], [("Category", "Throwable"), ("Pack", pack_tag(site, w["pack"])),
                             ("Stack size", fmt(st.get("stack"))), ("Item", item),
                             ("Placed in world", f'<a href="#where-to-find-it">{len(spots)}</a>' if spots else "None")],
                 image="~/" + w["icon"] if w["icon"] else None, subtitle="Throwable")
    side = [panel("Item ID", f'<table class="idtab"><tr><td>Item</td><td class="idv">{esc(st["h"])}</td></tr>'
                             "</table>", cls="wside")] if st.get("h") else []
    b = d.get("blast") or {}
    lead = (f"<p>The {esc(w['name'])} is a throwable {pack_label(w['pack'])[0] == 'Base game' and 'in the base game' or 'from the ' + esc(pack_label(w['pack'])[0])}. "
            f"Its blast does {fmt(b.get('damage_to_machines'))} damage to machines within "
            f"{fmt(b.get('radius_vs_machines_m'))} m.</p>")
    site.page(w["path"], w["name"], "".join(body), "weapons", sub="weapons",
              crumbs=[("All weapons", "~/weapons/index.html"), ("Throwables", "~/weapons/index.html#throwables")],
              desc=weapon_desc(w), infobox_html=ib, kind="Weapon · Throwable", lead=lead, head_extra=CSS, side=side)


# ---------------------------------------------------------------- weapons/experimental.html
def build_experimental(site, m):
    exp = [w for w in m["weapons"] if w["exp_name"]]
    placed_q = sorted({s["q"] for s in site.data("loot")["subs"] if s["main"] == "loot_weapons"})
    no_ov = [w for w in exp if not w["d"].get("experimental_ammo_overrides")]
    body = [bar("What makes a weapon experimental")]
    body.append("<p>Experimental is a sixth quality (6 crowns, pink badge) that only some weapons have. Each "
                "experimental weapon is a separate item with its own name and its own special behaviour – a railgun "
                "Pvg 90, flechette shotgun shells, an electric sledgehammer. In the game files it is the weapon's "
                "Q6 item, and for most of them it comes with its own ammo values that replace the normal ones when "
                "fired from it.</p>")
    m6 = sorted({w["mult"][6] for w in exp if 6 in w["mult"]})
    lower = [w for w in exp if w["mult"].get(6, 0) < w["mult"].get(5, 0)]
    facts = [f"<b>Damage multiplier</b>: ×{' to ×'.join(fmt(v) for v in m6)} at Experimental"
             + (", the same as Special for every weapon except the " + ", ".join(esc(w["name"]) for w in lower)
                + f" (Special ×{fmt(lower[0]['mult'][5])})" if lower else "") + ".",
             "<b>Augments</b>: experimental weapons take none.",
             "<b>Ammo</b>: a set of experimental-only rounds (listed below) is made for them."]
    if placed_q:
        facts.append(f"<b>Placed loot</b>: none. The hand-placed weapons in the world files go up to "
                     f"{QNAME[placed_q[-1]]}.")
    body.append("<ul>" + "".join(f"<li>{x}</li>" for x in facts) + "</ul>")
    rows = []
    for w in exp:
        ic = img(site, w["exp_icon"] or w["icon"], cls="wicon")
        rows.append([f'<span id="{w["slug"]}"></span>{ic}',
                     f'<a href="~/{w["path"]}#experimental">{esc(w["exp_name"])}</a>', wlink(site, w, icon=False),
                     esc(w["cat"]), exp_summary(m, w)])
    body.append(bar("Experimental weapons", f"{len(exp)}"))
    body.append("<p>Every weapon with an experimental version. The name opens the experimental section of the "
                "weapon's page, with its full ammo table.</p>")
    body.append(table(["", "Experimental", "Base weapon", "Category", "What the files change"], rows,
                      cls="compact exptab"))
    if no_ov:
        names = ", ".join(esc(w["name"]) for w in no_ov)
        body.append(note(f"{len(no_ov)} experimental weapons ({names}) have no ammo values of their own in the "
                         "extracted files: what makes them special lives elsewhere.", "data"))
    # experimental-only ammo: which rounds, and which experimental weapons have them in their ammo list
    xa = {}
    for w in m["weapons"]:
        for a in w["d"].get("ammo") or []:
            if a.get("experimental_only"):
                nm = ammo_name(m, a) or a["name"]
                e = xa.setdefault(nm, {"a": a, "cal": ammo_calibre(m, a), "w": []})
                if 6 in w["quals"] and w not in e["w"]:
                    e["w"].append(w)
    if xa:
        body.append(bar("Experimental-only ammo", f"{len(xa)}"))
        body.append("<p>The game files flag these rounds as experimental-only. The ammo pages have their full "
                    "stats; <b>Loaded by</b> lists the experimental weapons that have the round in their ammo "
                    "list.</p>")
        rows = [[ammo_cell(site, m, e["a"]).replace(" " + tag("Exp. only", "exp"), ""),
                 site.link("caliber", e["cal"], text=e["cal"]) if e["cal"] else "–",
                 ", ".join(f'<a href="~/{w["path"]}#experimental">{esc(w["exp_name"])}</a>' for w in e["w"])
                 or '<span class="dim">–</span>'] for nm, e in sorted(xa.items(), key=lambda kv: (kv[1]["cal"] or "", kv[0]))]
        body.append(table(["Ammo", "Calibre", "Loaded by"], rows, cls="compact"))
    ib = infobox("Experimental", [("Badge", qbadge(6)), ("Crowns", "6"), ("Weapons", fmt(len(exp))),
                                  ("Multiplier", " / ".join(f"×{fmt(v)}" for v in m6)), ("Augment slots", "None"),
                                  ("Placed in world", "None" if placed_q else None)],
                 image="~/img/crowns/6.png" if site.has_file("img/crowns/6.png") else None,
                 subtitle="Weapon quality 6", cls="expib")
    lead = (f"<p>{len(exp)} weapons have an experimental version: a sixth quality above Special with its own "
            "name and a special behaviour. This page lists them and what the game files change; each weapon's page "
            "has the full numbers.</p>")
    site.page(EXP_PAGE, "Experimental weapons", "".join(body), "weapons", sub="experimental", lead=lead,
              head_extra=CSS, crumbs=[("All weapons", "~/weapons/index.html")], infobox_html=ib,
              desc="Generation Zero experimental (Q6) weapons: which weapons have one, their multipliers, what the "
                   "files change and the experimental-only ammo.",
              search={"k": "Weapons", "w": "experimental q6 sixth quality"})


def exp_summary(m, w):
    """What the files say the experimental version changes, from its override names."""
    ov = w["d"].get("experimental_ammo_overrides") or []
    if not ov:
        return '<span class="dim">No separate values in the files</span>'
    kinds = sorted({mm.group(1) for a in ov for mm in [re.search(r"\(([^)]*)\)\s*$", ammo_display(m, a))] if mm})
    shots = [a for a in ov if "projectile_damage" in a]
    foreign = foreign_calibres(m, w, shots)
    if len(foreign) > 2:
        return f"Own values for {len(shots)} ammo types of {len(foreign)} other calibres"
    if kinds:
        return esc(", ".join(kinds)) + f" ammo ({len(ov)} entries)"
    if shots:
        return f"Own values for {len(shots)} ammo types"
    # blasts only (the sledgehammer): 'Electric discharge, charge level 1' ... -> names and number of levels
    base = sorted({re.sub(r",\s*charge level \d+$", "", a["name"]) for a in ov})
    levels = {mm.group(1) for a in ov for mm in [re.search(r"charge level (\d+)$", a["name"])] if mm}
    return esc(" and ".join(base)) + (f" at {len(levels)} charge levels" if levels else "")


# ---------------------------------------------------------------- weapons/skins.html
def pack_name(site, p, base):
    e = site.find("pack", str(p))
    if e:
        return f'<a href="~/{esc(e["path"])}">{esc(e["title"])}</a>'
    site.url("pack", str(p))   # records the missing target in the build report
    return "Base game" if p == base else "Other content pack"


def build_skins(site, m):
    sk = m["skins"]
    base = site.data("vanity")["base_pack"]
    weapons = [w for w in m["weapons"] if any(s["weapon"] is w for s in sk)]
    n_dlc = sum(1 for s in sk if s["dlc"])
    body = [bar("All skins", f"{len(sk)} skins")]
    n_l = sum(1 for s in sk if s["l"] == "L")
    n_u = sum(1 for s in sk if s["l"] == "U")
    body.append(f"<p>{len(sk)} skins for {len(weapons)} weapons: {n_dlc} come with DLC packs, {n_l} other skins "
                f"start locked and have to be earned in the game, and {n_u} start{'s' if n_u == 1 else ''} unlocked. A skin "
                "changes only the look of the weapon, never its stats. Many patterns are shared between weapons "
                "(the four “Graffiti Resistance” skins are different items for different guns), so each skin is a "
                "separate item.</p>")
    body.append('<div class="filterbar" data-for="skinlist"><input placeholder="Filter skins..." aria-label="Filter">'
                '<button class="chip on" data-g="d" data-f="*">All</button>'
                '<button class="chip" data-g="d" data-f="base">Not DLC</button>'
                '<button class="chip" data-g="d" data-f="dlc">DLC</button><span class="count"></span></div>')
    body.append('<div id="skinlist">')
    for w in weapons:
        ws = [s for s in sk if s["weapon"] is w]
        body.append(f'<h3 id="{w["slug"]}" class="skinh">{img(site, w["icon"], cls="wicon")}'
                    f'<a href="~/{w["path"]}">{esc(w["name"])}</a> <span class="dim">{len(ws)}</span></h3>')
        body.append('<div class="skingrid">')
        for s in ws:
            body.append(
                f'<div class="skin fitem" id="{s["anchor"]}" data-f="{"dlc" if s["dlc"] else "base"}" '
                f'data-w="{esc(w["name"])}">'
                f'{img(site, s["img"], s["name"], cls="")}<div><b>{esc(s["name"])}</b>'
                f' {status_tag(s)}<br>'
                f'<span class="small dim">Pack: {pack_name(site, s["pack"], base)}</span></div></div>')
        body.append("</div>")
    body.append("</div>")
    rows = [[img(site, s["img"], cls="aicon"), f'<a href="#{s["anchor"]}">{esc(s["name"])}</a>',
             wlink(site, s["weapon"], icon=False) if s["weapon"] else esc(s["sub_name"]),
             status_tag(s), pack_name(site, s["pack"], base)] for s in sk]
    body.append(fold("Skins table", "<p>The same skins as one sortable table.</p>"
                     + table(["", "Skin", "Weapon", "Status", "Pack"], rows, cls="compact"), open=False,
                     right=f"{len(sk)}"))
    body.append(note("<b>Status</b> is the unlock flag the game's vanity table carries for each skin: "
                     "<b>Starts unlocked</b> (every profile has it), <b>Starts locked</b> (you have to get it in "
                     "the game; the files don't say how), <b>DLC</b> (unlocked as soon as you own the pack) and "
                     "<b>DLC, earned</b> (starts locked even with the pack). “Pack” is the content pack the item "
                     "belongs to, which is not always the same thing: a skin can sit in a DLC's content pack and "
                     "still be flagged as starting unlocked. Weapons not listed here have no skins.", "data"))
    lead = "<p>Every weapon skin in the game files, grouped by weapon, with the pack it comes from.</p>"
    site.page("weapons/skins.html", "Weapon skins", "".join(body), "weapons", lead=lead, head_extra=CSS,
              crumbs=[("All weapons", "~/weapons/index.html")],
              desc="All Generation Zero weapon skins by weapon, with their DLC pack and unlock status.",
              search={"k": "Weapons", "w": "skins camo paint"})

