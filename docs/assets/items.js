/* Items & crafting: a filter bar whose rows sit in folds (equipment groups, companion cosmetics) opens the folds
   that still have rows while a chip filter is on, and hides the folds left empty. wiki.js does the filtering itself
   (and opens the folds while text is typed); this runs right after it. */
(() => {
  const active = fb => {
    const input = fb.querySelector("input");
    if (input && input.value.trim()) return true;
    return [...fb.querySelectorAll(".chip.on")].some(c => c.dataset.f !== "*");
  };
  function sync(fb) {
    const t = document.getElementById(fb.dataset.for);
    if (!t) return;
    const on = active(fb);
    t.querySelectorAll("details.fold").forEach(d => {
      const rows = [...d.querySelectorAll("tbody tr, .fitem")];
      const shown = rows.some(r => r.style.display !== "none");
      if (on) {
        d.style.display = shown ? "" : "none";
        if (shown && !d.open) { d.open = true; d._chip = true; }
      } else {
        d.style.display = "";
        if (d._chip) { d.open = false; d._chip = false; }
      }
    });
  }
  document.querySelectorAll(".filterbar[data-for]").forEach(fb => {
    if (!document.getElementById(fb.dataset.for) || !document.getElementById(fb.dataset.for).querySelector("details.fold")) return;
    fb.addEventListener("click", e => { if (e.target.closest(".chip")) setTimeout(() => sync(fb), 0); });
    fb.addEventListener("input", () => setTimeout(() => sync(fb), 0));
  });
})();
