#!/usr/bin/env python3
"""Wiegel Archive — static site builder.

Reads  data/catalog.json + raw/archives/*.zip
Writes fonts/<slug>/…   (extracted originals, never modified)
       site/…           (index, catalogue, font pages, legend, about, assets)

Requires: python3 ≥3.9, fontTools (pip install fonttools). No network.
"""
import hashlib, html, io, json, os, re, shutil, sys, unicodedata, urllib.parse, zipfile, collections, datetime
from fontTools.ttLib import TTFont, TTCollection
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.transformPen import TransformPen

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA, RAW, FONTS, SITE = (os.path.join(ROOT, p) for p in ("data", "raw/archives", "fonts", "site"))
STATIC = os.path.join(ROOT, "tools", "static")

UI_TEXT = "catlinz"          # Wiegel's CAT Linz: 4 true styles, ~1,860 glyphs
UI_DISPLAY = "altedin1451"   # DIN 1451 alte Mittelschrift for masthead / numerals
FONT_EXT = (".ttf", ".otf", ".woff", ".woff2")
DOC_EXT = (".pdf", ".txt", ".rtf", ".doc", ".docx", ".odt", ".htm", ".html")
PUA = range(0xE000, 0xF900)
ESC = html.escape

# ── icon system: Wiegel's green feature buttons, redrawn ─────────────────────────
ICONS = collections.OrderedDict([
    ("standard",     ("Aa",  "Standard layout",        "Full standard ANSI character set in the usual positions.")),
    ("nostandard",   ("A*",  "Custom layout",          "Characters sit in non-standard positions or the set is incomplete; read the bundled notes.")),
    ("eurosign",     ("€",   "Euro sign",              "Includes the euro sign.")),
    ("SZlig",        ("ẞ",   "Capital sharp s",        "Includes the capital ẞ (U+1E9E).")),
    ("fraktur",      ("ſ",   "Blackletter set",        "Long s, round s and the ligatures and special sorts blackletter setting needs.")),
    ("unz",          ("UNZ", "UNZ1 encoding",          "Encoded to the UNZ1 blackletter standard; needs a setting helper or keyboard driver for ligatures.")),
    ("OT",           ("OT",  "OpenType features",      "OpenType features (ligatures, contextual or stylistic alternates) — needs software that supports them.")),
    ("OTL",          ("fi",  "OpenType ligatures",     "Ligatures switched in automatically through OpenType.")),
    ("expert",       ("Ā",   "Extended Latin",         "Accented letters beyond Western European — Central, Eastern and Northern Europe.")),
    ("greek",        ("Ω",   "Greek",                  "Includes the Greek alphabet.")),
    ("greekpro",     ("ἄ",   "Polytonic Greek",        "Includes polytonic Greek.")),
    ("kyrill",       ("Ж",   "Cyrillic",               "Includes the Cyrillic alphabet.")),
    ("kyrillpro",    ("Ѣ",   "Extended Cyrillic",      "Includes extended Cyrillic, e.g. Serbian and Bulgarian forms.")),
    ("worldglyph",   ("◍",   "Latin · Greek · Cyrillic","Near-complete coverage of all three European scripts.")),
    ("latein",       ("Ll",  "Joined Latin script",    "A connected Latin handwriting; sometimes includes other scripts.")),
    ("deutsch",      ("Kr",  "Kurrent",                "German Kurrent hand (often wrongly called Sütterlin), with long s and ligatures.")),
    ("school",       ("abc", "School script",          "Developed with teaching input for use in schools and training.")),
    ("versalien",    ("AB",  "Capitals only",          "Capitals only; lowercase keys repeat the capitals.")),
    ("gemeine",      ("ab",  "Lowercase only",         "Lowercase only; capital keys repeat the lowercase.")),
    ("kapitaelchen", ("Aᴀ",  "Small caps",             "Small capitals take the place of lowercase.")),
    ("gaelic",       ("Ġ",   "Irish",                  "Includes the Irish alphabet.")),
    ("runen",        ("ᚱ",   "Runes",                  "Includes runes.")),
    ("ziffern",      ("12",  "Figures only",           "Numerals only.")),
    ("dingbat",      ("◆",   "Pictures",               "Dingbat font, or some glyphs replaced by pictures.")),
    ("spezial",      ("✱",   "Special font",           "A special-purpose font; read the instructions.")),
    ("color",        ("▚",   "Layered colour",         "Stack several glyphs on top of each other to build multicoloured characters.")),
    ("manual",       ("i",   "Manual required",        "Bundled instructions are essential; pass the font on only together with them.")),
])

COVERAGE = [  # (key, label, test)
    ("latin1", "Latin-1", lambda c: all(x in c for x in range(0x41, 0x5B)) and sum(1 for x in range(0xC0, 0x100) if x in c) > 50),
    ("ext",    "Extended Latin", lambda c: sum(1 for x in range(0x100, 0x180) if x in c) > 80),
    ("greek",  "Greek", lambda c: sum(1 for x in range(0x391, 0x3CA) if x in c) > 40),
    ("cyr",    "Cyrillic", lambda c: sum(1 for x in range(0x410, 0x450) if x in c) > 50),
    ("longs",  "ſ", lambda c: 0x17F in c),
    ("capsz",  "ẞ", lambda c: 0x1E9E in c),
    ("euro",   "€", lambda c: 0x20AC in c),
]


def log(*a):
    print(*a, flush=True)


def ascii_name(s):
    s = unicodedata.normalize("NFC", s)
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("Ä", "Ae"), ("Ö", "Oe"), ("Ü", "Ue"), ("ß", "ss")):
        s = s.replace(a, b)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("_") or "file"


def key(name):
    """Normalised archive key: Apify sanitised names (spaces → '-')."""
    n = urllib.parse.unquote(name).rsplit("/", 1)[-1].lower()
    n = re.sub(r"^files-", "", n)
    return re.sub(r"[^a-z0-9]", "", n)


def zip_names(zf):
    """Yield (info, decoded_name) fixing cp437-mangled German names."""
    for info in zf.infolist():
        n = info.filename
        if not (info.flag_bits & 0x800):
            try:
                n = n.encode("cp437").decode("cp850")
            except Exception:
                pass
        yield info, unicodedata.normalize("NFC", n)


def walk_archive(data, depth=0):
    """Yield (name, bytes) for every member, descending into nested zips / SFX exes."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return
    for info, name in zip_names(zf):
        if info.is_dir() or "__MACOSX" in name or name.split("/")[-1].lower() in ("thumbs.db", ".ds_store"):
            continue
        if name.startswith("/") or ".." in name.split("/"):
            continue
        b = zf.read(info)
        low = name.lower()
        if depth < 3 and (low.endswith(".zip") or low.endswith(".exe")):
            yield from walk_archive(b, depth + 1)
        else:
            yield name, b


def analyse(path):
    """Return metadata for one font file (first face of a collection)."""
    try:
        f = TTFont(path, fontNumber=0, lazy=True)
    except Exception as e:
        return {"error": str(e)}
    name = f["name"]

    def nm(*ids):
        for i in ids:
            r = name.getDebugName(i)
            if r:
                return r.strip()
        return ""
    cmap = f.getBestCmap() or {}
    cps = set(cmap)
    upm = f["head"].unitsPerEm
    os2 = f["OS/2"] if "OS/2" in f else None
    hhea = f["hhea"]
    cap = getattr(os2, "sCapHeight", 0) if os2 else 0
    xh = getattr(os2, "sxHeight", 0) if os2 else 0
    gs = f.getGlyphSet()

    def ink(ch):
        g = cmap.get(ord(ch))
        if not g or g not in gs:
            return None
        bp = BoundsPen(gs)
        try:
            gs[g].draw(bp)
        except Exception:
            return None
        return bp.bounds
    if not (0.45 * upm <= cap <= 0.9 * upm):
        b = ink("H")
        cap = (b[3] if b else 0) or cap
    if not (0.3 * upm <= xh <= 0.8 * upm):
        b = ink("x")
        xh = (b[3] if b else 0) or xh
    feats = []
    for t in ("GSUB", "GPOS"):
        if t in f and getattr(f[t].table, "FeatureList", None):
            feats += [r.FeatureTag for r in f[t].table.FeatureList.FeatureRecord]
    weight = getattr(os2, "usWeightClass", 400) if os2 else 400
    italic = bool(getattr(os2, "fsSelection", 0) & 1) if os2 else False
    style = nm(17, 2) or "Regular"
    return {
        "family": nm(16, 1), "style": style, "full": nm(4), "version": nm(5), "designer": nm(9),
        "copyright": nm(0)[:300], "license": nm(13)[:600], "license_url": nm(14),
        "upm": upm, "asc": hhea.ascent, "desc": hhea.descent, "cap": cap, "xh": xh,
        "glyphs": len(f.getGlyphOrder()), "chars": len(cps - set(PUA)), "pua": len(cps & set(PUA)),
        "feats": sorted(set(feats)), "weight": weight, "italic": italic or "italic" in style.lower() or "kursiv" in style.lower(),
        "rev": float(getattr(f["head"], "fontRevision", 0) or 0),
        "cmap": sorted(c for c in cps if c >= 0x20 and c not in PUA and not 0x7F <= c < 0xA0),
        "coverage": [k for k, _, t in COVERAGE if t(cps)],
    }


def sample_for(cmap):
    c = set(cmap)
    for s in ("Hamburgefonstiv", "Hamburgefons", "HAMBURGEFONS", "HAMBURG", "1234567890"):
        if all(ord(ch) in c for ch in s if ch != " "):
            return s
    printable = [chr(x) for x in cmap if x > 0x20 and unicodedata.category(chr(x))[0] in "LNSP"][:8]
    return "".join(printable) or "Aa"


# ── extraction ────────────────────────────────────────────────────────────────────
def extract(cat):
    archives = {key(n): os.path.join(RAW, n) for n in os.listdir(RAW)}
    seen_sha = {}
    report = collections.Counter()
    for f in cat["fonts"]:
        dst = os.path.join(FONTS, f["slug"])
        os.makedirs(dst, exist_ok=True)
        f["files"], f["docs"], f["downloads"] = [], [], []
        for z in f["zips"]:
            a = archives.get(key(z["u"]))
            if not a:
                f["downloads"].append({"name": urllib.parse.unquote(z["u"].rsplit("/", 1)[-1]), "kind": z.get("k", ""), "src": z["u"], "local": None, "bytes": None})
                report["archive missing"] += 1
                continue
            data = open(a, "rb").read()
            f["downloads"].append({"name": os.path.basename(a), "kind": z.get("k", ""), "src": z["u"], "local": os.path.basename(a), "bytes": len(data)})
            for name, b in walk_archive(data):
                low = name.lower()
                base = name.rsplit("/", 1)[-1]
                if low.endswith(FONT_EXT):
                    sha = hashlib.sha1(b).hexdigest()
                    if sha in seen_sha.get(f["slug"], set()):
                        continue
                    seen_sha.setdefault(f["slug"], set()).add(sha)
                    out = os.path.join(dst, ascii_name(base))
                    i = 2
                    while os.path.exists(out):
                        stem, ext = os.path.splitext(ascii_name(base))
                        out = os.path.join(dst, f"{stem}-{i}{ext}"); i += 1
                    open(out, "wb").write(b)
                    f["files"].append({"path": os.path.relpath(out, ROOT), "orig": name, "sha1": sha, "from": os.path.basename(a)})
                elif low.endswith(DOC_EXT):
                    os.makedirs(os.path.join(dst, "docs"), exist_ok=True)
                    out = os.path.join(dst, "docs", ascii_name(base))
                    open(out, "wb").write(b)
                    f["docs"].append({"path": os.path.relpath(out, ROOT), "orig": name})
        if not f["files"]:
            report["no font file"] += 1
    log("extract:", dict(report))


def inventory(cat):
    for f in cat["fonts"]:
        good = []
        for x in f["files"]:
            m = analyse(os.path.join(ROOT, x["path"]))
            if "error" in m:
                x["error"] = m["error"]
                continue
            x.update(m)
            good.append(x)
        # web-usable first, then OTF over TTF, then newest revision, upright regular first
        def rank(x):
            ext = x["path"].lower().rsplit(".", 1)[-1]
            return (x["italic"], abs(x["weight"] - 400), {"otf": 0, "ttf": 1, "woff2": 2, "woff": 3}.get(ext, 9), -x["rev"])
        good.sort(key=rank)
        # collapse identical family+style (TTF vs OTF vs webfont-kit copies)
        uniq, seenfs = [], set()
        for x in good:
            k = (x["family"].lower(), x["style"].lower())
            if k in seenfs:
                x["dup"] = True
                continue
            seenfs.add(k)
            uniq.append(x)
        f["faces"] = uniq
        canon = uniq[0] if uniq else None
        f["sample"] = sample_for(canon["cmap"]) if canon else ""
        f["glyphs"] = canon["chars"] if canon else 0
        f["coverage"] = canon["coverage"] if canon else []
        f["feats"] = sorted({t for x in uniq for t in x["feats"]})
        f["designer"] = next((x["designer"] for x in uniq if x["designer"]), "")
        f["font_license"] = next((x["license"] for x in uniq if x["license"]), "")
        f["copyright"] = next((x["copyright"] for x in uniq if x["copyright"]), "")


# ── icons from the archive's own type ─────────────────────────────────────────────
def icon_svgs(cat):
    by = {f["slug"]: f for f in cat["fonts"]}
    pool = [os.path.join(ROOT, x["path"]) for s in (UI_TEXT, UI_DISPLAY) for x in by.get(s, {}).get("faces", [])[:1]]
    pool += [os.path.join(ROOT, f["faces"][0]["path"]) for f in cat["fonts"] if f.get("faces") and set(f["coverage"]) >= {"greek", "cyr", "longs"}][:6]
    fonts = []
    for p in pool:
        try:
            fonts.append(TTFont(p, fontNumber=0))
        except Exception:
            pass
    out = {}
    for code, (mark, label, _) in ICONS.items():
        for t in fonts:
            cmap = t.getBestCmap() or {}
            if not all(ord(ch) in cmap for ch in mark):
                continue
            gs, upm = t.getGlyphSet(), t["head"].unitsPerEm
            spen, x, paths = None, 0, []
            bounds = [1e9, 1e9, -1e9, -1e9]
            for ch in mark:
                g = cmap[ord(ch)]
                bp = BoundsPen(gs)
                tp = TransformPen(bp, (1, 0, 0, 1, x, 0))
                gs[g].draw(tp)
                if bp.bounds:
                    b = bp.bounds
                    bounds = [min(bounds[0], b[0]), min(bounds[1], b[1]), max(bounds[2], b[2]), max(bounds[3], b[3])]
                sp = SVGPathPen(gs)
                gs[g].draw(TransformPen(sp, (1, 0, 0, 1, x, 0)))
                paths.append(sp.getCommands())
                x += gs[g].width
            if bounds[0] > 1e8:
                continue
            w, h = bounds[2] - bounds[0], bounds[3] - bounds[1]
            box = 14.0  # ink lives in a 14×14 field inside the 24×24 chip
            s = min(box / max(w, 1), box / max(h, 1), 10.0 / (upm * 0.7))
            s = min(box / max(w, 1), box / max(h, 1)) if len(mark) > 1 else min(s * 1.25, box / max(h, 1), box / max(w, 1))
            cx, cy = (bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2
            # ink-centred, y flipped; translate snapped to 1/2 px so straight stems land on the grid
            tx = round((12 - cx * s) * 2) / 2
            ty = round((12 + cy * s) * 2) / 2
            out[code] = f'<symbol id="i-{code}" viewBox="0 0 24 24"><rect x="0" y="0" width="24" height="24" rx="5" class="chip"/><path class="mark" transform="translate({tx} {ty}) scale({s:.5f} {-s:.5f})" d="{" ".join(paths)}"/></symbol>'
            break
        else:
            out[code] = f'<symbol id="i-{code}" viewBox="0 0 24 24"><rect x="0" y="0" width="24" height="24" rx="5" class="chip"/><text x="12" y="16" text-anchor="middle" class="mark-t">{ESC(mark[:2])}</text></symbol>'
    return '<svg xmlns="http://www.w3.org/2000/svg" style="display:none">' + "".join(out.values()) + "</svg>"


# ── HTML ─────────────────────────────────────────────────────────────────────────
def icon(code, size=20):
    if code not in ICONS:
        return ""
    return f'<svg class="ic" width="{size}" height="{size}" aria-label="{ESC(ICONS[code][1])}" role="img"><title>{ESC(ICONS[code][1])}</title><use href="#i-{code}"/></svg>'


def page(title, body, depth=0, sprite="", cls=""):
    up = "../" * depth
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>{ESC(title)}</title>
<link rel="stylesheet" href="{up}assets/app.css">
<script>window.ROOT="{up}"</script>
</head><body class="{cls}">
{sprite}
<header class="top"><a class="mark" href="{up}index.html"><span class="w">Wiegel</span><span class="a">Archive</span></a>
<nav><a href="{up}index.html">Specimens</a><a href="{up}catalogue.html">Catalogue</a><a href="{up}legend.html">Legend</a><a href="{up}about.html">About</a>
<button class="theme" type="button" aria-label="Toggle dark mode">◐</button></nav></header>
<main>{body}</main>
<footer class="foot"><span>A private, unpublished archive of the free fonts of Peter Wiegel / CAT Fonts.</span><span>Fonts © their authors, under the licences bundled in each archive. Texts are new English write-ups; originals at <a href="http://www.peter-wiegel.de/">peter-wiegel.de</a>.</span></footer>
<script src="{up}assets/catalog.js"></script><script src="{up}assets/app.js"></script>
</body></html>"""


def era(f):
    return f"{f['decade']}s" if f.get("decade") else "Undated"


def fonts_css_entry(f, i, x, up):
    src = up + "assets/fonts/" + f["slug"] + "/" + os.path.basename(x["path"])
    return {"id": f"wa-{f['slug']}-{i}", "src": src, "style": x["style"], "weight": x["weight"], "italic": x["italic"], "glyphs": x["chars"], "feats": x["feats"], "full": x["full"]}


def write_catalog_js(cat):
    rows = []
    for f in cat["fonts"]:
        faces = [fonts_css_entry(f, i, x, "") for i, x in enumerate(f.get("faces", []))]
        rows.append({
            "s": f["slug"], "n": f["name"], "fa": f["family"], "g": f["genre"], "e": f.get("decade"),
            "y": [y["y"] for y in f["years"]], "sec": f["section"], "p": f["pos"], "of": f["of"],
            "ic": f["icons"], "cv": f.get("coverage", []), "sm": f.get("sample", ""), "gl": f.get("glyphs", 0),
            "st": len(faces), "f": faces[:1], "sum": f.get("summary", ""), "pl": f.get("place"), "ph": bool(f.get("photo")),
            "tg": f.get("tags", []),
        })
    js = "window.CATALOG=" + json.dumps({"families": cat["families"], "fonts": rows}, ensure_ascii=False, separators=(",", ":")) + ";"
    open(os.path.join(SITE, "assets", "catalog.js"), "w", encoding="utf-8").write(js)


def index_html(cat, sprite):
    fonts = cat["fonts"]
    n_faces = sum(len(f.get("faces", [])) for f in fonts)
    n_glyphs = sum(x["chars"] for f in fonts for x in f.get("faces", []))
    fam = collections.Counter(f["family"] for f in fonts)
    chips = "".join(f'<button class="chip" data-fam="{ESC(k)}">{ESC(k)}<sup>{fam[k]}</sup></button>' for k in cat["families"] if fam[k])
    eras = sorted({f["decade"] for f in fonts if f.get("decade")})
    era_opts = "".join(f'<option value="{e}">{e}s</option>' for e in eras)
    cov = "".join(f'<button class="chip" data-cov="{k}">{ESC(lbl)}</button>' for k, lbl, _ in COVERAGE)
    body = f"""
<section class="hero">
  <h1 class="display">Peter Wiegel<br><span>CAT Fonts, 1976–2022</span></h1>
  <dl class="stats tnum"><div><dt>Typefaces</dt><dd>{len(fonts)}</dd></div><div><dt>Styles</dt><dd>{n_faces}</dd></div><div><dt>Characters drawn</dt><dd>{n_glyphs:,}</dd></div></dl>
  <p class="lede">A working archive of every free typeface published on peter-wiegel.de — blackletter and Kurrent, school scripts, DIN and railway lettering, signs copied off walls, manhole covers and kitchen drawers. Type below to set every specimen at once.</p>
</section>
<section class="controls" aria-label="Filters">
  <input id="retype" class="retype" type="text" placeholder="Type to set every specimen…" autocomplete="off" spellcheck="false">
  <div class="row"><span class="lbl">Family</span>{chips}</div>
  <div class="row"><span class="lbl">Coverage</span>{cov}
    <span class="lbl">Era</span><select id="era"><option value="">Any</option>{era_opts}<option value="none">Undated</option></select>
    <span class="lbl">Order</span><select id="sort"><option value="wiegel">Wiegel's index</option><option value="name">A–Z</option><option value="year">Year</option><option value="glyphs">Glyphs</option></select>
    <input id="q" class="q" type="search" placeholder="Search names, places, tags">
    <span class="count tnum" id="count"></span></div>
</section>
<section id="grid" class="grid" aria-live="polite"></section>
"""
    return page("Wiegel Archive — Specimens", body, 0, sprite, "home")


def catalogue_html(cat, sprite):
    rows = []
    for f in cat["fonts"]:
        yrs = [y["y"] for y in f["years"]]
        yr = (f"{min(yrs)}–{max(yrs)}" if len(set(yrs)) > 1 else str(yrs[0])) if yrs else "—"
        rows.append(
            f'<tr data-fam="{ESC(f["family"])}"><td class="n"><a href="font/{f["slug"]}.html">{ESC(f["name"])}</a></td>'
            f'<td>{ESC(f["family"])}</td><td class="sub">{ESC(f["genre"])}</td>'
            f'<td class="num" data-v="{min(yrs) if yrs else 9999}">{yr}</td>'
            f'<td class="sub">{ESC(f.get("origin") or "")}</td><td class="sub">{ESC(f.get("place") or "")}</td>'
            f'<td class="num" data-v="{len(f.get("faces", []))}">{len(f.get("faces", []))}</td>'
            f'<td class="num" data-v="{f.get("glyphs", 0)}">{f.get("glyphs", 0):,}</td>'
            f'<td class="icons">{"".join(icon(c, 16) for c in f["icons"] if c in ICONS)}</td>'
            f'<td class="num sub" data-v="{["A–K","L–Z","Fonts 2","Unlisted"].index(f["section"]) * 1000 + f["pos"]}">{ESC(f["section"])} · {f["pos"]}</td></tr>')
    body = f"""
<section class="pagehead"><h1 class="display">Catalogue</h1>
<p class="lede">{len(cat['fonts'])} typefaces. Click a column to sort; the last column is the font's position in Wiegel's own index.</p>
<input id="tq" class="q" type="search" placeholder="Filter rows"></section>
<div class="tablewrap"><table class="cat tnum" id="cat"><thead><tr>
<th data-k="0">Name</th><th data-k="1">Family</th><th data-k="2">Genre</th><th data-k="3" class="num">Years</th>
<th data-k="4">Source</th><th data-k="5">Place / object</th><th data-k="6" class="num">Styles</th><th data-k="7" class="num">Glyphs</th>
<th>Features</th><th data-k="9" class="num">Index</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>"""
    return page("Wiegel Archive — Catalogue", body, 0, sprite, "catalogue")


def font_html(f, by, sprite):
    up = "../"
    faces = [fonts_css_entry(f, i, x, up) for i, x in enumerate(f.get("faces", []))]
    canon = f["faces"][0] if f.get("faces") else None
    a = f.get("account") or {}
    years = "".join(f'<li><span class="y tnum">{y["y"]}</span><span>{ESC(y["what"])}</span></li>' for y in sorted(f["years"], key=lambda y: y["y"]))
    tags = "".join(f'<span class="tag">{ESC(t)}</span>' for t in f.get("tags", []))
    icons = "".join(f'<li>{icon(c, 24)}<span>{ESC(ICONS[c][1])}</span></li>' for c in f["icons"] if c in ICONS)
    styles = "".join(f'<option value="{i}">{ESC(x["style"])}</option>' for i, x in enumerate(faces))
    feats = "".join(f'<label class="feat"><input type="checkbox" value="{t}"{" checked" if t in ("liga","calt","kern") else ""}><span>{t}</span></label>'
                    for t in f.get("feats", []) if re.match(r"^(liga|dlig|calt|salt|ss\d\d|swsh|smcp|c2sc|onum|lnum|tnum|frac|hist|kern|cv\d\d|zero)$", t))
    dl = "".join(
        f'<li><a href="{up}assets/dl/{urllib.parse.quote(d["local"])}" download>{ESC(d["name"])}</a><span class="sub">{ESC(d["kind"])}{" · " + format(d["bytes"] / 1024, ".0f") + " KB" if d["bytes"] else ""}</span></li>'
        if d["local"] else f'<li><a href="{ESC(d["src"])}">{ESC(d["name"])}</a><span class="sub">original link</span></li>'
        for d in f.get("downloads", []))
    docs = "".join(f'<li><a href="{up}assets/docs/{f["slug"]}/{urllib.parse.quote(os.path.basename(d["path"]))}">{ESC(os.path.basename(d["path"]))}</a></li>' for d in f.get("docs", []))
    ph = f.get("photo")
    photo = ""
    if ph:
        photo = (f'<figure class="photo"><img src="{up}assets/photos/{f["slug"]}.jpg" alt="{ESC(ph.get("caption",""))}" loading="lazy" '
                 f'onerror="this.onerror=null;this.src=\'{ESC(ph["src"])}\'"><figcaption><span>{ESC(ph.get("caption",""))}</span>'
                 f'<span class="credit">Photo: {ESC(ph.get("author",""))} · {ESC(ph.get("license",""))} · <a href="{ESC(ph.get("page",""))}">source</a></span></figcaption></figure>')
    found = "".join(f'<li><a href="{ESC(x["u"])}">{ESC(x.get("t") or x.get("site",""))}</a><span class="sub">{ESC(x.get("site",""))} — {ESC(x.get("note",""))}</span></li>' for x in f.get("found", []))
    related = "".join(f'<li><a href="{ESC(x["u"])}">{ESC(x["t"])}</a></li>' for x in f.get("related", []))
    maps = f'<a class="btn" href="{ESC(f["maps"])}">Open in Google Maps ↗</a>' if f.get("maps") else ""
    prev_, next_ = by.get(f.get("prev")), by.get(f.get("next"))
    meta_rows = [("Family", f["family"]), ("Genre", f["genre"]), ("Source", f.get("origin")), ("Place / object", f.get("place")),
                 ("Designer field", f.get("designer")), ("Styles", str(len(faces))), ("Characters", f'{f.get("glyphs",0):,}'),
                 ("Licence (page)", f.get("license")), ("Licence (font file)", (f.get("font_license") or "")[:240]),
                 ("Wiegel's index", f'{f["section"]} · {f["pos"]} of {f["of"]}')]
    meta = "".join(f'<div><dt>{ESC(k)}</dt><dd>{ESC(v)}</dd></div>' for k, v in meta_rows if v)
    glyphs = json.dumps(canon["cmap"][:4000] if canon else [])
    acc = "".join(f'<div class="acc"><h3>{h}</h3><p>{ESC(a[k])}</p></div>' for k, h in (("what", "The typeface"), ("history", "History"), ("use", "In use"), ("notes", "Notes")) if a.get(k))
    if not acc:
        acc = f'<div class="acc"><p>{ESC(f.get("summary",""))}</p></div>'
    body = f"""
<article class="font" data-slug="{f['slug']}">
<script type="application/json" id="faces">{json.dumps(faces)}</script>
<script type="application/json" id="glyphs">{glyphs}</script>
<header class="fhead">
  <p class="crumb tnum"><a href="{up}index.html">Specimens</a> / {ESC(f['family'])} / <span>{ESC(f['section'])} · {f['pos']}</span></p>
  <h1 class="fname">{ESC(f['name'])}</h1>
  <ul class="icons-row">{icons}</ul>
</header>
<section class="tester" aria-label="Type tester">
  <div class="tools">
    <label>Size <input type="range" id="sz" min="12" max="320" value="120"><output id="szo" class="tnum">120</output></label>
    <label>Leading <input type="range" id="lh" min="0.7" max="2" step="0.01" value="1.1"><output id="lho" class="tnum">1.10</output></label>
    <label>Tracking <input type="range" id="tr" min="-0.1" max="0.4" step="0.005" value="0"><output id="tro" class="tnum">0</output></label>
    {f'<label>Style <select id="style">{styles}</select></label>' if len(faces) > 1 else ''}
    <span class="feats">{feats}</span>
    <button type="button" id="invert" class="btn">Invert</button>
  </div>
  <div id="live" class="live" contenteditable="true" spellcheck="false">{ESC(f.get('sample') or f['name'])}</div>
</section>
<section class="cols">
  <div class="text">{acc}
    <p class="orig"><a class="btn" href="{ESC(f['translate'])}">Read Wiegel's original in English ↗</a> <a class="btn ghost" href="{ESC(f['url'])}">Original German page ↗</a></p>
  </div>
  <aside class="meta"><dl>{meta}</dl>{f'<h3>Timeline</h3><ol class="years">{years}</ol>' if years else ''}{f'<div class="tags">{tags}</div>' if tags else ''}</aside>
</section>
{f'<section class="place"><h2>Found in the world</h2>{photo}<div class="placecol">{maps}{f"<h3>Seen elsewhere</h3><ul class=links>{found}</ul>" if found else ""}{f"<h3>Related</h3><ul class=links>{related}</ul>" if related else ""}</div></section>' if (photo or found or related or maps) else ''}
<section class="waterfall" id="wf" aria-label="Waterfall"></section>
<section class="glyphs"><h2>Characters <span class="sub tnum" id="gcount"></span></h2><div id="gl" class="gl"></div></section>
<section class="files"><h2>Downloads</h2><ul class="dl">{dl}</ul>{f'<h3>Bundled documents</h3><ul class="dl">{docs}</ul>' if docs else ''}
<p class="sub">{ESC(f.get('copyright') or '')}</p></section>
<nav class="pn"><a href="{prev_['slug'] + '.html' if prev_ else '#'}" class="{'' if prev_ else 'off'}">← {ESC(prev_['name'] if prev_ else '')}</a><a href="{next_['slug'] + '.html' if next_ else '#'}" class="{'' if next_ else 'off'}">{ESC(next_['name'] if next_ else '')} →</a></nav>
</article>"""
    return page(f"{f['name']} — Wiegel Archive", body, 1, sprite, "fontpage")


def legend_html(sprite):
    items = "".join(f'<li>{icon(c, 48)}<div><h3>{ESC(l)}</h3><p>{ESC(d)}</p><code>{ESC(c)}</code></div></li>' for c, (_, l, d) in ICONS.items())
    body = f"""<section class="pagehead"><h1 class="display">Legend</h1>
<p class="lede">Wiegel marked every font with small green buttons for its character set and features. Here they are redrawn: 24-pixel chips with the mark cut from the archive's own type, centred on its ink.</p></section>
<ul class="legend">{items}</ul>"""
    return page("Wiegel Archive — Legend", body, 0, sprite, "legend")


def about_html(cat, sprite):
    n = len(cat["fonts"])
    body = f"""<section class="pagehead"><h1 class="display">About</h1></section>
<section class="prose">
<h2>Peter Wiegel</h2>
<p>A self-described typographic amateur from Hamburg, later based in Wolgast, Peter Wiegel built CAT Fonts from the late 2000s into the 2020s: several hundred free typefaces, most of them revivals of German foundry type, school and handwriting models, standardised lettering (DIN, TGL, railway drawings) and lettering recorded from real objects. His site says that since 2022 he has been unable to maintain it for health reasons; it stays online as it is.</p>
<h2>Licences</h2>
<p>Wiegel's own designs are freeware, commercial use included; modified versions must stay free and take a new name. A large group of blackletter fonts on the second index page are re-encodings of Dieter Steffmann's digitisations — those are free for private use, and commercial use needs Steffmann's licence. Each font page shows the licence note from Wiegel's page and the licence embedded in the font file; the original archives, with their licence files, are kept untouched under Downloads.</p>
<h2>This archive</h2>
<p>{n} typefaces scraped with Apify from all three of Wiegel's index pages. The texts are new English write-ups of each page — facts regrouped, not translations — with a link to the original and to a machine translation of it. Photos of the buildings, signs and objects are freely licensed (credited); other sightings are linked, not copied. Specimens are set live from the font files; nothing on this site is an image of type.</p>
<h2>Method</h2>
<p>Planned with the Elephant–Goldfish model: one long-context design session wrote <code>docs/designs/archive.md</code>; three stateless reviewers (comprehension, hostile critic, implementation readiness) attacked it, and their findings were folded in before any code was written.</p>
<h2>Colophon</h2>
<p>Set in Wiegel's CAT Linz (text) and DIN 1451 alte Mittelschrift (display). Built {datetime.date.today().isoformat()}.</p>
</section>"""
    return page("Wiegel Archive — About", body, 0, sprite, "about")


def ui_font_css(by):
    css = []
    for slug, fam in ((UI_TEXT, "WA Text"), (UI_DISPLAY, "WA Display")):
        f = by.get(slug)
        for x in (f or {}).get("faces", []):
            src = "fonts/" + slug + "/" + os.path.basename(x["path"])
            css.append(f'@font-face{{font-family:"{fam}";src:url("{src}");font-weight:{x["weight"]};font-style:{"italic" if x["italic"] else "normal"};font-display:swap}}')
    return "\n".join(css)


def main():
    cat = json.load(open(os.path.join(DATA, "catalog.json"), encoding="utf-8"))
    if os.path.exists(FONTS):
        shutil.rmtree(FONTS)
    extract(cat)
    inventory(cat)
    by = {f["slug"]: f for f in cat["fonts"]}
    # site tree
    if os.path.exists(SITE):
        shutil.rmtree(SITE)
    for d in ("assets/fonts", "assets/dl", "assets/docs", "assets/photos", "font"):
        os.makedirs(os.path.join(SITE, d), exist_ok=True)
    for f in cat["fonts"]:
        for x in f.get("faces", []):
            d = os.path.join(SITE, "assets/fonts", f["slug"]); os.makedirs(d, exist_ok=True)
            shutil.copy2(os.path.join(ROOT, x["path"]), d)
        for dd in f.get("downloads", []):
            if dd["local"]:
                shutil.copy2(os.path.join(RAW, dd["local"]), os.path.join(SITE, "assets/dl", dd["local"]))
        for d in f.get("docs", []):
            dd = os.path.join(SITE, "assets/docs", f["slug"]); os.makedirs(dd, exist_ok=True)
            shutil.copy2(os.path.join(ROOT, d["path"]), dd)
        p = os.path.join(DATA, "photos", f["slug"] + ".jpg")
        if f.get("photo") and os.path.exists(p):
            shutil.copy2(p, os.path.join(SITE, "assets/photos"))
    sprite = icon_svgs(cat)
    css = open(os.path.join(STATIC, "app.css"), encoding="utf-8").read().replace("/*UI_FONTS*/", ui_font_css(by))
    open(os.path.join(SITE, "assets/app.css"), "w", encoding="utf-8").write(css)
    shutil.copy2(os.path.join(STATIC, "app.js"), os.path.join(SITE, "assets/app.js"))
    write_catalog_js(cat)
    W = lambda p, s: open(os.path.join(SITE, p), "w", encoding="utf-8").write(s)
    W("index.html", index_html(cat, sprite))
    W("catalogue.html", catalogue_html(cat, sprite))
    W("legend.html", legend_html(sprite))
    W("about.html", about_html(cat, sprite))
    for f in cat["fonts"]:
        W(f"font/{f['slug']}.html", font_html(f, by, sprite))
    # build report
    json.dump([{k: v for k, v in f.items() if k not in ("account",)} | {"faces": [{k2: v2 for k2, v2 in x.items() if k2 != "cmap"} for x in f.get("faces", [])]}
               for f in cat["fonts"]], open(os.path.join(DATA, "build-report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    nofont = [f["slug"] for f in cat["fonts"] if not f.get("faces")]
    log(f"pages: {len(cat['fonts'])} fonts; faces: {sum(len(f.get('faces', [])) for f in cat['fonts'])}; without usable font: {len(nofont)} {nofont[:30]}")


if __name__ == "__main__":
    main()
