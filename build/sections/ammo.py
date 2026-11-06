"""Weapons tab: the ammo page (weapons/ammo.html), one page per calibre (weapons/ammo/<calibre>.html) with all of
its variants, and the attachments page (weapons/attachments.html).

Data used
  stats.json   player_weapons: per weapon the ammo it fires with damage, multipliers, falloff and range, plus the
               experimental weapons' ammo overrides
  stock.json   inventory items: every ammo type's name, internal name, calibre group ('sub'), stack size and icon
  IDs.json     item ids of ammo, attachments (with WPNCompat = the ToolIDs of the weapons they fit) and weapons
  icons.json   item id -> icon (attachments)
  schematics.json  ammo crafting schematics (cost, recipe, and the in-game PROPERTIES text of experimental ammo)
  loot.json    ammo crate counts and the attachments placed by hand in the world
  gamedata.json    schematic currencies and skills

Kinds registered: 'caliber' (stock.json sub -> its calibre page), 'ammo' (stock.json name -> its section on the
calibre page; aliases: internal name, item id), 'attachment' (IDs.json name -> its card on the attachments page).
Internal names and item ids are only search aliases; the pages don't print them.
"""
import math
import re

from wiki.site import (esc, slug, norm, fmt, table, bar, fold, panel, note, kv, cards, infobox, maplink, minimap,
                       qbadge, tag, REGIONS)

AMMO_PAGE = "weapons/ammo.html"
ATT_PAGE = "weapons/attachments.html"
HEAD = '<link rel="stylesheet" href="~/assets/ammo.css">'
HEAD_JS = HEAD + '<script src="~/assets/ammo.js" defer></script>'   # the All ammo filter hides empty groups
GROUPS = ("Launcher rounds", "Arrows", "Other ammo")   # ammo groups that are not one calibre


def cal_path(cal):
    """The calibre's own page: weapons/ammo/9mm.html, weapons/ammo/32-acp.html ..."""
    return f"weapons/ammo/{slug(cal)}.html"


def cal_title(cal):
    if cal in NINE_MM:                      # '9mm Handgun' -> '9mm ammo (Handgun)', like the game's item names
        return f"9mm ammo ({cal.split()[1]})"
    return f"{cal} ammo" if cal[0] in ".0123456789" else cal


# the handgun and the SMG 9mm rounds are separate items no gun shares, so they are two calibres (see site.split_9mm)
NINE_MM = ("9mm Handgun", "9mm SMG")

# calibres in the order the page shows them (stock.json 'sub' values); anything else found in the data goes last
CAL_ORDER = ["9mm Handgun", "9mm SMG", ".32 ACP", ".44", "5.56mm", "7.62mm", "9x39mm", ".243", ".270", ".50 BMG", "12ga",
             "Launcher rounds", "Arrows", "Other ammo"]
CAL_ALIASES = {  # extra spellings people search for / other files use
    "9mm Handgun": ["9mm", "9mm handgun ammo", "9mm pistol", "9x19mm"], "9mm SMG": ["9mm SMG ammo", "9mm submachine gun"], ".32 ACP": ["32 ACP", ".32"], ".44": [".44 Magnum", "44"],
    "5.56mm": ["5.56", "556"], "7.62mm": ["7.62", "762"], "9x39mm": ["9x39"], ".243": ["243"], ".270": ["270"],
    ".50 BMG": [".50", "50 BMG"], "12ga": ["12 gauge", "12G", "shotgun shells"],
    "Launcher rounds": ["Launchers", "Grenade launcher ammo", "Granat", "GLHE", "Recoilless"],
    "Arrows": ["Bow", "Arrow"], "Other ammo": ["Misc"],
}

# Ammo kinds, matched against the ammo name in this order (first match wins: 'Slug Corrosive' is corrosive).
KINDS = [
    ("medical", "Medical", ["Medical"]),
    ("radioactive", "Radioactive", ["Radioactive"]),
    ("corrosive", "Corrosive", ["Corrosive"]),
    ("heat", "HEAT", ["HEAT"]),
    ("shock", "Shock", ["Shock"]),
    ("tar", "Tar", ["Tar Ammo"]),
    ("he", "High-explosive", ["High-Explosive", "HE Cartridge"]),
    ("explosive", "Explosive", ["Explosive"]),
    ("emp", "EMP", ["EMP", "Electromagnetic"]),
    ("smoke", "Smoke", ["Smoke"]),
    ("flare", "Flare", ["Flare"]),
    ("chaff", "Chaff", ["Chaff"]),
    ("ap", "Armour-piercing", ["Armor-Piercing"]),
    ("hp", "Hollow-point", ["Hollow-Point"]),
    ("sp", "Soft-point", ["Soft-Point"]),
    ("fmj", "Full metal jacket", ["Full Metal Jacket", "FMJ"]),
    ("slug", "Slug", ["Slug"]),
    ("buck", "Buckshot", ["Buckshot"]),
    ("bird", "Birdshot", ["Birdshot"]),
    ("arrow", "Arrow", ["Standard Resistance Arrows"]),
    ("napalm", "Napalm", ["Napalm"]),
    ("battery", "Battery", ["Battery"]),
    ("repair", "Repair", ["Repair"]),
]
KIND_LABEL = {k: label for k, label, _ in KINDS}

# What each kind does, in plain words. Numbers are added from the data where the data has them; the experimental
# kinds also quote the game's own schematic text (schematics.json) on the ammo's card.
KIND_TEXT = {
    "fmj": "The standard round. It does the weapon's full damage to both armour plates and components, so it is "
           "the safe all-round choice when you don't know what you'll meet.",
    "ap": "Armour-piercing rounds put more of their damage into armour plates and less into the components "
          "underneath. Use them to strip armour off big machines, then switch to a component round for the parts "
          "you have exposed.",
    "hp": "Hollow-point rounds are the opposite of armour-piercing: less damage to armour plates, more to "
          "components. They shine on parts that are already exposed, like fuel tanks, optics and weapons.",
    "sp": "Soft-point is the hunting-rifle version of hollow-point: less damage to armour plates, more to "
          "components. A good first shot on an exposed weak spot.",
    "heat": "HEAT (high-explosive anti-tank) rounds do no damage at all to armour plates but double damage to "
            "components. Aim at components only; a shot that lands on armour is wasted.",
    "corrosive": "Corrosive rounds are the strongest bullet option against armour, at the cost of half damage to "
                 "components.",
    "medical": "Medical rounds do no damage. They release a healing pulse where they land, healing players in "
               "the area (useful in co-op: shoot at the ground next to a teammate).",
    "radioactive": "Radioactive rounds do no direct damage; their job is to blind machines.",
    "shock": "Shock rounds plant small electric devices where they hit; two devices close to each other form a "
             "damaging electric tether between them.",
    "tar": "Tar rounds slow down what they hit, and the slowing stacks with more hits.",
    "explosive": "Explosive rounds plant a small proximity bomb where they hit.",
    "he": "A high-explosive grenade. All of its damage comes from the blast, so aim at the ground under a machine "
          "or at a group, not at a single small part.",
    "emp": "An electromagnetic pulse that briefly knocks out machines caught in the blast radius. The blast "
           "itself does very little damage; use it to stop a big machine so you can aim at its components.",
    "smoke": "Creates a smoke screen. Machines cannot see you through the smoke, so it covers an escape, a "
             "revive or a reposition.",
    "flare": "Lights a flare where it lands. It does almost no damage.",
    "chaff": "A launcher round that exists as an inventory item.",
    "slug": "One heavy projectile per shell. It keeps its damage much further than pellets do.",
    "buck": "A spread of large pellets: a lot of damage per shell at close range, but it falls off quickly.",
    "bird": "A wide spread of many small pellets. It falls off quickly and has the shortest range, but the spread "
            "makes it easy to hit small, fast machines up close.",
    "arrow": "The plain arrow. Its damage depends on how far you draw the bow.",
    "napalm": "Fuel for the Resistance Flamethrower. It sets targets on fire; the damage comes over time.",
    "battery": "The power cell of the experimental Meusser, which turns the rifle into a charged laser.",
    "repair": "The refill for the Companion's repair tool.",
}

# Attachments: internal entity names (without the _qN quality suffix). The item table only has names and ids;
# these come from the Gen0 tools' attachment extractor (gen0-tools/extractor/source/gz_attachments.py).
ATT_INTERNAL = {
    "Red Dot x2 Sight": "equipment_sight_rifle_acog_2x_01",
    "1-4x Rifle Scope": "equipment_sight_rifle_scope_1-4x_24mm_01",
    "4-8x Rifle Scope": "equipment_sight_rifle_scope_4-8x_42mm_01",
    "6-12x Rifle Scope": "equipment_sight_rifle_scope_6-12x_32mm_01",
    "8-16x Sniper Rifle Scope": "equipment_sight_rifle_scope_8-16x_50mm_01",
    "1-4x Shotgun Scope": "equipment_sight_shotgun_scope_1-4x_20mm_01",
    "2-4x Handgun Scope": "equipment_sight_handgun_scope_2-4x_20mm_01",
    "2.7x RLG-7 Scope": "equipment_sight_launcher_soviet_scope_01",
    "3-Pin Makeshift Bow Sight": "equipment_sight_bow_resistance_01",
    "Low Light Vision Amplifier": "equipment_vision_module_nv",
    "IR Vision Processor": "equipment_vision_module_hv",
    "Object Penetrating Vision Modulator": "equipment_vision_module_xr",
    "Dual Mode Low Light / IR Module": "equipment_vision_module_hv_nv",
    "Dual Mode Low Light / OPV Module": "equipment_vision_module_nv_xr",
    "Dual Mode IR / OPV Module": "equipment_vision_module_hv_xr",
    "Full Vision Module": "equipment_vision_module_hv_nv_xr",
    "Handgun Compensator": "attachment_muzzle_compensator_handgun_01",
    "Submachine Gun Compensator": "attachment_muzzle_compensator_smg_01",
    "Machine Gun Compensator": "attachment_muzzle_compensator_machine_gun_01",
    "Handgun Silencer": "attachment_muzzle_silencer_handgun_01",
    "Shotgun Silencer": "attachment_muzzle_silencer_shotgun_01",
    "Submachine Gun Silencer": "attachment_muzzle_silencer_smg_01",
    "Assault Rifle Silencer": "attachment_muzzle_silencer_assault_01",
    "Rifle Silencer": "attachment_muzzle_silencer_hunting_01",
    "Machine Gun Silencer": "attachment_muzzle_silencer_machine_gun_01",
    "COM-10 Silencer": "attachment_muzzle_silencer_smg_us_01",
    "Submachine Gun Barrel Extension": "attachment_muzzle_extension_smg_01",
    "Assault Rifle Barrel Extension": "attachment_muzzle_extension_assault_01",
    "Shotgun Choke": "attachment_muzzle_choke_shotgun_01",
    "Automatgevär 4 Extended Magazine": "attachment_mag_extended_assault_762_01",
    "Automatgevär 5 Extended Magazine": "attachment_mag_extended_assault_556_01",
    "AI-76 Extended Magazine": "attachment_mag_extended_assault_762_02",
    "Kpist Extended Magazine": "attachment_mag_extended_smg_9mm_02",
    "HP5 Extended Magazine": "attachment_mag_extended_smg_9mm_01",
    "Möller PP Extended Magazine": "attachment_mag_extended_handgun_32acp_01",
    "Klaucke 17 Extended Magazine": "attachment_mag_extended_handgun_9mm_01",
    "Pvg 90 Extended Magazine": "attachment_mag_extended_sniper_50mm_01",
    "Kvm 59 Extended Mag": "attachment_mag_extended_machine_gun_762_01",
    "Kvm 89 Extended Mag": "attachment_mag_extended_machine_gun_556_01",
    "N16 Extended Mag": "attachment_mag_extended_assault_us_01",
    "N60 Extended Mag": "attachment_mag_extended_machine_gun_us_01",
    "N9 Extended Mag": "attachment_mag_extended_handgun_us_01",
    "COM-10 Extended Mag": "attachment_mag_extended_smg_us_01",
    "S21 Extended Mag": "attachment_mag_extended_rifle_sniper_us_01",
    "Large Flamethrower Tank": "attachment_mag_extended_flamethrower_resistance_01",
    "AT-WAD Extended Mag": "attachment_mag_extended_assault_soviet_01",
    "Kotenok Extended Mag": "attachment_mag_extended_sniper_soviet_01",
    "Vosa Extended Mag": "attachment_mag_extended_submach_soviet_01",
    "Volkov Extended Mag": "attachment_mag_extended_handgun_soviet_01",
    "Iron Condor Extended Mag": "attachment_mag_extended_handgun_us_03",
    "PM-71 Extended Mag": "attachment_mag_extended_machine_gun_soviet_01",
}

# IDs.json attachment categories -> (page section title, slot, short explanation)
ATT_CATS = {
    "Scopes": ("Scopes and sights", "Sight",
               "Scopes replace the iron sights and magnify the view by the power in their name: a 4-8x scope "
               "zooms between 4 and 8 times. Higher zoom helps at long range but narrows your view, so match "
               "the scope to the range you fight at. The bow sight and the RLG-7 scope are made for those "
               "weapons only."),
    "Vision Modules": ("Vision modules", "Vision module",
                       "Vision modules add vision modes to the weapon's sight. Low light amplifies what little "
                       "light there is (night vision), IR shows heat, so machines stand out against the cold "
                       "background, and the object penetrating mode shows machines through cover. The dual "
                       "and full modules combine two or all three modes in one item. They come in a single "
                       "quality only."),
    "Compensators": ("Compensators", "Muzzle",
                     "A compensator sits on the muzzle and redirects the gas from each shot to reduce recoil "
                     "and muzzle climb, so long bursts stay on target. It takes the muzzle slot, so you can't "
                     "use it together with a silencer."),
    "Silencer": ("Silencers", "Muzzle",
                 "A silencer makes your shots much quieter, so machines further away don't hear you fire. "
                 "That keeps a fight small and lets you pick off machines one at a time. It takes the muzzle "
                 "slot."),
    "Extensions": ("Barrel extensions and chokes", "Muzzle",
                   "A barrel extension lengthens the barrel and the shotgun choke narrows the shot pattern, so "
                   "pellets stay together further out. Both take the muzzle slot."),
    "Magazines": ("Extended magazines", "Magazine",
                  "An extended magazine holds more rounds than the standard one, so you reload less often. Each "
                  "magazine fits one weapon (the Large Flamethrower Tank is the flamethrower's version)."),
}

SUPPORT = ("medical", "radioactive", "flare", "smoke", "emp")   # rounds valued for an effect, not damage
_MODEL = {}   # id(site) -> model, so collect() and build() share the parsed data


# =================================================================================================================
# model
# =================================================================================================================
def kind_of(name):
    for k, _label, words in KINDS:
        if any(w in name for w in words):
            return k
    return "other"


def pack_tag(pack):
    """DLC tag for a weapon pack ('US Weapons Pack (DLC)' -> tag 'US Weapons Pack')."""
    if not pack or not pack.endswith("(DLC)"):
        return ""
    return tag(pack.replace(" (DLC)", ""), "dlc")


def stock_icon(entry):
    return (entry.get("icon") or "").replace("assets/", "img/", 1)


def model(site):
    if id(site) in _MODEL:
        return _MODEL[id(site)]
    m = {"weapons": [], "ammo": {}, "cal": {}, "att": [], "tool": {}}
    # every player weapon from stats.json (category, name, data)
    for cat, ws in site.data("stats")["player_weapons"].items():
        for name, d in ws.items():
            m["weapons"].append({"cat": cat, "name": name, "d": d,
                                 "exp": "Q6" in (d.get("qualities") or []),
                                 "qmul": d.get("damage_multiplier_by_quality") or {}})
    # every ammo item from stock.json
    ids_short = _ids_ammo_names(site)
    for e in site.data("stock")["stock"]:
        if e["g"] != "ammo":
            continue
        a = {"name": e["name"], "raw": e["raw"], "h": e["h"], "cal": e["sub"], "stack": e["stack"],
             "icon": stock_icon(e), "kind": kind_of(e["name"]), "uses": [], "overrides": [],
             "short": ids_short.get(str(e["h"])), "schem": None, "exp_only": e["raw"].endswith("_q6")}
        a["id"] = "ammo-" + slug(a["name"])
        m["ammo"][a["name"]] = a
        m["cal"].setdefault(a["cal"], []).append(a)
    by_raw = {a["raw"]: a for a in m["ammo"].values()}
    # which weapon fires which ammo, and the experimental weapons' versions of it
    for w in m["weapons"]:
        for e in w["d"].get("ammo") or []:
            a = by_raw.get(e["internal_name"])
            if a:
                a["uses"].append((w, e))
                if e.get("experimental_only"):
                    a["exp_only"] = True
        for e in w["d"].get("experimental_ammo_overrides") or []:
            a = _override_target(e, m["ammo"], by_raw)
            if a:
                a["overrides"].append((w, e))
    for a in m["ammo"].values():
        a["firers"] = _firers(a)
    # experimental weapons whose tuning has entries for other calibres' rounds (the AI-76): weapon name -> overrides
    m["cross"] = {}
    for w in m["weapons"]:
        own = {by_raw[e["internal_name"]]["cal"] for e in w["d"].get("ammo") or [] if e["internal_name"] in by_raw}
        cross = [(a, e) for a in m["ammo"].values() for ww, e in a["overrides"]
                 if ww is w and a["cal"] not in own and a["cal"] != "Other ammo"]
        if cross:
            m["cross"][w["name"]] = cross
    # crafting schematics (key 'schematic_<raw>' with an optional '_q1')
    for s in site.data("schematics")["items"]:
        raw = re.sub(r"_q1$", "", s["k"].replace("schematic_", "", 1))
        if raw in by_raw:
            by_raw[raw]["schem"] = s
    # calibre order
    m["cal_order"] = [c for c in CAL_ORDER if c in m["cal"]] + sorted(c for c in m["cal"] if c not in CAL_ORDER)
    for c in m["cal"]:
        m["cal"][c].sort(key=lambda a: (a["exp_only"], _kind_rank(a["kind"]), a["name"]))
    # attachments and the weapon ToolID table
    m["tool"] = _tool_ids(site, [w["name"] for w in m["weapons"]])
    icons = site.data("icons")
    for cat, items in site.data("IDs")["Attachments"].items():
        for name, d in items.items():
            quals = [q for q in "012345" if q in d]
            ic = icons.get(d[quals[0]]) if quals else None
            m["att"].append({"cat": cat, "name": name, "nick": d.get("Nickname"), "quals": quals,
                             "ids": {q: d[q] for q in quals}, "icon": "img/" + ic if ic else None,
                             "compat": [t.strip() for t in (d.get("WPNCompat") or "").split(",") if t.strip()],
                             "internal": ATT_INTERNAL.get(name), "id": "att-" + slug(name)})
    _MODEL[id(site)] = m
    return m


def exp_name(w):
    """Name of a weapon's experimental (Q6) version, e.g. 'Experimental Kvm 89'."""
    return w["d"].get("experimental_name") or f"Experimental {w['name']}"


def _firers(a):
    """Who can actually fire this round: [(weapon, label)]. A Q6-only round only works in a weapon that has an
    experimental version, so weapons without Q6 are dropped and the rest are named by their experimental version.
    Experimental weapons whose own tuning lists the round (experimental_ammo_overrides) are added."""
    out = []
    for w, _e in a["uses"]:
        if a["exp_only"] and not w["exp"]:
            continue
        out.append((w, exp_name(w) if a["exp_only"] else w["name"]))
    for w, _e in a["overrides"]:
        if all(w is not x for x, _ in out):
            out.append((w, exp_name(w)))
    return out


def _blast_round(a, e):
    """True for rounds whose damage is a blast, not the projectile (launcher rounds, explosive arrows)."""
    if not e:
        return False
    return a["cal"] == "Launcher rounds" or ((e.get("on_hit") or {}).get("blast") and
                                             (e.get("projectile_damage") or 0) <= 1)


def _kind_rank(k):
    order = [x[0] for x in KINDS]
    first = ["fmj", "ap", "hp", "sp", "slug", "buck", "bird", "arrow"]
    return first.index(k) if k in first else len(first) + order.index(k) if k in order else 99


def _ids_ammo_names(site):
    """item id (string) -> the short name IDs.json uses ('9mm FMJ'), for aliases."""
    out = {}
    for groups in site.data("IDs")["Ammo"].values():
        for names in groups.values():
            for short, h in names.items():
                out[h] = short
    return out


def _override_target(e, ammo, by_raw):
    """Which stock ammo an experimental-weapon override belongs to: by the name before ' (...)', by a stock
    internal name inside its internal name, or by the name in brackets ('Laser (High Voltage Battery Mag)')."""
    name = e["name"]
    base = re.sub(r"\s*\([^)]*\)\s*$", "", name)
    if base in ammo:
        return ammo[base]
    for raw in sorted(by_raw, key=len, reverse=True):
        if raw in e["internal_name"]:
            return by_raw[raw]
    inner = re.findall(r"\(([^)]*)\)", name)
    if inner and inner[-1] in ammo:
        return ammo[inner[-1]]
    if "batterymag" in e["internal_name"] or "overcharge" in e["internal_name"]:
        return ammo.get("High Voltage Battery Mag")
    return None


def _tool_ids(site, stats_names):
    """IDs.json weapon ToolID ('06') -> weapon name as in stats.json (IDs.json spells some differently)."""
    manual = {"Volkov Handgun": "Volkov Pistol"}
    out = {}
    for items in site.data("IDs")["Weapons"].values():
        for name, d in items.items():
            k = norm(name)
            hit = manual.get(name) or next((s for s in stats_names if norm(s) == k), None) \
                or next((s for s in stats_names if norm(s).startswith(k) or k.startswith(norm(s))), None) \
                or next((s for s in stats_names if k in norm(s)), None)
            out[d["ToolID"]] = {"name": hit or name, "ids_name": name, "nick": d.get("Nickname")}
    return out


# =================================================================================================================
# collect
# =================================================================================================================
def collect(site):
    m = model(site)
    for cal in m["cal_order"]:
        ammo = m["cal"][cal]
        users = sorted({w["name"] for a in ammo for w, _ in a["uses"]})
        site.register("caliber", cal, cal_path(cal), cal_title(cal),
                      icon=ammo[0]["icon"], aliases=CAL_ALIASES.get(cal, []),
                      desc=f"{len(ammo)} ammo types" + (f", used by {', '.join(users[:4])}" if users else ""),
                      keywords="ammo caliber calibre " + " ".join(a["name"] for a in ammo))
    short_count = {}
    for a in m["ammo"].values():
        short_count[a["short"]] = short_count.get(a["short"], 0) + 1
    for a in m["ammo"].values():
        aliases = [a["raw"], str(a["h"])]
        if a["short"] and short_count[a["short"]] == 1:   # '9mm FMJ' is both the handgun and the SMG round
            aliases.append(a["short"])
        if a["schem"]:
            aliases.append(a["schem"]["n"])
        for w, e in a["overrides"]:
            aliases.append(e["internal_name"])
        dmg = _first_damage(a)
        desc = f"{a['cal']} · {KIND_LABEL.get(a['kind'], 'Ammo')}" + (f" · {fmt(dmg)} damage" if dmg else "") + \
            (" · experimental only" if a["exp_only"] else "")
        site.register("ammo", a["name"], f"{cal_path(a['cal'])}#{a['id']}", a["name"], icon=a["icon"], desc=desc,
                      aliases=aliases, keywords=f"ammo {a['cal']} {a['kind']} {KIND_LABEL.get(a['kind'], '')}")
    for at in m["att"]:
        aliases = [at["nick"], at["internal"]] + list(at["ids"].values())
        if at["name"].endswith(" Mag"):
            aliases.append(at["name"] + "azine")          # loot.json says 'Kvm 89 Extended Magazine'
        if at["name"] == "Red Dot x2 Sight":
            aliases.append("2x Red Dot Scope")            # the name in the placed-loot list
        site.register("attachment", at["name"], f"{ATT_PAGE}#{at['id']}", at["name"], icon=at["icon"],
                      desc=f"{ATT_CATS[at['cat']][0]} · fits " + ", ".join(m["tool"][t]["name"] for t in at["compat"]
                                                                        if t in m["tool"])[:120],
                      aliases=[x for x in aliases if x], keywords=f"attachment {at['cat']} {at['nick'] or ''}")


def _first_damage(a):
    for _w, e in a["uses"]:
        if e.get("projectile_damage"):
            return e["projectile_damage"]
    return None


# =================================================================================================================
# formatting helpers
# =================================================================================================================
MEDICAL_PULSE = ("Pulse (listed as a blast in the files; for a medical round this is most likely the healing "
                 "amount)")


def _blast(b, medical=False):
    word = "vs machines" if medical else "damage to machines"
    parts = [f"{fmt(b['damage_to_machines'])} {word} within {fmt(b['radius_vs_machines_m'])} m"]
    if b.get("damage_to_players") or b.get("radius_vs_players_m"):
        parts.append(f"{fmt(b['damage_to_players'])} {'vs' if medical else 'to'} players within "
                     f"{fmt(b['radius_vs_players_m'])} m")
    return ", ".join(parts)


def rng(x):
    """Max range for display: whole metres (the files hold values like 1000.1)."""
    return round(x) if x else x


def falloff_text(e, w=None):
    """The falloff string; 'draw' becomes 'charge' for a weapon that is charged rather than drawn (the
    experimental Meusser's laser)."""
    f = e.get("falloff")
    if f and w is not None and "Bow" not in w["name"]:
        f = f.replace("undrawn", "uncharged").replace("drawn", "charged").replace("draw", "charge")
    return f


def override_name(a, e):
    """Display name of an experimental override. Some entries are named by an internal name
    ('equipment_ammo_12ga_bird_01_exp (Dragon's Breath)'): show the stock name of that round instead."""
    if e["name"].startswith("equipment_ammo_"):
        inner = re.findall(r"\(([^)]*)\)", e["name"])
        return a["name"] + (f" ({inner[-1]})" if inner else "")
    return e["name"]


def _dot(d):
    return (f"{fmt(d['damage_per_tick'])} damage every {fmt(d['tick_seconds'])} s for {fmt(d['duration_seconds'])} s "
            f"(to {esc(d['target'])})")


def on_hit_html(e, medical=False):
    """Readable text for a projectile's on_hit / blast data (or '' when it has none). For a medical round the
    'blast' is labelled as a pulse: the files list it as a blast, but a medical round does no damage."""
    out = []
    oh = e.get("on_hit") or {}
    if e.get("blast"):
        out.append((MEDICAL_PULSE if medical else "Blast") + ": " + _blast(e["blast"], medical))
    if oh.get("blast"):
        out.append((MEDICAL_PULSE if medical else "Blast on impact") + ": " + _blast(oh["blast"], medical))
    if oh.get("heal_pulse"):
        h = oh["heal_pulse"]
        out.append(f"Healing pulse: {fmt(h['damage_to_players'])} health within {fmt(h['radius_vs_players_m'])} m")
    for d in oh.get("damage_over_time") or []:
        out.append("Damage over time: " + _dot(d))
    return "; ".join(out)


def stages_table(stages, medical=False):
    """on_hit_stages: a stronger blast once a requirement (bow draw / time in flight) is met."""
    rows = []
    for s in stages:
        req = s.get("requirement") or {}
        if "charge" in req:
            r = f"Bow drawn at least {req['charge'] * 100:.0f}%"
        elif "lifetime" in req:
            r = f"Round in flight at least {fmt(req['lifetime'])} s"
        else:
            r = esc(", ".join(f"{k} {v}" for k, v in req.items()))
        b = s.get("blast") or {}
        rows.append([r, b.get("damage_to_machines"), b.get("radius_vs_machines_m"), b.get("damage_to_players"),
                     b.get("radius_vs_players_m")])
    word = "Amount vs" if medical else "Damage to"
    return table(["Requirement", f"{word} machines", "Radius (m)", f"{word} players", "Radius vs players (m)"],
                 rows, cls="compact", sortable=False)


# A cell can carry its own sort value: put SORTV.format(value) at the start of the cell and run the table HTML
# through sortv_cells(), which moves it onto the <td> as data-v (what wiki.js sorts on).
SORTV = '<i data-sortv="{}"></i>'


def sortv_cells(html):
    return re.sub(r'<td( class="n")?><i data-sortv="([^"]*)"></i>', r'<td\1 data-v="\2">', html)


def mult_html(x):
    """A multiplier with a colour hint: above 1 is good, below 1 bad, 0 is none at all."""
    if x is None:
        return "–"
    cls = "mup" if x > 1 else "mdown" if x < 1 else ""
    return f'<span class="mult {cls}">×{fmt(x)}</span>'


def schem_html(site, s):
    """Schematic link with its cost and recipe."""
    if not s:
        return ""
    cur = next((c for c in site.data("gamedata")["schematics"] if c["key"] == _schem_tree(s)), None)
    cost = ""
    if cur and s.get("c") is not None:
        ic = site.img(cur["icon"].replace("assets/", "img/", 1), alt="", cls="cur", title=cur["name"])
        unit = re.sub(r"Points\b", "Point", cur["name"]) if s["c"] == 1 else cur["name"]
        cost = " · free" if s["c"] == 0 else f" · costs {fmt(s['c'])} {ic}{esc(unit)}"
    return f"{site.link('schematic', s['n'])}{cost}<br><span class=\"dim\">Recipe per craft: {esc(s.get('r') or '–')}</span>"


def _schem_tree(s):
    return {"ammo": "ammo", "experimental": "experimental", "dlc": "dlc", "equipment": "equipment"}.get(s["t"], s["t"])


def schem_properties(s):
    """The PROPERTIES part of an experimental schematic's in-game description."""
    if not s or "PROPERTIES:" not in (s.get("d") or ""):
        return ""
    return s["d"].split("PROPERTIES:", 1)[1].strip().lstrip("- ").strip()


def weapon_link(site, w, text=None):
    return site.link("weapon", w["name"], text=text)


def firers_html(site, m, a, chips=True):
    """'Fired by' links (with weapon icons when chips). A weapon that only lists the round in its tuning for other
    calibres (the AI-76) gets a '*' pointing to the note that explains it (on the calibre page)."""
    def star(w):
        return (' <a class="dim star" href="#cross-calibre" title="Why does this weapon list other calibres?">*</a>'
                if w["name"] in m["cross"] and any(x is a for x, _ in m["cross"][w["name"]]) else "")
    if not a["firers"]:
        return ""
    if chips:
        return wchips(site, a["firers"], star=star)
    return ", ".join(weapon_link(site, w, text=label) + star(w) for w, label in a["firers"])


def shots(hp, per_hit):
    if not per_hit:
        return "never"
    return math.ceil(round(hp / per_hit, 6))


# =================================================================================================================
# the ammo page (weapons/ammo.html)
# =================================================================================================================
def build(site):
    m = model(site)
    build_ammo(site, m)
    for cal in m["cal_order"]:
        build_caliber(site, m, cal)
    build_attachments(site, m)


def _users(ammo):
    """The weapons that fire any round of this list (in data order), from the normal weapon tuning."""
    out = []
    for a in ammo:
        for w, _ in a["uses"]:
            if all(w is not x for x in out):
                out.append(w)
    return out


def _loot_sub(site, key):
    return next((s for s in site.data("loot")["subs"] if s["key"] == key), None)


def _marker_count(site, key):
    return next((s.get("count") for s in site.data("markers")["subs"] if s["key"] == key), None)


def _currency(site, key):
    return next((c for c in site.data("gamedata")["schematics"] if c["key"] == key), None)


def build_ammo(site, m):
    body = [section_summary(site, m), section_guide(site, m), section_finding(site, m), section_tips(site, m),
            section_table(site, m), section_shots(site, m)]
    lead = (f"<p>Generation Zero has {len(m['ammo'])} kinds of ammunition in {len(m['cal_order'])} calibre groups. "
            "Every calibre has its own page with all of its variants (full metal jacket, armour-piercing, "
            "hollow-point, the experimental rounds and so on), the damage each one does from every weapon that fires "
            "it, and how to craft it. This page compares them and explains how to choose.</p>")
    site.page(AMMO_PAGE, "Ammo", "\n".join(body), "weapons", sub="ammo", head_extra=HEAD_JS, lead=lead,
              infobox_html=ammo_infobox(site, m),
              desc="All Generation Zero ammo: every calibre and variant, how to choose between them, where to find "
                   "ammo, and damage compared.",
              search={"k": "Weapons", "w": "ammo ammunition calibre caliber damage armour component"})


def ammo_infobox(site, m):
    ammo = list(m["ammo"].values())
    n_exp = sum(1 for a in ammo if a["exp_only"])
    n_craft = sum(1 for a in ammo if a["schem"])
    boxes = _loot_sub(site, "loot_c_ammo")
    pic = m["ammo"].get("7.62mm Full Metal Jacket Ammo") or ammo[0]
    rows = [("Ammo items", fmt(len(ammo))), ("Calibre groups", f'<a href="#summary">{len(m["cal_order"])}</a>'),
            ("Experimental only", fmt(n_exp)), ("Craftable", f"{n_craft} of {len(ammo)}"),
            ("Ammo box spots", f'<a href="#finding">{fmt(boxes["count"])}</a>' if boxes else None)]
    img = "~/" + pic["icon"] if site.has_file(pic["icon"]) else None
    return infobox("Ammo", rows, image=img, image_alt=pic["name"], subtitle="Ammunition for the player's weapons")


def section_summary(site, m):
    """Cards to the calibre pages, then the calibre x role grid."""
    items = []
    for cal in m["cal_order"]:
        ammo = m["cal"][cal]
        names = [w["name"] for w in _users(ammo)]
        n_exp = sum(1 for a in ammo if a["exp_only"])
        sub = f"{len(ammo)} variant{'s' if len(ammo) != 1 else ''}" + (f", {n_exp} experimental" if n_exp else "")
        if names:
            sub += "<br>" + esc(", ".join(names[:3])) + (f" +{len(names) - 3}" if len(names) > 3 else "")
        icon = ammo[0]["icon"]
        items.append({"href": "~/" + cal_path(cal), "title": cal_title(cal), "sub": sub,
                      "img": "~/" + icon if site.has_file(icon) else None})
    return (bar("Summary", id="summary") +
            "<p>Pick a calibre to see all of its variants, the damage they do from each weapon and how to craft "
            "them.</p>" + cards(items, cls="calcards") + section_matrix(site, m))


def section_guide(site, m):
    """How to choose ammo: the armour vs components idea, and every multiplier pair in the data."""
    combos = {}   # (kind, armour x, component x) -> rounds, in page order
    for cal in m["cal_order"]:
        if cal == "Launcher rounds":       # blast rounds: their projectile multipliers mean nothing
            continue
        for a in m["cal"][cal]:
            if not a["uses"] or a["kind"] == "napalm" or _blast_round(a, a["uses"][0][1]):
                continue
            e = a["uses"][0][1]
            combos.setdefault((a["kind"], e.get("armour_multiplier"), e.get("component_multiplier")), []).append(a)
    rows = []
    for (k, am, cm), ams in sorted(combos.items(), key=lambda x: (_kind_rank(x[0][0]), -(x[0][1] or 0))):
        cals, links = [], []
        for a in ams:
            if a["cal"] not in cals:
                cals.append(a["cal"])
                links.append(site.link("ammo", a["name"], text=a["cal"]))
        rows.append([esc(KIND_LABEL.get(k, k)), mult_html(am), mult_html(cm), ", ".join(links),
                     esc(_role(am, cm, k))])
    skills = " and ".join(site.link("skill", s) for s in ("Armor Damage", "Component Damage"))
    others = ", ".join(site.link("caliber", c, text=cal_title(c)) for c in ("Launcher rounds", "Arrows", "Other ammo")
                       if c in m["cal"])
    return (bar("Choosing ammo", id="choosing") +
            "<p>Machines in Generation Zero are built from two kinds of parts. <b>Armour plates</b> cover the "
            "body and have to be shot off before you can reach what is under them. <b>Components</b> are the "
            "working parts: weapons, optics, fuel tanks, engine drives and so on. Destroying components is what "
            "disarms and kills a machine (components you leave whole can be looted from the wreck afterwards, "
            f"see the {site.link('skill', 'Mechanic')} skill). Every round has two multipliers that decide "
            "how much of its damage goes into each:</p>"
            "<ul><li><b>Armour ×</b>: damage to armour plates = projectile damage × this.</li>"
            "<li><b>Component ×</b>: damage to components = projectile damage × this.</li></ul>"
            "<p>So the usual plan is: armour-piercing (or corrosive) to break the plates over the part you want, "
            "then a component round (hollow-point, soft-point or HEAT) into the part itself. Against small "
            "machines with thin armour and exposed parts (Runners, Seekers, Ticks) a component round is usually "
            f"the better choice from the start. The {skills} skills add a further +5% / +10% on top.</p>"
            "<p>The table lists every armour / component pair that appears in the game files and the calibres "
            "that have it. Green multipliers are better than standard, red ones worse. The special rounds "
            "(shock, tar, explosive, radioactive) keep ×1 / ×1: their value is the effect, not the "
            "multiplier.</p>" +
            table(["Ammo type", "Armour ×", "Component ×", "Calibres", "Best for"], rows, cls="compact") +
            note("Launcher rounds, explosive arrows and napalm do their work with a blast or with fire instead of "
                 f"the projectile, so they are left out of this table; their numbers are on their pages: {others}.",
                 "info"))


def _cross_note(site, m, cal):
    """Explain the experimental weapon(s) whose tuning has entries for other calibres' rounds (the AI-76)."""
    out = []
    for name, pairs in m["cross"].items():
        if not any(a["cal"] == cal for a, _ in pairs):
            continue
        w = next(x for x in m["weapons"] if x["name"] == name)
        cals = [c for c in m["cal_order"] if any(a["cal"] == c for a, _ in pairs)]
        exp = site.link("weapon", exp_name(w)) if site.find("weapon", exp_name(w)) else \
            weapon_link(site, w, text=exp_name(w))
        out.append(f"The {exp}'s tuning has entries for the rounds of other calibres as well as its own: "
                   f"{len(pairs)} in the files, covering {', '.join(esc(c) for c in cals)}. In other words it is "
                   "set up to fire other calibres' ammo. It is listed under “Fired by” on those rounds (marked *)"
                   + (", and where its numbers differ from the normal round they are in "
                      "<a href=\"#in-experimental-weapons\">In experimental weapons</a>"
                      if any(not _same_as_base(a, e) for a, e in pairs if a["cal"] == cal) else "") + ".")
    if not out:
        return ""
    return f'<div id="cross-calibre">{note(" ".join(out), "data", "Rounds of other calibres")}</div>'


def _role(am, cm, kind):
    if kind == "medical":
        return "Healing teammates (no damage)"
    if kind in ("radioactive", "flare"):
        return "Effect only"
    if am is None or cm is None:
        return ""
    if am == 0:
        return "Exposed components only (useless on armour)"
    if am > cm:
        return "Stripping armour plates"
    if cm > am:
        return "Components / weak spots"
    return "All-round"


def section_matrix(site, m):
    """Calibre x role grid: what each calibre offers for armour, components, all-round and specials."""
    cols = [("Support / effect / blast",                                      # checked first, shown last
             lambda a, am, cm: a["kind"] in SUPPORT or _blast_round(a, a["uses"][0][1])),
            ("All-round", lambda a, am, cm: am == cm),
            ("Anti-armour", lambda a, am, cm: am > cm),
            ("Anti-component", lambda a, am, cm: cm > am)]
    rows = []
    for cal in m["cal_order"]:
        if cal in ("Launcher rounds", "Other ammo"):
            continue
        cells = [[] for _ in cols]
        split = len({_group_label([a]) for a in m["cal"][cal]}) > 1     # 9mm: handgun and SMG rounds
        for a in m["cal"][cal]:
            if not a["uses"]:
                continue
            e = a["uses"][0][1]
            am, cm = e.get("armour_multiplier", 1), e.get("component_multiplier", 1)
            for i, (_label, test) in enumerate(cols):
                if test(a, am, cm):
                    lab = KIND_LABEL.get(a["kind"], a["kind"])
                    if _blast_round(a, e):
                        lab += " (blast)"
                    if split and _group_label([a]):
                        lab += " (" + _group_label([a]).split()[0].replace("Handgun", "handgun") + ")"
                    cells[i].append(site.link("ammo", a["name"], text=lab) +
                                    (' <span class="xq" title="Experimental only">Q6</span>' if a["exp_only"] else ""))
                    break
        cells = cells[1:] + cells[:1]       # support column last
        rows.append([f"<b>{site.link('caliber', cal, text=cal)}</b>"] + ["<br>".join(c) or "–" for c in cells])
    return ("<h3>What each calibre offers</h3>"
            "<p>The variants of each calibre by role. A <span class=\"xq\">Q6</span> mark means the round only "
            "works in experimental weapons.</p>" +
            table(["Calibre"] + [c[0] for c in cols[1:] + cols[:1]], rows, cls="matrix", sortable=False))


def _all_ammo_rows(site, m, cal):
    """[(filter tags, row)] of one calibre for the All ammo tables."""
    out = []
    for a in m["cal"][cal]:
        e = a["uses"][0][1] if a["uses"] else {}
        dmg, pel = e.get("projectile_damage"), e.get("projectiles_per_shot") or 1
        am, cm = e.get("armour_multiplier"), e.get("component_multiplier")
        per_shot = dmg * pel if dmg is not None else None
        if _blast_round(a, e):
            # the projectile does (next to) nothing: show the blast, leave the projectile columns empty
            b = (e.get("on_hit") or {}).get("blast")
            dmg_cell = (f'{SORTV.format(b["damage_to_machines"])}{fmt(b["damage_to_machines"])} blast · '
                        f'{fmt(b["radius_vs_machines_m"])} m' if b else "–")
            mults = ["–"] * 4
        else:
            dmg_cell = ((f'{SORTV.format(dmg)}{pel} × {fmt(dmg)}' if pel > 1 else dmg)
                        if dmg is not None else None)
            mults = [mult_html(am) if e else "–", mult_html(cm) if e else "–",
                     round(per_shot * am, 2) if per_shot is not None and am is not None else None,
                     round(per_shot * cm, 2) if per_shot is not None and cm is not None else None]
        w0 = a["uses"][0][0] if a["uses"] else None
        out.append(("exp" if a["exp_only"] else "std", [
            site.link("ammo", a["name"], icon=True), esc(KIND_LABEL.get(a["kind"], "–")), dmg_cell] + mults + [
            esc(falloff_text(e, w0) or "–"), rng(e.get("max_range_m")), a["stack"], len(a["firers"]),
            tag("Q6 only", "exp") if a["exp_only"] else ""]))
    return out


def _rows_with_tags(html, rows):
    """table() has no row attributes: add data-f to each body row."""
    parts = html.split("<tr>")
    out = parts[0] + "<tr>" + parts[1]
    for (f, _), p in zip(rows, parts[2:]):
        out += f'<tr data-f="{f}">' + p
    return out


def section_table(site, m):
    """Every ammo item, one closed fold (with a sortable table) per calibre."""
    heads = ["Ammo", "Type", "Damage", "Armour ×", "Comp. ×", "vs armour / shot", "vs comp. / shot", "Falloff",
             "Range (m)", "Stack", "Weapons", ""]
    folds, total = [], 0
    for cal in m["cal_order"]:
        rows = _all_ammo_rows(site, m, cal)
        total += len(rows)
        html = _rows_with_tags(sortv_cells(table(heads, [r for _, r in rows], num={2, 5, 6, 8, 9, 10},
                                                 cls="compact")), rows)
        page = site.link("caliber", cal, text=f"the {cal_title(cal)} page")
        folds.append(fold(cal_title(cal), f'<p class="small">Everything about these rounds is on {page}.</p>' + html,
                          level=3, right=f"{len(rows)} item{'s' if len(rows) != 1 else ''}", id=f"all-{slug(cal)}"))
    body = ("<p>One row per ammo item, grouped by calibre. <b>Damage</b> is the base damage of one projectile "
            "(pellet) at weapon multiplier 1.0, which is Q5 for most weapons (each calibre page has every weapon's "
            "own numbers per quality); shotgun shells show pellets × damage. <b>vs armour / shot</b> and <b>vs "
            "comp. / shot</b> multiply that by the pellets and the armour or component multiplier. For launcher "
            "rounds and explosive arrows the damage is the blast instead (damage to machines and its radius; for "
            "the arrow the weakest, undrawn stage), and the projectile columns are left empty because the "
            "projectile itself does no real damage. <b>Weapons</b> counts the weapons that can fire the round (for "
            "Q6-only rounds, the experimental versions). Typing in the filter opens the groups that match; click a header to "
            "sort.</p>" +
            '<div class="filterbar" data-for="ammotable"><input placeholder="Filter ammo...">'
            '<button class="chip on" data-g="x" data-f="*">Any</button>'
            '<button class="chip" data-g="x" data-f="std">Standard</button>'
            '<button class="chip" data-g="x" data-f="exp">Experimental only</button><span class="count"></span></div>'
            '<div class="foldall" data-for="ammotable"></div>'
            f'<div id="ammotable" class="ammotable">{"".join(folds)}</div>')
    return fold("All ammo", body, open=False, right=f"{total} items", id="all-ammo")


def _part(site, cls, mtype, comp, kind):
    """Health of one named part of a Swedish machine's first layout (None when the data has no such part)."""
    try:
        lay = site.data("stats")["machine_health"]["Swedish"][cls]["types"][mtype]["layouts"]["Layout 1"]
    except KeyError:
        return None
    for c in lay["components"]:
        if c["component"] == comp and c["type"] == kind:
            return c["health_each"]
    return None


def section_shots(site, m):
    """A worked example: hits needed to break a few common parts with each round."""
    targets = [("Military", "Hunter", "Hull", "armour"), ("Military", "Hunter", "Fuel Tank", "component"),
               ("Military", "Harvester", "Plate", "armour"), ("Military", "Tank", "Fuel Tank", "component")]
    targets = [(c, t, p, k, _part(site, c, t, p, k)) for c, t, p, k in targets]
    targets = [x for x in targets if x[4]]
    # short two-line headers (machine / part) with the full name as a tooltip; the legend under the table spells
    # them out with links, so the columns stay narrow
    def full(c, t, p, k, hp):
        return f"{c} {t} {p.lower()} ({k}), {fmt(hp)} hp"
    heads = [f'<abbr title="{esc(full(*x))}">{esc(x[1])}<br>{esc(x[2].lower())}</abbr>' for x in targets]
    legend = ("; ".join(f"<b>{esc(t)} {esc(p.lower())}</b>: {site.link('machine', t)} ({esc(c)}) "
                        f"{esc(p.lower())}, {'armour' if k == 'armour' else 'component'}, {fmt(hp)} hp"
                        for c, t, p, k, hp in targets))
    rows = []
    for cal in m["cal_order"]:
        for a in m["cal"][cal]:
            if not a["uses"]:
                continue
            e = a["uses"][0][1]
            dmg = (e.get("projectile_damage") or 0) * (e.get("projectiles_per_shot") or 1)
            if dmg <= 1 or cal in ("Launcher rounds", "Other ammo"):   # flare / explosive arrows: effect only
                continue
            am, cm = e.get("armour_multiplier", 1), e.get("component_multiplier", 1)
            row = [site.link("ammo", a["name"]) + (" " + tag("Q6", "exp") if a["exp_only"] else ""),
                   round(dmg * am, 2), round(dmg * cm, 2)]
            for _c, _t, _p, k, hp in targets:
                row.append(shots(hp, dmg * (am if k == "armour" else cm)))
            rows.append(row)
    body = ("<p>A worked example to compare rounds: the number of hits needed to break one part, using the "
            "base damage (weapon multiplier 1.0, Q5 for most weapons), before difficulty scaling, with no skills "
            "and no augments. Shotgun rows count whole shells with every pellet hitting. The part health comes "
            "from the machines' layout files (first layout of each machine). Treat it as a comparison, not an "
            "exact promise: weak-spot bonuses, falloff, difficulty and co-op scaling all change the real count.</p>"
            '<div class="ammotable">' +
            table(["Ammo", '<abbr title="Damage per shot against armour">Armour</abbr>',
                   '<abbr title="Damage per shot against components">Comp.</abbr>'] + heads, rows, raw_headers=True,
                  num=set(range(1, 3 + len(heads))), cls="compact hits") + "</div>" +
            '<p class="small hitkey"><b>Armour</b> / <b>Comp.</b>: damage per shot against armour / components. '
            f"The other columns are hits to break that part: {legend}.</p>" +
            note("“never” means the round does no damage to that kind of part: HEAT ammo has an armour "
                 "multiplier of 0, so it cannot break armour plates at all.", "info"))
    return fold("How many hits?", body, open=False, right=f"{len(rows)} rounds", id="hits")


def _weapon_q5(w):
    return w["qmul"].get("Q5", 1)


def section_tips(site, m):
    """Practical tips computed from the numbers (so they stay right when the data changes)."""
    A = m["ammo"]
    tips = []

    def e0(name):
        a = A.get(name)
        return a["uses"][0][1] if a and a["uses"] else None

    ap, fmj = e0("7.62mm Armor-Piercing Ammo"), e0("7.62mm Full Metal Jacket Ammo")
    if ap and fmj:
        tips.append(f"Armour-piercing puts ×{fmt(ap['armour_multiplier'])} into armour and ×"
                    f"{fmt(ap['component_multiplier'])} into components. A plate that takes 5 FMJ hits takes "
                    f"{math.ceil(5 / ap['armour_multiplier'])} with AP; on a component AP costs you about "
                    f"{(1 - ap['component_multiplier']) * 100:.0f}% of your damage. Switch ammo once the plate is "
                    "off.")
    b_ap, b_fmj = e0(".50 BMG Armor-Piercing Ammo"), e0(".50 BMG Full Metal Jacket Ammo")
    if b_ap and b_fmj:
        tips.append(f"The {site.link('caliber', '.50 BMG', text='.50 BMG')} rounds are special: AP has armour "
                    f"×{fmt(b_ap['armour_multiplier'])} (the highest of any bullet) and even the FMJ has component "
                    f"×{fmt(b_fmj['component_multiplier'])}. With {fmt(b_ap['projectile_damage'])} base damage and "
                    f"falloff “{esc(b_ap['falloff'])}”, a {site.link('weapon', 'Pansarvärnsgevär 90')} with AP does "
                    f"{fmt(b_ap['projectile_damage'] * b_ap['armour_multiplier'])} damage to armour per shot.")
    # 7.62mm in different weapons: the weapon's quality multiplier makes a big difference
    users = sorted(A["7.62mm Full Metal Jacket Ammo"]["uses"], key=lambda u: -_weapon_q5(u[0])) \
        if "7.62mm Full Metal Jacket Ammo" in A else []
    if users and _weapon_q5(users[0][0]) != _weapon_q5(users[-1][0]):
        base = users[0][1]["projectile_damage"]
        best = [f"{weapon_link(site, w)} ({fmt(base * _weapon_q5(w))})" for w, _ in users if _weapon_q5(w) > 1]
        tips.append(f"The same 7.62mm round hits harder from some guns: its base damage is {fmt(base)}, but at "
                    f"Q5 it does {', '.join(best)} per hit, because those weapons have higher quality "
                    f"multipliers. The {site.link('caliber', '7.62mm', text='7.62mm page')} shows every weapon's "
                    "numbers.")
    tips += _q6_drop_tips(site, m)
    buck, bird, slug_ = e0("12ga Buckshot Ammo"), e0("12ga Birdshot Ammo"), e0("12ga Slug Ammo")
    if buck and bird and slug_:
        tips.append(f"Shotgun shells: buckshot fires {buck['projectiles_per_shot']} × {fmt(buck['projectile_damage'])}"
                    f" = {fmt(buck['projectiles_per_shot'] * buck['projectile_damage'])} damage, birdshot "
                    f"{bird['projectiles_per_shot']} × {fmt(bird['projectile_damage'])} = "
                    f"{fmt(bird['projectiles_per_shot'] * bird['projectile_damage'])}, a slug "
                    f"{fmt(slug_['projectile_damage'])}. But pellets fall off fast ({esc(buck['falloff'])}, "
                    f"{fmt(buck['max_range_m'])} m max) while a slug keeps going ({esc(slug_['falloff'])}, "
                    f"{fmt(slug_['max_range_m'])} m max). Pellets up close, slugs past a few dozen metres.")
    # launchers: compare blast damage per round
    blasts = []
    for a in m["cal"].get("Launcher rounds", []):
        for w, e in a["uses"][:1]:
            b = (e.get("on_hit") or {}).get("blast")
            if b and b["damage_to_machines"] >= 100:
                blasts.append((b["damage_to_machines"], b["radius_vs_machines_m"], a, w))
    if blasts:
        blasts.sort(key=lambda x: -x[0])
        tips.append("Launcher rounds by blast damage to machines: " + "; ".join(
            f"{site.link('ammo', a['name'])} {fmt(d)} within {fmt(r)} m" for d, r, a, w in blasts) +
            f". They stack only {fmt(blasts[0][2]['stack'])} per slot, so save them for the big machines.")
    med = [(a, (a["uses"][0][1].get("on_hit") or {}).get("heal_pulse")) for a in A.values()
           if a["kind"] == "medical" and a["uses"]]
    med = [(a, h) for a, h in med if h]
    if med:
        med.sort(key=lambda x: x[1]["damage_to_players"])
        tips.append("Medical rounds heal more the bigger the calibre: " + ", ".join(
            f"{site.link('ammo', a['name'], text=a['cal'])} {fmt(h['damage_to_players'])} within "
            f"{fmt(h['radius_vs_players_m'])} m" for a, h in med) + ".")
    tips.append(f"Running low? The {site.link('skill', 'Salvage')} skill gives +50% / +100% ammo from containers "
                f"and destroyed machines, and the {site.link('item', 'Ammo Pack')} refills you and your team.")
    return bar("Tips from the numbers", id="tips") + "<ul>" + "".join(f"<li>{t}</li>" for t in tips) + "</ul>"


def _q6_drop_tips(site, m):
    """Weapons whose experimental (Q6) multiplier is lower than their Q5 one (the Kvm 89)."""
    out = []
    for w in m["weapons"]:
        q5, q6 = w["qmul"].get("Q5"), w["qmul"].get("Q6")
        if not (q5 and q6 and q6 < q5) or not w["d"].get("ammo"):
            continue
        e = w["d"]["ammo"][0]
        a = next((x for x in m["ammo"].values() if x["raw"] == e["internal_name"]), None)
        if not a:
            continue
        d5, _ = _q_damage(w, a, e, "Q5")
        d6, e6 = _q_damage(w, a, e, "Q6")
        tip = (f"The {weapon_link(site, w)} loses damage at Q6: its quality multiplier is ×{fmt(q5)} at Q5 "
               f"but ×{fmt(q6)} for the {esc(exp_name(w))}, so {site.link('ammo', a['name'], text=e['name'])} "
               f"does {fmt(d5)} per bullet from a Q5 gun and {fmt(d6)} from the experimental one.")
        if e6 is not e and e6.get("falloff") and e6.get("falloff") != e.get("falloff"):
            tip += (f" Its own experimental tuning also changes the falloff from "
                    f"“{esc(e.get('falloff'))}” to “{esc(e6['falloff'])}”.")
        out.append(tip)
    return out


# loot.json ammo box names -> readable names
BOX_NAMES = {
    "Ammobox large rifle 1": "Large rifle ammo box", "Ammobox large sniper rifle 1": "Large sniper rifle ammo box",
    "Ammobox large special explosives 1": "Large explosives ammo box",
    "Ammobox small hunting 1": "Small hunting rifle ammo box", "Ammobox small magnum 1": "Small magnum ammo box",
    "Ammobox small rifle 1": "Small rifle ammo box", "Ammobox small shotgun 1": "Small shotgun ammo box",
    "Fnix ammobox large": "FNIX large ammo box", "Soviet large ammo box": "Soviet large ammo box",
    "Soviet small ammo box": "Soviet small ammo box",
}


def _maplink_btn(href, text):
    return f'<a class="mapbtn" href="{href}">{esc(text)}</a>'


def _schem_trees(ammo):
    """The schematic trees (currency keys) the crafting schematics of these rounds are in, in a fixed order."""
    got = {_schem_tree(a["schem"]) for a in ammo if a["schem"]}
    return [k for k in ("ammo", "experimental", "dlc", "equipment") if k in got] + sorted(got - {"ammo", "experimental",
                                                                                                "dlc", "equipment"})


def _sources_html(site, m, ammo):
    """The ways to get these rounds, with map links that show just that category."""
    boxes = _loot_sub(site, "loot_c_ammo")
    packs = _loot_sub(site, "loot_i_ammo_station_01")
    n_pts = _marker_count(site, "sch_ammo")
    trees = _schem_trees(ammo)
    out = ["<ul class=\"sources\">"]
    if boxes:
        out.append(f"<li><b>Ammo boxes.</b> The map files have {fmt(boxes['count'])} ammo box spawn points; what a "
                   "box holds is rolled at random" + (f" ({esc(boxes['note'].rstrip('.').lower())})"
                                                      if boxes.get("note") else "") + ". " +
                   _maplink_btn(maplink(show=["loot_c_ammo"]), "Ammo boxes on the map") + "</li>")
    out.append("<li><b>Destroyed machines</b> drop ammo when you loot their wrecks.</li>")
    parts = []
    for k in trees:
        cur = _currency(site, k)
        if not cur:
            continue
        what = {"ammo": "Ammo schematics", "experimental": "The experimental rounds' schematics",
                "dlc": "DLC ammo schematics"}.get(k, f"The {k} schematics")
        t = f"{what} are bought with {esc(cur['name'])}: “{esc(cur['earn'])}”"
        if k == "ammo" and n_pts:
            t += (f" The map files place {n_pts} pickups that give them. " +
                  _maplink_btn(maplink(show=["sch_ammo"]), "Ammo schematic points"))
        parts.append(t)
    if parts:
        out.append("<li><b>Crafting.</b> " + " ".join(parts) + "</li>")
    if packs:
        out.append(f"<li>The {site.link('item', 'Ammo Pack')} refills ammo; {packs['count']} of them are placed "
                   "by hand in the world. " + _maplink_btn(maplink(show=["loot_i_ammo_station_01"]),
                                                           "Ammo Packs on the map") + "</li>")
    out.append(f"<li>The {site.link('skill', 'Salvage')} skill gives more ammo from every container and "
               "machine.</li></ul>")
    return "".join(out)


def section_finding(site, m):
    """Where ammo comes from, and the ammo boxes placed in the world by region and box type (loot.json)."""
    loot = site.data("loot")
    sub_idx = next((i for i, s in enumerate(loot["subs"]) if s["key"] == "loot_c_ammo"), None)
    out = (bar("Where to find ammo", id="finding") + "<p>Ammo comes from:</p>" +
           _sources_html(site, m, list(m["ammo"].values())))
    if sub_idx is None:
        return out
    counts, total = {}, {}
    for it in loot["items"]:
        if it[0] != sub_idx:
            continue
        name, reg = loot["names"][it[3]], loot["regions"][it[4]]
        counts.setdefault(name, {}).setdefault(reg, 0)
        counts[name][reg] += 1
        total[reg] = total.get(reg, 0) + 1
    regs = [r for r, _ in REGIONS if r in total]
    rows = []
    for name, by in sorted(counts.items(), key=lambda x: -sum(x[1].values())):
        rows.append([esc(BOX_NAMES.get(name, name))] + [by.get(r) for r in regs] + [sum(by.values())])
    rows.append(["<b>All ammo boxes</b>"] + [total[r] for r in regs] + [sum(total.values())])
    rows.append(['<span class="dim">On the map</span>'] +
                [f'<a href="{maplink(show=["loot_c_ammo"], region=[r])}">Map</a>' for r in regs] +
                [f'<a href="{maplink(show=["loot_c_ammo"])}">Map</a>'])
    heads = ["Box"] + [site.link("region", r, text=dict(REGIONS)[r].split(" (")[0]) for r in regs] + ["Total"]
    return (out + "<h3>Ammo boxes by region</h3>"
            "<p>How many ammo box spawn points the map files have in each region, by box type. The <b>Map</b> links "
            "open the interactive map with only the ammo boxes of that region shown.</p>" +
            table(heads, rows, raw_headers=True, num=set(range(1, len(heads))), cls="compact boxes"))


# =================================================================================================================
# the calibre pages (weapons/ammo/<calibre>.html)
# =================================================================================================================
def build_caliber(site, m, cal):
    ammo = m["cal"][cal]
    users = _users(ammo)
    body = [_cal_note(site, m, cal, ammo), section_cal_damage(site, m, cal, ammo, users)]
    for a in ammo:
        body.append(variant_section(site, m, a))
    ov = overrides_table(site, m, ammo)
    if ov:
        body.append(bar("In experimental weapons", id="in-experimental-weapons") + ov)
    body.append(section_cal_weapons(site, m, cal, ammo, users))
    body.append(section_cal_finding(site, m, cal, ammo))
    group = cal in GROUPS
    site.page(cal_path(cal), cal_title(cal), "".join(body), "weapons", sub="ammo",
              crumbs=[("Ammo", "~/" + AMMO_PAGE)], kind="Ammo · " + ("Ammo group" if group else "Calibre"),
              lead=cal_lead(site, m, cal, ammo, users), infobox_html=cal_infobox(site, m, cal, ammo, users),
              side=[fired_panel(site, m, cal, ammo, users), calibres_panel(site, m, cal)], head_extra=HEAD,
              desc=f"Generation Zero {cal_title(cal)}: all {len(ammo)} variants, their damage from every weapon, "
                   "effects and crafting.")


def cal_lead(site, m, cal, ammo, users):
    if cal == "Other ammo":
        return ("<p>Ammo that belongs to one special weapon or tool: " + ", ".join(
            f'<a href="#{a["id"]}">{esc(a["name"])}</a> ({firers_html(site, m, a, chips=False) or esc(OWNER_TEXT.get(a["kind"], "–"))})'
            for a in ammo) + ".</p>")
    exp = [a for a in ammo if a["exp_only"]]
    what = "group" if cal in GROUPS else "calibre"
    s = (f"<p>The {esc(cal.lower() if cal in GROUPS else cal)} {what} has {len(ammo)} kind"
         f"{'s' if len(ammo) != 1 else ''} of ammo" +
         (f", {len(exp)} of {'them' if len(exp) > 1 else 'it'} only for experimental weapons" if exp else "") + ".")
    if users:
        s += " It is fired by " + ", ".join(weapon_link(site, w) for w in users) + "."
    return s + "</p>"


def cal_infobox(site, m, cal, ammo, users):
    std = [a for a in ammo if not a["exp_only"]]
    exp = [a for a in ammo if a["exp_only"]]
    stacks = sorted({a["stack"] for a in ammo})
    n_craft = sum(1 for a in ammo if a["schem"])
    packs = sorted({w["d"].get("pack") for w in users if (w["d"].get("pack") or "").endswith("(DLC)")})
    rows = [("Ammo group" if cal in GROUPS else "Calibre", esc(cal)),
            ("Variants", f"{len(std)} standard" + (f" + {len(exp)} experimental" if exp else "")),
            ("Stack size", " / ".join(fmt(s) for s in stacks)),
            ("Weapons", f'<a href="#weapons-that-use-it">{len(users)}</a>' if users else "None"),
            ("DLC weapons", " ".join(pack_tag(p) for p in packs) or None),
            ("Craftable", f'<a href="#where-to-find-it">{n_craft} of {len(ammo)}</a>')]
    pic = ammo[0]
    img = "~/" + pic["icon"] if site.has_file(pic["icon"]) else None
    return infobox(cal_title(cal), rows, image=img, image_alt=pic["name"],
                   subtitle=esc(_cal_subtitle(cal, users)))


def _cal_subtitle(cal, users):
    cats = []
    for w in users:
        c = CAT_SINGULAR.get(w["cat"], w["cat"].lower())
        if c not in cats:
            cats.append(c)
    if cal in CAL_SUBTITLE:
        return CAL_SUBTITLE[cal]
    if not cats:
        return "Ammo"
    return "Ammo for " + (", ".join(cats[:-1]) + " and " + cats[-1] if len(cats) > 1 else cats[0])


CAL_SUBTITLE = {"Arrows": "Ammo for the bow", "Other ammo": "Ammo for special weapons and tools"}
# stats.json weapon categories -> plural words for the infobox subtitle
CAT_SINGULAR = {"Handguns": "handguns", "Submachine Guns": "submachine guns", "Assault Rifles": "assault rifles",
                "Machine Guns": "machine guns", "Shotguns": "shotguns", "Hunting Rifles": "hunting rifles",
                "Sniper Rifles": "sniper rifles", "Launchers": "launchers",
                "Bows and flamethrowers": "bows and flamethrowers"}


def _weapon_entry(site, w, label=None):
    """Registry entry of a weapon (its experimental version's anchor when label names it)."""
    return (site.find("weapon", label) if label else None) or site.find("weapon", w["name"])


def wchips(site, pairs, star=None):
    """Weapon links with their icons: pairs = [(weapon, label)]; star(w) -> extra HTML after one."""
    out = []
    for w, label in pairs:
        e = _weapon_entry(site, w, label)
        ic = site.img(e["icon"], cls="wci") if e and e.get("icon") else ""
        inner = f"{ic}<span>{esc(label)}</span>"
        s = (f'<a class="wchip" href="~/{esc(e["path"])}">{inner}</a>' if e else f'<span class="wchip">{inner}</span>')
        out.append(s + (star(w) if star else ""))
    return '<span class="wchips">' + "".join(out) + "</span>"


def fired_panel(site, m, cal, ammo, users):
    """Side panel: the weapons that fire this calibre, with icons; experimental-only firers below."""
    if not users and not any(a["firers"] for a in ammo):
        return ""
    out = []
    if users:
        out.append('<ul class="flist">' + "".join(
            f"<li>{wchips(site, [(w, w['name'])])}</li>" for w in users) + "</ul>")
    extra = []
    for a in ammo:
        for w, label in a["firers"]:
            if label != w["name"] and all(label != x for _, x in extra):
                extra.append((w, label))
    if extra:
        out.append('<div class="fsub">Experimental versions</div><ul class="flist">' + "".join(
            f"<li>{wchips(site, [(w, label)])}</li>" for w, label in extra) + "</ul>")
    return panel("Fired by", "".join(out), cls="amside")


def calibres_panel(site, m, cal):
    items = []
    for c in m["cal_order"]:
        ic = site.img(m["cal"][c][0]["icon"], cls="cpi")
        if c == cal:
            items.append(f'<li class="on">{ic}<b>{esc(cal_title(c))}</b></li>')
        else:
            items.append(f'<li><a href="~/{cal_path(c)}">{ic}{esc(cal_title(c))}</a></li>')
    return panel("All ammo", f'<ul class="clist">{"".join(items)}</ul>', cls="amside amnav")


def section_cal_damage(site, m, cal, ammo, users):
    groups = []   # rounds fired by the same set of weapons share one damage table (9mm: handguns / SMGs)
    for a in ammo:
        key = tuple(w["name"] for w, _ in a["uses"])
        g = next((g for g in groups if g[0] == key), None)
        if g:
            g[1].append(a)
        else:
            groups.append((key, [a]))
    blast = all(not e.get("projectile_damage") for a in ammo for _, e in a["uses"])
    if blast:
        groups = [((), ammo)]          # blast rounds: one effect table for the whole group
    tables = "".join(damage_table(site, m, rounds, [w for w in users if not key or w["name"] in key], explain=i == 0)
                     for i, (key, rounds) in enumerate(groups))
    if not tables:
        return ""
    return bar("What each round does" if blast else "Damage by weapon", id="damage") + tables


def _cal_note(site, m, cal, ammo):
    """Short data-driven notes for calibres with a twist."""
    if cal in NINE_MM:
        other = NINE_MM[1 - NINE_MM.index(cal)]
        if other in m["cal"]:
            mine, theirs = ammo[0], m["cal"][other][0]
            return note(f"Not the same as {site.link('caliber', other, text=cal_title(other))}: the "
                        f"{'handguns' if cal.endswith('Handgun') else 'SMGs'} fire these {len(ammo)} rounds "
                        f"(stack {fmt(mine['stack'])}, {fmt(_first_damage(mine))} base damage) and the "
                        f"{'SMGs' if cal.endswith('Handgun') else 'handguns'} their own "
                        f"(stack {fmt(theirs['stack'])}, {fmt(_first_damage(theirs))} base damage). They are "
                        "separate items and no gun takes both.", "warn")
    if cal == ".32 ACP":
        return "<p>The .32 ACP is shared by a handgun and an SMG; both fire the same items.</p>"
    if cal == "7.62mm":
        return ("<p>The most widely used calibre: assault rifles, machine guns, a bolt-action rifle and two "
                "sniper rifles all fire the same 7.62mm items, but with very different quality multipliers, so "
                "check the table for your gun.</p>")
    if cal == "Launcher rounds":
        return ("<p>Launcher rounds do their damage with a blast, not with the projectile, so the tables show "
                "the blast. The three launcher families use different items: the "
                f"{site.link('weapon', 'Granatgevär m/49')} fires the “Round” items, the "
                f"{site.link('weapon', 'G79 Grenade Launcher')} and {site.link('weapon', 'MGR-6 Grenade Launcher')} "
                f"fire the “Cartridge” items, and the {site.link('weapon', 'RLG-7')} has its own LG-7V round.</p>")
    return ""


def section_cal_weapons(site, m, cal, ammo, users):
    """Cards of the weapons that fire this calibre (icon, which rounds, experimental version)."""
    items = []
    for w in users:
        std = [a for a in ammo if not a["exp_only"] and any(x is w for x, _ in a["uses"])]
        exp = [a for a in ammo if a["exp_only"] and any(x is w for x, _ in a["firers"])]
        sub = "Loads " + esc(_and([_lc(_short(a)) for a in std])) if std else ""
        if exp:
            sub += ("<br>" if sub else "") + esc(f"{exp_name(w)} also: " + _and([_lc(_short(a)) for a in exp]))
        e = site.find("weapon", w["name"])
        pk = w["d"].get("pack") or ""
        items.append({"href": "~/" + e["path"] if e else "#weapons-that-use-it", "title": w["name"],
                      "img": "~/" + e["icon"] if e and e.get("icon") and site.has_file(e["icon"]) else None,
                      "sub": sub, "tag": "DLC" if pk.endswith("(DLC)") else "",
                      "color": "#8a6d1f"})
    if not items:
        return ""
    return (bar("Weapons that use it", f"{len(items)} weapon{'s' if len(items) != 1 else ''}") +
            cards(items, cls="wcards") + _cross_note(site, m, cal))


def _lc(label):
    """'Full metal jacket' -> 'full metal jacket'; 'HEAT' stays."""
    return label if label[:2].isupper() else label[:1].lower() + label[1:]


def _and(words):
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1] if words else ""


def _short(a):
    """Short name of a round inside its calibre: its kind ('Armour-piercing'), or the name for one of a kind."""
    return KIND_LABEL.get(a["kind"], a["name"])


def schem_cells(site, s):
    """(schematic link, cost, recipe) of a crafting schematic."""
    cur = next((c for c in site.data("gamedata")["schematics"] if c["key"] == _schem_tree(s)), None)
    cost = "–"
    if s.get("c") is not None:
        if s["c"] == 0:
            cost = "Free"
        elif cur:
            ic = site.img(cur["icon"].replace("assets/", "img/", 1), alt="", cls="cur", title=cur["name"])
            unit = re.sub(r"Points\b", "Point", cur["name"]) if s["c"] == 1 else cur["name"]
            cost = f"{fmt(s['c'])} {ic}{esc(unit)}"
        else:
            cost = fmt(s["c"])
    return site.link("schematic", s["n"]), cost, esc(s.get("r") or "–")


def section_cal_finding(site, m, cal, ammo):
    rows = []
    for a in ammo:
        icon = site.img(a["icon"], cls="li")
        name = f'<a href="#{a["id"]}">{icon}{esc(a["name"])}</a>'
        if a["schem"]:
            rows.append([name, *schem_cells(site, a["schem"])])
        else:
            rows.append([name, '<span class="dim">No schematic</span>', "–", "–"])
    return (bar("Where to find it") +
            "<p>The crafting schematic of each round, what it costs and what one craft takes:</p>" +
            table(["Ammo", "Crafting schematic", "Cost", "Recipe per craft"], rows, cls="compact") +
            "<p>Where ammo comes from:</p>" + _sources_html(site, m, ammo) +
            f'<p class="small">Ammo box counts per region are on the <a href="~/{AMMO_PAGE}#finding">main ammo '
            'page</a>.</p>')


OWNER_TEXT = {"repair": "the Companion's repair tool"}   # 'Other ammo' items no weapon fires
QS = ("Q1", "Q2", "Q3", "Q4", "Q5", "Q6")


def _qmul_text(w):
    return " / ".join(fmt(w["qmul"][q]) for q in QS if q in w["qmul"])


def _q_damage(w, a, e, q):
    """(damage, entry) for one projectile of round a fired from weapon w at quality q: base damage × the weapon's
    multiplier for q. At Q6 the experimental weapon's own entry for the round (experimental_ammo_overrides)
    replaces the normal one when it has one."""
    if q == "Q6":
        e = next((x for ww, x in a["overrides"] if ww is w), e)
    return round((e.get("projectile_damage") or 0) * w["qmul"].get(q, 1), 2), e


def _blast_suffix(a, e):
    """' + blast' when an entry does its damage with an impact blast (the experimental Älgstudsare); a medical
    round's 'blast' is its pulse."""
    if not ((e.get("on_hit") or {}).get("blast") or e.get("on_hit_stages")):
        return ""
    return " + pulse" if a["kind"] == "medical" else " + blast"


def _damage_cell(w, a, e):
    """One cell of the damage table: Q5 damage (with Q1–Q4 and Q6 on hover), or for a Q6-only round the damage
    from the weapon's experimental version ('–' when the weapon has none and so cannot fire it)."""
    pel = e.get("projectiles_per_shot") or 1
    pre = f"{pel} × " if pel > 1 else ""
    if a["exp_only"]:
        if not w["exp"]:
            return None
        d, e6 = _q_damage(w, a, e, "Q6")
        title = f"{exp_name(w)} (Q6)" + (", from its own experimental tuning" if e6 is not e else "")
        return f'<span title="{esc(title)}">{pre}{fmt(d)}{_blast_suffix(a, e6)}</span>'
    hover = []
    for q in QS:
        if q in w["qmul"] and q != "Q5" and (q != "Q6" or w["exp"]):
            d, eq = _q_damage(w, a, e, q)
            hover.append(f"{q} {fmt(d)}{_blast_suffix(a, eq) if eq is not e else ''}")
    q5, _ = _q_damage(w, a, e, "Q5")
    return f'<span title="{esc(", ".join(hover))}">{pre}{fmt(q5)}{_blast_suffix(a, e)}</span>'


def damage_table(site, m, ammo, users, explain=True):
    """Weapons (rows) x rounds (columns): damage per projectile at Q5, with the quality multipliers.
    Blast rounds (no projectile damage) get a list of their effect on impact instead."""
    used = [a for a in ammo if a["uses"]]
    if not used:
        return ""
    if all(not e.get("projectile_damage") for a in used for _, e in a["uses"]):
        rows = []
        for a in used:
            e = a["uses"][0][1]
            rows.append([f'<a href="#{a["id"]}">{esc(a["name"])}</a>', firers_html(site, m, a, chips=False) or "–",
                         on_hit_html(e) or "–", rng(e.get("max_range_m"))])
        has_blast = any((a["uses"][0][1].get("on_hit") or {}).get("blast") for a in used)
        return ("<p class=\"small\">Effect on impact as the tuning files give it" +
                (" (the files do not say whether the weapon's quality multiplier also scales the blast)"
                 if has_blast else "") + ".</p>" +
                table(["Round", "Fired by", "Effect on impact", "Max range (m)"], rows, cls="compact", num={3}))
    heads = ["Weapon", "Quality multiplier Q1–Q6", "Q6 version"] + \
        [f'<a href="#{a["id"]}" title="{esc(a["name"])}">{esc(KIND_LABEL.get(a["kind"], a["name"]))}'
         f'{" <span class=xq>Q6</span>" if a["exp_only"] else ""}</a>' for a in used]
    rows = []
    for w in users:
        row = [f'<span class="wcell">{site.link("weapon", w["name"], icon=True)}</span>',
               f'<span class="mono nw">{_qmul_text(w)}</span>', "Yes" if w["exp"] else "No"]
        for a in used:
            e = next((x for ww, x in a["uses"] if ww is w), None)
            row.append(_damage_cell(w, a, e) if e else None)
        rows.append(row)
    return ("<h4>Damage per projectile" + (f" · {esc(_group_label(used))}" if _group_label(used) else "") +
            "</h4>" + ("<p class=\"small\">Each cell is one projectile's damage from that weapon at Q5 (base damage × "
            "the weapon's Q5 multiplier; shotguns show pellets × damage); hover a cell for the other qualities. "
            "Columns marked <span class=\"xq\">Q6</span> are experimental-only rounds: their cells show the "
            "damage from the weapon's experimental version (base × its Q6 multiplier, or its own experimental "
            "tuning where it has one), and “–” for weapons without an experimental version, which cannot fire "
            "them. Armour and component multipliers are in each round's own section below.</p>" if explain else "") +
            '<div class="dmgtable">' +
            table(heads, rows, cls="compact", raw_headers=True, num=set(range(3, 3 + len(used)))) + "</div>")


def _group_label(rounds):
    """'Handgun' / 'SMG' when a calibre's rounds are split by weapon type (the 9mm)."""
    for word in ("Handgun", "SMG"):
        if all(word in a["name"] for a in rounds):
            return word + " rounds"
    return ""


def variant_section(site, m, a):
    """One ammo variant on its calibre page: a bar with the name, the icon and the facts on one side, what it does,
    who fires it and how to craft it on the other."""
    e = a["uses"][0][1] if a["uses"] else {}
    tags_html = tag(KIND_LABEL.get(a["kind"], "Ammo"))
    if a["exp_only"]:
        tags_html += tag("Experimental only", "exp")
    packs = {w["d"].get("pack") for w, _ in a["uses"]}
    if packs and all(p and p.endswith("(DLC)") for p in packs):
        tags_html += "".join(pack_tag(p) for p in sorted(packs))
    facts = [("Stack size", fmt(a["stack"]))]
    blast_only = e and not e.get("projectile_damage") and e.get("on_hit")
    if e and not blast_only:      # for blast rounds the projectile numbers mean nothing
        pel = e.get("projectiles_per_shot") or 1
        d = (e.get("projectile_damage") or 0) * pel
        facts += [("Base damage", (f"{pel} × " if pel > 1 else "") + fmt(e.get("projectile_damage"))),
                  ("Armour / comp. per shot",
                   f"{fmt(d * e['armour_multiplier'])} / {fmt(d * e['component_multiplier'])}" if d else None),
                  ("Armour mult.", mult_html(e.get("armour_multiplier"))),
                  ("Component mult.", mult_html(e.get("component_multiplier"))),
                  ("Falloff", esc(falloff_text(e, a["uses"][0][0])) if e.get("falloff") else None)]
    if e.get("max_range_m"):
        facts.append(("Max range", f"{fmt(rng(e['max_range_m']))} m"))
    lines = []
    if a["firers"]:
        lines.append(f'<div class="vline"><b>Fired by</b>{firers_html(site, m, a)}</div>')
    lines.append('<div class="vline"><b>Crafting</b><span>' +
                 (schem_html(site, a["schem"]) or '<span class="dim">no crafting schematic in the files</span>') +
                 "</span></div>")
    pic = site.img(a["icon"], alt=a["name"], cls="vicon")
    return (bar(a["name"], esc(KIND_LABEL.get(a["kind"], "Ammo")), id=a["id"]) +
            f'<div class="avar"><div class="vside"><div class="vpic">{pic}</div><div class="vtags">{tags_html}</div>'
            f'{kv(facts)}</div><div class="vmain">{effect_html(site, m, a, e)}{"".join(lines)}</div></div>')


# launcher rounds whose kind word means something else than on a bullet
LAUNCHER_TEXT = {
    "corrosive": "The experimental version of the high-explosive dual-purpose round, with a corrosive filling. "
                 "The files give it the same blast as the normal HEDP round; the corrosion comes on top.",
    "radioactive": "An experimental round whose blast does no damage: it blinds the machines it covers, so you "
                   "can reposition or pick them off while they can't see you.",
}


# kinds whose effect strength lives in a separate effect file the extractor does not read (HEAT, corrosive and the
# like are fully described by their multipliers and on_hit data, so they don't get the 'not in the data' remark)
EFFECT_FILE_KINDS = ("shock", "tar", "explosive", "radioactive")


def _kind_text(a, e):
    if a["cal"] == "Launcher rounds" and a["kind"] in LAUNCHER_TEXT:
        return LAUNCHER_TEXT[a["kind"]]
    if a["kind"] == "explosive" and _blast_round(a, e):       # the explosive arrow: a blast, not a planted bomb
        blasts = [s["blast"]["damage_to_machines"] for s in e.get("on_hit_stages") or [] if s.get("blast")] or \
            [e["on_hit"]["blast"]["damage_to_machines"]]
        span = f"{fmt(min(blasts))}–{fmt(max(blasts))}" if len(set(blasts)) > 1 else fmt(blasts[0])
        return (f"The arrowhead explodes on impact; almost all of its damage is the blast ({span} to machines "
                f"depending on draw), not the arrow itself ({fmt(e.get('projectile_damage'))} damage).")
    return KIND_TEXT.get(a["kind"], "")


def _exp_only_text(site, m, a):
    """Where a Q6-only round can be loaded: the experimental versions of its weapons, or (.32 ACP) none of them."""
    own = [(w, label) for w, label in a["firers"] if any(ww is w for ww, _ in a["uses"])]
    if own:
        return "<p>Experimental only: it can be loaded only into an experimental (Q6) weapon (see Fired by).</p>"
    names = sorted({w["name"] for w, _ in a["uses"]})
    who = (f"neither {a['cal']} weapon has" if len(names) == 2 else
           f"the {a['cal']} weapon has no" if len(names) == 1 else f"none of the {a['cal']} weapons has")
    who += "" if len(names) == 1 else " an"
    out = f"<p>Experimental only, but {esc(who)} experimental version in the files"
    if a["firers"]:
        out += ("; the only experimental weapon whose tuning lists this round is the " +
                " and ".join(weapon_link(site, w, text=label) for w, label in a["firers"]))
    return out + ".</p>"


def effect_html(site, m, a, e):
    """What the round does: our explanation, the game's own schematic text, and the numbers the data has."""
    k = a["kind"]
    text = _kind_text(a, e) if a["uses"] or k in ("battery", "repair") else ""
    out = [f"<p>{esc(text)}</p>"] if text else []
    if e and k in ("buck", "bird") and e.get("projectiles_per_shot"):
        out.append(f"<p>{e['projectiles_per_shot']} pellets × {fmt(e['projectile_damage'])} damage = "
                   f"{fmt(e['projectiles_per_shot'] * e['projectile_damage'])} per shell if every pellet hits; "
                   f"{esc(e['falloff'])}, {fmt(e['max_range_m'])} m at most.</p>")
    props = schem_properties(a["schem"])
    if props:
        out.append(f'<blockquote class="gametext"><b>In-game description</b> {esc(props)}</blockquote>')
    if k == "medical" and e:
        h = (e.get("on_hit") or {}).get("heal_pulse")
        if h:
            out.append(f"<p><b>From the game files:</b> the pulse heals {fmt(h['damage_to_players'])} within "
                       f"{fmt(h['radius_vs_players_m'])} m of the impact; the round itself does "
                       f"{fmt(e.get('projectile_damage'))} damage.</p>")
    elif e and on_hit_html(e):
        out.append(f"<p><b>From the game files:</b> {on_hit_html(e)}.</p>")
    if k == "corrosive" and e and (e.get("on_hit") or {}).get("damage_over_time"):
        out.append('<p class="dim small">The damage over time listed with it targets characters (people), not '
                   "machines; how it shows up in play is not clear from the files.</p>")
    if e and e.get("on_hit_stages"):
        out.append("<p>The blast grows with the bow's draw:</p>" + stages_table(e["on_hit_stages"]))
    if k in EFFECT_FILE_KINDS and any(x.get("note", "").startswith("Special effect not included")
                                      for _, x in a["uses"]):
        out.append('<p class="dim small">The strength of the special effect (slow, tether damage, blinding '
                   "time, bomb damage) is kept in a separate effect file that the extractor does not read, so "
                   "there are no numbers for it here; the damage and multipliers are the bullet itself.</p>")
    if a["exp_only"]:
        out.append(_exp_only_text(site, m, a))
    if not a["uses"]:
        if k == "repair":
            out.append("<p>Not fired by a weapon, so there is no damage data. The companion and its gear "
                       f"are covered under {site.link('item', a['name'], text='Items › Companion')}.</p>")
        elif k == "battery":
            out.append("<p>The normal weapon tuning lists no weapon for it; its numbers are in "
                       "<a href=\"#in-experimental-weapons\">In experimental weapons</a> below.</p>")
        else:
            out.append("<p>No weapon in the extracted weapon tuning lists this item, so there is no damage, "
                       "range or effect data for it. It exists in the item table with an item ID.</p>")
    return "".join(out)


_SAME_KEYS = ("projectile_damage", "projectiles_per_shot", "armour_multiplier", "component_multiplier", "falloff",
              "max_range_m", "on_hit", "on_hit_stages", "blast")


def _same_as_base(a, e):
    """True when an experimental override has exactly the numbers of the normal round."""
    if not a["uses"]:
        return False
    base = a["uses"][0][1]
    return all(base.get(k) == e.get(k) for k in _SAME_KEYS)


def overrides_table(site, m, ammo):
    """The changed versions of this calibre's rounds inside experimental weapons (experimental_ammo_overrides).
    Overrides with the same numbers as the normal round are named, not listed; for a weapon that lists other
    calibres' rounds (the AI-76) they are not even named, since it is already under 'Fired by' with a note."""
    pairs = [(a, w, e) for a in ammo for w, e in a["overrides"]]
    rows, same = [], {}
    for a, w, e in sorted(pairs, key=lambda p: (p[1]["name"], p[0]["name"])):
        if _same_as_base(a, e):
            if w["name"] not in m["cross"]:
                same.setdefault(w["name"], (w, []))[1].append(a)
            continue
        medical = a["kind"] == "medical"
        rows.append([weapon_link(site, w, text=exp_name(w)),
                     f'<a href="#{a["id"]}">{esc(override_name(a, e))}</a>',
                     e.get("projectile_damage"), e.get("projectiles_per_shot"),
                     mult_html(e.get("armour_multiplier")) if e.get("armour_multiplier") is not None else "–",
                     mult_html(e.get("component_multiplier")) if e.get("component_multiplier") is not None else "–",
                     esc(falloff_text(e, w) or "–"), rng(e.get("max_range_m")), on_hit_html(e, medical) or "–"])
    staged = {}   # identical stage lists are shown once, with every round that has them
    for a, w, e in pairs:
        if e.get("on_hit_stages"):
            key = (w["name"], repr(e["on_hit_stages"]))
            staged.setdefault(key, (w, e["on_hit_stages"], a["kind"] == "medical", []))[3].append(override_name(a, e))
    if not rows and not same and not staged:
        return ""
    out = ""
    if rows:
        out += ("<p class=\"small\">Experimental weapons carry their own tuning for some rounds. When you fire the "
                "round from that weapon, these numbers replace the normal ones.</p>" +
                table(["Experimental weapon", "Round", "Damage", "Pellets", "Armour ×", "Comp. ×",
                       "Falloff", "Range (m)", "Extra effect"], rows, cls="compact", num={2, 3, 7}))
    for w, rounds in same.values():
        out += (f'<p class="small">The {weapon_link(site, w, text=exp_name(w))} also has its own entry for '
                f'{", ".join(site.link("ammo", a["name"]) for a in rounds)}, with exactly the normal numbers.</p>')
    if any("drops to 0% by ~0 m" in (e.get("falloff") or "") for _, _, e in pairs):
        out += ('<p class="dim small">“drops to 0% by ~0 m” is what the files hold for some of these entries; it '
                "looks like an empty falloff curve rather than a round that does no damage.</p>")
    for w, stages, medical, names in staged.values():
        what = ("the pulse (listed as a blast in the files; for a medical round most likely the healing amount)"
                if medical else "the blast")
        out += (f"<p class=\"small\">{esc(exp_name(w))}, {esc(', '.join(names))}: {what} grows the longer the "
                "round has been in flight:</p>" + stages_table(stages, medical))
    return out


# =================================================================================================================
# attachments page
# =================================================================================================================
def build_attachments(site, m):
    placed = placed_attachments(site, m)
    body = [att_overview(site, m), att_by_weapon(site, m)]
    for cat in ATT_CATS:
        items = [a for a in m["att"] if a["cat"] == cat]
        if items:
            body.append(att_section(site, m, cat, items, placed))
    body.append(att_placed_section(site, m, placed))
    lead = (f"<p>All {len(m['att'])} weapon attachments in Generation Zero: scopes and sights, vision modules, "
            "compensators, silencers, barrel extensions and chokes, and extended magazines. For each one: which "
            "weapons it fits (straight from the game's compatibility list), what it does, and where the "
            "hand-placed ones lie in the world.</p>")
    site.page(ATT_PAGE, "Attachments", "\n".join(body), "weapons", sub="attachments", head_extra=HEAD, lead=lead,
              desc="Every Generation Zero weapon attachment: scopes, vision modules, silencers, compensators, "
                   "extended magazines, the weapons they fit and where to find them.",
              search={"k": "Weapons", "w": "attachments scope silencer suppressor magazine compensator choke"})


def att_overview(site, m):
    rows = []
    for cat, (title, slot, _text) in ATT_CATS.items():
        items = [a for a in m["att"] if a["cat"] == cat]
        weapons = {t for a in items for t in a["compat"]}
        rows.append([f'<a href="#{slug(title)}">{esc(title)}</a>', esc(slot), len(items), len(weapons),
                     esc(", ".join(sorted({"single" if a["quals"] == ["0"] else "Q1–Q5" for a in items})))])
    return (bar("Overview", id="overview") +
            "<p>Attachments come in four groups by where they go on the gun: a sight, a vision module, a muzzle "
            "attachment and a magazine. Silencers, compensators, barrel extensions and chokes all go on the "
            "muzzle, so a weapon carries one of them at a time. Attachments come in five qualities like weapons "
            "(Dilapidated to Special), except vision modules, which have one. Every attachment fits only the "
            "weapons in its compatibility list; the tables below show them all.</p>" +
            table(["Type", "Slot", "Attachments", "Weapons they fit", "Qualities"], rows, num={2, 3}, cls="compact") +
            note("The game files used for this wiki list which weapon each attachment fits, but not its exact "
                 "effect (zoom steps, recoil or noise reduction, extra rounds per magazine, the difference between "
                 "qualities). The effects below are described in words for that reason.", "data"))


def att_by_weapon(site, m):
    """Weapon -> the attachments that fit it, per slot."""
    slots = ["Sight", "Vision module", "Muzzle", "Magazine"]
    per = {}
    for a in m["att"]:
        slot = ATT_CATS[a["cat"]][1]
        for t in a["compat"]:
            per.setdefault(t, {}).setdefault(slot, []).append(a)
    all_vision = [a for a in m["att"] if a["cat"] == "Vision Modules"]
    rows = []
    for tid in sorted(m["tool"], key=lambda t: int(t)):
        w = m["tool"][tid]
        got = per.get(tid, {})
        if not got:
            continue
        cells = []
        for slot in slots:
            items = got.get(slot, [])
            if slot == "Vision module" and items and len(items) == len(all_vision):
                cells.append(f'<a href="#vision-modules">All {len(items)} vision modules</a>')
            else:
                cells.append("<br>".join(f'<a href="#{a["id"]}">{esc(a["name"])}</a>' for a in items) or "–")
        rows.append([f'<span class="wcell">{site.link("weapon", w["name"], icon=True)}</span>'] + cells)
    none = [m["tool"][t] for t in sorted(m["tool"], key=int) if t not in per]
    body = ("<p>Find your weapon to see everything that fits it. Weapons that take no attachments at all are "
            "listed under the table.</p>" + table(["Weapon"] + slots, rows, cls="compact matrix attw") +
            (f"<p class=\"small\">No attachments: {', '.join(site.link('weapon', w['name']) for w in none)}.</p>"
             if none else ""))
    return fold("Attachments by weapon", body, open=False, right=f"{len(rows)} weapons", id="by-weapon")


def att_section(site, m, cat, items, placed):
    title, slot, text = ATT_CATS[cat]
    return fold(title, f"<p>{esc(text)}</p>" + '<div class="attgrid">' +
                "".join(att_card(site, m, a, placed.get(a["name"], [])) for a in items) + "</div>",
                open=True, right=f"{len(items)} items", id=slug(title))


def _spot_link(s, zoom=1.2):
    """Map link for one placed attachment: only its loot category, centred on it with its popup open."""
    return maplink(show=[s["sub"]], at=(s["x"], s["z"]), zoom=zoom, focus=s["n"])


def att_card(site, m, a, placed):
    weapons = [m["tool"][t] for t in a["compat"] if t in m["tool"]]
    if a["quals"] == ["0"]:
        quals = '<span class="qb q0">Single quality</span>'
    else:
        qs = [int(q) for q in a["quals"]]
        quals = qbadge(qs[0], short=True) + ("–" + qbadge(qs[-1], short=True) if len(qs) > 1 else "")
    where = None
    if placed:
        best = max(placed, key=lambda s: s["q"] or 0)
        subs = sorted({s["sub"] for s in placed})
        href = maplink(show=subs, at=(best["x"], best["z"]), zoom=0.6, focus=best["n"])
        where = (f'<a href="#placed">{len(placed)} spot{"s" if len(placed) != 1 else ""}</a> · '
                 f'<a href="{href}">map</a>')
    facts = [("Slot", esc(ATT_CATS[a["cat"]][1])), ("Qualities", quals),
             ("Fits", ", ".join(site.link("weapon", w["name"]) for w in weapons) or "–"),
             ("Placed in world", where)]
    what = att_what(a)
    return (f'<section class="acard att"><div class="ahead">{site.img(a["icon"], alt=a["name"], cls="aicon")}'
            f'<div><h3 id="{a["id"]}">{esc(a["name"])}</h3><div class="dim small">{esc(ATT_CATS[a["cat"]][0])}'
            f'</div></div></div>{f"<p>{what}</p>" if what else ""}{kv(facts)}</section>')


def att_what(a):
    """A line about this attachment in particular (the category text covers the general idea)."""
    n = a["name"]
    zoom = re.match(r"^([\d.]+(?:-[\d.]+)?)x", n) or re.search(r"x([\d.]+)", n)
    if a["cat"] == "Scopes":
        if "Bow Sight" in n:
            return "A three-pin sight for the bow: each pin marks the aim point for a longer distance."
        if zoom:
            z = zoom.group(1)
            return f"{'Variable' if '-' in z else 'Fixed'} {esc(z)}× magnification."
    if a["cat"] == "Vision Modules":
        modes = [("Low light", "nv"), ("IR", "hv"), ("Object penetrating", "xr")]
        has = [label for label, code in modes if code in (a["internal"] or "").split("_")[-3:]]
        return f"Vision modes: {', '.join(has)}." if has else ""
    return ""


def placed_attachments(site, m):
    """Attachments placed by hand in the world (loot.json): attachment name -> [spot dicts]. A spot's 'n' is the
    marker name the interactive map shows ('Handgun Silencer (Dilapidated)'), 'sub' its loot category."""
    loot = site.data("loot")
    subs = {i: s for i, s in enumerate(loot["subs"]) if s["main"] == "loot_attachments"}
    out = {}
    for it in loot["items"]:
        s = subs.get(it[0])
        if not s:
            continue
        raw = loot["names"][it[3]]
        name = re.sub(r"\s*\([^)]*\)$", "", raw)
        e = site.find("attachment", name)
        key = e["key"] if e else name
        out.setdefault(key, []).append({"x": it[1], "z": it[2], "q": s.get("q"), "region": loot["regions"][it[4]],
                                        "sub": s["key"], "n": raw})
    return out


def _nearest_location(site, x, z):
    best, bd = None, None
    for loc in site.data("map_locations")["list"]:
        dd = math.hypot(loc["x"] - x, loc["z"] - z)
        if bd is None or dd < bd:
            best, bd = loc, dd
    return best, bd


def att_placed_section(site, m, placed):
    reg_name = dict(REGIONS)
    spots = []
    for name, ss in sorted(placed.items()):
        for s in sorted(ss, key=lambda s: (s["q"] or 0, s["region"])):
            spots.append((name, s))
    if not spots:
        return ""
    by_att = {a["name"]: a for a in m["att"]}
    rows, pts = [], []
    for name, s in spots:
        e = site.find("attachment", name)
        at = by_att.get(e["key"]) if e else None
        icon = site.img(at["icon"], cls="li") if at else ""
        link = f'<a href="#{e["path"].split("#")[1]}">{icon}{esc(name)}</a>' if e else esc(name)
        loc, dist = _nearest_location(site, s["x"], s["z"])
        rows.append([link, (qbadge(s["q"]), s["q"]) if s["q"] else "–",
                     site.link("region", s["region"], text=reg_name.get(s["region"], s["region"]).split(" (")[0]),
                     site.link("location", loc["name"]) if loc else "–", round(dist) if loc else None,
                     round(s["x"]), round(s["z"]), f'<a href="{_spot_link(s)}">Map</a>'])
        pts.append((s["x"], s["z"], s["n"]))
    subs = sorted({s["sub"] for _, s in spots})
    best = max(spots, key=lambda p: p[1]["q"] or 0)[1]
    mm = minimap(pts[0][0], pts[0][1], pts[0][2], markers=pts[1:], height=360, zoom=1, show=subs)
    # with several pins minimap() leaves the centre out: open the full map on the best one with its popup
    full = maplink(show=subs, at=(best["x"], best["z"]), zoom=0.6, focus=best["n"])
    mm = re.sub(r'(<a class="mmopen" href=")[^"]*', lambda x: x.group(1) + full, mm, count=1)
    counts = []
    for q in sorted({s["q"] for _, s in spots if s["q"]}):
        counts.append(f"{sum(1 for _, s in spots if s['q'] == q)} {qbadge(q)}")
    coords = fold("Detailed coordinates",
                  "<p>Every spot, with the nearest named map location and its distance. Coordinates are the game's "
                  "world x / z; <b>Map</b> opens the interactive map on that spot with its popup open.</p>" +
                  table(["Attachment", "Quality", "Region", "Nearest location", "Distance (m)", "x", "z", ""], rows,
                        cls="compact", num={4, 5, 6}),
                  open=False, level=3, right=f"{len(rows)} spots", id="detailed-coordinates")
    return (bar("Found in the world", f"{len(rows)} placed", id="placed") +
            "<p>Most attachments come from weapon and equipment boxes and from machines, where the contents are "
            "rolled at random. These are the ones the map files place at a fixed spot, so you can go and pick "
            f"them up: {', '.join(counts)}. " +
            f'<a class="mapbtn" href="{maplink(show=subs)}">All placed attachments on the map</a></p>' +
            mm + coords)
