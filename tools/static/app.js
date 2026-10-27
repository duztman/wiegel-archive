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
  setNavH(); addEventListener("resize", setNavH); document.fonts?.ready?.then(setNavH);

  /* theme */
  $(".theme")?.addEventListener("click", () => {
    const dark = matchMedia("(prefers-color-scheme: dark)").matches;
    const cur = document.documentElement.dataset.theme || (dark ? "dark" : "light");
    const nxt = cur === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = nxt; store.set("wa-theme", nxt, true);
    redrawAll();
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
      b.innerHTML = `${esc(label)}${n != null ? ` <span class="n tnum">${n}</span>` : ""}`; b.setAttribute("aria-pressed", !!on); b.onclick = fn; return b; };
    function renderSide() {
      const box = $("#fside"); box.replaceChildren();
      const group = (title, kids) => { const g = document.createElement("div"); g.className = "fg"; const h = document.createElement("h3"); h.className = "vlab"; h.textContent = title; const w = document.createElement("div"); w.className = "pills"; w.append(...kids); g.append(w, h); box.appendChild(g); };
      group("Order", ORDERS.map(([k, l]) => pill(l, null, state.order === k, () => { state.order = k; apply(); })));
      CATS.forEach(([k, label]) => {
        const sel = state.sel[k] || new Set();
        group(label, sortVals(k, vals[k]).map(([v, n]) => pill(v, n, sel.has(v), () => { const s = (state.sel[k] = state.sel[k] || new Set()); s.has(v) ? s.delete(v) : s.add(v); if (!s.size) delete state.sel[k]; apply(); })));
      });
    }
    function apply() {
      const q = state.q.toLowerCase();
      const pass = (f) => {
        for (const [k, , fn] of CATS) { const s = state.sel[k]; if (s && s.size && !fn(f).some((v) => s.has(v))) return false; }
        if (q && !(f.n + " " + (f.pl || "") + " " + f.tg.join(" ") + " " + f.g + " " + f.fa + " " + f.sum + " " + pad(f.no)).toLowerCase().includes(q)) return false;
        return true;
      };
      const by = { name: (a, b) => a.n.localeCompare(b.n), oy: (a, b) => (a.y || 9999) - (b.y || 9999), dy: (a, b) => (a.dy || 9999) - (b.dy || 9999), glyphs: (a, b) => b.gl - a.gl };
      let list = rows.filter((c) => pass(c._font));
      if (by[state.order]) list = list.slice().sort((a, b) => by[state.order](a._font, b._font));
      list.forEach((r, i) => {   // OG / DG named on the first row only; columns stay aligned
        const f = r._font;
        r.querySelector(".oy").textContent = f.y ? (i ? "" : "OG ") + f.y : "";
        r.querySelector(".dy").textContent = f.dy ? (i ? "" : "DG ") + f.dy : "";
      });
      grid.replaceChildren(...list);
      const any = Object.keys(state.sel).length || state.q;
      $("#count").textContent = list.length === C.fonts.length ? `${list.length}` : `${list.length} of ${C.fonts.length}`;
      $("#fclear").hidden = !any;
      renderSide(); save();
    }
    $("#fclear").onclick = (e) => { e.preventDefault(); }; $("#fclear").addEventListener("click", () => { state.sel = {}; state.q = ""; $("#q").value = ""; apply(); });
    $("#q").value = state.q; $("#q").oninput = (e) => { state.q = e.target.value; apply(); };
    let tm; $("#retype").oninput = (e) => { clearTimeout(tm); tm = setTimeout(() => { const t = e.target.value; rows.forEach((r) => (r.querySelector(".ln").textContent = t || r._font.n)); }, 120); };
    if (innerWidth < 900) $("#fdet")?.removeAttribute("open");
    apply();
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
      $$(".sortb", lst).forEach((b) => { b.classList.toggle("on", b.dataset.k === k); b.dataset.dir = b.dataset.k === k ? (asc ? "↑" : "↓") : ""; });
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
        b._px = Math.max(24, Math.min(small ? 160 : 420, Math.floor((avail / w) * 100 * 0.97)));
        paint(b); if (b === active) sync();
      });
    }
    $$(".feat input", art).forEach((i) => (i.onchange = applyFace));
    $("#style")?.addEventListener("change", (e) => { cur = +e.target.value; load(F[cur]).then(() => { applyFace(); fitBlocks(); drawGlyphs(); }); });

    /* colour */
    const navSync = () => { const bd = document.body.style; bd.setProperty("--navbg", art.style.getPropertyValue("--bg")); bd.setProperty("--navfg", art.style.getPropertyValue("--fg")); };
    function setPal(k) {
      $$(".sw", art).forEach((s) => s.classList.toggle("on", s.dataset.p === k));
      if (k === "plain" || !P[k]) { art.style.setProperty("--bg", css("--paper")); art.style.setProperty("--fg", css("--ink")); }
      else { art.style.setProperty("--bg", P[k][0]); art.style.setProperty("--fg", P[k][1]); }
      art.dataset.cur = k; navSync();
    }
    navSync();
    $$(".sw", art).forEach((s) => (s.onclick = () => setPal(s.dataset.p)));
    $("#invert").onclick = () => { const b = art.style.getPropertyValue("--bg"), f = art.style.getPropertyValue("--fg"); art.style.setProperty("--bg", f); art.style.setProperty("--fg", b); navSync(); };
    $("#reset").onclick = () => {
      blks.forEach((b) => { $(".ed", b).textContent = b.dataset.def; b._px = small ? Math.max(12, Math.round(+b.dataset.px * (+b.dataset.px > 30 ? 0.5 : 0.8))) : +b.dataset.px; b._lh = LEAD[b.dataset.role] ?? 1.0; b._tr = 0; paint(b); });
      userSized.clear(); setPal(defPal); fitBlocks(); sync(); wfText();
    };

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
        const h = document.createElement("div"); h.className = "gl-head"; h.textContent = `${name} ${cps.length}`; gl.appendChild(h);
        cps.forEach((c) => {
          const d = document.createElement("div"); d.className = "g"; d._cp = c;
          const hex = c.toString(16).toUpperCase().padStart(4, "0");
          d.innerHTML = `<canvas></canvas><span>${hex}</span>`; d.title = `U+${hex}`;
          gl.appendChild(d); gio.observe(d);
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
    window._redrawFont = () => { $$(".gl .g", art).forEach((d) => d.querySelector("canvas").width && drawG(d)); if (art.dataset.cur === "plain") setPal("plain"); };
  }
  window.WA_initFont = initFont;
  initFont();

  /* UI faces (Wiegel's DIN 1451 + CAT Linz) via FontFace too, so they also work where CSS font URLs are blocked */
  (window.UIFONTS || []).forEach((u) => {
    fetch(R + u.src).then((r) => r.arrayBuffer()).then((buf) => new FontFace(u.family, buf, { weight: String(u.weight), style: u.italic ? "italic" : "normal" }).load())
      .then((x) => { document.fonts.add(x); redrawAll(); }).catch(() => {});
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
