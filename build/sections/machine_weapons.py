"""Machines tab, part 2: machine weapons, difficulty & co-op scaling, and rivals.

Pages (layout v2: short intro, infobox on the right, short sections; no internal names or hashes are printed)
  machines/weapons.html     every machine weapon in stats.json machine_weapons (64), one open fold per kind with a
                            block per weapon (one anchor each); the sortable overview table is the last section,
                            collapsed
  machines/difficulty.html  stats.json difficulty: damage multipliers per difficulty and number of players
  machines/rivals.html      gamedata.json rival_levels, threat (a bar chart: score per threat level and the
                            new-rival chance), the Reaper and the Vulture (short, their pages are in 'machines'),
                            rival titles: a title builder (static/machine_weapons.js) and a tree of every title

Data (build/data)
  stats.json     machine_weapons   key (unique colloquial name) -> internal_name, kind, faction, damage{...}, used_by,
                                   note. damage can hold damage_per_projectile / projectiles_per_shot, blast,
                                   submunition (+ submunitions = count), damage_over_time [..], contact, heal_pulse.
                                   _about.reading_the_numbers explains the fields (we pass it on).
                 difficulty        Easy/Medium/Hard -> [{players, player_damage_to_machines, machine_damage_to_players}]
                 machine_health    used for the HP of each weapon's component on each machine
  loadouts.json  faction > class > type > layout > weapons: the short names, in-game component labels, ammo and
                 damage-effect internal names and notes of each weapon on each layout
  gamedata.json  rival_levels [{level, xp, health, damage, reward}], threat [{score, chance}] (index = threat level;
                 the Gen0 Editor shows level 1..n and calls score the region's threat points, InsurrectionScore),
                 titles {text hash: text} (the rival titles plus four rival-history texts), history {creation,
                 level_up} (hashes of those history texts)

Kinds registered: 'machine-weapon' -- key = the stats.json key ('Autocannon (Tank)'); aliases = internal weapon name,
ammo / damage-effect internal names and the short loadout name ('Autocannon'). A short name used by several weapons
goes to the one on the most layouts (first registration wins). Also 'Machine weapons', 'Difficulty' and 'Rivals'
for the three pages.
"""
import collections
import json
import math
import re

from wiki.site import esc, slug, norm, fmt, pct, bar, note, kv, tag, fold, infobox, maplink, REGIONS

CSS = ('<link rel="stylesheet" href="~/assets/machine_weapons.css">'
       '<script src="~/assets/machine_weapons.js" defer></script>')
WEAPONS_PAGE = "machines/weapons.html"
DIFF_PAGE = "machines/difficulty.html"
RIVALS_PAGE = "machines/rivals.html"

# kind -> (section title, what the kind means). Order = page order.
KINDS = {
    "ranged": ("Ranged weapons", "Guns, cannons and launchers that fire projectiles at you. Damage is per projectile "
                                 "(bullet, pellet, shell or rocket); explosive projectiles add a blast around the "
                                 "point of impact."),
    "melee": ("Melee attacks", "Close-range attacks: stomps, kicks, blade strikes and bites. The game stores most of "
                               "them as a small blast centred on the machine, so the radius is how close you must be "
                               "to get hit."),
    "explosive": ("Explosions", "Machines that blow themselves up."),
    "ability": ("Abilities", "Area attacks a machine triggers from a component rather than a gun: concussion and "
                             "shock pulses, neurotoxin gas, walls of fire and the Reaper's thermobaric blast."),
    "support": ("Support", "Components that help other machines instead of shooting you."),
    "support drop": ("Support drops", "Things the Vulture drops from its bomb bays."),
    "bombs": ("Bombs", "What the Firebird drops from its two bomb bays."),
    "defensive": ("Defensive", "Components that protect the machine itself."),
}
KIND_TAG = {"ranged": "main", "melee": "soviet", "explosive": "dlc", "ability": "alpine", "support": "green",
            "support drop": "green", "bombs": "dlc", "defensive": "base"}
DIFFS = ("Easy", "Medium", "Hard")
PEOPLE = {"Friends", "Allies", "Comrades", "Companions", "Society", "Homo Sapiens", "All Humankind", "the Survivors",
          "Humanity", "Humans", "Meatbags", "Teammates", "the Resistance"}
# place words in titles that are a region of the map: title text -> region key (world section)
REGION_PLACES = {"the Archipelago": "archipelago", "the Farmlands": "farmlands", "the Marshlands": "marshlands",
                 "the Forest": "forest", "Himfjäll": "alpine"}
# names from Russian folklore and myth that appear in the rival titles (shown as one group on the rivals page)
FOLKLORE = ("Baba Yaga", "Koschei", "Perun", "Zmey", "Kikimora", "Ilya Muromets", "Dobrynya Nikitich",
            "Alyosha Popovich", "Svyatogor", "Mikula Selyaninovich")
_CACHE = {}
# the 'Class X (unidentified)' Tick is in the files but unused in the game; the machines section leaves it out
SKIP_MACHINE = re.compile(r"\(class x\)$", re.I)
# weapons whose blast in the files is the explosion when the dropped object is destroyed, not part of an attack
DESTROYED_BLAST = {"Turret Drop"}


# ---------------------------------------------------------------------------------------------------------------
# data model: one dict per machine weapon, joined with the loadouts and the component health of its part
# ---------------------------------------------------------------------------------------------------------------
def _layouts(site):
    """Every loadout layout in file order: (machine name, layout label, layout dict, health layout or None)."""
    health = {}
    for fac, classes in site.data("stats")["machine_health"].items():
        for cv in classes.values():
            for tv in cv["types"].values():
                for l in tv["layouts"].values():
                    health[l["internal_name"]] = l
    lo = site.data("loadouts")
    out = []
    for fac in ("Swedish", "Soviet"):
        for cv in lo[fac].values():
            for tv in cv["types"].values():
                for label, l in tv["layouts"].items():
                    out.append((l["machine"]["colloquial_name"], label, l, health.get(l["internal_name"])))
    return out


def _stats_key(mws, w, machine):
    """The stats.json key of a loadout weapon (internal name; machine decides between same-named entries)."""
    cands = [k for k, d in mws.items() if d["internal_name"] == w["internal_name"]]
    if len(cands) > 1:
        cands = [k for k in cands if machine in mws[k].get("used_by", [])] or cands
    return cands[0] if cands else None


def clean_note(n):
    """A data note in plain words: notes about internal names are dropped, model / ammo file names taken out."""
    if not n or n.startswith("Internal name"):
        return None
    n = re.sub(r"\s*\(model [a-z0-9_]+\)", "", n)
    n = n.replace("AreaDamage component", "area damage")
    n = re.sub(r"the ammo this layout loads is '([a-z0-9_]+)'",
               lambda m: "this layout loads " + ("incendiary" if "incendiary" in m.group(1) else "explosive") +
                         " rounds", n)
    return None if re.search(r"\b[a-z]+_[a-z0-9_]+\b", n) else n


def model(site):
    if id(site) in _CACHE:
        return _CACHE[id(site)]
    mws = site.data("stats")["machine_weapons"]
    layouts = _layouts(site)
    machine_order, layout_count = [], collections.Counter()
    for machine, _, _, _ in layouts:
        if machine not in machine_order:
            machine_order.append(machine)
        layout_count[machine] += 1
    ws = {}
    for key, d in mws.items():
        dmg = dict(d.get("damage") or {})
        # a blast that only happens when the weapon itself is destroyed is not part of its attack
        destroyed = dmg.pop("blast", None) if key in DESTROYED_BLAST else None
        ws[key] = {"key": key, "d": d, "dmg": dmg, "destroyed_blast": destroyed, "anchor": slug(key),
                   "short": set(), "labels": set(), "ammo": set(), "effects": set(), "notes": [],
                   # layouts: machine -> [layout labels] (each once); slots: (machine, label) -> copies on it
                   # comps: machine -> {layout label: component health dict}
                   "layouts": {}, "slots": collections.Counter(), "comps": {}}
        if clean_note(d.get("note")):
            ws[key]["notes"].append(clean_note(d["note"]))
    for machine, label, l, h in layouts:
        comps = {c["component"].lower(): c for c in (h or {}).get("components", [])}
        for w in l["weapons"]:
            k = _stats_key(mws, w, machine)
            if not k:
                continue
            e = ws[k]
            e["short"].add(w["colloquial_name"])
            # a layout can carry two copies of a weapon: list the layout once and count the copies
            if label not in e["layouts"].setdefault(machine, []):
                e["layouts"][machine].append(label)
            e["slots"][(machine, label)] += 1
            if w.get("in_game_component_name"):
                e["labels"].add(w["in_game_component_name"])
                c = comps.get(w["in_game_component_name"].lower())
                if c:
                    e["comps"].setdefault(machine, {})[label] = c
            for f, s in (("ammo_internal_name", "ammo"), ("damage_effect_internal_name", "effects")):
                if w.get(f):
                    e[s].add(w[f])
            # skip a loadout note that repeats the start of one we already have
            wn = clean_note(w.get("note"))
            if wn and not any(n.startswith(wn.rstrip(".")) for n in e["notes"]):
                e["notes"].append(wn)
    for e in ws.values():
        for k in [k for k in e["layouts"] if SKIP_MACHINE.search(k)]:
            del e["layouts"][k]
            e["comps"].pop(k, None)
        e["used_by"] = sorted((u for u in e["d"].get("used_by", []) if not SKIP_MACHINE.search(u)),
                              key=lambda m: machine_order.index(m) if m in machine_order else 999)
        e["n_layouts"] = sum(len(v) for v in e["layouts"].values())
    m = {"weapons": ws, "layout_count": layout_count, "machine_order": machine_order}
    _CACHE[id(site)] = m
    return m


# ---------------------------------------------------------------------------------------------------------------
# damage arithmetic (all values are before difficulty scaling)
# ---------------------------------------------------------------------------------------------------------------
def dot_ticks(dot):
    """Number of ticks in one exposure: duration / tick interval, at least one."""
    return max(1, int(math.floor(dot["duration_seconds"] / dot["tick_seconds"] + 1e-9)))


def dot_total(dot):
    return dot["damage_per_tick"] * dot_ticks(dot)


def to_player_dots(dmg):
    return [x for x in dmg.get("damage_over_time") or [] if x.get("target") == "characters"]


def direct_per_shot(dmg):
    dpp = dmg.get("damage_per_projectile")
    return dpp * (dmg.get("projectiles_per_shot") or 1) if dpp else None


def blast_per_shot(dmg):
    """Blast damage to you if every projectile's (or bomblet's) blast catches you."""
    b = (dmg.get("blast") or {}).get("damage_to_players")
    if b is not None:
        return b * (dmg.get("projectiles_per_shot") or 1)
    sub = (dmg.get("submunition") or {}).get("blast") or {}
    if sub.get("damage_to_players") is not None:
        return sub["damage_to_players"] * (dmg.get("submunitions") or 1)
    return None


def max_per_attack(dmg):
    """Upper bound of what one attack does to you: every projectile, blast, bomblet and burn tick lands.
    None when the weapon has no damage to players in the files."""
    parts = [direct_per_shot(dmg), blast_per_shot(dmg)]
    parts += [dot_total(x) for x in to_player_dots(dmg)]
    if dmg.get("contact"):
        parts.append(dmg["contact"]["damage_to_players_max"])
    parts = [p for p in parts if p]
    return sum(parts) if parts else None


def one_hit(dmg):
    """What a single projectile or bomblet does to you, its blast and burn included (contact: the top hit)."""
    b = (dmg.get("blast") or {}).get("damage_to_players")
    if b is None:
        b = ((dmg.get("submunition") or {}).get("blast") or {}).get("damage_to_players")
    parts = [dmg.get("damage_per_projectile"), b] + [dot_total(x) for x in to_player_dots(dmg)]
    if dmg.get("contact"):
        parts.append(dmg["contact"]["damage_to_players_max"])
    parts = [p for p in parts if p]
    return sum(parts) if parts else None


def radius_players(dmg):
    b = dmg.get("blast") or (dmg.get("submunition") or {}).get("blast") or {}
    return b.get("radius_vs_players_m") or (dmg.get("contact") or {}).get("radius_vs_players_m")


def blast_machines(dmg):
    b = dmg.get("blast") or (dmg.get("submunition") or {}).get("blast") or {}
    return b.get("damage_to_machines"), b.get("radius_vs_machines_m")


def diff_table(site):
    """{(difficulty, players): (your damage to machines, machine damage to you)}."""
    out = {}
    for dname, rows in site.data("stats")["difficulty"].items():
        for r in rows:
            out[(dname, r["players"])] = (r["player_damage_to_machines"], r["machine_damage_to_players"])
    return out


# ---------------------------------------------------------------------------------------------------------------
# small html helpers
# ---------------------------------------------------------------------------------------------------------------
def num(v, digits=2, base=None):
    """A numeric table cell: (html, attrs). base = unscaled value for the difficulty switch on the weapons page."""
    if v is None:
        return None
    attrs = {"class": "n", "data-v": v}
    if base is not None:
        attrs["data-b"] = base
    return fmt(v, digits), attrs


def times_cell(each, n):
    """'10 × 6' cell sorted by the product; the per-projectile number rescales with the difficulty switch."""
    if not each:
        return None
    return (f'<span class="dsc" data-b="{each}">{fmt(each)}</span>' + (f" × {n}" if n > 1 else ""),
            {"class": "n", "data-v": each * n, "data-b": each * n})


def blast_cell(dmg):
    """Blast to you: damage per projectile / bomblet × count and the radius."""
    b = dmg.get("blast")
    n = dmg.get("projectiles_per_shot") or 1
    if not b:
        b = (dmg.get("submunition") or {}).get("blast")
        n = dmg.get("submunitions") or 1
    if not b or b.get("damage_to_players") is None:
        return None
    each = b["damage_to_players"]
    h, a = times_cell(each, n) or (fmt(each), {"class": "n", "data-v": 0})
    return h + f' <small class="dim">{fmt(b.get("radius_vs_players_m"))} m</small>', a


def _attrs(a):
    return "".join(f' {k}="{esc(v)}"' for k, v in (a or {}).items())


def rtable(headers, rows, num_cols=(), cls="", tid=None, sortable=True):
    """Like wiki.site.table(), but each row is (row attrs, cells) and a cell may be html, a number, None or
    (html, td attrs), so rows can carry data-f for a filterbar and cells data-v / data-b."""
    num_cols = set(num_cols)
    out = [f'<div class="tablewrap"{_attrs({"id": tid} if tid else None)}>'
           f'<table class="wt {cls}{" sortable" if sortable else ""}"><thead><tr>']
    out += [f'<th{_attrs({"class": "n"} if i in num_cols else None)}>{esc(h)}</th>' for i, h in enumerate(headers)]
    out.append("</tr></thead><tbody>")
    for attrs, cells in rows:
        out.append(f"<tr{_attrs(attrs)}>")
        for i, c in enumerate(cells):
            if c is None:
                out.append('<td class="n0">–</td>')
            elif isinstance(c, tuple):
                out.append(f"<td{_attrs(c[1])}>{c[0]}</td>")
            elif isinstance(c, (int, float)) and not isinstance(c, bool):
                out.append(f'<td class="n" data-v="{c}">{fmt(c)}</td>')
            else:
                out.append(f'<td{_attrs({"class": "n"} if i in num_cols else None)}>{c}</td>')
        out.append("</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def filterbar(target, placeholder, groups=()):
    """groups: [(group id, group label, [(value, label)])] -> chip rows ('All' first)."""
    chips = ""
    for g, glabel, items in groups:
        chips += (f'<span class="fgroup"><span class="flab">{esc(glabel)}</span>'
                  f'<button class="chip on" data-g="{g}" data-f="*">All</button>' + "".join(
                      f'<button class="chip" data-g="{g}" data-f="{esc(v)}">{esc(lbl)}</button>' for v, lbl in items)
                  + "</span>")
    return (f'<div class="filterbar" data-for="{target}"><input placeholder="{esc(placeholder)}" '
            f'aria-label="Filter">{chips}<span class="count"></span></div>')


def faction_tag(f):
    return tag(f, "soviet" if f == "Soviet" else "base")


def plural(n, word, many=None):
    return f"{fmt(n)} {word if n == 1 else (many or word + 's')}"


# ---------------------------------------------------------------------------------------------------------------
# registry
# ---------------------------------------------------------------------------------------------------------------
def collect(site):
    m = model(site)
    site.register("machine-weapon", "Machine weapons", WEAPONS_PAGE, "Machine weapons",
                  desc="Every machine weapon and attack with its damage, blast radius, burn and the machines that "
                       "use it.", aliases=["machine weapon", "machine attacks"], search=False)
    site.register("machine-weapon", "Difficulty", DIFF_PAGE, "Difficulty & co-op",
                  desc="Damage multipliers for Easy, Medium and Hard with 1 to 4 players.",
                  aliases=["difficulty scaling", "co-op scaling"], search=False)
    site.register("machine-weapon", "Rivals", RIVALS_PAGE, "Rivals",
                  desc="Rival levels, region threat levels and the rival title system.",
                  aliases=["Rival", "rival levels", "rival titles", "threat"], search=False)
    # weapons on most layouts first, so a shared short name ('Autocannon') goes to the most common one
    for e in sorted(m["weapons"].values(), key=lambda e: -e["n_layouts"]):
        d = e["d"]
        aliases = [d["internal_name"], *sorted(e["ammo"]), *sorted(e["effects"]), *sorted(e["short"]),
                   d["colloquial_name"]]
        mpa = max_per_attack(e["dmg"])
        desc = f"{d['faction']} machine {d['kind']}" + (f" · up to {fmt(mpa)} damage to you per attack" if mpa
                                                         else "") + f" · used by {len(e['used_by'])} machine class(es)"
        site.register("machine-weapon", e["key"], f"{WEAPONS_PAGE}#{e['anchor']}", e["key"], aliases=aliases,
                      desc=desc, keywords=f"machine weapon {d['kind']} {d['internal_name']} "
                                          + " ".join(e["used_by"]))


def build(site):
    build_weapons(site)
    build_difficulty(site)
    build_rivals(site)


# ===============================================================================================================
# machines/weapons.html
# ===============================================================================================================
def build_weapons(site):
    m = model(site)
    ws = m["weapons"]
    by_kind = collections.defaultdict(list)
    for e in ws.values():
        by_kind[e["d"]["kind"]].append(e)
    about = site.data("stats")["_about"]["reading_the_numbers"]
    lead = (f"<p>Every weapon and attack the machines use, from the Runner's submachine gun to the Reaper's "
            f"thermobaric blast: <b>{len(ws)}</b> entries read from the game's tuning files. Each one shows the damage "
            f"it does to you and to machines, its blast radius and burn, and which machines carry it.</p>")
    b = [fold("Reading the numbers", reading_guide(site, about), id="reading")]
    for kind, (title, blurb) in KINDS.items():
        es = sorted(by_kind.get(kind, []), key=lambda e: (-(one_hit(e["dmg"]) or 0), e["key"]))
        if not es:
            continue
        b.append(fold(title, f"<p>{blurb} Sorted by the damage of one hit.</p>" + kind_facts(kind, es) +
                      '<div class="mwgrid">' + "".join(weapon_block(site, e) for e in es) + "</div>",
                      open=True, right=plural(len(es), "entry", "entries"), id=slug(kind)))
    leftovers = [e for e in ws.values() if e["d"]["kind"] not in KINDS]
    if leftovers:  # a kind we don't know yet: still show it
        b.append(fold("Other", '<div class="mwgrid">' + "".join(weapon_block(site, e) for e in leftovers) +
                      "</div>", open=True, right=plural(len(leftovers), "entry", "entries"), id="other"))
    # the overview table: last and collapsed (the weapon blocks above hold the same numbers in words)
    b.append(fold("All machine weapons", summary_table(site, ws), right=f"{len(ws)} entries", id="summary"))
    site.page(WEAPONS_PAGE, "Machine weapons", "\n".join(b), "machines", sub="mweapons",
              crumbs=[("Machine weapons", "~/" + WEAPONS_PAGE)], infobox_html=weapons_infobox(site, ws, by_kind),
              desc=f"All {len(ws)} Generation Zero machine weapons: damage, blast radius, burn and the machines that "
                   f"carry them.", kind="Machines · Weapons", lead=lead, head_extra=CSS,
              search={"k": "Machines", "w": "machine weapons damage blast radius"})


def weapons_infobox(site, ws, by_kind):
    """Counts per kind (links to the sections), the hardest hit, the widest reach and the difficulty range."""
    dt = diff_table(site)
    rows = [("Entries", f"<b>{len(ws)}</b>"), (None, "By kind")]
    for kind, (title, _) in KINDS.items():
        if by_kind.get(kind):
            rows.append((title, f'<a href="#{slug(kind)}">{len(by_kind[kind])}</a>'))
    hit = max(ws.values(), key=lambda e: one_hit(e["dmg"]) or 0)
    reach = max(ws.values(), key=lambda e: radius_players(e["dmg"]) or 0)
    rows += [(None, "Records"),
             ("Hardest hit", f'<a href="#{hit["anchor"]}">{esc(hit["key"])}</a><br>'
                             f'<span class="dim">{fmt(one_hit(hit["dmg"]))} damage</span>'),
             ("Widest reach", f'<a href="#{reach["anchor"]}">{esc(reach["key"])}</a><br>'
                              f'<span class="dim">{fmt(radius_players(reach["dmg"]))} m</span>'),
             (None, "Difficulty"),
             ("Numbers shown", "base (Medium solo, ×1)"),
             ("Damage to you", f"×{fmt(dt[('Easy', 1)][1])} (Easy solo) to ×{fmt(dt[('Hard', 4)][1])} "
                               f"(Hard, 4 players)"),
             ("Rivals", f"×{fmt(site.data('gamedata')['rival_levels'][0]['damage'])} to "
                        f"×{fmt(site.data('gamedata')['rival_levels'][-1]['damage'])} on top"),
             ("More", site.link("machine-weapon", "Difficulty", "Difficulty & co-op") + " · " +
              site.link("machine-weapon", "Rivals", "Rivals"))]
    return infobox("Machine weapons", rows)


def reading_guide(site, about):
    rows = [
        ("Direct hit", "Damage of one bullet, pellet or shell that hits you. "
                       "A shotgun-style weapon fires several per shot; the table multiplies them out."),
        ("Blast", "Area damage where a projectile or attack explodes, separately against you and against "
                  "machines, each with its own radius in metres. Explosive shells do both: the direct hit "
                  "<i>and</i> the blast."),
        ("Bomblets", "Cluster weapons fire one carrier that splits into several bomblets; each bomblet has its own "
                     "blast."),
        ("Damage over time", "Burn, gas or radiation: a fixed amount every tick (e.g. every 1 s) for a set "
                             "duration, refreshed while you stay in it. We add the ticks up to one exposure."),
        ("Contact", "Damage from a part that hurts you while you touch it (the Lynx saw): a damage range per hit "
                    "within a small radius, repeating at a fixed interval while you stay in reach."),
        ("One hit", "What a single projectile or bomblet does to you if it hits: its direct damage, its blast and "
                    "its burn added up. This is the column to sort by to find the hardest single hits."),
        ("Max per attack", "Our upper bound for one attack against you: every projectile, blast, bomblet and burn "
                           "tick lands. Real hits are usually lower (you are at the edge of a blast, a pellet "
                           "misses), so use it to compare weapons, not as a promise."),
        ("Difficulty", f"All damage to you is multiplied by the difficulty and co-op multiplier "
                       f"(×{fmt(diff_table(site)[('Easy', 1)][1])} to ×{fmt(diff_table(site)[('Hard', 4)][1])}), "
                       f"see {site.link('machine-weapon', 'Difficulty', 'Difficulty & co-op')}. The numbers here "
                       f"are the base values (×1, Medium solo). Each weapon's <b>On difficulty</b> line shows its max per "
                       f"attack on five settings, from the lowest multiplier to the highest: Easy, Medium and Hard "
                       f"(E, M, H) solo, Hard with 2 and Hard with 4 players (<b>H4</b> = Hard, 4 players; "
                       f"Medium with 4 players has the same ×{fmt(diff_table(site)[('Medium', 4)][1])} as H1). "
                       f"Scaled values keep one decimal."),
    ]
    return ("<p>All numbers are taken unchanged from the game files. Damage is in hit points, radius in metres and "
            "time in seconds.</p>" + kv([(k, v) for k, v in rows]))


def summary_table(site, ws):
    """The sortable, filterable overview with a difficulty switch that rescales the damage-to-you columns."""
    dt = diff_table(site)
    opts = ['<option value="1">Base values (×1 = Medium, 1 player)</option>'] + [
        f'<option value="{dt[(d, p)][1]}">{d}, {plural(p, "player")} (×{fmt(dt[(d, p)][1])})</option>'
        for d in DIFFS for p in range(1, 5)]
    switch = (f'<div class="mwscale"><label for="mwDiff">Show damage to you on</label> '
              f'<select id="mwDiff">{"".join(opts)}</select>'
              f'<span class="dim small">Rescales the columns marked *. Blast against machines is not scaled.</span>'
              f'</div>')
    rows = []
    for e in sorted(ws.values(), key=lambda e: e["key"]):
        d, dmg = e["d"], e["dmg"]
        dot = sum(dot_total(x) for x in to_player_dots(dmg)) or None
        # the explosion of a destroyed drop still goes in the blast columns, marked as such
        bdmg = {"blast": e["destroyed_blast"]} if e["destroyed_blast"] else dmg
        bm, rm = blast_machines(bdmg)
        bcell = blast_cell(bdmg)
        if e["destroyed_blast"] and bcell:
            bcell = (bcell[0] + ' <small class="dim">when destroyed</small>', bcell[1])
        rows.append(({"data-f": f"{slug(d['kind'])} {slug(d['faction'])}"}, [
            site.link("machine-weapon", e["key"]),
            (esc(d["kind"].capitalize()), {"class": "nw"}),
            times_cell(dmg.get("damage_per_projectile"), dmg.get("projectiles_per_shot") or 1),
            bcell,
            num(dot, base=dot),
            num(one_hit(dmg), base=one_hit(dmg)),
            num(max_per_attack(dmg), base=max_per_attack(dmg)),
            (f'{fmt(bm)} <small class="dim">{fmt(rm)} m</small>', {"class": "n", "data-v": bm}) if bm else None,
            num(len(e["used_by"])),
        ]))
    kinds = [(slug(k), v[0].replace(" weapons", "").replace(" attacks", "")) for k, v in KINDS.items()]
    fb = filterbar("mwsum", "Filter weapons or machines...",
                   [("k", "Kind", kinds), ("f", "Faction", [("swedish", "Swedish"), ("soviet", "Soviet")])])
    head = ["Weapon", "Kind", "Direct hit *", "Blast to you *", "DoT to you *", "One hit *",
            "Max per attack *", "Blast to machines", "Classes"]
    return ("<p>One row per weapon. Click a column header to sort (for example by <b>Max per attack</b> to find the "
            "hardest hitters), use the chips to show one kind or faction, and switch the difficulty to see the "
            "damage you would actually take. <b>Direct hit</b> and <b>Blast</b> show damage per projectile (or "
            "bomblet) × how many per shot, with the blast radius in small print; <b>DoT</b> is the total of one burn "
            "/ gas / radiation exposure; <b>One hit</b> and <b>Max per attack</b> are explained under "
            "<a href=\"#reading\">Reading the numbers</a>; "
            "<b>Classes</b> is how many machine classes carry it.</p>" + switch + fb +
            rtable(head, rows, num_cols=range(2, 9), cls="mwsum compact", tid="mwsum"))


def kind_facts(kind, es):
    """One or two computed sentences per kind: the hardest hitter and the widest blast."""
    out = []
    hitters = [(one_hit(e["dmg"]), e) for e in es if one_hit(e["dmg"])]
    if len(hitters) > 1:
        v, e = max(hitters, key=lambda x: x[0])
        out.append(f"Hardest single hit: <b>{esc(e['key'])}</b>, {fmt(v)} damage to you.")
    radii = [(radius_players(e["dmg"]), e) for e in es if radius_players(e["dmg"])]
    if len(radii) > 1:
        v, e = max(radii, key=lambda x: x[0])
        out.append(f"Widest reach: <b>{esc(e['key'])}</b>, {fmt(v)} m.")
    return f'<p class="dim small">{" ".join(out)}</p>' if out else ""


# ---------------------------------------------------------------------------------------------------------------
# one weapon
# ---------------------------------------------------------------------------------------------------------------
def weapon_block(site, e):
    d, dmg = e["d"], e["dmg"]
    tags = tag(d["kind"], KIND_TAG.get(d["kind"], "")) + faction_tag(d["faction"])
    if e["used_by"] and all(u in ("Reaper", "Vulture") for u in e["used_by"]):
        tags += tag("Rival only", "unreleased")
    rows = damage_rows(dmg, d["kind"])
    if e["destroyed_blast"]:
        rows.append(("When destroyed", "explodes: " + blast_html(e["destroyed_blast"]) +
                     ' <span class="dim">(not part of its attack, so not counted below)</span>'))
    mpa = max_per_attack(dmg)
    if mpa:
        rows.append(("On difficulty", difficulty_line(site, mpa)))
    rows.append(("Used by", used_by_html(site, e)))
    if e["comps"]:
        rows.append(("Component HP", comp_html(site, e)))
    if e["labels"]:
        rows.append(("In-game label", ", ".join(esc(x) for x in sorted(e["labels"]))))
    shorts = sorted(s for s in e["short"] if s != e["key"])
    if shorts:
        rows.append(("Loadout name", ", ".join(esc(s) for s in shorts)))
    notes = "".join(f"<p>{esc(n)}</p>" for n in e["notes"])
    tip = TIPS.get(e["key"])
    tip_html = f'<p class="mwtip"><b>Tip.</b> {tip(dmg, e)}</p>' if tip else ""
    return (f'<section class="mw" id="{e["anchor"]}"><div class="mwh"><h3>{esc(e["key"])}</h3>'
            f'<span>{tags}</span></div><div class="mwb">{kv(rows)}'
            f'{f"<div class=mwnote>{notes}</div>" if notes else ""}{tip_html}</div></section>')


def damage_rows(dmg, kind=""):
    """(label, html) rows describing a damage block in words, with units."""
    rows = []
    if not dmg:
        why = ("it doesn't attack you itself." if kind in ("support", "support drop", "defensive")
               else "its effect isn't part of the extracted tuning data.")
        return [("Damage", f'<span class="dim">No damage values in the files: {why}</span>')]
    dpp, pps = dmg.get("damage_per_projectile"), dmg.get("projectiles_per_shot") or 1
    if dpp:
        rows.append(("Direct hit", f"<b>{fmt(dpp)}</b> per projectile" +
                     (f" × {pps} per shot = <b>{fmt(dpp * pps)}</b> per shot" if pps > 1 else "")))
    elif pps > 1:
        rows.append(("Projectiles", f"{pps} per shot (no direct-hit damage; each one carries the blast below)"))
    if dmg.get("blast"):
        rows.append(("Blast", blast_html(dmg["blast"])))
    if dmg.get("submunition"):
        n = dmg.get("submunitions")
        sub = dmg["submunition"]
        rows.append(("Bomblets", (f"<b>{n}</b> per shot, each: " if n else "each: ") +
                     (blast_html(sub["blast"]) if sub.get("blast") else "–")))
    for dot in dmg.get("damage_over_time") or []:
        who = "you" if dot.get("target") == "characters" else "machines and objects"
        rows.append((f"Over time ({'you' if who == 'you' else 'machines'})",
                     f"<b>{fmt(dot['damage_per_tick'])}</b> every {fmt(dot['tick_seconds'])} s for "
                     f"{fmt(dot['duration_seconds'])} s to {who} ≈ <b>{fmt(dot_total(dot))}</b> per exposure "
                     f"({plural(dot_ticks(dot), 'tick')})"))
    if dmg.get("contact"):
        c = dmg["contact"]
        rows.append(("Contact", f"<b>{fmt(c['damage_to_players_min'])}–{fmt(c['damage_to_players_max'])}</b> to you "
                                f"per hit within {fmt(c['radius_vs_players_m'])} m, repeating every "
                                f"{fmt(c['repeat_interval_seconds'])} s while you stay in reach; "
                                f"{fmt(c.get('damage_to_machines'))} to machines"))
    if dmg.get("heal_pulse"):
        h = dmg["heal_pulse"]
        rows.append(("Pulse", f"value <b>{fmt(h['damage_to_machines'])}</b> within "
                              f"{fmt(h['radius_vs_machines_m'])} m: it heals the machines around it and does not "
                              f"hurt you"))
    mpa = max_per_attack(dmg)
    if mpa and len([r for r in rows if r[0] != "Pulse"]) > 1:
        rows.append(("Max per attack", f"<b>{fmt(mpa)}</b> to you if everything lands"))
    return rows


def blast_html(b):
    rp, rm = b.get("radius_vs_players_m"), b.get("radius_vs_machines_m")
    you = f"<b>{fmt(b.get('damage_to_players'))}</b> to you within {fmt(rp)} m"
    mach = f"{fmt(b.get('damage_to_machines'))} to machines within {fmt(rm)} m"
    return f"{you}; {mach}"


def difficulty_line(site, base):
    """Max per attack on a few representative difficulty settings."""
    dt = diff_table(site)
    picks = [("Easy", 1), ("Medium", 1), ("Hard", 1), ("Hard", 2), ("Hard", 4)]
    # one decimal: avoids round()'s half-to-even surprises (18.5 -> 18 but 3.5 -> 4)
    parts = [f'<span title="{d}, {plural(p, "player")}">{d[0]}{p} <b>{fmt(base * dt[(d, p)][1], 1)}</b></span>'
             for d, p in picks if (d, p) in dt]
    return '<span class="dline">' + " · ".join(parts) + "</span>"


def used_by_html(site, e):
    out = []
    for mname in e["used_by"]:
        lays = e["layouts"].get(mname, [])
        total = model(site)["layout_count"].get(mname, 0)
        if not lays or not total:
            extra = ""
        elif len(lays) >= total:
            extra = "all layouts" if total > 1 else ""
            copies = {e["slots"][(mname, x)] for x in lays}
            if len(copies) == 1 and min(copies) > 1:
                extra = (extra + ", " if extra else "") + f"{min(copies)} on each"
        else:
            extra = "layout " + ", ".join(esc(short_layout(x)) for x in lays) + f" of {total}"
            doubled = [x for x in lays if e["slots"][(mname, x)] > 1]
            if doubled:
                extra += "; " + ", ".join(f"{e['slots'][(mname, x)]} on layout {esc(short_layout(x))}"
                                          for x in doubled)
        out.append(f"<li>{site.link('machine', mname)}{f' <span class=dim>({extra})</span>' if extra else ''}</li>")
    return f'<ul class="mwuse">{"".join(out)}</ul>' if out else "–"


def short_layout(label):
    """'Layout 1 (green variant)' -> '1 green'."""
    return label.replace("Layout ", "").replace(" (green variant)", " green")


def comp_html(site, e):
    """Health of the weapon's component on each machine (shoot it to disable the weapon)."""
    out = []
    for mname, by_layout in e["comps"].items():
        cs = list(by_layout.values())
        hp = sorted({c["health_each"] for c in cs})
        cnt = sorted({c["count"] for c in cs})
        armour = any(c.get("type") == "armour" for c in cs)
        v = fmt(hp[0]) if len(hp) == 1 else f"{fmt(hp[0])}–{fmt(hp[-1])}"
        # component count: one number, or the range when the layouts differ
        n = (f" × {cnt[0]}" if cnt[0] > 1 else "") if len(cnt) == 1 else f" × {cnt[0]}–{cnt[-1]}"
        out.append(f"<li>{site.link('machine', mname)}: <b>{v}</b>{n}{' (armour)' if armour else ''}</li>")
    return f'<ul class="mwuse">{"".join(out)}</ul>'


# Practical tips, written as functions of the weapon's numbers so they follow the data.
def _b(d, k="damage_to_players"):
    return fmt((d.get("blast") or {}).get(k))


def _r(d, k="radius_vs_players_m"):
    return fmt((d.get("blast") or {}).get(k))


TIPS = {
    "Thermobaric Explosion": lambda d, e: (
        f"{_b(d)} damage to you within {_r(d)} m is far beyond anything you can survive, and the same blast does "
        f"{_b(d, 'damage_to_machines')} to machines. Distance is the only defence."),
    "Concussion Actuator (Tank)": lambda d, e: (
        f"The pulse reaches {_r(d)} m, so staying close to a Tank never keeps you safe from it; fight it from "
        f"beyond {_r(d)} m if you can."),
    "Concussion Actuator (Harvester)": lambda d, e: (
        f"Its {_r(d)} m reach covers most fighting distances; the Harvester's version does {_b(d)} to you, a bit "
        f"less than the Tank's."),
    "Shock Actuator": lambda d, e: (
        f"{_b(d)} to you anywhere within {_r(d)} m of a Spetsnaz Wolf: keep your distance from that class."),
    "Melee Stomp (Reaper)": lambda d, e: f"The Reaper's stomp reaches {_r(d)} m. Don't fight it up close.",
    "Mortar": lambda d, e: (
        f"Its {_r(d)} m blast radius is the widest of any gun or launcher a machine fires at you, so sidestepping a few "
        f"metres is not enough: keep moving or get under cover."),
    "Gas Canister Drop": lambda d, e: (
        f"When the canister goes off it does {_b(d)} to you but {_b(d, 'damage_to_machines')} to machines within "
        f"{_r(d, 'radius_vs_machines_m')} m, so shoot it when machines are standing next to it, not you."),
    "Turret Drop": lambda d, e: (
        f"The turret's bullets do only {fmt(d.get('damage_per_projectile'))} each; its own explosion when destroyed "
        f"does {fmt(e['destroyed_blast']['damage_to_machines'])} to machines within "
        f"{fmt(e['destroyed_blast']['radius_vs_machines_m'])} m."),
    "Recovery Field Emitter": lambda d, e: (
        f"It reaches {fmt(d['heal_pulse']['radius_vs_machines_m'])} m and keeps the machines around it fighting. "
        f"Take out the Wolves that carry it first, or shoot the emitter itself."),
    "Self-Destruct Explosion": lambda d, e: (
        f"{_b(d)} to you but {_b(d, 'damage_to_machines')} to machines within {_r(d)} m: exploding Ticks are far "
        f"more dangerous to machines than to you."),
    "Incendiary Bombs": lambda d, e: (
        f"Firebird bomb blasts are tuned to hurt machines much more ({_b(d, 'damage_to_machines')}) than you "
        f"({_b(d)})."),
    "Thermobaric Bombs": lambda d, e: (
        f"Its {_r(d)} m radius against you is the widest of the Firebird's bombs: get well away from the drop "
        f"point."),
    "Linear Accelerator Cannon": lambda d, e: (
        f"{fmt(d.get('damage_per_projectile'))} per hit with no blast: one of the hardest single hits from a "
        f"regular machine. Break line of sight when a Tank lines up a shot."),
    "Concussion Rifle": lambda d, e: (
        f"Each shot does {fmt(d.get('damage_per_projectile'))} on a direct hit and a {_b(d)} blast within "
        f"{_r(d)} m, so cover that only blocks the direct hit doesn't save you from the blast."),
    "Auto Shotgun": lambda d, e: (
        f"{d['projectiles_per_shot']} pellets of {fmt(d['damage_per_projectile'])}: at close range, where every "
        f"pellet hits, it does {fmt(direct_per_shot(d))} per shot. Keep Runners carrying it at a distance."),
    "Sawblade": lambda d, e: (
        f"Only {fmt(d['contact']['damage_to_players_max'])} at most per hit, and it repeats only every "
        f"{fmt(d['contact']['repeat_interval_seconds'])} s while you stay within "
        f"{fmt(d['contact']['radius_vs_players_m'])} m."),
    "Tick Storage": lambda d, e: (
        "Ticks come out of this component. Destroying it early stops a machine from releasing more Ticks."),
    "Anti-Weapons Shield Emitter": lambda d, e: "".join(
        f"The {esc(m)} carries {c[0]['count']} of these emitters with {fmt(c[0]['health_each'])} health each "
        f"({fmt(c[0]['count'] * c[0]['health_each'])} in total). "
        for m, c in ((m, list(v.values())) for m, v in e["comps"].items())) +
        "",
}


# ===============================================================================================================
# machines/difficulty.html
# ===============================================================================================================
def build_difficulty(site):
    dt = diff_table(site)
    lead = ("<p>Generation Zero scales damage in two directions: how much damage <b>you</b> do to machines, and how "
            "much damage <b>machines</b> do to you. Both depend on the difficulty and on the number of players in "
            "the session. This page lists the multipliers from the game's difficulty settings and what they mean "
            "in practice.</p>")
    b = []
    b.append(bar("The multipliers", id="multipliers"))
    b.append("<p>Read each cell as <i>multiply the base damage by this</i>. ×1 means the damage you see in the "
             "weapon tables of this wiki. Your damage covers every weapon you use against machines; machine damage "
             "covers every machine weapon on the "
             f"{site.link('machine-weapon', 'Machine weapons', 'machine weapons')} page.</p>")
    b.append('<div class="cols"><div>' + mult_table(dt, 0, "Your damage to machines") + "</div><div>" +
             mult_table(dt, 1, "Machine damage to you") + "</div></div>")
    b.append(note("The multipliers are stored with two decimals in the data, so 0.67 and 1.33 are most likely "
                  "⅔ and 1⅓, and 0.63 / 0.38 most likely 0.625 / 0.375.", "data"))
    b.append(bar("What stands out", id="surprises"))
    b.append(surprises(dt))
    b.append(bar("Team damage", id="team"))
    b.append(team_table(dt))
    b.append(bar("Worked examples", id="examples"))
    b.append(examples(site, dt))
    site.page(DIFF_PAGE, "Difficulty & co-op", "\n".join(b), "machines", sub="difficulty",
              infobox_html=difficulty_infobox(site, dt),
              desc="Generation Zero difficulty and co-op damage multipliers: Easy, Medium, Hard with 1-4 players, "
                   "with worked examples.", kind="Machines · Difficulty", lead=lead,
              head_extra=CSS, search={"k": "Machines", "w": "difficulty co-op multiplayer scaling damage easy hard"})


def difficulty_infobox(site, dt):
    yours = [v[0] for v in dt.values()]
    theirs = [v[1] for v in dt.values()]
    rv = site.data("gamedata")["rival_levels"]
    rows = [("Difficulties", ", ".join(DIFFS)),
            ("Players", f"1 to {max(p for _, p in dt)}"),
            ("Baseline (×1)", "Medium, 1 player"),
            (None, "Range"),
            ("Your damage", f"×{fmt(min(yours))} to ×{fmt(max(yours))}"),
            ("Machine damage", f"×{fmt(min(theirs))} to ×{fmt(max(theirs))}"),
            (None, "On top"),
            ("Rival damage", f"×{fmt(rv[0]['damage'])} to ×{fmt(rv[-1]['damage'])}"),
            ("Rival health", f"×{fmt(rv[0]['health'])} to ×{fmt(rv[-1]['health'])}"),
            ("More", site.link("machine-weapon", "Rivals", "Rivals") + " · " +
             site.link("machine-weapon", "Machine weapons", "Machine weapons"))]
    return infobox("Difficulty", rows, subtitle="Damage multipliers by difficulty and number of players")


def mult_table(dt, i, title):
    rows = []
    for d in DIFFS:
        cells = [f"<b>{d}</b>"]
        for p in range(1, 5):
            v = dt.get((d, p), (None, None))[i]
            cells.append((f'<span class="{mult_cls(v, i)}">×{fmt(v)}</span>', {"class": "n", "data-v": v}))
        rows.append((None, cells))
    return (f"<h3>{esc(title)}</h3>" +
            rtable(["Difficulty", "1 player", "2 players", "3 players", "4 players"], rows, num_cols=range(1, 5),
                   cls="mult", sortable=False))


def mult_cls(v, i):
    """Colour a multiplier: good for you = green, bad = red, ×1 = plain."""
    if v is None or v == 1:
        return ""
    good = v > 1 if i == 0 else v < 1
    return "good" if good else "bad"


def surprises(dt):
    e1, e4 = dt[("Easy", 1)], dt[("Easy", 4)]
    m1, m2, m4 = dt[("Medium", 1)], dt[("Medium", 2)], dt[("Medium", 4)]
    h1, h4 = dt[("Hard", 1)], dt[("Hard", 4)]
    items = [
        f"<b>More players means harder machines on every difficulty.</b> Each extra player lowers everyone's "
        f"damage and raises the damage machines do. The difficulty settings hold only these two damage "
        f"multipliers, so this is how the game balances co-op.",
        f"<b>Medium co-op lowers your damage.</b> Medium is the ×1 baseline only when you play alone. With one "
        f"friend you already do ×{fmt(m2[0])} and take ×{fmt(m2[1])}; with four players you do ×{fmt(m4[0])} "
        f"(half) and take ×{fmt(m4[1])} (double).",
        f"<b>Easy with 4 players is exactly Medium solo</b> (×{fmt(e4[0])} / ×{fmt(e4[1])}). Easy is the only "
        f"difficulty where you ever do more than base damage: ×{fmt(e1[0])} solo, falling to ×{fmt(e4[0])} with "
        f"four players.",
        f"<b>Hard solo already doubles machine damage</b> (×{fmt(h1[1])}) and cuts yours to ×{fmt(h1[0])}. "
        f"Hard with 4 players is the extreme: you do ×{fmt(h4[0])} and take ×{fmt(h4[1])}. Compared with Easy "
        f"solo, a hit on you is {fmt(h4[1] / e1[1], 1)} times as strong and your shots are "
        f"{fmt(e1[0] / h4[0], 1)} times weaker.",
        f"<b>Swapping one difficulty step is worth about one or two players.</b> Medium with 3 players "
        f"(×{fmt(dt[('Medium', 3)][0])} / ×{fmt(dt[('Medium', 3)][1])}) is close to Hard solo "
        f"(×{fmt(h1[0])} / ×{fmt(h1[1])}).",
    ]
    return '<ul class="tips">' + "".join(f"<li>{x}</li>" for x in items) + "</ul>"


def team_table(dt):
    """players × your multiplier = the group's total damage output compared with one Medium solo player."""
    rows = []
    for d in DIFFS:
        cells = [f"<b>{d}</b>"]
        for p in range(1, 5):
            v = round(p * dt[(d, p)][0], 1)
            cells.append((f"×{fmt(v)}", {"class": "n", "data-v": v}))
        rows.append((None, cells))
    m3, m4 = round(3 * dt[("Medium", 3)][0], 1), round(4 * dt[("Medium", 4)][0], 1)
    h3, h4 = round(3 * dt[("Hard", 3)][0], 1), round(4 * dt[("Hard", 4)][0], 1)
    return ("<p>If every player fires at the same machine all the time, the group's combined damage is the "
            "number of players times the multiplier. This table shows that total compared with one player on "
            "Medium solo (×1), rounded to one decimal because the multipliers themselves are rounded.</p>" +
            rtable(["Difficulty", "1 player", "2 players", "3 players", "4 players"], rows, num_cols=range(1, 5),
                   cls="mult", sortable=False) +
            f"<p>The fourth player adds almost nothing to the group's firepower: on Medium three players together "
            f"do {_vs(m3, m4)}; on Hard {_vs(h3, h4)}. What a bigger group gains is more targets for the "
            f"machines, more angles and more people to revive you, while each of you takes more damage.</p>")


def _vs(three, four):
    """'×2, and four players also ×2' / '×1.5 against ×1.6 with four'."""
    return (f"×{fmt(three)} and four players also ×{fmt(four)}" if three == four
            else f"×{fmt(three)} and four players ×{fmt(four)}")


def _magnum(site):
    """The .44 Magnus FMJ round from stats.json for the worked example (None if the data changed)."""
    w = site.data("stats")["player_weapons"].get("Handguns", {}).get(".44 Magnus")
    if not w:
        return None
    ammo = next((a for a in w["ammo"] if "Full Metal" in a["name"]), None)
    return (w, ammo) if ammo else None


def examples(site, dt):
    mws = site.data("stats")["machine_weapons"]
    ex = []
    mg = _magnum(site)
    if mg:
        w, a = mg
        q = w["damage_multiplier_by_quality"]
        dmg = a["projectile_damage"]
        h1 = dt[("Hard", 1)][0]
        ex.append(
            f"<h4>Your {site.link('weapon', '.44 Magnus')} on Hard, solo</h4>"
            f"<p>The {site.link('ammo', a['name'])} does {fmt(dmg)} per bullet at full quality "
            f"(×{fmt(q['Q5'])} for {esc('Q5')}). On Hard solo your damage is ×{fmt(h1)}: "
            f"{fmt(dmg)} × {fmt(h1)} = <b>{fmt(dmg * h1)}</b> per hit. With a Worn (Q2) copy, which has a "
            f"quality multiplier of ×{fmt(q['Q2'])}, it is {fmt(dmg)} × {fmt(q['Q2'])} × {fmt(h1)} = "
            f"<b>{fmt(dmg * q['Q2'] * h1)}</b>. Armour and component multipliers of the ammo apply on top.</p>")
    sg = mws.get("Auto Shotgun")
    if sg:
        d = sg["damage"]
        m4 = dt[("Medium", 4)][1]
        per = d["damage_per_projectile"] * d["projectiles_per_shot"]
        ex.append(
            f"<h4>A Runner's {site.link('machine-weapon', 'Auto Shotgun')} against you, Medium with 4 players</h4>"
            f"<p>It fires {d['projectiles_per_shot']} pellets of {fmt(d['damage_per_projectile'])}: "
            f"{fmt(per)} per shot if every pellet hits. Medium with 4 players doubles machine damage "
            f"(×{fmt(m4)}): {fmt(per)} × {fmt(m4)} = <b>{fmt(per * m4)}</b> per shot, or "
            f"{fmt(d['damage_per_projectile'] * m4)} per pellet. Alone on Medium the same shot does {fmt(per)}.</p>")
    lac = mws.get("Linear Accelerator Cannon")
    if lac:
        d = lac["damage"]["damage_per_projectile"]
        ex.append(
            f"<h4>A Tank's {site.link('machine-weapon', 'Linear Accelerator Cannon')} across the difficulties</h4>"
            f"<p>{fmt(d)} per hit at base. Easy solo: {fmt(d * dt[('Easy', 1)][1])}. Hard solo: "
            f"{fmt(d * dt[('Hard', 1)][1])}. Hard with 4 players: <b>{fmt(d * dt[('Hard', 4)][1])}</b>.</p>")
    rv = site.data("gamedata")["rival_levels"]
    img = mws.get("Incendiary Machine Gun (Reaper)")
    if rv and img:
        top = rv[-1]
        d = img["damage"]["damage_per_projectile"]
        h1 = dt[("Hard", 1)][1]
        ex.append(
            f"<h4>A level {top['level']} rival on Hard, solo</h4>"
            f"<p>Rival damage multipliers stack with difficulty. A level {top['level']} rival does "
            f"×{fmt(top['damage'])} damage; on Hard solo that is ×{fmt(top['damage'])} × {fmt(h1)} = "
            f"×{fmt(top['damage'] * h1)}. A {fmt(d)}-damage bullet becomes <b>{fmt(d * top['damage'] * h1)}</b>. "
            f"The rival also has ×{fmt(top['health'])} health while you do ×{fmt(dt[('Hard', 1)][0])} damage, so "
            f"it takes {fmt(top['health'] / dt[('Hard', 1)][0], 1)} times as many hits as the same machine on "
            f"Medium solo. See {site.link('machine-weapon', 'Rivals', 'Rivals')}.</p>")
    return "".join(ex) + note("We assume the multipliers multiply each other, as their names in the game "
                              "files suggest. The game files don't say in which order the game rounds them.", "info")


# ===============================================================================================================
# machines/rivals.html
# ===============================================================================================================
RIVALS_DLC = 1173930      # steam.json appid of the free 'Rivals & Experimental Weapons' update


def build_rivals(site):
    gd = site.data("gamedata")
    dlc = next((d for d in site.data("steam")["dlc"] if d["appid"] == RIVALS_DLC), None)
    when = f" ({esc(dlc['date'].split(' ')[0])} {esc(dlc['date'].split(' ')[-1])})" if dlc else ""
    update = site.link("dlc", dlc["name"], f"{dlc['name']} update") if dlc else "Rivals update"
    lead = (f"<p>Rivals are machines that have grown stronger and earned a name and a title, such as <i>The "
            f"Tyrant of the Mountain</i>. They came with the free {update}{when}. When you destroy many machines in "
            f"a region, the machines there adapt and one of them evolves into a <b>regional rival</b>; a machine "
            f"that defeats you or a friend can become a <b>personal rival</b>. Each rival level multiplies its "
            f"health, damage and reward, and rivals are where "
            f"{site.link('experimental', 'Experimental weapons', 'experimental weapons')} come from.</p>")
    b = [bar("Rival levels", id="levels"), rival_levels(site, gd["rival_levels"])]
    b += [bar("Threat levels", f"{len(gd['threat']) - 1} levels", id="threat"), threat_levels(site, gd["threat"])]
    b += [bar("The Reaper and the Vulture", id="special"), special_rivals(site)]
    rows = [(h, t, classify_title(t)) for h, t in gd["titles"].items()]
    n_titles = sum(1 for r in rows if r[2]["group"] != "history")
    b += [bar("Rival titles", f"{fmt(n_titles)} titles", id="titles"), titles_intro(site, gd, rows)]
    b += [bar("Title parts", id="parts"), title_builder(site, rows)]
    b += [bar("All titles", f"{fmt(n_titles)} titles", id="all-titles"), title_tree(rows)]
    site.page(RIVALS_PAGE, "Rivals", "\n".join(b), "machines", sub="rivals",
              infobox_html=rivals_infobox(site, gd, n_titles, dlc),
              desc="Generation Zero rivals: levels, health and damage multipliers, region threat levels and every "
                   "rival title.", kind="Machines · Rivals", lead=lead, head_extra=CSS,
              search={"k": "Machines", "w": "rival rivals threat titles xp level reaper vulture"})


def rivals_infobox(site, gd, n_titles, dlc):
    lv, th = gd["rival_levels"], gd["threat"]
    rng = lambda k: f"×{fmt(lv[0][k], 3)} to ×{fmt(lv[-1][k], 3)}"
    img = f"~/{dlc['image']}" if dlc and site.has_file(dlc["image"]) else None
    rows = [("Added in", site.link("dlc", dlc["name"]) + f"<br><span class=\"dim\">{esc(dlc['date'])}, free</span>"
             if dlc else None),
            (None, "Rival levels"),
            ("Levels", f"{lv[0]['level']} to {lv[-1]['level']}"),
            ("Health", rng("health")), ("Damage", rng("damage")), ("Reward", rng("reward")),
            (None, "Regions"),
            ("Threat levels", f'<a href="#threat">1 to {len(th) - 1}</a>'),
            ("New-rival chance", f"{pct(th[1]['chance'])} to {pct(th[-1]['chance'], 1)}"),
            (None, "Unique rivals"),
            ("Swedish", site.link("machine", "Reaper") + ' <span class="dim">(Tank)</span>'),
            ("Soviet", site.link("machine", "Vulture") + ' <span class="dim">(Firebird)</span>'),
            (None, "Titles"),
            ("Titles", f'<a href="#all-titles">{fmt(n_titles)}</a>')]
    return infobox("Rivals", rows, image=img, image_alt="Rivals & Experimental Weapons")


def rival_levels(site, lv):
    dt = diff_table(site)
    rows = []
    prev = None
    for r in lv:
        rows.append((None, [f"<b>{r['level']}</b>", num(r["xp"]),
                            num(r["xp"] - prev["xp"]) if prev else None,
                            (f"×{fmt(r['health'], 3)}", {"class": "n", "data-v": r["health"]}),
                            (f"×{fmt(r['damage'], 3)}", {"class": "n", "data-v": r["damage"]}),
                            (f"×{fmt(r['reward'], 3)}", {"class": "n", "data-v": r["reward"]})]))
        prev = r
    top, first = lv[-1], lv[0]
    h4 = dt[("Hard", 4)]
    ex_machine = example_machine(site)
    ex = ""
    if ex_machine:
        name, label, hp = ex_machine
        ex = (f" Take {site.link('machine', name)}, {esc(label.lower())}: its components add up to {fmt(hp, 0)} "
              f"hit points; as a level {top['level']} rival that becomes about {fmt(hp * top['health'], 0)}.")
    return (
        "<p>A rival's level follows from its experience points (XP). <b>XP to reach</b> is the total XP at which "
        "the level starts; the multipliers apply to the machine's normal values, and <b>Reward</b> multiplies "
        "what you get for destroying it.</p>" +
        rtable(["Level", "XP to reach", "XP from previous level", "Health", "Damage", "Reward"], rows,
               num_cols=range(1, 6), cls="mult", sortable=False) +
        f'<ul class="tips"><li>Even a brand-new level {first["level"]} rival is tougher than the normal machine: '
        f"×{fmt(first['health'])} health and ×{fmt(first['damage'])} damage.{ex}</li>"
        f"<li>The total XP needed doubles with each level from level 2 on "
        f"({', '.join(fmt(r['xp']) for r in lv[1:])}).</li>"
        f"<li>Rival multipliers come on top of difficulty: a level {top['level']} rival on Hard with 4 players "
        f"hits ×{fmt(top['damage'])} × {fmt(h4[1])} = ×{fmt(top['damage'] * h4[1])} as hard as base (see "
        f"{site.link('machine-weapon', 'Difficulty', 'Difficulty & co-op')}).</li></ul>")


def example_machine(site):
    """A mid-sized example for the rival health sentence: the Hunter (FNIX) layout with the most health."""
    try:
        tv = site.data("stats")["machine_health"]["Swedish"]["FNIX"]["types"]["Hunter"]["layouts"]
        label, l = max(tv.items(), key=lambda x: x[1]["total_component_health"])
        return "Hunter (FNIX)", label, l["total_component_health"]
    except KeyError:
        return None


# ---------------------------------------------------------------------------------------------------------------
# threat levels: a bar chart (one row per level: bar = score needed, right = new-rival chance)
# ---------------------------------------------------------------------------------------------------------------
def threat_levels(site, th):
    """gamedata threat: index = threat level. Index 0 is a placeholder (the Gen0 Editor shows levels 1..n)."""
    levels = [(i, th[i]["score"], th[i]["chance"]) for i in range(1, len(th))]
    steps = {round(levels[k + 1][2] - levels[k][2], 6) for k in range(1, len(levels) - 1)}
    last = levels[-1]
    step_txt = (f"level {levels[1][0]} starts at {pct(levels[1][2])} and every level after it adds "
                f"{fmt(steps.pop() * 100, 1)} percentage points" if len(steps) == 1 else
                f"the chance rises from {pct(levels[1][2])} at level {levels[1][0]}")
    return (
        "<p>Every region of the map keeps a threat score. The score sets the region's threat level, and a higher "
        "level raises the chance that a new rival appears there (and, according to the Gen0 Editor's notes, makes "
        "the region's rival missions stronger). The chart shows the score each level starts at and the new-rival "
        "chance at that level.</p>" + threat_chart(levels) +
        f'<ul class="tips"><li>Level 1 starts at 0 points with a {pct(levels[0][2])} chance; {step_txt}, up to '
        f"{pct(last[2], 1)} at level {last[0]}.</li>"
        f"<li>The steps get longer: level 2 needs {fmt(levels[1][1])} points, the last level "
        f"{fmt(last[1] - levels[-2][1])} more than the one before.</li></ul>" +
        note("The game files give the thresholds and chances only. The Rivals update's Steam description says "
             "rivals appear as you take down large numbers of machines in a region; exactly how many points an "
             "action adds or removes isn't part of the extracted data.", "data"))


def threat_chart(levels):
    top = max(s for _, s, _ in levels)
    axis_max = int(math.ceil(top / 5000.0)) * 5000
    ticks = list(range(0, axis_max + 1, 5000))
    rows = []
    prev = None
    for lvl, score, chance in levels:
        w = score / axis_max * 100
        more = f", {fmt(score - prev)} more than level {lvl - 1}" if prev is not None else ""
        lab = f"{fmt(score)} pts"
        rows.append(f'<div class="tcr" title="Threat level {lvl}: from {fmt(score)} points{more}; new-rival chance '
                    f'{pct(chance, 1)}"><span class="tcl">{lvl}</span><span class="tct">'
                    f'<span class="tcb" style="width:{w:.2f}%"></span>'
                    f'<span class="tcv{" in" if w > 66 else ""}" style="--x:{w:.2f}%">{lab}</span></span>'
                    f'<span class="tcc">{pct(chance, 1).replace(".0%", "%")}</span></div>')
        prev = score
    # tick labels: '5,000' on wide screens, '5k' on phones (machine_weapons.css)
    axis = "".join(f'<span style="left:{t / axis_max * 100:.2f}%"><i class="lg">{fmt(t)}</i>'
                   f'<i class="sm">{fmt(t / 1000)}{"k" if t else ""}</i></span>' for t in ticks)
    return (f'<figure class="tchart" style="--ticks:{len(ticks) - 1}">'
            f'<figcaption>Threat score a region needs for each threat level, and the chance of a new rival at '
            f'that level</figcaption>'
            f'<div class="tcr tchd"><span class="tcl"><i class="lg">Level</i><i class="sm">Lv</i></span><span class="tct">Score needed (points)</span>'
            f'<span class="tcc"><i class="lg">Rival chance</i><i class="sm">Chance</i></span></div>'
            + "".join(rows) +
            f'<div class="tcr tcax"><span class="tcl"></span><span class="tct">{axis}</span>'
            f'<span class="tcc"></span></div></figure>')


# ---------------------------------------------------------------------------------------------------------------
# the two unique rival machines (their own pages are in the machines section)
# ---------------------------------------------------------------------------------------------------------------
def special_rivals(site):
    """Short facts on the Reaper and the Vulture from stats.json machine_health (class 'Rival')."""
    mh = site.data("stats")["machine_health"]
    mws = model(site)["weapons"]
    rows = []
    for fac, mtype, name in (("Swedish", "Tank", "Reaper"), ("Soviet", "Firebird", "Vulture")):
        lays = mh.get(fac, {}).get("Rival", {}).get("types", {}).get(mtype, {}).get("layouts", {})
        if not lays:
            continue
        hp = max(l["total_component_health"] for l in lays.values())
        regular = [l["total_component_health"] for c, cv in mh[fac].items() if c != "Rival"
                   for t, tv in cv["types"].items() if t == mtype for l in tv["layouts"].values()]
        wl = sorted((e for e in mws.values() if name in e["used_by"]), key=lambda e: e["key"])
        rows.append(f'<div class="panel mwrv"><h3>{site.link("machine", name)}</h3>' + kv([
            ("Faction", faction_tag(fac)),
            ("Based on", site.link("machine", mtype)),
            ("Total health", f"<b>{fmt(hp)}</b>" + (f" <span class=\"dim\">(×{fmt(hp / max(regular), 1)} the toughest "
                                                    f"regular {esc(mtype)} layout)</span>" if regular else "")),
            ("Weapons", ", ".join(site.link("machine-weapon", e["key"]) for e in wl))]) + "</div>")
    return ("<p>Besides the normal machines that become rivals, each faction has a separate Rival class with one "
            "unique machine: the Swedish Reaper, built on the Tank, and the Soviet Vulture, built on the Firebird. "
            "Their own pages have the full details.</p>" + '<div class="cols">' + "".join(rows) + "</div>" +
            '<p class="dim small">Total health adds up every component and armour plate: a size comparison, not an '
            'exact kill threshold.</p>')


# ---------------------------------------------------------------------------------------------------------------
# titles
# ---------------------------------------------------------------------------------------------------------------
# '(?: of)?' swallows the game's doubled 'of of' (The Guardian of of Ålnäset) so the place stays clean
TITLE_RE = re.compile(r"^The (?P<noun>.+?) (?P<prep>of|from)(?: of)? (?P<place>.+)$")


def classify_title(text):
    """-> dict(group, noun, prep, place). group: place | people | epithet | history."""
    t = text.strip()
    if "[" in t or t == "Defeated a player":
        return {"group": "history", "noun": "", "prep": "", "place": ""}
    m = TITLE_RE.match(t)
    if m and m.group("place") != "the Future":
        place = m.group("place")
        return {"group": "people" if place in PEOPLE else "place", "noun": m.group("noun"), "prep": m.group("prep"),
                "place": place}
    return {"group": "epithet", "noun": "", "prep": "", "place": ""}


def titles_intro(site, gd, rows):
    titles = gd["titles"]
    hist = {v: k for k, v in gd.get("history", {}).items()}
    groups = collections.Counter(c["group"] for _, _, c in rows)
    place_nouns = collections.Counter(c["noun"] for _, _, c in rows if c["group"] == "place")
    people_nouns = collections.Counter(c["noun"] for _, _, c in rows if c["group"] == "people")
    places = collections.Counter(c["place"] for _, _, c in rows if c["group"] == "place")
    peoples = collections.Counter(c["place"] for _, _, c in rows if c["group"] == "people")
    froms = sum(1 for _, _, c in rows if c["prep"] == "from")
    return "".join([
        f"<p>Every rival gets a title from a table of {fmt(len(titles) - groups['history'])} titles in the game "
        f"files. Most follow one pattern:</p>",
        '<div class="tpat"><span class="tp">The</span><span class="tp n">Epithet</span>'
        '<span class="tp">of / from</span><span class="tp p">Place or people</span></div>',
        f"<ul class=\"tips\"><li><b>{fmt(groups['place'])} place titles</b> combine {fmt(len(place_nouns))} epithets "
        f"(Tsar, Invader, Plague, Liberator ...) with {fmt(len(places))} places, from map locations like Hagaboda "
        f"to landscape words like <i>the Rugged Wilds</i>. Not every combination exists: each epithet appears with "
        f"{fmt(min(place_nouns.values()))} to {fmt(max(place_nouns.values()))} places, and {fmt(froms)} titles "
        f"use <i>from</i> (<i>The Menace from Sävered</i>).</li>"
        f"<li><b>{fmt(groups['people'])} people titles</b> name people instead of a place: <i>The Bane of "
        f"Friends</i>, <i>The Predator of Meatbags</i> ({fmt(len(people_nouns))} epithets, {fmt(len(peoples))} "
        f"words for people). Their wording fits the personal rivals that have defeated players, but the files we "
        f"read don't say when each set is used.</li>"
        f"<li><b>{fmt(groups['epithet'])} stand-alone titles</b>: <i>The Red Savior</i>, <i>General Frost</i>, "
        f"<i>Koschei the Deathless</i>. Many borrow names from Russian folklore and myth (Baba Yaga, Koschei, "
        f"Perun, the Zmey dragon, the Kikimora and the bogatyr heroes), which gives them a Soviet theme.</li></ul>",
        fold("Texts in the title table that are not titles", history_texts(rows, hist) + typo_note(titles, places),
             level=3, id="title-notes", right=f"{groups['history']} texts"),
    ])


def history_texts(rows, hist):
    """The four non-title texts of the table (rival history entries and a placeholder)."""
    items = []
    for h, t, c in sorted(rows, key=lambda r: r[1]):
        if c["group"] != "history":
            continue
        role = {"creation": "history entry when the rival is created; its title fills in [TITLE]",
                "level_up": "history entry for each level gained; [LEVEL] is the new level"}.get(hist.get(int(h)))
        if not role:
            role = ("placeholder text" if "TEMP" in t
                    else "probably a history entry; not referenced in the game's history table")
        items.append(f"<li><i>{esc(t)}</i> <span class=\"dim\">({esc(role)})</span></li>")
    return ("<p>Four texts in the title table are not titles: the rival history entries the game uses when a "
            "rival is created and levels up, one more that looks like a history entry, and a placeholder.</p>"
            f'<ul class="tips">{"".join(items)}</ul>') if items else ""


def _place_sort(p):
    return norm(re.sub(r"^(the|of) ", "", p.strip(), flags=re.I))


def _map_locations(site):
    key = ("maplocs", id(site))
    if key not in _CACHE:
        _CACHE[key] = {norm(x["name"]): x for x in site.data("map_locations")["list"]}
    return _CACHE[key]


def _rel(u):
    """'~/x.html?a=1&amp;b=2' -> 'x.html?a=1&b=2' (for the builder's JSON; the script adds the site root)."""
    return (u or "")[2:].replace("&amp;", "&") if u else ""


def place_info(site, place):
    """[what it is (text), wiki page (root-relative URL or ''), map link ('' if none)] for a title place."""
    regions = dict(REGIONS)
    if place in REGION_PLACES:
        k = REGION_PLACES[place]
        e = site.find("region", k)
        return ["a region of the map", e["path"] if e else "", _rel(maplink(region=[k]))]
    bare = re.sub(r"^(the|of) ", "", place.strip())
    ml = _map_locations(site).get(norm(bare))
    e = site.find("location", bare)
    if not ml and not e:
        return ["", "", ""]
    what = "a location"
    if ml:
        what += f" in the {regions.get(ml['region'], ml['region'])} region"
        mlink = _rel(maplink(show=[f"loc_{ml['kind']}"], region=[ml["region"]], at=(ml["x"], ml["z"]),
                             focus=ml["name"]))
    else:
        mlink = ""
    return [what, e["path"] if e else "", mlink]


def title_builder(site, rows):
    """Pick an epithet and a place / people word: the title they make, whether the game has it, and the place on
    the wiki and the map. Static chip lists (with counts) that machine_weapons.js makes interactive."""
    two = [(t, c) for _, t, c in rows if c["group"] in ("place", "people")]
    nouns = sorted({c["noun"] for _, c in two}, key=norm)
    places = sorted({c["place"] for _, c in two if c["group"] == "place"}, key=_place_sort)
    peoples = sorted({c["place"] for _, c in two if c["group"] == "people"}, key=_place_sort)
    parts = places + peoples
    ni, pi = {n: i for i, n in enumerate(nouns)}, {p: i for i, p in enumerate(parts)}
    ncount = collections.Counter(c["noun"] for _, c in two)
    pcount = collections.Counter(c["place"] for _, c in two)
    data = {"n": nouns, "p": parts, "np": len(places),
            "info": [place_info(site, p) for p in places] + [["people", "", ""] for _ in peoples],
            "t": [[ni[c["noun"]], pi[c["place"]], t.strip()] for t, c in sorted(two, key=lambda x: x[0])]}

    def chips(names, counts, k, start=0):
        return "".join(f'<button type="button" class="tbc" data-k="{k}" data-i="{start + i}">{esc(n)}'
                       f'<small>{counts[n]}</small></button>' for i, n in enumerate(names))
    js = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return (
        f"<p>Pick an epithet and a place (or people) to see the title they make, whether it is in the game and "
        f"where the place is. Picking one part shows only the parts it is combined with; the small number is how "
        f"many titles use a part.</p>"
        f'<div class="tb" id="tbuild">'
        f'<div class="tbout" aria-live="polite"><div class="tbtitle"><span class="tbw">The</span> '
        f'<span class="tbn tbslot">Epithet</span> <span class="tbw tbprep">of</span> '
        f'<span class="tbp tbslot">Place or people</span></div>'
        f'<div class="tbinfo">Pick an epithet and a place below, or try a random title.</div>'
        f'<div class="tbact"><button type="button" class="chip" data-a="rand">Random title</button>'
        f'<button type="button" class="chip" data-a="clear">Clear</button>'
        f'<label class="tbonly"><input type="checkbox" checked> Only parts that go together</label></div></div>'
        f'<div class="tbcols">'
        f'<div class="tbcol"><div class="tbh">Epithet <small>{len(nouns)}</small></div>'
        f'<input type="search" class="tbq" data-k="n" placeholder="Find an epithet..." aria-label="Find an epithet">'
        f'<div class="tbchips" data-k="n">{chips(nouns, ncount, "n")}</div></div>'
        f'<div class="tbcol"><div class="tbh">Place or people <small>{len(parts)}</small></div>'
        f'<input type="search" class="tbq" data-k="p" placeholder="Find a place..." aria-label="Find a place">'
        f'<div class="tbchips" data-k="p">{chips(places, pcount, "p")}'
        f'<span class="tbsep">People</span>{chips(peoples, pcount, "p", len(places))}</div></div>'
        f'</div><script type="application/json" class="tbdata">{js}</script></div>'
        f"<p class=\"dim small\">The {fmt(sum(1 for _, _, c in rows if c['group'] == 'epithet'))} stand-alone "
        f"titles have no parts; they are in the list below.</p>")


def standalone_group(t, mods):
    if t.endswith("of the Motherland"):
        return "… of the Motherland"
    if t.startswith(("The General's", "Bolshakov's")):
        return "The General's …"
    w = t.split()
    if w[0] == "The" and len(w) >= 3 and w[1] in mods:
        return f"The {w[1]} …"
    if w[0] == "The" and len(w) == 2:
        return "The … (one word)"
    return "Other titles"


def title_tree(rows):
    """Every title as a tree of closed folds: place titles by epithet, people titles by people word, stand-alone
    titles by their first word. A filter box opens the folds while typing (machine_weapons.js hides empty ones)."""
    def items(ts, grp):
        out = []
        for t in sorted(ts, key=lambda x: _place_sort(x[1]) if grp != "epithet" else norm(x[0])):
            text = t[0].strip()
            folk = any(x in text for x in FOLKLORE)
            out.append(f'<li class="fitem{" folk" if folk else ""}" data-f="{grp}{" folk" if folk else ""}">'
                       f'{esc(text)}</li>')
        return f'<ul class="tlist">{"".join(out)}</ul>'

    def branch(title, grp, key, groups, tid, note_html=""):
        n = sum(len(v) for v in groups.values())
        inner = note_html + "".join(
            fold(k, items(groups[k], grp), level=3, right=fmt(len(groups[k])), id=f"{tid}-{slug(k)}", cls="tsub")
            for k in sorted(groups, key=key))
        return fold(title, inner, level=3, right=f"{fmt(n)} titles", id=tid, cls="ttop")

    place, people, alone = (collections.defaultdict(list) for _ in range(3))
    for _, t, c in rows:
        if c["group"] == "place":
            place[c["noun"]].append((t, c["place"]))
        elif c["group"] == "people":
            people[c["place"]].append((t, c["noun"]))
    st = [t for _, t, c in rows if c["group"] == "epithet"]
    words = collections.Counter(t.split()[1] for t in st if t.startswith("The ") and len(t.split()) >= 3)
    mods = {w for w, n in words.items() if n >= 3 and not w.endswith("'s")}
    for t in st:
        alone[standalone_group(t.strip(), mods)].append((t, ""))
    last = lambda k: (k == "Other titles", norm(k))
    fb = ('<div class="filterbar" data-for="ttree"><input placeholder="Filter titles (a place, an epithet ...)" '
          'aria-label="Filter titles">'
          '<button class="chip on" data-g="g" data-f="*">All</button>'
          '<button class="chip" data-g="g" data-f="place">Place</button>'
          '<button class="chip" data-g="g" data-f="people">People</button>'
          '<button class="chip" data-g="g" data-f="epithet">Stand-alone</button>'
          '<button class="chip" data-g="g" data-f="folk">Folklore</button><span class="count"></span></div>')
    return ("<p>Every title, grouped like a tree: place titles by epithet, people titles by who they name, and "
            "stand-alone titles by how they start. Names from folklore are in <span class=\"folk\">gold</span>. "
            "Type in the filter to open the groups that match.</p>" + fb +
            '<div class="foldall" data-for="ttree"></div><div class="ttree" id="ttree">' +
            branch("Place titles", "place", norm, place, "tt-place") +
            branch("People titles", "people", _place_sort, people, "tt-people") +
            branch("Stand-alone titles", "epithet", last, alone, "tt-alone") + "</div>")


def typo_note(titles, places):
    """The game's own spelling slips, counted from the data, and places listed both with and without 'the'."""
    texts = list(titles.values())
    of_of = sum("of of" in t for t in texts)
    trailing = [t for t in texts if t != t.strip()]
    spots = sorted({t.strip().rsplit(" ", 1)[-1] for t in trailing})
    with_the = sorted(p[4:] for p in places if p.startswith("the ") and p[4:] in places)
    parts = [f"<i>Kommisar</i> next to <i>Kommissar</i>, <i>Ålnäset</i> next to <i>Ålnästet</i>, <i>Överby "
             f"bridge</i> next to <i>Överby Bridge</i>"]
    if of_of:
        parts.append(f"{plural(of_of, 'title')} with a doubled <i>of of</i> (counted under the right place here)")
    if trailing:
        parts.append(f"{plural(len(trailing), 'title')} with a trailing space"
                     + (f" (all {esc(spots[0])})" if len(spots) == 1 else ""))
    txt = "Titles are shown exactly as the game spells them, including its typos: " + ", ".join(parts[:-1]) + \
          (", and " if len(parts) > 1 else "") + parts[-1] + "."
    if with_the:
        txt += (f" {plural(len(with_the), 'place')} appear both with and without <i>the</i> ("
                + ", ".join(f"<i>{esc(p)}</i>" for p in with_the) +
                f"), so the {fmt(len(places))} distinct place strings stand for fewer real places.")
    return note(txt, "data")


