"use strict";
/* Gen0 Map - the MAP tab of the Gen0 Editor as a page of its own: no savegame, just the map and its filters.
   It is a static site (works on GitHub Pages or any web server); open it through a server, not as a file,
   since browsers don't let a page opened from disk read its JSON files.
   World coordinates: X right, Z down, (0,0) = centre of the map image, 32768 units across.
   Map images: 3 levels (4096, 8192, 16384 px) cut into 2048 px tiles; the renderer shows the coarsest level that
   is sharp enough, with the coarser levels kept underneath so zooming never shows holes (seamless LOD). */
(() => {
  const qs = (s, el = document) => el.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  // the page's settings (filters, icon size ...) are remembered in this browser only
  const store = {
    get(k, d) {
      try { const v = localStorage.getItem("gen0map." + k); return v == null ? d : JSON.parse(v); } catch (_) { return d; }
    },
    set(k, v) {
      if (!persist && /^map(Enabled|Regions|Advanced)$/.test(k)) return;   // a linked view: keep the saved filters
      try { localStorage.setItem("gen0map." + k, JSON.stringify(v)); } catch (_) { /* storage unavailable */ }
    },
  };

  // ------------------------------------------------------------------ links into the map
  // index.html?show=gnomes,loc_church&region=forest&at=X,Z&zoom=0.6&focus=Name opens the map with only those
  // categories (map/markers.json sub keys, loc_<kind> for locations, loot_* for placed loot) and regions ticked,
  // centred on world coordinates X,Z, and with the popup of the marker called Name open. Pages like the Gen0 Wiki
  // link here. A linked view doesn't overwrite the filters you saved, until you change one yourself.
  const LINK = (() => {
    const q = new URLSearchParams(location.search), list = (k) => (q.get(k) || "").split(",").map((x) => x.trim()).filter(Boolean);
    const at = list("at").map(Number);
    const L = { show: list("show"), region: list("region"), focus: q.get("focus") || "",
      at: at.length === 2 && at.every(Number.isFinite) ? at : null, zoom: Number(q.get("zoom")) || 0 };
    L.any = !!(L.show.length || L.region.length || L.at || L.focus);
    L.loot = L.show.some((k) => k.startsWith("loot_"));
    return L;
  })();
  let persist = !LINK.any;            // false while a linked view is shown: then the filters aren't saved

  // ------------------------------------------------------------------ map
  const MapView = (() => {
    const L3 = 16384;                 // pixel size of the most detailed level
    const CLUSTER_PX = 18;            // markers closer than this (on screen) are grouped
    let D = null, started = false;
    let stage, tilesEl, mkEl, legsEl, popEl;
    let W = 0, H = 0, s = 0.05, tx = 0, ty = 0, minS = 0.01;
    // placed loot sits metres apart (crate spots indoors): advanced mode lets the map zoom in much further
    const MAX_S = 2.5, MAX_S_ADV = 12;
    let maxS = MAX_S;
    let toL3 = 0.5;                   // world units -> level-3 pixels
    let items = [], subs = {}, mains = [], subsOf = {};
    let enabled = {}, regionOn = {}, regions = {}, collapsed = {};
    // the map locations (map/locations.json) are markers too, in a category of their own
    const isVis = (it) => (adv || !it.adv) && enabled[it.s] && regionOn[it.r] !== false;
    let clusters = [], clusterScale = 0, needCluster = true;
    let openCl = null, selected = null;     // selected = {item, spreadIdx}
    let raf = 0;
    let showBorders = false;          // region border overlay: off at every start, only the button / B turns it on
    let panelOpen = true;             // filters side panel (remembered)
    // icon size (remembered): 1x / 2x / 3x are labels, the markers grow by these factors
    const SIZES = [1, 1.45, 1.9];
    let sizeIx = 1;
    // advanced mode (remembered): the placed loot categories (map/loot.json, loaded the first time) join the list,
    // each one off until ticked
    let adv = false, lootLoad = null;
    const tileCache = new Map();

    const sx = (X) => tx + X * s, sy = (Z) => ty + Z * s;

    function schedule() { if (!raf) raf = requestAnimationFrame(render); }

    // ---------------- setup ----------------
    async function start() {
      started = true;
      stage = qs("#mapStage"); tilesEl = qs("#mapTiles"); mkEl = qs("#mapLayer"); legsEl = qs("#mapLegs"); popEl = qs("#mapPopup");
      // the files download at once (index.html already asked for them); the locations and side missions are optional
      const markersReq = fetch("map/markers.json");
      const locationsReq = fetch("map/locations.json").then((r) => r.json()).catch(() => null);
      const sideReq = fetch("map/side_missions.json").then((r) => (r.ok ? r.json() : null)).catch(() => null);
      try {
        D = await (await markersReq).json();
      } catch (e) {
        qs("#mapLoading").textContent = "Couldn't load map/markers.json";
        return;
      }
      toL3 = L3 / D.world;
      addLocations(await locationsReq);
      addSideMissions(await sideReq);
      mains = D.mains;
      D.subs.forEach((sb) => { subs[sb.key] = sb; (subsOf[sb.main] = subsOf[sb.main] || []).push(sb); });
      items = D.items.map((it, i) => ({ ...it, i, X: L3 / 2 + it.x * toL3, Z: L3 / 2 + it.z * toL3 }));
      const saved = store.get("mapEnabled", null);
      D.subs.forEach((sb) => { enabled[sb.key] = saved && sb.key in saved ? !!saved[sb.key] : true; });
      const savedR = store.get("mapRegions", null);
      (D.regions || []).forEach((r) => { regions[r.key] = r; regionOn[r.key] = savedR && r.key in savedR ? !!savedR[r.key] : true; });
      // every category starts closed except the regions (remembered once changed)
      collapsed = store.get("mapCollapsed2", null) || Object.fromEntries(D.mains.map((m) => [m.key, true]));
      D.mains.forEach((m) => { if (!(m.key in collapsed)) collapsed[m.key] = true; });   // a category added since: closed too
      if (LINK.any) applyLinkFilters();
      setPanel(store.get("mapPanel", true) !== false);
      sizeIx = Math.max(0, Math.min(SIZES.length - 1, Number.isFinite(+store.get("mapIconSize2", 1)) ? +store.get("mapIconSize2", 1) : 1));
      adv = LINK.loot || store.get("mapAdvanced", false) === true;   // a link to placed loot turns Extra Locations on
      applySize(); applyAdv();
      bindPanel();
      buildPanel();
      if (adv) loadLoot();
      measure();
      fitContent();
      if (LINK.at) centerOn(LINK.at[0], LINK.at[1], LINK.zoom || 0.6);
      bindEvents();
      // the user changing a filter makes the view theirs: from then on it is saved as usual
      qs("#mapPanel").addEventListener("pointerdown", () => { persist = true; }, true);
      if (LINK.focus) (LINK.loot ? loadLoot() || Promise.resolve() : Promise.resolve()).then(() => setTimeout(focusLinked, 60));
      new ResizeObserver(() => {
        if (!stage.clientWidth || !stage.clientHeight) return;
        const ow = W, oh = H; measure();
        tx += (W - ow) / 2; ty += (H - oh) / 2; clamp(); schedule();
      }).observe(stage);
      schedule();
    }

    // ---------------- linked view (see LINK) ----------------
    function applyLinkFilters() {
      if (LINK.show.length) {
        D.subs.forEach((sb) => { enabled[sb.key] = LINK.show.includes(sb.key); });
        // open the categories that have a ticked entry, so the panel shows what is on
        D.subs.forEach((sb) => { if (enabled[sb.key]) collapsed[sb.main] = false; });
      }
      if (LINK.region.length) (D.regions || []).forEach((r) => { regionOn[r.key] = LINK.region.includes(r.key); });
    }
    function centerOn(x, z, scale) {
      s = Math.min(maxS, Math.max(minS, scale));
      tx = W / 2 - (L3 / 2 + x * toL3) * s; ty = H / 2 - (L3 / 2 + z * toL3) * s;
      clamp(); needCluster = true; schedule();
    }
    function focusLinked() {
      const want = LINK.focus.toLowerCase();
      let best = null, bd = Infinity;
      for (const it of items) {
        if (!isVis(it) || String(it.n).toLowerCase() !== want) continue;
        const d = LINK.at ? Math.hypot(it.x - LINK.at[0], it.z - LINK.at[1]) : 0;
        if (d < bd) { bd = d; best = it; }
      }
      if (!best) return;
      if (!LINK.at) centerOn(best.x, best.z, LINK.zoom || 0.6);
      render(); openPopup(best);
    }

    // The map locations (map/locations.json): one category right under the regions,
    // a sub category per type with the game's map icon; the glyph is that icon's symbol
    function addLocations(G) {
      if (!G || !G.list || !G.list.length) return;     // no locations then
      const kinds = G.kinds.filter((k) => G.list.some((x) => x.kind === k.key));
      if (!kinds.length) return;
      D.mains = [{ key: "locations", name: "Locations", group: "locations" }, ...D.mains];
      const glyph = (icon) => `map/glyphs/loc_${icon}.png`;
      D.subs = [...kinds.map((k) => {
        const first = G.list.find((x) => x.kind === k.key);
        return { key: "loc_" + k.key, name: k.name, main: "locations", glyph: glyph(first.icon), icon: `assets/locations/${first.icon}.png`,
          count: G.list.filter((x) => x.kind === k.key).length };
      }), ...D.subs];
      D.items = D.items.concat(G.list.map((x) => ({ s: "loc_" + x.kind, n: x.name, x: x.x, z: x.z, r: x.region, d: x.region === "alpine" ? 1 : 0,
        loc: x.hash, g: glyph(x.icon) })));
    }

    // Where the side missions start (map/side_missions.json): a category of its own after the others, set apart by
    // the wide rule above and below it, a sub category per content pack; the markers look like the game's side
    // mission icon (white chevrons on its teal diamond)
    function addSideMissions(S) {
      if (!S || !S.list || !S.list.length) return;
      const packs = S.packs.filter((p) => S.list.some((x) => x.pack === p.key));
      D.mains = [...D.mains, { key: "sidemissions", name: "Side Missions", group: "sidemissions", wide: true }];
      D.subs = [...D.subs, ...packs.map((p) => ({ key: "sm_" + p.key, name: p.name, main: "sidemissions", mk: "side", color: "255, 255, 255",
        glyph: "map/glyphs/side_missions.png", icon: "map/icons/side_missions.png", count: S.list.filter((x) => x.pack === p.key).length }))];
      D.items = D.items.concat(S.list.map((x) => ({ s: "sm_" + x.pack, n: x.name, x: x.x, z: x.z, r: x.region, d: x.pack === "alpine" ? 1 : 0,
        l: "Start: " + [x.place, x.note].filter(Boolean).join(". "), ms: x.id })));
    }

    function measure() { W = stage.clientWidth; H = stage.clientHeight; minS = Math.min(W, H) / L3 * 0.85; }

    function fitContent() {                      // whole playable area (all markers) with a margin
      let x0 = Infinity, x1 = -Infinity, z0 = Infinity, z1 = -Infinity;
      for (const it of items) { x0 = Math.min(x0, it.X); x1 = Math.max(x1, it.X); z0 = Math.min(z0, it.Z); z1 = Math.max(z1, it.Z); }
      const pad = 0.08, bw = (x1 - x0) * (1 + pad * 2), bh = (z1 - z0) * (1 + pad * 2);
      s = Math.max(minS, Math.min(W / bw, H / bh));
      tx = W / 2 - (x0 + x1) / 2 * s; ty = H / 2 - (z0 + z1) / 2 * s;
      clamp(); needCluster = true; schedule();
    }

    function clamp() {
      s = Math.min(maxS, Math.max(minS, s));
      const m = L3 * s;                            // keep at least half the screen on the map
      tx = Math.min(W / 2, Math.max(W / 2 - m, tx));
      ty = Math.min(H / 2, Math.max(H / 2 - m, ty));
    }

    function zoomAt(f, cx = W / 2, cy = H / 2) {
      const ns = Math.min(maxS, Math.max(minS, s * f));
      tx = cx - (cx - tx) * ns / s; ty = cy - (cy - ty) * ns / s; s = ns;
      clamp(); schedule();
    }

    // ---------------- rendering ----------------
    function render() {
      raf = 0;
      if (!D) return;
      renderTiles();
      if (showBorders) placeBorders();
      if (needCluster || (Math.abs(Math.log(s / clusterScale)) > 0.06 && clusterDue())) recluster();
      else if (built) {
        const v = viewBox(0);
        if (v.x0 < built.x0 || v.x1 > built.x1 || v.z0 < built.z0 || v.z1 > built.z1) buildMarkers();
      }
      placeMarkers();
      placePopup();
    }

    function renderTiles() {
      const lv = D.levels;
      let cur = lv.length - 1;
      for (let L = 0; L < lv.length; L++) { if (s / (lv[L].size / L3) <= 1.25) { cur = L; break; } }
      const used = new Set();
      const vx0 = -tx / s, vx1 = (W - tx) / s, vy0 = -ty / s, vy1 = (H - ty) / s;
      for (let L = 0; L <= cur; L++) {
        const n = lv[L].tiles, size = L3 / n;
        const ix0 = Math.max(0, Math.floor(vx0 / size)), ix1 = Math.min(n - 1, Math.floor(vx1 / size));
        const iy0 = Math.max(0, Math.floor(vy0 / size)), iy1 = Math.min(n - 1, Math.floor(vy1 / size));
        for (let iy = iy0; iy <= iy1; iy++) for (let ix = ix0; ix <= ix1; ix++) {
          const key = `${lv[L].dir ?? L}/${ix}_${iy}`;
          let img = tileCache.get(key);
          if (!img) {
            img = new Image();
            img.decoding = "async"; img.draggable = false; img.alt = "";
            img.style.zIndex = L;
            if (L === 0) img.onload = () => { qs("#mapLoading").hidden = true; };
            img.src = `map/tiles/${key}.webp`;
            tileCache.set(key, img);
          }
          const x = Math.floor(tx + ix * size * s), y = Math.floor(ty + iy * size * s);
          const w = Math.ceil(tx + (ix + 1) * size * s) - x + 1, h = Math.ceil(ty + (iy + 1) * size * s) - y + 1;
          img.style.transform = `translate(${x}px,${y}px)`;
          img.style.width = w + "px"; img.style.height = h + "px";
          if (img.parentNode !== tilesEl) tilesEl.appendChild(img);
          used.add(img);
        }
      }
      for (const img of [...tilesEl.children]) if (!used.has(img)) img.remove();
    }

    // While zooming, the markers are grouped again at most every CLUSTER_MS (in between they just move with the
    // map): rebuilding thousands of markers on every frame made zooming in advanced mode stutter
    const CLUSTER_MS = 120;
    let clusteredAt = 0, clusterTimer = 0;
    function clusterDue() {
      const wait = CLUSTER_MS - (performance.now() - clusteredAt);
      if (wait <= 0) return true;
      if (!clusterTimer) clusterTimer = setTimeout(() => { clusterTimer = 0; schedule(); }, wait);
      return false;
    }
    // the markers the filters let through (in list order) with their positions, kept until the filters change:
    // recluster() runs on every zoom step and filtering tens of thousands of markers each time added up
    let visCache = null;
    function visible() {
      if (!visCache || visCache.of !== items.length) {
        const its = items.filter(isVis), X = new Float64Array(its.length), Z = new Float64Array(its.length), on = new Uint8Array(items.length);
        its.forEach((it, k) => { X[k] = it.X; Z[k] = it.Z; on[it.i] = 1; });
        visCache = { its, X, Z, on, of: items.length };
      }
      return visCache;
    }

    // Grouping: in list order, each marker that isn't in a group yet takes every ungrouped marker closer than R
    // (on screen). Markers are put in a grid of R px cells, so only the 3x3 cells around a marker are looked at.
    // A cell is keyed by one number (column * 2^20 + row); the cells live in flat typed arrays found through a
    // small hash table: with tens of thousands of placed loot markers this runs on every zoom step, and a Map of
    // arrays was most of the time spent zooming. The groups come out exactly as the Map version made them.
    const GK = 1048576, EMPTY = -0.5;          // EMPTY: a hash slot with no cell (keys are whole numbers)
    let cellX = new Float64Array(0), cellY = cellX, taken = new Uint8Array(0);
    let bucketOf = new Int32Array(0), bucketN = bucketOf, bucketAt = bucketOf, byBucket = bucketOf;
    let hashKey = new Float64Array(0), hashVal = new Int32Array(0);
    function group(V, R) {
      const its = V.its, n = its.length, vx = V.X, vz = V.Z, R2 = R * R, cell = R, out = [];
      if (cellX.length < n) {
        cellX = new Float64Array(n); cellY = new Float64Array(n); taken = new Uint8Array(n);
        bucketOf = new Int32Array(n); bucketN = new Int32Array(n); bucketAt = new Int32Array(n); byBucket = new Int32Array(n);
      }
      let size = 16, bits = 4; while (size < n * 2) { size *= 2; bits++; }
      if (hashKey.length < size) { hashKey = new Float64Array(size); hashVal = new Int32Array(size); }
      hashKey.fill(EMPTY, 0, size);
      const mask = size - 1, shift = 32 - bits;
      const slot = (key) => {                  // the slot holding this cell, or the empty slot where it would go
        let h = Math.imul((key | 0) ^ Math.imul((key / 4294967296) | 0, 0x85ebca6b), 0x9e3779b1) >>> shift;
        while (hashKey[h] !== key && hashKey[h] !== EMPTY) h = (h + 1) & mask;
        return h;
      };
      // bucket b (one per occupied cell) is byBucket[bucketAt[b] ... bucketAt[b] + bucketN[b] - 1], in list order
      let nb = 0;
      for (let k = 0; k < n; k++) {
        const cx = Math.floor(vx[k] * s / cell), cy = Math.floor(vz[k] * s / cell), key = cx * GK + cy, h = slot(key);
        cellX[k] = cx; cellY[k] = cy;
        if (hashKey[h] === EMPTY) { hashKey[h] = key; hashVal[h] = nb; bucketN[nb++] = 0; }
        bucketN[bucketOf[k] = hashVal[h]]++;
      }
      for (let b = 0, p = 0; b < nb; b++) { bucketAt[b] = p; p += bucketN[b]; }
      for (let k = 0; k < n; k++) byBucket[bucketAt[bucketOf[k]]++] = k;
      for (let b = 0; b < nb; b++) bucketAt[b] -= bucketN[b];
      taken.fill(0, 0, n);
      for (let k = 0; k < n; k++) {
        if (taken[k]) continue;
        taken[k] = 1;
        const members = [its[k]], X0 = vx[k], Z0 = vz[k], cx = cellX[k], cy = cellY[k];
        let X = X0, Z = Z0;                      // the centre: positions summed in member order
        for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++) {
          const h = slot((cx + dx) * GK + cy + dy);
          if (hashKey[h] === EMPTY) continue;
          for (let b = hashVal[h], p = bucketAt[b], e = p + bucketN[b]; p < e; p++) {
            const o = byBucket[p];
            if (taken[o]) continue;
            const ex = (vx[o] - X0) * s, ez = (vz[o] - Z0) * s;
            if (ex * ex + ez * ez < R2) { members.push(its[o]); taken[o] = 1; X += vx[o]; Z += vz[o]; }
          }
        }
        out.push({ members, X: X / members.length, Z: Z / members.length });
      }
      return out;
    }

    function recluster() {
      needCluster = false; clusterScale = s; clusteredAt = performance.now();
      const V = visible();
      clusters = group(V, CLUSTER_PX * SIZES[sizeIx]);
      // keep an open group open if it still exists (the same markers, in the same order)
      if (openCl) {
        const was = openCl.members;
        openCl = clusters.find((c) => c.members[0] === was[0] && c.members.length === was.length && c.members.every((m, k) => m === was[k])) || null;
      }
      if (selected && !V.on[selected.item.i]) closePopup();     // every marker the filters let through is in a group
      buildMarkers();
    }

    function markerHTML(it, extra = "") {
      const sb = subs[it.s];
      const cls = `mk${it.loc !== undefined ? " loc" : ""}${sb.mk ? " " + sb.mk : ""}${extra}`;
      const title = esc(it.n);
      return `<div class="${cls}" data-item="${it.i}" style="--g:url('${it.g || sb.glyph}')${sb.color ? `;--mk:${sb.color}` : ""}" title="${title}"><i></i></div>`;
    }

    // with many groups on screen (placed loot), only the ones near the view are built; render() builds again
    // once the view leaves that area
    const CULL_AT = 700;
    let built = null;
    function viewBox(m) {
      const w = W / s, h = H / s, x0 = -tx / s, z0 = -ty / s;
      return { x0: x0 - w * m, x1: x0 + w * (1 + m), z0: z0 - h * m, z1: z0 + h * (1 + m) };
    }
    // what placeMarkers() needs for each built element, in DOM order: the world position, the screen offset of the
    // markers of an open group, and the placing state
    const spot = (X, Z, o = null) => ({ X, Z, o, at: 0, off: false });
    let spots = [];
    function buildMarkers() {
      let h = "";
      built = clusters.length > CULL_AT ? viewBox(0.75) : null;
      const b = built;
      spots = [];
      clusters.forEach((c, ci) => {
        if (b && (c.X < b.x0 || c.X > b.x1 || c.Z < b.z0 || c.Z > b.z1) && c !== openCl) return;
        if (c.members.length === 1) {
          const it = c.members[0];
          h += markerHTML(it, selected && selected.item === it ? " sel" : "");
          spots.push(spot(it.X, it.Z));
        } else {
          const n = c.members.length;
          h += `<div class="cl${n >= 10 ? " big" : ""}${c === openCl ? " open" : ""}" data-cluster="${ci}" title="${n} locations - click to spread">${n}</div>`;
          spots.push(spot(c.X, c.Z));
        }
      });
      if (openCl) {
        const offs = spreadOffsets(openCl.members.length);
        openCl.offs = offs;
        openCl.members.forEach((m, k) => {
          h += markerHTML(m, " spread" + (selected && selected.item === m ? " sel" : "")).replace('class="mk', `data-spread="${k}" class="mk`);
          spots.push(spot(openCl.X, openCl.Z, offs[k]));
        });
      }
      mkEl.innerHTML = h;
      placedAt = NaN;                            // new elements: place them all, and the layer, afresh
    }

    function spreadOffsets(n) {                  // circle for small groups, spiral for big ones
      const out = [];
      if (n <= 10) {
        const r = Math.max(30, n * 27 / (2 * Math.PI));
        for (let k = 0; k < n; k++) { const a = -Math.PI / 2 + k * 2 * Math.PI / n; out.push([Math.cos(a) * r, Math.sin(a) * r]); }
      } else {
        let a = 0, r = 26;
        for (let k = 0; k < n; k++) { out.push([Math.cos(a) * r, Math.sin(a) * r]); const step = 27 / r; a += step; r += 27 * step / (2 * Math.PI) * 1.05; }
      }
      const k = SIZES[sizeIx];                    // bigger icons need more room
      return k === 1 ? out : out.map(([x, y]) => [x * k, y * k]);
    }

    // The markers all sit in one layer (#mapLayer, a zero-size box), and panning just moves the layer: a marker's own
    // transform is set again only when the scale changes, after a rebuild, or when it comes back on screen. Setting
    // the transform of every marker on every frame made the browser restyle hundreds of them while dragging the map.
    let placedAt = NaN, placeRun = 0, layerX = 0, layerY = 0, legsHTML = "";
    function placeMarkers() {
      const els = mkEl.children;
      if (s !== placedAt) { placedAt = s; placeRun++; layerX = tx; layerY = ty; }
      const lx = tx - layerX, ly = ty - layerY;  // how far the layer has moved since the markers were placed
      mkEl.style.transform = lx || ly ? `translate(${lx}px,${ly}px)` : "";
      let legs = "";
      for (let j = 0; j < els.length; j++) {
        const el = els[j], p = spots[j];
        let x = sx(p.X), y = sy(p.Z);
        if (p.o) {
          x += p.o[0]; y += p.o[1];
          legs += `<line x1="${sx(p.X)}" y1="${sy(p.Z)}" x2="${x}" y2="${y}"/>`;
        }
        const off = x < -40 || y < -40 || x > W + 40 || y > H + 40;
        if (off !== p.off) { p.off = off; el.style.display = off ? "none" : ""; }
        if (!off && p.at !== placeRun) { p.at = placeRun; el.style.transform = `translate(${x - lx}px,${y - ly}px)`; }   // off-screen ones aren't drawn anyway
      }
      if (legs !== legsHTML) legsEl.innerHTML = legsHTML = legs;
    }

    // ---------------- popup ----------------
    function itemScreenPos(sel) {
      if (sel.spread !== undefined && openCl && openCl.offs) {
        const o = openCl.offs[sel.spread]; return [sx(openCl.X) + o[0], sy(openCl.Z) + o[1]];
      }
      return [sx(sel.item.X), sy(sel.item.Z)];
    }
    // placed loot has its height too (the game's Y); copies stacked on one spot have several
    const heights = (y) => [].concat(y).map((v) => v.toFixed(2)).join(" / ");
    function openPopup(it, spread) {
      selected = { item: it, spread };
      const sb = subs[it.s], main = mains.find((m) => m.key === sb.main), reg = regions[it.r];
      const single = main && subsOf[main.key].length === 1;
      const meta = [main ? main.name : "", single ? "" : sb.name, reg ? reg.name : ""].filter(Boolean).map(esc).join(" · ");
      popEl.innerHTML = `<button class="px" title="Close">✕</button>
        <div class="pn">${esc(it.n)}</div>
        <div class="pc" title="Click to copy"><b>X</b><span>${it.x.toFixed(2)}</span>${it.y != null ? `<b>Y</b><span>${heights(it.y)}</span>` : ""}<b>Z</b><span>${it.z.toFixed(2)}</span></div>
        <div class="pm">${meta}${it.d ? ' · <span class="dlc">Alpine Unrest DLC</span>' : ""}${it.l ? "<br>" + esc(it.l) : ""}${sb.note ? `<br><span class="pnote">${esc(sb.note)}</span>` : ""}</div>`;
      popEl.hidden = false;
      popEl.querySelector(".px").onclick = (e) => { e.stopPropagation(); closePopup(); };
      popEl.querySelector(".pc").onclick = () => {
        if (String(getSelection()).trim()) return;      // selecting text to copy it: leave the selection alone
        const txt = it.y != null ? `${it.x.toFixed(2)}, ${[].concat(it.y)[0].toFixed(2)}, ${it.z.toFixed(2)}` : `${it.x.toFixed(2)}, ${it.z.toFixed(2)}`;
        try { navigator.clipboard.writeText(txt); } catch (_) { /* clipboard unavailable */ }
        const pc = popEl.querySelector(".pc"); const old = pc.innerHTML; pc.textContent = "Copied " + txt;
        setTimeout(() => { if (pc.isConnected) pc.innerHTML = old; }, 900);
      };
      mkEl.querySelectorAll(".mk.sel").forEach((e) => e.classList.remove("sel"));
      const sel = spread !== undefined ? mkEl.querySelector(`.mk[data-spread="${spread}"]`) : mkEl.querySelector(`.mk[data-item="${it.i}"]:not([data-spread])`);
      if (sel) sel.classList.add("sel");
      placePopup();
    }
    function closePopup() {
      selected = null; popEl.hidden = true;
      if (mkEl) mkEl.querySelectorAll(".mk.sel").forEach((e) => e.classList.remove("sel"));
    }
    function placePopup() {
      if (!selected || popEl.hidden) return;
      const [x, y] = itemScreenPos(selected);
      popEl.style.left = x + "px"; popEl.style.top = y + "px";
    }

    function collapseGroup() { if (openCl) { openCl = null; buildMarkers(); placeMarkers(); } }

    // ---------------- interaction ----------------
    function bindEvents() {
      let down = null;
      const coordsEl = qs("#mapCoords");
      // two fingers on a touch screen: pinch to zoom, and the pair pans the map as it moves
      const pts = new Map();
      let pinch = null;
      const pinchOf = () => {
        const [a, b] = [...pts.values()], r = stage.getBoundingClientRect();
        return { d: Math.hypot(a.x - b.x, a.y - b.y) || 1, x: (a.x + b.x) / 2 - r.left, y: (a.y + b.y) / 2 - r.top };
      };
      stage.addEventListener("pointerdown", (e) => {
        if (e.button !== 0 || e.target.closest(".maptools, .mappanelbtn, #mapPopup")) return;
        pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
        if (pts.size === 2) { down = null; stage.classList.remove("dragging"); pinch = pinchOf(); return; }
        if (pts.size > 2) return;
        down = { x: e.clientX, y: e.clientY, tx, ty, target: e.target, id: e.pointerId, drag: false };
        stage.focus({ preventScroll: true });
      });
      const lift = (e) => { pts.delete(e.pointerId); if (pts.size < 2) pinch = null; };
      stage.addEventListener("pointermove", (e) => {
        const r = stage.getBoundingClientRect();
        if (pts.has(e.pointerId)) pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
        if (pinch && pts.size >= 2) {
          const p = pinchOf();
          tx += p.x - pinch.x; ty += p.y - pinch.y;
          zoomAt(p.d / pinch.d, p.x, p.y);
          pinch = p;
          return;
        }
        const mx = e.clientX - r.left, my = e.clientY - r.top;
        const wx = ((mx - tx) / s - L3 / 2) / toL3, wz = ((my - ty) / s - L3 / 2) / toL3;
        coordsEl.textContent = `${wx.toFixed(3)}, ${wz.toFixed(3)}`;
        if (!down) return;
        const dx = e.clientX - down.x, dy = e.clientY - down.y;
        if (!down.drag && Math.hypot(dx, dy) > 4) { down.drag = true; stage.classList.add("dragging"); stage.setPointerCapture(down.id); }
        if (down.drag) { tx = down.tx + dx; ty = down.ty + dy; clamp(); schedule(); }
      });
      const up = (e) => {
        lift(e);
        if (!down) return;
        const d = down; down = null; stage.classList.remove("dragging");
        if (!d.drag) handleClick(d.target);
      };
      stage.addEventListener("pointerup", up);
      stage.addEventListener("pointercancel", (e) => { lift(e); down = null; stage.classList.remove("dragging"); });
      stage.addEventListener("pointerleave", () => { coordsEl.textContent = ""; });
      stage.addEventListener("wheel", (e) => {
        e.preventDefault();
        const r = stage.getBoundingClientRect();
        const dy = e.deltaMode === 1 ? e.deltaY * 40 : e.deltaY;
        zoomAt(Math.exp(-dy * 0.0016), e.clientX - r.left, e.clientY - r.top);
      }, { passive: false });
      stage.addEventListener("dblclick", (e) => {
        if (e.target.closest(".mk, .cl, .maptools, .mappanelbtn, #mapPopup")) return;
        const r = stage.getBoundingClientRect();
        zoomAt(2, e.clientX - r.left, e.clientY - r.top);
      });
      qs("#mapZoomIn").onclick = () => zoomAt(1.6);
      qs("#mapZoomOut").onclick = () => zoomAt(1 / 1.6);
      qs("#mapFit").onclick = () => { collapseGroup(); fitContent(); };
      qs("#mapBordersBtn").onclick = toggleBorders;
      qs("#mapSizeBtn").onclick = cycleSize;
      qs("#mapPanelBtn").onclick = () => setPanel(!panelOpen);
      document.addEventListener("keydown", (e) => {
        if (e.ctrlKey || e.metaKey || e.altKey) return;
        if (e.target.matches("input, select, textarea")) return;
        if (e.key === "+" || e.key === "=") zoomAt(1.6);
        else if (e.key === "-" || e.key === "_") zoomAt(1 / 1.6);
        else if (e.key === "0") { collapseGroup(); fitContent(); }
        else if (e.key === "b" || e.key === "B") toggleBorders();
        else if (e.key === "f" || e.key === "F") setPanel(!panelOpen);
        else if (e.key === "s" || e.key === "S") cycleSize();
        else if (e.key === "Escape") { closePopup(); collapseGroup(); }
      });
    }

    // ---------------- filters panel: collapse / expand ----------------
    // The map stage simply gets wider; the ResizeObserver keeps the view centred while it does.
    function setPanel(open) {
      panelOpen = open;
      qs("#mapView").classList.toggle("pclosed", !open);
      const b = qs("#mapPanelBtn");
      b.title = open ? "Hide the filters panel (F)" : "Show the filters panel (F)";
      b.setAttribute("aria-expanded", String(open));
      store.set("mapPanel", open);
    }

    // ---------------- icon size ----------------
    function applySize() {
      qs("#mapMarkers").style.setProperty("--mks", SIZES[sizeIx]);
      qs("#mapSizeLbl").textContent = (sizeIx + 1) + "x";
      qs("#mapSizeBtn").title = `Icon size: ${sizeIx + 1}x - click for ${(sizeIx + 1) % SIZES.length + 1}x (S)`;
    }
    function cycleSize() {
      sizeIx = (sizeIx + 1) % SIZES.length;
      store.set("mapIconSize2", sizeIx);
      applySize();
      needCluster = true; schedule();           // bigger icons group a little sooner, so they don't pile up
    }

    // ---------------- region borders overlay ----------------
    let bordersBuilt = false;
    function buildBorders() {
      bordersBuilt = true;
      const d = (D.regions || []).filter((r) => r.border).map((r) =>
        "M" + r.border.map(([x, z]) => `${(L3 / 2 + x * toL3).toFixed(1)} ${(L3 / 2 + z * toL3).toFixed(1)}`).join("L") + "Z").join("");
      qs("#mapBordersG").innerHTML = `<path class="bs" d="${d}"/><path class="bl" d="${d}"/>`;
    }
    function placeBorders() {
      qs("#mapBordersG").setAttribute("transform", `matrix(${s} 0 0 ${s} ${tx} ${ty})`);
    }
    function toggleBorders() {
      if (!D) return;
      showBorders = !showBorders;
      if (showBorders && !bordersBuilt) buildBorders();
      qs("#mapBorders").toggleAttribute("hidden", !showBorders);   // an <svg> has no .hidden property
      const b = qs("#mapBordersBtn");
      b.classList.toggle("on", showBorders); b.setAttribute("aria-pressed", String(showBorders));
      schedule();
    }

    function handleClick(target) {
      const mk = target.closest(".mk"), cl = target.closest(".cl");
      if (mk) {
        const it = items[+mk.dataset.item];
        const spread = mk.dataset.spread !== undefined ? +mk.dataset.spread : undefined;
        if (spread === undefined) collapseGroup();          // a normal marker closes an open group
        if (selected && selected.item === it && selected.spread === spread) closePopup();
        else openPopup(it, spread);
      } else if (cl) {
        const c = clusters[+cl.dataset.cluster];
        closePopup();
        openCl = openCl === c ? null : c;
        buildMarkers(); placeMarkers();
      } else {                                               // empty map: close everything
        closePopup(); collapseGroup();
      }
    }

    // ---------------- side panel ----------------
    function buildPanel() {
      // regions first: a filter across every category
      const R = D.regions || [];
      let advOpen = false;
      let h = R.length ? `<section class="mcat mreg${collapsed.regions ? " closed" : ""}" data-main="regions">
          <div class="mcat-h" data-collapse="regions"><span class="chev"></span>
            <span class="tick" data-tickregions title="Tick / untick all regions"></span>
            <span class="t">REGIONS</span><span class="n" data-mcount="regions"></span></div>
          <div class="mcat-b">` +
          R.map((r, i) => `<div class="msub mrow" data-region="${r.key}" title="${esc(r.name)}">
              <span class="tick"></span><span class="rb${i >= 7 ? " dlc" : ""}">${i < 7 ? i + 1 : "DLC"}</span><span class="t">${esc(r.name)}</span>
              <span class="n" data-rcount="${r.key}"></span><span></span></div>`).join("") +
          `</div></section>` : "";
      let group = null;
      for (const m of mains) {
        const list = subsOf[m.key] || [];
        // a separator line between the regions and the categories, and between groups of categories
        if (m.adv && !advOpen) { h += `<div class="madvcats" id="mapAdvCats"${adv ? "" : " hidden"}>`; advOpen = true; }
        if (m.wide) h += `<div class="mwide"></div>`;     // the side missions: the wide rule, as above the placed loot
        else if ((h && group === null) || (group !== null && m.group !== group)) h += `<div class="msep"></div>`;
        group = m.group;
        if (list.length === 1) {           // a category with a single entry: just its header, no list to open
          const sb = list[0];
          h += `<section class="mcat single" data-main="${m.key}">
            <div class="mcat-h msub" data-sub="${sb.key}" title="${esc(sb.name)}"><img class="ic" src="${sb.icon}" alt="">
              <span class="tick" data-tickmain="${m.key}"></span>
              <span class="t">${esc(m.name.toUpperCase())}</span><span class="n" data-mcount="${m.key}"></span></div></section>`;
          continue;
        }
        h += `<section class="mcat${collapsed[m.key] ? " closed" : ""}" data-main="${m.key}">
          <div class="mcat-h" data-collapse="${m.key}"><span class="chev"></span>
            <span class="tick" data-tickmain="${m.key}" title="Tick / untick all"></span>
            <span class="t">${esc(m.name.toUpperCase())}</span><span class="n" data-mcount="${m.key}"></span></div>
          <div class="mcat-b">` +
          list.map((sb) => `<div class="msub" data-sub="${sb.key}" title="${esc(sb.name)}">
              <span class="tick"></span><img src="${sb.icon}" alt="" loading="lazy"><span class="t">${esc(sb.name)}</span>
              <span class="n" data-scount="${sb.key}"></span><span class="gl" style="--g:url('${sb.glyph}')"></span></div>`).join("") +
          `</div></section>`;
      }
      if (advOpen) h += `</div>`;
      const cats = qs("#mapCats");
      cats.innerHTML = h;
      // the rows and counters updatePanel() fills in, found once per build instead of once per update
      const by = (sel, attr) => { const o = {}; cats.querySelectorAll(sel).forEach((e) => { if (!(e.dataset[attr] in o)) o[e.dataset[attr]] = e; }); return o; };
      panelEls = { sub: by(".msub[data-sub]", "sub"), scount: by("[data-scount]", "scount"), tickmain: by("[data-tickmain]", "tickmain"),
        mcount: by("[data-mcount]", "mcount"), region: by("[data-region]", "region"), rcount: by("[data-rcount]", "rcount"),
        tickregions: cats.querySelector("[data-tickregions]") };
      updatePanel();
    }
    let panelEls = null;

    // the subs the panel shows right now (the placed loot ones only in advanced mode)
    const listed = () => D.subs.filter((sb) => adv || !sb.adv);
    function bindPanel() {
      const R = D.regions || [];
      const cats = qs("#mapCats");
      cats.addEventListener("click", (e) => {
        if (e.target.closest("[data-tickregions]")) {
          const allOn = R.every((r) => regionOn[r.key]);
          R.forEach((r) => { regionOn[r.key] = !allOn; });
          return filtersChanged();
        }
        const tm = e.target.closest("[data-tickmain]");
        if (tm) {
          const list = subsOf[tm.dataset.tickmain] || [];
          const allOn = list.every((sb) => enabled[sb.key]);
          list.forEach((sb) => { enabled[sb.key] = !allOn; });
          return filtersChanged();
        }
        const col = e.target.closest("[data-collapse]");
        if (col) {
          const k = col.dataset.collapse; collapsed[k] = !collapsed[k];
          col.parentElement.classList.toggle("closed", collapsed[k]); store.set("mapCollapsed2", collapsed);
          return;
        }
        const rg = e.target.closest("[data-region]");
        if (rg) { regionOn[rg.dataset.region] = !regionOn[rg.dataset.region]; return filtersChanged(); }
        const row = e.target.closest("[data-sub]");
        if (row) { enabled[row.dataset.sub] = !enabled[row.dataset.sub]; filtersChanged(); }
      });
      qs("#mapAll").onclick = () => {
        listed().forEach((sb) => { enabled[sb.key] = true; }); R.forEach((r) => { regionOn[r.key] = true; }); filtersChanged();
      };
      qs("#mapNone").onclick = () => { listed().forEach((sb) => { enabled[sb.key] = false; }); filtersChanged(); };
      qs("#mapAdv").onclick = () => setAdv(!adv);
    }

    // ---------------- advanced mode: placed loot ----------------
    function applyAdv() {
      const b = qs("#mapAdv");
      b.classList.toggle("on", adv);
      b.setAttribute("aria-pressed", String(adv));
      b.title = adv ? "Extra Locations is on: the placed loot categories are in the list - click to remove them"
        : "Extra Locations: add the placed loot (weapons, items, materials, crates) to the list, each one off until ticked";
      const c = qs("#mapAdvCats");
      if (c) c.hidden = !adv;
      maxS = adv ? MAX_S_ADV : MAX_S;
      if (stage && W) { clamp(); schedule(); }
    }
    function setAdv(on) {
      adv = on; store.set("mapAdvanced", adv);
      applyAdv();
      if (adv) loadLoot();
      if (D) filtersChanged();
    }
    const LOOT_V = 5;   // bump when map/loot.json or its icons change
    function loadLoot() {
      if (lootLoad) return lootLoad;
      const b = qs("#mapAdv");
      b.classList.add("busy");
      lootLoad = fetch("map/loot.json?v=" + LOOT_V).then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }).then((L) => {
        const saved = store.get("mapEnabled", null) || {};
        const mainsL = L.mains.map((m) => ({ ...m, adv: true }));
        const bust = (u) => u && u + "?v=" + LOOT_V;   // icons keep their names between updates: don't let the browser reuse old ones
        const subsL = L.subs.map((sb) => ({ ...sb, glyph: bust(sb.glyph), icon: bust(sb.icon), adv: true }));
        mains = D.mains = [...D.mains, ...mainsL];
        D.subs = [...D.subs, ...subsL];
        subsL.forEach((sb) => {
          subs[sb.key] = sb; (subsOf[sb.main] = subsOf[sb.main] || []).push(sb);
          enabled[sb.key] = LINK.show.length ? LINK.show.includes(sb.key) : sb.key in saved ? !!saved[sb.key] : false;
          if (enabled[sb.key] && LINK.show.length) collapsed[sb.main] = false;
        });
        mainsL.forEach((m) => { if (!(m.key in collapsed)) collapsed[m.key] = true; });
        const base = items.length;
        L.items.forEach(([si, x, z, ni, ri, y], k) => {
          const sb = subsL[si];
          items.push({ s: sb.key, n: L.names[ni], x, y, z, r: L.regions[ri], d: L.regions[ri] === "alpine" ? 1 : 0, adv: 1, i: base + k,
            X: L3 / 2 + x * toL3, Z: L3 / 2 + z * toL3 });
        });
        buildPanel();
        filtersChanged();
      }).catch(() => {
        lootLoad = null;
        b.title = "Couldn't load map/loot.json";
      }).finally(() => b.classList.remove("busy"));
      return lootLoad;
    }

    const triState = (on, all) => "tick" + (on === all ? " on" : on ? " part" : "");

    function updatePanel() {
      // counts follow the other filter: a category shows how many it has in the ticked regions, a region how
      // many it has in the ticked categories
      const inReg = {}, inCat = {}, P = panelEls;
      if (!P) return;                            // the panel isn't built yet (the map is still starting)
      let shown = 0, all = 0;
      for (const it of items) {                  // one pass over every marker (tens of thousands with the placed loot)
        if (it.adv && !adv) continue;
        all++;
        const rOn = regionOn[it.r] !== false, eOn = enabled[it.s];
        if (rOn) inReg[it.s] = (inReg[it.s] || 0) + 1;
        if (eOn) inCat[it.r] = (inCat[it.r] || 0) + 1;
        if (eOn && rOn) shown++;
      }
      for (const sb of D.subs) {
        const row = P.sub[sb.key];
        if (!row) continue;
        row.classList.toggle("off", !enabled[sb.key]);
        const c = P.scount[sb.key];
        if (c) { c.textContent = inReg[sb.key] || 0; row.querySelector(".tick").className = "tick" + (enabled[sb.key] ? " on" : ""); }
      }
      for (const m of mains) {
        const list = subsOf[m.key] || [];
        const on = list.filter((sb) => enabled[sb.key]);
        const shownM = on.reduce((a, sb) => a + (inReg[sb.key] || 0), 0), total = list.reduce((a, sb) => a + (inReg[sb.key] || 0), 0);
        P.tickmain[m.key].className = triState(on.length, list.length);
        P.mcount[m.key].textContent = `${shownM}/${total}`;
      }
      const R = D.regions || [];
      if (R.length) {
        for (const r of R) {
          const row = P.region[r.key];
          row.classList.toggle("off", !regionOn[r.key]);
          row.querySelector(".tick").className = "tick" + (regionOn[r.key] ? " on" : "");
          P.rcount[r.key].textContent = inCat[r.key] || 0;
        }
        const on = R.filter((r) => regionOn[r.key]);
        P.tickregions.className = triState(on.length, R.length);
        P.mcount.regions.textContent = `${on.length}/${R.length}`;
      }
      qs("#mapCount").textContent = `Showing ${shown} of ${all}`;
    }

    function filtersChanged() {
      store.set("mapEnabled", { ...(store.get("mapEnabled", null) || {}), ...enabled });   // keeps the loot ones while they aren't loaded
      store.set("mapRegions", regionOn);
      visCache = null;
      updatePanel();
      needCluster = true; openCl = null;
      if (selected && !isVis(selected.item)) closePopup();
      schedule();
    }

    return {
      show() { if (!started) start(); else schedule(); },
      // for testing
      _state: () => ({ s, tx, ty, W, H, clusters: clusters.length, open: openCl ? openCl.members.length : 0,
        borders: showBorders, panel: panelOpen, size: sizeIx, tiles: [...tilesEl.children].map((i) => i.src.split("/tiles/")[1]), selected: selected ? selected.item.n : null }),
      _worldToScreen: (x, z) => [sx(L3 / 2 + x * toL3), sy(L3 / 2 + z * toL3)],
      _zoomAt: zoomAt, _items: () => items,
      _center(x, z, scale) { s = scale; tx = W / 2 - (L3 / 2 + x * toL3) * s; ty = H / 2 - (L3 / 2 + z * toL3) * s; clamp(); needCluster = true; schedule(); },
    };
  })();
  window.MapView = MapView;
  // phones start with the filters panel closed, so the map is what they see first
  if (matchMedia("(max-width: 760px)").matches && store.get("mapPanel", null) === null) store.set("mapPanel", false);
  MapView.show();
})();
