"""Augments & research: weapons/augments.html (overview, research, compatibility matrix, IDs, hidden entries) and
one page per augment, weapons/augments/<slug>.html.

Data (build/data):
  IDs.json       Augments: group (Primary / Support) -> augment name -> tier (Bronze / Silver / Gold, one augment has
                 extra 'Tier 4' / 'Tier 5' items) -> EquipmentName (equipment_augment_<x>_q1..), Augment (icon file),
                 Quality (tier frame file), "0" (the item id; augments come in a single quality)
  gamedata.json  research: one research task per augment (hash, slug, name, desc, task with [VALUE], task_one for a
                 count of 1, max, group, unlisted, tiers = the counter value that unlocks Bronze / Silver / Gold)
  augments.json  weapons = weapon names (IDs.json spelling); augments -> {only: the game's restriction text,
                 fits: [[weapon index, quality bit mask]], sch: [schematic hash of the Bronze / Silver / Gold design]}
                 Bit q-1 of the mask is weapon quality q (1 = Dilapidated ... 6 = Experimental); see
                 gen0-tools editor inv_editor.py (_aug_fits) and aug_groups_for for the slot rule.
  stats.json     player_weapons: each weapon's pack and the category shown (the weapons section's categories)
  stock.json     ammo and items named in research tasks
  icons.json     weapon icons (by item id) when the weapons section hasn't registered one
"""
import os
import re

from wiki.site import esc, slug, norm, fmt, table, infobox, bar, note, cards, kv, qbadge, tag, QUALITY

CSS = '<link rel="stylesheet" href="~/assets/augments.css">'
MAIN = "weapons/augments.html"
TIERS = ("Bronze", "Silver", "Gold")
GROUPS = ("Primary", "Support")
# Augment slots per weapon quality, as the game describes them (and the Gen0 Editor enforces: aug_groups_for):
# 2-3 crowns one Primary slot, 4-5 crowns a Primary and a Support slot, Dilapidated and Experimental none.
SLOTS = {1: (), 2: ("Primary",), 3: ("Primary",), 4: ("Primary", "Support"), 5: ("Primary", "Support"), 6: ()}
QNAME = {q: n for q, (n, _) in QUALITY.items()}
GROUP_COLOR = {"Primary": "#1c5777", "Support": "#1f6b5c"}
# IDs.json weapon categories that the restriction texts call "melee" / "explosive" / "handguns" / "shotguns"
CAT_WORDS = {"melee": {"Melee"}, "explosive": {"Grenade Launchers", "Recoilless Rifles"}, "handguns": {"Handguns"},
             "shotguns": {"Shotguns"}}

# What each research task talks about, so the augment page can link to it (keyed by research slug). Taken from the
# task text in gamedata.json; ("ammo", word) / ("item", word) list every stock item whose name has that word.
RELATED = {
    "acidic": [("ammo", "Corrosive")],
    "adhesive_rounds": [("ammo", "Tar")],
    "scorching": [("ammo", "HEAT")],
    "uranium_infused": [("ammo", "Radioactive")],
    "emp_detonation": [("item", "EMP"), ("ammo", "EMP"), ("ammo", "Electromagnetic")],
    "health_stealing": [("item", "First Aid Kit")],
    "flurry_of_blows": [("item", "Radioactive First Aid Kit")],
    "unstoppable_shells": [("item_raw", "_xr")],      # every vision module with an OPV mode (raw name ..._xr)
    "final_round": [("machine", "Vulture")],
    "rapid_reload": [("machine", "Reaper")],
    "small_fryer": [("machine", "Runner"), ("machine", "Tick"), ("machine", "Lynx")],
    "titan_toppler": [("machine", m) for m in ("Harvester", "Tank", "Wolf", "Firebird", "Reaper", "Vulture")],
    "crouching_tiger": [("machine", "Firebird")],
    "hip_shooter": [("machine", "Tank")],
    "oversized_clip": [("mg_mags", None)],
    "stabilization": [("weapon", "Granatgevär m/49")],
    "power_attacker": [("cat", "Melee")],
}

_CACHE = {}


# ---------------------------------------------------------------------------------------------------------------
# data model
# ---------------------------------------------------------------------------------------------------------------
def model(site):
    """Everything the pages need, built once: {'weapons', 'augs', 'by_name', 'hidden', 'unused_icons', ...}."""
    if id(site) in _CACHE:
        return _CACHE[id(site)]
    ids = site.data("IDs")
    adata = site.data("augments")
    research = {r["name"]: r for r in site.data("gamedata")["research"]}
    cat_of = {n: (c, e) for c, ws in ids["Weapons"].items() for n, e in ws.items()}

    weapons = []
    for i, name in enumerate(adata["weapons"]):
        cat, e = cat_of.get(name, ("Other", {}))
        weapons.append({"i": i, "name": name, "cat": cat, "tool": e.get("ToolID"), "ids": e})

    augs = []
    for group in GROUPS:
        for name, tiers in ids["Augments"].get(group, {}).items():
            augs.append(make_augment(name, group, tiers, research.get(name), adata["augments"].get(name, {})))
    by_name = {a["name"]: a for a in augs}

    hidden = [r for r in site.data("gamedata")["research"] if r["name"] not in by_name]
    used = {a["icon"] for a in augs} | {r["slug"] + ".png" for r in hidden}
    folder = os.path.join(site.out, "img", "augments")
    unused = sorted(f for f in os.listdir(folder) if f.endswith(".png") and f not in used) \
        if os.path.isdir(folder) else []
    m = {"weapons": weapons, "augs": augs, "by_name": by_name, "hidden": hidden, "unused_icons": unused}
    _CACHE[id(site)] = m
    return m


def make_augment(name, group, tiers, r, fit):
    """One augment: its items per tier, research task, fit masks and page path."""
    items = []
    for tname, v in tiers.items():
        items.append({"tier": tname, "nick": v.get("Nickname", ""), "raw": v.get("EquipmentName", ""),
                      "id": v.get("0", ""), "frame": v.get("Quality", "")})
    first = next(iter(tiers.values()), {})
    r = r or {}
    need = r.get("tiers") or []
    sch = fit.get("sch") or []
    for k, it in enumerate(items):          # research thresholds and design hashes exist for Bronze/Silver/Gold only
        it["need"] = need[k] if k < len(need) and it["tier"] in TIERS else None
        it["sch"] = sch[k] if k < len(sch) and it["tier"] in TIERS else None
    return {"name": name, "group": group, "slug": slug(name), "path": f"weapons/augments/{slug(name)}.html",
            "icon": first.get("Augment", ""), "items": items, "r": r, "rslug": r.get("slug", ""),
            "fits": {w: mk for w, mk in fit.get("fits", [])}, "only": fit.get("only", "")}


def stats_entry(site, w):
    """(stats.json player_weapons category, entry) for an augments.json weapon, or (None, {}).

    The weapons section registers the IDs.json spelling as an alias, so site.find() gives the stats key. Without
    that section, fall back to the stats name sharing the most words ('12G Pump Action' -> '12G Pump-Action');
    a tie gives (None, {})."""
    pw = site.data("stats")["player_weapons"]
    e = site.find("weapon", w["name"])
    for cat, ws in pw.items():
        if e and e["key"] in ws:
            return cat, ws[e["key"]]
    words = lambda n: set(re.findall(r"\w+", n.lower().replace("-", "")))
    scored = [(len(words(n) & words(w["name"])), cat, v) for cat, ws in pw.items() for n, v in ws.items()]
    best = max((x[0] for x in scored), default=0)
    hits = [(cat, v) for k, cat, v in scored if k == best]
    return hits[0] if best and len(hits) == 1 else (None, {})


def weapon_info(site, w):
    """{'name', 'url', 'icon', 'pack', 'dlc', 'type'} for an augments.json weapon. 'type' is the stats.json category
    the weapons section uses ('Sniper rifles', 'Launchers' ...); w['cat'] keeps the IDs.json one."""
    e = site.find("weapon", w["name"])
    stype, st = stats_entry(site, w)
    p = st.get("pack", "")
    dlc = p.endswith("(DLC)")
    pack = p[:-5].strip() if dlc else (p or "Base game")
    icon = e["icon"] if e and e.get("icon") else None
    if not icon:   # the weapons section isn't there: the best quality's item icon
        ip = site.data("icons").get(str(w["ids"].get("5", "")))
        icon = "img/" + ip if ip else None
    return {"name": e["title"] if e else w["name"], "url": "~/" + e["path"] if e else None, "icon": icon,
            "pack": pack, "dlc": dlc, "type": stype or w["cat"]}


def weapon_cell(site, w, icon=True):
    """Weapon icon + linked name (the link resolves through the weapons section's aliases)."""
    info = weapon_info(site, w)
    ic_path = info["icon"]
    ic = site.img(ic_path, "", cls="awicon") if icon and ic_path and site.has_file(ic_path) else ""
    label = f"{ic}{esc(info['name'])}"
    site.url("weapon", w["name"])           # records the link in the build report when it doesn't resolve
    url = info["url"]
    return f'<a class="awl" href="{esc(url)}">{label}</a>' if url else f'<span class="awl">{label}</span>'


def pack_cell(site, w, short=False):
    """The weapon's pack as a tag, linked to the DLC page when there is one. short drops ' Weapons Pack'
    ('Eastern European Weapons Pack' -> 'Eastern European', 'US Weapons Pack 2' -> 'US 2'); the full name stays in
    the title."""
    info = weapon_info(site, w)
    pack = info["pack"]
    if not info["dlc"]:
        return tag(pack or "Base game", "base")
    label = re.sub(r"\s*Weapons Pack\s*", " ", pack).strip() if short else pack
    t = tag(label or pack, "dlc").replace('<span ', f'<span title="{esc(pack)}" ', 1)
    url = site.url("dlc", pack)
    return f'<a href="{esc(url)}">{t}</a>' if url else t


def quals_of(mask, group):
    """Qualities with a slot of this group that the mask allows."""
    return [q for q in range(1, 7) if group in SLOTS[q] and mask >> (q - 1) & 1]


def slot_quals(group):
    return [q for q in range(1, 7) if group in SLOTS[q]]


def task_text(r, n):
    """The research task as the game words it for a target of n."""
    t = r.get("task_one") if n == 1 and r.get("task_one") else r.get("task", "")
    return t.replace("[VALUE]", fmt(n))


def counts_metres(r):
    """True when the counter itself is a distance ('Sprint for [VALUE] meters.'), not 'from more than 75 meters'."""
    return "[VALUE] meters" in r.get("task", "")


def km(r):
    """' That is 400 km.' for a task counted in metres."""
    return f" That is {fmt(r['max'] / 1000)} km." if counts_metres(r) else ""


def tier_label(it):
    """'Gold', or 'Tier 4' with an Unreleased tag for the items past Gold that nothing unlocks."""
    return esc(it["tier"]) + ("" if it["tier"] in TIERS else " " + tag("Unreleased", "unreleased"))


def tier_need_text(r, n):
    if n == 0:
        return "Unlocked from the start"
    return esc(task_text(r, n))


# ---------------------------------------------------------------------------------------------------------------
# icons
# ---------------------------------------------------------------------------------------------------------------
def aug_icon(site, a_icon, frame=None, size="m", title=None):
    """The augment's icon, on its tier frame (frame = 'q1.png' .. 'q3.png') like the game's Research menu."""
    ic = site.img(f"img/augments/{a_icon}", "", cls="ic") if a_icon else ""
    fr = site.img(f"img/augments/tiers/{frame}", "", cls="fr") if frame else ""
    t = f' title="{esc(title)}"' if title else ""
    return f'<span class="augi {size}{" t" if fr else ""}"{t}>{fr}{ic}</span>'


def tier_icons(site, a, size="m"):
    return "".join(aug_icon(site, a["icon"], it["frame"], size, it["nick"]) for it in a["items"]
                   if it["tier"] in TIERS)


# ---------------------------------------------------------------------------------------------------------------
# collect
# ---------------------------------------------------------------------------------------------------------------
def collect(site):
    m = model(site)
    for a in m["augs"]:
        aliases = [a["rslug"], a["slug"]] + [it["raw"] for it in a["items"]] + [it["nick"] for it in a["items"]] + \
                  [str(it["id"]) for it in a["items"] if it["id"]]
        site.register("augment", a["name"], a["path"], a["name"], icon=f"img/augments/{a['icon']}",
                      desc=f"{a['group']} augment. {a['r'].get('desc', '')}", aliases=[x for x in aliases if x],
                      keywords=f"augment {a['group']} research {a['rslug']}")
    for r in m["hidden"]:
        site.register("augment", r["name"], f"{MAIN}#{slug(r['name'])}", f"{r['name']} (hidden)",
                      icon=f"img/augments/{r['slug']}.png", desc=f"Hidden research entry. {r.get('desc', '')}",
                      aliases=[r["slug"]], keywords="augment research hidden unlisted")


# ---------------------------------------------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------------------------------------------
def build(site):
    m = model(site)
    add_types(site, m)
    build_main(site, m)
    for k, a in enumerate(m["augs"]):
        build_augment(site, m, a, m["augs"][k - 1], m["augs"][(k + 1) % len(m["augs"])])


def add_types(site, m):
    """w['type'] = the weapon category the weapons section shows; m['types'] = those categories in stats.json order
    (they are only known once every section's collect() has run, so this happens at build time)."""
    for w in m["weapons"]:
        w["type"] = weapon_info(site, w)["type"]
    order = list(site.data("stats")["player_weapons"])
    m["types"] = sorted(dict.fromkeys(w["type"] for w in m["weapons"]),
                        key=lambda t: order.index(t) if t in order else len(order))


# ---------------------------------------------------------------- main page
def build_main(site, m):
    augs = m["augs"]
    n = {g: sum(1 for a in augs if a["group"] == g) for g in GROUPS}
    lead = (f"<p>Augments are perks you put on a weapon: {n['Primary']} <b>Primary</b> augments that mostly change "
            f"how the weapon deals damage, and {n['Support']} <b>Support</b> augments that change how you handle "
            "it. You unlock each one by doing its <b>research task</b>, which comes in three tiers, Bronze, Silver "
            "and Gold. This page has every augment with its task and thresholds, which weapon (and which weapon "
            "quality) each fits, their internal names and item IDs, and the research entries that are in the game "
            "files but not in the game.</p>")
    body = [index_cards(site, m), section_slots(site, m), section_research(site, m), section_list(site, m),
            section_tasks(site, m), section_matrix(site, m), section_rules(site, m), section_ids(site, m),
            section_hidden(site, m)]
    site.page(MAIN, "Augments & research", "".join(body), "weapons", sub="augments", lead=lead, head_extra=CSS,
              kind="Weapons · Augments",
              desc="Every Generation Zero weapon augment: research tasks per tier, weapon compatibility by quality, "
                   "item IDs and hidden entries.")


def index_cards(site, m):
    """Icon tiles of every augment, by group (the full details are in the table further down)."""
    out = []
    for g in GROUPS:
        tiles = "".join(f'<a class="augtile" href="~/{a["path"]}" style="--c:{GROUP_COLOR[g]}">'
                        f'{aug_icon(site, a["icon"], "q3.png", "m")}<span>{esc(a["name"])}</span></a>'
                        for a in m["augs"] if a["group"] == g)
        out.append(f'<h3>{g} augments</h3><div class="augtiles">{tiles}</div>')
    return "".join(out)


def section_slots(site, m):
    rows = []
    for q in range(1, 7):
        s = SLOTS[q]
        crown = site.img(f"img/crowns/{q}.png", f"{q} crowns", cls="acrown")
        rows.append([f"{crown} {qbadge(q)}", "✓" if "Primary" in s else '<span class="dim">–</span>',
                     "✓" if "Support" in s else '<span class="dim">–</span>', len(s)])
    return (bar("Augment slots", "by weapon quality") +
            "<p>How many augments a weapon takes depends only on its quality. Worn and Good (2 and 3 crown) weapons "
            "have one Primary slot; Exceptional and Special (4 and 5 crown) weapons have a Primary and a Support slot; "
            "Dilapidated and experimental weapons have none. A weapon never takes two augments of the same group.</p>" +
            table(["Weapon quality", "Primary slot", "Support slot", "Augments"], rows, sortable=False, cls="compact",
                  num={3}) +
            note("Support augments only matter on Exceptional and Special weapons, while any Worn weapon already "
                 "takes a Primary augment. In the save an augment only exists on its weapon (the game never keeps "
                 "a loose one), so it goes when the weapon goes.", "info", "Tip"))


def section_research(site, m):
    augs = m["augs"]
    frames = []
    for k, t in enumerate(TIERS, 1):
        frames.append([site.img(f"img/augments/tiers/q{k}.png", t, cls="aframe"), f"<b>{t}</b>",
                       f"<code>equipment_augment_&lt;name&gt;_q{k}</code>", f"<code>q{k}.png</code>"])
    free = [a for a in augs if a["items"] and a["items"][0]["need"] == 0]
    one = [a for a in augs if a["items"] and a["items"][0]["need"] == 1]
    longest = max(augs, key=lambda a: a["r"].get("max", 0))
    out = [bar("Research and tiers"),
           "<p>Every augment has one research counter (the game keeps it with your currencies). Doing the task "
           "raises the counter, and when it reaches a tier's threshold that tier is researched. The counter is "
           "shared by the three tiers: an augment with thresholds 50 / 200 / 1,000 needs 1,000 in total for "
           "Gold, not 1,250. It stops at the Gold value. The task text in the Research menu always names the next "
           "threshold, so the number you see changes as you go.</p>"
           "<p>Finishing a tier's research is not quite the end: you then unlock that tier's <b>augmentation "
           "design</b> at a crafting station, and from then on can put the augment on your weapons. Unlocked "
           "designs are stored in your profile (not in one character), so they count for every character. Each "
           "tier is a separate item with its own icon frame:</p>",
           table(["Frame", "Tier", "Item internal name", "Frame file"], frames, sortable=False, cls="compact"),
           "<ul>"
           f"<li><b>Bronze from the start</b> ({len(free)}): " + ", ".join(site.link("augment", a["name"]) for a in free) +
           ". Their Bronze threshold is 0, so you can make the Bronze design straight away.</li>"
           f"<li><b>Bronze after one kill</b> ({len(one)}): " + "; ".join(
               f"{site.link('augment', a['name'])} ({esc(task_text(a['r'], 1))})" for a in one) + "</li>"
           f"<li><b>Biggest number</b>: {site.link('augment', longest['name'])} Gold, "
           f"“{esc(task_text(longest['r'], longest['r'].get('max', 0)))}”{km(longest['r'])}</li>"
           "</ul>"]
    if site.has_file("img/augments/tiers/q4.png"):
        out.append(note("The game files also hold a fourth (purple, with a star) tier frame, <code>q4.png</code>, "
                        "and one augment (" + site.link("augment", "Power Attacker") + ") has “Tier 4” and “Tier 5” "
                        "items. No research tier unlocks them; see <a href=\"#hidden-and-unused\">hidden and "
                        "unused</a>.", "data"))
    return "".join(out)


def section_list(site, m):
    rows = []
    for a in m["augs"]:
        r = a["r"]
        need = [it["need"] for it in a["items"] if it["tier"] in TIERS]
        nfit = sum(1 for mk in a["fits"].values() if mk)
        cells = [aug_icon(site, a["icon"], "q3.png"), f'<a href="~/{a["path"]}"><b>{esc(a["name"])}</b></a>',
                 tag(a["group"], "main" if a["group"] == "Primary" else "green"), esc(r.get("desc", ""))]
        cells += [n if n else '<span class="dim">start</span>' for n in need]
        cells += [nfit, esc(a["only"]) or '<span class="dim">–</span>']
        rows.append((a["group"].lower(), cells))
    head = ["", "Augment", "Group", "What it does", "Bronze", "Silver", "Gold", "Weapons", "Restriction"]
    html = table(head, [c for _, c in rows], cls="auglist", num={4, 5, 6, 7})
    html = add_row_filters(html, [f for f, _ in rows])
    return (bar("All augments", f"{len(m['augs'])} augments") +
            "<p>The descriptions are the game's own. Bronze / Silver / Gold are the research counter values that "
            "unlock each tier (“start” = unlocked from the beginning); the full task wording is in the next table. "
            "“Weapons” counts the weapons the augment fits at some quality, out of "
            f"{len(m['weapons'])}.</p>" +
            '<div class="filterbar" data-for="auglist"><input placeholder="Filter augments...">'
            '<button class="chip on" data-g="g" data-f="*">All</button>'
            '<button class="chip" data-g="g" data-f="primary">Primary</button>'
            '<button class="chip" data-g="g" data-f="support">Support</button><span class="count"></span></div>' +
            f'<div id="auglist">{html}</div>')


def add_row_filters(html, filters):
    """Give the n-th body row of a table() data-f=filters[n] (table() has no row attributes)."""
    it = iter(filters)
    head, _, rest = html.partition("<tbody>")
    rest = re.sub(r"<tr>", lambda _: f'<tr data-f="{esc(next(it, ""))}">', rest)
    return head + "<tbody>" + rest


def section_tasks(site, m):
    """One row per augment: the task with N for the number, then the target per tier."""
    rows = []
    for a in m["augs"]:
        r = a["r"]
        cells = []
        for it in a["items"]:
            if it["tier"] not in TIERS or it["need"] is None:
                continue
            n = it["need"]
            if n == 0:
                cells.append('<span class="dim">start</span>')
            else:   # the exact wording for this target (singular for 1) on hover
                cells.append(f'<span title="{esc(task_text(r, n))}">{fmt(n)}</span>')
        cells += ['<span class="dim">–</span>'] * (len(TIERS) - len(cells))
        task = esc(r.get("task", "").replace("[VALUE]", "N"))
        if counts_metres(r):
            task += f' <span class="dim">(Gold: {fmt(r["max"] / 1000)} km)</span>'

        rows.append([aug_icon(site, a["icon"], "q3.png", "s"), site.link("augment", a["name"]), task, *cells])
    head = ["", "Augment", "Research task", "Bronze", "Silver", "Gold"]
    return (bar("Research tasks") +
            "<p>The task as the game words it, with N standing for the number in the Research menu, and the value "
            "of N for each tier (“start” = researched from the beginning). Where a target is 1 the game uses "
            "the singular (“Destroy a Vulture.”); hover a number for the exact text.</p>" +
            '<div class="filterbar" data-for="augtasks"><input placeholder="Filter tasks (e.g. Tank, ammo, prone)...">'
            '<span class="count"></span></div>' +
            f'<div id="augtasks">{table(head, rows, cls="compact", num={3, 4, 5})}</div>')


# ---------------------------------------------------------------- compatibility matrix
def section_matrix(site, m):
    tabs, panes = [], []
    for g in GROUPS:
        tabs.append(f"<button>{g} augments</button>")
        panes.append(f'<div class="tspane">{matrix(site, m, g)}</div>')
    return (bar("Which augment fits which weapon") +
            "<p>One row per weapon, one column per augment. <span class=\"ok\">✓</span> means the augment fits every "
            "quality of that weapon that has a slot for it (Worn to Special for Primary augments, Exceptional and "
            "Special for Support augments). A quality badge means it fits only those qualities; an empty cell means "
            "it never fits. Hover a column header for the augment's name, or open its page for the details.</p>" +
            '<div class="filterbar" data-for="augmatrix"><input placeholder="Filter weapons..."></div>' +
            f'<div id="augmatrix"><div class="tabset"><div class="tsbtns">{"".join(tabs)}</div>{"".join(panes)}</div></div>')


def matrix(site, m, group):
    augs = [a for a in m["augs"] if a["group"] == group]
    sq = slot_quals(group)
    head = "".join(f'<th class="vh" title="{esc(a["name"])}"><a href="~/{a["path"]}">'
                   f'{aug_icon(site, a["icon"], None, "s")}<span>{esc(a["name"])}</span></a></th>' for a in augs)
    out = [f'<div class="tablewrap augmx"><table class="wt mx"><thead><tr><th class="wh">Weapon</th>{head}</tr></thead><tbody>']
    for cat in m["types"]:
        ws = [w for w in m["weapons"] if w["type"] == cat]
        out.append(f'<tr class="cat" data-w="{esc(" ".join(w["name"] for w in ws))}"><th colspan="{len(augs) + 1}">'
                   f'{esc(cat)}</th></tr>')
        for w in ws:
            cells = []
            for a in augs:
                qs = quals_of(a["fits"].get(w["i"], 0), group)
                if qs == sq:
                    cells.append('<td class="c ok" title="fits">✓</td>')
                elif qs:
                    cells.append(f'<td class="c part" title="{esc(", ".join(QNAME[q] for q in qs))} only">'
                                 + "".join(qbadge(q, True) for q in qs) + "</td>")
                else:
                    cells.append('<td class="c no"></td>')
            out.append(f'<tr data-w="{esc(cat)}"><td class="wn">{weapon_cell(site, w)}</td>{"".join(cells)}</tr>')
    out.append("</tbody></table></div>")
    return "".join(out)


# ---------------------------------------------------------------- restriction texts vs the files
def allowed_by_text(text, m):
    """Weapon indexes the restriction text allows, or None when the text can't be checked from categories."""
    t = text.lower()
    all_w = {w["i"] for w in m["weapons"]}
    in_cats = lambda words: {w["i"] for w in m["weapons"] if any(w["cat"] in CAT_WORDS[x] for x in words)}
    words = [x for x in CAT_WORDS if x in t]
    if not t:
        return all_w
    if "scope" in t:
        return None
    if t.startswith("only"):
        return in_cats(words)
    if "cannot" in t:
        return all_w - in_cats(words)
    return None


def text_mismatch(site, m, a):
    """"doesn't fit the X but does fit the Y" where the restriction text and the fit data disagree, else ''."""
    allowed = allowed_by_text(a["only"], m)
    if allowed is None:
        return ""
    fits = {i for i, mk in a["fits"].items() if mk}
    names = lambda ix: ", ".join(weapon_cell(site, m["weapons"][i], False) for i in sorted(ix))
    bits = []
    if allowed - fits:
        bits.append(f"doesn't fit the {names(allowed - fits)}")
    if fits - allowed:
        bits.append(f"does fit the {names(fits - allowed)}")
    return " but ".join(bits)


def section_rules(site, m):
    rows, odd = [], []
    for a in m["augs"]:
        fits = {i for i, mk in a["fits"].items() if mk}
        excl = [w for w in m["weapons"] if w["i"] not in fits]
        rows.append([site.link("augment", a["name"]), esc(a["only"]) or '<span class="dim">none</span>',
                     len(fits), ", ".join(weapon_cell(site, w, False) for w in excl) if 0 < len(excl) <= 14 else
                     (f'<span class="dim">the other {len(excl)} weapons</span>' if excl else
                      '<span class="dim">–</span>')])
        mism = text_mismatch(site, m, a)
        if mism:
            odd.append(f"<li>{site.link('augment', a['name'])}: {mism}.</li>")
    out = [bar("Restrictions", "the game's text and the files"),
           "<p>Many augments show a restriction in the game (“Melee weapons cannot use this augmentation.”). The "
           "table lists that text next to the weapons the compatibility rules actually leave out. “Melee” here "
           "is the bat, sledgehammer and pitchfork; “explosive” the grenade launchers and recoilless rifles.</p>",
           table(["Augment", "In-game restriction", "Fits", "Doesn't fit"], rows, cls="compact", num={2})]
    if odd:
        out.append(note("<p>Where the in-game text and the files differ (the files decide what you can actually "
                        "do):</p><ul>" + "".join(odd) + "</ul>", "data", "Text vs files"))
    return "".join(out)


# ---------------------------------------------------------------- item ids
def section_ids(site, m):
    rows = []
    for a in m["augs"]:
        for it in a["items"]:
            rows.append([site.link("augment", a["name"]), tier_label(it),
                         f"<code>{esc(it['raw'])}</code>", f"<code>{esc(it['id'])}</code>",
                         f"<code>{it['sch']}</code>" if it["sch"] else '<span class="dim">–</span>'])
    rrows = [[esc(a["name"]), f"<code>{esc(a['rslug'])}</code>", f"<code>{a['r'].get('hash', '')}</code>",
              a["r"].get("max", 0)] for a in m["augs"]]
    return (bar("Internal names and IDs", "for modders and save editing") +
            "<p>Each tier of an augment is its own item. <b>Item ID</b> is the equipment hash a save stores for an "
            "augment on a weapon; <b>design</b> is the hash of that tier's augmentation design (schematic), which "
            "the profile holds once it is unlocked. The research counter is a separate currency entry, listed in "
            "the second table with its maximum.</p>" +
            '<div class="filterbar" data-for="augids"><input placeholder="Filter by name, internal name or ID...">'
            '<span class="count"></span></div>' +
            f'<div id="augids">{table(["Augment", "Tier", "Internal name", "Item ID", "Design hash"], rows, cls="compact")}</div>' +
            "<h3>Research counters</h3>" +
            table(["Augment", "Research slug", "Counter hash", "Maximum"], rrows, cls="compact", num={3}))


# ---------------------------------------------------------------- hidden and unused
def section_hidden(site, m):
    out = [bar("Hidden and unused", tag("Not in the game", "unreleased")),
           "<p>The game files keep a few augments that you can't get. They are listed here for completeness.</p>"]
    if m["hidden"]:
        out.append("<h3>Research entries without an augment</h3>"
                   "<p>These research counters are in the game's currency list (marked <code>unlisted</code>), "
                   "but there is no augment item for them and they have no Bronze / Silver thresholds, only a "
                   "maximum. The Research menu doesn't show them.</p>")
        rows = []
        for r in m["hidden"]:
            rows.append([f'<span id="{slug(r["name"])}">{aug_icon(site, r["slug"] + ".png", None)}</span>',
                         f"<b>{esc(r['name'])}</b> {tag('Unreleased', 'unreleased')}", tag(r["group"].title(), "base"),
                         esc(r.get("desc", "")), esc(task_text(r, r.get("max", 0))), f"<code>{esc(r['slug'])}</code>"])
        out.append(table(["", "Name", "Group", "Description", "Task (maximum)", "Slug"], rows, cls="compact"))
    extra = [(a, it) for a in m["augs"] for it in a["items"] if it["tier"] not in TIERS]
    if extra:
        out.append("<h3>Extra tiers</h3><p>Items past Gold that no research tier or design unlocks:</p><ul>" + "".join(
            f"<li>{site.link('augment', a['name'])}: {esc(it['nick'])} (<code>{esc(it['raw'])}</code>, ID "
            f"<code>{esc(it['id'])}</code>)</li>" for a, it in extra) + "</ul>")
    if m["unused_icons"]:
        tiles = "".join(f'<div class="icon">{aug_icon(site, f, None, "l")}<span>{esc(f[:-4].replace("_", " ").capitalize())}'
                        f'</span><span class="dim"><code>{esc(f)}</code></span></div>' for f in m["unused_icons"])
        out.append("<h3>Icons without an augment</h3><p>The game's augment icon folder also has these icons, which "
                   "no augment, item or research task uses. The names are the file names, nothing more is known "
                   "about them from the files.</p>" + f'<div class="icongrid">{tiles}</div>')
    return "".join(out)


# ---------------------------------------------------------------- one augment
def build_augment(site, m, a, prev, nxt):
    r = a["r"]
    fits = {i: mk for i, mk in a["fits"].items() if mk}
    tiers = [it for it in a["items"] if it["tier"] in TIERS]
    box = infobox(a["name"], [
        ("Group", f"{a['group']} augment"),
        ("Slot on", ", ".join(QNAME[q] for q in slot_quals(a["group"])) + " weapons"),
        ("Fits", f"{len(fits)} of {len(m['weapons'])} weapons"),
        (None, "Research"),
        *[(it["tier"], "from the start" if it["need"] == 0 else fmt(it["need"])) for it in tiers],
        ("Research slug", f"<code>{esc(a['rslug'])}</code>"),
        (None, "Item IDs"),
        # infobox labels are plain text, so the Unreleased tag of the extra tiers goes with the value
        *[(it["tier"], f"<code>{esc(it['id'])}</code>" + ("" if it["tier"] in TIERS else
                                                          " " + tag("Unreleased", "unreleased")))
          for it in a["items"]],
    ], subtitle=f'<div class="augbig">{tier_icons(site, a, "l")}</div>')
    lead = (f"<p><b>{esc(a['name'])}</b> is a {a['group']} augment. The game describes it as: "
            f"“{esc(r.get('desc', ''))}”</p>")
    if a["only"]:
        lead += f"<p>{esc(a['only'])}</p>"
    body = [section_aug_research(site, a), related(site, m, a), section_aug_fits(site, m, a),
            section_aug_ids(site, a), nav_links(prev, nxt)]
    site.page(a["path"], a["name"], "".join(body), "weapons", sub="augments",
              crumbs=[("Augments & research", "~/" + MAIN)], desc=f"{a['name']}: {r.get('desc', '')}",
              infobox_html=box, kind=f"Augment · {a['group']}", lead=lead, head_extra=CSS)


def section_aug_research(site, a):
    r = a["r"]
    rows = []
    prev = 0
    for it in a["items"]:
        if it["tier"] not in TIERS or it["need"] is None:
            continue
        step = it["need"] - prev
        rows.append([aug_icon(site, a["icon"], it["frame"], "m"), f'<span class="tier {it["tier"].lower()}">'
                     f'{it["tier"]}</span>', it["need"], step if it["need"] else 0, tier_need_text(r, it["need"])])
        prev = it["need"]
    first = a["items"][0]["need"] if a["items"] else None
    tip = ""
    if first == 0:
        tip = note("The Bronze threshold is 0, so Bronze counts as researched from the start: you only need to "
                   "unlock its design at a crafting station.", "info", "Tip")
    return (bar("Research", f"maximum {fmt(r.get('max', 0))}") +
            "<p>One counter is shared by all three tiers. “Counter” is the value that unlocks the tier, “more” is "
            "how much further that is from the tier before it; the task text is the game's own for that "
            "threshold.</p>" +
            table(["", "Tier", "Counter", "More", "Task"], rows, sortable=False, cls="compact augres", num={2, 3}) + tip)


def related(site, m, a):
    """Links to the machines, ammo, items and weapons the research task names."""
    links = []
    stock = site.data("stock")["stock"]
    for kind, key in RELATED.get(a["rslug"], []):
        if kind in ("ammo", "item"):
            g = "ammo" if kind == "ammo" else "items"
            names = [s["name"] for s in stock if s["g"] == g and has_word(s["name"], key)]
            links += [site.link(kind, n) for n in names]
        elif kind == "item_raw":
            links += [site.link("item", s["name"]) for s in stock if s["g"] == "items" and key in s["raw"]]
        elif kind == "machine":
            links.append(site.link("machine", key))
        elif kind == "weapon":
            links.append(site.link("weapon", key))
        elif kind == "cat":
            links += [weapon_cell(site, w) for w in m["weapons"] if w["cat"] == key]
        elif kind == "mg_mags":
            links += mg_magazines(site, m)
    if not links:
        return ""
    words = {"acidic": "Ammo with “Corrosive” in its name", "adhesive_rounds": "Ammo with “Tar” in its name",
             "scorching": "Ammo with “HEAT” in its name", "uranium_infused": "Ammo with “Radioactive” in its name",
             "emp_detonation": "Items and ammo with EMP in their name", "health_stealing": "First aid kits",
             "oversized_clip": "Machine gun extended magazines (attachment data)",
             "unstoppable_shells": "Vision modules with an object-penetrating (OPV) mode"}
    if a["rslug"] in words:
        intro = (f"{words[a['rslug']]}. Which of these the game counts for the task is not in the data, so treat "
                 "the list as a pointer, not a rule.")
    else:
        intro = "What the research task or the description names:"
    return bar("Related") + f"<p>{intro}</p>" + f'<p class="related">{" · ".join(links)}</p>'


def has_word(name, word):
    """'5.56mm Corrosive Ammo' has the word 'Corrosive'; 'Highly-Radioactive ...' has 'Radioactive'."""
    return re.search(r"(^|[\s-])" + re.escape(word) + r"($|[\s-])", name) is not None


def mg_magazines(site, m):
    """Extended magazine attachments that fit a machine gun (IDs.json WPNCompat holds weapon ToolIDs)."""
    mg = {int(w["tool"]) for w in m["weapons"] if w["cat"] == "Light Machine Guns" and w["tool"]}
    out = []
    for name, v in site.data("IDs")["Attachments"].get("Magazines", {}).items():
        compat = {int(x) for x in str(v.get("WPNCompat", "")).replace(" ", "").split(",") if x}
        if compat & mg:
            out.append(site.link("attachment", name))
    return out


def section_aug_fits(site, m, a):
    sq = slot_quals(a["group"])
    rows, no = [], []
    for w in m["weapons"]:
        mk = a["fits"].get(w["i"], 0)
        if not mk:
            no.append(w)
            continue
        cells = ['<span class="ok">✓</span>' if mk >> (q - 1) & 1 else '<span class="dim">–</span>' for q in sq]
        rows.append((slug(w["type"]), [weapon_cell(site, w), esc(w["type"]), pack_cell(site, w, True), *cells,
                                       f'<code title="binary {mk:06b}">{mk}</code>']))
    head = ["Weapon", "Type", "Pack"] + [qbadge(q, True) for q in sq] + ["Mask"]
    html = add_row_filters(table(head, [c for _, c in rows], cls="compact augfits", raw_headers=True),
                           [f for f, _ in rows])
    cats = [c for c in m["types"] if any(f == slug(c) for f, _ in rows)]
    chips = "".join(f'<button class="chip" data-g="c" data-f="{slug(c)}">{esc(c)}</button>' for c in cats)
    tid = f"fits-{a['slug']}"
    out = [bar("Weapons it fits", f"{len(rows)} of {len(m['weapons'])}"),
           f"<p>The weapons {esc(a['name'])} goes on, at the qualities that have a {a['group']} slot "
           "(Q2 Worn, Q3 Good, Q4 Exceptional, Q5 Special). “Mask” is the raw value from the compatibility data: bit 1 is Dilapidated, bit 2 Worn and so on up to "
           "bit 6 Experimental (31 = Dilapidated to Special).</p>"]
    if len(cats) > 1:
        out.append(f'<div class="filterbar" data-for="{tid}"><input placeholder="Filter weapons...">'
                   f'<button class="chip on" data-g="c" data-f="*">All</button>{chips}<span class="count"></span></div>')
    out.append(f'<div id="{tid}">{html}</div>')
    gaps = [w for w in m["weapons"] if a["fits"].get(w["i"], 0) and quals_of(a["fits"][w["i"]], a["group"]) != sq]
    if gaps:
        out.append(note("The compatibility data leaves some qualities out for " + ", ".join(
            weapon_cell(site, w, False) for w in gaps) + ": the missing ones (–) can't take this augment.", "data"))
    if no:
        out.append(f"<p><b>Doesn't fit</b> ({len(no)}): " + ", ".join(weapon_cell(site, w, False) for w in no) + "</p>")
    mism = text_mismatch(site, m, a)
    if mism:
        said = f"The in-game text says “{esc(a['only'])}”" if a["only"] else "The game shows no restriction"
        out.append(note(f"{said}, but the compatibility data {mism}.", "data", "Text vs files"))
    return "".join(out)


def section_aug_ids(site, a):
    rows = [[aug_icon(site, a["icon"], it["frame"] or None, "s"), tier_label(it), esc(it["nick"]),
             f"<code>{esc(it['raw'])}</code>", f"<code>{esc(it['id'])}</code>",
             f"<code>{it['sch']}</code>" if it["sch"] else '<span class="dim">–</span>'] for it in a["items"]]
    out = [bar("Internal names and IDs"),
           "<p>Each tier is a separate item. The design hash is the tier's augmentation design, which your profile "
           "holds once you have unlocked it.</p>",
           table(["", "Tier", "Item name", "Internal name", "Item ID", "Design hash"], rows, sortable=False,
                 cls="compact"),
           kv([("Research slug", f"<code>{esc(a['rslug'])}</code>"),
               ("Research counter hash", f"<code>{a['r'].get('hash', '')}</code>"),
               ("Icon file", f"<code>{esc(a['icon'])}</code>")])]
    if any(it["tier"] not in TIERS for it in a["items"]):
        out.append(note("The items past Gold are in the game's item list, but no research tier or design unlocks "
                        "them, so you can't get them in the game.", "warn"))
    return "".join(out)


def nav_links(prev, nxt):
    return (f'<p class="augnav"><a href="~/{prev["path"]}">← {esc(prev["name"])}</a>'
            f'<a href="~/{MAIN}">All augments</a><a href="~/{nxt["path"]}">{esc(nxt["name"])} →</a></p>')
