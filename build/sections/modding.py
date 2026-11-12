"""Modding tab: an overview of modding Generation Zero, the Gen0 tools, the F1 console / SteamVR mod, the Gen0 Map
Editor, and a game data reference (item IDs per quality, region / location / skill / research / statistic hashes,
and what each build/data file is).

The tool pages are written from the tools' own READMEs and source (gen0-tools, gen0-console, gen0-dlc); the data
page is generated from build/data (IDs.json, gamedata.json, stock.json, stats.json, kinds.json ...).

Registers kind 'tool': every Gen0 tool (anchors on modding/tools.html, plus the console and map editor pages) and the
main sections of the data page, so other sections can write site.link("tool", "Gen0 Editor").
"""
import re

from wiki.site import esc, slug, norm, fmt, table, bar, note, cards, kv, qbadge, tag, REGIONS, QUALITY

GH = "https://github.com/The-Bewwy-2510/"
REPOS = {  # repo name -> what it holds
    "gen0-tools": "Gen0 Editor, Modder, Extractor, VR and Hub (Windows, Python)",
    "gen0-console": "the F1 console with the SteamVR mode (C++ DLL)",
    "gen0-dlc": "the Gen0 Map Editor (Godot 4, C#)",
    "gen0-mapping": "the interactive map (static web page)",
    "gen0-wiki": "this wiki (Python generator + the static site in docs/)",
}
HEAD = '<link rel="stylesheet" href="~/assets/modding.css?v=2">'

INDEX = "modding/index.html"
TOOLS = "modding/tools.html"
CONSOLE = "modding/console.html"
MAPED = "modding/map-editor.html"
DATA = "modding/data.html"

# kind 'tool': key, path, title, aliases, one-line description
TOOL_ENTRIES = [
    ("Gen0 tools", TOOLS, "Gen0 tools", ["gen0-tools", "tools"],
     "The Gen0 tools for Windows: save editor, mod maker, file extractor, VR installer and the hub."),
    ("Gen0 Editor", TOOLS + "#editor", "Gen0 Editor", ["editor", "save editor", "DECA-Inv-26", "inv_editor"],
     "Savegame editor: inventory, skills, schematics, research, challenges, unlocks, safehouses, rivals, locations."),
    ("Gen0 Modder", TOOLS + "#modder", "Gen0 Modder", ["modder", "mod maker", "DECA-Mod-26", "Gen0 Skins"],
     "Builds dropzone mods: remove machines, player / vehicle / companion / loot settings, new weapon skins."),
    ("Gen0 Extractor", TOOLS + "#extractor", "Gen0 Extractor", ["extractor", "DECA-Dec-26"],
     "Unpacks the game archives: items, textures, 3D models, animations, audio, the world map and locations."),
    ("Gen0 VR", TOOLS + "#vr", "Gen0 VR", ["vr installer", "DECA-Vir-26"],
     "Installs or uninstalls the F1 console with the SteamVR mode, with backups, and switches VR on or off."),
    ("Gen0 Hub", TOOLS + "#hub", "Gen0 Hub", ["hub", "tools hub", "DECA-Hub-26"],
     "The Tools Hub: one window with a Launch button for each Gen0 tool."),
    ("Gen0 Map", TOOLS + "#map", "Gen0 Map (interactive map)", ["gen0-mapping", "interactive map"],
     "The Gen0 Editor's map as a web page: collectibles, schematics, safehouses, locations and placed loot."),
    ("Gen0 Console", CONSOLE, "Gen0 Console & SteamVR mod", ["gen0-console", "console", "F1 console", "VR mod",
                                                             "SteamVR mod", "Console Thingy", "xinput9_1_0.dll"],
     "The F1 mod menu (a fork of Generation Zero Console Thingy) with loot highlight, render distance and SteamVR."),
    ("Gen0 Map Editor", MAPED, "Gen0 Map Editor", ["gen0-dlc", "map editor", "level editor"],
     "Move, turn, copy and delete every object placed in the world, then build it into a dropzone mod."),
    ("Dropzone", INDEX + "#dropzone", "Dropzone folder & launch options", ["launch options", "vfs-fs"],
     "How Generation Zero loads mods from the dropzone folder, and the Steam launch options it needs."),
    ("Game data & IDs", DATA, "Game data & IDs", ["data", "ids", "hashes"],
     "Item IDs per quality, location / region / skill / research / statistic hashes, and the data files."),
]
# sections of the data page (registered as 'tool' so they are searchable; anchor ids must exist on the page)
DATA_ANCHORS = [
    ("weapon-ids", "Weapon IDs per quality", "weapon item ids equipmenthash quality"),
    ("attachment-ids", "Attachment IDs per quality", "scope silencer magazine ids"),
    ("ammo-ids", "Ammo IDs", "ammo item ids"),
    ("augment-ids", "Augment IDs", "augment bronze silver gold ids"),
    ("skin-ids", "Weapon skin IDs", "skin ids"),
    ("item-ids", "Item and material IDs", "items materials ids"),
    ("region-hashes", "Region hashes", "region hash"),
    ("location-hashes", "Location hashes", "location hash locationid"),
    ("safehouse-ids", "Safehouse IDs", "safehouse playerspawnpoints"),
    ("skill-hashes", "Skill hashes", "skill hash"),
    ("research-hashes", "Research hashes", "research augment task hash currencies"),
    ("challenge-hashes", "Challenge hashes", "challenge tier objective hash title"),
    ("stat-hashes", "Statistic hashes", "statistics namehash"),
    ("data-files", "The data files", "json data files extracted"),
]


def collect(site):
    for key, path, title, aliases, desc in TOOL_ENTRIES:
        site.register("tool", key, path, title, desc=desc, aliases=aliases, keywords="modding " + " ".join(aliases))
    for aid, title, kw in DATA_ANCHORS:
        site.register("tool", aid, f"{DATA}#{aid}", title, desc="Game data reference for modders and save editing.",
                      keywords=kw)


def build(site):
    build_index(site)
    build_tools(site)
    build_console(site)
    build_map_editor(site)
    build_data(site)


# ===============================================================================================================
# small helpers
# ===============================================================================================================
def repo(name, text=None):
    return f'<a href="{GH}{name}">{esc(text or name)}</a>'


def pre(text):
    """A block of code / commands, shown exactly as written."""
    return f'<pre class="mcode"><code>{esc(text)}</code></pre>'


def keys(*ks):
    return " ".join(f"<kbd>{esc(k)}</kbd>" for k in ks)


def keytable(rows):
    """rows: [(key or tuple of keys, what it does)]."""
    out = [[keys(*(k if isinstance(k, tuple) else (k,))), esc(v)] for k, v in rows]
    return table(["Key", "What it does"], out, cls="compact mkeys", sortable=False)


def steps(items):
    return '<ol class="msteps">' + "".join(f"<li>{i}</li>" for i in items) + "</ol>"


def ul(items):
    return "<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"


def tool(site, key, text=None):
    return site.link("tool", key, text)


def filterbar(tid, placeholder, chips=(), group="g", more=()):
    """Filter box for the table / list wrapped in <div id=tid>. chips: [(filter value, label)]. more: extra chip
    groups [(group, chips)]; a row must match one chip in every group (wiki.js ANDs the groups)."""
    ch = ""
    for g, cs in [(group, chips)] + list(more):
        if cs:
            ch += f'<button class="chip on" data-g="{g}" data-f="*">All</button>' + "".join(
                f'<button class="chip" data-g="{g}" data-f="{esc(f)}">{esc(lbl)}</button>' for f, lbl in cs)
    return (f'<div class="filterbar" data-for="{tid}"><input placeholder="{esc(placeholder)}">{ch}'
            f'<span class="count"></span></div>')


def ftable(tid, headers, rows, filters, **kw):
    """table() whose n-th body row gets data-f=filters[n] (table() has no row attributes), in <div id=tid>."""
    html = table(headers, rows, **kw)
    it = iter(filters)
    head, _, rest = html.partition("<tbody>")
    rest = re.sub(r"<tr>", lambda _: f'<tr data-f="{esc(next(it, ""))}">', rest)
    return f'<div id="{tid}">{head}<tbody>{rest}</div>'


def idc(v):
    """An item ID / hash cell: monospace, selected with one click (CSS user-select: all)."""
    if v in (None, "", "N/A"):
        return None
    return f'<code class="idc">{esc(v)}</code>'


def link_any(site, kinds, key, text=None):
    """Link to the first kind that has key registered (falls back to the first kind, which records the miss)."""
    for k in kinds:
        if site.find(k, key):
            return site.link(k, key, text)
    return site.link(kinds[0], key, text)


def page(site, path, title, body, sub, lead, desc, infobox_html="", kind=None, wide=False):
    site.page(path, title, "\n".join(body), "modding", sub=sub, lead=lead, desc=desc, infobox_html=infobox_html,
              kind=kind, head_extra=HEAD, wide=wide)


# ===============================================================================================================
# modding/index.html - overview
# ===============================================================================================================
def build_index(site):
    lead = ("<p>Generation Zero can be modded in three ways: <b>files the game "
            "loads from a <code>dropzone</code> folder</b> instead of its own archives, a <b>DLL next to the game's "
            "exe</b> that adds an in-game menu, and <b>editing the savegame</b>. This tab covers all three and the "
            "free Gen0 tools that do the work for you, plus a reference of the item IDs and hashes you need when "
            "you edit files by hand.</p>")
    body = [
        cards([
            {"href": "~/" + TOOLS, "title": "Gen0 tools", "tag": "WIN", "color": "#1c5777",
             "sub": "Editor (saves), Modder (dropzone mods and weapon skins), Extractor (game files), VR and Hub."},
            {"href": "~/" + CONSOLE, "title": "Console & VR mod", "tag": "DLL", "color": "#7a2a26",
             "sub": "The F1 mod menu: god mode, spawning, weather, teleport, loot highlight, render distance, SteamVR."},
            {"href": "~/" + MAPED, "title": "Map editor", "tag": "3D", "color": "#5f4258",
             "sub": "Move, copy and delete the objects placed in the world and build them into a mod."},
            {"href": "~/" + DATA, "title": "Game data & IDs", "tag": "IDS", "color": "#4d4a2c",
             "sub": "Item IDs for every quality, location, region, skill, research and statistic hashes."},
        ]),
        index_overview(site),
        index_dropzone(site),
        index_console(site),
        index_saves(site),
        index_paths(site),
        index_safety(site),
        index_requirements(site),
        index_repos(site),
    ]
    page(site, INDEX, "Modding Generation Zero", body, "modding", lead,
         "How to mod Generation Zero: the dropzone folder and Steam launch options, DLL mods, save editing, "
         "backups, and the Gen0 tools.")


def index_overview(site):
    rows = [
        [tool(site, "Gen0 Editor"), "Your savegame", "Edits a save: inventory, skills, schematics, research, "
         "challenges, unlocks, safehouses, rivals, locations and keys.", "Writes the save (keeps a backup)"],
        [tool(site, "Gen0 Modder"), "A dropzone mod", "Removes machines, changes player, vehicle, companion and loot "
         "settings, adds new weapon skins.", "Writes its own <code>dropzone\\</code>; you copy it in"],
        [tool(site, "Gen0 Map Editor"), "A dropzone mod", "Moves, turns, copies and deletes objects placed in the "
         "world.", "Builds a dropzone mod and can install it (with backups)"],
        [tool(site, "Gen0 Console"), "The running game", "In-game F1 menu: cheats, spawning, weather, teleport, "
         "loot highlight, render distance, SteamVR.", "A DLL in the game folder"],
        [tool(site, "Gen0 VR"), "The game folder", "Installs / uninstalls the console with VR, with a backup.",
         "Copies the DLLs into the game folder"],
        [tool(site, "Gen0 Extractor"), "Nothing (read only)", "Unpacks the archives: items, textures, models, "
         "animations, audio, world map, locations.", "Writes exports next to itself"],
        [tool(site, "Gen0 Hub"), "Nothing", "Launches the other tools.", "–"],
        [tool(site, "Gen0 Map"), "Nothing", "The interactive map in a browser.", "–"],
    ]
    return (bar("The tools at a glance", id="tools") +
            "<p>Every tool is free and its source is on GitHub. The table says what each one changes, which matters for "
            "backups: only the Editor touches your save, and only Gen0 VR and the Map Editor's Install copy files "
            "into the game folder.</p>" +
            table(["Tool", "Changes", "What it does", "Writes"], rows, sortable=False) +
            "<p>The Windows tools in " + repo("gen0-tools") + " all look alike: a small Python program that opens "
            "a game-styled window (a local web page shown by Brave in app mode, or Chrome when Brave isn't "
            "installed; never Edge) with its own private browser profile. Nothing is uploaded anywhere. The Gen0 "
            "Hub starts them from one window. The game folder is only ever read, except by Gen0 VR, which "
            "installs the VR mod's files there.</p>")


def index_dropzone(site):
    opts = ("--vfs-fs dropzone --vfs-archive archives_win64/initial --vfs-archive archives_win64/supplemental "
            "--vfs-archive archives_win64/optional")
    return "".join([
        bar("Dropzone mods and launch options", id="dropzone"),
        "<p>The game normally reads everything from the packed archives in <code>archives_win64</code>. With the "
        "launch options below it also reads a folder called <code>dropzone</code> next to "
        "<code>GenerationZero_F.exe</code>, and a file in there with the same path as a game file is used "
        "instead of the original. Mods made by the " + tool(site, "Gen0 Modder") + " and the " +
        tool(site, "Gen0 Map Editor") + " are such files.</p>",
        "<h3>Turning dropzone on (Steam)</h3>",
        steps(["In your Steam <b>Library</b>, right-click <b>Generation Zero</b> and choose <b>Properties</b>.",
               "Paste this into <b>Launch options</b>:" + pre(opts),
               "Create a folder called <code>dropzone</code> next to <code>GenerationZero_F.exe</code> if it isn't "
               "there yet."]),
        "<p>Without these options the game ignores <code>dropzone</code>, so a mod that \"does nothing\" is "
        "usually a missing launch option. Leaving the options in with an empty <code>dropzone</code> folder plays "
        "the normal game.</p>",
        "<h3>Installing, removing and updating a mod</h3>",
        ul(["<b>Install</b>: the Modder builds its mod into a <code>dropzone\\</code> folder next to itself. Copy "
            "<b>everything</b> inside it into the game's <code>dropzone</code> folder. The Map Editor's Install "
            "button copies its build in for you.",
            "<b>Turn a mod off</b>: delete the files it added from the game's <code>dropzone</code> (or put "
            "another mod's copies of those files back).",
            "<b>After a game update</b>: take the mod out before playing, then build it again from the updated "
            "game files. A mod is a patched copy of the game's own files, so an old one can undo or break what "
            "the update changed."]),
        note("The game reads its settings from <code>gdc\\global.gdcc</code>, a bundle holding byte-exact copies "
             "of the settings files. Loose settings files in <code>dropzone</code> are ignored, so every Modder "
             "mod is a patched <code>global.gdcc</code>; two mods that both change it can't simply be copied over "
             "each other. The Modder can build on top of another mod's dropzone folder instead (its GAME tab).",
             "data", "Why mods clash"),
    ])


def index_console(site):
    return "".join([
        bar("DLL mods: the F1 console", id="dll"),
        "<p>The console is a file called <code>xinput9_1_0.dll</code> that goes next to "
        "<code>GenerationZero_F.exe</code>. Windows loads it with the game, and it adds an in-game menu you open "
        "with <kbd>F1</kbd>. It changes the running game's memory, not its files, so it needs no launch options "
        "and can be used alongside dropzone mods. See " + tool(site, "Gen0 Console", "the console page") +
        " for every feature, and " + tool(site, "Gen0 VR") + " for installing it with a backup.</p>",
        "<p>On Linux / Steam Deck (Proton) add this to the launch options so the game uses the mod's DLL instead "
        "of the built-in one:</p>",
        pre('WINEDLLOVERRIDES="xinput9_1_0.dll=n,b" %command%'),
        "<p>If you also use dropzone mods, put the <code>--vfs-fs ...</code> options after "
        "<code>%command%</code>.</p>",
    ])


def index_saves(site):
    return "".join([
        bar("Save editing", id="saves"),
        "<p>The " + tool(site, "Gen0 Editor") + " opens a savegame, shows it in game-styled tabs and writes the "
        "result back over the original. Before anything is written it runs a set of save checks, writes through a "
        "temporary copy and reads the file back to compare it. When a save is loaded, the file as it was is "
        "copied to <code>Backup\\savegame-backup</code> next to the editor.</p>",
        "<p>Saves are in <code>Documents\\Avalanche Studios\\GenerationZero\\Saves\\</code> (or under "
        "<code>OneDrive\\Documents</code> when Windows moves your Documents there). Newer saves are zstd-compressed; the editor reads both those and the older uncompressed "
        "ones. EXPORT JSON writes the decoded save as readable JSON to <code>Output\\savegame.json</code>.</p>",
        "<p>Item IDs, location and skill hashes for editing a save by hand are on the " +
        tool(site, "Game data & IDs", "game data page") + ".</p>",
    ])


def index_paths(site):
    rows = [
        ["Game folder", "<code>...\\steamapps\\common\\GenerationZero\\</code>",
         "<code>GenerationZero_F.exe</code>, the archives in <code>archives_win64\\</code>, your "
         "<code>dropzone\\</code>, and the console's files (<code>xinput9_1_0.dll</code>, "
         "<code>GZConsoleThingy.ini</code>, <code>GZVR.txt</code>, <code>logs\\</code>)"],
        ["Saves", "<code>Documents\\Avalanche Studios\\GenerationZero\\Saves\\</code>",
         "The savegame (in a sub-folder)"],
        ["Game settings", "<code>...\\Saves\\settings\\&lt;Steam ID&gt;\\settings.json</code>",
         "Graphics and game options (Gen0 VR can swap in a VR copy)"],
        ["Map Editor data", "<code>%LOCALAPPDATA%\\Gen0 Map Editor</code>",
         "The Map Editor's changes, world cache, builds and backups"],
    ]
    return (bar("Where things are", id="paths") +
            "<p>The game folder path is the Steam default; the tools have a Browse button, and Gen0 VR, the "
            "Extractor, the Modder and the Map Editor also find the game in your other Steam libraries (another "
            "drive, e.g. <code>D:\\Steam</code>). The Map Editor asks for the folder with "
            "<code>archives_win64</code> in it when it can't find one.</p>" +
            table(["What", "Where", "Holds"], rows, sortable=False))


def index_safety(site):
    backups = [
        [tool(site, "Gen0 Editor"), "<code>Backup\\savegame-backup</code>", "The save exactly as it was loaded"],
        [tool(site, "Gen0 Modder"), "<code>backup\\&lt;date&gt;\\</code>", "The previous build, moved there "
         "before each new one"],
        [tool(site, "Gen0 VR"), "<code>backup\\before-install\\</code>", "What was in the game folder before the "
         "first install (renamed with the date when an uninstall uses it, never deleted), plus replaced "
         "<code>settings.json</code> files"],
        [tool(site, "Gen0 Map Editor"), "<code>%LOCALAPPDATA%\\Gen0 Map Editor</code>", "Backups made when it "
         "installs into the game"],
    ]
    return "".join([
        bar("Backups and safety", id="safety"),
        note("<b>Back up your save before using the editor or playing with a mod.</b> Copy the whole "
             "<code>Saves</code> folder somewhere safe; it takes seconds.", "warn"),
        "<p>Each tool also keeps its own backup, next to the tool unless noted:</p>",
        table(["Tool", "Backup", "What it holds"], backups, sortable=False),
        "<h3>Things that can go wrong</h3>",
        ul(["<b>Weapon skin mods change the save.</b> Once you have used a skin from a Modder skin mod, removing "
            "the mod's files breaks that save. Keep the mod installed for that save, or restore a backup from "
            "before the skin.",
            "<b>Game updates.</b> Remove dropzone mods before playing after an update and rebuild them. If the "
            "game crashes at start after an update with the console installed, uninstall it (Gen0 VR).",
            "<b>The console changes game memory</b> and may cause instability or crashes. Its new features use "
            "addresses of the <b>Steam build</b>; on the Microsoft Store build they stay off.",
            "<b>Machines already alive stay.</b> Removing a machine type with the Modder stops the world refilling "
            "it; machines that already exist in your save remain until destroyed.",
            "<b>Unsigned programs.</b> Windows may warn the first time you start a built <code>.exe</code>, because "
            "it isn't signed: choose <i>More info</i>, then <i>Run anyway</i>.",
            "<b>Close the game first.</b> Gen0 VR waits for the game to close before installing or uninstalling, "
            "and a console build can't copy its DLL into the game folder while the game runs.",
            "<b>Co-op.</b> Some console features (spawning machines, controlling or making a machine "
            "invulnerable) only work for the host or for machines your game hosts."]),
    ])


def index_requirements(site):
    rows = [
        ["Gen0 Editor, Modder, Extractor, VR, Hub", "Windows, Python 3 (tick <b>Add python.exe to PATH</b> when "
         "installing), Brave or Google Chrome. The .bat files install the extra packages: <code>zstandard</code> "
         "for the Editor (only on Python older than 3.14), <code>pillow</code> and <code>numpy</code> for the "
         "Extractor and the Modder's Skins tab, <code>pyinstaller</code> to build an .exe."],
        ["Gen0 Map Editor", "The setup program; to build it yourself the .NET 8 SDK, Godot 4.7.2 .NET with its "
         "export templates and Inno Setup 6."],
        ["Console (building)", "Visual Studio 2022 or its Build Tools (C++ workload) and CMake 3.16+. The ready DLL "
         "needs nothing; the VR mode needs SteamVR and <code>openvr_api.dll</code>."],
        ["Interactive map, this wiki", "A web browser. To open them from your own disk, serve the folder (for "
         "example <code>python -m http.server</code>)."],
    ]
    return bar("Requirements", id="requirements") + table(["Tool", "Needs"], rows, sortable=False)


def index_repos(site):
    rows = [[repo(n), esc(w), f'<a href="{GH}{n}/issues">Issues</a>'] for n, w in REPOS.items()]
    return (bar("Source code", id="repos") +
            "<p>All of it is on GitHub under " + f'<a href="{GH[:-1]}">The-Bewwy-2510</a>' + ". Each repository "
            "has a README with the full details; the pages of this tab are written from them.</p>" +
            table(["Repository", "What's in it", ""], rows, sortable=False))


# ===============================================================================================================
# modding/tools.html - the Gen0 tools
# ===============================================================================================================
def build_tools(site):
    lead = ("<p>The " + repo("gen0-tools", "Gen0 tools") + " are five small Windows programs for Generation Zero, "
            "each in its own folder of the repository. They share one way of working: <code>Run without "
            "building.bat</code> starts a tool straight from its Python source, and <code>Build Gen0 "
            "&lt;Tool&gt;.bat</code> turns it into a standalone <code>Gen0 &lt;Tool&gt;.exe</code> with "
            "PyInstaller. Each one opens a game-styled window with tabs and footer hotkeys like the game's "
            "menus.</p>")
    body = [
        tools_common(site),
        tools_editor(site),
        tools_modder(site),
        tools_extractor(site),
        tools_vr(site),
        tools_hub(site),
        tools_map(site),
    ]
    page(site, TOOLS, "Gen0 tools", body, "tools", lead,
         "The Gen0 tools for Generation Zero: Editor, Modder, Extractor, VR and Hub - features, how to run and "
         "build them, and the files they make.", infobox_html=tools_infobox(site))


def tools_infobox(site):
    from wiki.site import infobox
    return infobox("Gen0 tools", [
        ("Repository", repo("gen0-tools")),
        ("Runs on", "Windows"),
        ("Needs", "Python 3, Brave or Chrome"),
        ("Window", "Local web page, Brave / Chrome app mode"),
        ("Network", "127.0.0.1 only, private token"),
        (None, "Tools"),
        ("Saves", tool(site, "Gen0 Editor")),
        ("Mods", tool(site, "Gen0 Modder")),
        ("Game files", tool(site, "Gen0 Extractor")),
        ("Console + VR", tool(site, "Gen0 VR")),
        ("Launcher", tool(site, "Gen0 Hub")),
    ], subtitle="Save editor, mod maker, extractor, VR installer, hub")


def tools_common(site):
    rows = [
        ["<code>editor\\</code>", "Gen0 Editor", "<code>inv_editor.py</code> + <code>web\\</code> (the item list is "
         "<code>web\\misc\\IDs.json</code>)"],
        ["<code>modder\\</code>", "Gen0 Modder", "<code>source\\gen0_modder.py</code> + <code>gzm_*.py</code>, "
         "<code>gzs_*.py</code>, <code>source\\templates\\</code>, <code>source\\web\\</code>"],
        ["<code>extractor\\</code>", "Gen0 Extractor", "<code>source\\gen0_gui.py</code> + <code>gz_*.py</code> + "
         "<code>source\\web\\</code>"],
        ["<code>vr\\</code>", "Gen0 VR", "<code>source\\gen0_vr.py</code> + <code>source\\web\\</code>; the mod to "
         "install goes in <code>vr\\mod\\</code>, its source in <code>vr\\mod-source\\</code>"],
        ["<code>hub\\</code>", "Gen0 Hub", "<code>source\\gen0_hub.py</code> + <code>source\\web\\</code>; built "
         "tools go in <code>hub\\toolexe\\</code>"],
    ]
    return "".join([
        bar("Running and building", id="running"),
        steps(["Install <a href=\"https://www.python.org/downloads/\">Python 3</a> and tick <b>Add python.exe to "
               "PATH</b>. Have Brave or Google Chrome installed.",
               "Download the repository (GitHub: <b>Code &rarr; Download ZIP</b>) and unpack it.",
               "In a tool's folder double-click <code>Run without building.bat</code> to try it. The first run "
               "installs the Python packages that tool needs.",
               "Optional: double-click <code>Build Gen0 &lt;Tool&gt;.bat</code> for a standalone .exe (a minute or "
               "a few). Keep the .exe in its folder: it saves its settings and output there. Rebuild after "
               "changing any source file."]),
        "<p>Every tool runs a small web server that only your computer can reach (127.0.0.1, a random port and a "
        "private access token) and shows its window with its own browser profile, so your normal browser tabs, "
        "extensions and history are not touched. Everything a tool creates while running (settings, logs, "
        "backups, built mods, exports, built .exe files) is in the repository's <code>.gitignore</code>.</p>",
        table(["Folder", "Tool", "Source"], rows, sortable=False),
    ])


def tool_head(site, anchor, title, summary, facts):
    """The start of one tool's section: bar with anchor, a one-line summary, and a key-value box."""
    return bar(title, id=anchor) + f"<p>{summary}</p>" + kv(facts)


# ---------------------------------------------------------------------------------------------------------------
def tools_editor(site):
    tabs = [
        ["MAP", "", "The interactive world map (collectibles, schematics, house photos, safehouses, control points, "
         "beacons, locations, with region borders and filters). With a save loaded it can show what that save has "
         "already collected or unlocked.", "–"],
        ["STATISTICS", "", "The character's statistics. Read only.", "<code>Characters[].Statistics</code>, "
         "<code>World.Statistics</code>"],
        ["PLAYER", "INVENTORY", "Weapons, attachments and weapon augments: edit, add, remove. ADD ITEM adds a "
         "weapon, attachment, ammo, item or material of any quality / amount.", "<code>Characters[].Inventory</code>"],
        ["", "STORAGE", "The safehouse storage box.", "<code>Profile.SafehouseStorage</code>"],
        ["", "RECYCLE", "The resource storage (recycling).", "<code>Profile.ResourceStorage</code>"],
        ["", "SKILLS", "Skill ranks, skill points and the active skill.", "<code>Characters[].Skills</code>, "
         "<code>SkillLevel</code>, <code>SkillPoints</code>"],
        ["", "SCHEMATICS", "Schematic points per category and the unlocked crafting schematics, laid out like the "
         "game's trees.", "<code>Profile.Currencies</code>, <code>Profile.ItemStash</code>"],
        ["", "RESEARCH", "Augment research task counters (also all Silver / all Gold / reset).",
         "<code>Profile.Currencies</code>"],
        ["", "CHALLENGES", "Meta-progression challenge tiers; complete or reset a whole category.",
         "<code>Characters[].Challenges</code>"],
        ["", "VANITY", "Unlocked apparel, face paint, weapon skins, companion parts, vehicles and emotes. DLC items "
         "only when the save shows the pack as owned.", "<code>Profile.ItemStash</code>"],
        ["WORLD", "MISSIONS", "Story and side missions with their stages. Read only.", "<code>MissionCampaigns</code>"],
        ["", "SAFEHOUSES", "Unlock or lock safehouses (Yttervik, the starting one, stays unlocked).",
         "<code>PlayerSpawnPoints</code> (three copies)"],
        ["", "RIVALS", "Each rival's XP and level; the level-up history follows.",
         "<code>RivalRegions[].Rivals[].XP</code>"],
        ["", "REGIONS", "Each rival region's threat points (threat level).", "<code>RivalRegions[].InsurrectionScore"
         "</code>"],
        ["", "LOCATIONS", "Discover / undiscover map locations; advanced mode edits each location's progress "
         "(loot crates needed and found, and what was found there).", "<code>LocationSummaries</code>"],
        ["", "KEYS", "Door keys, bunker barcodes, keycards and mission items (mission keys ask first).",
         "<code>Profile.ItemStash</code>"],
        ["LOG", "", "Everything changed since the editor was opened (kept in memory only, with COPY).", "–"],
    ]
    rows = [[f"<b>{esc(a)}</b>" if a else "", esc(b), esc(c), d] for a, b, c, d in tabs]
    files = [
        ["<code>Backup\\savegame-backup</code>", "The save as it was when loaded"],
        ["<code>Output\\savegame.json</code>", "EXPORT JSON: the decoded save as readable JSON"],
        ["<code>loadouts\\&lt;name&gt;.json</code>", "EXPORT: a whole save as a loadout (IMPORT loads it again or "
         "merges its inventory into another save)"],
        ["<code>Gen0 Inv settings.json</code>", "The window's settings (open tab, map filters ...)"],
        ["<code>web\\misc\\IDs.json</code>", "The item list (also on the " + tool(site, "Game data & IDs", "data page")
         + "); you can edit it"],
    ]
    return "".join([
        tool_head(site, "editor", "Gen0 Editor", "A savegame editor. It loads a Generation Zero save, shows it in "
                  "game-styled tabs, and SAVE writes the result back over the original savegame after its save "
                  "checks pass.", [
                      ("Folder", "<code>editor\\</code> (<code>inv_editor.py</code> + <code>web\\</code>)"),
                      ("Start", "<code>Run without building.bat</code> (no console window)"),
                      ("Build", "<code>Build Gen0 Editor.bat</code> &rarr; <code>Gen0 Editor.exe</code>"),
                      ("Needs", "Python 3; <code>zstandard</code> on Python older than 3.14 (saves are "
                       "zstd-compressed)"),
                      ("Changes", "Only the savegame you load, after a backup")]),
        "<h3>Tabs</h3><p>The first column is the main tab, the second its sub tabs. The last column "
        "names the part of the save it edits, useful if you look at an exported <code>savegame.json</code>.</p>",
        table(["Tab", "Sub tab", "What you can do", "Save field"], rows, sortable=False, cls="compact"),
        "<h3>Workflow</h3>",
        steps(["BROWSE to your savegame (it starts in the game's Saves folder) and press LOAD. The original is "
               "copied to <code>Backup\\</code>.",
               "Make your changes; the LOG tab lists every one.",
               "SAVE (<kbd>Ctrl+S</kbd>). The editor checks the rebuilt save, writes it through a temporary copy "
               "and reads it back before it replaces the original.",
               "Start the game and load the character."]),
        "<h3>Hotkeys</h3>",
        keytable([("Ctrl+S", "Save"), ("Ctrl+O", "Browse for a savegame"), ("Ctrl+L", "Load"),
                  ("Ctrl+E", "Export the decoded save as JSON"), ("0", "Map: whole map"), ("B", "Map: region borders"),
                  ("F", "Map: filters panel"), ("S", "Map: icon size"), ("G", "Map: icon style"),
                  ("C", "Map: hide what the loaded save has done")]),
        "<h3>Files it makes (next to the editor)</h3>",
        table(["File", "What"], files, sortable=False),
    ])


# ---------------------------------------------------------------------------------------------------------------
def tools_modder(site):
    tabs = [
        ["GAME", "The game folder (only ever read), an optional other mod's dropzone folder to build on top of, "
         "where the mod goes and how to install it."],
        ["MACHINES", "Tick machines, or single classes, to remove from the world. <i>Also stop scripted spawns</i> "
         "also blocks them in missions, events, beacons and reinforcements."],
        ["PLAYER", "Carry weight (up to 99,999 kg), max health, sprint duration (or infinite), stamina refill delay "
         "and time, storage box and recycling capacity (given to every upgrade level of that storage)."],
        ["VEHICLES", "Flakmopeds, motorbikes and the bicycle: top speed, acceleration, steering, grip, stability, "
         "steepest slope, fuel range (or infinite), health (or indestructible), headlight width and reach, horn "
         "sound."],
        ["COMPANION", "Shutdown health, indestructible, repair beam heal, armour health and resistance, weapon damage, "
         "a launcher that can't hurt you, and swapping its SMG / shotgun / launcher for another machine's weapon "
         "(experimental)."],
        ["WORLD", "How long emptied loot (boxes, bags, bodies) takes to come back, and the loot drops: items per "
         "container, ammo / crafting materials / supplies per stack, and how likely quality 4-6 finds are."],
        ["SKINS", "New weapon skins from your own textures (Color, Metal Rough, Normal PNGs, optional Emissive, and "
         "an icon), locked until picked up from a thrown health station or unlocked from the start; PREVIEW shows "
         "the skin on the weapon's 3D model."],
        ["LOG", "Which tabs go into the mod, <b>Build mod</b>, Reset all tabs, and what the last build did."],
    ]
    how = [
        ["Machines", "<code>settings/hp_settings/reserve_0.bin</code> (each population's target count set to 0) and "
         "<code>settings/spawn_defs/spawn_animals_defs.bin</code> (removed machines point at a file that doesn't "
         "exist). Friendly ticks, the RC tick, the spy tick and the Companion are never touched."],
        ["Player", "Carry weight in <code>gdc\\global.gdcc</code>; max health and storage in "
         "<code>settings\\playersettings.playersettingsc</code>; stamina in <code>player_movement.mtunec</code> "
         "inside <code>local_player_character.ee</code> (the whole 50 MB file goes into the mod)."],
        ["Companion", "<code>comp_load01-03.ee</code>, <code>companion.aitunec</code>, <code>companion_armor.bin</code> "
         "(in <code>global.gdcc</code>), its ammo and weapon files."],
        ["World", "Each loot container's <code>.ee</code> (PersistentTimer, the game's default 14400 s = 4 hours); "
         "the 281 loot tables in <code>settings/all_loot_crates.lootcrates</code>. The backpack you drop on death "
         "is never changed."],
        ["Vehicles", "Each vehicle colour's <code>.ee</code> (driving physics in <code>.vmodc</code>, lights / horn / "
         "invulnerable in the <code>.epe</code>). Top speed raises engine revs and gearing and lowers air drag "
         "by the same factor, so the vehicle really reaches it."],
        ["Skins", "Built last, on top of the other tabs: a new item in <code>global.gdcc</code>, a body model and "
         "textures packed into every quality of the weapon's <code>.ee</code>, a skin entity, a 128&times;128 "
         "icon, its name, and (when locked) a health station box holding the skins."],
    ]
    files = [
        ["<code>dropzone\\</code>", "The built mod: copy everything inside it into the game's dropzone"],
        ["<code>backup\\&lt;date&gt;\\</code>", "The previous build, moved here before each new one"],
        ["<code>mods\\</code>", "Exported choices (<code>.json</code>) to share; Import lists them"],
        ["<code>last_build.json</code>", "What the last build contains"],
        ["<code>Gen0 Modder settings.json</code>, <code>Gen0 Modder log.txt</code>", "Your choices, the log of the "
         "last build"],
    ]
    return "".join([
        tool_head(site, "modder", "Gen0 Modder", "A mod maker. Tick what you want changed on its tabs and it builds "
                  "one dropzone mod from the game's original files. It merged in the former Gen0 Skins tool as its "
                  "Skins tab.", [
                      ("Folder", "<code>modder\\</code>"),
                      ("Start", "<code>Run without building.bat</code> (first run installs Pillow and numpy)"),
                      ("Build", "<code>Build Gen0 Modder.bat</code> &rarr; <code>Gen0 Modder.exe</code>"),
                      ("Makes", "<code>dropzone\\</code> next to itself"),
                      ("Needs", "The " + tool(site, "Dropzone", "dropzone launch options") + " in Steam")]),
        "<h3>Tabs</h3><p>Tabs with a diamond are parts of the mod: everything ticked goes into one build.</p>",
        table(["Tab", "What it changes"], [[f"<b>{a}</b>", b] for a, b in tabs], sortable=False),
        "<h3>Sharing a mod</h3><p><b>Export</b> saves the ticked tabs' choices as <code>mods\\&lt;name&gt;.json</code> "
        "(a few KB, no game files). The other person puts it in their own <code>mods\\</code> folder, presses "
        "<b>Import</b>, picks it and builds. The same game version gives exactly the same mod. Skins aren't part of "
        "Export, because they point at PNG files on your PC.</p>",
        "<h3>How it works</h3><p>All edits are same-size and in place: nothing in the game's bundles moves. This is "
        "where each tab's change lives:</p>",
        table(["Tab", "Files it patches"], [[f"<b>{a}</b>", b] for a, b in how], sortable=False),
        note("Stamina is a \"heart rate\" in the game files: sprinting raises it 25 per second up to 100 (4 seconds "
             "of sprint), and it refills at 50 per second after a 2 second pause. Loot qualities q1 to q6 have "
             "falling weights in the loot tables.", "data"),
        "<h3>Hotkeys</h3>",
        keytable([("Enter", "Build the mod"), ("A", "Add a skin (Skins tab)"), ("O", "Open the dropzone folder"),
                  ("E", "Export your choices"), ("I", "Import someone else's")]),
        "<h3>Files it makes (next to the program)</h3>",
        table(["File", "What"], files, sortable=False),
        note("Once you have used a skin from the mod, removing the mod's files breaks that save. Machines already "
             "alive in a save stay there until destroyed.", "warn"),
    ])


# ---------------------------------------------------------------------------------------------------------------
def tools_extractor(site):
    tabs = [
        ["GAME", "Pick the game folder and press UNPACK once: it builds the file index (about an hour the first "
         "time, minutes after a game update; it can be stopped and resumed)."],
        ["DATA", "Items, Map, Locations"],
        ["TEXTURES", "Asset Textures, GUI"],
        ["3D MODELS", "Weapons, Attachments, Machines, NPCs, World, Places"],
        ["AUDIO", "Music, Dialogue, Ambience, Weapons, Machines, Vehicles, Player, GUI, Effects, Missions, Other"],
        ["LOG", "Progress of the running export"],
    ]
    out = [
        ["<code>files\\_index\\</code>", "The file index. Keep it: it takes an hour to rebuild. Every tab reads the "
         "game files straight from the archives."],
        ["<code>data\\</code>", "Items, collectibles, house photos, schematics, player safehouses, player bases, relay "
         "beacons (<code>.csv</code> + <code>.json</code>)"],
        ["<code>map\\</code>", "<code>world_map_color_zoom0..3.png</code>, <code>world_map_zoom1..3.png</code>, "
         "<code>heightmap.png</code> (16-bit, metres above sea level), <code>spawn_maps\\&lt;machine&gt;.png</code> "
         "+ <code>all_machines.png</code>"],
        ["<code>textures\\</code>", "PNG textures in the game's folders"],
        ["<code>models\\weapons\\</code>", "<code>&lt;Type&gt;\\&lt;Weapon&gt;\\&lt;id&gt;_q1.glb</code> (+ "
         "<code>_rigged.glb</code>), every quality"],
        ["<code>models\\attachments\\</code>", "Scopes, compensators, silencers, barrel extensions / chokes, extended "
         "magazines, every quality (vision modules have no model)"],
        ["<code>models\\machines\\</code>", "<code>Swedish | Soviet\\&lt;Machine&gt;\\&lt;Class&gt;\\</code> and "
         "<code>Bosses\\Reaper | Vulture</code>, static and rigged"],
        ["<code>models\\world\\</code>, <code>models\\npcs\\</code>", "Every other model by game folder (buildings, "
         "props, vegetation, vehicles ...) and people (bodies, heads, hair, clothing)"],
        ["<code>models\\places\\</code>", "A whole location file (<code>.nl</code> + <code>.fl</code>) as one "
         "<code>.glb</code> in world coordinates"],
        ["<code>...\\animations\\</code>", "Every animation of a weapon / machine class as "
         "<code>&lt;animation&gt;.glb</code>"],
        ["<code>ui\\</code>", "Item, mission item and menu icons as PNG, <code>item_icons.csv/.json</code>, the "
         "Research menu's augment icons and tier diamonds (PNG, optional SVG)"],
        ["<code>audio\\</code>", "Every sound as <code>.ogg</code> (the game's own Vorbis data, no quality loss), "
         "<code>audio_index.csv</code>, <code>dialogue\\dialogue_lines.csv</code> (every line with subtitles)"],
    ]
    mods = [
        ["<code>gz_unpack.py</code>", "Reads the <code>.tab</code>/<code>.arc</code> archives, recovers file names "
         "(Jenkins hash) and writes the index; can extract any file by name or pattern"],
        ["<code>gz_vfs.py</code>", "Lets every tool read game files from the archives by their in-game path"],
        ["<code>gz_items.py</code>", "Reads the game's ADF data files: the item list (names, hashes, stats, prices, "
         "crafting), the text table; dumps any ADF file to JSON"],
        ["<code>gz_locations.py</code>", "IDs and world coordinates of collectibles, house photos, schematic points "
         "and map markers"],
        ["<code>gz_textures.py</code>", "<code>.ddsc</code> + <code>.atx</code> textures to PNG (BC1-BC7), stitches "
         "the world map"],
        ["<code>gz_terrain.py</code>", "The heightmap and the machine spawn maps"],
        ["<code>gz_weapons.py</code>, <code>gz_attachments.py</code>, <code>gz_machines.py</code>, "
         "<code>gz_world.py</code>", "3D models to glTF (<code>.glb</code>), with skeletons and skinning"],
        ["<code>gz_anims.py</code>", "Animations from the Havok <code>.ban</code> files"],
        ["<code>gz_ui.py</code>, <code>gz_swfvec.py</code>", "UI icons, and vector art from the Scaleform menus as "
         "SVG / PNG"],
        ["<code>gz_audio.py</code>", "FMOD sound banks to <code>.ogg</code>, plus the dialogue lines"],
    ]
    return "".join([
        tool_head(site, "extractor", "Gen0 Extractor", "Unpacks the game's archives and exports items, textures, "
                  "3D models (with skeletons and animations), audio, the world map and location data. The weapon and "
                  "machine numbers on this wiki were read out of the game with it.", [
                      ("Folder", "<code>extractor\\</code>"),
                      ("Start", "<code>Run without building.bat</code> (needs Pillow and numpy)"),
                      ("Build", "<code>Build Gen0 Extractor.bat</code> &rarr; <code>Gen0 Extractor.exe</code> (a few "
                       "minutes)"),
                      ("Changes", "Nothing: the game folder is only read"),
                      ("First run", "UNPACK builds the file index, about an hour")]),
        "<h3>Tabs</h3><p>Tick the diamond of every sub tab you want (a main tab's diamond ticks all of its sub "
        "tabs), choose the options and press EXTRACT SELECTED. Your choices are remembered.</p>",
        table(["Tab", "Sub tabs"], [[f"<b>{a}</b>", esc(b)] for a, b in tabs], sortable=False),
        "<h3>Hotkeys</h3>",
        keytable([("Enter", "Extract selected"), ("Esc", "Stop (finished files are kept)"),
                  ("O", "Open the output folder")]),
        "<p>With <i>Skip what's already been exported</i> ticked, the next run continues where a stopped one "
        "ended.</p>",
        "<h3>What it writes (next to the .exe)</h3>",
        table(["Folder", "What"], out, sortable=False),
        "<h3>Using the models in Blender</h3>",
        ul(["<b>File &rarr; Import &rarr; glTF 2.0 (.glb)</b>. Textures are embedded (World, NPCs and Places use the "
            "shared PNGs in <code>textures\\</code> by default: keep <code>models\\</code> and <code>textures\\</code> "
            "together, or pick <i>In each model</i>).",
            "Pose rigged models in Pose Mode, not Edit Mode.",
            "Animations: open the <code>_rigged</code> model and pick an Action in the Action Editor / NLA editor. "
            "Walk / run / turn animations include the root motion; additive ones (names ending <code>_add</code>) "
            "show on top of the rest pose.",
            "A Places export is an empty at the place's centre with the models below it: set its location to 0 to "
            "bring it to the origin."]),
        "<h3>The modules (source\\)</h3><p>Every <code>gz_*.py</code> also works on its own from a command prompt, "
        "for example:</p>",
        pre("python source\\gz_audio.py export music dialogue\n"
            "python source\\gz_weapons.py export AI-76 --models rigged\n"
            "python source\\gz_attachments.py export Scopes --quality 5\n"
            "python source\\gz_world.py export manmade/props --textures embed\n"
            "python source\\gz_world.py places churches"),
        "<p>The first lines of each file list all its commands.</p>",
        table(["Module", "What it does"], mods, sortable=False, cls="compact"),
    ])


# ---------------------------------------------------------------------------------------------------------------
def tools_vr(site):
    files = [
        ["<code>mod\\</code>", "What Install copies: <code>xinput9_1_0.dll</code> (the console with VR), "
         "<code>openvr_api.dll</code> (Valve) and, optionally, <code>nvngx_dlss.dll</code> (NVIDIA)"],
        ["<code>console\\</code>", "The console without VR (the default for \"uninstall to the console without VR\")"],
        ["<code>original\\</code>", "The plain console v1.5.0 (used when <code>console\\</code> isn't there)"],
        ["<code>backup\\before-install\\</code>", "What was in the game folder before the first install"],
        ["<code>backup\\vr-settings\\GZVR.txt</code>", "Your VR settings, with \"Keep my VR settings\""],
        ["<code>source\\misc\\settings.json</code>, <code>settings_vr.json</code>", "Your no-VR and VR game settings "
         "(not in the GitHub repository)"],
        ["<code>mod-source\\</code>, <code>mod-build\\</code>", "The mod's source (a " + repo("gen0-console") +
         " checkout) and its build"],
        ["<code>Gen0 VR settings.json</code>", "The tab, game folder and choices"],
    ]
    return "".join([
        tool_head(site, "vr", "Gen0 VR", "Installs or uninstalls the SteamVR mod (the " +
                  tool(site, "Gen0 Console", "F1 console") + " with VR) in the game folder, with a backup of what "
                  "was there, and switches VR on or off.", [
                      ("Folder", "<code>vr\\</code>"),
                      ("Start", "<code>Run without building.bat</code> (Python 3, nothing else)"),
                      ("Build", "<code>Build Gen0 VR.bat</code> &rarr; <code>Gen0 VR.exe</code> (the mod, the plain "
                       "console and the game settings go inside the .exe)"),
                      ("Changes", "The game folder (and, if you tick it, the game's <code>settings.json</code>)"),
                      ("Game", "Steam version only")]),
        "<h3>VR MOD tab</h3>",
        ul(["Shows what is in the game folder now and what is ready to install.",
            "<b>Turn VR on</b> + mode: <b>true stereo</b> (default), <b>alternate eye</b> or <b>flat screen</b>. "
            "Written to <code>GZVR.txt</code> when installing; once the mod is in, a change is saved right away "
            "(the game reads the file every second, even while it runs).",
            "<b>INSTALL</b> copies the DLLs from <code>mod\\</code> into the game folder. <i>Use the VR game "
            "settings</i> also copies <code>settings_vr.json</code> over the game's <code>settings.json</code> "
            "(the replaced one goes to <code>backup\\</code>).",
            "<b>UNINSTALL</b> leaves one of these in the game folder: what was there before the first install, the "
            "console without VR, or no console at all. Everything else the mod left goes too "
            "(<code>openvr_api.dll</code>, <code>nvngx_dlss.dll</code>, <code>GZVR.txt</code>, "
            "<code>GZTerrainExperiment.ini</code>, <code>GZWatch.txt</code>, old <code>.ini</code> backups, crash "
            "dumps in <code>logs\\</code>); files you may have made are moved to <code>backup\\</code>. "
            "<code>GZConsoleThingy.ini</code> and the console's <code>logs\\</code> stay."]),
        "<p>The <b>GAME</b> tab picks the Generation Zero folder (Browse, or Find looks in your Steam libraries). "
        "Install and uninstall wait until the game is closed.</p>",
        "<h3>Playing in VR</h3>",
        steps(["Install with <b>Turn VR on</b> ticked.", "Start SteamVR, then the game.",
               "In the game options turn <b>Motion Blur off</b>.",
               "<kbd>F1</kbd> &rarr; Extra tab &rarr; VR: 3D on/off, recenter, eye distance. <kbd>F7</kbd> recenters. "
               "A Detail Level (LOD) of about 6 looks right."]),
        "<p>After a game update, uninstall if the game crashes at start. More on the VR mode on the " +
        tool(site, "Gen0 Console", "console page") + ".</p>",
        "<h3>Hotkeys</h3>",
        keytable([("I", "Install"), ("U", "Uninstall"), ("V", "VR on / off"), ("G", "Open the game folder")]),
        "<h3>Building the mod</h3><p><code>Build VR mod.bat</code> builds <code>mod-source\\</code> twice with Visual "
        "Studio Build Tools 2022 (C++) and CMake: with VR into <code>mod-build</code> &rarr; <code>mod\\</code>, and "
        "without VR (<code>GZ_VR=OFF</code>) into <code>console-build</code> &rarr; <code>console\\</code>. It doesn't "
        "copy anything into the game folder: install with Gen0 VR.</p>",
        "<h3>Files (next to the program)</h3>",
        table(["File", "What"], files, sortable=False),
    ])


# ---------------------------------------------------------------------------------------------------------------
def tools_hub(site):
    rows = [
        ["<code>toolexe\\Gen0 Modder.exe</code>", "<code>Build Gen0 Modder.bat</code>"],
        ["<code>toolexe\\Gen0 Editor.exe</code>", "<code>Build Gen0 Editor.bat</code>"],
        ["<code>toolexe\\Gen0 Extractor.exe</code>", "<code>Build Gen0 Extractor.bat</code>"],
        ["<code>toolexe\\Gen0 VR.exe</code>", "<code>Build Gen0 VR.bat</code>"],
    ]
    return "".join([
        tool_head(site, "hub", "Gen0 Hub", "The Tools Hub: one game-styled window with a LAUNCH button for each "
                  "Gen0 tool.", [
                      ("Folder", "<code>hub\\</code>"),
                      ("Start", "<code>Run without building.bat</code> (Python 3, nothing else)"),
                      ("Build", "<code>Build Gen0 Hub.bat</code> &rarr; <code>Gen0 Hub.exe</code>"),
                      ("Tools go in", "<code>toolexe\\</code> next to the hub")]),
        "<p>Build each tool as usual and put its .exe in <code>toolexe\\</code>. These four are always listed:</p>",
        table(["Put here", "Made by"], rows, sortable=False),
        ul(["When a tool's .exe isn't in <code>toolexe\\</code>, the hub runs that tool's <code>Run without "
            "building.bat</code> from its own folder instead (<code>..\\modder</code>, <code>..\\editor</code> and "
            "so on, as laid out in the repository); the card shows which one it will use. A tool with neither is "
            "greyed out.",
            "Any other .exe in <code>toolexe\\</code> gets a card too, and new files show up within a couple of "
            "seconds.",
            "A tool started from <code>toolexe\\</code> makes its settings, log, <code>dropzone\\</code> and "
            "<code>backup\\</code> there. To keep a tool's current settings, copy its <code>&lt;tool&gt; "
            "settings.json</code> into <code>toolexe\\</code> along with the .exe.",
            "SETTINGS tab: <b>Close the hub</b> (default) as soon as a tool starts, or <b>Keep the hub open</b>.",
            "The " + tool(site, "Gen0 Map Editor") + " has a hub card too: the hub starts it through "
            "<code>Run without building.bat</code> in " + repo("gen0-dlc") + "."]),
        keytable([("1-9", "Launch the tool on that card"), ("K", "Keep the hub open on / off"),
                  ("O", "Open the toolexe folder")]),
    ])


def tools_map(site):
    return "".join([
        tool_head(site, "map", "Gen0 Map", "The Gen0 Editor's MAP tab as a web page of its own, without the "
                  "savegame features: collectibles, schematics, house photos, safehouses, control points, beacons, "
                  "every map location and (with <i>Extra Locations</i>) the placed loot, with filters by category "
                  "and region. This wiki's " + '<a href="~/map/index.html">interactive map</a>' + " is the same "
                  "page.", [
                      ("Repository", repo("gen0-mapping")),
                      ("Runs in", "Any browser; a plain static site (GitHub Pages)"),
                      ("Locally", "<code>Open map.bat</code>, or <code>python -m http.server</code> in the folder")]),
        keytable([("Scroll", "Zoom"), ("Drag", "Pan"), ("Click", "A marker's name and coordinates (click the "
                  "coordinates to copy them)"), ("0", "Whole map"), ("B", "Region borders"), ("F", "Filters panel"),
                  ("S", "Icon size"), ("G", "Game icons"), ("Esc", "Close")]),
    ])


# ===============================================================================================================
# modding/console.html - the F1 console and the SteamVR mod
# ===============================================================================================================
def build_console(site):
    from wiki.site import infobox
    lead = ("<p><b>gen0-console</b> is a Generation Zero mod menu that opens in the game with <kbd>F1</kbd>. It is a "
            "fork of <a href=\"https://github.com/j4ceee/gz-console-thingy\">Generation Zero Console Thingy</a> by "
            "jacee (MIT licence): everything the original console does still works, and the fork adds a loot "
            "highlight, longer render distance, a lock-height float, more saved toggles, and an experimental "
            "<b>SteamVR mode</b>.</p>")
    box = infobox("Gen0 Console", [
        ("Repository", repo("gen0-console")),
        ("File", "<code>xinput9_1_0.dll</code>"),
        ("Goes in", "The game folder, next to <code>GenerationZero_F.exe</code>"),
        ("Opens with", "<kbd>F1</kbd>"),
        ("Based on", "gz-console-thingy v1.5.0"),
        ("Licence", "MIT"),
        ("Game build", "Steam (new features); Store build: original features only"),
        ("Installer", tool(site, "Gen0 VR")),
        ("Built with", "ImGui, MinHook, meow-hook, OpenVR headers"),
    ], subtitle="F1 mod menu with an experimental SteamVR mode")
    body = [
        note("This mod modifies game memory and may lead to instability or crashes. Use it at your own risk and "
             "back up your saves.", "warn"),
        console_install(site),
        console_hotkeys(site),
        console_tabs(site),
        console_ini(site),
        console_vr(site),
        console_files(site),
        console_build(site),
        console_credits(site),
    ]
    page(site, CONSOLE, "Console & VR mod", body, "console", lead,
         "The Generation Zero F1 console (gen0-console): every feature by tab, hotkeys, the SteamVR mode, "
         "installing with Gen0 VR and building it.", infobox_html=box, kind="Mod · DLL")


def console_install(site):
    return "".join([
        bar("Installing", id="install"),
        "<h3>With Gen0 VR (recommended)</h3>",
        "<p>" + tool(site, "Gen0 VR") + " copies the console into the game folder, keeps a backup of what was "
        "there, and can uninstall it again cleanly. Untick <b>Turn VR on</b> for just the console. Uninstall can "
        "leave what was there before, the console without VR, or no console at all.</p>",
        "<h3>By hand</h3>",
        steps(["Build the DLL (below) or take <code>xinput9_1_0.dll</code> from a release.",
               "Copy <code>xinput9_1_0.dll</code> into the Generation Zero folder, next to "
               "<code>GenerationZero_F.exe</code>.",
               "Start the game and open the console with <kbd>F1</kbd>."]),
        "<p>Linux / Steam Deck: add <code>WINEDLLOVERRIDES=\"xinput9_1_0.dll=n,b\" %command%</code> to the game's "
        "launch options. To go back to the original console, put the original console's "
        "<code>xinput9_1_0.dll</code> back.</p>",
    ])


def console_hotkeys(site):
    rows = [("F1", "Toggle the console", "ToggleUIKey"), ("F2", "Teleport to where you aim", "TeleportToAimKey"),
            ("F3", "Hide the HUD", "HideHUDKey"), ("F4", "Third person", "ThirdPersonKey"),
            ("F5", "Highlight nearby loot (fork)", "LootHighlightKey"), ("F6", "Ghost mode on / off (fork)",
                                                                        "GhostModeKey"),
            ("F7", "Recenter the VR view (fork, VR build)", "VRRecenterKey"),
            ("F8", "Lock height on / off (fork)", "LockHeightKey")]
    return (bar("Hotkeys", id="hotkeys") +
            "<p>All hotkeys can be changed in <b>Settings &rarr; Hotkeys</b> (Reset to Defaults puts back the F keys "
            "below). The last column is the key's name in <code>GZConsoleThingy.ini</code>.</p>" +
            table(["Key", "What it does", "ini key"], [[keys(k), esc(w), f"<code>{i}</code>"] for k, w, i in rows],
                  sortable=False, cls="compact"))


# the console's tabs: tab -> [(group, [feature (html)])]; "fork" marks this fork's additions
CONSOLE_TABS = [
    ("Player", [
        ("Health", ["Player invulnerable (all damage)", "Revive player"]),
        ("Stamina", ["Infinite stamina (sprinting, jumping)"]),
        ("Inventory", ["Unlimited carry weight", "Unlimited storage size", "Infinite ammo",
                       "Infinite deployables &amp; consumables",
                       "Unlimited resources (nothing used when building or crafting)"]),
        ("HUD", ["Hide HUD (<kbd>F3</kbd>)"]),
        ("Camera", ["Third person (<kbd>F4</kbd>; not while controlling a machine or vehicle)", "Reset camera"]),
        ("Map", ["Enable fast travel anywhere"]),
        ("Machine interaction", ["Bullet damage multiplier (0.1 to 100, damage bullets do to machines)",
                                 "Undetectable by machines", "Faction"]),
        ("Base building", ["Unrestricted building (no collision checks, no building limits)",
                           "Command tokens (for claiming control points)"]),
        ("Vehicles", ["Infinite vehicle fuel", "Vehicle acceleration &amp; speed multiplier",
                      "No air resistance (much higher top speed)"]),
        ("Skills &amp; experience", ["Player level", "Experience", "Skill points"]),
        ("Miscellaneous", ["First-person shadow (change clothes once for it to show)",
                           "Ignore deep water (travel underwater)",
                           "Ghost mode: float through everything without collision (<kbd>F6</kbd>; teleporting also "
                           "ends it)"]),
    ]),
    ("Machines", [
        ("Spawning", ["Spawn any machine at your aim position, by category (host only; experimental)",
                      "Force spawn machines (also at positions the game wouldn't pick)",
                      "Spawn machines as friendly (instantly hacked)",
                      "Spawned machines disappear when you leave the area (intended)"]),
        ("Hacking", ["Hacking always succeeds", "Unlimited hacking time",
                     "Advanced hacking (hacked machines always attack other enemies)"]),
        ("Targeted machine", ["Invulnerable", "Kill", "Health (%)", "Faction (hostile to every other faction)",
                              "Control targeted machine (play as the machine)"]),
        ("Controlled machine", ["Unlimited signal strength", "Control machine on hack", "Release control",
                                "Invulnerable", "Kill", "Undetectable by other machines",
                                "Third-person camera distance (also the mouse wheel)"]),
    ]),
    ("World", [
        ("Events", ["Block automatic event scheduling", "Select an event; shows the currently active ones"]),
        ("World time", ["Mirror real time (your system clock)", "Time of day", "Pause time", "Time scale"]),
        ("Spawning", ["Spawn objects at your aim position by category, or any resource by tag / type ID "
                      "(experimental; some stay until you exit to the menu). For more vehicles spawn a "
                      "<i>Vehicle Station</i> from <i>Buildings &amp; Props</i>."]),
        ("Physics", ["World gravity (in G)", "Player gravity (in G)", "Zero / reset gravity"]),
        ("Teleportation", ["Teleport to X / Y / Z, use current position", "Teleport to aim position (<kbd>F2</kbd>)",
                           "Predefined locations"]),
        ("Weather", ["Control weather: cloud density, transition time, manual downpour (rain without clouds), "
                     "downpour, snow ratio (above 0.5 is snow), ground snow, snow randomness, ground wetness, "
                     "lightning, cloud height and range, wind strength (2 to 8 works best)"]),
        ("GFX &amp; filters", ["The game's graphics filter presets, Clear filter"]),
    ]),
    ("Extra (fork)", [
        ("Loot", ["Highlight nearby loot (<kbd>F5</kbd>): the game's own pickup outline on every lootable item and "
                  "container within 5 to 50 m (default 7.5 m); looted containers are skipped"]),
        ("Render distance", ["Extra load range (0 to +3,000 m): towns, buildings and props stream in from further "
                             "away (stock 250-500 m per location; the physics body limit is raised at game start)",
                             "Terrain detail distance (game default 256 m)",
                             "Detail level (LOD): 0 = game setting, 3 to 8 goes past the game's maximum (about 6 in "
                             "VR)"]),
        ("Lock height", ["Float the player at a fixed height (<kbd>F8</kbd>); the height is editable. Not saved."]),
        ("VR (experimental)", ["Enable VR, 3D on / off, recenter view, eye distance (1.00 = your headset's IPD), "
                               "keep depth of field, sharpening",
                               "Advanced: head-tracked gun, gun uses headset FOV, mirrored head turns (flip Z), eye "
                               "lag"]),
    ]),
    ("Settings", [
        ("Hotkeys", ["Rebind all eight hotkeys, reset to defaults"]),
        ("Console", ["Quicker startup (loads the main menu during the splash screens)", "UI font scale",
                     "Developer mode (debug info and unfinished features)", "Show the console hint"]),
    ]),
]


def console_tabs(site):
    out = [bar("Features by tab", id="tabs"),
           "<p>The console has five tabs. Most switches act on the running game at once; the ones listed under "
           "<a href=\"#ini\">saved settings</a> are remembered between sessions.</p>", '<div class="cols">']
    for tab_name, groups in CONSOLE_TABS:
        items = "".join(f"<h4>{g}</h4>" + ul(feats) for g, feats in groups)
        out.append(f'<div class="panel mtab"><h3 id="tab-{slug(tab_name)}">{esc(tab_name)}</h3>{items}</div>')
    out.append("</div>")
    return "".join(out)


def console_ini(site):
    rows = [
        ("Player invulnerable", "PlayerInvulnerable"), ("Infinite stamina", "InfiniteStamina"),
        ("Undetectable by machines", "Undetectable"), ("Ignore deep water", "IgnoreDeepWater"),
        ("No air resistance", "NoAirResistance"), ("Vehicle acceleration & speed", "VehicleSpeedMultiplier"),
        ("Highlight nearby loot / radius", "LootHighlight, LootHighlightRadius"),
        ("Extra load range", "RenderDistanceExtra"), ("Detail level (LOD)", "LodLevel"),
    ]
    return (bar("Saved settings", id="ini") +
            "<p>The console keeps its settings in <code>GZConsoleThingy.ini</code> in the game folder. This fork "
            "added these toggles to it (invulnerability, stamina and undetectable are put back after a respawn or "
            "a save load). <i>Unlimited resources</i> and <i>Infinite vehicle fuel</i> already had ini keys, and now "
            "really write them.</p>" +
            table(["Setting", "ini key"], [[esc(a), f"<code>{esc(b)}</code>"] for a, b in rows], sortable=False,
                  cls="compact"))


def console_vr(site):
    cfg = [
        ("on", "1 = VR on, 0 or no file = off"),
        ("mode", "<code>stereo</code> (true stereo, Gen0 VR's default), <code>aer</code> (alternate eye) or "
                 "<code>mono</code> (flat screen)"),
        ("recenter", "Re-centres the view"),
        ("flipz", "Head-turn axis convention; 0 is the correct one"),
        ("lag", "Eye lag in frames for alternate-eye mode; 1 is correct (the picture runs one camera update "
                "behind), 0 swaps the eyes"),
        ("gun", "First-person gun follows the head pose: 2 (default)"),
        ("dof", "0 (default) turns depth of field off in VR, 1 keeps it"),
        ("taaeye", "Per-eye anti-aliasing history: 2 (default)"),
        ("dlss", "1 = NVIDIA DLSS upscaling per eye with <code>mode=stereo</code> (work in progress; needs "
                 "<code>nvngx_dlss.dll</code>)"),
        ("simreuse", "1 = the right eye skips view-independent passes already run for the left (opt-in)"),
    ]
    return "".join([
        bar("SteamVR mode", id="vr"),
        "<p>Plays Generation Zero in a SteamVR headset (developed on a Steam Frame). The mouse still aims; your "
        "head looks around.</p>",
        ul(["<b>Head tracking</b> on the game camera.",
            "<b>True stereo</b>: the scene is drawn twice per frame, once per eye, each with its own off-centre "
            "projection. The older alternate-eye mode (one eye per frame) is still there.",
            "<b>First-person gun</b> follows the head and uses the headset field of view, so it is life-size and "
            "in 3D, and sights line up when aiming.",
            "<b>HUD</b> (icons, prompts, menus) is carried into both eyes.",
            "<b>Depth of field</b> is off in VR (it blurred the gun when aiming).",
            "<b>Per-eye TAA history</b> so the game's anti-aliasing doesn't blend the two eyes (work in "
            "progress)."]),
        "<h3>Setting it up</h3>",
        steps(["Install with " + tool(site, "Gen0 VR") + " and <b>Turn VR on</b> (or by hand: put "
               "<code>openvr_api.dll</code> from <a href=\"https://github.com/ValveSoftware/openvr\">Valve's OpenVR "
               "SDK</a>, <code>bin/win64</code>, next to the game's exe).",
               "Start SteamVR, then the game.",
               "In the game: <b>Motion Blur off</b>. In the console: Extra tab &rarr; VR &rarr; Enable VR.",
               "<kbd>F7</kbd> recenters. Set Extra &rarr; Render Distance &rarr; Detail Level to about 6."]),
        "<h3>GZVR.txt</h3>",
        "<p>The VR settings live in <code>GZVR.txt</code> in the game folder. The console writes it from its Extra "
        "tab and the game re-reads it every second. A few of its keys, as the change notes describe them (the full "
        "list is at the top of <code>src/game/custom/vr.h</code>):</p>",
        table(["Key", "What it does"], [[f"<code>{k}</code>", v] for k, v in cfg], sortable=False, cls="compact"),
        note("Alternate-eye 3D needs Motion Blur off and anti-aliasing on plain FXAA, because TAA and motion blur "
             "mix the eyes. The DLSS SDK is not in the repository (licence).", "info"),
    ])


def console_files(site):
    rows = [
        ["<code>xinput9_1_0.dll</code>", "The console itself"],
        ["<code>GZConsoleThingy.ini</code>", "Its settings and hotkeys"],
        ["<code>GZVR.txt</code>", "VR settings (VR build only)"],
        ["<code>openvr_api.dll</code>, <code>nvngx_dlss.dll</code>", "Valve's OpenVR runtime, NVIDIA DLSS (optional)"],
        ["<code>logs\\</code>", "The console's log, and its own crash dumps <code>gz_crash_*.dmp</code> (with all "
         "thread stacks)"],
        ["<code>GZTerrainExperiment.ini</code>", "Research hooks for terrain detail; a missing file or 0 has no effect"],
        ["<code>GZWatch.txt</code>", "Developer memory watchpoint (<code>addr=&lt;hex&gt;</code>); "
         "<code>addr=0</code> or deleting the file clears it"],
    ]
    return (bar("Files in the game folder", id="files") +
            "<p>Everything the console and its VR mode use or write, all next to "
            "<code>GenerationZero_F.exe</code>. Gen0 VR's Uninstall clears the VR and research files and the crash "
            "dumps, leaves the <code>xinput9_1_0.dll</code> you choose (or none), and keeps "
            "<code>GZConsoleThingy.ini</code> and the console's <code>logs\\</code>.</p>" +
            table(["File", "What"], rows, sortable=False) +
            note("The game's own crash reporter writes its dumps to <code>%LOCALAPPDATA%\\CrashRpt\\"
                 "UnsentCrashReports\\</code> and deletes them when its window closes; the console's own dumps in "
                 "<code>logs\\</code> stay.", "info", "Crash dumps"))


def console_build(site):
    return "".join([
        bar("Building from source", id="build"),
        "<p>Needs Visual Studio 2022 (or the Build Tools, C++ workload) and CMake 3.16+. The dependencies (ImGui, "
        "MinHook, meow-hook, FW1FontWrapper) are in <code>deps/</code>, so there are no submodules.</p>",
        pre('cmake -B build -G "Visual Studio 17 2022"\ncmake --build build --config Release'),
        ul(["The DLL ends up in <code>build/out/Release/Release/</code>.",
            "A post-build step copies it to <code>C:/Program Files (x86)/Steam/steamapps/common/GenerationZero/</code>; "
            "if your game is elsewhere (another Steam library or drive), point it there with "
            "<code>-DGZ_GAME_DIR=\"D:/Steam/steamapps/common/GenerationZero\"</code>, or turn the copy off with "
            "<code>-DGZ_COPY_TO_GAME=OFF</code>. The copy fails while the game is running.",
            "<code>-DGZ_VR=OFF</code> builds the console without VR: no OpenVR, no <code>GZVR.txt</code>, no VR "
            "hooks or DLSS, and the VR controls are hidden. Everything else is the same.",
            "Gen0 VR's <code>Build VR mod.bat</code> builds both versions from a <code>mod-source</code> checkout."]),
        "<p>The repository's <code>docs/CHANGES.md</code> lists every change against gz-console-thingy v1.5.0 in "
        "detail, and <code>docs/RENDERER.md</code> holds the reverse-engineering notes on the game's renderer "
        "(frame structure, cameras, passes, terrain, crash signatures) for anyone writing a mod like this.</p>",
    ])


def console_credits(site):
    return (bar("Credits", id="credits") +
            ul(["Original console: <a href=\"https://github.com/j4ceee\">jacee</a> "
                "(<a href=\"https://github.com/j4ceee/gz-console-thingy\">gz-console-thingy</a>), based on "
                "<a href=\"https://github.com/aaronkirkham/jc4-console-thingy\">jc4-console-thingy</a> by Aaron "
                "Kirkham",
                "This fork: <a href=\"https://github.com/The-Bewwy-2510\">The-Bewwy-2510</a>",
                "Built with <a href=\"https://github.com/ocornut/imgui\">ImGui</a>, "
                "<a href=\"https://github.com/TsudaKageyu/minhook\">MinHook</a>, "
                "<a href=\"https://github.com/magicalcookie/meow-hook\">meow-hook</a> and "
                "<a href=\"https://github.com/ValveSoftware/openvr\">OpenVR</a> headers",
                "Fonts: Material Design Icons (Apache 2.0), Roboto (SIL OFL 1.1)"]))


# ===============================================================================================================
# modding/map-editor.html - the Gen0 Map Editor (gen0-dlc)
# ===============================================================================================================
def build_map_editor(site):
    from wiki.site import infobox
    lead = ("<p>The <b>Gen0 Map Editor</b> shows every object placed in the Generation Zero world in 3D. You can "
            "select, move, turn, duplicate and delete objects, then build the changed location files into a "
            "dropzone mod and install or uninstall it in the game, with backups. It is a Godot 4 (C#) program laid "
            "out like Blender, with a Rendered view of the game's own models, ground, roads, plants and "
            "decals.</p>")
    box = infobox("Gen0 Map Editor", [
        ("Repository", repo("gen0-dlc")),
        ("Engine", "Godot 4.7.2 .NET (C#)"),
        ("Renderer", "Forward+ / Vulkan, OpenGL fallback"),
        ("Install", "Setup program (Inno Setup)"),
        ("Your data", "<code>%LOCALAPPDATA%\\Gen0 Map Editor</code>"),
        ("Makes", "A dropzone mod (changed location files)"),
        ("Needs", tool(site, "Dropzone", "dropzone launch options")),
        ("Hub card", "Gen0 Map Editor"),
    ], subtitle="3D editor for the objects placed in the world")
    body = [
        maped_install(site),
        maped_workflow(site),
        maped_controls(site),
        maped_kinds(site),
        maped_props(site),
        maped_build(site),
    ]
    page(site, MAPED, "Map editor", body, "mapeditor", lead,
         "The Gen0 Map Editor: edit the objects placed in Generation Zero's world in 3D and build them into a "
         "dropzone mod. Install, controls, object kinds and building.", infobox_html=box, kind="Tool · Windows")


def maped_install(site):
    return "".join([
        bar("Installing and starting", id="install"),
        ul(["<b>Install</b> with <code>build\\installer\\Gen0 Map Editor Setup &lt;version&gt;.exe</code> (made by "
            "<code>editor\\Build installer.bat</code>). Your changes, the world cache, builds and backups are kept "
            "in <code>%LOCALAPPDATA%\\Gen0 Map Editor</code>.",
            "<b>Start</b> it from the Start menu / desktop shortcut, or with <code>Run without building.bat</code> "
            "(also what the Tools Hub uses): it starts the installed program, or the project in Godot when it isn't "
            "installed.",
            "The first time, it asks where Generation Zero is installed (the folder with <code>archives_win64</code> "
            "in it), and loading the world reads every location in the game, which takes about a minute. Later "
            "starts use the world cache.",
            "Coming from the old browser-based version (0.1 - 0.6, Python)? <code>Remove old web version.bat</code> "
            "clears out what it left, after moving your changes, backups and the installed-mod record to the new "
            "program."]),
        note("The game folder is only read. <b>Build</b> writes the mod into a dropzone folder and <b>Install</b> "
             "copies it into the game's dropzone, which needs the " + tool(site, "Dropzone", "dropzone launch options") +
             ".", "info"),
    ])


def maped_workflow(site):
    return "".join([
        bar("Workflow", id="workflow"),
        steps(["Go to the place you want to change in the 3D viewport (orbit, pan and zoom, or walk mode), or "
               "search for a location by name (for example <i>iboholmen</i>).",
               "Select objects (click, box select) and move (<kbd>G</kbd>), rotate (<kbd>R</kbd>), duplicate "
               "(<kbd>Shift+D</kbd>) or delete (<kbd>X</kbd>) them, or type exact values in the properties panel. "
               "<b>Add</b> puts in a static model (building, rock, prop), an object (light, AI blocker, lootable, "
               "decal ...) or a whole place (church, farm, bunker ...).",
               "Check the change list on the right; <kbd>Ctrl+Z</kbd> / <kbd>Ctrl+Shift+Z</kbd> undo and redo.",
               "<b>Build the mod</b>: the changed location files are written as a dropzone mod.",
               "<b>Install into the game</b> (with backups), start the game with the dropzone launch options, and "
               "<b>Uninstall</b> to go back."]),
        "<p>Every object has an <code>_object_id</code>; saves remember looted, destroyed and collected objects by "
        "it, and copies get new ones. So a duplicated loot crate is a new crate as far as your save is "
        "concerned.</p>",
    ])


def maped_controls(site):
    rows = [
        ("Middle mouse", "Orbit"), (("Shift", "Middle mouse"), "Pan"), (("Ctrl", "Middle mouse"), "Zoom (or wheel)"),
        (("Numpad 1", "3", "7"), "Front / side / top view"), ("Numpad .", "Frame the selection"),
        (("Shift", "`"), "Walk mode"), ("Click", "Select (Shift adds, Ctrl toggles)"),
        (("B",), "Box select (or drag)"), ("A", "Select all in view"), (("Alt", "A"), "Deselect all"),
        (("Ctrl", "I"), "Invert selection"), ("H", "Hide"), (("Shift", "H"), "Hide the rest"),
        (("Alt", "H"), "Show hidden"),
        ("G", "Move; then X / Y / Z for an axis (Shift for a plane), type a value, Ctrl to snap"),
        ("R", "Rotate (R X / R Y tilt)"), (("Shift", "D"), "Duplicate"), (("X",), "Delete (or Delete)"),
        (("Ctrl", "Z"), "Undo"), (("Ctrl", "Shift", "Z"), "Redo"), ("T", "Tool bar"), ("N", "Properties panel"),
    ]
    return (bar("Controls", id="controls") +
            "<p>The keys follow Blender. Property fields take Blender-style sums such as <code>+10</code>, "
            "<code>*2</code> or <code>12+3</code>.</p>" + keytable(rows))


def maped_kinds(site):
    kd = site.data("kinds")
    cats = {c["id"]: c for c in kd["categories"]}
    count = {}
    for v in kd["kinds"].values():
        count[v["cat"]] = count.get(v["cat"], 0) + 1
    crow = [[f'<b>{esc(c["name"])}</b>', esc(c["about"]), count.get(c["id"], 0)] for c in kd["categories"]]
    rows, flt = [], []
    for cls, v in sorted(kd["kinds"].items(), key=lambda kv_: (list(cats).index(kv_[1]["cat"]), kv_[1]["name"])):
        rows.append([esc(v["name"]), f"<code>{esc(cls)}</code>", esc(cats.get(v["cat"], {}).get("name", v["cat"])),
                     esc(v["about"])])
        flt.append(v["cat"])
    comps = [[f"<code>{esc(k)}</code>", esc(v)] for k, v in kd["components"].items()]
    return "".join([
        bar("Kinds of objects", f"{len(kd['kinds'])} kinds", id="kinds"),
        "<p>Every placed object has a kind (its engine class). The editor gives each one a plain name, a category "
        "and a description; its list has " + str(len(kd["kinds"])) + " kinds in " + str(len(kd["categories"])) +
        " categories:</p>",
        table(["Category", "What's in it", "Kinds"], crow, num={2}),
        "<p>The full list. Filter by category, or search by name or class (e.g. <code>CLootCrate</code>):</p>",
        filterbar("mkinds", "Filter kinds...", [(c["id"], c["name"]) for c in kd["categories"]]),
        ftable("mkinds", ["Name", "Class", "Category", "What it is"], rows, flt, cls="compact"),
        "<h3>Components</h3><p>Small records inside objects:</p>",
        table(["Component", "What it is"], comps, sortable=False, cls="compact"),
    ])


def maped_props(site):
    props = site.data("kinds")["props"]
    rows = [[f"<code>{esc(k)}</code>", esc(v)] for k, v in props.items()]
    return (bar("Object properties", f"{len(props)} properties", id="props") +
            "<p>What the properties shown in the properties panel mean, as the editor explains them. A few of the "
            "most useful: <code>_object_id</code> (saves remember looted / destroyed / collected objects by it), "
            "<code>filename</code> (the model), <code>world</code> (position and rotation).</p>" +
            f'<details class="mdet"><summary>Show all {len(props)} properties</summary>' +
            filterbar("mprops", "Filter properties...") + ftable("mprops", ["Property", "Meaning"], rows,
                                                                 [""] * len(rows), cls="compact") + "</details>")


def maped_build(site):
    return "".join([
        bar("Building from source", id="build"),
        "<p>Needs the .NET 8 SDK or newer, Godot 4.7.2 .NET with its export templates, and Inno Setup 6. "
        "<code>editor\\Build installer.bat</code> does three steps:</p>",
        steps(["Compiles the C# code (<code>dotnet build App\\Gen0MapEditor.csproj -c ExportRelease</code>).",
               "Exports the Godot app to <code>build\\app\\Gen0 Map Editor.exe</code>.",
               "Makes the setup with Inno Setup into <code>build\\installer</code>."]),
        "<p>To run it from source, open <code>editor\\App</code> in Godot, or run "
        "<code>Godot_v4.7.2-stable_mono_win64.exe --path App</code>.</p>",
        "<h3>Project layout</h3>",
        table(["Folder", "What"], [
            ["<code>editor/Core/</code>", "<b>Gen0.Core</b>: the file formats and editing logic in C# with no Godot "
             "dependency: archives, SARC containers, RTPC placement data, static models (<code>.mdic</code>) and their "
             "collision (the location's <code>.pfs</code>, a Havok 2016 tagfile), the world scan and cache, terrain, "
             "edits / undo / redo / change list, build into dropzone, install / uninstall"],
            ["<code>editor/App/</code>", "The app (Godot 4.7.2 .NET): menus, tool bar, 3D viewport, outliner, change "
             "list, properties, status bar"],
            ["<code>editor/Check/</code>", "Command-line checks and research: <code>dotnet run --project Check -- "
             "formats|scan|terrain|build ...</code>"],
            ["<code>editor/installer/</code>", "The Inno Setup script"],
            ["<code>data/</code>", "What the program reads besides the game: the location list, ground heights, "
             "plain names of every kind of object (<code>kinds.json</code>), every model's path, and "
             "<code>data/tiles</code> (the map pictures for the Map view)"],
        ], sortable=False),
        "<h3>Test switches</h3>",
        table(["Environment variable", "What it does"], [
            ["<code>GEN0_ROOT=&lt;folder&gt;</code>", "Keeps the cache, changes and builds there instead"],
            ["<code>GEN0_SHOT=&lt;png&gt;</code>", "Takes a screenshot after loading and quits"],
            ["<code>GEN0_TEST=move|click|static</code>", "With GEN0_SHOT: first moves an object (G X 10 Enter), clicks "
             "objects, or moves / copies / deletes static models"],
        ], sortable=False),
    ])


# ===============================================================================================================
# modding/data.html - item IDs, hashes and the data files
# ===============================================================================================================
def build_data(site):
    lead = ("<p>The numbers you need when you edit a savegame or game files by hand: the item ID of every weapon, "
            "attachment, ammo type, augment, skin, item and material (one ID per quality), and the hashes the save "
            "uses for regions, map locations, safehouses, skills, research tasks, challenges and statistics. Everything is "
            "generated from the same extracted game data as the rest of the wiki. Click an ID to select it for "
            "copying.</p>")
    d = DataCtx(site)
    body = [
        data_quality(site),
        data_save(site),
        data_weapons(site, d),
        data_attachments(site, d),
        data_ammo(site, d),
        data_augments(site, d),
        data_skins(site, d),
        data_items(site, d),
        data_regions(site, d),
        data_locations(site, d),
        data_safehouses(site, d),
        data_skills(site, d),
        data_research(site, d),
        data_challenges(site, d),
        data_currencies_stats(site, d),
        data_files(site, d),
    ]
    page(site, DATA, "Game data & IDs", body, "data", lead,
         "Generation Zero item IDs per quality (weapons, attachments, ammo, augments, skins, items) and save hashes "
         "for regions, locations, safehouses, skills, research, challenges and statistics.", wide=True)


class DataCtx:
    """Lookups shared by the data page's tables."""

    def __init__(self, site):
        self.ids = site.data("IDs")
        self.gd = site.data("gamedata")
        self.stock = {s["h"]: s for s in site.data("stock")["stock"]}
        self.icons = site.data("icons")
        self.stats = {}
        self.exp_ammo = set()       # internal names of experimental-only ammo
        for cat, ws in site.data("stats")["player_weapons"].items():
            for name, w in ws.items():
                self.stats[norm(name)] = (cat, name, w)
                for a in w.get("ammo") or []:
                    if a.get("experimental_only"):
                        self.exp_ammo.add(a.get("internal_name"))
        # weapon ToolID -> IDs.json weapon name (attachments list the weapons they fit by ToolID)
        self.tool_ids = {w["ToolID"]: name for ws in self.ids["Weapons"].values() for name, w in ws.items()}

    # names in IDs.json and stats.json differ a little ('RACS-12' / 'RACS-12 Semi-Auto Shotgun')
    STATS_ALIASES = {"Volkov Handgun": "Volkov Pistol"}

    def weapon_stats(self, name):
        n = norm(self.STATS_ALIASES.get(name, name))
        if n in self.stats:
            return self.stats[n][2]
        for k, v in self.stats.items():
            if k.startswith(n) or n.startswith(k) or k.endswith(n):
                return v[2]
        return None

    def icon(self, site, item_id, cls="mic"):
        p = self.icons.get(str(item_id))
        return site.img("img/" + p, "", cls=cls) if p else ""


def pack_tag(pack):
    """A DLC tag for a stats.json pack name ('US Weapons Pack (DLC)'); nothing for the base game."""
    if not pack or pack.startswith("Base game"):
        return ""
    return tag(pack.replace(" (DLC)", ""), "dlc")


def qheaders(first, qs):
    """Headers with quality badges for the quality columns (raw HTML headers)."""
    return [esc(h) for h in first] + [qbadge(q, short=True) for q in qs]


def data_quality(site):
    ql = site.data("IDs")["_QualityLevels"]
    rows = []
    for k, name in ql.items():
        q = int(k)
        badge = qbadge(q) if q in QUALITY else "–"
        what = {0: "Items that only come in one quality (vision modules, ammo, augments, skins, items)",
                6: "Experimental weapons only (no attachments have it)"}.get(q, "")
        rows.append([q, badge, esc(name), esc(what)])
    return "".join([
        bar("Quality IDs", id="quality"),
        "<p>Every quality of a weapon or attachment is a <b>separate item with its own ID</b>, so changing a "
        "weapon's quality in a save means swapping its item ID for the ID of the same weapon in the other quality "
        "(the " + tool(site, "Gen0 Editor") + " does exactly that and leaves the record's timestamp, seed and ID "
        "alone). The tables below use these quality numbers:</p>",
        table(["Quality", "Badge", "Name in the files", "Notes"], rows, sortable=False, cls="compact"),
        '<p>What each quality does to damage is on the <a href="~/weapons/quality.html">quality page</a>.</p>',
    ])


def data_save(site):
    fields = [
        ("EquipmentHash", "u32", "The item ID from the tables on this page: which item this is, including its "
                                 "quality"),
        ("ID", "u32", "This record's own number in the save (unique per item you hold)"),
        ("Amount", "u32", "Stack size for ammo, items and materials"),
        ("ChildEquipment", "list", "IDs of the records attached to a weapon (attachments, augments, an applied "
                                   "skin); 0 = empty slot"),
        ("ChildEquipmentCount", "u8", "How many of those slots there are"),
        ("Seed", "u32", "Random seed of the item"),
        ("PickupTimestamp", "u64", "When it was picked up"),
        ("RefinementLevels", "u8", ""),
        ("Flags", "u8", ""),
    ]
    areas = [
        ("Inventory", "Characters[c].Inventory, PPInventorySlot, InventorySlotPreferredItem, EquipmentIDCounter"),
        ("Storage box", "Profile.SafehouseStorage"),
        ("Recycling (resource storage)", "Profile.ResourceStorage"),
        ("Vanity, skins, schematics, keys", "Profile.ItemStash"),
        ("Schematic points, research tasks", "Profile.Currencies (Name = hash, Amount)"),
        ("Skills", "Characters[c].Skills (hashes), SkillLevel, SkillPointsSpent, SkillPoints, ActiveSkill"),
        ("Challenges", "Characters[c].Challenges"),
        ("Safehouses", "PlayerSpawnPoints in Characters[c], World and Worlds[w]; the SafeHousesUnlocked statistic"),
        ("Map locations", "Worlds[w].LocationSummaries[] (LocationId = location hash, Activated, found lists)"),
        ("Collectables", "Worlds[w].Collectables"),
        ("Rival regions", "Worlds[w].RivalRegions[] (RegionHash, InsurrectionScore, Rivals[].XP / History)"),
        ("Statistics", "Characters[c].Statistics and World.Statistics (NameHash, Value)"),
        ("Missions", "MissionCampaigns"),
    ]
    return "".join([
        bar("How the save stores things", id="save"),
        "<p>A decoded save (the Gen0 Editor's EXPORT JSON) is one tree under <code>SaveData</code>. Inventory, "
        "storage and stash entries are item records with these fields (limits as the editor checks them):</p>",
        table(["Field", "Type", "What it is"], [[f"<code>{a}</code>", b, esc(c)] for a, b, c in fields],
              sortable=False, cls="compact"),
        "<p>Where each kind of progress lives (<code>c</code> = the active character, <code>w</code> = the active "
        "world slot; paths shortened):</p>",
        table(["What", "Where in the save"], [[esc(a), f"<code>{esc(b)}</code>"] for a, b in areas],
              sortable=False, cls="compact"),
        note("In older saves the <code>EquipmentIDCounter</code> must stay ahead of every record ID, so a new record "
             "needs a new, higher ID. Back up before you edit by hand.", "warn"),
    ])


# ---------------------------------------------------------------------------------------------------------------
def data_weapons(site, d):
    rows, flt, cats = [], [], []
    for cat, ws in d.ids["Weapons"].items():
        cats.append(cat)
        for name, w in ws.items():
            st = d.weapon_stats(name) or {}
            first = next((w[q] for q in "54321" if w.get(q, "N/A") != "N/A"), None)
            nick = f'<br><span class="dim small">{esc(w["Nickname"])}</span>' if w.get("Nickname") else ""
            cells = [d.icon(site, first), site.link("weapon", name) + nick,
                     f"<code>{esc(st.get('internal_name', ''))}</code>" if st.get("internal_name") else None,
                     f"<code>{esc(w['ToolID'])}</code>",
                     pack_tag(st.get("pack")) or '<span class="dim">Base</span>']
            cells += [idc(w.get(str(q))) for q in range(1, 7)]
            rows.append(cells)
            flt.append(slug(cat))
    return "".join([
        bar("Weapon IDs", f"{len(rows)} weapons", id="weapon-ids"),
        "<p>One row per weapon, one ID per quality. <b>Tool ID</b> is the weapon's number in the item list, used "
        "by the attachment table below to say what an attachment fits. The small line under each weapon is its nickname in the item list. A dash in the Q6 (Experimental) column means the "
        "weapon has no experimental version in the item list. Sort by clicking a header; filter by type:</p>",
        filterbar("mwids", "Filter by name or ID...", [(slug(c), c) for c in cats]),
        ftable("mwids", qheaders(["", "Weapon", "Internal name", "Tool ID", "Pack"], range(1, 7)), rows,
               flt, raw_headers=True, cls="compact mids"),
    ])


def data_attachments(site, d):
    rows, flt, cats = [], [], []
    for cat, atts in d.ids["Attachments"].items():
        cats.append(cat)
        for name, a in atts.items():
            fits = []
            for tid in [t.strip() for t in a["WPNCompat"].split(",") if t.strip()]:
                wn = d.tool_ids.get(tid)
                fits.append(site.link("weapon", wn) if wn else esc(tid))
            single = "0" in a
            first = a.get("0") or next((a[q] for q in "54321" if a.get(q)), None)
            cells = [d.icon(site, first), site.link("attachment", name), esc(cat), esc(a["Nickname"]),
                     '<span class="mfits">' + ", ".join(fits) + "</span>"]
            if single:
                cells += [f'{idc(a["0"])} <span class="dim small">(one quality)</span>', None, None, None, None]
            else:
                cells += [idc(a.get(str(q))) for q in range(1, 6)]
            rows.append(cells)
            flt.append(slug(cat))
    return "".join([
        bar("Attachment IDs", f"{len(rows)} attachments", id="attachment-ids"),
        "<p>Attachments come in qualities 1 to 5; vision modules have a single ID. <b>Fits</b> is the list of "
        "weapons from the item list's compatibility field (weapon Tool IDs, translated to names).</p>",
        filterbar("maids", "Filter by name, weapon or ID...", [(slug(c), c) for c in cats]),
        ftable("maids", qheaders(["", "Attachment", "Type", "Nickname", "Fits"], range(1, 6)), rows, flt,
               raw_headers=True, cls="compact mids"),
    ])


def data_ammo(site, d):
    rows, flt, groups = [], [], []
    for grp, cals in d.ids["Ammo"].items():
        groups.append(grp)
        for cal, ammo in cals.items():
            for short, h in ammo.items():
                s = d.stock.get(int(h), {})
                raw = s.get("raw", "")
                exp = raw in d.exp_ammo
                icon = site.img(s["icon"].replace("assets/", "img/", 1), "", cls="mic") if s.get("icon") else ""
                name = site.link("ammo", raw, s.get("name", short)) if raw else esc(short)
                rows.append([icon, name, esc(cal), esc(grp), f"<code>{esc(raw)}</code>" if raw else None,
                             s.get("stack"), (tag("Experimental only", "exp") if exp else ""), idc(h)])
                flt.append(slug(grp) + (" exp" if exp else ""))
    nexp = sum(1 for f in flt if f.endswith(" exp"))
    return "".join([
        bar("Ammo IDs", f"{len(rows)} ammo types", id="ammo-ids"),
        "<p>Ammo has one ID per type (no qualities). <b>Stack</b> is the most that fits in one inventory stack. "
        f"{nexp} types are marked <b>Experimental only</b>: they can only be loaded into an experimental (Q6) "
        "weapon.</p>",
        filterbar("mammo", "Filter by name, caliber or ID...", [(slug(g), g) for g in groups] + [("exp", "Experimental only")]),
        ftable("mammo", ["", "Ammo", "Caliber", "Group", "Internal name", "Stack", "", "Item ID"], rows, flt,
               cls="compact mids"),
    ])


AUG_TIERS = ["Bronze", "Silver", "Gold", "Tier 4", "Tier 5"]


def data_augments(site, d):
    rows, flt, extra = [], [], []
    for grp, augs in d.ids["Augments"].items():
        for name, tiers in augs.items():
            first = next(iter(tiers.values()))
            icon = site.img("img/augments/" + first["Augment"], "", cls="mic") if first.get("Augment") else ""
            base = re.sub(r"_q\d$", "", first["EquipmentName"])
            cells = [idc(tiers[t]["0"]) if t in tiers else None for t in AUG_TIERS]
            # tiers past Gold: in the item list, but no research tier unlocks them
            cells[3:] = [f"{c} {tag('Unused', 'unreleased')}" if c else c for c in cells[3:]]
            rows.append([icon, site.link("augment", name), esc(grp), f"<code>{esc(base)}</code>"] + cells)
            flt.append(grp.lower())
            if len(tiers) > 3:
                extra.append(name)
    return "".join([
        bar("Augment IDs", f"{len(rows)} augments", id="augment-ids"),
        "<p>Each augment tier is its own item. The internal name is the one shown plus <code>_q1</code> (Bronze), "
        "<code>_q2</code> (Silver) or <code>_q3</code> (Gold). " +
        (("The item list also has tiers past Gold for " + ", ".join(site.link("augment", n) for n in extra) +
          " (<code>_q4</code>, <code>_q5</code>), marked " + tag("Unused", "unreleased") + ": no research tier "
          "unlocks them; they are in the item list but the game never gives them out (see the augments page's "
          '<a href="~/weapons/augments.html#hidden-and-unused">hidden and unused</a> section). ') if extra else "") +
        'How each one is unlocked is on the <a href="~/weapons/augments.html">augments page</a> and under '
        '<a href="#research-hashes">research hashes</a>.</p>',
        filterbar("maug", "Filter augments...", [("primary", "Primary"), ("support", "Support")]),
        ftable("maug", ["", "Augment", "Group", "Internal name"] + AUG_TIERS, rows, flt, cls="compact mids"),
    ])


def data_skins(site, d):
    vanity = site.data("vanity")
    base = vanity["base_pack"]
    by_raw = {x["r"]: x for x in vanity["items"]}
    by_hash = {x["h"]: x for x in vanity["items"]}
    rows, flt, cats, packs = [], [], [], []
    for cat, ws in d.ids["Skins"].items():
        cats.append(cat)
        for wname, skins in ws.items():
            for sname, s in skins.items():
                img = site.img("img/skins/" + s["SkinPNG"], "", cls="mic") if s.get("SkinPNG") else ""
                v = by_raw.get(s["EquipmentName"]) or by_hash.get(int(s["0"])) or {}
                p = v.get("p")
                if p is None or p == base:
                    pack = '<span class="dim">Base</span>'
                else:
                    pack = site.link("pack", str(p))
                    if p not in packs:
                        packs.append(p)
                rows.append([img, link_any(site, ["skin"], s["EquipmentName"], sname), site.link("weapon", wname),
                             f"<code>{esc(s['EquipmentName'])}</code>", pack, idc(s["0"])])
                flt.append(slug(cat) + (" p-base" if p is None or p == base else f" p-{p}"))
    return "".join([
        bar("Weapon skin IDs", f"{len(rows)} skins", id="skin-ids"),
        "<p>Weapon skins are unlocks in the profile's item stash (shared by every character). One ID each; the "
        "internal name is the weapon's internal name plus <code>_skin_NN</code>. <b>Pack</b> is the content pack "
        f"the skin belongs to: {sum(1 for f in flt if f.endswith(' p-base'))} of the {len(rows)} are in the base game, the "
        "rest come with a DLC or other content pack, and adding one to a save without owning that pack may not "
        "work.</p>",
        filterbar("mskin", "Filter skins...", [(slug(c), c) for c in cats],
                  more=[("p", [("p-base", "Base game")] + [(f"p-{p}", (site.find("pack", str(p)) or {})
                                                            .get("title", f"Pack {p}")) for p in packs])]),
        ftable("mskin", ["", "Skin", "Weapon", "Internal name", "Pack", "Item ID"], rows, flt, cls="compact mids"),
        "<p>Item IDs for the rest of the item stash are on their own pages: "
        '<a href="~/character/apparel.html">apparel</a>, '
        '<a href="~/character/vanity.html">face paint, emotes and vehicles</a>, '
        '<a href="~/items/companion.html">companion cosmetics</a>, '
        '<a href="~/world/keys.html">keys</a> and '
        '<a href="~/items/schematics.html">schematics</a>.</p>',
    ])


def data_items(site, d):
    rows, flt, subs = [], [], []
    items = [s for s in d.stock.values() if s["g"] in ("items", "materials")]
    for s in sorted(items, key=lambda x: (x["g"], x.get("sub") or "", x["name"], x["raw"])):
        sub = s.get("sub") or "Other"
        if sub not in subs:
            subs.append(sub)
        kinds = ["material", "item"] if s["g"] == "materials" else ["item"]
        icon = site.img(s["icon"].replace("assets/", "img/", 1), "", cls="mic") if s.get("icon") else ""
        q = re.search(r"_q(\d)$", s["raw"])     # companion armour: one item per quality
        rows.append([icon, link_any(site, kinds, s["name"]), esc(s["g"].capitalize()), esc(sub),
                     qbadge(q.group(1), short=True) if q else "&ndash;",
                     f"<code>{esc(s['raw'])}</code>", s.get("stack"), idc(s["h"])])
        flt.append(f"{s['g']} s-{slug(sub)}")
    return "".join([
        bar("Item and material IDs", f"{len(rows)} items", id="item-ids"),
        "<p>Everything else that goes in the inventory: companion parts, keys and quest items, tools, lures, "
        "throwables, medical items, fuel and power, vision modules and crafting materials. Ammo is in its own "
        "table above. Items with the same name in several rows (companion armour, for example) are the qualities "
        "of one item; the internal name ends in <code>_q1</code>, <code>_q2</code> ... and <b>Q</b> shows that "
        "quality.</p>",
        filterbar("mitems", "Filter items...", [(f"s-{slug(x)}", x) for x in subs]),
        ftable("mitems", ["", "Name", "Group", "Kind", "Q", "Internal name", "Stack", "Item ID"], rows, flt,
               cls="compact mids"),
    ])


# ---------------------------------------------------------------------------------------------------------------
def region_key(name):
    """gamedata.json region name -> the wiki's region key ('Alpine Unrest' -> 'alpine')."""
    n = norm(name)
    for key, rname in REGIONS:
        if norm(rname) == n or n in norm(rname):
            return key
    return None


def data_regions(site, d):
    rows = []
    for r in d.gd["regions"]:
        key = region_key(r["name"])
        rows.append([site.link("region", key, r["name"]) if key else esc(r["name"]),
                     f"<code>{esc(key or '')}</code>", idc(r["hash"]), idc(f"0x{r['hash']:08X}")])
    hist = d.gd.get("history") or {}
    return "".join([
        bar("Region hashes", id="region-hashes"),
        "<p>The save's rival regions name their region by this hash (<code>RivalRegions[].RegionHash</code>). "
        "Shown as a number and in hex.</p>",
        table(["Region", "Wiki key", "Hash", "Hex"], rows, cls="compact mids"),
        "<p>Two more hashes from the same part of the save, the events in a rival's history "
        "(<code>Rivals[].History[].Hash</code>):</p>",
        kv([("Rival created", idc(hist.get("creation"))), ("Rival levelled up (\"Evolved to level N\")",
                                                            idc(hist.get("level_up")))]),
        f"<p>Threat levels, rival levels and the {fmt(len(d.gd.get('titles') or {}))} rival titles are on the "
        '<a href="~/machines/rivals.html">rivals page</a>.</p>',
    ])


def data_locations(site, d):
    lo = d.gd["locations"]
    kinds = {k["key"]: k["name"] for k in lo["kinds"]}
    rnames = {r["key"]: r["name"] for r in lo["regions"]}
    rows, flt = [], []
    order = [k for k, _ in REGIONS]
    for x in sorted(lo["list"], key=lambda x: (order.index(x["region"]) if x["region"] in order else 99, x["name"])):
        rows.append([site.link("location", str(x["hash"]), x["name"]),
                     site.link("region", x["region"], rnames.get(x["region"], x["region"])),
                     esc(kinds.get(x["kind"], x["kind"])), esc(x.get("type") or ""), f"<code>{esc(x['id'])}</code>",
                     idc(x["hash"]), round(x["x"]), round(x["z"]), x.get("spawns") or None])
        flt.append(f"r-{x['region']}")
    return "".join([
        bar("Location hashes", f"{len(rows)} locations", id="location-hashes"),
        "<p>Every map location with the hash the save uses for it (<code>LocationSummaries[].LocationId</code>; "
        "<code>Activated</code> = 1 means discovered). <b>X</b> / <b>Z</b> are world coordinates as on the "
        "interactive map, <b>Crates</b> the number of loot crate spawn points known for the location.</p>",
        filterbar("mlocs", "Filter by name, id or hash...", [(f"r-{r['key']}", r["name"]) for r in lo["regions"]]),
        ftable("mlocs", ["Location", "Region", "Kind", "Type", "Internal id", "Hash", "X", "Z", "Crates"], rows, flt,
               cls="compact mids", num={6, 7, 8}),
    ])


def spawn_point_value(object_id):
    """A world object ID ('0x376AD71E8085') as the save's PlayerSpawnPoints stores it: its three 16-bit parts in
    reverse order, moved to the top of the u64 (same as the Gen0 Editor's spawn_point_value)."""
    o = int(object_id, 16)
    return ((o & 0xFFFF) << 48) | (((o >> 16) & 0xFFFF) << 32) | (((o >> 32) & 0xFFFF) << 16)


def data_safehouses(site, d):
    sh = d.gd["safehouses"]
    start = set(sh.get("start") or [])
    rows, flt = [], []
    for reg in sh["regions"]:
        for s in reg["list"]:
            v = spawn_point_value(s["id"])
            rows.append([link_any(site, ["safehouse"], s["name"]), site.link("region", reg["key"], reg["name"]),
                         idc(s["id"]), idc(f"0x{v:016X}"), idc(v), "Yes" if s.get("start") else ""])
            flt.append(f"r-{reg['key']}")
    named = {s["id"]: s["name"] for reg in sh["regions"] for s in reg["list"]}
    srows = []
    for x in sorted(start):
        v = spawn_point_value(x)
        srows.append([idc(x), idc(f"0x{v:016X}"), idc(v),
                      link_any(site, ["safehouse"], named[x]) if x in named else
                      '<span class="dim">not a listed safehouse (start spawn point)</span>'])
    return "".join([
        bar("Safehouse IDs", f"{len(rows)} safehouses", id="safehouse-ids"),
        "<p>Unlocked safehouses are a list of 64-bit values in <code>PlayerSpawnPoints</code>, kept three times (in "
        "the character, the world and the active world slot). The value is the safehouse's world object ID with "
        "its three 16-bit parts in reverse order, shifted to the top: <b>Object ID</b> is what the location files "
        "use, <b>Save value</b> what the save holds (hex and decimal). The <code>SafeHousesUnlocked</code> "
        "statistic counts them.</p>",
        filterbar("mshs", "Filter safehouses...", [(f"r-{r['key']}", r["name"]) for r in sh["regions"]]),
        ftable("mshs", ["Safehouse", "Region", "Object ID", "Save value (hex)", "Save value", "Start"], rows, flt,
               cls="compact mids"),
        "".join(["<p>The data also lists these start spawn points. The editor accepts these values in "
                 "<code>PlayerSpawnPoints</code> too.</p>",
                 table(["Object ID", "Save value (hex)", "Save value", "Safehouse"], srows, cls="compact mids",
                       sortable=False)]) if srows else "",
    ])


def data_skills(site, d):
    sk = d.gd["skills"]
    tree_names = [t["name"].capitalize() for t in sk["trees"]]
    rows, flt = [], []
    for sid, s in sk["list"].items():
        icon = site.img(s["icon"].replace("assets/", "img/", 1), "", cls="mic") if s.get("icon") else ""
        tree = tree_names[s["tree"]] if s["tree"] < len(tree_names) else s["tree"]
        rows.append([icon, link_any(site, ["skill"], s["name"]), esc(tree), f"<code>{esc(sid)}</code>",
                     idc(s["hash"]), s.get("max"), "Yes" if s.get("active") else ""])
        flt.append(f"t-{slug(tree)}")
    return "".join([
        bar("Skill hashes", f"{len(rows)} skills", id="skill-hashes"),
        "<p>The save lists learned skills by hash in <code>Characters[].Skills</code>, with the rank in the same "
        "position of <code>SkillLevel</code> (rank minus one). <code>ActiveSkill</code> is the hash of the "
        "equipped active skill. <b>Max</b> is the highest rank.</p>",
        filterbar("mskills", "Filter skills...", [(f"t-{slug(t)}", t) for t in tree_names]),
        ftable("mskills", ["", "Skill", "Tree", "Id", "Hash", "Max", "Active"], rows, flt, cls="compact mids",
               num={5}),
    ])


def data_research(site, d):
    rows = []
    for r in d.gd["research"]:
        tiers = " / ".join(fmt(t) for t in r.get("tiers") or [])
        rows.append([link_any(site, ["augment"], r["name"], r["name"]), esc(r["group"].capitalize()),
                     f"<code>{esc(r['slug'])}</code>",
                     idc(r["hash"]), tiers or None, r["max"],
                     tag("Unlisted") if r.get("unlisted") else "",
                     esc(r["task"].replace("[VALUE]", "N"))])
    return "".join([
        bar("Research hashes", f"{len(rows)} tasks", id="research-hashes"),
        "<p>Augment research progress is a counter in the profile's currency list (<code>Profile.Currencies</code>, "
        "<code>Name</code> = the hash below, <code>Amount</code> = the count). <b>Tiers</b> are the counter values "
        "that unlock Bronze / Silver / Gold; the counter goes from 0 to <b>Max</b>. Tasks marked <b>Unlisted</b> "
        "are in the files but not shown in the Research menu.</p>",
        table(["Augment", "Group", "Slug", "Hash", "Tiers", "Max", "", "Task"], rows, cls="compact mids", num={5}),
    ])


def data_challenges(site, d):
    """One row per challenge tier: the tier's id (the Id of its entry in Characters[].Challenges) and objective."""
    trees = d.gd["challenges"]
    rows, flt = [], []
    for t in trees:
        tree = esc(t["name"].title()) + (" " + tag("DLC", "dlc") if t.get("dlc") else "")
        for c in t["challenges"]:
            for n, ti in enumerate(c["tiers"], 1):
                rows.append([tree, site.link("challenge", c["name"]), f"<code>{esc(c['key'])}</code>", n,
                             idc(ti["id"]), idc(ti["obj"]), f"{fmt(ti['start'])} &rarr; {fmt(ti['req'])}",
                             esc(ti.get("desc") or ""), esc(ti.get("title") or "")])
                flt.append(f"t-{slug(t['name'])}")
    nch = sum(len(t["challenges"]) for t in trees)
    return "".join([
        bar("Challenge hashes", f"{nch} challenges, {len(rows)} tiers", id="challenge-hashes"),
        "<p>Each challenge is a chain of tiers, and the save keeps one entry per tier in "
        "<code>Characters[].Challenges</code>: its <code>Id</code> is the <b>Tier id</b> below, and its one child, "
        "the tier's objective, holds the progress in <code>CompletionsDone</code> (<b>Objective</b> is the "
        "objective's hash in the challenge data). A tier is "
        "complete (<code>CompletionState</code> 4) once the progress reaches its target. <b>Progress</b> is the "
        "tier's range: it starts where the previous tier ended and is complete at the second number. All tiers of "
        "a challenge carry the same progress value, each clamped to its own range, which is how the "
        + tool(site, "Gen0 Editor") + " writes it. IDs are signed 32-bit numbers, as in the decoded save. The "
        "game only adds a challenge to a character the first time it is played with, and the trees marked "
        + tag("DLC", "dlc") + " need their DLC. What each challenge asks and awards is on the "
        '<a href="~/missions/challenges.html">challenges page</a>.</p>',
        filterbar("mchal", "Filter by challenge, title or ID...",
                  [(f"t-{slug(t['name'])}", t["name"].title()) for t in trees]),
        ftable("mchal", ["Tree", "Challenge", "Key", "Tier", "Tier id", "Objective", "Progress", "Task",
                         "Title awarded"], rows, flt, cls="compact mids", num={3}),
    ])


def data_currencies_stats(site, d):
    cur = []
    for c in d.gd["schematics"]:
        icon = site.img(c["icon"].replace("assets/", "img/", 1), "", cls="mic") if c.get("icon") else ""
        cur.append([icon, esc(c["name"]), f"<code>{esc(c['key'])}</code>", idc(c["hash"]), esc(c["earn"])])
    stats = [[esc(s["label"]), f"<code>{esc(s['key'])}</code>", idc(s["hash"]), esc(s.get("unit") or "")]
             for s in d.gd["stats"]]
    return "".join([
        bar("Schematic point currencies", id="currencies"),
        "<p>Schematic points are in the same currency list as research (<code>Profile.Currencies</code>), one entry "
        "per kind. A kind you never earned has no entry yet.</p>",
        table(["", "Points", "Key", "Hash", "How you earn them"], cur, cls="compact mids"),
        bar("Statistic hashes", f"{len(stats)} statistics", id="stat-hashes"),
        "<p>The statistics on the in-game stats screen are kept twice in the save, in "
        "<code>Characters[].Statistics</code> and <code>World.Statistics</code>, each as <code>NameHash</code> + "
        "<code>Value</code>. Distances are in metres and times in seconds.</p>",
        table(["Statistic", "Key", "Hash", "Unit"], stats, cls="compact mids"),
    ])


# ---------------------------------------------------------------------------------------------------------------
# what each build/data file is: file, what it holds, the tool it was copied from, where in that tool's repo
# (see build/import_sources.py)
DATA_FILES = [
    ("stats.json", "Machine and weapon stats: player weapon damage per ammo and quality, machine component health "
     "per layout, detection, machine weapons, difficulty", "Gen0 Extractor", "\"Machine & Weapon Stats\" export"),
    ("loadouts.json", "Every machine layout with its weapons, in-game and internal names", "Gen0 Extractor",
     "\"Machine Loadouts\" export"),
    ("gamedata.json", "Skills, schematic currencies, research tasks, regions, threat and rival levels, rival "
     "titles, statistics, challenges, safehouses, map locations", "Gen0 Editor", "web/assets"),
    ("IDs.json", "Item IDs per quality: weapons, attachments (with compatibility), ammo, skins, augments",
     "Gen0 Editor", "web/misc"),
    ("stock.json", "Every inventory item: name, internal name, group, stack size, icon", "Gen0 Editor", "web/assets"),
    ("augments.json", "Which augment fits which weapon and quality", "Gen0 Editor", "web/assets"),
    ("schematics.json", "Schematic trees and every schematic (cost, recipe, prerequisites)", "Gen0 Editor",
     "web/assets"),
    ("missions.json", "Story and side missions with region, pack, description and steps", "Gen0 Editor",
     "web/assets"),
    ("keys.json", "Bunker barcodes, keycards, door keys and mission items", "Gen0 Editor", "web/assets"),
    ("vanity.json", "Apparel, face paint, weapon skins, emotes, vehicles, companion cosmetics, packs",
     "Gen0 Editor", "web/assets"),
    ("icons.json", "Item ID &rarr; icon file", "Gen0 Editor", "web/assets"),
    ("location_crates.json", "Loot crate spawn points per location (by location hash)", "Gen0 Editor",
     "web/assets"),
    ("markers.json", "Map markers (collectibles, schematics, house photos, safehouses, control points, beacons) and "
     "region borders", "Gen0 Map", "map/markers.json"),
    ("map_locations.json", "Every map location with kind, region and position", "Gen0 Map", "map/locations.json"),
    ("loot.json", "Placed loot (weapons by quality, attachments, items, materials, crates) with positions",
     "Gen0 Map", "map/loot.json"),
    ("kinds.json", "Plain names and descriptions of every kind of placed object and their properties",
     "Gen0 Map Editor", "data/kinds.json, hand-written"),
]


def data_files(site, d):
    import os
    from wiki.site import DATA as DATA_DIR
    rows = []
    for f, what, src, where in DATA_FILES:
        path = os.path.join(DATA_DIR, f)
        size = round(os.path.getsize(path) / 1024) if os.path.exists(path) else None
        rows.append([f"<code>{esc(f)}</code>", what, f"{tool(site, src)} <span class=\"dim small\">({esc(where)})</span>",
                     size])
    notes = []
    for f in ("stats", "loadouts"):
        about = site.data(f).get("_about") or {}
        if about.get("source"):
            notes.append(f"<li><code>{f}.json</code>: {esc(about['source'])}</li>")
    for f, key in (("missions", "about"), ("location_crates", "about")):
        a = site.data(f).get(key)
        if isinstance(a, str):
            notes.append(f"<li><code>{f}.json</code>: {esc(a)}</li>")
    return "".join([
        bar("The data files", id="data-files"),
        "<p>The wiki is generated from these JSON files in the <code>build/data/</code> folder of " +
        repo("gen0-wiki") + ". <code>build/import_sources.py</code> copies them in from the other Gen0 repos after "
        "they were re-extracted from the game, and <code>build/build.py</code> turns them into this site.</p>",
        table(["File", "What it holds", "Comes from", "KB"], rows, cls="compact mids", num={3}),
        "<h3>How the data was read</h3>",
        "<p>The " + tool(site, "Gen0 Extractor") + " builds an index of the game's <code>.tab</code> / "
        "<code>.arc</code> archives (recovering the file names from their Jenkins hashes) and reads the files "
        "straight from the archives: the ADF data files and the in-game text table for items, the location files "
        "for positions and IDs, the tuning files for damage and health. The files' own notes say:</p>",
        '<ul class="mnotes">' + "".join(notes) + "</ul>",
        note("Item IDs and hashes are the game's own and stay the same as long as the game doesn't change the item. "
             "After a game update, re-extract and rebuild before trusting a value for a new item.", "data"),
    ])
