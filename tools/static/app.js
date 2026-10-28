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

  const onScroll = () => document.documentElement.classList.toggle("scrolled", scrollY > 0);
  addEventListener("scroll", onScroll, { passive: true }); onScroll();

  /* top-bar search: Enter searches the index (here, or by going there with the query) */
  const ns = $(".nsearch");
  ns?.addEventListener("submit", (e) => {
    e.preventDefault();
    const q = $("#nq").value.trim(), side = $("#q");
    if (side) { side.value = q; side.dispatchEvent(new Event("input")); return; }
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
    cbtn?.classList.toggle("on", !!pick);
    $$(".mode[data-m=mono]").forEach((b) => b.classList.toggle("on", root.dataset.mode === "mono"));
    $$("#cpanel .sw[data-p]").forEach((s) => s.classList.toggle("on", s.dataset.p === pick));
    $("#cinv")?.classList.toggle("on", !!window.WA_INV);
  }
  function applyColour() {
    const art = $("article.font");
    if (root.dataset.mode === "mono") { art && window._setPal ? window._setPal("plain") : window.WA_theme?.(null); }
    else if (window.WA_PICK) { art && window._setPal ? window._setPal(window.WA_PICK) : window.WA_theme?.(PAL[window.WA_PICK]); }
    else { art && window._setPal ? window._setPal(art.dataset.pal) : window.WA_theme?.(null); }
    markModes(); redrawAll();
  }
  const openPanel = (on) => { if (!cpanel) return;
    if (on) {   // the pill reaches past the search; if its swatches need more room it covers whole neighbours, never half of one
      cpanel.style.minWidth = ""; cpanel.hidden = false;
      const right = cbtn.getBoundingClientRect().right, need = right - cpanel.scrollWidth;
      const items = [...cbtn.closest(".nav1").children].filter((el) => !el.contains(cbtn) && !el.classList.contains("home")).reverse();
      let left = right;
      for (const el of items) { const r = el.getBoundingClientRect(); left = r.left; if (r.left <= need && el.matches(".nsearch, a, form")) break; }
      const W = Math.ceil(right - Math.min(left, need)), cw = cbtn.offsetWidth, sws = $$(".sw", cpanel), n = sws.length;
      const g = Math.max(4, (W - cw - n * sws[0].offsetWidth) / (n + 1));   // the same gap before, between and after
      cpanel.style.minWidth = W + "px"; cpanel.style.gap = g + "px"; cpanel.style.paddingLeft = g + "px"; cpanel.style.paddingRight = cw + g + "px";
    }
    cpanel.hidden = !on; cbtn.setAttribute("aria-expanded", on); cbtn.closest(".cpick").classList.toggle("open", on); };
  cbtn?.addEventListener("click", () => openPanel(cpanel.hidden));
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
  document.addEventListener("click", (e) => { if (cpanel && !cpanel.hidden && !e.target.closest(".cpick")) openPanel(false); });
  $$(".mode[data-m=mono]").forEach((b) => (b.onclick = () => {
    const again = root.dataset.mode === "mono";
    root.dataset.mode = "mono"; store.set("wa-mode", "mono", true);
    if (again) window.WA_theme?.(null); else applyColour();
    markModes(); redrawAll();
  }));
  markModes();
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
    const p = fetch(R + src).then((r) => { if (!r.ok) throw new Error(r.status); return r.arrayBuffer(); })
      .then((buf) => new FontFace(id, buf).load()).then((x) => { document.fonts.add(x); return x; });
    faces.set(id, p);
    return p.then(() => id);
  }
  const load = (f) => (f ? loadSrc(f.src, f.id) : Promise.reject());

  /* lazily set names in their own face (timeline, list) */
  const lazy = new IntersectionObserver((es) => es.forEach((e) => {
    if (!e.isIntersecting) return;
    lazy.unobserve(e.target);
    const el = e.target;
    if (!el.dataset.src) { el.classList.add("ok"); return; }
    loadSrc(el.dataset.src).then((id) => { el.style.fontFamily = `"${id}"`; el.classList.add("ok"); }).catch(() => el.classList.add("ok"));
  }), { rootMargin: "600px 0px" });

  /* ink-centred fitting on canvas: scale by cap height, clamp to the ink box, centre the ink box */
  const meas = document.createElement("canvas").getContext("2d");
  function fit(ctx, W, H, family, text) {
    meas.font = `100px "${family}"`;
    const m = meas.measureText(text);
    const L = m.actualBoundingBoxLeft, Rr = m.actualBoundingBoxRight, A = m.actualBoundingBoxAscent, D = m.actualBoundingBoxDescent;
    const cap = meas.measureText("H").actualBoundingBoxAscent || A || 70;
    const iw = Math.max(1, L + Rr), ih = Math.max(1, A + D);
    let s = Math.min((H * 0.42) / cap, (W * 0.86) / iw, (H * 0.78) / ih);
    if (!isFinite(s) || s <= 0) s = 0.2;
    ctx.font = `${100 * s}px "${family}"`;
    ctx.fillText(text, W / 2 - ((Rr - L) / 2) * s, H / 2 + ((A - D) / 2) * s);
  }
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
      ["fa", "Family", (f) => [f.fa]],
      ["oy", "Original", (f) => [bucket(f.y)]],
      ["dy", "Digitised", (f) => [f.dy ? String(f.dy) : "Unknown"]],
      ["cv", "Script", (f) => f.cv.map((k) => SCRIPTS[k]).filter(Boolean)],
      ["ic", "Features", (f) => f.ic.map((k) => (C.icons || {})[k]).filter(Boolean)],
      ["pl", "Place", (f) => [f.ph ? "Photographed" : null, f.pl ? "Has a place" : "No place"].filter(Boolean)],
    ];
    const ORDERS = [["index", "Wiegel’s order"], ["name", "A to Z"], ["oy", "Original date"], ["dy", "Digitised"], ["glyphs", "Most glyphs"]];
    const vals = {};
    CATS.forEach(([k, , fn]) => { const m = new Map(); C.fonts.forEach((f) => fn(f).forEach((v) => m.set(v, (m.get(v) || 0) + 1))); vals[k] = m; });
    const num = (v) => parseInt(v) || (v === "Before 1800" ? 0 : 9999);
    const sortVals = (k, m) => {
      const e = [...m.entries()];
      if (k === "fa") return e.sort((a, b) => C.families.indexOf(a[0]) - C.families.indexOf(b[0]));
      if (k === "oy" || k === "dy") return e.sort((a, b) => num(a[0]) - num(b[0]));
      return e.sort((a, b) => b[1] - a[1]);
    };
    const state = { sel: {}, q: "", order: "index" };
    try { const s = JSON.parse(store.get("wa-index2") || "{}"); Object.assign(state, s); } catch {}
    Object.keys(state.sel).forEach((k) => (state.sel[k] = new Set(state.sel[k])));
    const save = () => store.set("wa-index2", JSON.stringify({ ...state, sel: Object.fromEntries(Object.entries(state.sel).map(([k, v]) => [k, [...v]])) }));
    const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
    const ico = (c) => `<svg class="ic" width="18" height="18"><use href="#i-${c}"/></svg>`;
    const rows = C.fonts.map((f) => {
      const a = document.createElement("a");
      a.className = "lrow tnum"; a.href = flink(f.s); a._font = f;
      a.innerHTML = `<span class="meta info tnum"><span class="oy"></span><span class="dy"></span><span class="fa">${esc(f.fa)}</span><span class="ics">${f.ic.slice(0, 8).map(ico).join("")}</span><span class="no">${pad(f.no)}</span></span>`
        + `<span class="ln" data-src="${f.f[0] ? esc(f.f[0].src) : ""}">${esc(f.n)}</span>`;
      return a;
    });
    rows.forEach((r) => lazy.observe(r.querySelector(".ln")));

    const pill = (label, n, on, fn) => { const b = document.createElement("button"); b.type = "button"; b.className = "pill" + (on ? " on" : "");
      if (n === 0 && !on) { b.classList.add("zero"); b.disabled = true; }
      b.innerHTML = `${esc(label)}${n != null ? ` <span class="n tnum">${n}</span>` : ""}`; b.setAttribute("aria-pressed", !!on); b.onclick = fn; return b; };
    function renderSide() {
      const box = $("#fside"); box.replaceChildren();
      const group = (title, kids) => { const g = document.createElement("div"); g.className = "fg"; const h = document.createElement("h3"); h.className = "vlab"; h.textContent = title; const w = document.createElement("div"); w.className = "pills"; w.append(...kids); g.append(w, h); box.appendChild(g); };
      const pk = $("#picked"), toggle = (k, v) => { const s = (state.sel[k] = state.sel[k] || new Set()); s.has(v) ? s.delete(v) : s.add(v); if (!s.size) delete state.sel[k]; apply(); };
      pk.replaceChildren(...CATS.flatMap(([k]) => [...(state.sel[k] || [])].map((v) => { const b = pill(v, null, true, () => toggle(k, v)); b.insertAdjacentHTML("beforeend", '<svg class="x" viewBox="0 0 18 18" aria-hidden="true"><path d="M2 2L16 16M16 2L2 16" vector-effect="non-scaling-stroke"/></svg>'); b.setAttribute("aria-label", "Remove " + v); return b; })));
      group("Order", ORDERS.map(([k, l]) => pill(l, null, state.order === k, () => { state.order = k; apply(); })));
      CATS.forEach(([k, label, fn]) => {
        const sel = state.sel[k] || new Set(), live = liveCounts(k, fn);
        group(label, sortVals(k, vals[k]).map(([v]) => [v, live.get(v) || 0]).map(([v, n]) => pill(v, n, sel.has(v), () => toggle(k, v))));
      });
    }
    /* a font passes every selected group (OR inside a group, AND across groups) and the search; `skip` leaves one group out */
    function passing(skip) {
      const q = state.q.toLowerCase();
      return (f) => {
        for (const [k, , fn] of CATS) { if (k === skip) continue; const s = state.sel[k]; if (s && s.size && !fn(f).some((v) => s.has(v))) return false; }
        if (q && !(f.n + " " + (f.pl || "") + " " + f.tg.join(" ") + " " + f.g + " " + f.fa + " " + f.sum + " " + pad(f.no)).toLowerCase().includes(q)) return false;
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
      let list = rows.filter((c) => pass(c._font));
      if (by[state.order]) list = list.slice().sort((a, b) => by[state.order](a._font, b._font));
      list.forEach((r, i) => {   // OG / DG named on the first row only; columns stay aligned
        const f = r._font;
        r.querySelector(".oy").textContent = f.y ? (i ? "" : "OG ") + f.y : "";
        r.querySelector(".dy").textContent = f.dy ? (i ? "" : "DG ") + f.dy : "";
      });
      const changed = grid.children.length !== list.length || grid.firstElementChild !== list[0];
      grid.replaceChildren(...list);
      if (changed) {   // a new result set starts at its top, never inside empty space left by the old one
        const sc = grid.closest(".homelist");
        if (sc && sc.scrollHeight > sc.clientHeight) sc.scrollTop = 0;
        else if (scrollY > grid.offsetTop) scrollTo(0, Math.max(0, grid.getBoundingClientRect().top + scrollY - 120));
      }
      const any = Object.keys(state.sel).length || state.q;
      $("#count").textContent = list.length === C.fonts.length ? `Filtering ${list.length} fonts` : `Filtering ${list.length} of ${C.fonts.length} fonts`;
      $("#fclear").hidden = !any;
      renderSide(); save();
    }
    $("#fclear").addEventListener("click", () => { state.sel = {}; state.q = ""; $("#q").value = ""; apply(); });
    $("#q").value = state.q; $("#q").oninput = (e) => { state.q = e.target.value; apply(); };
    const rt = $("#retype"); rt.rows = innerWidth < 900 ? 1 : 2;
    const grow = () => { rt.style.height = "auto"; if (rt.value) rt.style.height = rt.scrollHeight + "px"; };
    let tm; rt.addEventListener("input", grow); $("#retype").oninput = (e) => { grow(); clearTimeout(tm); tm = setTimeout(() => { const t = e.target.value; rows.forEach((r) => (r.querySelector(".ln").textContent = t || r._font.n)); }, 120); };
    if (innerWidth < 900) $("#fdet")?.removeAttribute("open");
    apply();
    /* the rule above Search sits on the rule above the second font in the list */
    function alignSide() {
      const r2 = grid.children[1];
      const pk = $("#picked");
      if (!r2 || innerWidth < 900) { pk.style.minHeight = ""; return; }
      // the selected-filter box fills the space between the write box and the search rule
      pk.style.minHeight = Math.max(16, r2.offsetTop - grid.offsetTop - rt.offsetHeight) + "px";
    }
    const ro = new ResizeObserver(alignSide);
    const watch = () => { ro.disconnect(); [grid.children[0], rt].forEach((el) => el && ro.observe(el)); alignSide(); };
    new MutationObserver(watch).observe(grid, { childList: true });
    watch(); addEventListener("resize", alignSide);
    const side = $(".homegrid .side"); side?.addEventListener("scroll", () => side.classList.toggle("scrolled", side.scrollTop > 0), { passive: true });
  }

  /* ── timeline: names in their own face, a font's entries light up together ── */
  const tl = $("#tl");
  if (tl) {
    $$(".fn", tl).forEach((el) => lazy.observe(el));
    let cur = null;
    const mark = (s, on) => $$(`.ev[data-s="${CSS.escape(s)}"]`, tl).forEach((e) => e.classList.toggle("hl", on));
    tl.addEventListener("pointerover", (e) => { const ev = e.target.closest(".ev"); const s = ev?.dataset.s || null; if (s === cur) return; if (cur) mark(cur, false); cur = s; if (s) mark(s, true); });
    tl.addEventListener("pointerleave", () => { if (cur) mark(cur, false); cur = null; });
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
  function initFont() {
    const art = $("article.font"), blocks = $("#blocks");
    if (!art || !blocks) return;
    const sub = $("#subnav"), tpl = $("#subnavtpl");
    if (sub && tpl) { sub.innerHTML = tpl.innerHTML; setNavH(); }
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
      $(".vl", b).style.marginTop = Math.round(iA - cA) + "px";      // label still starts at cap height
    }
    function sync() {
      $("#sz").value = active._px; $("#szo").textContent = Math.round(active._px);
      $("#lh").value = active._lh; $("#lho").textContent = (+active._lh).toFixed(2);
      $("#tr").value = active._tr; $("#tro").textContent = (+active._tr).toFixed(3);
    }
    function activate(b) { if (!b || b === active) return; active.classList.remove("on"); active = b; b.classList.add("on"); sync(); }
    blks.forEach((b) => { b.addEventListener("pointerdown", () => activate(b)); $(".ed", b).addEventListener("focus", () => activate(b)); });
    $("#sz").oninput = (e) => { active._px = +e.target.value; userSized.add(active); paint(active); sync(); };
    $("#lh").oninput = (e) => { active._lh = +e.target.value; paint(active); sync(); };
    $("#tr").oninput = (e) => { active._tr = +e.target.value; paint(active); sync(); };

    const feats = () => $$(".feat input", art).map((i) => `"${i.value}" ${i.checked ? 1 : 0}`).join(", ") || "normal";
    function applyFace() {
      const f = F[cur]; if (!f) return;
      art.style.setProperty("--ff", `"${f.id}"`); blocks.style.setProperty("--ff", `"${f.id}"`);
      art.style.setProperty("--fea", feats()); blocks.style.setProperty("--fea", feats());
      $$(".wf .tx", art).forEach((el) => (el.style.fontFeatureSettings = feats()));
    }
    function fitBlocks() {
      const f = F[cur]; if (!f) return;
      $$(".blk.fit", blocks).forEach((b) => {
        if (userSized.has(b)) return;
        const ed = $(".ed", b);
        meas.font = `100px "${f.id}"`;
        const w = meas.measureText(ed.textContent).width || 1;
        const avail = ed.clientWidth;
        const px = Math.floor((avail / w) * 100 * 0.97), floor = 2 * parseFloat(css("--ui"));   // one line across the measure
        b.classList.toggle("wrapped", px < floor);   // text too long for one readable line wraps at the floor instead
        b._px = Math.min(small ? 160 : 420, Math.max(floor, px));
        paint(b); if (b === active) sync();
      });
    }
    $$(".feat input", art).forEach((i) => (i.onchange = applyFace));
    $("#style")?.addEventListener("change", (e) => { cur = +e.target.value; load(F[cur]).then(() => { applyFace(); fitBlocks(); drawGlyphs(); }); });

    /* colour */
    function setPal(k) {
      $$(".sw", art).forEach((s) => s.classList.toggle("on", s.dataset.p === k));
      window.WA_theme?.(k === "plain" || !P[k] ? null : P[k]);
      if (k === "plain" && document.documentElement.dataset.mode === "random") { const r = document.documentElement.style; r.removeProperty("--paper"); r.removeProperty("--ink"); }
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
    load(F[0]).then(() => { blocks.classList.remove("waiting"); applyFace(); fitBlocks(); drawGlyphs(); sync(); })
      .catch(() => { blocks.classList.remove("waiting"); blocks.innerHTML = `<p class="msg">This font file can’t be shown in a browser. The original archives are under Files below.</p>`; });
    let rz; addEventListener("resize", () => { clearTimeout(rz); rz = setTimeout(fitBlocks, 150); });
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
  window.WA_initFont = initFont;
  initFont();

  /* pill labels sit on their ink's centre of weight, not on the font's line box */
  const inkCache = new Map(), inkCv = document.createElement("canvas"), inkCx = inkCv.getContext("2d", { willReadFrequently: true });
  function inkOf(text, font) {   // centroid of the ink in em: x from the pen start, y above the baseline; plus advance and font box
    const k = font + "|" + text;
    if (inkCache.has(k)) return inkCache.get(k);
    inkCx.font = `${font.replace(/[\d.]+px/, "100px")}`;
    const m = inkCx.measureText(text), w = Math.ceil(m.width) + 40, h = 300;
    inkCv.width = w; inkCv.height = h; inkCx.font = `${font.replace(/[\d.]+px/, "100px")}`; inkCx.fillText(text, 20, 200);
    const d = inkCx.getImageData(0, 0, w, h).data; let sx = 0, sy = 0, sw = 0;
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) { const a = d[(y * w + x) * 4 + 3]; if (a) { sx += a * x; sy += a * y; sw += a; } }
    const r = sw ? { cx: (sx / sw - 20) / 100, cy: (200 - sy / sw) / 100, bx: (m.actualBoundingBoxRight - m.actualBoundingBoxLeft) / 200, by: (m.actualBoundingBoxAscent - m.actualBoundingBoxDescent) / 200, adv: m.width / 100, fA: m.fontBoundingBoxAscent / 100, fD: m.fontBoundingBoxDescent / 100 } : null;
    inkCache.set(k, r); return r;
  }
  const RASTER = 0.029;   // measured: rendered glyphs sit 0.029em lower than canvas metrics place them (8× screenshots of C, M and the nav pills)
  const PILLS = ".pill, .top a:not(.home), .top button, .top .crumb, .pnav a";
  function inkCenter(el) {
    const cs = getComputedStyle(el);
    if (!el._pad) el._pad = [parseFloat(cs.paddingTop), parseFloat(cs.paddingBottom)];
    let t = [...el.childNodes].map((n) => (n.nodeType === 3 || n.tagName === "SPAN" ? n.textContent : "")).join("").replace(/\s+/g, " ").trim();
    if (!t) return;
    if (cs.textTransform === "uppercase") t = t.toUpperCase();
    const size = parseFloat(cs.fontSize), ink = inkOf(t, `${cs.fontStyle} ${cs.fontWeight} ${size}px ${cs.fontFamily}`);
    if (!ink || !ink.fA) return;
    const circle = el.classList.contains("mode") || el.classList.contains("cinv");   // a lone letter in a circle sits on its ink box, which reads as centred; words sit on their weight
    const cx = circle ? ink.bx : ink.cx, cy = circle ? ink.by : ink.cy;
    const [pt, pb] = el._pad, L = parseFloat(cs.lineHeight) || size * 1.2;
    const baseline = pt + (L - (ink.fA + ink.fD) * size) / 2 + ink.fA * size;
    const shift = (pt + L + pb) / 2 - (baseline - cy * size) - RASTER * size;   // + moves the text down
    const dy = Math.max(-pt, Math.min(pb, shift));
    el.style.paddingTop = pt + dy + "px"; el.style.paddingBottom = pb - dy + "px";
    if (circle) { const sx = (ink.adv / 2 - cx) * size; el.style.paddingLeft = Math.max(0, 2 * sx) + "px"; el.style.paddingRight = Math.max(0, -2 * sx) + "px"; }   // asymmetric padding, not text-indent: Safari centres an indented line differently   // circles: centre sideways too
  }
  let inkQ = 0;
  const inkAll = () => { if (inkQ) return; inkQ = requestAnimationFrame(() => { inkQ = 0; $$(PILLS).forEach(inkCenter); }); };
  new MutationObserver(inkAll).observe(document.body, { childList: true, subtree: true });
  inkAll(); document.fonts?.ready?.then(() => { inkCache.clear(); inkAll(); });

  /* UI faces (Wiegel's DIN 1451 + CAT Linz) via FontFace too, so they also work where CSS font URLs are blocked */
  (window.UIFONTS || []).forEach((u) => {
    fetch(R + u.src).then((r) => r.arrayBuffer()).then((buf) => new FontFace(u.family, buf, { weight: String(u.weight), style: u.italic ? "italic" : "normal" }).load())
      .then((x) => { document.fonts.add(x); redrawAll(); inkCache.clear(); inkAll(); }).catch(() => {});
  });

  /* hosted shell: font.html#slug pulls the page body from a pack */
  const shell = $("#fontshell");
  if (shell) {
    const order = C.fonts.map((f) => f.s);
    const cache = {};
    async function show() {
      const slug = decodeURIComponent(location.hash.slice(1)) || order[0];
      const i = order.indexOf(slug);
      if (i < 0) { if (document.getElementById(slug)) return; shell.innerHTML = `<p class="lead">No font called “${slug}”. <a href="index.html">Back to the index</a>.</p>`; return; }
      const pk = Math.floor(i / (window.PACK || 20));
      cache[pk] = cache[pk] || fetch(`pages/p${pk}.json`).then((r) => r.json());
      const pack = await cache[pk];
      shell.innerHTML = pack[slug];
      document.title = C.fonts[i].n + " — Wiegel Archive";
      scrollTo(0, 0);
      initFont();
    }
    addEventListener("hashchange", show);
    show();
  }
})();
