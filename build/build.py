"""Build the Gen0 Wiki into docs/ (served by GitHub Pages).

    python build/build.py                 # everything
    python build/build.py weapons world   # only these section modules (quick check while editing; the
                                          # other sections' pages are still registered, so links resolve)

Needs Python 3.8+ and nothing else. Data comes from build/data/*.json (see build/import_sources.py), the icons and
the interactive map from docs/img and docs/map.
"""
import importlib
import os
import pkgutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from wiki.site import Site  # noqa: E402

# build order doesn't matter for links (every section's collect() runs before any build()); it only decides which
# section wins when two register the same name
ORDER = ["home", "weapons", "ammo", "augments", "machines", "machine_weapons", "world", "collectibles", "missions",
         "items", "character", "modding"]


# sections that are turned off for now: not imported, so their pages aren't built and nothing links to them
DISABLED = {"modding"}


def section_modules():
    import sections
    found = [m.name for m in pkgutil.iter_modules(sections.__path__)
             if not m.name.startswith("_") and m.name not in DISABLED]
    return sorted(found, key=lambda n: (ORDER.index(n) if n in ORDER else len(ORDER), n))


def main(argv):
    t0 = time.time()
    only = set(argv) or None
    site = Site()
    site.write_static()
    mods = []
    for name in section_modules():
        try:
            mods.append((name, importlib.import_module("sections." + name)))
        except Exception as e:  # a broken section must not stop the others
            print(f"!! section {name}: import failed: {e!r}")
            if only and name in only:
                raise
    for name, m in mods:
        if hasattr(m, "collect"):
            try:
                m.collect(site)
            except Exception as e:  # another section being edited must not stop this one
                print(f"!! section {name}: collect failed: {e!r}")
                if only and name in only:
                    raise
    for name, m in mods:
        if only and name not in only:
            continue
        if hasattr(m, "build"):
            t = time.time()
            n0 = len(site.pages)
            m.build(site)
            print(f"  {name:16s} {len(site.pages) - n0:5d} pages  {time.time() - t:5.1f}s")
    n = site.write_search()
    print(f"{len(site.pages)} pages, {n} search entries, {time.time() - t0:.1f}s")
    if site.missing:
        print(f"\n{len(site.missing)} link targets nobody registered (shown as plain text):")
        for (kind, key), c in sorted(site.missing.items())[:80]:
            print(f"  {kind}: {key}  ({c}x)")
    if site.warnings:
        print(f"\n{len(site.warnings)} warnings:")
        for w in site.warnings[:80]:
            print("  " + w)
    if True:
        bad = site.check_links()   # with a section list: only its pages are checked; registered pages count as there
        if bad:
            print(f"\n{len(bad)} broken links:")
            for tgt, srcs in sorted(bad.items())[:80]:
                print(f"  {tgt}  <- {', '.join(sorted(srcs)[:3])}{' ...' if len(srcs) > 3 else ''}")
        else:
            print("No broken links.")


if __name__ == "__main__":
    main(sys.argv[1:])
