"""Character tab: skills, apparel, emotes & face paint, vehicles.

Pages
    character/skills.html    gamedata.json skills: one "Skill tree" menu with a tab per tree (Combat, Support, Survival,
                             Tech) drawn like the game's skill menu (icons, connector lines, rank pips, a details pane
                             and a small point planner in character.js), specializations, skill points and tips
    character/apparel.html   vanity.json group 'apparel': a card grid (one card per piece of clothing, its colours as
                             swatches; base game, then packs, then DLCs; two rows per slot until opened) filtered
                             by slot and pack, and a table split into one collapsed fold per slot
    character/emotes.html    vanity.json emotes (gestures, dances, companion tricks) and face paint; the dances that
                             come from videotape collectibles
    character/vehicles.html  vanity.json vehicles: every bike model with its paint jobs, Steam store text per model

Item packs are listed on the DLC page (home module, kind 'pack' -> dlc.html#pack-<hash>); pack tags here link there.
packs(site) stays here (pack hash -> short name, class) because other modules import it.

Kinds registered
    skill     key = skill name ('Reload Speed'), aliases = internal key (skill_01_02), upper-case name, hash
    apparel   key = item name (internal name when the name is taken), aliases = internal name, item hash; one extra
              searchable entry per card (base name, e.g. 'Adventurer fedora')
    vanity    every apparel, face paint, emote and vehicle item: key = name, aliases = internal name, hash; and each
              vehicle model ('Dirt bike')

vanity.json item fields (meanings checked against the Gen0 Editor, editor/web/panes.js and inv_editor.py):
    h  item hash (EquipmentHash in Profile.ItemStash)     n  display name        r  internal name
    g  group (apparel, facepaint, skins, companion, vehicles, emotes)           s  sub group (slot / weapon / bike)
    p  content pack hash (vanity.json base_pack = base game)                     i  icon file in img/vanity/
    l  lock flag: 'U' starts unlocked, 'L' starts locked, a trailing 'D' marks downloadable content (the editor
       tags 'UD' and 'LD' items as DLC). No game file defines it, so the readings are inferred; heads and hands
       (slot 'body') are all 'L' although you pick them in the character creator
    m  model hash, apparel only: colour variants of one piece of clothing share it (0 for heads and hands)
    x  body: 'F' / 'M' for the few items made for one body only
None of the hashes or internal names are printed on the pages (layout v2); they stay as search aliases.
"""
import collections
import re

from wiki.site import esc, slug, norm, fmt, table, bar, fold, panel, kv, tag, infobox, minimap, maplink

CSS = '<link rel="stylesheet" href="~/assets/character.css">'
JS = '<script src="~/assets/character.js" defer></script>'
HEAD = CSS + JS
SKILLS = "character/skills.html"
APPAREL = "character/apparel.html"
EMOTES = "character/emotes.html"
VEHICLES = "character/vehicles.html"

# Names for the content packs the data doesn't name, inferred from what is in them: (short label, long name).
# Only a fallback: pack tags use the name the DLC page (home module) registers for the pack when there is one.
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

# How you get an item, from its lock flag (vanity.json 'l'). No game file defines the flag; the readings follow how
# the Gen0 Editor treats it (it marks UD and LD items as DLC). flag -> (tag text, tag class, explanation)
AVAIL = {
    "U": ("Unlocked", "green", "every profile has it from the start"),
    "UD": ("With its pack", "dlc", "unlocked as soon as you own its pack (or add it, for the free packs)"),
    "L": ("Find or earn", "", "not given automatically: found or earned in the game"),
    "LD": ("Find or earn (pack)", "dlc", "needs its pack, and then you still find or earn it in the game"),
}


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
    """Content pack hash -> {short, name, inferred, cls, dlc}. Names from the data first, then INFERRED.
    Kept importable for the home module (from sections.character import packs)."""
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
        short, name = INFERRED.get(h, ("Item pack", "Item pack"))
        dlc_items = any(i["p"] == h and i["l"].endswith("D") for i in v["items"])
        out[h] = {"short": short, "name": name, "inferred": True, "cls": "dlc" if dlc_items else "", "dlc": None}
    site._char_packs = out
    return out


def pack_label(site, h):
    """The pack's name: what the DLC page calls it (home module), else our short name."""
    e = site.find("pack", str(h))
    if e and e.get("title") and e["title"] != "Item pack":
        return e["title"]
    return (packs(site).get(h) or {}).get("short", "Item pack")


def pack_tag(site, h):
    """The pack as a coloured tag that links to its entry on the DLC page."""
    t = tag(pack_label(site, h), (packs(site).get(h) or {}).get("cls", ""))
    u = site.url("pack", str(h))
    return f'<a class="ptag" href="{esc(u)}">{t}</a>' if u else t


def pack_key(site, h):
    """Filter token for a pack (no hashes in the HTML)."""
    return "p-" + slug(pack_label(site, h))


def avail_tag(l):
    """How you get an item, as a small outlined label (explained by avail_legend in the side panel)."""
    label, cls, why = AVAIL.get(l, (l, "", ""))
    return f'<span class="av {slug(l)}">{esc(label)}</span>'


def avail_legend(site, flags=("U", "UD", "L", "LD")):
    rows = "".join(f"<li>{avail_tag(f)} <span>{esc(AVAIL[f][2].capitalize())}.</span></li>" for f in flags)
    return (f'<ul class="avleg">{rows}</ul><p class="dim small">Read from each item\'s lock flag in the game '
            "files. No file says what the flag means; this is how the Gen0 Editor reads it.</p>")


def vimg(site, icon, alt="", cls="vi"):
    return site.img(f"img/vanity/{icon}", alt, cls=cls) if icon else ""


def first_free(site, kind, *keys):
    """The first of keys that isn't registered yet under kind (vanity names are not unique)."""
    for k in keys:
        if not site.find(kind, k):
            return k
    return keys[-1]


def page_of(site, kind, key):
    """The page (no #anchor) another section registered key under, or None."""
    e = site.find(kind, key)
    return "~/" + e["path"].split("#")[0] if e else None


# ---------------------------------------------------------------------------------------------------------------
# colour swatches from colour names ('black/white', 'dark blue', 'Bodacious Blue')
# ---------------------------------------------------------------------------------------------------------------
COLOURS = {
    "black": "#161616", "white": "#f1f1ef", "red": "#c4302b", "crimson": "#a3182a", "brown": "#74492a",
    "blue": "#2d67c8", "navy": "#1d2f63", "marine": "#1f3f7a", "sky": "#73b4e8", "green": "#3c8a3a",
    "army": "#4b5a2a", "forest": "#2f5a2f", "pink": "#e27aa8", "flamingo": "#f08fb0", "candy": "#f06aa8",
    "yellow": "#e6c337", "butter": "#f0dc7a", "gray": "#85898d", "grey": "#85898d", "purple": "#7b45b0",
    "amethyst": "#8a5cc0", "tyrian": "#66023c", "violet": "#9a6ad8", "blond": "#dcbc72", "blonde": "#dcbc72",
    "ginger": "#c0602a", "beige": "#d6c29e", "khaki": "#b3a777", "gold": "#d2ad3a", "silver": "#c0c4c8",
    "steel": "#7b8794", "bronze": "#a76d36", "brass": "#b5953a", "teal": "#23918d", "teel": "#23918d",
    "turquoise": "#38c4bb", "mint": "#9ee6c2", "lime": "#9bd43a", "orange": "#e47f28", "peach": "#f1b38a",
    "mustard": "#c69f24", "bordeaux": "#6a1a2a", "burgundy": "#6a1a2a", "emerald": "#1f8f5a", "ruby": "#b0142e",
    "off-white": "#e8e3d6",
}
LIGHTER = {"light", "bleach", "pale"}
DARKER = {"dark", "midnight"}


def _mix(hexc, other, t):
    a = [int(hexc[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(other[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def colours_of(label):
    """CSS colours named in a variant label, one per '/' part; [] when the label names no colour."""
    out = []
    for part in label.lower().replace(" with ", "/").split("/"):
        words = re.findall(r"[a-z-]+", part)
        col = None
        for n, w in enumerate(words):
            c = COLOURS.get(w) or COLOURS.get(w.split("-")[0])
            if c:
                prev = words[n - 1] if n else ""
                if prev in LIGHTER:
                    c = _mix(c, "#ffffff", .38)
                elif prev in DARKER:
                    c = _mix(c, "#000000", .42)
                col = c          # the last colour word of the part wins ('sky blue' -> sky, 'army green' -> green)
                if w in ("sky", "army", "forest", "navy", "marine", "candy", "butter", "amethyst", "flamingo",
                         "tyrian", "emerald", "ruby", "crimson"):
                    break
        if col:
            out.append(col)
    return out


def swatch(label):
    cs = colours_of(label)
    if not cs:
        return '<i class="sw none"></i>'
    if len(cs) == 1:
        bg = cs[0]
    else:
        step = 100 / len(cs)
        bg = "linear-gradient(135deg," + ",".join(
            f"{c} {step * k:.0f}% {step * (k + 1):.0f}%" for k, c in enumerate(cs)) + ")"
    camo = " camo" if "camo" in label.lower() else ""
    return f'<i class="sw{camo}" style="background:{bg}"></i>'


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
    if not fits:
        return icon
    if not icon:
        return f"{GENERIC}{fits[0]}_alpha.png"
    if not icon.startswith(GENERIC) or any(icon == f"{GENERIC}{f}_alpha.png" for f in fits):
        return icon
    return f"{GENERIC}{fits[0]}_alpha.png"


def slot_icon(key):
    return f"{GENERIC}{SLOT_ICONS[key][0]}_alpha.png" if key in SLOT_ICONS else None


def variant_label(it, base):
    rest = it["n"][len(base):].lstrip(", ").strip()
    return rest or "plain"


def card_labels(c):
    """Variant label of every item of a card; repeated labels (the game reuses some colour names) get ' 2', ' 3'."""
    if "_labels" not in c:
        seen, out = collections.Counter(), []
        total = collections.Counter(variant_label(i, c["base"]) for i in c["items"])
        for i in c["items"]:
            lab = variant_label(i, c["base"])
            seen[lab] += 1
            out.append(f"{lab} {seen[lab]}" if total[lab] > 1 else lab)
        c["_labels"] = {i["h"]: l for i, l in zip(c["items"], out)}
    return c["_labels"]


def apparel_cards(site):
    if hasattr(site, "_char_cards"):
        return site._char_cards
    order = {k: n for n, (k, _) in enumerate(subs_of(site, "apparel"))}
    groups = collections.OrderedDict()
    for it in sorted(items_of(site, "apparel"), key=lambda i: (order.get(i["s"], 99), i["n"].lower())):
        base = it["n"].split(", ")[0]
        groups.setdefault((it["s"], base, it["p"]), []).append(it)
    cards, used = [], set()
    for (s, base, p), its in groups.items():
        icons = collections.Counter(apparel_icon(i) for i in its)
        cid = f"ap-{slug(s)}-{slug(base)}"
        if cid in used:
            cid += "-" + slug(packs(site).get(p, {}).get("short", "pack"))
        n = 2
        while cid in used:
            cid, n = f"{cid}-{n}", n + 1
        used.add(cid)
        c = {"slot": s, "base": base, "pack": p, "items": its, "id": cid,
             "icon": icons.most_common(1)[0][0] if icons else None,
             "flags": sorted({i["l"] for i in its}, key=list(AVAIL).index),
             "body": sorted({i.get("x") for i in its} - {None})}
        cards.append(c)
    site._char_cards = cards
    return cards


# ===============================================================================================================
# collect
# ===============================================================================================================
def collect(site):
    collect_skills(site)
    collect_apparel(site)
    collect_vanity(site)


def collect_skills(site):
    sk = site.data("gamedata")["skills"]
    for t in sk["trees"]:
        for col in t["cols"]:
            for sid in col:
                s = sk["list"][sid]
                site.register("skill", s["name"], f"{SKILLS}#{slug(s['name'])}", s["name"],
                              icon=s["icon"].replace("assets/", "img/", 1),
                              desc=f"{t['name'].title()} skill, max level {s['max']}. "
                                   + " ".join(skill_text(s)[0])[:100],
                              aliases=[sid, s["upper"], str(s["hash"])],
                              keywords=f"skill {t['name'].lower()} {'specialization' if s['active'] else 'perk'}")


def collect_apparel(site):
    slot_name = dict(subs_of(site, "apparel"))
    for c in apparel_cards(site):
        icon = f"img/vanity/{c['icon']}" if c["icon"] else None
        path = f"{APPAREL}#{c['id']}"
        for it in c["items"]:
            key = first_free(site, "apparel", it["n"], it["r"])
            site.register("apparel", key, path, it["n"], icon=icon, aliases=[it["r"], str(it["h"])], search=False)
            site.register("vanity", first_free(site, "vanity", it["n"], it["r"]), path, it["n"], icon=icon,
                          aliases=[it["r"], str(it["h"])], search=False)
        n = len(c["items"])
        short = packs(site)[c["pack"]]["short"]
        key = first_free(site, "apparel", c["base"], f"{c['base']} ({short})")
        site.register("apparel", key, path, c["base"], icon=icon,
                      desc=f"{slot_name.get(c['slot'], c['slot'])}, {n} colour{'s' if n > 1 else ''} · {short}",
                      keywords="apparel clothing " + slot_name.get(c["slot"], ""))


def collect_vanity(site):
    for group, label, page, pre in (("facepaint", "Face paint", EMOTES, "fp"), ("emotes", "Emote", EMOTES, "em"),
                                    ("vehicles", "Vehicle paint job", VEHICLES, "veh")):
        for it in items_of(site, group):
            icon = f"img/vanity/{it['i']}" if it.get("i") else None
            site.register("vanity", first_free(site, "vanity", it["n"], it["r"]), f"{page}#{pre}-{slug(it['n'])}",
                          it["n"], icon=icon, aliases=[it["r"], str(it["h"])],
                          desc=f"{label} · {packs(site)[it['p']]['short']}", keywords=f"{group} {label.lower()}")
    for key, name in subs_of(site, "vehicles"):
        its = [i for i in items_of(site, "vehicles") if i["s"] == key]
        if not its:
            continue
        site.register("vanity", first_free(site, "vanity", name, key), f"{VEHICLES}#{vehicle_id(key, name)}",
                      model_name(key, name), icon=f"img/vanity/{its[0]['i']}" if its[0].get("i") else None,
                      aliases=[key, model_name(key, name)],
                      desc=f"Vehicle · {len(its)} paint jobs", keywords="vehicle bike motorbike flakmoped")


# ===============================================================================================================
# build
# ===============================================================================================================
def build(site):
    build_skills(site)
    build_apparel(site)
    build_emotes(site)
    build_vehicles(site)


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


def skill_img(site, s, key="icon", cls="skico"):
    return site.img(s[key].replace("assets/", "img/", 1), "", cls=cls) if s.get(key) else ""


def tree_points(L, t):
    return sum(L[sid]["max"] for col in t["cols"] for sid in col)


def build_skills(site):
    sk = site.data("gamedata")["skills"]
    L, trees = sk["list"], sk["trees"]
    total = sum(s["max"] for s in L.values())
    specs = [sid for sid, s in L.items() if s["active"]]
    lead = (f"<p>Skills are the perks you buy with skill points as your character levels up. There are "
            f"<b>{len(L)} skills</b> in four trees: {', '.join(t['name'].title() for t in trees)}. Each tree has two "
            f"columns of six skills, and the last skill of every column is a <b>specialization</b>, an ability you "
            f"switch on. Every rank costs one point; maxing everything takes <b>{total} points</b>.</p>")
    ib = infobox("Skills", [
        ("Trees", str(len(trees))), ("Skills", str(len(L))), ("Specializations", f"{len(specs)} (one active)"),
        ("Cost", "1 skill point per rank"), ("Points to max", f"{total}"),
    ], image=f"~/{sk['list'][specs[0]]['image'].replace('assets/', 'img/', 1)}"
    if site.has_file(L[specs[0]]["image"].replace("assets/", "img/", 1)) else None)
    side = [panel("Points per tree", kv(
        [(t["name"].title(), f'<a href="#tree-{esc(t["key"])}" data-tree="{esc(t["key"])}">'
                             f'{tree_points(L, t)} points</a>') for t in trees]))]
    b = [bar("Skill tree", f"{len(L)} skills · {total} points", id="skill-tree"),
         "<p>Pick a tree in the bar below. Click a skill to read what it does; with <b>+</b> and <b>−</b> you can "
         "plan your points. As in the game, a skill opens once the skill above it has a point.</p>",
         skill_menu(site, L, trees)]
    b += specialization_section(site, L, specs)
    b += skill_points_section(site, L, trees, specs)
    site.page(SKILLS, "Skills", "\n".join(b), "character", sub="skills", lead=lead, head_extra=HEAD,
              kind="Character · Skills", infobox_html=ib, side=side,
              desc=f"All {len(L)} Generation Zero skills in the Combat, Support, Survival and Tech trees: per-level "
                   "effects, prerequisites, specializations and skill point costs.")


def skill_menu(site, L, trees):
    """The four trees as one menu with a tab bar, like the game's skill menu."""
    tabs = "".join(
        f'<button type="button" role="tab" class="{"on" if ti == 0 else ""}" data-t="{esc(t["key"])}">'
        f'{esc(t["name"].title())}<small>{tree_points(L, t)} pts</small></button>' for ti, t in enumerate(trees))
    panes = []
    for ti, t in enumerate(trees):
        nodes, details = [], []
        first = True
        for ci, col in enumerate(t["cols"]):
            for ri, sid in enumerate(col):
                s = L[sid]
                sl = slug(s["name"])
                par = slug(L[s["parents"][0]]["name"]) if s["parents"] else ""
                cls = "sknd" + (" spec" if s["active"] else "") + (" sel" if first else "")
                nodes.append(
                    f'<button type="button" class="{cls}" id="{sl}" data-s="{sl}" data-max="{s["max"]}" '
                    f'data-par="{par}" style="grid-column:{ci + 1};grid-row:{ri + 1 if ri < 5 else 7}" '
                    f'aria-label="{esc(s["name"])}, {s["max"]} rank{"s" if s["max"] > 1 else ""}">'
                    f'<span class="skic">{skill_img(site, s)}</span>'
                    f'<span class="skpips">{"<i></i>" * s["max"]}</span>'
                    f'<span class="sknm">{esc(s["name"])}</span></button>')
                details.append(skill_detail(site, L, s, t, first))
                first = False
        panes.append(
            f'<div class="skpane{" on" if ti == 0 else ""}" id="tree-{esc(t["key"])}" data-t="{esc(t["key"])}" '
            f'role="tabpanel">'
            f'<div class="skhead"><span class="skttl">{esc(t["name"])} skill tree</span>'
            f'<span class="skpts"><span class="plan"><b class="skspent">0</b> / </span>{tree_points(L, t)} points'
            f'</span><button type="button" class="skreset plan">Reset</button></div>'
            f'<div class="skwrap"><div class="skgrid">{"".join(nodes)}<span class="skspec" '
            f'aria-hidden="true">Specializations</span></div>'
            f'<div class="skinfo">{"".join(details)}</div></div></div>')
    return (f'<div class="skmenu" id="skmenu"><div class="sktabs" role="tablist">{tabs}</div>'
            f'{"".join(panes)}</div>')


def skill_detail(site, L, s, t, on):
    paras, levels = skill_text(s)
    kind = "Specialization" if s["active"] else "Skill"
    lv = ""
    if levels:
        lv = '<ol class="sklv">' + "".join(
            f'<li data-l="{n}"><span class="lvn">{n}</span><span>{esc(e)}</span></li>' for n, e in levels) + "</ol>"
    elif s["max"] > 1:
        lv = f'<p class="dim small">The game gives no per-level values for its {s["max"]} ranks.</p>'
    req = (", ".join(f'<a href="#{slug(L[p]["name"])}">{esc(L[p]["name"])}</a>' for p in s["parents"])
           or '<span class="dim">nothing, top of the column</span>')
    unl = (", ".join(f'<a href="#{slug(L[c]["name"])}">{esc(L[c]["name"])}</a>' for c in s["children"])
           or '<span class="dim">nothing, end of the column</span>')
    cost = f'{s["max"]} point{"s" if s["max"] > 1 else ""}' + (f" ({s['max']} ranks)" if s["max"] > 1 else "")
    return (f'<div class="skd{" on" if on else ""}" data-s="{slug(s["name"])}">'
            f'<div class="skart">{skill_img(site, s, "image", "skimg")}<div class="skdt">{skill_img(site, s)}'
            f'<div><b>{esc(s["name"])}</b><span>{esc(t["name"].title())} · {kind}</span></div></div></div>'
            f'<div class="skdb">' + "".join(f"<p>{esc(p)}</p>" for p in paras) + lv +
            f'<dl class="skrel"><dt>Cost</dt><dd>{cost}</dd><dt>Requires</dt><dd>{req}</dd>'
            f'<dt>Unlocks</dt><dd>{unl}</dd></dl>'
            f'<div class="skplan plan"><button type="button" data-d="-1" aria-label="Remove a point">−</button>'
            f'<span class="skrk">0 / {s["max"]}</span>'
            f'<button type="button" data-d="1" aria-label="Add a point">+</button>'
            f'<span class="sklock dim small">Needs a point in the skill above</span></div></div></div>')


def specialization_section(site, L, specs):
    trees = site.data("gamedata")["skills"]["trees"]
    rows = []
    for sid in specs:
        s = L[sid]
        paras, _ = skill_text(s)
        effect = " ".join(p for p in paras if not p.startswith("Only one specialization"))
        rows.append([site.link("skill", s["name"], icon=True), esc(trees[s["tree"]]["name"].title()), esc(effect)])
    return [bar("Specializations", f"{len(specs)}"),
            f"<p>The {len(specs)} specializations sit at the bottom of the columns. You can learn all of them, but "
            "the game lets only one be active at a time, so you choose the one that is switched on.</p>",
            table(["Specialization", "Tree", "Effect"], rows, cls="spect")]


def skill_points_section(site, L, trees, specs):
    one_rank = [s for s in L.values() if s["max"] == 1 and not s["active"]]
    return [bar("Skill points and tips"),
            "<p>Each level-up gives you a skill point, and a rank of a skill costs one point. One rank is enough to "
            "open the next skill in the column, so the cheapest way down a column is one point per skill: "
            "<b>any specialization costs at least 6 points</b> (one rank in each of the five skills above it, plus "
            "the specialization itself).</p>",
            "<ul>"
            f"<li><b>One-point skills give their full effect at once</b>: "
            f"{', '.join(site.link('skill', s['name']) for s in one_rank)}. Of these, "
            f"{site.link('skill', 'Lockpicking')} (open locked doors with lockpicks) and "
            f"{site.link('skill', 'Healer')} (heal other players with a first aid kit) add abilities rather than "
            f"bonuses.</li>"
            f"<li><b>{site.link('skill', 'Armor')} protects against a different damage type per level</b>: level 1 "
            f"is bullets, level 2 explosives, level 3 gas. {site.link('skill', 'Chemist')} adds another 10% gas "
            f"resistance for one point.</li>"
            f"<li><b>Each damage skill covers one kind of hit</b>: {site.link('skill', 'Armor Damage')} (Combat) on "
            f"armor, {site.link('skill', 'Component Damage')} (Tech) on components, "
            f"{site.link('skill', 'Trigger Happy')} on automatic fire, and {site.link('skill', 'Make Em Count')} "
            f"on components with single shots from automatic weapons.</li>"
            f"<li><b>Binocular skills</b> ({site.link('skill', 'Enemy Marking')}, "
            f"{site.link('skill', 'Designated Target')}, {site.link('skill', 'Spotting Intel')}, "
            f"{site.link('skill', 'Remote Hacking')}) all work through the binoculars, so keep them on you.</li>"
            f"<li>{site.link('skill', 'Inquisitive Mind')} doubles mission XP at level 2 (+100%), so it pays back "
            f"fastest when you take it early.</li>"
            "</ul>"]


# ---------------------------------------------------------------------------------------------------------------
# apparel
# ---------------------------------------------------------------------------------------------------------------
def build_apparel(site):
    items = items_of(site, "apparel")
    cards = apparel_cards(site)
    subs = subs_of(site, "apparel")
    base = van(site)["base_pack"]
    n_base = sum(1 for i in items if i["p"] == base)
    sch = site.link("schematic", "Apparel", "apparel crafting schematics")
    lead = (f"<p>Apparel is the clothing your character wears: <b>{fmt(len(items))} items</b> in {len(subs)} "
            f"slots, from hats and hair to shoes and backpacks. Most pieces come in several colours, so they make "
            f"<b>{len(cards)} different pieces</b>. Unlocked apparel belongs to your profile, so every character on "
            f"it can wear it. Apparel only changes your looks; the bonuses (such as bullet resistance) come from the "
            f"{sch}.</p>")
    ib = infobox("Apparel", [
        ("Items", fmt(len(items))), ("Pieces", fmt(len(cards))), ("Slots", str(len(subs))),
        ("Base game", fmt(n_base)), ("From packs", fmt(len(items) - n_base)),
    ], image=f"~/img/vanity/{slot_icon('head')}" if site.has_file(f"img/vanity/{slot_icon('head')}") else None)
    side = [panel("How you get it", avail_legend(site))]
    b = [bar("Browse apparel", f"{len(cards)} pieces · {fmt(len(items))} items", id="browse"),
         "<p><b>Grid</b>: one card per piece of clothing, with its colours as little swatches. "
         "Each slot lists the base game first, then the outfit packs, then the DLCs. "
         "Pick a slot, a pack, or type a name or a colour. <b>Table</b>: every single item, one "
         "fold per slot.</p>",
         '<div class="tabset aptabs"><div class="tsbtns"><button class="on">Grid</button><button>Table</button></div>',
         '<div class="tspane">' + grid_filter(site, items, cards, subs) + apparel_grid(site, cards, subs) + "</div>",
         '<div class="tspane">' + apparel_tables(site, items, subs) + "</div></div>",
         bar("Good to know"),
         "<ul>"
         "<li><b>The pictures show the slot, not the look.</b> The game files give most apparel one generic icon per "
         "slot, so only a few pieces (the Experimental set, for example) have a picture of their own.</li>"
         "<li><b>Heads and hands</b> are picked in the character creator, whatever their lock flag says. A few of "
         "them, and one hairstyle, are made for one body only (marked <i>female</i> or <i>male</i>).</li>"
         f"<li>Packs are how the game files group content; many packs are free (rewards, events, updates). "
         f"Every pack tag links to its entry on the {site.link('dlc', 'Base game', 'DLC page')}.</li>"
         "</ul>"]
    site.page(APPAREL, "Apparel", "\n".join(b), "character", sub="apparel", lead=lead, head_extra=HEAD,
              kind="Character · Apparel", infobox_html=ib, side=side,
              desc=f"All {len(items)} Generation Zero apparel items: {len(cards)} pieces of clothing by slot and "
                   "pack, with their colours and how you get them.")


def grid_filter(site, items, cards, subs):
    """Slot chips (with the slot's icon and number of pieces) and pack chips (packs that have apparel)."""
    nslot = collections.Counter(c["slot"] for c in cards)
    slot_chips = "".join(
        f'<button class="chip ico" data-g="slot" data-f="s-{esc(k)}">{vimg(site, slot_icon(k), "", "chi")}'
        f'{esc(n)} <span class="n">{nslot[k]}</span></button>' for k, n in subs if nslot[k])
    npack = collections.Counter(c["pack"] for c in cards)
    pack_chips = "".join(
        f'<button class="chip" data-g="pack" data-f="{esc(pack_key(site, p))}">{esc(pack_label(site, p))} '
        f'<span class="n">{n}</span></button>' for p, n in npack.most_common())
    return (f'<div class="filterbar apfilter" data-for="apgrid"><input placeholder="Find a piece or a colour...">'
            f'<span class="count"></span>'
            f'<div class="fgrp"><span class="flbl">Slot</span><button class="chip on" data-g="slot" data-f="*">All'
            f'</button>{slot_chips}</div>'
            f'<details class="fgrp more"><summary><span class="flbl">Pack</span> <span class="dim small">'
            f'{len(npack)} packs</span></summary><div class="fgrp"><button class="chip on" data-g="pack" '
            f'data-f="*">All</button>{pack_chips}</div></details></div>')


def apparel_card(site, c):
    its = c["items"]
    icons = {apparel_icon(i) for i in its}
    img = vimg(site, c["icon"], "") or '<span class="vglyph"></span>'
    n = len(its)
    tags = [pack_tag(site, c["pack"])] + [avail_tag(f) for f in c["flags"]]
    tags += [tag({"F": "female", "M": "male"}[x]) for x in c["body"]]
    if n == 1:
        lab = variant_label(its[0], c["base"]) if its[0]["n"] != c["base"] else ""
        sw = f'<div class="apsw one">{swatch(lab) if lab and colours_of(lab) else ""}' \
             f'{f"<span>{esc(lab)}</span>" if lab else ""}</div>' if lab else ""
    else:
        # different pictures per colour: show them as thumbnails, else colour swatches with the names
        thumbs = len(icons) == n
        labs = card_labels(c)
        sw = '<div class="apsw">' + "".join(
            (f'<span class="apv th">{vimg(site, apparel_icon(i), labs[i["h"]], "vt")}'
             f'<span>{esc(labs[i["h"]])}</span></span>' if thumbs else
             f'<span class="apv">{swatch(labs[i["h"]])}<span>{esc(labs[i["h"]])}</span></span>') for i in its) + "</div>"
    words = " ".join(dict.fromkeys(i["n"] for i in its)) + " " + pack_label(site, c["pack"])
    meta = "1 version" if n == 1 else (
        f"{n} colours" if all(colours_of(variant_label(i, c["base"])) for i in its) else f"{n} versions")
    return (f'<div class="apc fitem" id="{c["id"]}" data-f="s-{esc(c["slot"])} {esc(pack_key(site, c["pack"]))}" '
            f'data-w="{esc(words)}"><div class="apimg">{img}</div><div class="apinfo"><b>{esc(c["base"])}</b>'
            f'<span class="apmeta">{meta}</span>'
            f'<div class="aptags">{"".join(tags)}</div>{sw}</div></div>')


MAIN_DLC = ("alpine", "fnix")      # pack classes of the two story DLCs, in release order


def source_order(site, c):
    """Sort key of a card by where it comes from: the base game, then the outfit packs (alphabetically by pack
    name), then the main DLCs (Alpine Unrest, then FNIX Rising); by name inside each group."""
    cls = (packs(site).get(c["pack"]) or {}).get("cls", "")
    if cls == "base":
        group = (0, 0, "")
    elif cls in MAIN_DLC:
        group = (2, MAIN_DLC.index(cls), "")
    else:
        group = (1, 0, pack_label(site, c["pack"]).lower())
    return group + (c["base"].lower(),)


def apparel_grid(site, cards, subs):
    """One section per slot. character.js shows the first two rows of each and a 'Show all' button."""
    out = ['<div id="apgrid" class="apslots">']
    for key, name in subs:
        cs = sorted((c for c in cards if c["slot"] == key), key=lambda c: source_order(site, c))
        if not cs:
            continue
        out.append(f'<section class="apslot"><h3 class="aph">{vimg(site, slot_icon(key), "", "chi")}{esc(name)}'
                   f' <small>{len(cs)} pieces</small></h3><div class="apgrid">'
                   + "".join(apparel_card(site, c) for c in cs) + '</div><button type="button" class="apmore" '
                   f'aria-expanded="false" hidden>Show all {len(cs)}</button></section>')
    out.append("</div>")
    return "".join(out)


def apparel_tables(site, items, subs):
    card_of = {i["h"]: c for c in apparel_cards(site) for i in c["items"]}
    out = ['<div class="filterbar" data-for="aptables"><input placeholder="Filter all items..."><span class="count">'
           '</span></div><div class="foldall" data-for="aptables"></div><div id="aptables">']
    for key, name in subs:
        its = sorted((i for i in items if i["s"] == key),
                     key=lambda i: (card_of[i["h"]]["base"].lower(), i["n"].lower()))
        if not its:
            continue
        rows = []
        for i in its:
            c = card_of[i["h"]]
            lab = card_labels(c)[i["h"]] if i["n"] != c["base"] or len(c["items"]) > 1 else ""
            rows.append([f'<a href="#{c["id"]}" class="aptl" data-tab="0">{esc(c["base"])}</a>',
                         (f'<span class="apcol">{swatch(lab) if colours_of(lab) else ""}{esc(lab)}</span>'
                          if lab else '<span class="dim">–</span>'),
                         pack_tag(site, i["p"]), avail_tag(i["l"])])
        out.append(fold(name, table(["Piece", "Colour / version", "Pack", "How you get it"], rows,
                                    cls="compact aptab"),
                        level=3, id=f"t-{slug(key)}", right=f"{len(its)} items"))
    out.append("</div>")
    return "".join(out)


# ---------------------------------------------------------------------------------------------------------------
# emotes and face paint
# ---------------------------------------------------------------------------------------------------------------
def build_emotes(site):
    em = items_of(site, "emotes")
    fp = items_of(site, "facepaint")
    base = van(site)["base_pack"]
    esubs = subs_of(site, "emotes")
    lead = (f"<p><b>Emotes</b> are the gestures and dances your character can perform; you choose which ones sit "
            f"in your emote wheel. <b>Face paint</b> goes over your character's face in the looks menu. The game "
            f"has {len(em)} emotes and {len(fp)} face paints. Like apparel, they belong to your profile, so every "
            f"character on it can use them.</p>")
    ib = infobox("Emotes & face paint", [(n, str(sum(1 for i in em if i["s"] == k))) for k, n in esubs]
                 + [("Face paint", str(len(fp))),
                    ("Base game", f"{sum(1 for i in em if i['p'] == base)} emotes, "
                                  f"{sum(1 for i in fp if i['p'] == base)} face paints")],
                 image=f"~/img/vanity/{em[0]['i']}" if em[0].get("i") and site.has_file(f"img/vanity/{em[0]['i']}")
                 else None)
    see = [l for l in (
        (page_of(site, "skin", items_of(site, "skins")[0]["r"]), "Weapon skins"),
        (page_of(site, "item", items_of(site, "companion")[0]["r"]), "Companion cosmetics"),
        ("~/" + VEHICLES, "Vehicle paint jobs"), ("~/" + APPAREL, "Apparel")) if l[0]]
    side = [panel("How you get it", avail_legend(site)),
            panel("Other cosmetics", "<ul class=\"plain\">" + "".join(
                f'<li><a href="{esc(u)}">{esc(t)}</a></li>' for u, t in see) + "</ul>")]
    b = emotes_section(site, em, esubs, base)
    b += face_paint(site, fp, base)
    b += videotape_map(site)
    site.page(EMOTES, "Emotes & face paint", "\n".join(b), "character", sub="emotes", lead=lead, head_extra=HEAD,
              kind="Character · Emotes", infobox_html=ib, side=side,
              desc=f"All {len(em)} Generation Zero emotes (gestures, dances, companion tricks) and {len(fp)} face "
                   "paints: where they come from and how you get them; the dances hidden on videotapes.")


def vtile(site, it, pre, extra=""):
    return (f'<div class="vtile" id="{pre}-{slug(it["n"])}">{vimg(site, it.get("i"), it["n"]) or "<span class=vglyph></span>"}'
            f'<b>{esc(it["n"])}</b>{extra}<span class="vtags">{pack_tag(site, it["p"])}{avail_tag(it["l"])}</span>'
            f'</div>')


def emotes_section(site, its, esubs, base):
    tapes = videotape_titles(site)
    out = [bar("Emotes", f"{len(its)}"),
           f"<p>{sum(1 for i in its if i['p'] == base and i['l'] == 'U')} base game emotes are unlocked from the "
           "start; the others come with packs or are found in the world. Companion tricks are the emotes of your "
           f"{site.link('machine', 'Runner', 'machine companion')}.</p>"]
    for key, name in esubs:
        sub = sorted((i for i in its if i["s"] == key), key=lambda i: i["n"].lower())
        grid = '<div class="vgrid">' + "".join(
            vtile(site, i, "em", '<span class="dim small">from a videotape</span>'
                  if norm(i["n"]) in tapes and i["p"] == base and i["l"] == "L" else "") for i in sub) + "</div>"
        out.append(fold(name, grid, open=True, level=3, id=f"emotes-{key}", right=f"{len(sub)}", cls="vfold"))
    locked = [i for i in its if i["s"] == "dance" and i["p"] == base and i["l"] == "L"]
    if locked:
        out += videotape_section(site, locked)
    return out


def videotapes(site):
    return [i for i in site.data("markers")["items"] if i.get("s") == "videotapes"]


def videotape_titles(site):
    """norm(title) of every videotape collectible ('Videotape 04 - Jschwiss' -> 'jschwiss')."""
    return {norm(i["n"].split(" - ", 1)[-1]) for i in videotapes(site)}


def videotape_section(site, dances):
    """Dance -> the videotape that unlocks it, with its region, the nearest named map location and a map link."""
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
        href = maplink(show=["videotapes"], region=[t["r"]] if t.get("r") else (), at=(t["x"], t["z"]), zoom=0.6,
                       focus=t["n"])
        rows.append([f'<a href="#em-{slug(d["n"])}">{esc(d["n"])}</a>',
                     (f'{esc(num.group(1))}' if num else "–", int(num.group(1)) if num else 0),
                     site.link("region", t["r"]),
                     (f'<span class="dim">{"at" if dist < 40 else f"{dist:,.0f} m from"}</span> '
                      f'{site.link("location", near["name"])}', round(dist)),
                     f'<a href="{href}">Map</a>'])
    if not rows:
        return []
    matched = len(rows)
    return [bar("Dances from videotapes", f"{matched} tapes", id="videotapes"),
            f"<p>{len(dances)} base game dances start locked. "
            + (f"All {matched}" if matched == len(dances) else f"{matched} of them")
            + f" share their name with one of the {site.link('collectible-type', 'videotapes', 'videotape')} "
            "collectibles: picking up the tape is how you get the dance. <i>Nearest place</i> is the closest named "
            "location on the map.</p>",
            table(["Dance", "Tape no.", "Region", "Nearest place", "Map"], rows, num={1}, cls="compact")]


def face_paint(site, its, base):
    its = sorted(its, key=lambda i: i["n"].lower())
    nb = sum(1 for i in its if i["p"] == base)
    rows = [[f'<span id="fp-{slug(i["n"])}">{esc(i["n"])}</span>', pack_tag(site, i["p"]), avail_tag(i["l"])]
            for i in its]
    return [fold("Face paint",
                 f"<p>{nb} of the {len(its)} face paints are base game items; the rest come with packs. They all "
                 "share one icon in the game files, so they are listed by name.</p>"
                 + table(["Face paint", "Pack", "How you get it"], rows, cls="compact"),
                 open=False, right=f"{len(its)}")]


def videotape_map(site):
    vt = videotapes(site)
    if not vt:
        return []
    return [minimap(vt[0]["x"], vt[0]["z"], vt[0]["n"], markers=[(t["x"], t["z"], t["n"]) for t in vt[1:]],
                    show=["videotapes"], small=True, zoom=1,
                    text=f"<p><b>The {len(vt)} videotapes on the map.</b> Each tape unlocks the dance with the same "
                         f"name. The {site.link('collectible-type', 'videotapes', 'videotapes page')} has every "
                         "tape with directions.</p>")]


# ---------------------------------------------------------------------------------------------------------------
# vehicles
# ---------------------------------------------------------------------------------------------------------------
# Families of bikes (by the model key in vanity.json) and where the Steam store describes each model:
# model key -> (Steam app id, text before the description on the store page)
FAMILIES = [
    ("bicycle", "Bicycle", ["v007_bike_bicycle"]),
    ("motorbikes", "Motorbikes", ["v012_bike_moped", "v011_bike_dirtbike", "v013_bike_military",
                                  "v014_bike_resistance"]),
    ("flakmopeds", "Flakmopeds", ["v015_bike_flakmoped", "v017_bike_ramming", "v019_bike_offroad",
                                  "v018_bike_utility"]),
]
STEAM_TEXT = {
    "v007_bike_bicycle": (1103830, "Cykel Bicycle:"),
    "v011_bike_dirtbike": (2144761, "Dirt Bike:"),
    "v013_bike_military": (2144761, "Military Motorcycle:"),
    "v014_bike_resistance": (2144761, "Resistance Bike:"),
    "v017_bike_ramming": (2689180, "- Stridsflak:"),
    "v019_bike_offroad": (2689180, "- Terrängflak:"),
    "v018_bike_utility": (2689180, "- Bruksflak:"),
}


def model_name(key, name):
    return {"v007_bike_bicycle": "Cykel (bicycle)"}.get(key, name[:1].upper() + name[1:])


def vehicle_id(key, name):
    return "veh-" + slug(re.sub(r"\(.*?\)", "", name))


def steam_dlc(site, appid):
    return next((d for d in site.data("steam")["dlc"] if d["appid"] == appid), None)


def steam_line(site, appid, prefix):
    """The text after prefix on the Steam store page of a DLC (the same line, or the next one when the prefix ends
    its line), or ''."""
    d = steam_dlc(site, appid)
    if not d:
        return ""
    lines = d.get("about", "").split("\n")
    for n, ln in enumerate(lines):
        i = ln.find(prefix)
        if i < 0:
            continue
        rest = ln[i + len(prefix):].strip()
        if not rest and n + 1 < len(lines):
            rest = lines[n + 1].strip()
        # keep it short: the first two sentences
        sent = re.split(r"(?<=[.!?])\s+", rest)
        return " ".join(sent[:2])
    return ""


def paint_label(it, model):
    """'Dirt Bike - Bodacious Blue' -> 'Bodacious Blue'; 'Flakmoped Blue' -> 'Blue'."""
    n = it["n"]
    if " - " in n:
        return n.split(" - ", 1)[1]
    m = re.match(r"^(.*)\s(\w+)$", n)
    return m.group(2) if m else n


def build_vehicles(site):
    its = items_of(site, "vehicles")
    models = dict(subs_of(site, "vehicles"))
    used = {i["s"] for i in its}
    lead = (f"<p>Vehicles get you across Östertörn faster: a bicycle, motorbikes and three-wheeled flakmopeds, "
            f"{len(used)} models with {len(its)} paint jobs in all. The Steam store says you spawn them at the "
            f"<b>vehicle station</b> of a safehouse. Each colour is a separate unlock, kept in your profile.</p>")
    first = next((i for i in its if i["s"] == "v007_bike_bicycle" and i["l"] == "UD"), its[0])
    sh = [i for i in site.data("markers")["items"] if i.get("s") == "playersafehouses"]
    sh_page = page_of(site, "safehouse", sh[0]["n"]) if sh else None
    ib = infobox("Vehicles", [
        ("Models", str(len(used))), ("Paint jobs", str(len(its))),
        ("Spawned at", f'<a href="{esc(sh_page)}">safehouse vehicle stations</a>' if sh_page
         else "safehouse vehicle stations"),
        ("Packs", str(len({i["p"] for i in its}))),
    ], image=f"~/img/vanity/{first['i']}" if first.get("i") and site.has_file(f"img/vanity/{first['i']}") else None)
    side = [panel("How you get them", avail_legend(site, sorted({i["l"] for i in its}, key=list(AVAIL).index)))]
    b = []
    for fkey, fname, keys in FAMILIES:
        keys = [k for k in keys if k in used]
        if not keys:
            continue
        n = sum(1 for i in its if i["s"] in keys)
        b.append(bar(fname, f"{len(keys)} model{'s' if len(keys) > 1 else ''} · {n} paint jobs", id=fkey))
        b.append(family_intro(site, fkey))
        for k in keys:
            b.append(vehicle_block(site, k, models.get(k, k), [i for i in its if i["s"] == k]))
    left = [k for k in models if k in used and not any(k in f[2] for f in FAMILIES)]
    if left:
        b.append(bar("Other vehicles"))
        for k in left:
            b.append(vehicle_block(site, k, models.get(k, k), [i for i in its if i["s"] == k]))
    if sh:
        b.append(minimap(sh[0]["x"], sh[0]["z"], sh[0]["n"], markers=[(m["x"], m["z"], m["n"]) for m in sh[1:]],
                         show=["playersafehouses"], small=True, zoom=1,
                         text=f"<p><b>Safehouses on the map.</b> Vehicles are spawned at the vehicle station of a "
                              f"safehouse; the map shows all {len(sh)} safehouses.</p>"))
    site.page(VEHICLES, "Vehicles", "\n".join(b), "character", sub="vehicles", lead=lead, head_extra=HEAD,
              kind="Character · Vehicles", infobox_html=ib, side=side,
              desc=f"All {len(used)} Generation Zero vehicles (Cykel bicycle, motorbikes, flakmopeds) and their "
                   f"{len(its)} paint jobs: which pack each comes from and how you get it.")


def family_intro(site, fkey):
    if fkey == "bicycle":
        d = steam_dlc(site, 1103830)
        var = steam_line(site, 1103830, "Variations:")
        return (f"<p>The {site.link('dlc', 'Bikes', 'Bikes')} update (free) added the Cykel. "
                + (f"The store page: <q>{esc(var)}</q>" if var else "") + "</p>") if d else ""
    if fkey == "motorbikes":
        d = steam_dlc(site, 2144761)
        txt = d.get("about", "") if d else ""
        facts = []
        if "fuel" in txt:
            facts.append("they need fuel (jerry cans from abandoned cars and gas stations, or crafted)")
        if "repair" in txt:
            facts.append("they need repairs now and then (repair kits, found or crafted)")
        if "loud" in txt:
            facts.append("they are loud and can draw machines to you")
        return (f"<p>The tuned moped is free; the other three came with the {site.link('dlc', 'Motorbikes Pack')}. "
                + (f"The store page says {', '.join(facts[:-1])} and {facts[-1]}.</p>" if len(facts) > 1 else "</p>"))
    if fkey == "flakmopeds":
        return (f"<p>Flakmopeds are three-wheeled motorbikes with a flatbed at the front. The plain Flakmoped is "
                f"free; the Stridsflak, Terrängflak and Bruksflak came with the "
                f"{site.link('dlc', 'Reinforced Flakmoped Pack')}.</p>")
    return ""


def model_icon(its, label):
    """The picture for a model: its 'default' icon, else a starting colour whose icon shows that colour, else the
    first paint job whose icon shows its own colour."""
    def own(i):
        words = re.findall(r"[a-z]+", paint_label(i, label).lower())
        return i.get("i") and any(w in i["i"] for w in words)
    for test in (lambda i: "default" in (i.get("i") or ""), lambda i: i["l"].startswith("U") and own(i), own,
                 lambda i: i.get("i")):
        i = next((i for i in its if test(i)), None)
        if i:
            return i["i"]
    return None


def vehicle_block(site, key, name, its):
    its = sorted(its, key=lambda i: i["n"].lower())
    label = model_name(key, name)
    st = STEAM_TEXT.get(key)
    line = steam_line(site, *st) if st else ""
    packs_ = sorted({i["p"] for i in its})
    icons = collections.Counter(i.get("i") for i in its)
    shared = len(icons) < len(its)
    big = model_icon(its, label)
    flags = collections.Counter(i["l"] for i in its)
    mixed = len(flags) > 1
    tiles = "".join(
        f'<div class="vptile" id="veh-{slug(i["n"])}">'
        f'{vimg(site, i.get("i"), i["n"], "vpi") if not shared else ""}'
        f'<span class="vpn">{swatch(paint_label(i, label))}{esc(paint_label(i, label))}</span>'
        f'{avail_tag(i["l"]) if mixed else ""}</div>' for i in its)
    how = ""
    given = [i for i in its if i["l"].startswith("U")]
    if mixed and given and len(given) < len(its):
        how = (f'<p class="small">{" and ".join(esc(paint_label(i, label)) for i in given)} '
               f'{"comes" if len(given) == 1 else "come"} with the pack; the other {len(its) - len(given)} '
               "colours you find or earn in the game.</p>")
    return (f'<div class="vblock" id="{vehicle_id(key, name)}"><div class="vbimg">{vimg(site, big, label, "vbi")}'
            f'</div><div class="vbinfo"><h3>{esc(label)}</h3><div class="vtags">'
            f'{"".join(pack_tag(site, p) for p in packs_)}{"" if mixed else avail_tag(its[0]["l"])}</div>'
            + (f'<p class="vq">{esc(line)} <span class="dim small">(Steam store)</span></p>' if line else "")
            + how + f'<div class="vpgrid{" noimg" if shared else ""}">{tiles}</div></div></div>')
