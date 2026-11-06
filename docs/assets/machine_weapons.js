/* Machine weapons & rivals pages: the difficulty switch of the weapon table, the rival title builder and the
   filter of the title tree. No dependencies; runs after wiki.js (deferred). */
"use strict";
(function () {
  const ROOT = document.body.dataset.root || "";
  const $$ = (s, el = document) => Array.from(el.querySelectorAll(s));
  const fold = s => String(s || "").normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"})[c]);

  // ------------------------------------------------------------ weapons page: rescale every cell with data-b
  const sel = document.getElementById("mwDiff"), sum = document.getElementById("mwsum");
  if (sel && sum) {
    const f = n => (Math.round(n * 100) / 100).toLocaleString("en-US");
    sel.addEventListener("change", () => {
      const k = parseFloat(sel.value);
      $$("td[data-b]", sum).forEach(td => {
        const v = parseFloat(td.dataset.b) * k, s = td.querySelector(".dsc");
        td.dataset.v = v;
        if (s) s.textContent = f(parseFloat(s.dataset.b) * k); else td.textContent = f(v);
      });
    });
  }

  // ------------------------------------------------------------ rivals page: title builder
  const tb = document.getElementById("tbuild");
  if (tb) {
    let D = null;
    try { D = JSON.parse(tb.querySelector(".tbdata").textContent); } catch (e) { D = null; }
    if (D) builder(tb, D);
  }
  function builder(tb, D) {
    const pairs = {}, byN = D.n.map(() => []), byP = D.p.map(() => []);
    D.t.forEach(([n, p, text]) => { pairs[n + "," + p] = text; byN[n].push(p); byP[p].push(n); });
    const chips = {n: $$('.tbchips[data-k="n"] .tbc', tb), p: $$('.tbchips[data-k="p"] .tbc', tb)};
    const boxes = {n: tb.querySelector('.tbchips[data-k="n"]'), p: tb.querySelector('.tbchips[data-k="p"]')};
    const qs = {n: tb.querySelector('.tbq[data-k="n"]'), p: tb.querySelector('.tbq[data-k="p"]')};
    const only = tb.querySelector(".tbonly input"), sep = tb.querySelector(".tbsep");
    const out = {n: tb.querySelector(".tbn"), p: tb.querySelector(".tbp"), prep: tb.querySelector(".tbprep"),
                 title: tb.querySelector(".tbtitle"), info: tb.querySelector(".tbinfo")};
    const cur = {n: -1, p: -1};
    const link = (u, t) => u ? `<a href="${esc(ROOT + u)}">${esc(t)}</a>` : "";
    const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;

    function render() {
      const n = cur.n, p = cur.p;
      // the chips that go with the other pick
      const okP = n >= 0 ? new Set(byN[n]) : null, okN = p >= 0 ? new Set(byP[p]) : null;
      const filt = {n: fold(qs.n.value.trim()), p: fold(qs.p.value.trim())};
      ["n", "p"].forEach(k => {
        const ok = k === "n" ? okN : okP;
        chips[k].forEach(c => {
          const i = +c.dataset.i, match = !ok || ok.has(i);
          c.classList.toggle("on", i === cur[k]);
          c.classList.toggle("no", !match);
          const txt = c._t || (c._t = fold(c.firstChild.textContent));
          c.hidden = (only.checked && !match && i !== cur[k]) || (!!filt[k] && !txt.includes(filt[k]));
        });
      });
      if (sep) sep.hidden = !chips.p.some(c => !c.hidden && +c.dataset.i >= D.np);
      out.n.textContent = n >= 0 ? D.n[n] : "Epithet";
      out.p.textContent = p >= 0 ? D.p[p] : "Place or people";
      out.n.classList.toggle("tbslot", n < 0); out.p.classList.toggle("tbslot", p < 0);
      const text = n >= 0 && p >= 0 ? pairs[n + "," + p] : null;
      out.prep.textContent = text && / from /.test(text) && !/ of /.test(text) ? "from" : "of";
      out.title.classList.toggle("yes", !!text); out.title.classList.toggle("nope", n >= 0 && p >= 0 && !text);
      // what the picked place is, with its wiki page and a map link (people words have none)
      const where = () => {
        const [what, page, map] = D.info[p];
        if (!what || what === "people") return "";
        const name = D.p[p].charAt(0).toUpperCase() + D.p[p].slice(1);
        return ` <i>${esc(name)}</i> is ${esc(what)}`
          + (page || map ? ": " + [link(page, "wiki page"), link(map, "show on the map")].filter(Boolean).join(" · ") : "") + ".";
      };
      let h;
      if (n >= 0 && p >= 0) {
        if (text) {
          const people = p >= D.np;
          h = `<b>In the game.</b> ${people ? "A people title: it names who the rival fights instead of a place." : "A place title."}`;
          if (text !== `The ${D.n[n]} ${out.prep.textContent} ${D.p[p]}`) h += ` The game spells it “${esc(text)}”.`;
          h += where();
        } else {
          h = `<b>Not in the game.</b> ${esc(D.n[n])} is never paired with ${esc(D.p[p])}.` + where();
        }
      } else if (n >= 0) {
        const pl = byN[n].filter(i => i < D.np).length, pe = byN[n].length - pl;
        const parts = [pl ? plural(pl, "place", "places") : "", pe ? plural(pe, "word", "words") + " for people" : ""].filter(Boolean);
        h = `<b>${esc(D.n[n])}</b> is in ${plural(byN[n].length, "title", "titles")}, with ${parts.join(" and ")}. `
          + `Now pick ${[pl ? "a place" : "", pe ? "people" : ""].filter(Boolean).join(" or ")}.`;
      } else if (p >= 0) {
        h = `<b>${esc(D.p[p])}</b> is in ${plural(byP[p].length, "title", "titles")}, each with another epithet. Now pick an epithet.` + where();
      } else h = "Pick an epithet and a place below, or try a random title.";
      out.info.innerHTML = h;
    }
    function reveal(k) {
      const c = chips[k].find(x => +x.dataset.i === cur[k]), box = boxes[k];
      if (c && box.scrollHeight > box.clientHeight) box.scrollTop = c.offsetTop - box.clientHeight / 2;
    }
    tb.addEventListener("click", e => {
      const c = e.target.closest(".tbc");
      if (c) { const k = c.dataset.k, i = +c.dataset.i; cur[k] = cur[k] === i ? -1 : i; render(); return; }
      const a = e.target.closest("button[data-a]");
      if (!a) return;
      if (a.dataset.a === "rand") {
        const t = D.t[Math.floor(Math.random() * D.t.length)];
        cur.n = t[0]; cur.p = t[1];
      } else { cur.n = cur.p = -1; }
      qs.n.value = qs.p.value = "";
      render(); reveal("n"); reveal("p");
    });
    [qs.n, qs.p, only].forEach(x => x.addEventListener("input", render));
    render();
  }

  // ------------------------------------------------------------ rivals page: title tree filter
  // wiki.js filters the items and opens the folds while typing; here the folds without a match are hidden and
  // their counts show what is left.
  const tree = document.getElementById("ttree"), fb = document.querySelector('.filterbar[data-for="ttree"]');
  if (tree && fb) {
    const folds = $$("details.fold", tree);
    folds.forEach(d => { const s = d.querySelector(":scope > summary small"); d._small = s; d._total = s ? s.textContent : ""; });
    const update = () => {
      const filtering = fb.querySelector("input").value.trim() !== "" || !fb.querySelector('.chip[data-f="*"]').classList.contains("on");
      const typing = fb.querySelector("input").value.trim() !== "";
      // a chip alone (nothing typed) opens the groups when few titles are left, e.g. Folklore
      const few = filtering && $$(".fitem", tree).filter(li => li.style.display !== "none").length <= 200;
      folds.forEach(d => {
        const n = $$(".fitem", d).filter(li => li.style.display !== "none").length;
        d.hidden = filtering && n === 0;
        if (d._small) d._small.textContent = filtering ? `${n} shown` : d._total;
        if (!typing) {
          if (few && n && !d.open) { d.open = true; d._auto = true; }
          else if (!few && d._auto) { d.open = false; d._auto = false; }
        }
      });
    };
    fb.addEventListener("input", () => setTimeout(update));
    fb.addEventListener("click", e => { if (e.target.closest(".chip")) setTimeout(update); });
    update();
  }
})();
