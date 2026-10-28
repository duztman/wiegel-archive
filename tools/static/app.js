/* Wiegel Archive v3 — one script for all pages. No dependencies. */
(() => {
  const R = window.ROOT || "";
  const C = window.CATALOG || { fonts: [] };
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const store = { get(k) { try { return sessionStorage.getItem(k) ?? localStorage.getItem(k); } catch { return null; } },
    set(k, v, keep) { try { (keep ? localStorage : sessionStorage).setItem(k, v); } catch {} } };
  const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const pad = (n) => String(n).padStart(3, "0");
  const flink = (s) => (window.HOSTED ? `${R}font.html#${s}` : `${R}font/${s}.html`);

  /* header height → sticky offsets */
  function setNavH() { const t = document.getElementById("top"); if (t) document.documentElement.style.setProperty("--navh", t.offsetHeight + "px"); }
  setNavH(); if (window.ResizeObserver && document.getElementById("top")) new ResizeObserver(setNavH).observe(document.getElementById("top")); else addEventListener("resize", setNavH);   // follows the bar when the UI font arrives and it un-wraps

  const homeList = document.querySelector(".homelist");   // on the index the list scrolls inside its own column
  const onScroll = () => document.documentElement.classList.toggle("scrolled", scrollY > 0);
  homeList?.addEventListener("scroll", () => homeList.classList.toggle("scrolled", homeList.scrollTop > 0), { passive: true });   // the list fades under its own head, not over Cards / Preview
  addEventListener("scroll", onScroll, { passive: true }); onScroll();

  $$("#subnav > .secs").forEach((x) => x.addEventListener("scroll", () => x.classList.toggle("sc", x.scrollLeft > 0), { passive: true }));   // About row: fades in at the left once scrolled

  /* phone menu: the search and the colour controls move into it while it is open */
  const burger = $("#burger"), menu = $("#menu");
  if (burger && menu) {
    const slot = $(".mslot", menu), parts = [$(".nsearch"), $(".top .modes")].filter(Boolean);
    const homes = parts.map((el) => [el.parentNode, el.nextSibling]);
    const open = (on) => {
      const cp = $("#cpanel");
      if (cp) { cp.removeAttribute("style"); $(".cin", cp).removeAttribute("style"); cp.hidden = !on; cp.closest(".cpick").classList.remove("open"); }   // the pairs are always open in the menu
      if (on) parts.forEach((el) => slot.appendChild(el));
      else parts.map((el, i) => [el, i]).reverse().forEach(([el, i]) => homes[i][0].insertBefore(el, homes[i][1]));   // last first, so each one's neighbour is back
      menu.hidden = !on; burger.setAttribute("aria-expanded", on); document.documentElement.style.overflow = on ? "hidden" : "";
      (on ? $("#mclose") : burger).focus();
    };
    burger.addEventListener("click", () => open(true));
    $("#mclose").addEventListener("click", () => open(false));
    menu.addEventListener("click", (e) => { if (e.target.closest(".mlist a")) open(false); });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !menu.hidden) open(false); });
    matchMedia("(max-width: 800px)").addEventListener("change", (e) => { if (!e.matches && !menu.hidden) open(false); });
  }

  /* top-bar search: Enter searches the index (here, or by going there with the query) */
  const ns = $(".nsearch");
  ns?.addEventListener("submit", (e) => {
    e.preventDefault();
    const q = $("#nq").value.trim();
    if ($("#grid")) return;   // on the font list the bar's search already filters as you type
    let st = {}; try { st = JSON.parse(store.get("wa-index2") || "{}"); } catch {}
    store.set("wa-index2", JSON.stringify({ ...st, sel: {}, q }));
    location.href = R + "index.html";
  });

  /* colour: C opens Wiegel's pairs in a pill that grows left from it; the pick is remembered on every page.
     Tapping the picked pair again forgets it (random pairs again). M: black/white + one accent; again for a new accent. */
  const root = document.documentElement, cbtn = $("#cbtn"), cpanel = $("#cpanel");
  const PAL = window.WA_PAL || {};
  function markModes() {
    const pick = root.dataset.mode === "random" ? window.WA_PICK : "";
    if (cbtn) { const cs = getComputedStyle(root); cbtn.style.setProperty("--b", cs.getPropertyValue("--paper").trim()); cbtn.style.setProperty("--f", cs.getPropertyValue("--ink").trim()); }   // the button is the swatch on show
    $$("[data-m=mono]").forEach((b) => { b.classList.toggle("on", root.dataset.mode === "mono"); b.setAttribute("aria-pressed", root.dataset.mode === "mono"); });
    $$("#cpanel .sw[data-p]").forEach((s) => { s.classList.toggle("on", s.dataset.p === pick); s.setAttribute("aria-pressed", s.dataset.p === pick); });
    $("#cinv")?.classList.toggle("on", !!window.WA_INV); $("#cinv")?.setAttribute("aria-pressed", !!window.WA_INV);
  }
  function applyColour() {
    const art = $("article.font");
    if (root.dataset.mode === "mono") { art && window._setPal ? window._setPal("plain") : window.WA_theme?.(null); }
    else if (window.WA_PICK) { art && window._setPal ? window._setPal(window.WA_PICK) : window.WA_theme?.(PAL[window.WA_PICK]); }
    else { art && window._setPal ? window._setPal(art.dataset.pal) : window.WA_theme?.(null); }
    markModes(); redrawAll();
  }
  const openPanel = (on) => { if (!cpanel) return;
    cpanel.hidden = !on; cbtn.closest(".cpick").classList.toggle("open", on); cbtn.setAttribute("aria-expanded", on);
  };
  cbtn?.addEventListener("click", () => openPanel(!cbtn.closest(".cpick").classList.contains("open")));
  $$("#cpanel .sw[data-p]").forEach((s) => (s.onclick = () => {
    const k = s.dataset.p, same = root.dataset.mode === "random" && window.WA_PICK === k;
    window.WA_PICK = same ? "" : k;
    try { same ? localStorage.removeItem("wa-pair") : localStorage.setItem("wa-pair", k); } catch {}
    root.dataset.mode = "random"; store.set("wa-mode", "random", true);
    applyColour();
  }));
  $("#cinv")?.addEventListener("click", () => {   // I: every pair turns dark paper / light ink, the swatches too
    window.WA_INV = !window.WA_INV; root.classList.toggle("inv", window.WA_INV);
    try { localStorage.setItem("wa-inv", window.WA_INV ? "1" : "0"); } catch {}
    if (root.dataset.mode === "random" && window.WA_CUR) window.WA_theme(window.WA_CUR);
    markModes(); redrawAll();
  });
  document.addEventListener("click", (e) => { if (cpanel && cbtn.closest(".cpick").classList.contains("open") && !e.target.closest(".cpick")) openPanel(false); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && cpanel && cbtn.closest(".cpick").classList.contains("open")) { openPanel(false); cbtn.focus(); } });
  $$("[data-m=mono]").forEach((b) => (b.onclick = () => {
    const again = root.dataset.mode === "mono";
    root.dataset.mode = "mono"; store.set("wa-mode", "mono", true);
    if (again) window.WA_theme?.(null); else applyColour();
    markModes(); redrawAll();
  }));
  markModes();
  new MutationObserver(markModes).observe(root, { attributes: true, attributeFilter: ["style", "class", "data-mode"] });   // the button follows every change of pair
  $("#rndfont")?.addEventListener("click", (e) => {
    if (!C.fonts.length) return;
    e.preventDefault();
    const cur = $("article.font")?.dataset.slug;
    let f; do { f = C.fonts[Math.floor(Math.random() * C.fonts.length)]; } while (C.fonts.length > 1 && f.s === cur);
    location.href = flink(f.s);
  });

  /* font loading — fetch + FontFace (works on a local server and in a sandboxed host) */
  const faces = new Map();
  function loadSrc(src, id) {
    id = id || "wa-" + src.replace(/[^a-z0-9]/gi, "");
    if (faces.has(id)) return faces.get(id).then(() => id);
    const p = bytes(src).then((buf) => new FontFace(id, buf).load()).then((x) => { document.fonts.add(x); return x; });
    faces.set(id, p);
    p.catch(() => faces.delete(id));
    return p.then(() => id);
  }
  /* a font file, or one font out of a pack ('pack.woff2#name': 4-byte header length, JSON index {name: [offset, length]}, the fonts) */
  const packs = new Map();
  const get = (u) => fetch(R + u).then((r) => { if (!r.ok) throw new Error(r.status); return r.arrayBuffer(); });
  function bytes(src) {
    const [file, name] = src.split("#");
    if (!name) return get(src);
    if (!packs.has(file)) {
      const p = get(file).then((buf) => { const n = new DataView(buf).getUint32(0, true);
        return { buf, base: 4 + n, idx: JSON.parse(new TextDecoder().decode(new Uint8Array(buf, 4, n))) }; });
      packs.set(file, p); p.catch(() => packs.delete(file));
    }
    return packs.get(file).then(({ buf, base, idx }) => { const e = idx[name]; if (!e) throw new Error("not in pack: " + name); return buf.slice(base + e[0], base + e[0] + e[1]); });
  }
  const load = (f) => (f ? loadSrc(f.src, f.id) : Promise.reject());

  /* lazily set names in their own face (timeline, list) */
  const lazy = new IntersectionObserver((es) => es.forEach((e) => {
    if (!e.isIntersecting) return;
    lazy.unobserve(e.target);
    const el = e.target;
    if (!el.dataset.src) { el.classList.add("ok"); return; }
    loadSrc(el.dataset.src).then((id) => { el.style.fontFamily = `"${id}", "WA Blank"`; el.classList.add("ok"); if (el.classList.contains("aa")) fitAa(el); }).catch(() => el.classList.add("ok"));
  }), { rootMargin: "600px 0px" });

  /* font cards: one size for every 'Aa'; only a face too wide for the card is set smaller, never cut */
  function fitAa(el) {
    el.style.fontSize = "";
    const c = el.parentElement, cs = getComputedStyle(c), room = c.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
    const w = el.getBoundingClientRect().width;
    if (w > room) el.style.fontSize = Math.floor(parseFloat(getComputedStyle(el).fontSize) * room / w) + "px";
  }
  const meas = document.createElement("canvas").getContext("2d");   // text measuring for fitting and cap alignment
  function prep(canvas) {
    const dpr = Math.max(1, Math.round(devicePixelRatio || 1));
    const W = canvas.clientWidth, H = canvas.clientHeight;
    if (canvas.width !== W * dpr || canvas.height !== H * dpr) { canvas.width = W * dpr; canvas.height = H * dpr; }
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = css("--ink"); ctx.textBaseline = "alphabetic";
    return { ctx, W, H };
  }

  /* ── home: the list of names set in their own faces, with a side column of filter pills ── */
  const grid = $("#grid");
  function redrawAll() { window._redrawFont?.(); }

  if (grid) {
    const SCRIPTS = { latin1: "Latin-1", ext: "Extended Latin", greek: "Greek", cyr: "Cyrillic", longs: "Long s", capsz: "Capital ẞ", euro: "Euro sign" };
    const bucket = (y) => (!y ? "Undated" : y < 1800 ? "Before 1800" : `${Math.floor(y / 10) * 10}s`);
    const CATS = [
      ["fa", "Family", (f) => [f.fa, ...(f.xf || []), ...(f.set ? ["Sets"] : [])]],   // DIN, dot-matrix fonts and sets show under their own family as well
      ["oy", "Original", (f) => [bucket(f.y)]],
      ["cv", "Script", (f) => (f.cv || []).map((k) => SCRIPTS[k]).filter(Boolean)],
      ["ic", "Features", (f) => (f.ic || []).map((k) => (C.icons || {})[k]).filter(Boolean)],
      ["pl", "Place", (f) => [f.ph ? "Photographed" : null, f.pl ? "Has a place" : "No place"].filter(Boolean)],
      // reached only from the small pills in a font's Facts (index.html#g=…); no pills of their own here
      ["g", "Genre", (f) => [f.g], true],
      ["tg", "Tag", (f) => f.tg || [], true],
      ["st", "Styles", (f) => { const n = f.set ? f.set[0] : f.st; return [n + (n === 1 ? " style" : " styles")]; }, true],
      ["gl", "Characters", (f) => [f.gl + " characters"], true],
    ];
    const ORDERS = [["index", "Wiegel’s order"], ["name", "A to Z"], ["oy", "Original date"], ["dy", "Digitised"], ["glyphs", "Most glyphs"]];
    const vals = {};
    CATS.forEach(([k, , fn]) => { const m = new Map(); C.fonts.forEach((f) => fn(f).forEach((v) => m.set(v, (m.get(v) || 0) + 1))); vals[k] = m; });
    const num = (v) => parseInt(v) || (v === "Before 1800" ? 0 : 9999);
    const sortVals = (k, m) => {
      const e = [...m.entries()];
      if (k === "fa") {   // the extra pills follow the family most of their fonts belong to
        const fam = [...C.families];
        fam.splice(fam.indexOf("Norm & Sans") + 1, 0, "DIN"); fam.splice(fam.indexOf("Technical") + 1, 0, "Dot matrix", "Typewriter"); fam.push("Sets");
        return e.sort((a, b) => fam.indexOf(a[0]) - fam.indexOf(b[0]));
      }
      if (k === "oy" || k === "dy") return e.sort((a, b) => num(a[0]) - num(b[0]));
      return e.sort((a, b) => b[1] - a[1]);
    };
    const state = { sel: {}, q: "", order: "index" };
    try {   // saved state from an older build, or edited by hand, must not stop the page
      const s = JSON.parse(store.get("wa-index2") || "{}");
      if (s && typeof s === "object") {
        if (s.sel && typeof s.sel === "object") Object.entries(s.sel).forEach(([k, v]) => { if (Array.isArray(v) && v.length && CATS.some(([c]) => c === k)) state.sel[k] = v; });
        if (typeof s.q === "string") state.q = s.q;
        if (typeof s.order === "string") state.order = s.order;
      }
    } catch {}
    Object.keys(state.sel).forEach((k) => (state.sel[k] = new Set(state.sel[k])));
    /* a link from a font page (index.html#ic=Greek) opens the list filtered by exactly that */
    const fromLink = [...new URLSearchParams(location.hash.slice(1))].filter(([k, v]) => vals[k]?.has(v));
    if (fromLink.length) {
      state.sel = {}; state.q = "";
      fromLink.forEach(([k, v]) => (state.sel[k] = state.sel[k] || new Set()).add(v));
      history.replaceState(null, "", location.pathname + location.search);
    }
    const save = () => store.set("wa-index2", JSON.stringify({ ...state, sel: Object.fromEntries(Object.entries(state.sel).map(([k, v]) => [k, [...v]])) }));
    const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
    const ico = (c) => `<svg class="ic" width="18" height="18"><use href="#i-${c}"/></svg>`;
    C.fonts.forEach((f) => (f._hb = (f.n + " " + (f.pl || "") + " " + (f.tg || []).join(" ") + " " + f.g + " " + f.fa + " " + f.sum + " " + pad(f.no)).toLowerCase(), f._h = f._hb + " " + (f.mn || "").toLowerCase()));   // search text, built once; a font's includes its members' names, a row's only its own
    const figs = (f, t) => { const d = (t || "").replace(/[^0-9.,:; ]/g, "").trim(); return d || f.sm || "0123456789"; };   // figures-only fonts preview figures, also when the text is retyped
    const facts = (f, n) => [n || f.n, f.y ? "OG " + f.y : "", f.dy ? "DG " + f.dy : "", f.fa, f.set ? f.set[0] + (f.set[1] === "styles" ? " styles" : " fonts") : ""].filter(Boolean).map(esc).join(" · ");
    /* one row per font file: a set gives a row to each of its styles, each opening the set's page with that style on */
    const rows = C.fonts.flatMap((f) => (f.ms || [[0, f.n, f.f[0] ? f.f[0].src : ""]]).map(([i, n, src]) => {
      const a = document.createElement("a");
      a.className = "lrow tnum"; a.href = flink(f.s); a._font = f; a._n = n; a._src = src; a._i = i;
      a._h = f.ms ? (f._hb + " " + n.toLowerCase()) : f._h;
      if (f.ms) a.addEventListener("click", () => store.set("wa-style", f.s + ":" + i));
      a.innerHTML = `<span class="meta info tnum"><span class="fx">${facts(f, n)}</span><span class="ics">${(f.ic || []).slice(0, 8).map(ico).join("")}</span><span class="no">${pad(f.no)}</span></span>`
        + `<span class="ln" data-src="${esc(src)}">${esc(f.fo ? figs(f) : n)}</span>`;
      return a;
    }));
    rows.forEach((r) => lazy.observe(r.querySelector(".ln")));
    /* the same fonts as cards (as on the timeline): their own 'Aa' and the name; made on first use */
    const card = (r) => { if (r._card) return r._card; const f = r._font, a = document.createElement("a");
      a.className = "fc"; a.href = r.href; a.title = r._n; a._row = r;
      if (f.ms) a.addEventListener("click", () => store.set("wa-style", f.s + ":" + r._i));
      a.innerHTML = `<span class="aa" data-src="${esc(r._src)}">${esc(f.aa || "Aa")}</span><span class="nm">${esc(r._n)}</span>`;
      lazy.observe(a.firstChild); return (r._card = a); };
    let view = store.get("wa-view") === "cards" ? "cards" : "preview";

    const pill = (label, n, on, fn) => { const b = document.createElement("button"); b.type = "button"; b.className = "pill" + (on ? " on" : "");
      if (n === 0 && !on) { b.classList.add("zero"); b.disabled = true; }
      b.innerHTML = `${esc(label)}${n != null ? ` <span class="n tnum">${n}</span>` : ""}`; b.setAttribute("aria-pressed", !!on); b.onclick = fn; return b; };
    function renderSide() {
      const box = $("#fside"); box.replaceChildren();
      const group = (title, kids) => { const g = document.createElement("div"); g.className = "fg"; const h = document.createElement("h3"); h.className = "vlab"; h.textContent = title; const w = document.createElement("div"); w.className = "pills"; w.append(...kids); g.append(w, h); box.appendChild(g); };
      const pk = $("#picked"), toggle = (k, v) => { const s = (state.sel[k] = state.sel[k] || new Set()); s.has(v) ? s.delete(v) : s.add(v); if (!s.size) delete state.sel[k]; apply(); };
      pk.replaceChildren(...CATS.flatMap(([k]) => [...(state.sel[k] || [])].map((v) => { const b = pill(v, null, true, () => toggle(k, v)); b.insertAdjacentHTML("beforeend", '<svg class="x" viewBox="0 0 18 18" aria-hidden="true"><path d="M3.4 3.4L14.6 14.6M14.6 3.4L3.4 14.6" vector-effect="non-scaling-stroke"/></svg>'); b.setAttribute("aria-label", "Remove " + v); return b; })));
      group("Order", ORDERS.map(([k, l]) => pill(l, null, state.order === k, () => { state.order = k; apply(); })));
      CATS.forEach(([k, label, fn, hidden]) => { if (hidden) return;
        const sel = state.sel[k] || new Set(), live = liveCounts(k, fn);
        group(label, sortVals(k, vals[k]).map(([v]) => [v, live.get(v) || 0]).map(([v, n]) => pill(v, n, sel.has(v), () => toggle(k, v))));
      });
    }
    /* a font passes every selected group (OR inside a group, AND across groups) and the search; `skip` leaves one group out */
    function passing(skip) {
      const q = state.q.toLowerCase();
      return (f) => {
        for (const [k, , fn] of CATS) { if (k === skip) continue; const s = state.sel[k]; if (s && s.size && !fn(f).some((v) => s.has(v))) return false; }
        if (q && !f._h.includes(q)) return false;
        return true;
      };
    }
    /* each pill counts what it would show next to the other active filters, so no pill leads to an empty list */
    function liveCounts(k, fn) {
      const m = new Map(), ok = passing(k);
      C.fonts.forEach((f) => { if (ok(f)) fn(f).forEach((v) => m.set(v, (m.get(v) || 0) + 1)); });
      return m;
    }
    function apply() {
      const pass = passing();
      const by = { name: (a, b) => a.n.localeCompare(b.n), oy: (a, b) => (a.y || 9999) - (b.y || 9999), dy: (a, b) => (a.dy || 9999) - (b.dy || 9999), glyphs: (a, b) => b.gl - a.gl };
      const q = state.q.toLowerCase();
      let list = rows.filter((c) => pass(c._font) && (!q || c._h.includes(q)));   // a search for one style finds that style's row
      if (by[state.order]) list = list.slice().sort((a, b) => by[state.order](a._font, b._font));
      const shown = [...grid.children].map((el) => el._row || el);
      const changed = shown.length !== list.length || shown[0] !== list[0];
      const same = !changed && list.every((r, i) => shown[i] === r);
      const els = view === "cards" ? list.map(card) : list;
      if (!same || grid.firstElementChild !== els[0]) grid.replaceChildren(...els);   // same rows in the same order and view: leave the list alone
      grid.className = view === "cards" ? "grid fcs" : "grid list";
      if (changed) {   // a new result set starts at its top, never inside empty space left by the old one
        const sc = grid.closest(".homelist");
        if (sc && sc.scrollHeight > sc.clientHeight) sc.scrollTop = 0;
        else if (scrollY > grid.offsetTop) scrollTo(0, Math.max(0, grid.getBoundingClientRect().top + scrollY - 120));
      }
      const any = Object.keys(state.sel).length || state.q;
      $("#count").textContent = list.length === rows.length ? `Filtering ${list.length} fonts` : `Filtering ${list.length} of ${rows.length} fonts`;
      $("#fclear").hidden = !any;
      renderSide(); save();
    }
    const nq = $("#nq");   // the bar's search is the list's search
    $("#fclear").addEventListener("click", () => { state.sel = {}; state.q = ""; nq.value = ""; apply(); });
    nq.value = state.q; nq.addEventListener("input", (e) => { state.q = e.target.value.trim(); apply(); });
    const rt = $("#retype"); rt.rows = innerWidth < 900 ? 1 : 2;
    const grow = () => { rt.style.height = "auto"; if (rt.value) rt.style.height = rt.scrollHeight + "px"; };
    let tm; $("#retype").oninput = (e) => { grow(); clearTimeout(tm); tm = setTimeout(() => { const t = e.target.value; rows.forEach((r) => (r.querySelector(".ln").textContent = r._font.fo ? figs(r._font, t) : t || r._n)); }, 120); };
    /* Cards / Preview: in cards the preview box goes */
    const vbs = $$(".vmode .pill");
    const setView = (v) => { view = v; store.set("wa-view", v); rt.hidden = v === "cards"; grid.closest(".homegrid")?.classList.toggle("cards", v === "cards");
      vbs.forEach((b) => { const on = b.dataset.v === v; b.classList.toggle("on", on); b.setAttribute("aria-pressed", on); }); };
    vbs.forEach((b) => (b.onclick = () => { if (b.dataset.v !== view) { setView(b.dataset.v); apply(); alignSide(); } }));
    setView(view);
    if (innerWidth < 900) $("#fdet")?.removeAttribute("open");
    apply();
    /* the rule above the first filter group sits on the rule above the second font in the list */
    function alignSide() {
      const r2 = grid.children[1];
      const pk = $("#picked");
      if (!r2 || innerWidth < 900) { pk.style.minHeight = ""; return; }
      if (view === "cards") { pk.style.minHeight = ""; return; }   // no preview box: the first filter rule sits level with the top of the cards (CSS)
      // the selected-filter box fills the space between the write box and the search rule
      pk.style.minHeight = Math.max(16, r2.offsetTop - grid.offsetTop - rt.offsetHeight) + "px";
    }
    const ro = new ResizeObserver(alignSide);
    const watch = () => { ro.disconnect(); [grid.children[0], rt].forEach((el) => el && ro.observe(el)); alignSide(); };
    new MutationObserver(watch).observe(grid, { childList: true });
    let rq; watch(); addEventListener("resize", () => { alignSide(); cancelAnimationFrame(rq); rq = requestAnimationFrame(() => $$(".aa.ok", grid).forEach(fitAa)); });
    const side = $(".homegrid .side"); side?.addEventListener("scroll", () => side.classList.toggle("scrolled", side.scrollTop > 0), { passive: true });
  }

  /* ── timeline: names in their own face; a year jumped to clears the sticky decade strip ── */
  const tl = $("#tl");
  if (tl) {
    $$(".aa", tl).forEach((el) => lazy.observe(el));
    const decs = $(".decs", tl), dh = () => tl.style.setProperty("--decsh", decs.offsetHeight + "px");
    let rq; dh(); addEventListener("resize", () => { dh(); cancelAnimationFrame(rq); rq = requestAnimationFrame(() => $$(".aa.ok", tl).forEach(fitAa)); });
  }

  /* ── catalogue: sortable lister ────────────────────────────────────── */
  const lst = $("#cat");
  if (lst) {
    const body = $(".cbody", lst), rws = [...body.children];
    let key = "no", asc = true;
    function sortBy(k) {
      asc = k === key ? !asc : true; key = k;
      $$(".sortb", lst).forEach((b) => { b.classList.toggle("on", b.dataset.k === k); b.querySelector(".arw")?.remove(); if (b.dataset.k === k) b.insertAdjacentHTML("beforeend", `<svg class="arw ${asc ? "u" : "d"}" viewBox="0 0 18 12" aria-hidden="true"><path d="M1 6H17M12 1L17 6L12 11" vector-effect="non-scaling-stroke"/></svg>`); });
      const v = (r) => (k === "name" ? r.dataset.name : +r.dataset[k]);
      rws.sort((a, b) => { const x = v(a), y = v(b); return (x > y ? 1 : x < y ? -1 : (+a.dataset.no - +b.dataset.no)) * (asc ? 1 : -1); });
      body.replaceChildren(...rws);
    }
    $$(".sortb", lst).forEach((b) => (b.onclick = () => sortBy(b.dataset.k)));
    $(".sortb[data-k=no]", lst)?.classList.add("on");
    $("#tq").oninput = (e) => { const q = e.target.value.toLowerCase(); rws.forEach((r) => (r.hidden = q && !r.textContent.toLowerCase().includes(q))); };
  }
  const pics = $("#pics");
  if (pics) $$(".fn", pics).forEach((el) => lazy.observe(el));

  /* ── font page ─────────────────────────────────────────────────────── */
  const LEAD = { "Large Title": 1.0, Title: 1.05, Headline: 1.15, Body: 1.4, Caption: 1.4 };
  let fontAC = null;   // the current font page's listeners and observers; the hosted shell replaces the page on hash change
  function initFont() {
    const art = $("article.font"), blocks = $("#blocks");
    if (!art || !blocks) return;
    fontAC?.abort(); fontAC = new AbortController();
    const signal = fontAC.signal;
    const sub = $("#subnav"), tpl = $("#subnavtpl");
    if (sub && tpl) { sub.innerHTML = tpl.innerHTML; }
    const secs = $(".secs", sub || document), pn = $(".pname", sub || document);
    if (secs) {   // phone: the pills fade in under the name once scrolled; a very long name takes its own row
      secs.addEventListener("scroll", () => secs.classList.toggle("sc", secs.scrollLeft > 0), { passive: true, signal });
      const long = () => sub.classList.toggle("long", innerWidth <= 800 && pn && pn.scrollWidth > sub.clientWidth * 0.5);
      long(); document.fonts?.ready.then(long); addEventListener("resize", long, { signal });   // again once the UI face has its real width
    }
    const sn = $("#stylenav"), stpl = $("#stylenavtpl");
    if (sn) sn.innerHTML = stpl ? stpl.innerHTML : "";
    setNavH();
    $$("[href^='#']", sub || document).forEach((a) => a.addEventListener("click", (e) => { const t = document.getElementById(a.getAttribute("href").slice(1)); if (t) { e.preventDefault(); t.scrollIntoView({ behavior: "smooth" }); } }));

    const F = JSON.parse($("#faces").textContent || "[]");
    const G = JSON.parse($("#glyphs").textContent || "[]");
    const blks = $$(".blk", blocks);
    const small = innerWidth < 800;
    const P = C.palette || {};
    const defPal = art.dataset.pal;
    let cur = 0, active = blks[0];
    const userSized = new Set();

    blks.forEach((b) => {
      const px = small ? Math.max(12, Math.round(+b.dataset.px * (+b.dataset.px > 30 ? 0.5 : 0.8))) : +b.dataset.px;
      b._px = px; b._lh = LEAD[b.dataset.role] ?? 1.0; b._tr = 0;
      paint(b);
    });
    function paint(b) {
      const ed = $(".ed", b);
      ed.style.fontSize = b._px + "px"; ed.style.setProperty("--blh", b._lh); ed.style.setProperty("--btr", b._tr + "em");
      $(".vl b", b).textContent = Math.round(b._px);
      capAlign(b);
    }
    /* the vertical label starts at the cap height of the first line */
    function capAlign(b) {
      const f = F[cur]; if (!f) return;
      meas.font = `${b._px}px "${f.id}"`;
      const m = meas.measureText("H"), ed = $(".ed", b);
      const fA = m.fontBoundingBoxAscent, fD = m.fontBoundingBoxDescent, cA = m.actualBoundingBoxAscent;
      if (!fA || !cA) return;
      const iA = Math.max(cA, meas.measureText(ed.textContent.split("\n")[0] || "H").actualBoundingBoxAscent);   // tallest ink of the text itself
      const lh = (b.classList.contains("cols") ? 1.4 : b._lh) * b._px;
      const above = (lh - (fA + fD)) / 2 + fA - iA;   // empty line space above the ink
      ed.style.marginTop = -Math.max(0, Math.round(above)) + "px";   // ink starts where the block's padding ends
      // the label starts at the cap height of the first line, measured from the laid-out first letter
      const vl = $(".vl", b), t = ed.firstChild;
      vl.style.marginTop = "0px";
      if (t && t.nodeType === 3 && t.length) {
        const rg = document.createRange(); rg.setStart(t, 0); rg.setEnd(t, 1);
        const capTop = rg.getBoundingClientRect().top + fA - cA;   // a glyph's range box starts one font ascent above its baseline
        vl.style.marginTop = Math.max(0, Math.round(capTop - vl.getBoundingClientRect().top)) + "px";
      } else vl.style.marginTop = Math.round(iA - cA) + "px";
    }
    function sync() {
      $("#sz").value = active._px; $("#szo").textContent = Math.round(active._px);
      $("#lh").value = active._lh; $("#lho").textContent = (+active._lh).toFixed(2);
      $("#tr").value = active._tr; $("#tro").textContent = (+active._tr).toFixed(3);
    }
    function activate(b) { if (!b || b === active) return; active.classList.remove("on"); active = b; b.classList.add("on"); sync(); }
    blks.forEach((b) => { b.addEventListener("pointerdown", () => activate(b)); $(".ed", b).addEventListener("focus", () => activate(b)); });
    $("#sz").oninput = (e) => { active._px = +e.target.value; userSized.add(active); fit(active); sync(); };
    $("#lh").oninput = (e) => { active._lh = +e.target.value; paint(active); sync(); };
    $("#tr").oninput = (e) => { active._tr = +e.target.value; fit(active); sync(); };

    const feats = () => $$(".feat input", art).map((i) => `"${i.value}" ${i.checked ? 1 : 0}`).join(", ") || "normal";
    function applyFace() {
      const f = F[cur]; if (!f) return;
      art.style.setProperty("--ff", `"${f.id}"`); blocks.style.setProperty("--ff", `"${f.id}"`);
      art.style.setProperty("--fea", feats()); blocks.style.setProperty("--fea", feats());
      $$(".wf .tx", art).forEach((el) => (el.style.fontFeatureSettings = feats()));
    }
    /* fit: one line across the measure, sized from the line as the browser lays it out (tracking and features included) and from its ink,
       so swashes that reach past the first or last letter fit too: the left overhang is indented, never clipped. A block sized by hand wraps. */
    const probe = document.createElement("span");
    probe.style.cssText = "position:absolute;left:-99999px;top:0;visibility:hidden;white-space:pre;font-size:100px";
    document.body.appendChild(probe);
    signal.addEventListener("abort", () => probe.remove());
    function fit(b) {
      const f = F[cur], ed = $(".ed", b);
      if (!f || !b.classList.contains("fit")) { paint(b); return; }
      if (userSized.has(b)) { b.classList.add("wrapped"); ed.style.textIndent = ""; paint(b); return; }
      const t = ed.textContent;
      probe.style.fontFamily = `"${f.id}"`; probe.style.letterSpacing = b._tr + "em"; probe.style.fontFeatureSettings = feats(); probe.textContent = t;
      const w = probe.getBoundingClientRect().width || 1;
      meas.font = `100px "${f.id}"`;
      const m = meas.measureText(t), oL = Math.max(0, m.actualBoundingBoxLeft), oR = Math.max(0, m.actualBoundingBoxRight - m.width);
      const avail = ed.clientWidth, floor = 2 * parseFloat(css("--ui"));
      const px = Math.floor(Math.min((avail / w) * 100 * 0.97, (avail / (w + oL + oR)) * 100));   // the measure with a little air; the ink within it
      b.classList.toggle("wrapped", px < floor);   // text too long for one readable line wraps at the floor instead
      b._px = Math.min(small ? 160 : 420, Math.max(floor, px));
      ed.style.textIndent = b.classList.contains("wrapped") || !oL ? "" : ((oL * b._px) / 100).toFixed(1) + "px";
      paint(b); if (b === active) sync();
    }
    function fitBlocks() { if (F[cur]) $$(".blk", blocks).forEach(fit); }   // every block repaints with the real face's metrics
    blks.forEach((b) => { if (b.classList.contains("fit")) { let q; $(".ed", b).addEventListener("input", () => { cancelAnimationFrame(q); q = requestAnimationFrame(() => fit(b)); }); } });
    $$(".feat input", art).forEach((i) => (i.onchange = () => { applyFace(); fitBlocks(); }));
    /* set: each member is listed in its own font, loaded as it nears the screen; the style pills in the bar switch the specimen */
    const setLis = $$(".fl li[data-i]", art);
    if (setLis.length) {
      const sio = new IntersectionObserver((es) => es.forEach((e) => { if (!e.isIntersecting) return; sio.unobserve(e.target);
        const i = +e.target.dataset.i; load(F[i]).then((id) => ($(".fn", e.target).style.fontFamily = `"${id}", "WA Blank"`)).catch(() => {}); }), { rootMargin: "400px" });
      signal.addEventListener("abort", () => sio.disconnect());
      setLis.forEach((li) => sio.observe(li));
    }
    const sbs = $$("#stylenav .styles button");
    const want = store.get("wa-style"); try { sessionStorage.removeItem("wa-style"); } catch {}   // a style row clicked in the list opens with that style on
    sbs.forEach((b) => b.addEventListener("click", () => { const n = +b.dataset.i; if (n === cur) return;
      load(F[n]).then(() => {   // a face that fails keeps the previous one
        cur = n; applyFace(); fitBlocks(); drawGlyphs();
        sbs.forEach((x) => { x.classList.toggle("on", x === b); x.setAttribute("aria-pressed", x === b); });
      }).catch(() => {}); }));

    /* colour */
    function setPal(k) {
      $$(".sw", art).forEach((s) => s.classList.toggle("on", s.dataset.p === k));
      window.WA_theme?.(k === "plain" || !P[k] ? null : P[k]);
      art.dataset.cur = k; window._redrawFont?.();
    }
    window._setPal = setPal;
    setPal(document.documentElement.dataset.mode === "random" ? (window.WA_PICK || defPal) : "plain");

    /* waterfall */
    const wf = $("#wf");
    const wfSrc = blks.find((b) => b.dataset.role === "Title") || blks[0];
    function wfText() { $$(".wf .tx", art).forEach((el) => (el.textContent = $(".ed", wfSrc).textContent)); }
    if (wf) {
      wf.replaceChildren();
      [12, 16, 20, 24, 32, 48, 64, 96].forEach((px) => {
        const r = document.createElement("div"); r.className = "wf";
        r.innerHTML = `<span class="px tnum">${px}</span><span class="tx" style="font-size:${px}px"></span>`;
        wf.appendChild(r);
      });
      wfText(); $(".ed", wfSrc).addEventListener("input", wfText);
    }

    blocks.classList.add("waiting");
    F.slice(1).forEach((f) => load(f).catch(() => {}));
    load(F[0]).then(() => { blocks.classList.remove("waiting"); applyFace(); fitBlocks(); drawGlyphs(); sync();
      const [ws, wi] = (want || "").split(":"); if (ws === art.dataset.slug && +wi) sbs.find((b) => +b.dataset.i === +wi)?.click(); })
      .catch(() => { blocks.classList.remove("waiting"); blocks.innerHTML = `<p class="msg">This font file can’t be shown in a browser. The original archives are under Files below.</p>`; });
    let rz; addEventListener("resize", () => { clearTimeout(rz); rz = setTimeout(fitBlocks, 150); }, { signal });
    signal.addEventListener("abort", () => { clearTimeout(rz); gio?.disconnect(); });
    sync();

    /* glyph grid — shared baseline, each glyph centred on its own ink horizontally */
    const gl = $("#gl");
    $("#gcount").textContent = G.length ? `${G.length.toLocaleString("en")} characters` : "";
    const ranges = [[0x20, 0x7F, "Basic Latin"], [0xA0, 0x100, "Latin-1"], [0x100, 0x250, "Latin Extended"], [0x250, 0x370, "IPA and modifiers"],
      [0x370, 0x400, "Greek"], [0x400, 0x530, "Cyrillic"], [0x1E00, 0x1F00, "Latin Additional"], [0x1F00, 0x2000, "Greek Extended"],
      [0x2000, 0x2100, "Punctuation and currency"], [0x2100, 0x2200, "Letterlike and number forms"], [0xFB00, 0xFB50, "Ligatures"], [0, 0x110000, "Other"]];
    let gio;
    function drawGlyphs() {
      const f = F[cur]; if (!f || !gl) return;
      gl.replaceChildren(); gio?.disconnect();
      gio = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { drawG(e.target); gio.unobserve(e.target); } }), { rootMargin: "200px" });
      const done = new Set();
      ranges.forEach(([a, b, name]) => {
        const cps = G.filter((c) => c >= a && c < b && !done.has(c)); if (!cps.length) return;
        cps.forEach((c) => done.add(c));
        const blk = document.createElement("div"); blk.className = "gblock";
        const h = document.createElement("h3"); h.className = "vlab"; h.textContent = `${name} ${cps.length}`;
        const cells = document.createElement("div"); cells.className = "gcells";
        blk.append(h, cells); gl.appendChild(blk);
        cps.forEach((c) => {
          const d = document.createElement("div"); d.className = "g"; d._cp = c;
          const hex = c.toString(16).toUpperCase().padStart(4, "0");
          d.innerHTML = `<canvas></canvas><span>${hex}</span>`; d.title = `U+${hex}`;
          cells.appendChild(d); gio.observe(d);
        });
      });
    }
    function drawG(d) {
      const f = F[cur], ch = String.fromCodePoint(d._cp);
      const { ctx, W, H } = prep(d.querySelector("canvas"));
      meas.font = `100px "${f.id}"`;
      const cap = meas.measureText("H").actualBoundingBoxAscent || 70;
      const s = (H * 0.42) / cap, m = meas.measureText(ch);
      ctx.font = `${100 * s}px "${f.id}"`;
      ctx.fillText(ch, W / 2 - ((m.actualBoundingBoxRight - m.actualBoundingBoxLeft) / 2) * s, H / 2 + (cap * s) / 2);
    }
    window._redrawFont = () => { $$(".gl .g", art).forEach((d) => d.querySelector("canvas").width && drawG(d)); };
  }
  initFont();

  /* pill labels: a lone letter in a circle sits on its ink box; words sit on their cap band (baseline to cap height) */
  const inkCache = new Map(), inkCv = document.createElement("canvas"), inkCx = inkCv.getContext("2d", { willReadFrequently: true });
  function inkOf(text, font) {   // centroid of the ink in em: x from the pen start, y above the baseline; plus advance and font box
    const k = font + "|" + text;
    if (inkCache.has(k)) return inkCache.get(k);
    inkCx.font = `${font.replace(/[\d.]+px/, "100px")}`;
    const m = inkCx.measureText(text), w = Math.ceil(m.width) + 40, h = 300;
    inkCv.width = w; inkCv.height = h; inkCx.font = `${font.replace(/[\d.]+px/, "100px")}`; inkCx.fillText(text, 20, 200);
    const d = inkCx.getImageData(0, 0, w, h).data; let sx = 0, sy = 0, sw = 0;
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) { const a = d[(y * w + x) * 4 + 3]; if (a) { sx += a * x; sy += a * y; sw += a; } }
    const r = sw ? { cx: (sx / sw - 20) / 100, cy: (200 - sy / sw) / 100, bx: (m.actualBoundingBoxRight - m.actualBoundingBoxLeft) / 200, cap: inkCx.measureText("H").actualBoundingBoxAscent / 100, by: (m.actualBoundingBoxAscent - m.actualBoundingBoxDescent) / 200, adv: m.width / 100, fA: m.fontBoundingBoxAscent / 100, fD: m.fontBoundingBoxDescent / 100 } : null;
    inkCache.set(k, r); return r;
  }
  const NUDGE = 2;   // px: labels sit 2px right of their computed centre
  const CENTRED = 0.05;   // em: WA UI's letters now carry half their old right sidebearing on the left (tools/uifonts.py centre(): Wiegel set them flush left, ~0.1em all on the right), so their ink sits this much further right; word labels take it back from NUDGE and stay where Okay tuned them
  const RASTER = 0.029;   // measured: rendered glyphs sit 0.029em lower than canvas metrics place them (8× screenshots of C, M and the nav pills)
  const PILLS = ".pill:not(.small), .top a:not(.home), .top button, .top .crumb, .pnav a";
  function inkCenter(el) {
    const cs = getComputedStyle(el);
    if (!el._pad) el._pad = [parseFloat(cs.paddingTop), parseFloat(cs.paddingBottom), parseFloat(cs.paddingLeft), parseFloat(cs.paddingRight)];
    let t = [...el.childNodes].map((n) => (n.nodeType === 3 || n.tagName === "SPAN" ? n.textContent : "")).join("").replace(/\s+/g, " ").trim();
    if (!t) return;
    if (cs.textTransform === "uppercase") t = t.toUpperCase();
    const size = parseFloat(cs.fontSize), ink = inkOf(t, `${cs.fontStyle} ${cs.fontWeight} ${size}px ${cs.fontFamily}`);
    if (!ink || !ink.fA) return;
    const circle = el.classList.contains("mode") || el.classList.contains("cinv");   // a lone letter in a circle sits on its ink box, which reads as centred; words sit on their weight
    const cx = circle ? ink.bx : ink.cx, cy = circle ? ink.by : ink.cap / 2;   // words: the band from baseline to cap height sits on the pill's middle (ascenders and descenders hang out evenly)
    const [pt, pb] = el._pad, L = parseFloat(cs.lineHeight) || size * 1.2;
    const baseline = pt + (L - (ink.fA + ink.fD) * size) / 2 + ink.fA * size;
    const shift = (pt + L + pb) / 2 - (baseline - cy * size) - RASTER * size;   // + moves the text down
    const dy = Math.max(-pt, Math.min(pb, shift));
    el.style.paddingTop = pt + dy + "px"; el.style.paddingBottom = pb - dy + "px";
    // sideways: circles centre their letter's ink box; every label then sits NUDGE px right (tuned by eye on Okay's iPad)
    const sx = circle ? (ink.adv / 2 - cx) * size + NUDGE : NUDGE - CENTRED * size, [, , pl, pr] = el._pad;
    if (circle) { el.style.paddingLeft = Math.max(0, 2 * sx) + "px"; el.style.paddingRight = Math.max(0, -2 * sx) + "px"; }   // asymmetric padding, not text-indent: Safari centres an indented line differently
    else { el.style.paddingLeft = pl + sx + "px"; el.style.paddingRight = Math.max(0, pr - sx) + "px"; }
  }
  let inkQ = 0;
  const inkAll = () => { if (inkQ) return; inkQ = requestAnimationFrame(() => { inkQ = 0; $$(PILLS).forEach(inkCenter); }); };
  new MutationObserver((ms) => { if (ms.some((m) => !m.target.closest?.("#grid"))) inkAll(); }).observe(document.body, { childList: true, subtree: true });   // the font list holds no pills
  inkAll(); document.fonts?.ready?.then(() => { inkCache.clear(); inkAll(); });

  /* UI faces (Wiegel's Preussische IV 44 + Proletarsk) via FontFace too, so they also work where CSS font URLs are blocked */
  (window.UIFONTS || []).forEach((u) => {
    fetch(R + u.src).then((r) => r.arrayBuffer()).then((buf) => new FontFace(u.family, buf, { weight: String(u.weight), style: u.italic ? "italic" : "normal" }).load())
      .then((x) => { document.fonts.add(x); redrawAll(); inkCache.clear(); inkAll(); }).catch(() => {});
  });

  /* the interface copies (Account › On this site): the hosted page cannot start a download itself, so it hands the file
     to the viewer through the artifact's downloads capability; where that is missing the link is hidden */
  if (window.HOSTED) {
    let saver;
    const ready = (window.claude?.use ? window.claude.use("downloads") : Promise.resolve(null)).catch(() => null)
      .then((d) => { saver = d; document.documentElement.classList.toggle("nosave", !d); return d; });
    document.addEventListener("click", async (e) => {
      const a = e.target.closest?.("a[data-save]");
      if (!a) return;
      e.preventDefault();
      const d = saver ?? await ready;
      if (!d) return;
      try {
        const buf = await (await fetch(R + a.getAttribute("href"))).arrayBuffer();
        await d.save({ filename: a.dataset.save, data: buf });
      } catch (err) { if (!["declined", "rate_limited"].includes(err?.code)) console.warn("download:", err?.code || err); }
    });
  }

  /* hosted shell: font.html#slug pulls the page body from a pack */
  const shell = $("#fontshell");
  if (shell) {
    const order = C.fonts.map((f) => f.s);
    const cache = {};
    let showing = 0;   // a newer hash wins over a slower pack still loading
    const missing = (slug) => {   // the slug is shown as text, never parsed as HTML
      const p = document.createElement("p"); p.className = "lead";
      const a = document.createElement("a"); a.href = "index.html"; a.textContent = "Back to the index";
      p.append(`No font called “${slug}”. `, a, "."); shell.replaceChildren(p);
    };
    async function show() {
      const tok = ++showing;
      let slug = location.hash.slice(1);
      try { slug = decodeURIComponent(slug); } catch {}
      slug = slug || order[0];
      const i = order.indexOf(slug);
      if (i < 0) { if (document.getElementById(slug)) return; missing(slug); return; }
      const pk = Math.floor(i / (window.PACK || 20));
      cache[pk] = cache[pk] || fetch(`pages/p${pk}.json`).then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); });
      let pack;
      try { pack = await cache[pk]; } catch { delete cache[pk]; if (tok === showing) missing(slug); return; }   // a failed pack is fetched again next time
      if (tok !== showing) return;
      shell.innerHTML = pack[slug];
      document.title = C.fonts[i].n + " — Wiegel Archive";
      scrollTo(0, 0);
      initFont();
    }
    addEventListener("hashchange", show);
    show();
  }
})();
