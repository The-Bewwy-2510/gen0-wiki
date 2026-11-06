/* Weapons section: the comparison table on weapons/index.html is one closed fold per category.
   wiki.js filters the rows and opens the folds while typing; here a fold without a match is hidden, its count
   shows what is left, and a pack chip alone (nothing typed) opens the folds that still have weapons. */
(() => {
  const box = document.getElementById("wcompare"), fb = document.querySelector('.filterbar[data-for="wcompare"]');
  if (!box || !fb) return;
  const input = fb.querySelector("input");
  const folds = [...box.querySelectorAll("details.fold")];
  folds.forEach(d => { const s = d.querySelector(":scope > summary small"); d._small = s; d._total = s ? s.textContent : ""; });
  const update = () => {
    const typing = input.value.trim() !== "";
    const chip = [...fb.querySelectorAll('.chip[data-f="*"]')].some(c => !c.classList.contains("on"));
    const filtering = typing || chip;
    folds.forEach(d => {
      const n = [...d.querySelectorAll("tbody tr")].filter(r => r.style.display !== "none").length;
      d.hidden = filtering && n === 0;
      if (d._small) d._small.textContent = filtering ? `${n} shown` : d._total;
      if (typing) { if (n && !d.open) { d.open = true; d._auto = true; } }   // e.g. a ?f= link
      else {
        if (chip && n && !d.open) { d.open = true; d._auto = true; }
        else if (!chip && d._auto) { d.open = false; d._auto = false; }
      }
    });
  };
  fb.addEventListener("input", () => setTimeout(update));
  fb.addEventListener("click", e => { if (e.target.closest(".chip")) setTimeout(update); });
  update();
})();
