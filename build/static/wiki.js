/* Gen0 Wiki: search, sortable and filterable tables, in-page tabs, mini maps, menu and keys. No dependencies. */
"use strict";
(function () {
  const ROOT = document.body.dataset.root || "";
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => Array.from(el.querySelectorAll(s));
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"})[c]);
  const fold = s => String(s || "").normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase();

  // ------------------------------------------------------------------ menu (narrow screens)
  const menuBtn = $("#menuBtn"), tabs = $("#tabs");
  if (menuBtn) menuBtn.onclick = () => { const o = tabs.classList.toggle("open"); menuBtn.setAttribute("aria-expanded", o); };

  // ------------------------------------------------------------------ search
  const q = $("#q"), box = $("#results");
  let index = null, sel = -1, hits = [];
  async function load() {
    if (index) return index;
    try { const r = await fetch(ROOT + "assets/search.json"); index = await r.json(); }
    catch (e) { index = []; }
    index.forEach(e => { e._t = fold(e.t); e._all = fold(e.t + " " + e.k + " " + (e.w || "") + " " + (e.d || "")); });
    return index;
  }
  function score(e, words, phrase) {
    let s = 0;
    for (const w of words) {
      if (!e._all.includes(w)) return -1;
      if (e._t.startsWith(w)) s += 6; else if (e._t.includes(" " + w)) s += 4; else if (e._t.includes(w)) s += 2; else s += 1;
    }
    if (e._t === phrase) s += 30; else if (e._t.startsWith(phrase)) s += 12; else if (e._t.includes(phrase)) s += 6;
    return s - e._t.length / 200;
  }
  async function search() {
    const phrase = fold(q.value.trim());
    if (!phrase) { box.hidden = true; return; }
    await load();
    const words = phrase.split(/\s+/);
    hits = index.map(e => [score(e, words, phrase), e]).filter(x => x[0] >= 0).sort((a, b) => b[0] - a[0]).slice(0, 30).map(x => x[1]);
    sel = hits.length ? 0 : -1;
    box.innerHTML = hits.length ? hits.map((e, i) => `<a href="${ROOT + e.u}" class="${i === sel ? "sel" : ""}">${e.i ? `<img src="${ROOT + e.i}" alt="" loading="lazy">` : ""}<span><span class="rk">${esc(e.k)}</span><span class="rt">${esc(e.t)}</span>${e.d ? `<span class="rd">${esc(e.d)}</span>` : ""}</span></a>`).join("")
      : `<div class="rnone">Nothing found for “${esc(q.value)}”.</div>`;
    box.hidden = false;
  }
  // the field is closed to an icon; the icon (or "/") opens it, Escape or a click elsewhere on an empty field closes it
  const sbox = $("#search"), sbtn = $("#searchBtn");
  function openSearch() {
    if (!sbox) return;
    sbox.classList.add("open"); sbtn.setAttribute("aria-expanded", "true"); q.focus(); load();
  }
  function closeSearch() {
    if (!sbox) return;
    sbox.classList.remove("open"); sbtn.setAttribute("aria-expanded", "false"); box.hidden = true; q.blur();
  }
  if (sbtn) sbtn.addEventListener("click", () => {
    if (!sbox.classList.contains("open")) openSearch();
    else if (q.value.trim()) { search(); q.focus(); }
    else closeSearch();
  });
  if (q) {
    q.addEventListener("input", search);
    q.addEventListener("focus", () => { if (q.value) search(); load(); });
    q.addEventListener("keydown", e => {
      const links = $$("a", box);
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault(); if (!links.length) return;
        sel = (sel + (e.key === "ArrowDown" ? 1 : -1) + links.length) % links.length;
        links.forEach((a, i) => a.classList.toggle("sel", i === sel)); links[sel].scrollIntoView({block: "nearest"});
      } else if (e.key === "Enter" && links[sel]) { location.href = links[sel].href; }
      else if (e.key === "Escape") closeSearch();
    });
    document.addEventListener("click", e => {
      if (e.target.closest(".search")) return;
      box.hidden = true;
      if (!q.value.trim()) closeSearch();
    });
  }
  document.addEventListener("keydown", e => {
    if (e.target.closest("input, textarea, select") || e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.key === "/") { e.preventDefault(); openSearch(); }
    else if (e.key === "h" || e.key === "H") location.href = ROOT + "index.html";
    else if (e.key === "m" || e.key === "M") location.href = ROOT + "map/index.html";
  });

  // ------------------------------------------------------------------ sortable tables
  function cellVal(td) {
    if (!td) return "";
    if (td.dataset.v !== undefined) { const v = parseFloat(td.dataset.v); return isNaN(v) ? fold(td.dataset.v) : v; }
    const t = td.textContent.trim();
    const n = t.replace(/[,%×x]/g, "").replace(/^[–-]$/, "");
    if (n !== "" && !isNaN(n)) return parseFloat(n);
    return fold(t);
  }
  $$("table.wt.sortable").forEach(t => {
    const ths = $$("thead th", t);
    ths.forEach((th, i) => th.addEventListener("click", () => {
      const asc = !th.classList.contains("asc");
      ths.forEach(h => h.classList.remove("asc", "desc"));
      th.classList.add(asc ? "asc" : "desc");
      const body = t.tBodies[0], rows = Array.from(body.rows);
      rows.sort((a, b) => {
        const x = cellVal(a.cells[i]), y = cellVal(b.cells[i]);
        const nx = typeof x === "number", ny = typeof y === "number";
        let r = nx && ny ? x - y : nx ? -1 : ny ? 1 : String(x).localeCompare(String(y));
        return asc ? r : -r;
      });
      rows.forEach(r => body.appendChild(r));
    }));
  });

  // ------------------------------------------------------------------ filters: <div class="filterbar" data-for="tableId"> with an
  // <input> (text filter) and/or .chip buttons with data-f="value" matched against each row's data-f="a b c"
  $$(".filterbar[data-for]").forEach(fb => {
    const target = document.getElementById(fb.dataset.for);
    if (!target) return;
    const rows = () => $$("tbody tr, .fitem", target);
    const input = $("input", fb), chips = $$(".chip", fb), count = $(".count", fb);
    const groups = {};
    chips.forEach(c => { (groups[c.dataset.g || "_"] ||= []).push(c); });
    function apply() {
      const words = input ? fold(input.value.trim()).split(/\s+/).filter(Boolean) : [];
      const active = Object.values(groups).map(g => g.filter(c => c.classList.contains("on")).map(c => c.dataset.f)).filter(a => a.length && !a.includes("*"));
      let n = 0;
      rows().forEach(r => {
        const text = r._t || (r._t = fold(r.textContent + " " + (r.dataset.w || "")));
        const tags = (r.dataset.f || "").split(" ");
        const ok = words.every(w => text.includes(w)) && active.every(a => a.some(f => tags.includes(f)));
        r.classList.toggle("hidden", !ok); r.style.display = ok ? "" : "none";
        if (ok) n++;
      });
      if (count) count.textContent = `${n} shown`;
    }
    chips.forEach(c => c.addEventListener("click", () => {
      const g = groups[c.dataset.g || "_"];
      if (c.dataset.f === "*") g.forEach(x => x.classList.toggle("on", x === c));
      else {
        c.classList.toggle("on");
        const all = g.find(x => x.dataset.f === "*");
        if (all) all.classList.toggle("on", !g.some(x => x !== all && x.classList.contains("on")));
      }
      apply();
    }));
    if (input) input.addEventListener("input", apply);
    const pre = new URLSearchParams(location.search).get("f");
    if (pre && input) input.value = pre;
    apply();
  });

  // ------------------------------------------------------------------ in-page tabs: <div class="tabset"><div class="tsbtns"><button>..</button></div><div class="tspane">..</div>..
  $$(".tabset").forEach(ts => {
    const btns = $$(":scope > .tsbtns > button", ts), panes = $$(":scope > .tspane", ts);
    const show = i => { btns.forEach((b, j) => b.classList.toggle("on", i === j)); panes.forEach((p, j) => p.classList.toggle("on", i === j)); };
    btns.forEach((b, i) => b.addEventListener("click", () => show(i)));
    show(Math.max(0, btns.findIndex(b => b.classList.contains("on"))));
  });

  // ------------------------------------------------------------------ collapsible sections (<details class="fold">)
  // A link to a section (contents bar, #hash, search result) opens every fold around it first.
  function openTo(id, scroll) {
    let el = null;
    try { el = id && document.getElementById(decodeURIComponent(id)); } catch (e) { el = null; }
    if (!el) return false;
    for (let d = el.closest("details"); d; d = d.parentElement && d.parentElement.closest("details")) d.open = true;
    if (scroll) el.scrollIntoView({block: "start"});
    return true;
  }
  document.addEventListener("click", e => {
    const a = e.target.closest('a[href^="#"]');
    if (!a || a.getAttribute("href").length < 2) return;
    const id = a.getAttribute("href").slice(1);
    if (openTo(id, true)) { e.preventDefault(); history.replaceState(null, "", "#" + id); closeToc(); }
  });
  window.addEventListener("hashchange", () => openTo(location.hash.slice(1), true));
  if (location.hash) requestAnimationFrame(() => openTo(location.hash.slice(1), true));
  // "open all / close all" for a group of folds: <div class="foldall" data-for="id"></div> (the folds inside #id)
  $$(".foldall").forEach(fa => {
    const scope = fa.dataset.for ? document.getElementById(fa.dataset.for) : fa.parentElement;
    if (!scope) return;
    fa.innerHTML = '<button type="button" data-o="1">Open all</button><button type="button" data-o="0">Close all</button>';
    fa.addEventListener("click", e => {
      const b = e.target.closest("button"); if (!b) return;
      $$("details.fold", scope).forEach(d => { d.open = b.dataset.o === "1"; });
    });
  });
  // a filter box whose rows sit inside closed folds opens those folds while something is typed
  document.addEventListener("input", e => {
    const fb = e.target.closest(".filterbar[data-for]"); if (!fb) return;
    const t = document.getElementById(fb.dataset.for); if (!t) return;
    const on = e.target.value.trim() !== "";
    $$("details.fold", t).forEach(d => {
      if (on) { if (!d.open) { d.open = true; d._auto = true; } }
      else if (d._auto) { d.open = false; d._auto = false; }
    });
  });

  // ------------------------------------------------------------------ contents bar: highlight the section on screen
  const toc = $(".rail .toc");
  function closeToc() { if (toc) toc.classList.remove("open"); }
  if (toc) {
    const links = $$("a", toc);
    const heads = links.map(a => document.getElementById(decodeURIComponent(a.getAttribute("href").slice(1))));
    let ticking = false;
    const spy = () => {
      ticking = false;
      let cur = 0;
      heads.forEach((h, i) => { if (h && h.getBoundingClientRect().top < 150) cur = i; });
      if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4) cur = heads.length - 1;
      links.forEach((a, i) => a.classList.toggle("on", i === cur));
      const on = links[cur];
      if (on && toc.scrollHeight > toc.clientHeight) {
        const r = on.offsetTop - toc.scrollTop;
        if (r < 30 || r > toc.clientHeight - 30) toc.scrollTop = on.offsetTop - toc.clientHeight / 2;
      }
    };
    window.addEventListener("scroll", () => { if (!ticking) { ticking = true; requestAnimationFrame(spy); } }, {passive: true});
    document.addEventListener("toggle", () => requestAnimationFrame(spy), true);
    spy();
    // narrow screens: the contents bar opens from a button in the corner
    const btn = document.createElement("button");
    btn.type = "button"; btn.className = "tocbtn"; btn.setAttribute("aria-label", "Contents");
    btn.innerHTML = '<svg viewBox="0 0 20 20"><path d="M2 4h3v2H2zm5 0h11v2H7zM2 9h3v2H2zm5 0h11v2H7zm-5 5h3v2H2zm5 0h11v2H7z"/></svg>Contents';
    btn.onclick = e => { e.stopPropagation(); toc.classList.toggle("open"); };
    document.body.appendChild(btn);
    document.addEventListener("click", e => { if (!e.target.closest(".toc, .tocbtn")) closeToc(); });
  }

  // ------------------------------------------------------------------ switcher: <div class="switcher"><div class="swpanes">
  // <div class="swpane">..</div>..</div><div class="swbtns"><button>..</button>..</div></div> (buttons with .swx do nothing)
  $$(".switcher").forEach(sw => {
    const panes = $$(":scope > .swpanes > .swpane", sw), btns = $$(":scope > .swbtns > button:not(.swx)", sw);
    btns.forEach((b, i) => b.addEventListener("click", () => {
      btns.forEach((x, j) => x.classList.toggle("on", i === j)); panes.forEach((p, j) => p.classList.toggle("on", i === j));
    }));
  });

  // ------------------------------------------------------------------ mini maps (img/mm: the interactive map's tiles
  // cut into 1024 px tiles by tools/optimize.py, plus a level 0 with the whole world in one 2048 px picture)
  // world units -> level-3 pixels: 8192 + x / 2 (world 32768 units across, 16384 px)
  const LEVELS = {0: {px: 2048, n: 1, t: 2048}, 1: {px: 4096, n: 4, t: 1024}, 2: {px: 8192, n: 8, t: 1024}, 3: {px: 16384, n: 16, t: 1024}};
  const DPR = Math.min(2, window.devicePixelRatio || 1);
  // A map inside a closed fold has no size yet, so each one starts the first time it is shown.
  function startMap(mm) {
    let pts; try { pts = JSON.parse(mm.dataset.pts); } catch (e) { return; }
    const layer = document.createElement("div"); layer.className = "mmlayer"; mm.prepend(layer);
    const zoom = document.createElement("div"); zoom.className = "mmzoom";
    zoom.innerHTML = '<button type="button" aria-label="Zoom in">+</button><button type="button" aria-label="Zoom out">−</button>';
    mm.appendChild(zoom);
    let lvl = Math.min(3, Math.max(1, +mm.dataset.zoom || 3));
    const MINS = 0.012;   // lowest zoom: the whole 16384px world in ~200px
    // centre in level-3 pixels; scale = screen px per level-3 px
    const cx0 = pts.reduce((s, p) => s + p[0], 0) / pts.length, cz0 = pts.reduce((s, p) => s + p[1], 0) / pts.length;
    let cx = 8192 + cx0 / 2, cz = 8192 + cz0 / 2, scale = LEVELS[lvl].px / 16384;
    if (pts.length > 1) {
      const xs = pts.map(p => 8192 + p[0] / 2), zs = pts.map(p => 8192 + p[1] / 2);
      // fit every point with ~28px of screen space around them; small overview maps may show the whole world
      const w = Math.max(200, Math.max(...xs) - Math.min(...xs)), h = Math.max(200, Math.max(...zs) - Math.min(...zs));
      scale = Math.min(1, Math.max(MINS, Math.min((mm.clientWidth - 56) / w, (mm.clientHeight - 56) / h)));
      cx = (Math.max(...xs) + Math.min(...xs)) / 2; cz = (Math.max(...zs) + Math.min(...zs)) / 2;
    }
    const tiles = {};
    function draw() {
      const W = mm.clientWidth, H = mm.clientHeight;
      // level 0 only while it is drawn at about half size or less (sharp on high-DPI screens too)
      const L = scale > 0.5 ? 3 : scale > 0.2 ? 2 : scale * DPR > 0.07 ? 1 : 0, info = LEVELS[L], f = info.px / 16384;  // level px per level-3 px
      const s = scale / f, T = info.t;   // screen px per level-L px; tile size
      layer.style.transform = `translate(${W / 2 - cx * scale}px, ${H / 2 - cz * scale}px) scale(${s})`;
      layer.style.setProperty("--ov", (1.5 / s).toFixed(2) + "px");   // tiles overlap by 1.5 screen px: no hairline seams
      const x0 = (cx * scale - W / 2) / s, x1 = (cx * scale + W / 2) / s, z0 = (cz * scale - H / 2) / s, z1 = (cz * scale + H / 2) / s;
      for (const k in tiles) tiles[k].style.display = k.startsWith(L + "/") ? "" : "none";
      for (let i = Math.max(0, Math.floor(x0 / T)); i <= Math.min(info.n - 1, Math.floor(x1 / T)); i++)
        for (let j = Math.max(0, Math.floor(z0 / T)); j <= Math.min(info.n - 1, Math.floor(z1 / T)); j++) {
          const k = `${L}/${i}_${j}`;
          if (!tiles[k]) {
            const im = document.createElement("img"); im.alt = ""; im.draggable = false;
            im.src = `${ROOT}img/mm/${k}.webp`; im.style.left = i * T + "px"; im.style.top = j * T + "px";
            im.style.width = im.style.height = `calc(${T}px + var(--ov, 0px))`;
            layer.appendChild(im); tiles[k] = im;
          }
        }
      pins.forEach(p => { p.el.style.left = (W / 2 + (p.x - cx) * scale) + "px"; p.el.style.top = (H / 2 + (p.z - cz) * scale) + "px";
        if (p.lb) { p.lb.style.left = p.el.style.left; p.lb.style.top = p.el.style.top; } });
    }
    const pins = pts.map((p, i) => {
      const el = document.createElement("div"); el.className = "mmpin" + (i ? " sec" : ""); el.title = p[2] || "";
      mm.appendChild(el);
      let lb = null;
      if (p[2] && (i === 0 || pts.length <= 12)) { lb = document.createElement("div"); lb.className = "mmlabel"; lb.textContent = p[2]; mm.appendChild(lb); }
      return {x: 8192 + p[0] / 2, z: 8192 + p[1] / 2, el, lb};
    });
    const zoomBy = f => { scale = Math.min(2, Math.max(MINS, scale * f)); draw(); };
    const [zi, zo] = $$("button", zoom); zi.onclick = () => zoomBy(1.6); zo.onclick = () => zoomBy(1 / 1.6);
    let drag = null;
    mm.addEventListener("pointerdown", e => { if (e.target.closest("button, a")) return; drag = {x: e.clientX, y: e.clientY, cx, cz}; mm.setPointerCapture(e.pointerId); });
    mm.addEventListener("pointermove", e => { if (!drag) return; cx = drag.cx - (e.clientX - drag.x) / scale; cz = drag.cz - (e.clientY - drag.y) / scale; draw(); });
    mm.addEventListener("pointerup", () => { drag = null; });
    mm.addEventListener("wheel", e => { e.preventDefault(); zoomBy(e.deltaY < 0 ? 1.25 : 0.8); }, {passive: false});
    new ResizeObserver(draw).observe(mm);
    draw();
  }
  const mmWatch = new ResizeObserver(entries => entries.forEach(en => {
    const mm = en.target;
    if (mm._started || !mm.clientWidth || !mm.clientHeight) return;
    mm._started = true; mmWatch.unobserve(mm); startMap(mm);
  }));
  $$(".minimap").forEach(mm => mmWatch.observe(mm));
})();
