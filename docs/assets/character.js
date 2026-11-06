/* Character section: the skill menu (tree tabs, skill details, point planner) and links into in-page tabs. */
(() => {
  const $ = (s, r = document) => r.querySelector(s), $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

  // ---------------------------------------------------------------- links to something inside a hidden tab pane
  // (.tabset from wiki.js): switch to that pane first.
  function showTabOf(el) {
    for (let p = el.closest(".tspane"); p; p = p.parentElement && p.parentElement.closest(".tspane")) {
      const ts = p.parentElement, panes = $$(":scope > .tspane", ts), i = panes.indexOf(p);
      const b = $$(":scope > .tsbtns > button", ts)[i];
      if (b && !p.classList.contains("on")) b.click();
    }
  }

  // ---------------------------------------------------------------- skill menu
  const menu = $("#skmenu");
  let ranks = {};
  const KEY = "gz-skill-plan";
  if (menu) {
    menu.classList.add("js");
    try { ranks = JSON.parse(localStorage.getItem(KEY) || "{}") || {}; } catch (e) { ranks = {}; }
    const tabs = $$(".sktabs button", menu), panes = $$(".skpane", menu);
    const nodes = $$(".sknd", menu), byId = {};
    nodes.forEach(n => { byId[n.dataset.s] = n; });

    const showTree = key => {
      tabs.forEach(b => b.classList.toggle("on", b.dataset.t === key));
      panes.forEach(p => p.classList.toggle("on", p.dataset.t === key));
    };
    const select = (id, scroll) => {
      const n = byId[id]; if (!n) return false;
      const pane = n.closest(".skpane");
      showTree(pane.dataset.t);
      $$(".sknd", pane).forEach(x => x.classList.toggle("sel", x === n));
      $$(".skd", pane).forEach(d => d.classList.toggle("on", d.dataset.s === id));
      if (scroll) {
        const d = $(`.skd[data-s="${id}"]`, pane), r = d.getBoundingClientRect();
        if (r.top > innerHeight * .75 || r.top < 60) d.scrollIntoView({block: "nearest", behavior: "smooth"});
      }
      return true;
    };
    const locked = n => n.dataset.par && !(ranks[n.dataset.par] > 0);
    const render = () => {
      nodes.forEach(n => {
        const r = ranks[n.dataset.s] || 0, max = +n.dataset.max, lk = locked(n);
        n.classList.toggle("learned", r > 0); n.classList.toggle("full", r >= max); n.classList.toggle("locked", !!lk);
        n.classList.toggle("lit", !!n.dataset.par && ranks[n.dataset.par] > 0);
        $$(".skpips i", n).forEach((p, j) => p.classList.toggle("on", j < r));
        const d = $(`.skd[data-s="${n.dataset.s}"]`, menu);
        if (d) {
          $(".skrk", d).textContent = `${r} / ${max}`;
          $('[data-d="-1"]', d).disabled = r <= 0;
          $('[data-d="1"]', d).disabled = r >= max || lk;
          d.classList.toggle("locked", !!lk);
          $$(".sklv li", d).forEach(li => li.classList.toggle("on", +li.dataset.l <= r));
        }
      });
      panes.forEach(p => {
        const spent = $$(".sknd", p).reduce((a, n) => a + (ranks[n.dataset.s] || 0), 0);
        $(".skspent", p).textContent = spent;
      });
      try { localStorage.setItem(KEY, JSON.stringify(ranks)); } catch (e) { /* private mode: no memory */ }
    };
    const setRank = (id, r) => {
      const n = byId[id]; if (!n) return;
      ranks[id] = Math.max(0, Math.min(+n.dataset.max, r));
      if (!ranks[id]) {          // taking the last point out locks everything below it
        delete ranks[id];
        nodes.filter(c => c.dataset.par === id).forEach(c => setRank(c.dataset.s, 0));
      }
    };
    // drop anything the saved plan can't have (locked skills with points)
    Object.keys(ranks).forEach(id => { if (!byId[id]) delete ranks[id]; });
    nodes.forEach(n => { if (locked(n)) setRank(n.dataset.s, 0); });

    tabs.forEach(b => b.addEventListener("click", () => {
      showTree(b.dataset.t);
      const sel = $(".sknd.sel", $(`.skpane[data-t="${b.dataset.t}"]`, menu));
      if (sel) history.replaceState(null, "", "#" + sel.id);
    }));
    nodes.forEach(n => n.addEventListener("click", () => { select(n.dataset.s, true); history.replaceState(null, "", "#" + n.id); }));
    nodes.forEach(n => n.addEventListener("dblclick", e => {       // double click: add a point, like the game
      e.preventDefault(); if (!locked(n)) { setRank(n.dataset.s, (ranks[n.dataset.s] || 0) + 1); render(); }
    }));
    $$(".skd", menu).forEach(d => d.addEventListener("click", e => {
      const b = e.target.closest("button[data-d]"); if (!b) return;
      setRank(d.dataset.s, (ranks[d.dataset.s] || 0) + +b.dataset.d); render();
    }));
    $$(".skreset", menu).forEach(b => b.addEventListener("click", () => {
      $$(".sknd", b.closest(".skpane")).forEach(n => delete ranks[n.dataset.s]); render();
    }));
    // tree links in the side panel
    $$("a[data-tree]").forEach(a => a.addEventListener("click", e => {
      e.preventDefault(); e.stopPropagation(); showTree(a.dataset.tree);
      menu.scrollIntoView({block: "start", behavior: "smooth"});
    }));
    render();
    window.__skSelect = select;
  }

  // ---------------------------------------------------------------- #links: skills, and targets in hidden tab panes
  function go(id, scroll) {
    let el = null;
    try { el = id && document.getElementById(decodeURIComponent(id)); } catch (e) { el = null; }
    if (!el) return false;
    if (menu && el.classList.contains("sknd")) {
      window.__skSelect(el.dataset.s, false);
      if (scroll) menu.scrollIntoView({block: "start"});
      return true;
    }
    if (el.closest(".tspane:not(.on)")) {
      showTabOf(el);
      for (let d = el.closest("details"); d; d = d.parentElement && d.parentElement.closest("details")) d.open = true;
      if (scroll) el.scrollIntoView({block: "center"});
      el.classList.add("flash"); setTimeout(() => el.classList.remove("flash"), 1600);
      return true;
    }
    return false;
  }
  window.addEventListener("click", e => {          // capture phase: runs before wiki.js's own #link handler
    const a = e.target.closest && e.target.closest('a[href^="#"]');
    if (!a || a.getAttribute("href").length < 2 || a.dataset.tree) return;
    if (go(a.getAttribute("href").slice(1), true)) {
      e.preventDefault(); e.stopPropagation(); history.replaceState(null, "", a.getAttribute("href"));
    }
  }, true);
  window.addEventListener("hashchange", () => go(location.hash.slice(1), true));
  if (location.hash) go(location.hash.slice(1), true);
})();
