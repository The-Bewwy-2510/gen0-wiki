/* World section: the location list (world/locations.html) has one closed fold per region. While a kind chip is on
   or a name is typed, the folds with matching rows open and the ones without any are hidden. Runs after wiki.js
   has filtered the rows (wiki.js itself opens every fold while something is typed). */
"use strict";
(function () {
  document.querySelectorAll("[data-chipfold]").forEach((box) => {
    const bars = document.querySelectorAll(`.filterbar[data-for="${box.id}"]`);
    const sync = () => {
      const on = Array.from(bars).some((fb) => fb.querySelector('.chip.on:not([data-f="*"])') ||
                                               (fb.querySelector("input") && fb.querySelector("input").value.trim()));
      box.querySelectorAll("details.fold").forEach((d) => {
        if (on) {
          const any = Array.from(d.querySelectorAll("tbody tr")).some((r) => r.style.display !== "none");
          d.style.display = any ? "" : "none";
          if (any && !d.open) { d.open = true; d._chip = true; }
        } else {
          d.style.display = "";
          if (d._chip) { d.open = false; d._chip = false; }
        }
      });
    };
    bars.forEach((fb) => {
      fb.addEventListener("click", (e) => { if (e.target.closest(".chip")) setTimeout(sync, 0); });
      fb.addEventListener("input", () => setTimeout(sync, 0));
    });
    sync();
  });
})();
