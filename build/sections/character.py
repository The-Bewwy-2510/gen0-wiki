"""Character tab: skills, apparel, other vanity items (face paint, emotes, vehicles) and content packs.

Pages
    character/skills.html    gamedata.json skills: the four trees as columns like the game's skill menu, every skill
                             with icon, art, per-level effects, prerequisites and what it unlocks; skill point guide
    character/apparel.html   vanity.json group 'apparel': every clothing item, grouped into cards by slot + base
                             name + pack, with a filterable icon grid and a full item table
    character/vanity.html    face paint, emotes and vehicles (bike paint jobs) from vanity.json, plus summaries that
                             point to weapon skins (weapons section) and companion cosmetics (items section)
    character/packs.html     every content pack hash: name (from the data where it has one, otherwise inferred from
                             the contents), and everything in it (vanity.json + keys.json pack_items)

Kinds registered
    skill     key = skill name ('Reload Speed'), aliases = internal key (skill_01_02), upper-case name, hash
    apparel   key = item name (internal name when the name is taken), aliases = internal name, item hash; one extra
              searchable entry per card (base name, e.g. 'Adventurer fedora')
    vanity    every apparel, face paint, emote and vehicle item: key = name, aliases = internal name, hash
    pack      key = content pack hash as a string, alias = pack name

vanity.json item fields (meanings checked against the Gen0 Editor, editor/web/panes.js and inv_editor.py):
    h  item hash (EquipmentHash in Profile.ItemStash)     n  display name        r  internal name
    g  group (apparel, facepaint, skins, companion, vehicles, emotes)           s  sub group (slot / weapon / bike)
    p  content pack hash (vanity.json base_pack = base game)                     i  icon file in img/vanity/
    l  lock flag: 'U' starts unlocked, 'L' starts locked, a trailing 'D' marks downloadable content (the editor
       tags 'UD' and 'LD' items as DLC; the Gen0 Modder describes DLC skins as "unlocked from the start"). No game
       file defines it, so the readings are inferred; heads and hands (slot 'body') are all 'L' although you pick
       them in the character creator
    m  model hash, apparel only: colour variants of one piece of clothing share it (0 for heads and hands)
    x  body: 'F' / 'M' for the few items made for one body only (the editor shows FEMALE / MALE)
"""
import collections
import re

from wiki.site import esc, slug, norm, fmt, table, bar, note, kv, tag

CSS = '<link rel="stylesheet" href="~/assets/character.css">'
SKILLS = "character/skills.html"
APPAREL = "character/apparel.html"
VANITY = "character/vanity.html"
PACKS = "character/packs.html"

# Names for the content packs the data doesn't name, inferred from what is in them: (short label, long name).
# Where the internal names share a theme word it is used ('summer', 'fall', 'movies', 'raid' in char_part_*).
# The base game and the two expansions are named by the data (vanity.json base_pack, missions.json packs).
INFERRED = {
    1275017523: ("Summer", "Summer set: Midsummer, Miami and Adventurer apparel"),
    175186114: ("Easter & rain", "Easter, rain, workout and Timeless apparel"),
    157725165: ("Movies", "Movies set: Ecto-scientist, Interceptor, Xeno-specialist and Annihilator apparel"),
    741473295: ("Fall", "Fall set: Slayer's, Elegant, Antarctic and Worn apparel"),
    2276382681: ("Companion basics", "Companion basics: Runner parts, paint jobs, voice boxes and tricks"),
    4059682403: ("Experimental", "Experimental (raid) apparel set"),
    3513538084: ("Retro casual", "Retro casual set: band tee, bomber jacket, rolled-up jeans"),
    1081059118: ("Companion kits", "Companion kits: light kits, modules, plate armor and paint jobs"),
    1694085061: ("Story outfits", "Story outfits: hazard suit, FNIX machine pieces, Child of the Apocalypse"),
    3080402858: ("Sporty", "Sporty set: puffy sport jacket, tights and cyclist cap"),
    2503864856: ("Rewards", "Reward items: reward hats, varsity jacket, backpacks and two weapon skins"),
    3835143588: ("Flak bikes", "Flak bikes: Bruksflak, Stridsflak and Terrängflak paint jobs"),
    2781443650: ("Motorcycles", "Motorcycle paint jobs: Dirt Bike, Military Motorcycle, Resistance Custom"),
    3559300629: ("Camo skins", "Camouflage weapon skins"),
    532636854: ("FNIX skins & Apocalypse", "FNIX-themed weapon skins and the Apocalypse companion kit"),
    403227705: ("Soviet outfits", "Soviet Soldier and Soviet Exosuit outfits"),
    2403426898: ("Street Art", "Street Art weapon skins and two companion voice boxes"),
    1125639235: ("Cykel", "Cykel (bicycle) paint jobs"),
    2713648062: ("Flakmoped", "Flakmoped paint jobs"),
    941601146: ("Tuned Moped", "Tuned Moped paint jobs"),
    3516781347: ("Cyberpunk", "Cyberpunk outfit"),
    419370957: ("Varsity jacket", "Generation Zero varsity jacket (developer item)"),
    3867371168: ("Apparel crafting", "Apparel crafting: apparel schematics, crafting container key and materials"),
    485717896: ("Tracking device", "A single mission item (A tracking device)"),
}
PACK_CLASS = {"alpine": "alpine", "fnix": "fnix"}

# No game file defines the flag; these readings follow how the Gen0 Editor treats it (see the module docstring).
FLAG = {  # vanity.json 'l' -> (short label, explanation)
    "U": ("Starts unlocked", "every profile has it from the start"),
    "L": ("Starts locked", "not given automatically: found, earned, or chosen in the character creator"),
    "UD": ("DLC, given", "downloadable content that is unlocked as soon as you own the pack"),
    "LD": ("DLC, earned", "downloadable content that starts locked even when you own the pack"),
}
BODY = {"F": "Female body only", "M": "Male body only"}
SEP = ' <span class="sep">·</span> '   # list separator: many vanity names contain commas
GROUP_ORDER = ["apparel", "facepaint", "skins", "companion", "vehicles", "emotes"]


# ===============================================================================================================
# shared data helpers
# ===============================================================================================================
def van(site):
    return site.data("vanity")


def subs_of(site, group):
    """[(sub key, sub name)] of a vanity group, in the game's order."""
    g = next(g for g in van(site)["groups"] if g["key"] == group)
    return [(s["key"], s["name"]) for s in g["subs"]]


def items_of(site, group):
    return [i for i in van(site)["items"] if i["g"] == group]


def packs(site):
    """Content pack hash -> {short, name, inferred, cls, dlc}. Names from the data first, then INFERRED."""
    if hasattr(site, "_char_packs"):
        return site._char_packs
    v = van(site)
    out = {v["base_pack"]: {"short": "Base game", "name": "Base game", "inferred": False, "cls": "base", "dlc": None}}
    for p in site.data("missions")["packs"]:
        if p.get("dlc"):
            out[p["dlc"]] = {"short": p["name"], "name": p["name"], "inferred": False,
                             "cls": PACK_CLASS.get(p["key"], "dlc"), "dlc": p["name"]}
    hashes = {i["p"] for i in v["items"]} | {int(h) for h in v["packs"]} | \
             {int(h) for h in site.data("keys")["pack_items"]}
    for h in sorted(hashes):
        if h in out:
            continue
        short, name = INFERRED.get(h, (f"Pack {h}", f"Pack {h}"))
        dlc_items = any(i["p"] == h and i["l"].endswith("D") for i in v["items"])
        out[h] = {"short": short, "name": name, "inferred": True, "cls": "dlc" if dlc_items else "", "dlc": None}
    site._char_packs = out
    return out


def pack_tag(site, p, short=True):
    """The pack as a coloured tag that links to its section on the packs page."""
    pk = packs(site).get(p) or {"short": str(p), "cls": "", "inferred": True}
    hint = f'{pk.get("name", p)} · name inferred from contents' if pk.get("inferred") else pk.get("name", str(p))
    return (f'<a class="ptag" href="~/{PACKS}#pack-{p}" title="{esc(hint)}">'
            f'{tag(pk["short"] if short else pk["name"], pk["cls"])}</a>')


def plain_pack_tag(site, p):
    """The pack tag without a link (for the 1,200-row apparel table, where links would double the page size)."""
    pk = packs(site).get(p) or {"short": str(p), "cls": ""}
    return tag(pk["short"], pk["cls"])


def flag_tags(it):
    """Tags for the lock flag and the body restriction of a vanity item ('L' is the normal case: no tag)."""
    return lock_tag(it["l"]) + (tag(BODY[it["x"]].split(" body")[0]) if it.get("x") else "")


def lock_tag(l):
    return {"U": tag("Starts unlocked", "green"), "UD": tag("DLC", "dlc"),
            "LD": tag("DLC, earned", "dlc")}.get(l, "")


def flag_cell(l):
    label, why = FLAG.get(l, (l, ""))
    return f'<code>{esc(l)}</code> <span class="dim">{esc(label)}</span>'


def flag_counts(its):
    """'5 × DLC, earned · 1 × DLC, given' for a list of vanity items."""
    c = collections.Counter(i["l"] for i in its)
    if len(c) == 1:
        return esc(FLAG[next(iter(c))][0])
    return " · ".join(f"{n} × {esc(FLAG[l][0])}" for l, n in c.most_common())


def vimg(site, it, cls="vi"):
    """Icon of a vanity item (img/vanity/), or '' when it has none."""
    return site.img(f"img/vanity/{it['i']}", it["n"], cls=cls) if it.get("i") else ""


def first_free(site, kind, *keys):
    """The first of keys that isn't registered yet under kind (vanity names are not unique)."""
    for k in keys:
        if not site.find(kind, k):
            return k
    return keys[-1]


# ===============================================================================================================
# apparel cards: items grouped by slot + base name (text before the first comma) + pack
# ===============================================================================================================
# The generic per-slot icons that fit each apparel slot (first = the one to use). About 20 items carry another
# slot's generic icon in the game files (the Cyberpunk set shows the hat, some hats the shoes): swap those.
GENERIC = "generic_apparel_"
SLOT_ICONS = {"head": ["hat", "hair"], "eyes": ["glasses"], "face": ["face"], "neck": ["neck"], "jacket": ["top"],
              "shirt": ["shirt", "top"], "gloves": ["hands"], "wrists": ["wrist"], "pants": ["bottom"],
              "shoes": ["shoes"], "back": ["backpack"], "body": ["face", "hands"]}


def apparel_icon(it):
    """An apparel item's icon file, with a wrong slot's generic icon replaced by its own slot's."""
    icon = it.get("i")
    fits = SLOT_ICONS.get(it["s"])
    if not icon or not icon.startswith(GENERIC) or not fits:
        return icon
    if any(icon == f"{GENERIC}{f}_alpha.png" for f in fits):
        return icon
    return f"{GENERIC}{fits[0]}_alpha.png"


def apparel_cards(site):
    if hasattr(site, "_char_cards"):
        return site._char_cards
    order = {k: n for n, (k, _) in enumerate(subs_of(site, "apparel"))}
    groups = collections.OrderedDict()
    for it in sorted(items_of(site, "apparel"), key=lambda i: (order.get(i["s"], 99), i["n"].lower())):
        base = it["n"].split(", ")[0]
        groups.setdefault((it["s"], base, it["p"]), []).append(it)
    cards = []
    for (s, base, p), its in groups.items():
        icons = collections.Counter(apparel_icon(i) for i in its if i.get("i"))
        single = len(its) == 1
        c = {"slot": s, "base": base, "pack": p, "items": its, "single": single,
             "icon": icons.most_common(1)[0][0] if icons else None,
             "id": f"ap-{its[0]['h']}",
             "flags": sorted({i["l"] for i in its}), "body": {i.get("x") for i in its} - {None}}
        for i in its:
            # where an item's own link goes: its variant chip, or the card when the card is just that item
            i["_anchor"] = c["id"] if single else f"a-{i['h']}"
        cards.append(c)
    site._char_cards = cards
    return cards


def variant_label(it, base):
    rest = it["n"][len(base):].lstrip(", ").strip()
    return rest or it["n"]


# ===============================================================================================================
# collect
# ===============================================================================================================
def collect(site):
    collect_skills(site)
    collect_apparel(site)
    collect_vanity(site)
    for h, pk in packs(site).items():
        site.register("pack", str(h), f"{PACKS}#pack-{h}", pk["name"], aliases=[] if pk["inferred"] else [pk["name"]],
                      desc=f"Content pack {h}" + (" (name inferred from its contents)" if pk["inferred"] else ""),
                      keywords="content pack dlc " + pk["short"])
    for pack in weapon_packs(site):
        name = weapon_pack_name(pack)
        site.register("pack", name, f"{PACKS}#pack-{slug(name)}", name, aliases=[pack],
                      desc="Weapon DLC pack (named in the weapon stats)", keywords="dlc weapons pack")


def weapon_packs(site):
    """Named weapon packs from stats.json ('US Weapons Pack (DLC)' -> [(category, weapon name)]), base game left out.
    The stats file names these packs but doesn't give their content pack hashes."""
    out = collections.OrderedDict()
    for cat, ws in site.data("stats")["player_weapons"].items():
        for name, d in ws.items():
            pack = d.get("pack") if isinstance(d, dict) else None
            if pack and not pack.startswith("Base game"):
                out.setdefault(pack, []).append((cat, name))
    return out


def weapon_pack_name(pack):
    return pack.replace(" (DLC)", "")


def collect_skills(site):
    sk = site.data("gamedata")["skills"]
    for t in sk["trees"]:
        for col in t["cols"]:
            for sid in col:
                s = sk["list"][sid]
                site.register("skill", s["name"], f"{SKILLS}#{slug(s['name'])}", s["name"],
                              icon=s["icon"].replace("assets/", "img/", 1),
                              desc=f"{t['name'].title()} skill, max level {s['max']}. " + " ".join(skill_text(s)[0])[:100],
                              aliases=[sid, s["upper"], str(s["hash"])],
                              keywords=f"skill {t['name'].lower()} {'specialization' if s['active'] else 'perk'}")


def collect_apparel(site):
    slot_name = dict(subs_of(site, "apparel"))
    for c in apparel_cards(site):
        icon = f"img/vanity/{c['icon']}" if c["icon"] else None
        for it in c["items"]:
            path = f"{APPAREL}#{it['_anchor']}"
            key = first_free(site, "apparel", it["n"], it["r"])
            site.register("apparel", key, path, it["n"], icon=icon, aliases=[it["r"], str(it["h"])], search=False)
            site.register("vanity", first_free(site, "vanity", it["n"], it["r"]), path, it["n"], icon=icon,
                          aliases=[it["r"], str(it["h"])], search=False)
        n = len(c["items"])
        key = first_free(site, "apparel", c["base"], f"{c['base']} ({packs(site)[c['pack']]['short']})")
        site.register("apparel", key, f"{APPAREL}#{c['id']}", c["base"], icon=icon,
                      desc=f"{slot_name.get(c['slot'], c['slot'])}, {n} version{'s' if n > 1 else ''} · "
                           f"{packs(site)[c['pack']]['short']}",
                      keywords="apparel clothing " + slot_name.get(c["slot"], ""))


def collect_vanity(site):
    for group, label in (("facepaint", "Face paint"), ("emotes", "Emote"), ("vehicles", "Vehicle paint job")):
        for it in items_of(site, group):
            icon = f"img/vanity/{it['i']}" if it.get("i") else None
            site.register("vanity", first_free(site, "vanity", it["n"], it["r"]), f"{VANITY}#v-{it['h']}", it["n"],
                          icon=icon, aliases=[it["r"], str(it["h"])],
                          desc=f"{label} · {packs(site)[it['p']]['short']}", keywords=f"{group} {label.lower()}")


# ===============================================================================================================
# build
# ===============================================================================================================
def build(site):
    build_skills(site)
    build_apparel(site)
    build_vanity(site)
    build_packs(site)


# ---------------------------------------------------------------------------------------------------------------
# skills
# ---------------------------------------------------------------------------------------------------------------
LEVEL_RE = re.compile(r"^Level (\d+):\s*(.*)$")


def skill_text(s):
    """Split a skill description into (description paragraphs, [(level, effect)])."""
    paras, levels = [], []
    for part in s["desc"].split("\n\n"):
        part = part.strip()
        m = LEVEL_RE.match(part)
        if m:
            levels.append((int(m.group(1)), m.group(2).strip()))
        elif part:
            paras.append(part)
    return paras, levels


NUM_RE = re.compile(r"\d+(?:\.\d+)?")


def at_max(levels):
    """The effect at the highest level, for the All skills table.
    Levels that differ only by the number ('+5% damage', '+10% damage') replace each other, so the last one is the
    effect at max. Levels with different wording add different effects (Armor: bullet, then explosive, then gas
    resistance), so all of them are joined, folding a shared ending ('+10% bullet, +10% explosive, +10% gas damage
    resistance')."""
    if not levels:
        return '<span class="dim">–</span>'
    effects = [e.rstrip(".") for _, e in levels]
    if len({NUM_RE.sub("#", e).replace(" ", "").lower() for e in effects}) == 1:
        return esc(effects[-1])
    words = [e.split() for e in effects]
    common = 0      # number of trailing words all levels share
    while common < min(map(len, words)) - 1 and len({tuple(w[len(w) - common - 1:]) for w in words}) == 1:
        common += 1
    if common:
        heads = [" ".join(w[:len(w) - common]) for w in words]
        joined = " and ".join(heads) if len(heads) == 2 else ", ".join(heads)
        return esc(joined + " " + " ".join(words[0][-common:]))
    return esc("; ".join(effects))


def skill_pos(site):
    """skill id -> (tree index, column, row), from the trees' column lists."""
    out = {}
    for ti, t in enumerate(site.data("gamedata")["skills"]["trees"]):
        for ci, col in enumerate(t["cols"]):
            for ri, sid in enumerate(col):
                out[sid] = (ti, ci, ri)
    return out


def skill_links(site, ids):
    L = site.data("gamedata")["skills"]["list"]
    return ", ".join(site.link("skill", L[i]["name"]) for i in ids)


def build_skills(site):
    sk = site.data("gamedata")["skills"]
    L, trees = sk["list"], sk["trees"]
    total = sum(s["max"] for s in L.values())
    specs = [sid for sid, s in L.items() if s["active"]]
    lead = (f"<p>Your character has <b>{len(L)} skills</b> in four trees ({', '.join(t['name'].title() for t in trees)})."
            f" Each tree has two columns of six skills; a skill opens once the skill above it is learned, and the "
            f"bottom skill of every column is a <b>specialization</b>, an ability you switch on. Ranks cost one "
            f"skill point each, and maxing every skill takes <b>{total} skill points</b>. All names, descriptions "
            f"and level values below are the game's own text.</p>")
    b = [bar("Skill trees at a glance", f"{len(L)} skills · {total} points to max"),
         "<p>The four trees laid out as in the game's skill menu: each tree is two columns, read from top to "
         "bottom. The number on a skill is how many ranks it has. Specializations have a gold frame. Click a "
         "skill for its details.</p>",
         overview_trees(site)]
    b += skill_point_guide(site, L, trees, total, specs)
    for ti, t in enumerate(trees):
        b += tree_section(site, L, ti, t)
    b += specialization_table(site, L, specs)
    b += skill_table(site, L)
    site.page(SKILLS, "Skills", "\n".join(b), "character", sub="skills", lead=lead, head_extra=CSS,
              kind="Character · Skill trees",
              desc=f"All {len(L)} Generation Zero skills in the Combat, Support, Survival and Tech trees: per-level "
                   "effects, prerequisites, specializations and skill point costs.")


def overview_trees(site):
    """The four trees side by side, each a 2 x 6 grid of skill icons (like the game's menu)."""
    sk = site.data("gamedata")["skills"]
    L = sk["list"]
    out = ['<div class="sktrees">']
    for t in sk["trees"]:
        pts = sum(L[sid]["max"] for col in t["cols"] for sid in col)
        cells = []
        for ci, col in enumerate(t["cols"]):
            for ri, sid in enumerate(col):
                s = L[sid]
                cls = "sknode" + (" spec" if s["active"] else "") + (" linked" if ri else "")
                cells.append(f'<a class="{cls}" href="#{slug(s["name"])}" style="grid-column:{ci + 1};'
                             f'grid-row:{ri + 1}" title="{esc(s["name"])}">'
                             f'{site.img(s["icon"].replace("assets/", "img/", 1), "", cls="skico")}'
                             f'<span class="skn">{esc(s["name"])}</span><span class="skr">{s["max"]}</span></a>')
        out.append(f'<section class="sktree"><h3><a href="#{slug(t["name"])}">{esc(t["name"])}</a>'
                   f'<small>{pts} points</small></h3><div class="skgrid">{"".join(cells)}</div></section>')
    out.append("</div>")
    return "".join(out)


def skill_point_guide(site, L, trees, total, specs):
    rows = []
    for t in trees:
        for ci, col in enumerate(t["cols"]):
            spec = L[col[-1]]
            rows.append([f'<b>{esc(t["name"].title())}</b>', f"Column {ci + 1}",
                         f'{site.link("skill", L[col[0]]["name"])} → {site.link("skill", spec["name"])}',
                         len(col), sum(L[s]["max"] for s in col)])
    one_rank = [s for s in L.values() if s["max"] == 1 and not s["active"]]
    out = [bar("Skill points"),
           "<p>Each level-up gives you a skill point. A rank of a skill costs one point, so a skill with three "
           "levels costs three points to max. One rank in a skill is enough to open the next skill in its "
           "column (the Gen0 Editor's skill tab works the same way), which means the cheapest way down a column "
           "is one point per skill.</p>",
           "<p>The table shows each column of each tree: its first skill and the specialization at the bottom, "
           "and how many points it takes to max the whole column. Reaching any specialization takes 6 points "
           "(one rank in each of the five skills above it, plus the specialization itself).</p>",
           table(["Tree", "Column", "From → specialization", "Skills", "Points to max"], rows, num={3, 4}),
           kv([(t["name"].title(), f"{sum(L[s]['max'] for col in t['cols'] for s in col)} points to max all "
                                   f"{sum(len(c) for c in t['cols'])} skills") for t in trees]
              + [("All trees", f"<b>{total} points</b>")]),
           bar("Tips from the numbers"),
           "<ul>"
           f"<li><b>Every specialization costs at least 6 points</b>: five skills above it at one rank each, plus "
           f"the specialization's single rank. With {len(specs)} specializations and only one active at a time, "
           f"it's worth getting one early and filling in the rest later.</li>"
           f"<li><b>One-point skills give their full effect at once</b>: "
           f"{', '.join(site.link('skill', s['name']) for s in one_rank)}. Of these, "
           f"{site.link('skill', 'Lockpicking')} (open locked doors with lockpicks) and "
           f"{site.link('skill', 'Healer')} (heal other players with a first aid kit) add abilities rather than "
           f"bonuses.</li>"
           f"<li><b>{site.link('skill', 'Armor')} protects against a different damage type per level</b>: level 1 "
           f"is bullets, level 2 explosives, level 3 gas. If gas is your problem you need all three ranks; "
           f"{site.link('skill', 'Chemist')} adds another 10% gas resistance for one point.</li>"
           f"<li><b>Each damage skill covers one kind of hit</b>: {site.link('skill', 'Armor Damage')} (Combat) works "
           f"on armor and {site.link('skill', 'Component Damage')} (Tech) on components, "
           f"{site.link('skill', 'Trigger Happy')} on automatic fire, and {site.link('skill', 'Make Em Count')} adds "
           f"component damage for single shots from automatic weapons, so it works alongside Component Damage "
           f"rather than as a general damage boost.</li>"
           f"<li><b>Binocular skills</b> ({site.link('skill', 'Enemy Marking')}, "
           f"{site.link('skill', 'Designated Target')}, {site.link('skill', 'Spotting Intel')}, "
           f"{site.link('skill', 'Remote Hacking')}) all work through the binoculars, so keep them on you.</li>"
           f"<li>{site.link('skill', 'Inquisitive Mind')} doubles mission XP at level 2 (+100%), so it pays back "
           f"fastest when you take it early.</li>"
           "</ul>"]
    return out


def tree_section(site, L, ti, t):
    pts = sum(L[s]["max"] for col in t["cols"] for s in col)
    out = [bar(f"{t['name'].title()} tree", f"{sum(len(c) for c in t['cols'])} skills · {pts} points",
               id=slug(t["name"]))]
    out.append('<div class="skcols">')
    for ci, col in enumerate(t["cols"]):
        out.append('<div class="skcol">')
        for ri, sid in enumerate(col):
            if ri:
                out.append('<div class="skarrow" aria-hidden="true"></div>')
            out.append(skill_card(site, L, sid, t, ci, ri))
        out.append("</div>")
    out.append("</div>")
    return out


def skill_card(site, L, sid, t, ci, ri):
    s = L[sid]
    paras, levels = skill_text(s)
    art = site.img(s["image"].replace("assets/", "img/", 1), "", cls="skart") if s.get("image") else ""
    icon = site.img(s["icon"].replace("assets/", "img/", 1), "", cls="skico")
    kind = tag("Specialization", "exp") if s["active"] else tag("Passive", "base")
    lv = ""
    if levels:
        lv = '<ol class="sklv">' + "".join(f"<li><b>Level {n}</b> {esc(e)}</li>" for n, e in levels) + "</ol>"
    elif s["max"] > 1:
        lv = f'<p class="dim small">The game gives no per-level values for its {s["max"]} levels.</p>'
    req = skill_links(site, s["parents"]) if s["parents"] else '<span class="dim">nothing (top of the column)</span>'
    unl = skill_links(site, s["children"]) if s["children"] else '<span class="dim">nothing (end of the column)</span>'
    return (f'<div class="skc{" spec" if s["active"] else ""}" id="{slug(s["name"])}">'
            f'<div class="skhd">{art}{icon}<div><b>{esc(s["name"])}</b>'
            f'<span class="dim small">{kind} {esc(t["name"].title())} · column {ci + 1}, row {ri + 1}</span></div>'
            f'<span class="skmax" title="Maximum level">{s["max"]}<small>max</small></span></div>'
            f'<div class="skbody">'
            + "".join(f"<p>{esc(p)}</p>" for p in paras) + lv +
            f'<dl class="skrel"><dt>Requires</dt><dd>{req}</dd><dt>Unlocks</dt><dd>{unl}</dd></dl>'
            f'<div class="skid"><code>{esc(sid)}</code> · hash <code>{s["hash"]}</code></div></div></div>')


def specialization_table(site, L, specs):
    pos = skill_pos(site)
    trees = site.data("gamedata")["skills"]["trees"]
    rows = []
    for sid in specs:
        s = L[sid]
        ti, ci, ri = pos[sid]
        paras, _ = skill_text(s)
        effect = " ".join(p for p in paras if not p.startswith("Only one specialization"))
        rows.append([site.link("skill", s["name"], icon=True), esc(trees[ti]["name"].title()),
                     site.link("skill", L[s["parents"][0]]["name"]) if s["parents"] else "–", esc(effect)])
    return [bar("Specializations"),
            f"<p>The {len(specs)} specializations are the last skill of each column. You can learn all of them, but "
            "the game says only one specialization may be active at a time, so you pick the one that is switched "
            "on.</p>",
            table(["Specialization", "Tree", "Needs", "Effect"], rows, cls="spect")]


def skill_table(site, L):
    pos = skill_pos(site)
    trees = site.data("gamedata")["skills"]["trees"]
    rows = []
    for sid, s in sorted(L.items(), key=lambda kv_: pos[kv_[0]]):
        ti, ci, ri = pos[sid]
        _, levels = skill_text(s)
        rows.append([site.link("skill", s["name"], icon=True), esc(trees[ti]["name"].title()),
                     f'<span data-v="{ci * 10 + ri}">{ci + 1} / {ri + 1}</span>', s["max"],
                     "Specialization" if s["active"] else "Passive",
                     at_max(levels),
                     skill_links(site, s["parents"]) or "–", skill_links(site, s["children"]) or "–",
                     f"<code>{esc(sid)}</code>", f"<code>{s['hash']}</code>"])
    return [bar("All skills"),
            "<p>Every skill in one sortable table. <i>Col / row</i> is the position in its tree, "
            "<i>At max</i> what the skill gives at its highest level, in the game's words (only for skills whose "
            "text lists levels): the last level's value where the levels only change a number, or every level's "
            "effect where each level adds something different (Armor, Explosives Expert, Spotting Intel). The "
            "internal key and the hash are what save files and the "
            f"{site.link('tool', 'Gen0 Editor')} use.</p>",
            table(["Skill", "Tree", "Col / row", "Levels", "Type", "At max", "Requires", "Unlocks", "Key", "Hash"],
                  rows, cls="compact sktab", num={3})]


# ---------------------------------------------------------------------------------------------------------------
# apparel
# ---------------------------------------------------------------------------------------------------------------
def build_apparel(site):
    items = items_of(site, "apparel")
    cards = apparel_cards(site)
    subs = subs_of(site, "apparel")
    base = van(site)["base_pack"]
    lead = (f"<p>Apparel is the clothing your character wears: <b>{fmt(len(items))} items</b> in "
            f"{len(subs)} slots, from hats and hair to shoes and backpacks. Many items are colour versions of the "
            f"same piece, so they are grouped here into {len(cards)} cards. Unlocked apparel is kept in the "
            "profile's item stash (<code>Profile.ItemStash</code>), so it is shared by every character on the "
            "profile. The items on this page change your looks; bonuses such as bullet resistance come from the "
            f"{schematics_link(site)}.</p>")
    n_u = sum(1 for i in items if i["l"] == "U")
    b = [bar("Slots"), "<p>How many items each slot has, how many of them are base game and how many come from "
         "content packs, and how many carry the DLC flag. <i>Cards</i> is the number of different pieces (colour "
         "versions folded together). The last two columns split the unlocked items: <code>U</code> is unlocked "
         "for everyone, <code>UD</code> only on a profile that owns the item's pack"
         + (", and no apparel item is plain <code>U</code>, so every apparel item that starts unlocked is DLC"
            if n_u == 0 else "") + ".</p>",
         slot_table(site, items, cards, subs, base)]
    b += how_to_read(site)
    b += [bar("Browse apparel", f"{len(cards)} cards · {fmt(len(items))} items", id="browse"),
          "<p>Filter by slot and by pack (the pack chips are the packs that have apparel; names other than Base "
          "game and the two expansions are inferred from the contents). The text box searches names, colours "
          "and internal names. The <b>Grid</b> shows one card per piece with its colour versions; the "
          "<b>Table</b> lists every single item with its hashes. Most apparel uses a generic icon per slot in "
          "the game files, so the pictures show the slot, not the look.</p>",
          '<div class="tabset"><div class="tsbtns"><button class="on">Grid</button><button>Table</button></div>',
          '<div class="tspane">' + apparel_filter(site, "apgrid", items, subs) + apparel_grid(site, cards, subs)
          + "</div>",
          '<div class="tspane">' + apparel_filter(site, "aptable", items, subs) + apparel_table(site, items, subs)
          + "</div></div>"]
    b += apparel_oddities(site, items)
    site.page(APPAREL, "Apparel", "\n".join(b), "character", sub="apparel", lead=lead, head_extra=CSS, wide=True,
              kind="Character · Vanity",
              desc=f"All {len(items)} Generation Zero apparel items by slot and pack, with colour versions, DLC "
                   "flags and internal names.")


def schematics_link(site):
    return '<a href="~/items/schematics.html">apparel crafting schematics</a>'


def slot_table(site, items, cards, subs, base):
    rows = []
    for key, name in subs:
        its = [i for i in items if i["s"] == key]
        rows.append([esc(name),
                     f"<code>{esc(key)}</code>", len(its), sum(1 for c in cards if c["slot"] == key),
                     sum(1 for i in its if i["p"] == base), sum(1 for i in its if i["p"] != base),
                     sum(1 for i in its if i["l"].endswith("D"))] + unlock_counts(its))
    rows.append(["<b>All slots</b>", "", len(items), len(cards), sum(1 for i in items if i["p"] == base),
                 sum(1 for i in items if i["p"] != base), sum(1 for i in items if i["l"].endswith("D"))]
                + unlock_counts(items))
    return table(["Slot", "Internal", "Items", "Cards", "Base game", "From packs", "DLC flag",
                  "Starts unlocked (U)", "Unlocked with pack (UD)"], rows, num={2, 3, 4, 5, 6, 7, 8})


def unlock_counts(its):
    """[plain U count, UD count]: UD items are unlocked only on a profile that owns their pack."""
    return [sum(1 for i in its if i["l"] == "U"), sum(1 for i in its if i["l"] == "UD")]


def how_to_read(site):
    rows = [[f"<code>{esc(k)}</code>", esc(lbl), esc(why)] for k, (lbl, why) in FLAG.items()]
    return [bar("How to read the data"),
            "<p>Every apparel item in the game files has a display name, an internal name "
            "(<code>char_part_…</code>), a slot, an icon and the hash of the content pack it belongs to. Three "
            "more fields matter for players:</p>",
            "<ul><li><b>Lock flag</b>: the item's starting state. <code>U</code> means unlocked from the start, "
            "<code>L</code> not given automatically (found, earned, or chosen in the character creator); a "
            "trailing <code>D</code> marks downloadable content. No game file says what the letters mean: this "
            "reading is inferred from how the Gen0 Editor uses them (it marks <code>UD</code> and <code>LD</code> "
            "items as DLC). It doesn't fit every slot: the heads and hands (slot <code>body</code>) are all "
            "<code>L</code>, yet you choose them at character creation.</li>"
            "<li><b>Model</b>: colour versions of the same piece of clothing share one model hash. The cards below "
            "group by name instead, because a few model hashes are shared by differently named pieces (for example "
            "<i>Band tee</i> and <i>Lousy T-shirt</i>).</li>"
            "<li><b>Body</b>: a handful of items (one hairstyle and the heads and hands) are made for one body "
            "only, marked <i>Female</i> or <i>Male</i>. Everything else fits both.</li></ul>",
            table(["Flag", "Shown as", "Meaning"], rows, sortable=False, cls="compact"),
            note("A <b>content pack</b> is how the game files group content; it is not always something you buy. "
                 "Many packs hold items you get in the game for free (rewards, events), and the lock flag tells "
                 f"you which. See <a href=\"~/{PACKS}\">Item packs</a> for what each pack contains.", "data")]


def apparel_filter(site, target, items, subs):
    """Filterbar with a slot chip group and a pack chip group (packs ordered by number of apparel items)."""
    pk = packs(site)
    count = collections.Counter(i["p"] for i in items)
    slot_chips = "".join(f'<button class="chip" data-g="slot" data-f="s-{esc(k)}">{esc(n)}</button>'
                         for k, n in subs)
    pack_chips = "".join(f'<button class="chip" data-g="pack" data-f="p-{p}" title="{esc(pk[p]["name"])}">'
                         f'{esc(pk[p]["short"])} <span class="dim">{n}</span></button>'
                         for p, n in count.most_common())
    return (f'<div class="filterbar" data-for="{target}"><input placeholder="Filter apparel...">'
            f'<span class="count"></span>'
            f'<div class="fgrp"><span class="flbl">Slot</span><button class="chip on" data-g="slot" data-f="*">All</button>'
            f'{slot_chips}</div>'
            f'<div class="fgrp"><span class="flbl">Pack</span><button class="chip on" data-g="pack" data-f="*">All</button>'
            f'{pack_chips}</div></div>')


def apparel_grid(site, cards, subs):
    slot_name = dict(subs)
    out = [f'<div class="apgrid" id="apgrid">']
    for c in cards:
        its = c["items"]
        icon = site.img(f"img/vanity/{c['icon']}", "", cls="vi") if c["icon"] else '<span class="vglyph"></span>'
        tags = [pack_tag(site, c["pack"])]
        tags += [lock_tag(f) for f in c["flags"]]
        for x in sorted(c["body"]):
            tags.append(tag(BODY[x].split(" body")[0]))
        if c["single"]:
            it = its[0]
            variants = f'<div class="apraw"><code>{esc(it["r"])}</code></div>'
        else:
            variants = '<div class="apvars">' + "".join(
                f'<span class="apv" id="a-{i["h"]}" title="{esc(i["n"])} · {esc(i["r"])} · {i["h"]}">'
                f'{esc(variant_label(i, c["base"]))}</span>' for i in its) + "</div>"
        words = " ".join(i["r"] for i in its) + " " + packs(site)[c["pack"]]["name"]
        n = len(its)
        out.append(f'<div class="apc fitem" id="{c["id"]}" data-f="s-{esc(c["slot"])} p-{c["pack"]}" '
                   f'data-w="{esc(words)}"><div class="aphd">{icon}<div><b>{esc(c["base"])}</b>'
                   f'<span class="dim small">{esc(slot_name.get(c["slot"], c["slot"]))}'
                   f'{f" · {n} versions" if n > 1 else ""}</span><div class="aptags">{"".join(tags)}</div></div></div>'
                   f'{variants}</div>')
    out.append("</div>")
    return "".join(out)


def apparel_table(site, items, subs):
    slot_name = dict(subs)
    order = {k: n for n, (k, _) in enumerate(subs)}
    rows = []
    for it in sorted(items, key=lambda i: (order.get(i["s"], 99), i["n"].lower())):
        rows.append([esc(it["n"]), f'<span data-v="{order.get(it["s"], 99)}">{esc(slot_name.get(it["s"]))}</span>',
                     plain_pack_tag(site, it["p"]), flag_cell(it["l"]), esc(it.get("x", "")) or "–",
                     f'<code>{it["m"]}</code>' if it.get("m") else "–", f'<code>{esc(it["r"])}</code>',
                     f'<code>{it["h"]}</code>'])
    html = table(["Name", "Slot", "Pack", "Lock flag", "Body", "Model", "Internal name", "Item hash"], rows,
                 cls="compact aptab")
    # rows need data-f for the chip filter: add it to each <tr> in order
    tags = iter(f's-{i["s"]} p-{i["p"]}' for i in sorted(items, key=lambda i: (order.get(i["s"], 99),
                                                                                 i["n"].lower())))
    html = re.sub(r"<tr>(?=<td)", lambda m: f'<tr data-f="{next(tags)}">', html)
    return f'<div id="aptable">{html}</div>'


def apparel_oddities(site, items):
    by_name = collections.defaultdict(list)
    for it in items:
        by_name[it["n"]].append(it)
    dups = {n: its for n, its in by_name.items() if len(its) > 1}
    rows = [[esc(n), len(its), ", ".join(f"<code>{esc(i['r'])}</code>" for i in its),
             " ".join(sorted({pack_tag(site, i["p"]) for i in its}))] for n, its in sorted(dups.items())]
    gnomes = [i for i in items if i["r"].startswith("char_part_head_gnome_reward")]
    out = [bar("Oddities in the data"),
           f"<p>{len(dups)} apparel names are used by more than one item. Most are two colour versions the game "
                    "gives the same colour name; the internal names show they are different items. The most "
           "striking case is <i>Uncle Calle's tin foil hat</i>: the name is shared by reward items whose "
           "internal names are berets, a firefighter helmet and a construction helmet.</p>",
           table(["Name", "Items", "Internal names", "Packs"], rows, cls="compact")]
    if gnomes:
        out.append(f"<p>The {len(gnomes)} gnome masks have internal names ending in <code>gnome_reward</code>; see "
                   f"{site.link('collectible-type', 'gnomes', 'Gnomes')} for the gnome collectibles: "
                   + ", ".join(site.link("apparel", i["n"]) for i in gnomes) + ".</p>")
    return out


# ---------------------------------------------------------------------------------------------------------------
# face paint, emotes, vehicles (+ pointers to weapon skins and companion cosmetics)
# ---------------------------------------------------------------------------------------------------------------
def build_vanity(site):
    allv = van(site)["items"]
    lead = ("<p>Besides apparel, the game's vanity list has <b>face paint</b>, <b>emotes</b> (gestures, dances and "
            "companion tricks), <b>vehicle paint jobs</b> for the bikes, <b>weapon skins</b> and <b>companion "
            f"cosmetics</b>: {fmt(len(allv))} vanity items in all. This page lists face paint, emotes and vehicles "
            "in full; weapon skins and companion parts have their own pages. Like apparel, unlocked vanity items "
            "are shared by every character on a profile. Pack names other than Base game, Alpine Unrest and FNIX "
            f"Rising are inferred from their contents (see <a href=\"~/{PACKS}\">Item packs</a>).</p>")
    b = [bar("Overview"), "<p>Every vanity group with its item count, how many are base game items, how many "
         "start unlocked for everyone (<code>U</code>), how many are unlocked only when you own their pack "
         f"(<code>UD</code>) and how many carry the DLC flag. See <a href=\"~/{PACKS}#flags\">Lock flags</a> for "
         "what the flags mean.</p>", vanity_overview(site)]
    b += face_paint(site)
    b += emotes(site)
    b += vehicles(site)
    b += skins_pointer(site)
    b += companion_pointer(site)
    site.page(VANITY, "Emotes, vehicles & more", "\n".join(b), "character", sub="vanity", lead=lead, head_extra=CSS,
              kind="Character · Vanity",
              desc="Generation Zero face paint, emotes, dances and bike paint jobs, with packs, unlock flags and "
                   "internal names; pointers to weapon skins and companion cosmetics.")


def vanity_overview(site):
    base = van(site)["base_pack"]
    where = {"apparel": f'<a href="~/{APPAREL}">Apparel</a>', "facepaint": '<a href="#face-paint">below</a>',
             "emotes": '<a href="#emotes">below</a>', "vehicles": '<a href="#vehicles">below</a>',
             "skins": '<a href="~/weapons/skins.html">Weapon skins</a>',
             "companion": '<a href="~/items/companion.html">Companion</a>'}
    rows = []
    for g in sorted(van(site)["groups"], key=lambda g: GROUP_ORDER.index(g["key"]) if g["key"] in GROUP_ORDER else 9):
        its = items_of(site, g["key"])
        rows.append([f"<b>{esc(g['name'])}</b>", f"<code>{esc(g['key'])}</code>", len(g["subs"]), len(its),
                     sum(1 for i in its if i["p"] == base)] + unlock_counts(its)
                    + [sum(1 for i in its if i["l"].endswith("D")), where.get(g["key"], "")])
    return table(["Group", "Internal", "Kinds", "Items", "Base game", "Starts unlocked (U)",
                  "Unlocked with pack (UD)", "DLC flag", "Listed on"], rows, num={2, 3, 4, 5, 6, 7})


def vanity_rows(site, its):
    return [[f'<span id="v-{i["h"]}">{esc(i["n"])}</span>', pack_tag(site, i["p"]), flag_cell(i["l"]),
             f'<code>{esc(i["r"])}</code>', f'<code>{i["h"]}</code>'] for i in its]


def face_paint(site):
    its = sorted(items_of(site, "facepaint"), key=lambda i: i["n"].lower())
    base = van(site)["base_pack"]
    nb = sum(1 for i in its if i["p"] == base)
    return [bar("Face paint", f"{len(its)} items"),
            f"<p>Face paint goes over your character's face in the looks menu. {nb} of the {len(its)} are base game "
            f"items ({flag_counts([i for i in its if i['p'] == base]).lower()}); the rest come with content packs. "
            + ("All face paints share one generic icon in the game files, so they are listed by name."
               if len({i.get("i") for i in its}) == 1 else "") + "</p>",
            table(["Face paint", "Pack", "Lock flag", "Internal name", "Item hash"], vanity_rows(site, its),
                  cls="compact")]


def emote_tile(site, it, extra=""):
    return (f'<div class="icon vtile" id="v-{it["h"]}" style="--c:{"#8a6d1f" if it["l"].endswith("D") else "#3d4a50"}">'
            f'{vimg(site, it)}<b>{esc(it["n"])}</b>{extra}'
            f'<span>{pack_tag(site, it["p"])}{flag_tags(it)}</span><code class="small">{esc(it["r"])}</code></div>')


def emotes(site):
    its = items_of(site, "emotes")
    base = van(site)["base_pack"]
    tapes = videotape_titles(site)
    out = [bar("Emotes", f"{len(its)} items"),
           f"<p>Emotes are the gestures and dances your character can perform; you pick which ones go in your emote "
           f"slots. There are {len(its)} in the files: "
           + ", ".join(f"{sum(1 for i in its if i['s'] == k)} {esc(n.lower())}" for k, n in subs_of(site, "emotes"))
           + f". {sum(1 for i in its if i['p'] == base and i['l'] == 'U')} base game emotes start unlocked.</p>"]
    locked_dances = [i for i in its if i["s"] == "dance" and i["p"] == base and i["l"] == "L"]
    if locked_dances:
        matched = [i for i in locked_dances if norm(i["n"]) in tapes]
        out.append(note(
            f"The {len(locked_dances)} base game dances that start locked are "
            + ", ".join(site.link("vanity", i["n"]) for i in locked_dances) + ". "
            + (f"All {len(matched)} share their name with one of the "
               if len(matched) == len(locked_dances) else f"{len(matched)} of them share their name with one of the ")
            + f"{site.link('collectible-type', 'videotapes', 'Videotape')} collectibles; picking up the tape is "
            "how you get the dance.", "info", "Dances from videotapes"))
        out += videotape_table(site, locked_dances)
    for key, name in subs_of(site, "emotes"):
        sub = sorted((i for i in its if i["s"] == key), key=lambda i: i["n"].lower())
        out.append(f'<h3 id="emotes-{esc(key)}">{esc(name)} ({len(sub)})</h3>')
        out.append('<div class="icongrid vgrid">' + "".join(
            emote_tile(site, i, ' <span class="dim small">videotape</span>' if norm(i["n"]) in tapes
                       and i["p"] == base else "") for i in sub) + "</div>")
    return out


def videotape_table(site, dances):
    """Dance -> the videotape that unlocks it, with its region and the nearest named map location."""
    by_title = {norm(t["n"].split(" - ", 1)[-1]): t for t in videotapes(site)}
    locs = [l for l in site.data("map_locations")["list"] if l["name"] != "Unknown"]
    rows = []
    for d in dances:
        t = by_title.get(norm(d["n"]))
        if not t:
            continue
        near = min(locs, key=lambda l: (l["x"] - t["x"]) ** 2 + (l["z"] - t["z"]) ** 2)
        dist = ((near["x"] - t["x"]) ** 2 + (near["z"] - t["z"]) ** 2) ** 0.5
        num = re.match(r"Videotape (\d+)", t["n"])
        rows.append([site.link("vanity", d["r"], d["n"]), esc(t["n"]),
                     f'<span data-v="{int(num.group(1)) if num else 0}">{num.group(1) if num else "–"}</span>',
                     site.link("region", t["r"]),
                     f'<span data-v="{dist:.0f}"><span class="dim">{"at" if dist < 40 else f"{dist:,.0f} m from"}'
                     f'</span> {site.link("location", near["name"])}</span>'])
    if not rows:
        return []
    return [f"<p>Where each tape lies (from the map markers). <i>Nearest location</i> is the closest named place "
            f"on the map, to help you find the spot; the {site.link('collectible-type', 'videotapes', 'Videotapes')} "
            "page has them on a map.</p>",
            table(["Dance", "Videotape", "Tape no.", "Region", "Nearest location"], rows, num={2}, cls="compact")]


def videotapes(site):
    return [i for i in site.data("markers")["items"] if i.get("s") == "videotapes"]


def videotape_titles(site):
    """norm(title) of every videotape collectible ('Videotape 04 - Jschwiss' -> 'jschwiss')."""
    return {norm(i["n"].split(" - ", 1)[-1]) for i in videotapes(site)}


def vehicles(site):
    its = items_of(site, "vehicles")
    out = [bar("Vehicles", f"{len(its)} paint jobs"),
           "<p>" + " ".join(vehicle_facts(site, its)) + "</p>"]
    rows = []
    for key, name in subs_of(site, "vehicles"):
        sub = sorted((i for i in its if i["s"] == key), key=lambda i: i["n"].lower())
        if not sub:
            continue
        ps = sorted({i["p"] for i in sub})
        rows.append([f'<a href="#veh-{slug(key)}">{esc(name)}</a>', f"<code>{esc(key)}</code>", len(sub),
                     " ".join(pack_tag(site, p) for p in ps), flag_counts(sub)])
    out.append(table(["Bike", "Internal", "Paint jobs", "Pack", "Lock flags"], rows, num={2}, cls="compact"))
    for key, name in subs_of(site, "vehicles"):
        sub = sorted((i for i in its if i["s"] == key), key=lambda i: i["n"].lower())
        if not sub:
            continue
        out.append(f'<h3 id="veh-{slug(key)}">{esc(name)} <code class="small">{esc(key)}</code></h3>')
        out.append('<div class="icongrid vgrid">' + "".join(emote_tile(site, i) for i in sub) + "</div>")
    dup_icons = [k for k, n in collections.Counter((i["s"], i.get("i")) for i in its).items() if n > 1]
    if dup_icons:
        out.append(note("Some paint jobs share one icon in the game files (for example every Dirt Bike, Military "
                        "Motorcycle and Resistance Custom colour uses the model's default icon), so the pictures "
                        "above don't always show the colour.", "data"))
    return out


def vehicle_facts(site, its):
    """Sentences about the bike paint jobs, each checked against the data."""
    bikes = subs_of(site, "vehicles")
    out = [f"Each bike in the game has its paint jobs as separate vanity items: {len(bikes)} bike models with "
           f"{len(its)} paint jobs in all."]
    if all(len({i["p"] for i in its if i["s"] == k}) <= 1 for k, _ in bikes):
        out.append("Every model's paint jobs come from a single content pack, shown next to its name.")
    if not any(i["p"] == van(site)["base_pack"] for i in its):
        out.append("None of them is base game content.")
    out.append("The internal key (<code>v0xx_bike_…</code>) is the bike model.")
    return out


def skins_pointer(site):
    its = items_of(site, "skins")
    rows = []
    for key, name in subs_of(site, "skins"):
        sub = [i for i in its if i["s"] == key]
        if sub:
            rows.append([site.link("weapon", name), len(sub),
                         ", ".join(site.link("skin", i["r"], i["n"]) for i in sorted(sub, key=lambda i: i["n"]))])
    return [bar("Weapon skins", f"{len(its)} skins"),
            f"<p>Weapon skins change how a weapon looks, not how it performs. There are {len(its)} skins for "
            f"{len(rows)} weapons; the full list with pictures is on "
            f'<a href="~/weapons/skins.html">Weapon skins</a>, and each weapon page shows its own.</p>',
            table(["Weapon", "Skins", "Skin names"], rows, num={1}, cls="compact")]


def companion_pointer(site):
    its = items_of(site, "companion")
    rows = []
    for key, name in subs_of(site, "companion"):
        sub = [i for i in its if i["s"] == key]
        if sub:
            rows.append([esc(name), f"<code>{esc(key)}</code>", len(sub),
                         " ".join(pack_tag(site, p) for p in sorted({i["p"] for i in sub}))])
    return [bar("Companion cosmetics", f"{len(its)} parts"),
            f"<p>The companion (your Runner-type machine friend) has {len(its)} parts in the vanity list. They are "
            'covered with the companion itself on <a href="~/items/companion.html">Companion</a>; this is just '
            "the count per kind, the packs they come from and a link to each part. Companion tricks (the companion's emotes) are "
            '<a href="#emotes-companion">listed above</a>.</p>',
            table(["Kind", "Internal", "Parts", "Packs"], rows, num={2}, cls="compact"),
            "<p>The parts by kind, each linked to its entry on the Companion page:</p>",
            pack_group_list(site, "companion", its)]


# ---------------------------------------------------------------------------------------------------------------
# packs
# ---------------------------------------------------------------------------------------------------------------
def pack_extras(site):
    """Content pack -> non-vanity items listed for it in keys.json pack_items: [(kind, name, link html)]."""
    k = site.data("keys")
    keys = {i["h"]: i for i in k["items"]}
    stock = {i["h"]: i for i in site.data("stock")["stock"]}
    sch = {i["h"]: i for i in site.data("schematics")["items"]}
    vh = {i["h"] for i in van(site)["items"]}
    out = collections.defaultdict(list)
    for p, hs in k["pack_items"].items():
        for h in hs:
            if h in vh:
                continue
            if h in keys:
                out[int(p)].append(("Keys and mission items", keys[h]["n"], site.link("key", keys[h]["n"])))
            elif h in sch:
                out[int(p)].append(("Schematics", sch[h]["n"], site.link("schematic", str(h), sch[h]["n"])))
            elif h in stock:
                s = stock[h]
                kind = "material" if s["g"] == "materials" else "item"
                out[int(p)].append(("Materials" if kind == "material" else "Items", s["name"],
                                    site.link(kind, s["name"])))
            else:
                out[int(p)].append(("Unknown", str(h), f"<code>{h}</code>"))
    return out


def build_packs(site):
    pk = packs(site)
    by_pack = collections.defaultdict(list)
    for it in van(site)["items"]:
        by_pack[it["p"]].append(it)
    extras = pack_extras(site)
    base = van(site)["base_pack"]
    order = sorted(pk, key=lambda h: (h != base, pk[h]["inferred"], -(len(by_pack[h]) + len(extras[h]))))
    n_inf = sum(1 for h in pk if pk[h]["inferred"])
    lead = (f"<p>The game files sort content into <b>content packs</b>, each known by a hash. This page lists all "
            f"{len(pk)} packs that appear in the vanity list and in the key and item lists, with everything that "
            f"belongs to each. The data names only three of them: the base game, "
            f"{site.link('dlc', 'Alpine Unrest')} and {site.link('dlc', 'FNIX Rising')}. The other {n_inf} have no "
            f"name in the files, so the names here are <b>inferred from their contents</b> and marked as such. "
            f"The weapon DLC packs, which the weapon stats name but without a hash, are listed "
            f'<a href="#weapon-packs">at the end</a>.</p>')
    b = [bar("All packs"),
         "<p>One row per pack. The counts are items of each vanity group; <i>Other</i> counts keys, mission items, "
         "schematics and materials. <i>DLC flag</i> is how many of its vanity items carry the DLC lock flag "
         "(see <a href=\"#flags\">below</a>). In the pack lists further down, <i>×N</i> after a name is the "
         "number of versions: colours for apparel, qualities for schematics.</p>",
         pack_overview(site, order, by_pack, extras),
         note("A content pack is not always a paid DLC. The lock flag is set per item: items that start locked "
              "(flag <code>L</code>) are things you earn or find in the game, like rewards and event items, and "
              "items with the <code>D</code> flag are downloadable content. Some packs mix flags; the "
              "<i>Lock flags</i> line of each pack below lists them. The Gen0 Editor reads a profile's owned packs from "
              "the items it has unlocked and the items the game set aside as inaccessible.", "data")]
    b += flags_section()
    for h in order:
        b += pack_section(site, h, by_pack[h], extras[h])
    b += weapon_pack_sections(site)
    # no table of contents: the overview table links every pack section
    site.page(PACKS, "Item packs", "\n".join(b), "character", sub="packs", lead=lead, head_extra=CSS, toc=False,
              kind="Character · Content packs",
              desc="Every Generation Zero content pack hash with its apparel, emotes, skins, vehicles, companion "
                   "parts, keys and schematics.")


def weapon_pack_sections(site):
    wp = weapon_packs(site)
    if not wp:
        return []
    rows = [[f'<a href="#pack-{slug(weapon_pack_name(p))}">{esc(weapon_pack_name(p))}</a>', len(ws),
             ", ".join(site.link("weapon", n) for _, n in ws)] for p, ws in wp.items()]
    out = [bar("Weapon packs", f"{len(wp)} packs"),
           "<p>The weapon stats name the DLC packs that add weapons. They have no cosmetics in the vanity list, "
           "and the stats don't give their content pack hashes, so they are listed here by name. Weapons not "
           "listed are base game.</p>",
           table(["Pack", "Weapons", "Weapon list"], rows, num={1}, cls="compact")]
    for p, ws in wp.items():
        name = weapon_pack_name(p)
        out.append(f'<h3 id="pack-{slug(name)}">{esc(name)} {tag("DLC", "dlc")}</h3>')
        out.append('<dl class="pklist">' + "".join(
            f"<dt>{esc(cat)}</dt><dd>{site.link('weapon', n)}</dd>" for cat, n in ws) + "</dl>")
    return out


def pack_name_html(site, h):
    pk = packs(site)[h]
    inferred = ' <span class="tag">name inferred</span>' if pk["inferred"] else ""
    return f'<a href="#pack-{h}">{esc(pk["name"])}</a>{inferred}'


def pack_overview(site, order, by_pack, extras):
    rows = []
    for h in order:
        its = by_pack[h]
        c = collections.Counter(i["g"] for i in its)
        rows.append([pack_name_html(site, h), f"<code>{h}</code>"] + [c.get(g) or None for g in GROUP_ORDER]
                    + [len(extras[h]) or None, sum(1 for i in its if i["l"].endswith("D")) or None])
    groups = {g["key"]: g["name"] for g in van(site)["groups"]}
    return table(["Pack", "Hash"] + [groups.get(g, g) for g in GROUP_ORDER] + ["Other", "DLC flag"], rows,
                 num=set(range(2, 10)), cls="compact pktab")


def flags_section():
    rows = [[f"<code>{esc(k)}</code>", esc(lbl), esc(why)] for k, (lbl, why) in FLAG.items()]
    return [bar("Lock flags", id="flags"),
            "<p>Every vanity item has a lock flag. The first letter is its starting state, a trailing D marks "
            "downloadable content. A pack's flags tell you how you get its items. No game file defines the "
            "letters; the meanings below are inferred from how the Gen0 Editor uses them. Heads and hands are "
            "chosen at character creation whatever their flag (they are all <code>L</code>).</p>",
            table(["Flag", "Shown as", "Meaning"], rows, sortable=False, cls="compact")]


def pack_section(site, h, its, extra):
    pk = packs(site)[h]
    out = [bar(pk["name"], f"pack {h}", id=f"pack-{h}")]
    desc = []
    if pk["dlc"]:
        desc.append(f"The content pack of the {site.link('dlc', pk['dlc'])} expansion (named in the mission data).")
    elif h == van(site)["base_pack"]:
        desc.append(f"The base game's own pack ({h}). Several free additions, such as the companion, apparel "
                    "crafting and event or story outfits, have packs of their own (flag <code>L</code> or "
                    "<code>U</code>, no <code>D</code>); see below.")
    elif pk["inferred"]:
        desc.append("The files don't name this pack; the name above is inferred from its contents.")
    flags = collections.Counter(i["l"] for i in its)
    if flags:
        desc.append("Lock flags: " + ", ".join(f"{n} × <code>{esc(l)}</code> ({esc(FLAG[l][0])})"
                                               for l, n in flags.most_common()) + ".")
    out.append(f"<p>{' '.join(desc)}</p>")
    groups = {g["key"]: g["name"] for g in van(site)["groups"]}
    for g in GROUP_ORDER:
        gi = [i for i in its if i["g"] == g]
        if gi:
            out.append(f'<h4>{esc(groups.get(g, g))} ({len(gi)})</h4>')
            out.append(pack_group_list(site, g, gi))
    by_kind = collections.defaultdict(list)
    for kind, name, link in extra:
        by_kind[kind].append((name, link))
    for kind, lst in by_kind.items():
        out.append(f"<h4>{esc(kind)} ({len(lst)})</h4>")
        out.append("<p>" + SEP.join(collapse(lst)) + "</p>")
    if not its and not extra:
        out.append('<p class="dim">No items found for this pack.</p>')
    return out


def collapse(lst):
    """[(name, link)] -> links, with repeats folded into 'name ×5' (schematics have one entry per quality)."""
    seen = collections.OrderedDict()
    for name, link in lst:
        if name in seen:
            seen[name][1] += 1
        else:
            seen[name] = [link, 1]
    return [link + (f' <span class="dim">×{n}</span>' if n > 1 else "") for link, n in seen.values()]


def pack_group_list(site, g, gi):
    """A pack's items of one vanity group, grouped by sub group; apparel folded into pieces with version counts."""
    subs = dict(subs_of(site, g))
    card_ids = {(c["slot"], c["base"], c["pack"]): c["id"] for c in apparel_cards(site)}
    by_sub = collections.OrderedDict((k, []) for k in subs)
    for i in gi:
        by_sub.setdefault(i["s"], []).append(i)
    rows = []
    for s, lst in by_sub.items():
        if not lst:
            continue
        if g == "apparel":
            pieces = collections.OrderedDict()
            for i in sorted(lst, key=lambda i: i["n"].lower()):
                pieces.setdefault(i["n"].split(", ")[0], []).append(i)
            cells = [f'<a href="~/{APPAREL}#{card_ids[(s, base, ps[0]["p"])]}">{esc(base)}</a>'
                     + (f' <span class="dim">×{len(ps)}</span>' if len(ps) > 1 else "")
                     for base, ps in pieces.items()]
        elif g == "skins":
            cells = [site.link("skin", i["r"], i["n"]) for i in sorted(lst, key=lambda i: i["n"].lower())]
        elif g == "companion":
            # the items section registers every companion part (kind 'item', internal name as alias)
            cells = collapse([(i["n"], site.link("item", i["r"], i["n"]))
                              for i in sorted(lst, key=lambda i: i["n"].lower())])
        else:
            cells = [site.link("vanity", i["r"], i["n"]) for i in sorted(lst, key=lambda i: i["n"].lower())]
        label = (site.link("weapon", subs.get(s, s)) if g == "skins" else esc(subs.get(s, s)))
        rows.append(f"<dt>{label} <span class=\"dim\">{len(lst)}</span></dt><dd>{SEP.join(cells)}</dd>")
    return f'<dl class="pklist">{"".join(rows)}</dl>'
