/* ammo page (sections/ammo.py): while the "All ammo" filter is in use, hide the calibre groups that have no
   matching rows, so typing "shock" shows only the groups with a shock round instead of every group opened empty. */
(function () {
  "use strict";
  document.querySelectorAll(".filterbar[data-for]").forEach(function (fb) {
    var target = document.getElementById(fb.dataset.for);
    if (!target || !target.querySelector("details.fold")) return;
    var input = fb.querySelector("input");
    function sync() {
      var filtering = (input && input.value.trim() !== "") ||
        Array.prototype.some.call(fb.querySelectorAll(".chip.on"), function (c) { return c.dataset.f !== "*"; });
      target.querySelectorAll("details.fold").forEach(function (d) {
        var rows = d.querySelectorAll("tbody tr, .fitem");
        var any = Array.prototype.some.call(rows, function (r) { return r.style.display !== "none"; });
        d.style.display = filtering && rows.length && !any ? "none" : "";
      });
    }
    // run after wiki.js has applied the filter to the rows
    var later = function () { setTimeout(sync, 0); };
    if (input) input.addEventListener("input", later);
    fb.querySelectorAll(".chip").forEach(function (c) { c.addEventListener("click", later); });
    later();
  });
})();
