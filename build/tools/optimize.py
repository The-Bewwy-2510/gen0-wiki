#!/usr/bin/env python3
"""
tools/optimize.py - one-off asset optimizer for the wiki (not part of build.py, which stays stdlib-only).

Needs:  pip install pillow fonttools brotli

What it does (each step is safe to run again; it skips work that is already done):

  icons     docs/img/**/*.png -> lossless .webp next to it, then removes the .png (and *.jpg -> WebP at quality
            82, as they are already lossy). The data files still name the .png / .jpg; Site.asset() (wiki/site.py) points every reference at the .webp, so nothing else changes.
            Augment icons and their tier frames (264 px, shown at 76 px at most) are scaled to 160 px first.
  machines  docs/img/machines/<type>_<class>.webp (720 px renders, shown at 190 px at most) -> 400 px, plus a
            128 px copy in docs/img/machines/small/ for the 48 px pictures in lists and cards.
  static    build/static/bg.jpg -> bg.webp (behind a dark overlay, so a low quality is invisible);
            build/static/logo.png (608 px, shown at 120 px) -> logo.webp at 240 px.
  fonts     build/fonts/OpenSans-*.woff2 (full fonts, kept as the source) -> build/static/OpenSans-*.woff2 with only
            the characters the wiki uses (Latin, Latin-1, Latin Extended-A, punctuation, plus every character
            found in the built pages and the search index).
  tiles     docs/map/map/tiles/<level>/<i>_<j>.webp (2048 px tiles of the interactive map) -> docs/img/mm/: the
            same levels cut into 1024 px tiles (a small map loads one or two small tiles, not up to four big
            ones) and a level 0: the whole world in one 2048 px picture (0/0_0.webp).

Usage:  python tools/optimize.py [icons] [machines] [static] [fonts] [tiles]     (no argument = all)
"""
import glob, os, re, sys
from concurrent.futures import ProcessPoolExecutor

from PIL import Image

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # build/
DOCS = os.path.join(os.path.dirname(HERE), "docs")
STATIC = os.path.join(HERE, "static")
FONTS = os.path.join(HERE, "fonts")
SMALL_FOLDERS = {"augments": 160}      # folder under docs/img -> largest side in px


def _icon(path):
    w = path[:-4] + ".webp"
    im = Image.open(path)
    im.load()
    rel = os.path.relpath(path, os.path.join(DOCS, "img")).replace(os.sep, "/")
    top = rel.split("/")[0]
    if top in SMALL_FOLDERS and max(im.size) > SMALL_FOLDERS[top]:
        im.thumbnail((SMALL_FOLDERS[top],) * 2, Image.LANCZOS)
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGBA")
    im.save(w, "WEBP", lossless=True, method=6)
    a, b = os.path.getsize(path), os.path.getsize(w)
    os.remove(path)
    return a, b


def _photo(path):
    w = path[:-4] + ".webp"
    Image.open(path).convert("RGB").save(w, "WEBP", quality=82, method=6)
    a, b = os.path.getsize(path), os.path.getsize(w)
    os.remove(path)
    return a, b


def icons():
    photos = sorted(glob.glob(os.path.join(DOCS, "img", "**", "*.jpg"), recursive=True))
    if photos:     # Steam store art and achievement icons: already lossy JPEG, so a lossy WebP of the same quality
        with ProcessPoolExecutor() as ex:
            res = list(ex.map(_photo, photos, chunksize=4))
        print(f"photos: {len(photos)} JPEG -> WebP, {sum(r[0] for r in res) / 1e6:.1f} MB -> "
              f"{sum(r[1] for r in res) / 1e6:.1f} MB")
    files = sorted(glob.glob(os.path.join(DOCS, "img", "**", "*.png"), recursive=True))
    if not files:
        print("icons: nothing to do")
        return
    with ProcessPoolExecutor() as ex:
        res = list(ex.map(_icon, files, chunksize=8))
    a, b = sum(r[0] for r in res), sum(r[1] for r in res)
    print(f"icons: {len(files)} PNG -> WebP, {a / 1e6:.1f} MB -> {b / 1e6:.1f} MB")


def machines():
    folder = os.path.join(DOCS, "img", "machines")
    small = os.path.join(folder, "small")
    os.makedirs(small, exist_ok=True)
    n = 0
    for f in sorted(glob.glob(os.path.join(folder, "*.webp"))):
        im = Image.open(f)
        im.load()
        sp = os.path.join(small, os.path.basename(f))
        if not os.path.exists(sp):
            t = im.copy()
            t.thumbnail((128, 128), Image.LANCZOS)
            t.save(sp, "WEBP", quality=88, alpha_quality=90, method=6)
        if max(im.size) > 400:
            im.thumbnail((400, 400), Image.LANCZOS)
            im.save(f, "WEBP", quality=86, alpha_quality=90, method=6)
            n += 1
    print(f"machines: {n} pictures scaled to 400 px, small copies in img/machines/small/")


def static():
    bg = os.path.join(STATIC, "bg.jpg")
    if os.path.exists(bg):
        Image.open(bg).save(os.path.join(STATIC, "bg.webp"), "WEBP", quality=60, method=6)
        os.remove(bg)
    logo = os.path.join(STATIC, "logo.png")
    if os.path.exists(logo):
        im = Image.open(logo).convert("RGBA")
        im.thumbnail((240, 240 * im.height // im.width + 1), Image.LANCZOS)
        im.save(os.path.join(STATIC, "logo.webp"), "WEBP", lossless=True, method=6)
        os.remove(logo)
    print("static: bg.webp, logo.webp")


def used_chars():
    chars = set()
    for f in glob.glob(os.path.join(DOCS, "**", "*.html"), recursive=True) + [os.path.join(DOCS, "assets", "search.json")]:
        if os.sep + "map" + os.sep in f:
            continue
        t = open(f, encoding="utf-8").read()
        t = re.sub(r"<(script|style)\b.*?</\1>", " ", t, flags=re.S)
        t = re.sub(r"<[^>]+>", " ", t)
        t = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), t)
        t = re.sub(r"&#x([0-9a-f]+);", lambda m: chr(int(m.group(1), 16)), t, flags=re.I)
        chars.update(t)
    for f in glob.glob(os.path.join(STATIC, "*.js")):     # text the scripts write (buttons, counts, "shown")
        chars.update(open(f, encoding="utf-8").read())
    return chars


def fonts():
    from fontTools import subset
    os.makedirs(FONTS, exist_ok=True)
    for f in glob.glob(os.path.join(STATIC, "OpenSans-*.woff2")):      # first run: keep the full fonts as the source
        src = os.path.join(FONTS, os.path.basename(f))
        if not os.path.exists(src):
            os.replace(f, src)
    ranges = [(0x20, 0x7E), (0xA0, 0x17F), (0x2000, 0x206F), (0x20AC, 0x20AC), (0x2122, 0x2122),
              (0x2190, 0x2193), (0x2212, 0x2212)]
    cps = {c for a, b in ranges for c in range(a, b + 1)} | {ord(c) for c in used_chars() if ord(c) >= 0x20}
    for src in sorted(glob.glob(os.path.join(FONTS, "OpenSans-*.woff2"))):
        dst = os.path.join(STATIC, os.path.basename(src))
        opts = subset.Options()
        opts.flavor = "woff2"
        opts.layout_features = ["kern", "liga", "calt", "ccmp", "locl", "mark", "mkmk", "tnum", "lnum"]
        opts.name_IDs = ["*"]
        opts.notdef_outline = True
        font = subset.load_font(src, opts)
        cmap = font.getBestCmap()
        sub = subset.Subsetter(opts)
        sub.populate(unicodes=[c for c in cps if c in cmap])
        sub.subset(font)
        subset.save_font(font, dst, opts)
        missing = sorted(chr(c) for c in cps if c not in cmap and c > 0x7F and c not in range(0x2000, 0x2070))
        print(f"fonts: {os.path.basename(src)} {os.path.getsize(src) // 1024} KB -> {os.path.getsize(dst) // 1024} KB"
              + (f" (not in the font, shown in a fallback font: {''.join(missing[:40])})" if missing else ""))


def _tile_job(args):
    src, dst, box, size, q = args
    im = Image.open(src)
    im = im.crop(box) if box else im
    if size and im.size != (size, size):
        im = im.resize((size, size), Image.LANCZOS)
    im.save(dst, "WEBP", quality=q, method=5)
    return os.path.getsize(dst)


def tiles():
    src = os.path.join(DOCS, "map", "map", "tiles")
    out = os.path.join(DOCS, "img", "mm")
    jobs = []
    for level, n in ((1, 2), (2, 4), (3, 8)):           # 2048 px tiles -> 1024 px tiles
        os.makedirs(os.path.join(out, str(level)), exist_ok=True)
        for i in range(n):
            for j in range(n):
                s = os.path.join(src, str(level), f"{i}_{j}.webp")
                for di in (0, 1):
                    for dj in (0, 1):
                        d = os.path.join(out, str(level), f"{2 * i + di}_{2 * j + dj}.webp")
                        if not os.path.exists(d):     # level 3 a bit higher: keeps the map's fine hatching
                            jobs.append((s, d, (di * 1024, dj * 1024, di * 1024 + 1024, dj * 1024 + 1024), None,
                                         82 if level == 3 else 76))
    with ProcessPoolExecutor() as ex:
        total = sum(ex.map(_tile_job, jobs, chunksize=4))
    # the whole world: level 1 (2 x 2 tiles of 2048) -> 2048 px (world.webp) and 1024 px (level 0)
    world = Image.new("RGB", (4096, 4096))
    for i in (0, 1):
        for j in (0, 1):
            world.paste(Image.open(os.path.join(src, "1", f"{i}_{j}.webp")).convert("RGB"), (i * 2048, j * 2048))
    os.makedirs(os.path.join(out, "0"), exist_ok=True)
    world.resize((2048, 2048), Image.LANCZOS).save(os.path.join(out, "0", "0_0.webp"), "WEBP", quality=80, method=5)
    print(f"tiles: {len(jobs)} new 1024 px tiles ({total / 1e6:.1f} MB) and level 0")


if __name__ == "__main__":
    steps = sys.argv[1:] or ["icons", "machines", "static", "fonts", "tiles"]
    for s in steps:
        globals()[s]()
