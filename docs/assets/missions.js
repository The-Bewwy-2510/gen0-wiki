/* Gen0 Wiki - Missions section: the challenge browser (tree tabs, challenge rows with their tier nodes, the details
   panel on the right; on narrow screens the details open under the picked challenge) and the secret achievements'
   spoilers. Without JavaScript every tree and every challenge's details are simply shown one after another. */
"use strict";
(function () {
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => Array.from(el.querySelectorAll(s));

  // ------------------------------------------------------------------ spoilers (secret achievements)
  document.addEventListener("click", e => {
    const sp = e.target.closest(".spoil");
    if (sp && !sp.classList.contains("shown")) { e.preventDefault(); sp.classList.add("shown"); }
  });

  // ------------------------------------------------------------------ challenge browser
  const chb = $("#chb");
  if (!chb) return;
  chb.classList.add("js");
  const grid = $(".chgrid", chb), detail = $(".chdetail", chb);
  const tabs = $$(".chtab", chb), trees = $$(".chtree", chb), rows = $$(".chrow", chb);
  let cur = null, tier = 0;

  const narrow = () => chb.clientWidth <= 760;
  function place() {
    // narrow: the details sit right under the picked row; wide: in the right-hand column
    if (narrow() && cur) { if (cur.nextElementSibling !== detail) cur.after(detail); }
    else if (detail.parentElement !== grid) grid.appendChild(detail);
  }
  function showTree(id) {
    tabs.forEach(t => t.classList.toggle("on", t.dataset.tree === id));
    trees.forEach(t => t.classList.toggle("on", t.dataset.tree === id));
  }
  function paint() {
    rows.forEach(r => {
      const on = r === cur, nodes = $$(".chnode", r), segs = $$(".chseg", r);
      const upto = on ? (tier || nodes.length) : 0;
      nodes.forEach((n, i) => n.classList.toggle("on", i < upto));
      segs.forEach((s, i) => s.classList.toggle("on", i + 1 < upto));
      r.classList.toggle("sel", on);
      r.setAttribute("aria-expanded", on);
    });
    const key = cur && cur.dataset.ch;
    $$(".chd", detail).forEach(d => {
      const on = d.dataset.ch === key;
      d.classList.toggle("on", on);
      if (on) $$(".chtier", d).forEach((li, i) => {
        li.classList.toggle("on", i < (tier || 99));
        li.classList.toggle("pick", tier > 0 && i === tier - 1);
      });
    });
  }
  function select(row, t, how) {
    if (!row) return;
    cur = row; tier = t || 0;
    showTree(row.closest(".chtree").dataset.tree);
    paint(); place();
    if (how !== "load") detail.scrollTop = 0;
    if (tier) { const p = $(".chd.on .chtier.pick", detail); if (p && !narrow()) p.scrollIntoView({block: "nearest"}); }
    if (how === "user") {
      try { history.replaceState(null, "", "#" + row.id); } catch (e) { /* file:// in some browsers */ }
      if (narrow()) {
        const r = detail.getBoundingClientRect();
        if (r.top > window.innerHeight - 80) detail.scrollIntoView({block: "nearest", behavior: "smooth"});
      }
    }
  }
  function fromHash(how) {
    let id = ""; try { id = decodeURIComponent(location.hash.slice(1)); } catch (e) { id = ""; }
    const el = id && document.getElementById(id);
    if (el && el.classList.contains("chrow")) { select(el, 0, how); return true; }
    if (el && el.classList.contains("chtree")) { select($(".chrow", el), 0, how); return true; }
    return false;
  }

  tabs.forEach(t => t.addEventListener("click", () => {
    const tree = trees.find(x => x.dataset.tree === t.dataset.tree);
    select($(".chrow", tree), 0, "user");
    try { history.replaceState(null, "", "#" + tree.id); } catch (e) { /* ignore */ }
  }));
  chb.addEventListener("click", e => {
    const row = e.target.closest(".chrow"); if (!row || e.target.closest("a")) return;
    const node = e.target.closest(".chnode");
    select(row, node ? +node.dataset.tier : 0, "user");
  });
  chb.addEventListener("keydown", e => {
    const row = e.target.closest(".chrow"), tab = e.target.closest(".chtab");
    if (row && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); select(row, 0, "user"); }
    else if (row && (e.key === "ArrowDown" || e.key === "ArrowUp")) {
      const list = $$(".chrow", row.closest(".chtree")), i = list.indexOf(row);
      const nx = list[Math.max(0, Math.min(list.length - 1, i + (e.key === "ArrowDown" ? 1 : -1)))];
      e.preventDefault(); nx.focus(); select(nx, 0, "user");
    } else if (tab && (e.key === "ArrowLeft" || e.key === "ArrowRight")) {
      const i = tabs.indexOf(tab), nx = tabs[(i + (e.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length];
      e.preventDefault(); nx.focus(); nx.click();
    }
  });
  window.addEventListener("hashchange", () => fromHash("hash"));
  if (!fromHash("load")) select(rows[0], 0, "load");
  new ResizeObserver(place).observe(chb);
})();
