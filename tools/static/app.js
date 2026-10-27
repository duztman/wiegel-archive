/* Wiegel Archive — one script for all pages. No dependencies. */
(() => {
  const R = window.ROOT || "";
  const C = window.CATALOG || { fonts: [] };
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const store = { get(k) { try { return localStorage.getItem(k); } catch { return null; } }, set(k, v) { try { localStorage.setItem(k, v); } catch {} } };
  const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

  /* theme */
  const t = store.get("wa-theme"); if (t) document.documentElement.dataset.theme = t;
  $(".theme")?.addEventListener("click", () => {
    const dark = matchMedia("(prefers-color-scheme: dark)").matches;
    const cur = document.documentElement.dataset.theme || (dark ? "dark" : "light");
    const nxt = cur === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = nxt; store.set("wa-theme", nxt);
    redrawAll();
  });

  /* font loading — one FontFace per file, registered lazily */
  const faces = new Map();
  function load(f) {
    if (!f) return Promise.reject();
    if (faces.has(f.id)) return faces.get(f.id);
    // fetch + ArrayBuffer works both on a local server and inside a sandboxed host
    const p = fetch(R + f.src).then((r) => { if (!r.ok) throw new Error(r.status); return r.arrayBuffer(); })
      .then((buf) => new FontFace(f.id, buf).load()).then((x) => { document.fonts.add(x); return x; });
    faces.set(f.id, p);
    return p;
  }

  /* ink-centred fitting on canvas.
     Scale is set by cap height (not swashes), clamped so the whole ink box fits;
     the ink box centre — not the em box — is placed at the box centre. */
  const meas = document.createElement("canvas").getContext("2d");
  function fit(ctx, W, H, family, text, opts = {}) {
    const fill = opts.fill ?? 0.40, maxW = opts.maxW ?? 0.86, maxH = opts.maxH ?? 0.80;
    meas.font = `100px "${family}"`;
    const m = meas.measureText(text);
    const L = m.actualBoundingBoxLeft, Rr = m.actualBoundingBoxRight, A = m.actualBoundingBoxAscent, D = m.actualBoundingBoxDescent;
    const cap = meas.measureText("H").actualBoundingBoxAscent || A || 70;
    const iw = Math.max(1, L + Rr), ih = Math.max(1, A + D);
    let s = Math.min((H * fill) / cap, (W * maxW) / iw, (H * maxH) / ih);
    if (!isFinite(s) || s <= 0) s = 0.2;
    const x0 = W / 2 - ((Rr - L) / 2) * s;
    const y0 = H / 2 + ((A - D) / 2) * s;
    ctx.font = `${100 * s}px "${family}"`;
    ctx.fillText(text, x0, y0);
  }
  function prep(canvas) {
    const dpr = Math.max(1, Math.round(devicePixelRatio || 1));
    const W = canvas.clientWidth, H = canvas.clientHeight;
    if (canvas.width !== W * dpr || canvas.height !== H * dpr) { canvas.width = W * dpr; canvas.height = H * dpr; }
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = css("--ink");
    ctx.textBaseline = "alphabetic";
    return { ctx, W, H };
  }

  /* ── home: specimen grid ───────────────────────────────────────────── */
  const grid = $("#grid");
  let retype = "";
  const visible = new Set();
  function drawCard(card) {
    const f = card._font, face = f.f[0];
    const cv = card.querySelector("canvas");
    if (!face) { const { ctx, W, H } = prep(cv); ctx.fillStyle = css("--ink-3"); ctx.font = "13px system-ui"; ctx.fillText("no web-usable font file", 16, H / 2); return; }
    load(face).then(() => {
      const { ctx, W, H } = prep(cv);
      fit(ctx, W, H, face.id, retype || f.sm || f.n);
    }).catch(() => { const { ctx, H } = prep(cv); ctx.fillStyle = css("--ink-3"); ctx.font = "13px system-ui"; ctx.fillText("font failed to load", 16, H / 2); });
  }
  function redrawAll() { visible.forEach(drawCard); if (window._redrawFont) window._redrawFont(); }

  if (grid) {
    const io = new IntersectionObserver((es) => es.forEach((e) => {
      if (e.isIntersecting) { visible.add(e.target); drawCard(e.target); } else visible.delete(e.target);
    }), { rootMargin: "400px 0px" });
    const ico = (c) => `<svg class="ic" width="16" height="16"><use href="#i-${c}"/></svg>`;
    const cards = C.fonts.map((f) => {
      const a = document.createElement("a");
      a.className = "card"; a.href = window.HOSTED ? `${R}font.html#${f.s}` : `${R}font/${f.s}.html`; a._font = f;
      const yr = f.y.length ? Math.min(...f.y) : "";
      a.innerHTML = `<canvas aria-label="${f.n} specimen"></canvas>${f.pl ? `<span class="pl">Found in the world</span>` : ""}`
        + `<span class="ico">${f.ic.slice(0, 6).map(ico).join("")}</span>`
        + `<div class="cap"><span class="n">${f.n}</span><span class="m tnum">${f.fa}${yr ? " · " + yr : ""}</span></div>`;
      return a;
    });
    const state = { fam: new Set(), cov: new Set(), era: "", q: "", sort: "wiegel" };
    try { Object.assign(state, JSON.parse(decodeURIComponent(location.hash.slice(1)) || "{}"), {}); state.fam = new Set(state.fam || []); state.cov = new Set(state.cov || []); } catch {}
    function apply() {
      const q = state.q.toLowerCase();
      let list = cards.filter((c) => {
        const f = c._font;
        if (state.fam.size && !state.fam.has(f.fa)) return false;
        for (const k of state.cov) if (!f.cv.includes(k)) return false;
        if (state.era === "none" && f.e) return false;
        if (state.era && state.era !== "none" && String(f.e) !== state.era) return false;
        if (q && !(f.n + " " + (f.pl || "") + " " + f.tg.join(" ") + " " + f.g + " " + f.sum).toLowerCase().includes(q)) return false;
        return true;
      });
      const by = { name: (a, b) => a._font.n.localeCompare(b._font.n),
        year: (a, b) => (Math.min(...a._font.y, 9999)) - (Math.min(...b._font.y, 9999)),
        glyphs: (a, b) => b._font.gl - a._font.gl };
      if (by[state.sort]) list = list.slice().sort(by[state.sort]);
      grid.replaceChildren(...list);
      $("#count").textContent = `${list.length} / ${cards.length}`;
      try { history.replaceState(null, "", "#" + encodeURIComponent(JSON.stringify({ ...state, fam: [...state.fam], cov: [...state.cov] }))); } catch {}
    }
    cards.forEach((c) => io.observe(c));
    $$("[data-fam]").forEach((b) => { b.setAttribute("aria-pressed", state.fam.has(b.dataset.fam)); b.onclick = () => { state.fam.has(b.dataset.fam) ? state.fam.delete(b.dataset.fam) : state.fam.add(b.dataset.fam); b.setAttribute("aria-pressed", state.fam.has(b.dataset.fam)); apply(); }; });
    $$("[data-cov]").forEach((b) => { b.setAttribute("aria-pressed", state.cov.has(b.dataset.cov)); b.onclick = () => { state.cov.has(b.dataset.cov) ? state.cov.delete(b.dataset.cov) : state.cov.add(b.dataset.cov); b.setAttribute("aria-pressed", state.cov.has(b.dataset.cov)); apply(); }; });
    $("#era").value = state.era; $("#era").onchange = (e) => { state.era = e.target.value; apply(); };
    $("#sort").value = state.sort; $("#sort").onchange = (e) => { state.sort = e.target.value; apply(); };
    $("#q").value = state.q; $("#q").oninput = (e) => { state.q = e.target.value; apply(); };
    let tm; $("#retype").oninput = (e) => { clearTimeout(tm); tm = setTimeout(() => { retype = e.target.value; visible.forEach(drawCard); }, 150); };
    apply();
    let rz; addEventListener("resize", () => { clearTimeout(rz); rz = setTimeout(() => visible.forEach(drawCard), 120); });
  }

  /* ── catalogue: sortable table ─────────────────────────────────────── */
  const tbl = $("#cat");
  if (tbl) {
    const body = tbl.tBodies[0];
    const rows = [...body.rows];
    $$("th[data-k]", tbl).forEach((th) => th.onclick = () => {
      const k = +th.dataset.k, asc = th.getAttribute("aria-sort") !== "ascending";
      $$("th", tbl).forEach((x) => x.removeAttribute("aria-sort")); th.setAttribute("aria-sort", asc ? "ascending" : "descending");
      const val = (r) => { const c = r.cells[k]; return c.dataset.v !== undefined ? +c.dataset.v : c.textContent.trim().toLowerCase(); };
      rows.sort((a, b) => { const x = val(a), y = val(b); return (x > y ? 1 : x < y ? -1 : 0) * (asc ? 1 : -1); });
      body.replaceChildren(...rows);
    });
    $("#tq").oninput = (e) => { const q = e.target.value.toLowerCase(); rows.forEach((r) => r.hidden = q && !r.textContent.toLowerCase().includes(q)); };
  }

  /* ── font page ─────────────────────────────────────────────────────── */
  function initFont() {
  const live = $("#live");
  if (!live) return;
  {
    const F = JSON.parse($("#faces").textContent || "[]");
    const G = JSON.parse($("#glyphs").textContent || "[]");
    let cur = 0;
    const feats = () => $$(".feat input").map((i) => `"${i.value}" ${i.checked ? 1 : 0}`).join(", ") || "normal";
    function applyLive() {
      const f = F[cur]; if (!f) return;
      live.style.fontFamily = `"${f.id}"`;
      live.style.fontSize = $("#sz").value + "px";
      live.style.lineHeight = $("#lh").value;
      live.style.letterSpacing = $("#tr").value + "em";
      live.style.fontFeatureSettings = feats();
      $("#szo").textContent = $("#sz").value; $("#lho").textContent = (+$("#lh").value).toFixed(2); $("#tro").textContent = (+$("#tr").value).toFixed(3);
      $$("#wf .t").forEach((el) => { el.style.fontFamily = `"${f.id}"`; el.style.fontFeatureSettings = feats(); });
    }
    F.forEach((f) => load(f).catch(() => {}));
    load(F[0]).then(() => { applyLive(); drawGlyphs(); }).catch(() => { live.textContent = "This font file could not be loaded in the browser — use the downloads below."; });
    $$("#sz,#lh,#tr").forEach((i) => i.oninput = applyLive);
    $$(".feat input").forEach((i) => i.onchange = applyLive);
    $("#style")?.addEventListener("change", (e) => { cur = +e.target.value; load(F[cur]).then(() => { applyLive(); drawGlyphs(); }); });
    $("#invert").onclick = () => live.classList.toggle("inv");
    live.addEventListener("input", () => $$("#wf .t").forEach((el) => el.textContent = live.textContent));

    /* waterfall */
    const wf = $("#wf");
    [12, 16, 24, 36, 60, 96].forEach((px) => {
      const r = document.createElement("div"); r.className = "wf";
      r.innerHTML = `<span class="px tnum">${px}</span><span class="t" style="font-size:${px}px">${live.textContent}</span>`;
      wf.appendChild(r);
    });

    /* glyph grid — shared baseline, each glyph centred on its own ink horizontally */
    const gl = $("#gl");
    $("#gcount").textContent = G.length ? `${G.length.toLocaleString()} mapped characters` : "";
    const blocks = [[0x20, 0x7F, "Basic Latin"], [0xA0, 0x100, "Latin-1"], [0x100, 0x250, "Latin Extended"], [0x250, 0x370, "IPA & modifiers"],
      [0x370, 0x400, "Greek"], [0x400, 0x530, "Cyrillic"], [0x1E00, 0x1F00, "Latin Additional"], [0x1F00, 0x2000, "Greek Extended"],
      [0x2000, 0x2100, "Punctuation & currency"], [0x2100, 0x2200, "Letterlike & number forms"], [0xFB00, 0xFB50, "Ligatures"], [0, 0x110000, "Other"]];
    let gio;
    function drawGlyphs() {
      const f = F[cur]; if (!f) return;
      gl.replaceChildren(); gio?.disconnect();
      gio = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { drawG(e.target); gio.unobserve(e.target); } }), { rootMargin: "200px" });
      const done = new Set();
      blocks.forEach(([a, b, name]) => {
        const cps = G.filter((c) => c >= a && c < b && !done.has(c)); if (!cps.length) return;
        cps.forEach((c) => done.add(c));
        const h = document.createElement("div"); h.className = "gl-head"; h.textContent = `${name} · ${cps.length}`; gl.appendChild(h);
        cps.forEach((c) => {
          const d = document.createElement("div"); d.className = "g"; d._cp = c;
          d.innerHTML = `<canvas></canvas><span>${c.toString(16).toUpperCase().padStart(4, "0")}</span>`;
          d.title = `U+${c.toString(16).toUpperCase().padStart(4, "0")}`;
          gl.appendChild(d); gio.observe(d);
        });
      });
    }
    function drawG(d) {
      const f = F[cur], ch = String.fromCodePoint(d._cp);
      const { ctx, W, H } = prep(d.querySelector("canvas"));
      meas.font = `100px "${f.id}"`;
      const cap = meas.measureText("H").actualBoundingBoxAscent || 70;
      const s = (H * 0.42) / cap;
      const m = meas.measureText(ch);
      ctx.font = `${100 * s}px "${f.id}"`;
      const x0 = W / 2 - ((m.actualBoundingBoxRight - m.actualBoundingBoxLeft) / 2) * s;
      const y0 = H / 2 + (cap * s) / 2;   // shared baseline: cap-height centred in the cell
      ctx.fillText(ch, x0, y0);
    }
    window._redrawFont = () => { $$(".gl .g").forEach((d) => d.querySelector("canvas").width && drawG(d)); };
  }
  }
  window.WA_initFont = initFont;
  initFont();

  /* UI faces (Wiegel's CAT Linz + DIN 1451) loaded the same way, so they also work where CSS font URLs are blocked */
  (window.UIFONTS || []).forEach((u) => {
    fetch(R + u.src).then((r) => r.arrayBuffer()).then((buf) => new FontFace(u.family, buf, { weight: String(u.weight), style: u.italic ? "italic" : "normal" }).load())
      .then((x) => document.fonts.add(x)).catch(() => {});
  });

  /* hosted shell: font.html#slug pulls the page body from a pack */
  const shell = $("#fontshell");
  if (shell) {
    const order = C.fonts.map((f) => f.s);
    const cache = {};
    async function show() {
      const slug = decodeURIComponent(location.hash.slice(1)) || order[0];
      const i = order.indexOf(slug);
      if (i < 0) { shell.innerHTML = `<p class="lede" style="padding:64px 0">No font called “${slug}”. <a href="index.html">Back to specimens</a>.</p>`; return; }
      const pk = Math.floor(i / (window.PACK || 20));
      cache[pk] = cache[pk] || fetch(`pages/p${pk}.json`).then((r) => r.json());
      const pack = await cache[pk];
      shell.innerHTML = pack[slug];
      document.title = C.fonts[i].n + " · Wiegel Archive";
      scrollTo(0, 0);
      initFont();
    }
    addEventListener("hashchange", show);
    show();
  }
})();
