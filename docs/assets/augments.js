// Augment pages: the "Internal names and IDs" side panel starts closed on narrow screens (one column), where the
// rail sits above the article.
(function () {
  if (!window.matchMedia("(max-width: 1100px)").matches) return;
  document.querySelectorAll("details.augside[open]").forEach(d => { d.open = false; });
})();
