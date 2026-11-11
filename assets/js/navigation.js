(function () {
  "use strict";
  const nav = document.querySelector("[data-site-nav]");
  if (!nav || !document.body.hasAttribute("data-site-shell")) return;

  const pages = new Map([...nav.querySelectorAll("a[data-page]")].map(link =>
    [new URL(link.href).pathname, link]));
  const home = nav.querySelector('[data-page="overview"]');
  const route = url => pages.get(url.pathname) ||
    (url.pathname === new URL("index.html", home.href).pathname ? home : null);
  const label = document.querySelector("[data-project-label-text]");
  const description = document.querySelector('meta[name="description"]');
  const brand = document.querySelector(".brand");
  const timingLabel = document.querySelector("[data-latency-label]");
  const timing = document.querySelector("[data-page-load-time]");
  let current = route(new URL(location.href));
  let main = document.getElementById("inhalt");
  let dispose = () => {};
  let pending = null;
  let view = 0;
  if (!current || !main) return;

  const documentReady = document.readyState === "complete" ? Promise.resolve() :
    new Promise(resolve => window.addEventListener("load", resolve, {once: true}));
  const paint = () => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));

  function mount(started) {
    const id = ++view;
    timing.textContent = "— ms";
    timing.setAttribute("aria-label", "Seitenladezeit wird gemessen");
    timing.removeAttribute("title");
    const modules = current === home ? [window.MosaIsinLookup] :
      current.dataset.page === "market" ? [window.MosaIsinLookup, window.MosaMarket] :
      [window.MosaFundamentals];
    const sessions = modules.filter(module => module?.mount).map(module => module.mount(main));
    dispose = () => sessions.forEach(session => session.dispose());
    Promise.allSettled([documentReady, ...sessions.map(session => session.ready)]).then(async () => {
      await paint();
      if (id !== view) return;
      const ms = Math.round(performance.now() - started);
      const value = ms >= 1000 ? (ms / 1000).toLocaleString("de-DE", {
        minimumFractionDigits: 2, maximumFractionDigits: 2
      }) + " s" : ms + " ms";
      timing.textContent = value;
      timing.title = "Seitenladezeit: " + value;
      timing.setAttribute("aria-label", "Seitenladezeit " + value);
    });
  }

  function position(url) {
    let target = null;
    if (url.hash) {
      try { target = document.getElementById(decodeURIComponent(url.hash.slice(1))); }
      catch { /* An invalid fragment should behave like a missing anchor. */ }
    }
    const focus = target || main;
    if (!focus.hasAttribute("tabindex")) focus.tabIndex = -1;
    focus.focus({preventScroll: true});
    if (target) target.scrollIntoView();
    else window.scrollTo(0, 0);
  }

  async function navigate(url, next, traverse) {
    pending?.abort();
    pending = null;
    if (next === current) {
      if (!traverse && url.href !== location.href) history.pushState(null, "", url);
      position(url);
      return;
    }
    const controller = new AbortController();
    pending = controller;
    const started = performance.now();
    const timeout = setTimeout(() => controller.abort(), 5000);
    try {
      const asset = new URL("assets/main-" + next.dataset.page + ".html?v=page-shell-1", home.href);
      const response = await fetch(asset, {credentials: "same-origin", signal: controller.signal});
      if (!response.ok || response.redirected) throw Error("Main unavailable");
      const template = document.createElement("template");
      template.innerHTML = await response.text();
      const replacement = template.content.firstElementChild;
      if (template.content.childElementCount !== 1 || !replacement?.matches("main#inhalt") ||
          replacement.querySelector("script")) throw Error("Invalid Main");
      if (pending !== controller) return;
      if (controller.signal.aborted) throw Error("Main timeout");
      if (!traverse) history.pushState(null, "", url);
      dispose();
      document.body.classList.replace(current.dataset.page + "-page", next.dataset.page + "-page");
      document.body.toggleAttribute("data-isin-stored-quotes", next.dataset.page !== "fundamentals");
      current.removeAttribute("aria-current");
      next.setAttribute("aria-current", "page");
      current = next;
      label.textContent = next.dataset.projectLabel;
      description.content = next.dataset.description;
      document.title = "MOSA 2 · " + next.textContent;
      brand.setAttribute("href", next === home ? "#inhalt" : home.getAttribute("href"));
      timingLabel.textContent = next.dataset.page === "fundamentals"
        ? "Seitenladezeit inkl. Daten · " : "Seitenladezeit · ";
      main.replaceWith(replacement);
      main = replacement;
      mount(started);
      position(url);
    } catch {
      if (pending !== controller) return;
      if (url.href === location.href) location.reload();
      else location.assign(url);
    } finally {
      clearTimeout(timeout);
      if (pending === controller) pending = null;
    }
  }

  document.addEventListener("click", event => {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey ||
        event.shiftKey || event.altKey) return;
    const anchor = event.target.closest?.("a[href]");
    if (!anchor || anchor.target || anchor.hasAttribute("download")) return;
    const url = new URL(anchor.href);
    if (url.origin !== location.origin || url.search) return;
    const next = route(url);
    if (!next) return;
    if (next === current && !pending && anchor.getAttribute("href").startsWith("#")) return;
    event.preventDefault();
    navigate(url, next, false);
  });
  window.addEventListener("popstate", () => {
    const url = new URL(location.href);
    const next = route(url);
    if (next && (next !== current || pending)) navigate(url, next, true);
  });

  mount(0);
}());
