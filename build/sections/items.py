"""Items & crafting tab: equipment, crafting materials, the schematic trees and the machine companion.

Pages
    items/index.html        stock.json group 'items' (equipment) by sub group, with the schematic that crafts each
                            item, the game's own description of it and how many lie placed in the world
    items/materials.html    stock.json group 'materials': which schematics use each one and where it lies placed
    items/schematics.html   schematics.json: every tree laid out in paths like the game's SCHEMATICS menu, with
                            the currency of each tree (gamedata.json 'schematics') and a full table per tree
    items/companion.html    the machine companion: its stock items, the companion armor tree and the companion
                            cosmetics of vanity.json (paint jobs, light kits, voice boxes, modules, weapons, tricks)

Kinds registered
    item        key = stock.json name (a second item with the same name is registered by internal name);
                aliases = internal name, item hash
    material    key = stock.json name; aliases = internal name, item hash
    schematic   key = schematic name (the lowest rank when several ranks share a name, the others by internal
                name); aliases = hash, internal name 'k', '<name> (rank N)'. The tree keys ('apparel', 'ammo', ...)
                are registered too, as anchors of the trees.

Data
    stock.json       {h: item hash, raw: internal name, name, g: ammo/items/materials, sub: group, stack: stack size,
                     icon: assets/stock/x.png, add: offered in the Gen0 Editor's add menu (not a game value)}
    schematics.json  trees: [{key, name, cur: currency hash, groups: [{name, rows: [{name, nodes: [hash...]}]}]}],
                     items: [{h, n: name, k: internal name, q: quality / rank, c: cost in points, d: description,
                     r: recipe '8 Adhesive, 16 Wood', i: icon (img/schematics), pre: prerequisite hashes, t: tree,
                     free: 1 = unlocked from the start, dlc: 1 = DLC}]
    gamedata.json    schematics: the six schematic point currencies (name, how they are earned, icon)
    loot.json        placed loot; subs of main 'loot_items' / 'loot_materials' name one item each
    markers.json     the schematic point pickups on the map (subs sch_ammo, sch_apparel, sch_equipment)
    vanity.json      companion cosmetics (group 'companion', and emotes sub 'companion'); l = the vanity table's
                     lock flag (U = unlocked from the start, L = locked until earned, a D = DLC), p = content pack
"""
import collections
import re

from wiki.site import esc, slug, norm, fmt, table, bar, note, qbadge, tag, REGIONS

CSS = '<link rel="stylesheet" href="~/assets/items.css">'
REGION_NAME = dict(REGIONS)
REGION_KEYS = [k for k, _ in REGIONS]
REGION_SHORT = {k: n.split(" (")[0] for k, n in REGIONS}

# Equipment sub groups of stock.json in the order of the page, with a short intro and a filter key.
EQUIP_GROUPS = [
    ("Medical", "medical", "First aid kits and other things that heal you or get you back on your feet."),
    ("Throwables and explosives", "throw",
     "Grenades, gas tanks and other things you throw, place or shoot at. Several of them are also weapons with "
     "their own damage page."),
    ("Lures and distractions", "lure",
     "Noise makers and flares that pull machines away from you, or confuse them for a moment."),
    ("Tools and gadgets", "tool", "Optics, lockpicks, deployable turrets, repair kits and other gadgets."),
    ("Power and fuel", "power", "Fuel, fuel cells and EMP battery packs."),
    ("Vision modules", "vision", "Modules for the vision modes; the Dual Mode and Full modules combine two or "
                                 "three of the single modes."),
    ("Other", "other", "The two items the game files don't put in any of the groups above."),
]
KEYS_GROUP = "Keys and quest items"
# Developer test entries of the item list (not obtainable in the game; key_testkey_01 is left out of the editor's
# add menu, 'add': 0).
TEST_ITEMS = {"key_testkey_01"}
COMPANION_GROUP = "Companion"

MAT_GROUPS = [
    ("Raw materials", "raw", "Basic metals, wood and phosphorus, picked up in the world or salvaged from machines."),
    ("Fabricated", "fab", "Processed materials such as adhesive, textile and explosive."),
    ("Alloys", "alloy", "Steel and the three refined alloys. The refined alloys are what the higher ranks of the "
                        "apparel tree, the experimental ammo and some companion armor ask for."),
    ("Components", "comp", "Ultracapacitors and weapon parts."),
]

# Short descriptions of items that no schematic describes. Only plain facts: the names, the internal names and the
# group the game files put them in. Everything else on the equipment page is the game's own schematic text.
MANUAL_DESC = {
    "equipment_apple": "Listed with the medical items. It shares its icon with the Semla.",
    "equipment_consumable_food_semla_01": "A Swedish cream bun (the icon file is named after <i>Fettisdagen</i>, "
                                          "Shrove Tuesday). The game files list it with the medical items.",
    "equipment_grenade_holy_01": "The name suggests a joke grenade, a nod to Monty Python's Holy Hand Grenade. A "
                                 "stack holds only one.",
    "equipment_snowball_03": "A snowball to throw.",
    "snowball_dispenser_01_held": "A pile of snow to carry (internal name <code>snowball_dispenser_01_held</code>: "
                                  "the held version of a snowball dispenser).",
    "equipment_distraction_firework_box_01": "The game files list it with the lures and distractions (internal name "
                                             "<code>distraction_firework_box</code>).",
    "equipment_distraction_firework_box_02": "The internal name makes it a second version of the Firework Box "
                                             "(<code>firework_box_02</code>), named for Lunar New Year.",
    "equipment_lure_commarray_01": "The internal name <code>lure_commarray_01</code> suggests a lure built from a "
                                   "communication array; Light is the first of three sizes.",
    "equipment_lure_commarray_02": "The internal name <code>lure_commarray_02</code> suggests a lure built from a "
                                   "communication array; Medium is the second of three sizes.",
    "equipment_lure_commarray_03": "The internal name <code>lure_commarray_03</code> suggests a lure built from a "
                                   "communication array; Heavy is the third of three sizes.",
    "equipment_emp_batterypack_small_01": "Its internal name (<code>emp_batterypack</code>) puts it in the same "
                                          "family as the Car Battery EMP.",
    "equipment_emp_batterypack_medium_01": "Its internal name (<code>emp_batterypack</code>) puts it in the same "
                                           "family as the Car Battery EMP.",
    "equipment_emp_batterypack_large_01": "Its internal name (<code>emp_batterypack</code>) puts it in the same "
                                          "family as the Car Battery EMP.",
    "equipment_optics_binoculars_01": "Binoculars (8× magnification, 42 mm lenses, as the name says).",
    "equipment_optics_rangefinder_binoculars_01": "Binoculars with a rangefinder (7×42).",
    "equipment_optics_rangefinder_01": "A rangefinder (5×30).",
    "equipment_optics_camera_01": "A camera; its internal name (<code>optics_camera</code>) puts it in the optics "
                                  "family with the binoculars.",
    "equipment_flashlight_01": "A hand-held light.",
    "equipment_pest_01": "The icon file calls it a <i>friendly pest</i>, which suggests a pod with a Tick on your "
                         "side.",
    "equipment_gnome_pest_01": "The icon file calls it a <i>friendly gnome pest</i>; going by that, a garden-gnome "
                               "variant of the Tick Pod.",
    "equipment_comp_armor_repairpack": "Repairs your companion's armor.",
    "equipment_vision_module_nv": "Low-light (night) vision.",
    "equipment_vision_module_hv": "Infrared vision.",
    "equipment_vision_module_xr": "Object-penetrating vision: see through objects.",
    "equipment_vision_module_hv_nv": "Low-light and infrared vision in one module.",
    "equipment_vision_module_hv_xr": "Infrared and object-penetrating vision in one module.",
    "equipment_vision_module_nv_xr": "Low-light and object-penetrating vision in one module.",
    "equipment_vision_module_hv_nv_xr": "All three vision modes in one module.",
    "comp_spawner": "The item behind your machine companion. See the companion page.",
    "equipment_comp_repairgun_ammo": "Ammo for the repair tool that mends your companion; the game files list it "
                                     "with the ammo.",
}

# The DLC gadgets' schematic text only repeats their name ('Item crafting schematic that makes a Sensory Jammer.'),
# so these short descriptions of how they behave in the game stand in for it.
GADGET_DESC = {
    "equipment_molotov_cocktail_01": "A bottle of fuel that sets the spot where it lands on fire. Its damage is on "
                                     "its weapon page.",
    "equipment_remote_explosive_01": "An explosive charge you place, then set off by remote when machines are near.",
    "equipment_autonomous_turret_01": "A turret you set down that fires a machine gun at machines near it.",
    "equipment_autonomous_turret_02": "A turret you set down that fires homing missiles at machines near it.",
    "equipment_portable_cover_01": "A shield you set down and take cover behind.",
    "equipment_lure_bomb_01": "A noisy toy that draws machines to it, then explodes.",
    "equipment_rc_car_lure_01": "A remote-controlled toy car you drive to pull machines away from you.",
    "equipment_hacking_dart_01": "A dart that turns the machine it hits to your side for a while.",
    "equipment_rc_tick_01": "A Tick you steer by remote control and blow up next to machines.",
    "equipment_sensory_jammer_01": "Disrupts the sensors of the machines around it, so they have a harder time "
                                   "finding you.",
}

# Companion cosmetics: vanity.json sub key -> (title, one-line intro)
COMP_SUBS = [
    ("paint", "Paint jobs", "Paint jobs change the colour and pattern of the companion's shell."),
    ("light", "Light kits", "Light kits change the companion's lights."),
    ("voice", "Voice boxes", "Voice boxes change the sounds the companion makes."),
    ("module", "Modules", "Modules are the companion's equipment slot. Going by their names and how they play, the "
                          "Medic Module lets the companion help heal you, the Scavenger Module has it find loot, and "
                          "the Spotter Module has it spot and mark machines; the game files hold no values for "
                          "them."),
    ("weapon", "Weapons", "The companion's own weapons."),
]
LOCK_FLAG = {  # vanity.json 'l' -> (label, css class, explanation)
    "U": ("Default", "green", "unlocked from the start"),
    "L": ("Locked", "base", "locked until you find or earn it"),
    "UD": ("DLC", "dlc", "comes with a content pack (DLC)"),
    "LD": ("DLC · locked", "dlc", "from a content pack (DLC), and locked until earned"),
}
ARMOR_TYPES = ["runner", "stealth", "aggro", "ballistic", "concussive", "retardant"]
# What each armor kind is for, going by its name and how it plays (the game files hold no protection values).
ARMOR_DESC = {
    "runner": "The basic all-round armor plate.",
    "stealth": "Makes the companion harder for machines to detect.",
    "aggro": "Draws the machines' attention to the companion, so it tanks for you.",
    "ballistic": "Resists bullets.",
    "concussive": "Resists explosions.",
    "retardant": "Resists fire.",
}
TREE_ICON = "img/currencies/{}.png"


# ---------------------------------------------------------------------------------------------------------------
# The model: everything the four pages need, built once per build from the JSON.
# ---------------------------------------------------------------------------------------------------------------
class Model:
    def __init__(self, site):
        self.site = site
        stock = site.data("stock")["stock"]
        self.stock = stock
        self.by_raw = {s["raw"]: s for s in stock}
        self.by_name = collections.defaultdict(list)       # norm(name) -> stock entries (items and materials)
        for s in stock:
            if s["g"] != "ammo":
                self.by_name[norm(s["name"])].append(s)
        self.items = [s for s in stock if s["g"] == "items"]
        self.materials = [s for s in stock if s["g"] == "materials"]
        sd = site.data("schematics")
        self.trees = sd["trees"]
        self.schem = sd["items"]
        self.sch_by_hash = {s["h"]: s for s in self.schem}
        self.currency = {c["hash"]: c for c in site.data("gamedata")["schematics"]}
        self.product = {s["h"]: self._product(s) for s in self.schem}   # hash -> stock entry it makes (or None)
        self.schem_for_raw = {}                                          # stock raw -> schematic that makes it
        for s in self.schem:
            p = self.product[s["h"]]
            if p and p["raw"] not in self.schem_for_raw:
                self.schem_for_raw[p["raw"]] = s
        self.recipes = {s["h"]: self._recipe(s) for s in self.schem}
        self.uses = collections.defaultdict(list)                       # material raw -> [(schematic, amount)]
        for s in self.schem:
            for amount, name, ref in self.recipes[s["h"]]:
                if ref and ref[0] in ("material", "item"):
                    self.uses[ref[1]["raw"]].append((s, amount))
        self.loot = self._loot()
        self.dlc_packs = self._dlc_packs()                              # schematic hash -> [DLC pack names]
        self.vanity = site.data("vanity")
        self.anchor = {}                                                 # stock raw -> path#anchor (registered)

    # ---------------------------------------------------------------- schematics
    def _product(self, s):
        """The stock item a schematic makes: its internal name is 'schematic_' + the item's (with or without a
        '_q1' / '_q6' rank suffix or an 'equipment_' prefix); apparel schematics make no item."""
        if s["t"] == "apparel":
            return None
        k = re.sub(r"^schematic_", "", s["k"])
        base = re.sub(r"_q\d$", "", k)
        for c in (k, base, "equipment_" + k, "equipment_" + base):
            if c in self.by_raw:
                return self.by_raw[c]
        hits = [e for e in self.stock if norm(e["name"]) == norm(s["n"])]
        return hits[0] if hits else None

    def _recipe(self, s):
        """'8 Adhesive, 1 Bullet-Resistant Pants (rank 1)' -> [(8, 'Adhesive', ('material', stock)), (1, '...',
        ('schematic', previous rank))]. ref is None for a name nothing matches."""
        out = []
        for part in s["r"].split(", "):
            m = re.match(r"(\d+) (.+)$", part.strip())
            if not m:
                continue
            amount, name = int(m.group(1)), m.group(2)
            ref = None
            rank = re.match(r"(.+) \(rank (\d+)\)$", name)
            if rank:   # the same garment with the previous rank of the apparel upgrade on it
                prev = next((self.sch_by_hash[p] for p in s["pre"] if self.sch_by_hash[p]["q"] == int(rank.group(2))),
                            None)
                ref = ("schematic", prev) if prev else None
            else:
                hits = self.by_name.get(norm(name), [])
                if hits:
                    ref = ("material" if hits[0]["g"] == "materials" else "item", hits[0])
            out.append((amount, name, ref))
        return out

    def _dlc_packs(self):
        """The DLC pack of each DLC schematic. The schematics carry no pack, but the weapon data
        (stats.json player_weapons[...]['pack']) does: a schematic that makes a weapon (the Molotov Cocktail) or ammo
        a DLC weapon fires gets that weapon's pack, and every DLC schematic of the same path gets the packs found in
        that path. A path with no such schematic (the second gadget path) stays a plain 'DLC'."""
        by_product = collections.defaultdict(set)    # stock raw or norm(weapon name) -> pack names
        for cat in self.site.data("stats")["player_weapons"].values():
            for wname, w in cat.items():
                pack = w.get("pack") or ""
                if not pack.endswith("(DLC)"):
                    continue
                pack = pack[:-5].strip()
                by_product[norm(wname)].add(pack)
                for a in w.get("ammo", []):
                    if isinstance(a, dict) and a.get("internal_name"):
                        by_product[a["internal_name"]].add(pack)
        out = {}
        for t in self.trees:
            for g in t["groups"]:
                for r in g["rows"]:
                    nodes = [self.sch_by_hash[h] for h in r["nodes"] if self.sch_by_hash[h].get("dlc")]
                    packs = set()
                    for sc in nodes:
                        p = self.product[sc["h"]]
                        if p:
                            packs |= by_product.get(p["raw"], set()) | by_product.get(norm(p["name"]), set())
                    for sc in nodes:
                        out[sc["h"]] = sorted(packs)
        return out

    def tree_items(self, tree):
        return [self.sch_by_hash[h] for g in tree["groups"] for r in g["rows"] for h in r["nodes"]]

    def path_cost(self, s):
        """Points to unlock this schematic and everything it needs first."""
        seen, todo, total = set(), [s["h"]], 0
        while todo:
            h = todo.pop()
            if h in seen:
                continue
            seen.add(h)
            total += self.sch_by_hash[h]["c"]
            todo += self.sch_by_hash[h]["pre"]
        return total

    def tree_of(self, s):
        return next(t for t in self.trees if t["key"] == s["t"])

    # ---------------------------------------------------------------- placed loot
    def _loot(self):
        """stock raw -> Counter(region -> placed pickups) for the loot_items / loot_materials subs of loot.json.
        A sub is matched to the stock item by its name (the 'Radio' sub carries the Field Radio's internal name
        in the data, but its name and count are those of the plain Radio)."""
        lo = self.site.data("loot")
        out = collections.defaultdict(collections.Counter)
        sub_item = {}
        for i, sb in enumerate(lo["subs"]):
            if sb["main"] not in ("loot_items", "loot_materials"):
                continue
            hits = self.by_name.get(norm(sb["name"]))
            e = hits[0] if hits else self.by_raw.get(sb.get("item"))
            if e:
                sub_item[i] = e["raw"]
        for row in lo["items"]:
            raw = sub_item.get(row[0])
            if raw:
                y = row[5] if len(row) > 5 else None
                out[raw][lo["regions"][row[4]]] += len(y) if isinstance(y, list) else 1
        return out

    def placed(self, raw):
        return sum(self.loot.get(raw, {}).values())


_MODEL = None


def model(site):
    global _MODEL
    if _MODEL is None or _MODEL.site is not site:
        _MODEL = Model(site)
    return _MODEL


# ---------------------------------------------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------------------------------------------
def plural(n, one, many=None):
    """'1 item', '3 items' (many defaults to one + 's')."""
    return f"{fmt(n)} {one if n == 1 else (many or one + 's')}"


def and_list(parts):
    """['a', 'b', 'c'] -> 'a, b and c'."""
    return ", ".join(parts[:-1]) + " and " + parts[-1] if len(parts) > 1 else "".join(parts)


def dlc_tags(site, m, s):
    """DLC tag(s) of a schematic: one per pack the weapon data names for its path (linked to the DLC page when the
    home section registers the pack), or a plain 'DLC' tag."""
    packs = m.dlc_packs.get(s["h"]) or []
    if not packs:
        return tag("DLC", "dlc")
    out = []
    for p in packs:
        url = site.url("dlc", p)
        t = tag(p, "dlc")
        out.append(f'<a href="{esc(url)}">{t}</a>' if url else t)
    return " ".join(out)


def stock_icon(site, e, cls="ii"):
    return site.img(e["icon"].replace("assets/", "img/", 1), alt="", cls=cls) if e and e.get("icon") else ""


def sch_anchor(s):
    return "s-" + slug(s["k"])


def item_anchor(e):
    return "i-" + slug(e["raw"])


def mat_anchor(e):
    return "m-" + slug(e["raw"])


def sch_link(site, s, text=None):
    """Link to a schematic's row on the schematics page (by hash, so ranks never mix up)."""
    if not s:
        return "–"
    label = text if text is not None else s["n"] + (f" (rank {s['q']})" if s["t"] == "apparel" else "")
    return site.link("schematic", str(s["h"]), text=label)


def item_link(site, e, text=None, icon=False):
    """Link to a stock entry: materials and items are ours, ammo belongs to the ammo section."""
    if e["g"] == "ammo":
        return site.link("ammo", e["name"], text=text)
    if e["g"] == "materials":
        return site.link("material", e["raw"], text=text if text is not None else e["name"], icon=icon)
    return site.link("item", e["raw"], text=text if text is not None else e["name"], icon=icon)


def recipe_html(site, m, s):
    """Recipe as chips: icon, amount and a link per ingredient."""
    out = []
    for amount, name, ref in m.recipes[s["h"]]:
        if ref and ref[0] == "schematic":
            out.append(f'<span class="ing">{amount}× {esc(name.split(" (rank")[0])} with '
                       f'{sch_link(site, ref[1], "rank " + str(ref[1]["q"]))}</span>')
        elif ref:
            out.append(f'<span class="ing">{stock_icon(site, ref[1], "ingi")}{amount}× {item_link(site, ref[1])}</span>')
        else:
            out.append(f'<span class="ing">{amount}× {esc(name)}</span>')
    return " ".join(out)


def game_text(d):
    """A schematic description as the item's description: 'Item crafting schematic that makes simple first aid
    kits that ...' -> 'Simple first aid kits that ...'. 'PROPERTIES: - X: ...' gets a line of its own."""
    t = re.sub(r"^Apparel crafting schematic that makes ", "Makes ", d.strip())     # 'Makes pants more ...'
    t = re.sub(r"^(Experimental )?(Item|Ammo)( crafting)? schematic that makes (an? )?", "", t)
    t = t[:1].upper() + t[1:]
    t = esc(t)
    return re.sub(r"\s*PROPERTIES:\s*-\s*", "<br><b>Properties:</b> ", t)


def says_nothing(text, name):
    """True when a description only repeats the name: 'Makes .32 ACP Hollow-Point Ammo.', 'Sensory Jammer.'."""
    t = norm(re.sub(r"<[^>]+>", "", text).strip().rstrip("."))
    t = re.sub(r"^makes ", "", t)
    n = norm(name)
    return t in (n, n + "s")


def flags_html(site, m, s):
    out = []
    if s.get("free"):
        out.append(tag("Free", "green"))
    if s.get("dlc"):
        out.append(dlc_tags(site, m, s))
    return " ".join(out)


def pack_link(site, p):
    e = site.find("pack", str(p))
    if e:
        return f'<a href="~/{esc(e["path"])}">{esc(e["title"])}</a>'
    site.url("pack", str(p))   # records the missing target in the build report
    base = site.data("vanity")["base_pack"]
    return "Base game" if p == base else f"Content pack <code>{p}</code>"


def row_table(headers, rows, attrs, cls="", num=None):
    """table() with attributes on each <tr> (anchors, filter tags): attrs[i] is the attribute string of row i."""
    html = table(headers, rows, cls=cls, num=num)
    # a cell that starts with '<!--v:N-->' sorts by N (a number followed by more text)
    html = re.sub(r'<td class="n"><!--v:(-?[\d.]+)-->', r'<td class="n" data-v="\1">', html)
    head, body = html.split("<tbody>", 1)
    parts = body.split("<tr>")
    return head + "<tbody>" + parts[0] + "".join(f"<tr{attrs[i]}>" + p for i, p in enumerate(parts[1:]))


def region_counts(c):
    """'Forest 67 · Himfjäll 57 · ...' (biggest first)."""
    return " · ".join(f"{esc(REGION_SHORT.get(r, r))} {n}" for r, n in c.most_common())


# ---------------------------------------------------------------------------------------------------------------
# collect: register every item, material and schematic
# ---------------------------------------------------------------------------------------------------------------
def collect(site):
    m = model(site)
    for e in sorted(m.items, key=lambda e: e["raw"]):
        if e["sub"] == COMPANION_GROUP:
            path = "items/companion.html#c-" + slug(e["raw"])
        else:
            path = "items/index.html#" + item_anchor(e)
        m.anchor[e["raw"]] = path
        key = e["name"]
        if site.find("item", key):   # a second item with the same name (armor qualities, 'Storage Key')
            key = e["raw"]
        s = m.schem_for_raw.get(e["raw"])
        desc = f"{e['sub']} · stack {e['stack']}" + (f" · crafted with the {s['n']} schematic" if s else "")
        site.register("item", key, path, e["name"], icon=e["icon"].replace("assets/", "img/", 1), desc=desc,
                      aliases=[e["raw"], str(e["h"])], keywords=f"item equipment {e['raw']} {e['sub']}",
                      search=key == e["name"])
    juice = m.by_raw.get("equipment_comp_repairgun_ammo")   # ammo in the item list, but companion gear
    if juice:
        path = "items/companion.html#c-" + slug(juice["raw"])
        m.anchor[juice["raw"]] = path
        site.register("item", juice["name"], path, juice["name"], icon=juice["icon"].replace("assets/", "img/", 1),
                      desc=f"Companion repair tool ammo · stack {juice['stack']}",
                      aliases=[juice["raw"], str(juice["h"])],
                      keywords=f"item companion repair {juice['raw']}")
    for e in m.materials:
        path = "items/materials.html#" + mat_anchor(e)
        m.anchor[e["raw"]] = path
        n_use = len(m.uses.get(e["raw"], []))
        site.register("material", e["name"], path, e["name"], icon=e["icon"].replace("assets/", "img/", 1),
                      desc=f"Crafting material ({e['sub']}) · used by {n_use} schematics · stack {e['stack']}",
                      aliases=[e["raw"], str(e["h"])], keywords=f"material crafting {e['raw']} {e['sub']}")
    for t in m.trees:
        site.register("schematic", t["key"], f"items/schematics.html#tree-{t['key']}", f"{t['name']} schematic tree",
                      icon=TREE_ICON.format(t["key"]), search=False)
    for s in m.schem:
        key = s["n"] if not site.find("schematic", s["n"]) else s["k"]
        aliases = [str(s["h"]), s["k"]] + ([f"{s['n']} (rank {s['q']})"] if s["t"] == "apparel" else [])
        title = s["n"] + (f" (rank {s['q']})" if s["t"] == "apparel" else "")
        site.register("schematic", key, f"items/schematics.html#{sch_anchor(s)}", title,
                      icon="img/schematics/" + s["i"], aliases=aliases,
                      desc=f"{m.tree_of(s)['name']} schematic · {s['c']} points · {s['r']}",
                      keywords=f"schematic crafting recipe {s['k']}", search=key == s["n"])


def build(site):
    m = model(site)
    build_equipment(site, m)
    build_materials(site, m)
    build_schematics(site, m)
    build_companion(site, m)


# ---------------------------------------------------------------------------------------------------------------
# items/index.html: equipment
# ---------------------------------------------------------------------------------------------------------------
def equipment_row(site, m, e):
    """Cells of one equipment row: icon, name, stack, schematic, what it does, placed, internal name."""
    s = m.schem_for_raw.get(e["raw"])
    name = f"<b>{esc(e['name'])}</b>"
    w = site.find("weapon", e["name"])
    if w:
        name += f'<br><span class="small">{site.link("weapon", e["name"], text="Damage & weapon page")}</span>'
    if s and s.get("dlc"):
        name += " " + dlc_tags(site, m, s)
    if s:
        cur = m.currency.get(m.tree_of(s)["cur"])
        ic = site.img(TREE_ICON.format(s["t"]), alt="", cls="cur", title=cur["name"] if cur else "")
        cost = "free" if s["c"] == 0 else f"{s['c']} pt{'s' if s['c'] != 1 else ''}"
        sch = f'{ic}{sch_link(site, s)}<br><span class="small dim">{esc(m.tree_of(s)["name"])} · {cost}</span>' \
              f'<div class="small">{recipe_html(site, m, s)}</div>'
        what = game_text(s["d"])
        if says_nothing(what, e["name"]):   # the DLC gadgets' text only repeats the name
            what = GADGET_DESC.get(e["raw"], '<span class="dim">–</span>')
        else:
            what = f'<span class="gtext">{what}</span>'
    else:
        sch = '<span class="dim">–</span>'
        what = MANUAL_DESC.get(e["raw"], '<span class="dim">–</span>')
    placed = m.placed(e["raw"])
    regs = f'<span class="small dim regs">{region_counts(m.loot[e["raw"]])}</span>'
    placed_html = f'<!--v:{placed}-->{fmt(placed)}{regs}' if placed else None   # sorts by the count
    return [stock_icon(site, e), name, e["stack"], sch, what, placed_html,
            f"<code>{esc(e['raw'])}</code><br><code class=\"dim\">{e['h']}</code>"]


def build_equipment(site, m):
    by_sub = collections.defaultdict(list)
    for e in m.items:
        by_sub[e["sub"]].append(e)
    n_equip = sum(len(by_sub[g]) for g, _, _ in EQUIP_GROUPS)
    n_craft = sum(1 for g, _, _ in EQUIP_GROUPS for e in by_sub[g] if e["raw"] in m.schem_for_raw)
    body = []
    body.append(bar("How to read the tables", id="reading"))
    body.append(
        "<p>One table per group of the inventory. <b>Stack</b> is how many fit in one inventory slot. "
        "<b>Schematic</b> is the crafting schematic that makes the item, with the tree it sits in, what it costs to "
        "unlock and the materials one craft takes. <b>What it does</b> is the game's own schematic text where there "
        "is a schematic (marked with a bar on the left), and a short plain description otherwise (also for the "
        "DLC gadgets, whose schematic text only repeats their name). "
        "<b>Placed</b> is how many of the item lie at fixed spots in the world files, with the regions under the "
        "number (random loot from crates, bodies and machines comes on top). The internal name and item hash are "
        "what save editors and mods use.</p>")
    chips = "".join(f'<button class="chip" data-g="g" data-f="{k}">{esc(g)}</button>' for g, k, _ in EQUIP_GROUPS)
    body.append(f'<div class="filterbar" data-for="equip"><input placeholder="Filter equipment..." '
                f'aria-label="Filter equipment"><button class="chip on" data-g="g" data-f="*">All</button>{chips}'
                f'<button class="chip" data-g="d" data-f="craft">Craftable</button>'
                f'<button class="chip" data-g="d" data-f="dlc">DLC</button><span class="count"></span></div>')
    body.append('<div id="equip">')
    headers = ["", "Item", "Stack", "Schematic", "What it does", "Placed", "Internal name / hash"]
    for g, k, intro in EQUIP_GROUPS:
        items = sorted(by_sub[g], key=lambda e: e["name"].lower())
        body.append(bar(g, f"{len(items)} items", id=k))
        body.append(f"<p>{intro}</p>")
        rows, attrs = [], []
        for e in items:
            s = m.schem_for_raw.get(e["raw"])
            f = [k] + (["craft"] if s else []) + (["dlc"] if s and s.get("dlc") else [])
            rows.append(equipment_row(site, m, e))
            attrs.append(f' id="{item_anchor(e)}" data-f="{" ".join(f)}" data-w="{esc(e["raw"])} {e["h"]}"')
        body.append(row_table(headers, rows, attrs, cls="equip", num={2, 5}))
        if k == "lure":
            body.append(radio_note(site, m))
    body.append("</div>")
    body.extend(equipment_extras(site, m, by_sub))
    lead = (f"<p>Every piece of equipment in the game's item list: {n_equip} items in {len(EQUIP_GROUPS)} groups, "
            f"{n_craft} of which you can craft once you have unlocked their schematic. Each row has the stack size, "
            f"the schematic with its recipe, what the item does, how many are placed in the world and the internal "
            f"name. Keys and quest items and the companion's gear are on their own pages.</p>")
    site.page("items/index.html", "Equipment", "".join(body), "items", lead=lead, head_extra=CSS, wide=True,
              desc="Every Generation Zero equipment item: stack sizes, crafting schematics and recipes, what each "
                   "item does, placed loot counts and internal names.",
              search={"k": "Items", "w": "equipment items consumables throwables lures gadgets"})


def radio_note(site, m):
    """The world files' 'Radio' pickups carry the Field Radio's internal name; say how they are counted."""
    lo = site.data("loot")
    sub = next((sb for sb in lo["subs"] if sb["key"] == "loot_i_radio"), None)
    field = next((sb for sb in lo["subs"] if sb["key"] == "loot_i_field_radio_01"), None)
    if not sub or sub.get("item") != "field_radio_01":
        return ""
    radio, fr = m.by_raw.get("lure_radio_equipment"), m.by_raw.get("field_radio_01")
    extra = f", and the {item_link(site, fr)}'s own {fmt(field['count'])} are separate" if field and fr else ""
    return note(f"The world files' <i>Radio</i> pickups ({fmt(sub['count'])}) carry the Field Radio's internal name "
                f"(<code>field_radio_01</code>). They are counted as the plain "
                f"{item_link(site, radio) if radio else 'Radio'} here{extra}.", "data")


def equipment_extras(site, m, by_sub):
    """Tips from the numbers, the keys summary and the pointer to the companion page."""
    out = [bar("Tips from the numbers", id="tips")]
    placed = sorted(((m.placed(e["raw"]), e) for g, _, _ in EQUIP_GROUPS for e in by_sub[g] if m.placed(e["raw"])),
                    key=lambda x: -x[0])
    top = ", ".join(f"{item_link(site, e)} ({n})" for n, e in placed[:5])
    tips = [f"The items lying around most often at fixed spots are {top}."]
    rare = [(n, e) for n, e in placed if n <= 2]
    rare_craft = ", ".join(f"{item_link(site, e)} ({n})" for n, e in rare if e["raw"] in m.schem_for_raw)
    rare_loot = ", ".join(f"{item_link(site, e)} ({n})" for n, e in rare if e["raw"] not in m.schem_for_raw)
    if rare_craft:
        tips.append(f"Some are almost never placed by hand: {rare_craft}. Craft those instead of hoping to find "
                    f"them.")
    if rare_loot:
        tips.append(f"{rare_loot} {'are' if ',' in rare_loot else 'is'} just as rarely placed and "
                    f"{'have' if ',' in rare_loot else 'has'} no schematic either, so random loot is the main "
                    f"way to get {'them' if ',' in rare_loot else 'it'}.")
    adr = m.schem_for_raw.get("equipment_consumable_adrenaline_01")
    if adr:
        tips.append(f"The {sch_link(site, adr)} is the last schematic of the equipment tree: it costs "
                    f"{adr['c']} points by itself and {m.path_cost(adr)} points with everything before it.")
    stacks = collections.Counter(e["stack"] for g, _, _ in EQUIP_GROUPS for e in by_sub[g])
    gas = m.by_raw.get("equipment_consumable_fuelcan_01")
    if gas:
        tips.append(f"{item_link(site, gas)} stacks to {gas['stack']}, more than anything else here; the "
                    f"{sch_link(site, m.schem_for_raw.get(gas['raw']))} recipe makes it from accelerant and lead, and "
                    f"the Explosive Gas Tank recipe takes 100 of it.")
    out.append("<ul>" + "".join(f"<li>{t}</li>" for t in tips) + "</ul>")
    out.append(f"<p class=\"small dim\">Stack sizes in this list: "
               + ", ".join(f"{k} ({plural(v, 'item')})" for k, v in sorted(stacks.items())) + "."
               + (" The stack of 0 is the Machine Companion, which you never carry as an item." if 0 in stacks else "")
               + "</p>")

    keys = sorted(by_sub[KEYS_GROUP], key=lambda e: e["name"].lower())
    out.append(bar(KEYS_GROUP, f"{len(keys)} items", id="keys"))
    keys_url = site.url("key", keys[0]["raw"]) if keys else None
    page = f'<a href="{esc(keys_url.split("#")[0])}">Keys &amp; barcodes page</a>' if keys_url else "Keys & barcodes page"
    out.append(f"<p>{len(keys)} items in the game's list are keys, bunker barcodes, keycards and things a mission "
               f"hands you. They have their own {page} with what each one opens, its content pack and the missions "
               f"that use it. Here they are at a glance; most tiles link to their entry there.</p>")
    tiles = []
    in_keys = {k["r"] for k in site.data("keys")["items"]}   # a few are only in the item list, not in keys.json
    for e in keys:
        u = site.url("key", e["raw"]) if e["raw"] in in_keys else None
        test = tag("Test item", "unreleased") if e["raw"] in TEST_ITEMS else ""
        inner = (f'{stock_icon(site, e, "")}<span>{esc(e["name"])}</span>{test}'
                 f'<span class="dim"><code>{esc(e["raw"])}</code></span>')
        tiles.append(f'<a class="icon" id="{item_anchor(e)}" href="{esc(u)}">{inner}</a>' if u else
                     f'<div class="icon" id="{item_anchor(e)}">{inner}</div>')
    out.append('<div class="icongrid keygrid">' + "".join(tiles) + "</div>")

    comp = by_sub[COMPANION_GROUP]
    out.append(bar("Companion items", f"{len(comp)} items", id="companion"))
    out.append(f"<p>{len(comp)} more items belong to the machine companion: its armor, paint jobs, light kits, voice "
               f"boxes, modules and weapons. They are on the <a href=\"~/items/companion.html\">Companion page</a>, "
               f"with the companion armor schematics and the packs the cosmetics come from.</p>")
    return out


# ---------------------------------------------------------------------------------------------------------------
# items/materials.html
# ---------------------------------------------------------------------------------------------------------------
def material_need(m, e):
    """(schematics using it, total amount to craft every one of them once)."""
    uses = m.uses.get(e["raw"], [])
    return len(uses), sum(a for _, a in uses)


def build_materials(site, m):
    by_sub = collections.defaultdict(list)
    for e in m.materials:
        by_sub[e["sub"]].append(e)
    body = [bar("All materials", f"{len(m.materials)} materials", id="all")]
    body.append("<p>The overview. <b>Schematics</b> counts the schematics whose recipe asks for the material, and "
                "<b>Total for one of each</b> adds up what crafting every one of those schematics once would take "
                "(the apparel ranks count once each). <b>Placed</b> is how many pickups of it lie at fixed spots in "
                "the world files; most materials come from crates, bodies and destroyed machines instead, which "
                "are random. Click a name for the full list of schematics.</p>")
    chips = "".join(f'<button class="chip" data-g="g" data-f="{k}">{esc(g)}</button>' for g, k, _ in MAT_GROUPS)
    body.append(f'<div class="filterbar" data-for="mats"><input placeholder="Filter materials..." '
                f'aria-label="Filter materials"><button class="chip on" data-g="g" data-f="*">All</button>{chips}'
                f'<span class="count"></span></div>')
    rows, attrs = [], []
    gkey = {g: k for g, k, _ in MAT_GROUPS}
    for g, k, _ in MAT_GROUPS:
        for e in sorted(by_sub[g], key=lambda e: e["name"]):
            n, total = material_need(m, e)
            rows.append([stock_icon(site, e), f'<a href="#{mat_anchor(e)}">{esc(e["name"])}</a>', esc(g),
                         e["stack"], n if n else None, total if total else None, m.placed(e["raw"]) or None,
                         f"<code>{esc(e['raw'])}</code>"])
            attrs.append(f' data-f="{gkey[g]}"')
    body.append('<div id="mats">' + row_table(["", "Material", "Group", "Stack", "Schematics", "Total for one of each",
                                               "Placed", "Internal name"], rows, attrs, cls="compact",
                                              num={3, 4, 5, 6}) + "</div>")
    body.extend(material_tips(site, m))
    for g, k, intro in MAT_GROUPS:
        body.append(bar(g, f"{len(by_sub[g])} materials", id=k))
        body.append(f"<p>{intro}</p>")
        for e in sorted(by_sub[g], key=lambda e: e["name"]):
            body.append(material_block(site, m, e))
    body.extend(material_loot(site, m))
    lead = (f"<p>The {len(m.materials)} crafting materials of the game, in the four groups of the inventory. For each "
            f"one: its stack size, every schematic that uses it and how much, and where it lies placed in the world. "
            f"The numbers are read from the schematic recipes and the world files.</p>")
    site.page("items/materials.html", "Materials", "".join(body), "items", lead=lead, head_extra=CSS,
              desc="Generation Zero crafting materials: which schematics use each material and how much, stack "
                   "sizes, internal names and placed pickups per region.",
              search={"k": "Items", "w": "materials crafting resources alloys"})


def material_tips(site, m):
    out = [bar("Tips from the numbers", id="tips")]
    need = sorted(((material_need(m, e), e) for e in m.materials), key=lambda x: -x[0][1])
    top = ", ".join(f"{item_link(site, e)} ({fmt(t)} in {n} schematics)" for (n, t), e in need[:4])
    unused = [e for (n, t), e in need if n == 0]
    by_count = sorted(((material_need(m, e)[0], e) for e in m.materials), key=lambda x: -x[0])
    top_n, top_e = by_count[0]
    in_apparel = sum(1 for sc, _ in m.uses[top_e["raw"]] if sc["t"] == "apparel")
    tips = [f"By total amount the most wanted materials are {top}. Keep a good stock of them.",
            f"{item_link(site, top_e)} is in the most recipes ({top_n}), {in_apparel} of them apparel upgrades."]
    if unused:
        tips.append("No schematic in the current game files asks for "
                    + ", ".join(item_link(site, e) for e in unused) + ".")
    for e in m.materials:   # where the refined alloys are needed
        if not e["raw"].startswith("refined_"):
            continue
        where = collections.OrderedDict()
        for sc, _ in m.uses.get(e["raw"], []):
            label = m.tree_of(sc)["name"].lower() + (f" rank {sc['q']}" if sc["t"] == "apparel" else "")
            where[label] = where.get(label, 0) + 1
        tips.append(f"{item_link(site, e)} is only asked for by "
                    + ", ".join(f"{esc(k)} ({v} schematic{'s' if v != 1 else ''})" for k, v in where.items()) + ".")
    out.append("<ul>" + "".join(f"<li>{t}</li>" for t in tips) + "</ul>")
    return out


def material_block(site, m, e):
    """One material: icon, facts and the schematics that use it, by tree."""
    uses = m.uses.get(e["raw"], [])
    n, total = material_need(m, e)
    placed = m.placed(e["raw"])
    facts = [("Group", esc(e["sub"])), ("Stack", fmt(e["stack"])), ("Internal name", f"<code>{esc(e['raw'])}</code>"),
             ("Hash", f"<code>{e['h']}</code>"),
             ("Used by", f"{n} schematics, {fmt(total)} for one of each" if n else "no schematic"),
             ("Placed", f"{placed}: {region_counts(m.loot[e['raw']])}" if placed else "none at fixed spots")]
    facts_html = "".join(f'<span><i>{esc(k)}</i> {v}</span>' for k, v in facts)
    out = [f'<div class="matblock" id="{mat_anchor(e)}"><div class="mathead">{stock_icon(site, e, "mati")}'
           f'<h3>{esc(e["name"])}</h3></div><div class="facts">{facts_html}</div>']
    if uses:
        by_tree = collections.OrderedDict((t["key"], []) for t in m.trees)
        for s, a in uses:
            by_tree[s["t"]].append((s, a))
        parts = []
        for t in m.trees:
            lst = by_tree[t["key"]]
            if not lst:
                continue
            items = "".join(f'<li>{sch_link(site, s)} <span class="dim">×</span> <b>{a}</b></li>' for s, a in lst)
            parts.append(f'<div class="usetree"><h4>{site.img(TREE_ICON.format(t["key"]), cls="cur")}{esc(t["name"])} '
                         f'<span class="dim">{len(lst)} · {fmt(sum(a for _, a in lst))} total</span></h4>'
                         f'<ul class="uselist">{items}</ul></div>')
        op = " open" if n <= 16 else ""
        out.append(f'<details{op}><summary>Schematics that use {esc(e["name"])} ({n})</summary>'
                   f'<div class="usetrees">{"".join(parts)}</div></details>')
    out.append("</div>")
    return "".join(out)


def material_loot(site, m):
    out = [bar("Placed materials by region", id="placed")]
    regs = [r for r in REGION_KEYS if any(m.loot[e["raw"]].get(r) for e in m.materials)]
    rows = []
    for e in sorted(m.materials, key=lambda e: -m.placed(e["raw"])):
        if not m.placed(e["raw"]):
            continue
        c = m.loot[e["raw"]]
        rows.append([f'{stock_icon(site, e)} <a href="#{mat_anchor(e)}">{esc(e["name"])}</a>']
                    + [c.get(r) or None for r in regs] + [m.placed(e["raw"])])
    out.append(f"<p>Material pickups at fixed spots in the world files, per region. Only {len(rows)} of the "
               f"{len(m.materials)} materials are placed by hand at all, and in small numbers: the bulk of your "
               f"materials comes from random loot in crates, on bodies and from destroyed machines. The interactive "
               f"map shows every one of these spots with <i>Additional Locations</i> on.</p>")
    out.append(table(["Material"] + [REGION_SHORT[r] for r in regs] + ["Total"], rows, cls="compact",
                     num=set(range(1, len(regs) + 2))))
    slag = m.by_raw.get("slag")
    if slag:
        out.append(note(f"{item_link(site, slag)} (<code>slag</code>, stack {slag['stack']}) looks like a material "
                        f"but the game files list it under <i>Other</i> items, and no schematic uses it.", "data"))
    gold = m.by_raw.get("gold")
    if gold and "uranium" in gold["icon"]:
        out.append(note("The game's item list gives Gold the Uranium icon, so the two look the same in the "
                        "inventory.", "data"))
    return out


# ---------------------------------------------------------------------------------------------------------------
# items/schematics.html
# ---------------------------------------------------------------------------------------------------------------
def build_schematics(site, m):
    body = [bar("The six trees", id="trees")]
    body.append("<p>Schematics are bought with schematic points. Each tree has its own kind of points, earned in its "
                "own way; within a path you unlock from left to right, each schematic needing the one before it. "
                "Once unlocked, a schematic can be crafted as often as you have materials for it. <b>Free</b> "
                "schematics are unlocked from the start.</p>")
    rows = []
    for t in m.trees:
        its = m.tree_items(t)
        cur = m.currency.get(t["cur"], {})
        rows.append([f'{site.img(TREE_ICON.format(t["key"]), cls="cur")}<a href="#tree-{t["key"]}">{esc(t["name"])}</a>',
                     esc(cur.get("name", "–")), esc(cur.get("earn", "–")), len(its),
                     sum(1 for s in its if s.get("free")) or None, sum(1 for s in its if s.get("dlc")) or None,
                     sum(s["c"] for s in its), max(s["c"] for s in its)])
    body.append(table(["Tree", "Currency", "How you earn it (game text)", "Schematics", "Free", "DLC", "Total points",
                       "Most expensive"], rows, cls="trees", num={3, 4, 5, 6, 7}))
    body.append(f"<p>All {len(m.schem)} schematics together cost {fmt(sum(s['c'] for s in m.schem))} points of the "
                f"six currencies.</p>")
    body.extend(schematic_pickups(site, m))
    for t in m.trees:
        body.extend(tree_section(site, m, t))
    lead = (f"<p>All {len(m.schem)} crafting schematics of the game, laid out like the SCHEMATICS menu: six trees, "
            f"each with its own currency, and inside each tree the paths you unlock from left to right. Below the "
            f"paths of each tree is a full table with every schematic's quality, cost, recipe, prerequisites, what it "
            f"makes and its internal name.</p>")
    site.page("items/schematics.html", "Schematics", "".join(body), "items", lead=lead, head_extra=CSS, wide=True,
              desc="Every Generation Zero crafting schematic: the six schematic trees and their currencies, costs, "
                   "recipes, prerequisites and internal names.",
              search={"k": "Items", "w": "schematics crafting recipes trees points"})


def schematic_pickups(site, m):
    """The schematic point pickups of markers.json, per region."""
    mk = site.data("markers")
    subs = [s for s in mk["subs"] if s["main"] == "schematics"]
    if not subs:
        return []
    counts = {s["key"]: collections.Counter(i["r"] for i in mk["items"] if i["s"] == s["key"]) for s in subs}
    regs = [r for r in REGION_KEYS if any(c.get(r) for c in counts.values())]
    out = [bar("Schematic points on the map", id="pickups")]
    out.append("<p>Besides the ways the game names, some schematic points lie in the world as pickups (a schematic "
               "magazine). Each pickup gives points of one currency; it doesn't unlock a particular schematic. The "
               "collectibles pages have a map and a list of every spot.</p>")
    rows = []
    for s in subs:
        c = counts[s["key"]]
        rows.append([site.link("collectible-type", s["key"], text=s["name"])] + [c.get(r) or None for r in regs]
                    + [sum(c.values())])
    totals = {k: sum(c.values()) for k, c in counts.items()}
    out.append(note("Older guides list schematic pickups that unlock one particular schematic. In the current game "
                    "files each pickup gives points of one currency ("
                    + and_list([f"{fmt(totals[sb['key']])} {esc(re.sub(r' schematics?$', '', sb['name'].lower()))}"
                                for sb in subs])
                    + " pickups), and you spend them in the trees.", "fix"))
    out.append(table(["Pickup"] + [REGION_SHORT[r] for r in regs] + ["Total"], rows, cls="compact",
                     num=set(range(1, len(regs) + 2))))
    app = m.currency.get(next((t["cur"] for t in m.trees if t["key"] == "apparel"), None), {})
    if "Rival" in app.get("earn", "") and counts.get("sch_apparel"):
        out.append(note(f"The game's text says Apparel Schematic Points are found as loot on Rivals; the world files "
                        f"also place {sum(counts['sch_apparel'].values())} apparel schematic point pickups.", "data"))
    return out


def tree_section(site, m, t):
    its = m.tree_items(t)
    cur = m.currency.get(t["cur"], {})
    total = sum(s["c"] for s in its)
    out = [bar(f"{t['name']} tree", f"{len(its)} schematics · {fmt(total)} points", id=f"tree-{t['key']}")]
    out.append(f'<div class="curbox">{site.img(TREE_ICON.format(t["key"]), alt="", cls="curbig")}<div>'
               f'<b>{esc(cur.get("name", t["name"]))}</b><p>{esc(cur.get("earn", ""))}</p>'
               f'<span class="small dim">Currency hash <code>{t["cur"]}</code> · unlocking the whole tree costs '
               f'{fmt(total)} points</span></div></div>')
    out.append(TREE_NOTES.get(t["key"], lambda site, m, t: "")(site, m, t))
    for g in t["groups"]:
        if len(t["groups"]) > 1 or g["name"] not in (f"{t['name']} schematic tree",):
            out.append(f'<h3 id="tree-{t["key"]}-{slug(g["name"])}">{esc(g["name"])}</h3>')
        out.append(path_grid(site, m, g))
        out.append(schematic_table(site, m, t, g))
    return out


def path_grid(site, m, g):
    """The rows of one group as in the game menu: row label, then the schematics left to right."""
    out = ['<div class="spaths">']
    for r in g["rows"]:
        nodes = [m.sch_by_hash[h] for h in r["nodes"]]
        cells = []
        for i, s in enumerate(nodes):
            cost = "free" if s.get("free") and s["c"] == 0 else f"{s['c']} pt{'s' if s['c'] != 1 else ''}"
            dlc = '<i class="ndlc">DLC</i>' if s.get("dlc") else ""
            cells.append(f'{"<i class=sparr>›</i>" if i else ""}<a class="snode q{s["q"]}" href="#{sch_anchor(s)}" '
                         f'title="{esc(s["n"])}: {esc(s["r"])}">{site.img("img/schematics/" + s["i"], cls="sni")}'
                         f'<span><b>{esc(s["n"])}</b><small>{qbadge(s["q"], short=True)} {cost}{dlc}</small></span></a>')
        out.append(f'<div class="sprow"><div class="splabel">{esc(r["name"])}{path_dlc(site, m, nodes)}<small>{len(nodes)} · '
                   f'{plural(sum(s["c"] for s in nodes), "pt")}</small></div><div class="spnodes">{"".join(cells)}</div></div>')
    out.append("</div>")
    return "".join(out)


def path_dlc(site, m, nodes):
    """The DLC pack tag(s) of a path whose schematics are DLC ('' for other paths)."""
    dlc = [n for n in nodes if n.get("dlc")]
    return f'<span class="pdlc">{dlc_tags(site, m, dlc[0])}</span>' if dlc else ""


def makes_html(site, m, s):
    p = m.product[s["h"]]
    if p:
        return f"{stock_icon(site, p, 'ingi')}{item_link(site, p)}"
    if s["t"] == "apparel":
        return f'<span class="dim">Clothing, rank {s["q"]}</span>'
    return "–"


def schematic_table(site, m, t, g):
    rows, attrs = [], []
    for r in g["rows"]:
        for h in r["nodes"]:
            s = m.sch_by_hash[h]
            pre = ", ".join(sch_link(site, m.sch_by_hash[p]) for p in s["pre"]) or '<span class="dim">–</span>'
            desc = game_text(s["d"])
            if says_nothing(desc, s["n"]):    # 'Makes .32 ACP Hollow-Point Ammo.' says nothing new
                p = m.product[s["h"]]
                desc = GADGET_DESC.get(p["raw"], "") if p else ""
            name = f'<b>{esc(s["n"])}</b> {flags_html(site, m, s)}' + (f'<div class="small dim sdesc">{desc}</div>' if desc else "")
            rows.append([site.img("img/schematics/" + s["i"], cls="ii"), name, esc(r["name"]),
                         qbadge(s["q"], short=True), s["c"], m.path_cost(s), recipe_html(site, m, s), pre,
                         makes_html(site, m, s), f"<code>{esc(s['k'])}</code><br><code class=\"dim\">{s['h']}</code>"])
            attrs.append(f' id="{sch_anchor(s)}"')
    headers = ["", "Schematic", "Path", "Q", "Cost", "With prereqs", "Recipe (one craft)", "Needs first", "Makes",
               "Internal name / hash"]
    return row_table(headers, rows, attrs, cls="schtab", num={4, 5})


# Extra prose per tree, from the numbers.
def _apparel_note(site, m, t):
    its = m.tree_items(t)
    ranks = sorted({s["c"] for s in its})
    first_row = t["groups"][0]["rows"][0]["nodes"]
    per_row = sum(m.sch_by_hash[h]["c"] for h in first_row)
    rows = sum(len(g["rows"]) for g in t["groups"])
    return (f"<p>Every apparel row has five ranks costing {', '.join(map(str, ranks))} points ({per_row} for a full "
            f"row; {rows} rows in all). An apparel schematic doesn't make a new garment, it improves one you have: "
            f"rank 1 adds the property, and the recipe of each higher rank takes a garment that already has the "
            f"rank below (listed as <i>1 … (rank N)</i>). Pants and shoes have an Athletic row and shoes a "
            f"Padded row; shirts and jackets don't.</p>")


def _experimental_note(site, m, t):
    its = m.tree_items(t)
    alloy = sum(1 for sc in its if any(ref and ref[1]["raw"].startswith("refined_")
                                       for _, _, ref in m.recipes[sc["h"]]))
    return ("<p>Experimental schematics make the quality-6 ammo and first aid kits with special properties "
            "(corrosion, tar, shock, HEAT, proximity explosives, medicine, radioactivity), described under each "
            f"schematic below. {alloy} of the {len(its)} recipes need a refined alloy per craft, so stock up on "
            "those before you spend your points.</p>")


def _companion_note(site, m, t):
    return ("<p>The companion tree makes armor for your machine companion: six kinds of armor in four qualities. "
            "Standard Runner Armor is free. The <a href=\"~/items/companion.html\">Companion page</a> has the armor "
            "together with everything else about the companion.</p>")


def _dlc_note(site, m, t):
    rows = [r for g in t["groups"] for r in g["rows"]]
    unknown = [r["name"] for r in rows if not any(m.dlc_packs.get(h) for h in r["nodes"])]
    multi = [r["name"] for r in rows if any(len(m.dlc_packs.get(h, [])) > 1 for h in r["nodes"])]
    out = ("<p>The DLC tree holds the schematics for the gear of the paid packs. The first schematic of every path is "
           "free, so owning the pack is all it takes to start; DLC points come from crafting DLC items.</p>"
           "<p>The schematics themselves don't name their pack. The pack shown on a path is the one the weapon data "
           "gives for the weapon or the ammo in that path (the Molotov Cocktail, or the weapons that fire the ammo).")
    if multi:
        out += f" The ammo of {' and '.join(multi)} is fired by weapons of two packs, so it shows both."
    if unknown:
        out += f" Nothing in the data names the pack of {' and '.join(unknown)}, so it stays a plain <i>DLC</i>."
    return out + "</p>\n"


def _equipment_note(site, m, t):
    return ("<p>The two schematics under <i>Not in a tree</i> (Gasoline for the motorbikes, and the Repair Kit) "
            "aren't part of any path: they cost nothing and are unlocked from the start.</p>")


TREE_NOTES = {"apparel": _apparel_note, "experimental": _experimental_note, "companion": _companion_note,
              "dlc": _dlc_note, "equipment": _equipment_note}


# ---------------------------------------------------------------------------------------------------------------
# items/companion.html
# ---------------------------------------------------------------------------------------------------------------
def build_companion(site, m):
    comp_items = [e for e in m.items if e["sub"] == COMPANION_GROUP]
    van = [v for v in m.vanity["items"] if v["g"] == "companion"]
    tricks = [v for v in m.vanity["items"] if v["g"] == "emotes" and v["s"] == "companion"]
    tree = next(t for t in m.trees if t["key"] == "companion")
    cur = m.currency.get(tree["cur"], {})
    body = []
    body.extend(companion_intro(site, m, tree, cur))
    body.extend(companion_armor(site, m, tree, cur))
    body.extend(companion_cosmetics(site, m, van))
    body.extend(companion_tricks(site, m, tricks))
    body.extend(companion_packs(site, m, van + tricks))
    n_cos = sum(1 for v in van if v["s"] != "armor")
    lead = (f"<p>Everything about the machine companion, the Runner that travels with you: the "
            f"{len(m.tree_items(tree))} armor schematics of the companion tree and what they cost in "
            f"{esc(cur.get('name', 'companion points'))}, the {len(comp_items)} companion items in the game's item "
            f"list, and the {n_cos} paint jobs, light kits, voice boxes, modules and weapons that change its looks "
            f"and kit, with the packs they come from.</p>")
    site.page("items/companion.html", "Companion", "".join(body), "items", lead=lead, head_extra=CSS,
              desc="The Generation Zero machine companion: armor schematics and costs, paint jobs, light kits, voice "
                   "boxes, modules, weapons, tricks, internal names and packs.",
              search={"k": "Items", "w": "companion runner pet dog armor paint voice light module"})


def companion_intro(site, m, tree, cur):
    out = [bar("The companion", id="companion")]
    out.append(f"<p>The companion is a {site.link('machine', 'Runner')} machine rebuilt to fight on your side. It "
               f"travels with you, carries some of your gear, can wear armor and does tricks.</p>")
    out.extend(companion_mission(site))
    spawner = m.by_raw.get("comp_spawner")
    repair = m.by_raw.get("equipment_comp_armor_repairpack")
    juice = m.by_raw.get("equipment_comp_repairgun_ammo")
    rows = []
    for e in (spawner, repair, juice):
        if not e:
            continue
        s = m.schem_for_raw.get(e["raw"])
        what = MANUAL_DESC.get(e["raw"], "").replace(" See the companion page.", "")
        if e["g"] == "ammo":
            what += f" Details on its {site.link('ammo', e['name'], text='ammo entry')}."
        rows.append([stock_icon(site, e), f'<b>{esc(e["name"])}</b>', e["stack"], esc(e["sub"]), what,
                     sch_link(site, s) if s else None,
                     f"<code>{esc(e['raw'])}</code><br><code class=\"dim\">{e['h']}</code>"])
    out.append("<p>The game's item list has the item behind the companion, a repair pack for its armor and the "
               "Repair Juice that the repair tool uses:</p>")
    attrs = [f' id="c-{slug(e["raw"])}"' for e in (spawner, repair, juice) if e]
    out.append(row_table(["", "Item", "Stack", "Group", "What it is", "Schematic", "Internal name / hash"], rows,
                         attrs, cls="compact", num={2}))
    out.append(f'<div class="curbox">{site.img(TREE_ICON.format("companion"), alt="", cls="curbig")}<div>'
               f'<b>{esc(cur.get("name", "Companion Schematic Points"))}</b><p>{esc(cur.get("earn", ""))}</p>'
               f'<span class="small dim">Currency hash <code>{tree["cur"]}</code></span></div></div>')
    return out


def companion_mission(site):
    """'Getting the companion': the main mission that builds it, with the three places listed in its description."""
    ms = site.data("missions")["missions"]
    mis = next((x for x in ms if x["name"] == "Making Friends"), None)
    if not mis:
        return []
    places = re.findall(r"^- (.+)$", mis.get("description", ""), re.M)
    parts = [st["name"].split("Pick up the ", 1)[1] for st in mis.get("steps", [])
             if st["name"].startswith("Pick up the ")]
    parts = [p.replace(" component", "") for p in parts]
    found = ""
    if places and len(parts) == len(places):
        found = " You collect three parts: " + and_list([f"the {esc(p)} at {esc(pl)}"
                                                          for p, pl in zip(parts, places)]) + "."
    station = next((st["name"] for st in mis.get("steps", []) if "companion station" in st["name"]), "")
    where = (" Then you " + esc(station[0].lower() + station[1:]) + ", assemble it there and deploy it."
             if station else "")
    reg = mis.get("region", "")
    return [f"<h3 id=\"getting\">Getting the companion</h3><p>You build it in the main mission "
            f"{site.link('mission', mis['name'])} ({site.link('region', reg, text=REGION_SHORT.get(reg, reg))}"
            f", story arc <i>{esc(mis.get('arc', ''))}</i>).{found}{where} The last steps of the mission have you "
            f"check its inventory, let it do a trick and build armor for it.</p>"]


def armor_type(raw):
    m = re.match(r"equipment_comp_armor_([a-z]+)_q(\d)$", raw)
    return (m.group(1), int(m.group(2))) if m else (None, None)


def companion_armor(site, m, tree, cur):
    its = m.tree_items(tree)
    total = sum(s["c"] for s in its)
    out = [bar("Armor", f"{len(its)} schematics · {fmt(total)} CSP", id="armor")]
    out.append("<p>Companion armor is crafted from the schematics of the companion tree: six kinds, each in four "
               "qualities (Standard, Improved, Superior, Exceptional; the armor items themselves carry the name "
               "without the quality word and stack to 2). Each row is one quality: the schematic, what it costs, "
               "the points for the whole row up to it, the materials for one piece and the item it makes. The line "
               "under each kind says what it is for, going by its name and how it plays: the game files don't hold "
               "the armor's protection values, only its name.</p>")
    for g in tree["groups"]:
        for r in g["rows"]:
            nodes = [m.sch_by_hash[h] for h in r["nodes"]]
            item = m.product[nodes[0]["h"]]
            dlc = " " + tag("DLC", "dlc") if any(s.get("dlc") for s in nodes) else ""
            vi = next((v for v in m.vanity["items"] if item and v["r"] == item["raw"]), None)
            pk = f' · Pack: {pack_link(site, vi["p"])}' if vi else ""
            out.append(f'<h3 id="armor-{slug(r["name"])}">{stock_icon(site, item, "mati")}{esc(r["name"])}{dlc}</h3>')
            kind, _ = armor_type(item["raw"]) if item else (None, None)
            if ARMOR_DESC.get(kind):
                out.append(f"<p>{ARMOR_DESC[kind]}</p>")
            out.append(f'<p class="small dim">{len(nodes)} qualities · {fmt(sum(s["c"] for s in nodes))} CSP for all '
                       f'of them{pk}</p>')
            rows, attrs = [], []
            for s in nodes:
                p = m.product[s["h"]]
                rows.append([site.img("img/schematics/" + s["i"], cls="ii"),
                             sch_link(site, s, s["n"]) + " " + flags_html(site, m, s),
                             qbadge(s["q"], short=True), s["c"], m.path_cost(s), recipe_html(site, m, s),
                             f"<code>{esc(p['raw'])}</code><br><code class=\"dim\">{p['h']}</code>" if p else "–"])
                attrs.append(f' id="c-{slug(p["raw"])}"' if p else "")
            out.append(row_table(["", "Schematic", "Q", "CSP", "With prereqs", "Recipe (one piece)", "Item / hash"],
                                 rows, attrs, cls="compact", num={3, 4}))
    out.extend(armor_tips(site, m, tree))
    return out


def armor_tips(site, m, tree):
    rows = [[m.sch_by_hash[h] for h in r["nodes"]] for g in tree["groups"] for r in g["rows"]]
    tips = []
    free = [r[0] for r in rows if r[0].get("free")]
    if free:
        tips.append(f"{sch_link(site, free[0], free[0]['n'])} is free; every other kind starts at "
                    f"{min(r[0]['c'] for r in rows if not r[0].get('free'))} CSP.")
    full = sorted(rows, key=lambda r: sum(s["c"] for s in r))
    tips.append(f"Taking one kind all the way to Exceptional costs {fmt(sum(s['c'] for s in full[0]))} CSP for "
                f"{esc(full[0][0]['n'].split(' ', 1)[1])} and {fmt(sum(s['c'] for s in full[-1]))} CSP for each of the "
                f"others, so pick the kind you want before spending.")
    tips.append("Each kind uses its own pair of materials, and the amount grows with quality: "
                + "; ".join(f"{esc(r[0]['n'].split(' ', 1)[1])}: "
                            + " + ".join(esc(n) for _, n, _ in m.recipes[r[0]["h"]]) for r in rows) + ".")
    return ["<ul>" + "".join(f"<li>{t}</li>" for t in tips) + "</ul>"]


def vanity_tile(site, v, anchor=True):
    label, cls, _ = LOCK_FLAG.get(v["l"], (v["l"], "base", ""))
    img = site.img("img/vanity/" + v["i"], alt="") if v.get("i") else ""
    aid = f' id="c-{slug(v["r"])}"' if anchor else ""
    return (f'<div class="icon ctile fitem"{aid} data-f="{v["s"]} {"dlc" if "D" in v["l"] else "nodlc"}" '
            f'data-w="{esc(v["r"])} {v["h"]}">{img}<span>{esc(v["n"])}</span>{tag(label, cls)}'
            f'<span class="dim small">{pack_link(site, v["p"])}</span><code class="small">{esc(v["r"])}</code></div>')


def unlocked_phrase(n, total):
    """'None of the 4 is unlocked ...', '1 of the 25 is ...', 'All 3 are ...', '7 of the 25 are ...'."""
    if n == 0:
        return f"None of the {total} is unlocked from the start."
    if n == total:
        return f"All {total} are unlocked from the start." if total > 1 else "It is unlocked from the start."
    return f"{n} of the {total} {'is' if n == 1 else 'are'} unlocked from the start."


def companion_cosmetics(site, m, van):
    out = [bar("Paint, lights, voice, modules and weapons", f"{sum(1 for v in van if v['s'] != 'armor')} items",
               id="cosmetics")]
    out.append("<p>These are unlocks of the vanity list, shared by all characters of a profile. Each tile shows the "
               "lock flag of the game's vanity table: <b>Default</b> items are unlocked from the start, <b>Locked</b> "
               "items are locked until you find or earn them, and <b>DLC</b> items come with a content pack. Under it "
               "is the pack the item belongs to, then its internal name.</p>")
    chips = "".join(f'<button class="chip" data-g="s" data-f="{k}">{esc(t)}</button>' for k, t, _ in COMP_SUBS)
    out.append(f'<div class="filterbar" data-for="cosm"><input placeholder="Filter companion items..." '
               f'aria-label="Filter companion items"><button class="chip on" data-g="s" data-f="*">All</button>{chips}'
               f'<button class="chip" data-g="d" data-f="dlc">DLC</button><span class="count"></span></div>')
    out.append('<div id="cosm">')
    for key, title, intro in COMP_SUBS:
        lst = sorted((v for v in van if v["s"] == key), key=lambda v: v["n"])
        if not lst:
            continue
        nd = sum(1 for v in lst if v["l"] == "U")
        out.append(f'<h3 id="{key}">{esc(title)} <span class="dim">{len(lst)}</span></h3>')
        out.append(f"<p>{intro} {unlocked_phrase(nd, len(lst))}</p>")
        out.append('<div class="icongrid cgrid">' + "".join(vanity_tile(site, v) for v in lst) + "</div>")
    out.append("</div>")
    out.append(bar("Companion items table", id="table"))
    out.append("<p>All companion items of the vanity list in one sortable table, with the item hash save editors use. "
               "Stack sizes come from the game's item list.</p>")
    sub_name = {k: t for k, t, _ in COMP_SUBS}
    sub_name["armor"] = "Armor"
    rows = []
    for v in sorted(van, key=lambda v: (v["s"], v["n"], v["r"])):
        e = m.by_raw.get(v["r"])
        label, cls, _ = LOCK_FLAG.get(v["l"], (v["l"], "base", ""))
        rows.append([site.img("img/vanity/" + v["i"], cls="ii") if v.get("i") else "",
                     f'<a href="#c-{slug(v["r"])}">{esc(v["n"])}</a>', esc(sub_name.get(v["s"], v["s"])),
                     tag(label, cls), pack_link(site, v["p"]), e["stack"] if e else None,
                     f"<code>{esc(v['r'])}</code>", f"<code>{v['h']}</code>"])
    out.append(table(["", "Item", "Type", "Lock flag", "Pack", "Stack", "Internal name", "Hash"], rows, cls="compact",
                     num={5}))
    out.append(note("The lock flag is the one the game's vanity table carries for each item (U, L, UD or LD); "
                    "“Default” is U, “Locked” is L, “DLC” is UD and “DLC · locked” is LD. Which mission, challenge "
                    "or crate gives a locked "
                    "item isn't part of this table.", "data"))
    return out


def companion_tricks(site, m, tricks):
    if not tricks:
        return []
    out = [bar("Companion tricks", f"{len(tricks)} emotes", id="tricks")]
    out.append("<p>Three emotes make the companion do a trick. They sit in the emote list with the gestures and "
               "dances.</p>")
    rows = []
    for v in sorted(tricks, key=lambda v: v["n"]):
        label, cls, _ = LOCK_FLAG.get(v["l"], (v["l"], "base", ""))
        rows.append([site.img("img/vanity/" + v["i"], cls="ii") if v.get("i") else "",
                     site.link("vanity", v["n"]), tag(label, cls), pack_link(site, v["p"]),
                     f"<code>{esc(v['r'])}</code>", f"<code>{v['h']}</code>"])
    out.append(table(["", "Emote", "Lock flag", "Pack", "Internal name", "Hash"], rows, cls="compact"))
    return out


def companion_packs(site, m, items):
    out = [bar("Packs", id="packs")]
    by_pack = collections.defaultdict(list)
    for v in items:
        by_pack[v["p"]].append(v)
    out.append("<p>The content packs the companion items belong to, with how many companion items each one "
               "holds.</p>")
    rows = []
    for p, lst in sorted(by_pack.items(), key=lambda x: -len(x[1])):
        kinds = collections.Counter(v["s"] for v in lst)
        label = {"paint": ("paint job", None), "light": ("light kit", None), "voice": ("voice box", "voice boxes"),
                 "module": ("module", None), "weapon": ("weapon", None), "armor": ("armor item", None),
                 "companion": ("trick", None)}
        rows.append([pack_link(site, p), len(lst),
                     ", ".join(plural(n, *label.get(k, (k, k))) for k, n in kinds.most_common()),
                     tag("DLC", "dlc") if any("D" in v["l"] for v in lst) else tag("Not DLC", "base")])
    out.append(table(["Pack", "Items", "What", "DLC"], rows, cls="compact", num={1}))
    return out
