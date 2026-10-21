(function () {
  "use strict";
  const nav = document.querySelector("[data-site-nav]");
  if (!nav) return;
  const pages = [["./", "Projektüberblick"], ["marktdaten.html", "Marktdaten & Messungen"]];
  const current = location.pathname.endsWith("/marktdaten.html") ? "marktdaten.html" : "./";
  for (const [href, label] of pages) {
    const link = document.createElement("a");
    link.href = href;
    link.textContent = label;
    if (href === current) link.setAttribute("aria-current", "page");
    nav.append(link);
  }
}());
