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
from fontTools.pens.statisticsPen import StatisticsPen
from fontTools.pens.transformPen import TransformPen

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA, RAW, FONTS, SITE = (os.path.join(ROOT, p) for p in ("data", "raw/archives", "fonts", "site"))
STATIC = os.path.join(ROOT, "tools", "static")

UI_TEXT = "proletarsk"       # Wiegel's Proletarsk: large x-height, Latin + Cyrillic, ~860 glyphs
UI_DISPLAY = "preussische"   # Prussian railway lettering IV 44 (1880s), DIN 1451's ancestor: the interface face
UI_DIN = "altedin1451"       # no longer used in the interface (labels use the UI face)
UI_MONO = "erikatype"        # Wiegel's Erika Type, the bold face: the one monospaced text (glyph codes)
FONT_EXT = (".ttf", ".otf", ".woff", ".woff2")
DOC_EXT = (".pdf", ".txt", ".rtf", ".doc", ".docx", ".odt", ".htm", ".html")
PUA = range(0xE000, 0xF900)
HOSTED = False   # set by tools/hosted.py: single-shell font pages, original download links

def flink(slug, up=""):
    return f"{up}font.html#{slug}" if HOSTED else f"{up}font/{slug}.html"
WRITTEN = set()   # paths written this run (deletion is disabled in the target folder, so we overwrite instead)
ESC = html.escape


def URL(u):
    """href for a URL from the data: escaped, and only http(s), mailto or relative; anything else becomes '#'."""
    u = (u or "").strip()
    return ESC(u) if not re.match(r"^[a-z][a-z0-9+.-]*:", u, re.I) or re.match(r"^(https?|mailto):", u, re.I) else "#"


def JSON(o):
    """JSON for an inline <script>: '</' cannot close the element early."""
    return json.dumps(o).replace("</", "<\\/")

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
        if depth == 0:
            log("extract: not a zip archive, skipped")   # a nested .exe that is not a self-extractor is expected; a top-level one is not
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
                w = name.getName(i, 3, 1, 0x409)
                w = w.toUnicode() if w else ""
                # a Mac record written in Latin-1 reads back as MacRoman ('VarietÈ'); the Windows record has it right
                if w and w != r and len(w) == len(r) and all(a == b or (127 < ord(a) < 0x250 and ord(b) > 127) for a, b in zip(w, r)):   # only accented letters differ
                    r = w
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
        "created": created_year(f),
        "cmap": sorted(c for c in cps if c >= 0x20 and c not in PUA and not 0x7F <= c < 0xA0),
        "coverage": [k for k, _, t in COVERAGE if t(cps)],
    }


def web_font(src, dst):
    """Copy a font for the browser. A name table whose strings pass 64 KB (a licence text stored twice, Mac and
    Windows) overflows its 16-bit offsets and browsers reject the file; the web copy then drops the Mac records,
    which repeat the Windows ones. The original stays untouched in the downloads."""
    try:
        t = TTFont(src, fontNumber=0, lazy=True, recalcTimestamp=False)   # same bytes on every machine
        names = t["name"].names
        if sum(len(r.toBytes()) for r in names) > 0xFFFF and any(r.platformID == 3 for r in names):
            t["name"].names = [r for r in names if r.platformID != 1]
            t.save(dst)
            log(f"fonts: {os.path.basename(src)}: name table over 64 KB, web copy without Mac name records")
            return
    except Exception:
        pass
    shutil.copy2(src, dst)


def created_year(f):
    try:
        from fontTools.misc.timeTools import timestampToString
        return int(timestampToString(f["head"].created)[-4:])
    except Exception:
        return None


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
                    while out in WRITTEN:
                        stem, ext = os.path.splitext(ascii_name(base))
                        out = os.path.join(dst, f"{stem}-{i}{ext}"); i += 1
                    open(out, "wb").write(b)
                    WRITTEN.add(out)
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
            fp = os.path.join(ROOT, x["path"])
            # a copy without the font folder (cloud session) reuses the metadata recorded by the last full build
            m = analyse(fp) if os.path.exists(fp) or "cmap" not in x else {k: v for k, v in x.items() if k not in ("path", "orig", "sha1", "from")}
            if "error" in m:
                x["error"] = m["error"]
                continue
            x.update(m)
            good.append(x)
        # web-usable first, then OTF over TTF, then newest revision, upright regular first
        def rank(x):
            ext = x["path"].lower().rsplit(".", 1)[-1]
            label = (os.path.basename(x["path"]) + " " + x.get("style", "") + " " + x.get("full", "")).lower()
            variant = bool(re.search(r"(schatten|shadow|outline|kontur|contour|3d|inline|hohl|licht|webfont|_b\b|_bi\b|beach|negativ)", label))
            return (variant, x["italic"], abs(x["weight"] - 400), {"otf": 0, "ttf": 1, "woff2": 2, "woff": 3}.get(ext, 9), -x["rev"])
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
        bad = [x for x in f["files"] if x.get("error")]
        if bad:
            log(f"fonts: {f['slug']}: {len(bad)} unreadable file(s) skipped, e.g. {os.path.basename(bad[0]['path'])}")
        canon = uniq[0] if uniq else None
        f["sample"] = CLOCKS[f["slug"]][0] if f["slug"] in CLOCKS else sample_for(canon["cmap"]) if canon else ""
        f["glyphs"] = canon["chars"] if canon else 0
        f["coverage"] = canon["coverage"] if canon else []
        f["feats"] = sorted({t for x in uniq for t in x["feats"]})
        f["designer"] = next((x["designer"] for x in uniq if x["designer"]), "")
        f["font_license"] = next((x["license"] for x in uniq if x["license"]), "")
        f["copyright"] = next((x["copyright"] for x in uniq if x["copyright"]), "")


# ── photos: freely licensed (Commons), bundled by Apify into raw/photos/*.zip ───
def _pkey(name):
    n = urllib.parse.unquote(name).rsplit("/", 1)[-1]
    n = re.sub(r"^(files-)?[0-9a-f]{8}-", "", n)
    n = re.sub(r"^\d+px-", "", n)
    n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", n)


def place_photos(cat):
    pdir = os.path.join(ROOT, "raw", "photos")
    pool = {}
    if os.path.isdir(pdir):
        for z in sorted(os.listdir(pdir)):
            if not z.lower().endswith(".zip"):
                continue
            try:
                zf = zipfile.ZipFile(os.path.join(pdir, z))
            except zipfile.BadZipFile:
                continue
            for n in zf.namelist():
                pool[_pkey(n)] = (zf, n)
    try:
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None   # trusted Commons originals; some museum scans exceed 300 MP
    except ImportError:
        Image = None
    out_dir = os.path.join(SITE, "assets", "photos")
    hit = 0
    for f in cat["fonts"]:
        ph = f.get("photo")
        if not ph:
            continue
        k = _pkey(ph["src"])
        if k not in pool:
            continue
        zf, n = pool[k]
        b = zf.read(n)
        dst = os.path.join(out_dir, f["slug"] + ".jpg")
        if Image:
            im = Image.open(io.BytesIO(b))
            im.thumbnail((2400, 2400))
            if im.mode not in ("RGB", "L"):
                bg = Image.new("RGB", im.size, (244, 242, 236))
                bg.paste(im.convert("RGBA"), mask=im.convert("RGBA").split()[-1])
                im = bg
            im.save(dst, "JPEG", quality=86, optimize=True, progressive=True)
        else:
            open(dst, "wb").write(b)
        ph["local"] = True
        hit += 1
    log(f"photos: {hit} placed locally")


# ── icons from the archive's own type ─────────────────────────────────────────────
# chip outline: thin and proportional (1.5 of 24 units → 1.1px at 18px, 3px at 48px)
CHIP = '<rect x="0.75" y="0.75" width="22.5" height="22.5" rx="5.5" class="chip"/>'


def icon_svgs(cat):
    by = {f["slug"]: f for f in cat["fonts"]}
    pool = [os.path.join(ROOT, x["path"]) for s in (UI_DISPLAY, UI_DIN, UI_TEXT) for x in by.get(s, {}).get("faces", [])[:1]]
    pool += [os.path.join(ROOT, f["faces"][0]["path"]) for f in cat["fonts"] if f.get("faces") and set(f["coverage"]) >= {"greek", "cyr", "longs"}][:6]
    fonts = []
    for p in pool:   # the order decides which font a mark is cut from; a font missing here changes the sprite
        try:
            fonts.append(TTFont(p, fontNumber=0))
            if pool.index(p) == 0 and os.path.basename(os.path.dirname(p)) == UI_DISPLAY:
                import uifonts   # then the interface's own copy of Preussische IV 44: marks Wiegel's file lacks (ẞ) come from it, the rest stay his
                fonts.append(uifonts.face(UI_DISPLAY, p, kerning=False)[0])
        except Exception as e:
            log(f"icons: pool font unreadable, marks may be cut from another font: {os.path.relpath(p, ROOT)} ({e.__class__.__name__})")
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
            # one optical size for every mark: scale by the bbox's geometric mean, then fit a 15×12 field
            s = min(10.5 / max((w * h) ** 0.5, 1), 15.0 / max(w, 1), 12.0 / max(h, 1))
            # centre on the ink's centre of weight (area centroid), kept inside a 4.5-unit margin
            st = StatisticsPen(glyphset=gs); xx = 0
            for ch in mark:
                g = cmap[ord(ch)]; gs[g].draw(TransformPen(st, (1, 0, 0, 1, xx, 0))); xx += gs[g].width
            cx, cy = (st.meanX, st.meanY) if abs(st.area) > 1 else ((bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2)
            tx = 12 - cx * s; ty = 12 + cy * s
            tx = min(max(tx, 4.5 - bounds[0] * s), 19.5 - bounds[2] * s)
            ty = min(max(ty, 4.5 + bounds[3] * s), 19.5 + bounds[1] * s)
            tx, ty = round(tx * 4) / 4, round(ty * 4) / 4
            out[code] = f'<symbol id="i-{code}" viewBox="0 0 24 24">{CHIP}<path class="mark" transform="translate({tx} {ty}) scale({s:.5f} {-s:.5f})" d="{" ".join(paths)}"/></symbol>'
            break
        else:
            out[code] = f'<symbol id="i-{code}" viewBox="0 0 24 24">{CHIP}<text x="12" y="16" text-anchor="middle" class="mark-t">{ESC(mark[:2])}</text></symbol>'
    return '<svg xmlns="http://www.w3.org/2000/svg" style="display:none">' + "".join(out.values()) + "</svg>"


# ── data derived for v3 ───────────────────────────────────────────────────────────
# Wiegel's own colours, sampled from peter-wiegel.de (CSS + button/banner images)
# light paper / dark ink, light first (pale yellow / navy and lilac / violet dropped 28 Oct 2026, Okay); ordered by the light's hue, yellow to pinks. One light per pair, none repeated.
# From Wiegel's site: starburst yellow, pale yellow, specimen tan, banner sky, navy, oxblood, UNZ indigo, button violet;
# the other lights and darks are shades of those, chosen so no ground fights his download green (all ≥ 1.6 : 1 against it).
PALETTE = collections.OrderedDict([
    ("sun",      ("#FDFA00", "#5C2A00", "Starburst yellow / umber")),
    ("tan",      ("#D3BFA4", "#800025", "Specimen paper / oxblood")),
    ("sky",      ("#00A3EA", "#002A4D", "Banner sky / deep sea")),
    ("lavender", ("#CFC8F5", "#3B2A98", "Lavender / UNZ indigo")),
    ("rose",     ("#FF9EC4", "#2A0A3D", "Rose / aubergine")),
    ("blush",    ("#FFD1DC", "#5A0038", "Blush / plum")),
])
USE_PAL = PALETTE
FAM_PAL = {
    "Blackletter": ["tan", "blush"],
    "Handwriting": ["sky", "lavender"],
    "Norm & Sans": ["sun", "sky"],
    "Serif":       ["tan", "blush"],
    "Display":     ["sun", "sky", "rose"],
    "Technical":   ["sun", "sky"],
    "Symbols":     ["lavender", "rose"],
    "Other":       ["lavender", "tan", "rose"],
}
TEXT_FAMS = {"Blackletter", "Handwriting", "Norm & Sans", "Serif", "Technical"}
LANES = [("type", "Type"), ("digital", "Digitised"), ("world", "Elsewhere")]


def pal_for(f):
    opts = FAM_PAL.get(f["family"], FAM_PAL["Other"])
    return opts[int(hashlib.md5(f["slug"].encode()).hexdigest(), 16) % len(opts)]


def digitised(f):
    """(year, who) of the digital font, from the font file: copyright line first, then head.created."""
    for x in f.get("faces", []):
        cp = x.get("copyright", "")
        m = re.search(r"(?:copyright|\(c\)|©)\D{0,8}((?:19|20)\d\d)", cp, re.I)
        if m and 1990 <= int(m.group(1)) <= 2023:
            return int(m.group(1)), ("Steffmann" if "steffmann" in cp.lower() else "Wiegel")
    for x in f.get("faces", []):
        if x.get("created") and 1995 <= x["created"] <= 2023:
            return x["created"], "Wiegel"
    return None, None


def is_text(f):
    if not f.get("faces"):
        return False
    c = set(f["faces"][0]["cmap"])
    full = all(x in c for x in range(0x41, 0x5B)) and all(x in c for x in range(0x61, 0x7B))
    odd = set(f["icons"]) & {"versalien", "gemeine", "dingbat", "ziffern", "kapitaelchen", "spezial", "color"}
    return f["family"] in TEXT_FAMS and full and not odd


def lane_of(what):
    if re.search(r"\b(wiegel|digiti[sz]|request|revis|forum|opentype|lockdown|expanded|built at|recreate)", what, re.I):
        return "digital"
    if re.search(r"(issu|releas|\bcut|design|foundry|typeface|\btypes?\b|\bfont|script|standard|specimen|\bDIN\b|\bTGL\b|\bcast|publish|lettering|alphabet|schrift|fraktur|catalogue|engraver|typo)", what, re.I):
        return "type"
    return "world"


# a design that came inside another font's download, shown as a font of its own (Okay, 28 Oct 2026: "a fluke by Peter")
SPLIT = [("variete", "barnroof.ttf", "barnroof", "Barnroof",
          "A design of its own that came inside the Varieté download; Wiegel never posted it separately.")]


def split_out(cat):
    """Take each SPLIT face out of its parent and add it as a font at the end of the archive, so no number moves."""
    by = {f["slug"]: f for f in cat["fonts"]}
    for parent, file, slug, name, summary in SPLIT:
        p = by.get(parent)
        face = next((x for x in (p or {}).get("faces", []) if os.path.basename(x["path"]).lower() == file), None)
        if not face or slug in by:
            continue
        p["faces"].remove(face)
        c = set(face["cmap"])
        f = json.loads(json.dumps(p))
        f.update(slug=slug, name=name, faces=[face], account={}, summary=summary, tags=[], photo=None, place=None, maps=None,
                 found=[], related=[], years=[], year=None, decade=None, origin=None, prev=cat["fonts"][-1]["slug"], next=None,
                 icons=[i for i in p["icons"] if i != "eurosign" or 0x20AC in c],   # Wiegel's buttons for the download, as far as this face has them
                 sample=sample_for(face["cmap"]), glyphs=face["chars"], coverage=face["coverage"], feats=sorted(face["feats"]))
        cat["fonts"][-1]["next"] = slug
        cat["fonts"].append(f)


def enrich(cat):
    split_out(cat)
    for i, f in enumerate(cat["fonts"]):
        f["no"] = i + 1
        f["pal"] = pal_for(f)
        f["dy"], f["dwho"] = digitised(f)
        f["text"] = is_text(f)
        evs = [{"y": y["y"], "what": y["what"], "lane": lane_of(y["what"])} for y in f.get("years", [])]
        if f["dy"] and not any(e["lane"] == "digital" and e["y"] == f["dy"] for e in evs):
            evs.append({"y": f["dy"], "what": "Digitised by Dieter Steffmann; re-encoded by Wiegel later" if f["dwho"] == "Steffmann" else "Digitised by Peter Wiegel", "lane": "digital", "auto": True})
        f["events"] = sorted(evs, key=lambda e: e["y"])
        ky = f.get("year")
        orig = [e["y"] for e in f["events"] if e["lane"] == "type"]
        f["oy"] = ky if ky in orig else min(orig) if orig else (ky if ky and not any(e["y"] == ky and e["lane"] == "digital" for e in f["events"]) and (not f["dy"] or ky < f["dy"]) else None)


def nofmt(n):
    return f"{n:03d}"


# ── HTML ─────────────────────────────────────────────────────────────────────────
def icon(code, size=24):
    if code not in ICONS:
        return ""
    return f'<svg class="ic" width="{size}" height="{size}" aria-label="{ESC(ICONS[code][1])}" role="img"><title>{ESC(ICONS[code][1])}</title><use href="#i-{code}"/></svg>'


NAV = [("index", "Fonts", "index.html"), ("timeline", "Timeline", "timeline.html"), ("images", "Images", "images.html"), ("about", "About", "about.html")]
ABOUT = [("about", "Peter Wiegel", "about.html"), ("site", "This site", "site.html"), ("legend", "Legend", "legend.html"), ("catalogue", "Catalogue", "catalogue.html")]   # the About pages share the second row


THEME_JS = """(function(){var P=%s,A={dark:["#00A3EA","#FDFA00","#E20084","#2FB35A","#FF3D7F","#B04CFF"],light:["#0079B8","#E20084","#05872C","#D40051","#7C00AD"]},r=document.documentElement,m;
try{m=localStorage.getItem("wa-mode")}catch(e){}r.dataset.mode=m=(m==="mono"?"mono":"random");
var pick=function(a){return a[Math.floor(Math.random()*a.length)]};
try{window.WA_INV=localStorage.getItem("wa-inv")==="1"}catch(e){}if(window.WA_INV)r.classList.add("inv");
window.WA_PAL=P;window.WA_theme=function(pair){var s=r.style;
 if(!pair&&r.dataset.mode==="random"){var c=s.getPropertyValue("--paper"),L=Object.values(P).filter(function(x){return x[0]!==c});pair=pick(L.length?L:Object.values(P))}
 if(pair){window.WA_CUR=pair;var a=pair[0],b=pair[1];if(window.WA_INV){a=pair[1];b=pair[0]}s.setProperty("--paper",a);s.setProperty("--ink",b);s.setProperty("--hot",b);s.setProperty("--dark",pair[1]);r.dataset.on="pair"}
 else{s.removeProperty("--paper");s.removeProperty("--ink");s.removeProperty("--dark");var d=matchMedia("(prefers-color-scheme: dark)").matches;s.setProperty("--hot",pick(d?A.dark:A.light));r.dataset.on="mono"}};
var k;try{k=localStorage.getItem("wa-pair")}catch(e){}window.WA_PICK=P[k]?k:"";
window.WA_theme(r.dataset.mode!=="random"?null:P[k]||(window.WA_FONTPAL?P[window.WA_FONTPAL]:null))})();"""


SWATCHES = '<button type="button" class="sw cinv" id="cinv" title="Invert: dark grounds, light ink" aria-label="Invert colours"><svg viewBox="0 0 18 18" aria-hidden="true"><path d="M10.5 1 3.5 10.2h4.6L7 17l7.5-9.6H9.8z"/></svg></button><button type="button" class="sw cmono" data-m="mono" style="--b:#f4f2ec;--f:#12110f" title="Mono: black and white with one bright accent" aria-label="Mono colours"></button>' + "".join(f'<button type="button" class="sw" data-p="{k}" style="--b:{v[0]};--f:{v[1]}" title="{ESC(v[2])}" aria-label="{ESC(v[2])}"></button>' for k, v in USE_PAL.items())


def page(title, body, depth=0, sprite="", cls="", cur="", fontpal="", sub=""):
    """sub: key of the About page shown; fills the second row server-side (font pages fill it from their template)"""
    up = "../" * depth
    row2 = ('<span class="secs">' + "".join(f'<a class="{"on" if k == sub else ""}" href="{up}{href}"{" aria-current=page" if k == sub else ""}>{label}</a>' for k, label, href in ABOUT) + '</span>') if sub else ""
    links = "".join(f'<a class="{"on" if k == cur else ""}" href="{up}{href}"{" aria-current=page" if k == cur and not sub else ""}>{label}</a>' for k, label, href in NAV)
    return deco(f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex,nofollow">
<title>{ESC(title)}</title>
<link rel="stylesheet" href="{up}assets/app.css">
<script>window.ROOT="{up}";window.HOSTED={"true" if HOSTED else "false"};window.UIFONTS={json.dumps(UIFONTS)};window.WA_FONTPAL={json.dumps(fontpal)};{THEME_JS % json.dumps({k: v[:2] for k, v in USE_PAL.items()})}</script>
</head><body class="p-{cls}">
{sprite}
<header class="top" id="top">
<nav class="nav1" aria-label="Site"><a class="home" href="{up}index.html">Wiegel Archive</a>{links}<form class="nsearch" role="search" action="{up}index.html"><input class="fin" id="nq" type="search" name="q" autocomplete="off" enterkeyhint="search" placeholder="Search" aria-label="Search the archive"></form><span class="modes"><span class="cpick"><span class="cpanel" id="cpanel" hidden role="group" aria-label="Wiegel's colours"><span class="cin">{SWATCHES}</span></span><button class="sw cbtn" id="cbtn" type="button" title="Colours: invert, mono or one of Wiegel's pairs" aria-expanded="false" aria-controls="cpanel" aria-label="Colours"></button></span><a class="rndfont" href="{up}index.html" id="rndfont" title="Open a random font">Random</a></span><button class="mode burger" id="burger" type="button" aria-label="Menu" aria-expanded="false" aria-controls="menu"><svg viewBox="0 0 18 18" aria-hidden="true"><path d="M3 5H15M3 9H15M3 13H15" vector-effect="non-scaling-stroke"/></svg></button></nav>
<nav class="nav2" id="subnav" aria-label="{"About" if sub else "This font"}">{row2}</nav>
<nav class="nav3" id="stylenav" aria-label="Styles and neighbours"></nav>
<div class="menu" id="menu" hidden role="dialog" aria-modal="true" aria-label="Menu"><button class="mode mclose" id="mclose" type="button" aria-label="Close menu"><svg viewBox="0 0 18 18" aria-hidden="true"><path d="M4 4L14 14M14 4L4 14" vector-effect="non-scaling-stroke"/></svg></button><nav class="mlist" aria-label="Site">{links}</nav><div class="mslot"></div></div>
</header>
<main>{body}
<footer class="foot"><p class="info">A private archive of the free fonts of Peter Wiegel / CAT Fonts. Fonts © their authors, under the licences bundled in each archive. Texts are new English write-ups; the originals are at <a href="http://www.peter-wiegel.de/">peter-wiegel.de</a>.</p></footer>
</main>
<script src="{up}assets/catalog.js"></script><script src="{up}assets/app.js"></script>
</body></html>""")


def fonts_css_entry(f, i, x, up):
    src = up + (x.get("websrc") or "assets/fonts/" + f["slug"] + "/" + os.path.basename(x["path"]))   # websrc: the hosted copy's set bundle
    return {"id": f"wa-{f['slug']}-{i}", "src": src, "style": x["style"], "weight": x["weight"], "italic": x["italic"], "glyphs": x["chars"], "feats": x["feats"], "full": x["full"]}


DIN_RX = re.compile(r"\bDIN ?(?:1451|16)\b")   # cites the DIN 1451 or DIN 16/17 standard; "pre-DIN" ancestors do not match


def is_din(f):
    """In the DIN family pill as well as its own family: the standard is named in its name, origin or tags."""
    return bool(DIN_RX.search(" ".join([f["name"], f.get("origin") or ""] + f.get("tags", []))))


DOT_EXTRA = {"baudotmurrey"}   # punched-tape holes on a grid; Wiegel files it under dingbats


def is_dot(f):
    """In the Dot matrix pill as well: letters built from small elements repeated on a grid (bulbs, LEDs, pixels, cells, holes)."""
    return f["genre"] == "dot-matrix/led" or f["slug"] in DOT_EXTRA


def is_typewriter(f):
    """In the Typewriter pill as well: faces of typewriters, tagged so by hand (Erika, Tippa, Schiet Schriefmaschin …)."""
    return "typewriter" in [t.lower() for t in f.get("tags", [])]


def extra_families(f):
    """Family pills a font shows under besides its own (checked by eye on 28 Oct 2026)."""
    return [x for x, test in (("DIN", is_din), ("Dot matrix", is_dot), ("Typewriter", is_typewriter)) if test(f)]


MEMBERS = {}


def members_of(f):
    """A download holding several fonts: [(face index, member)], in the curated order, or None. Names come from data/members.json."""
    if not MEMBERS:
        p = os.path.join(DATA, "members.json")
        MEMBERS.update(json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {"": {}})
    m = MEMBERS.get(f["slug"])
    if not m:
        return None
    idx = {os.path.basename(x["path"]): i for i, x in enumerate(f.get("faces", []))}
    out = [(idx[x["file"]], x) for x in m["members"] if x["file"] in idx]
    return out if len([1 for _, x in out if not x.get("other")]) > 1 else None


# fonts whose pictures come from typing times: OpenType ligatures turn h:mm (five-minute steps) into a clock face
CLOCKS = {"stefansuhr": ("8:45 12:00 3:30", "1:05 2:10 4:20 5:25 6:35 7:40 9:50 10:55 11:15")}


def figures_only(f):
    """Digits but no Latin letters (or Wiegel's 'Figures only' button): set in figures everywhere, never in its name.
    Clock fonts count too: their letters are a plain stand-in, the clocks come from typed times."""
    if f["slug"] in CLOCKS:
        return True
    c = set(f["faces"][0]["cmap"]) if f.get("faces") else set()
    letters = any(x in c for x in list(range(0x41, 0x5B)) + list(range(0x61, 0x7B)))
    return "ziffern" in f["icons"] or (not letters and any(x in c for x in range(0x30, 0x3A)))


COMPANION = re.compile(r"\b(?:Alt|Alternates?|Init|Initials?|Start)\b", re.I)   # alternates, initials and word-start forms go with an original


def list_rows(f, faces):
    """The set's styles as rows of the font list. Companions (alternates, initials, start forms) stay under their original:
    they show on the font page, not as rows. A set made only of such names keeps them all ('Schwaben Alt' is a name)."""
    ms = [(i, x) for i, x in members_of(f) if not x.get("other")]
    keep = [(i, x) for i, x in ms if not COMPANION.search(x["name"])] or ms
    return [[i, member_name(f, x), faces[i]["src"]] for i, x in keep]


def member_name(f, x):
    """A set member's name as the list shows it: 'Varieté Cabaret'; for styles, the font's name and the style ('cbe Bold')."""
    if MEMBERS[f["slug"]]["kind"] == "collection":
        return x["name"]
    return f["name"] if x["short"] in ("Regular", "Normal") else f["name"] + " " + x["name"]


def set_count(f):
    ms = members_of(f)
    return [len([1 for _, x in ms if not x.get("other")]), MEMBERS[f["slug"]]["kind"]] if ms else None


def write_catalog_js(cat):
    rows = []
    for x in ("DIN", "Dot matrix", "Typewriter"):
        log(f"{x}: " + ", ".join(f["slug"] for f in cat["fonts"] if x in extra_families(f)))
    for f in cat["fonts"]:
        faces = [fonts_css_entry(f, i, x, "") for i, x in enumerate(f.get("faces", []))]
        rows.append({
            "s": f["slug"], "n": f["name"], "no": f["no"], "fa": f["family"], "g": f["genre"], "e": f.get("decade"),
            "y": f.get("oy"), "dy": f.get("dy"), "sec": f["section"], "p": f["pos"], "of": f["of"],
            "ic": f["icons"], "cv": f.get("coverage", []), "sm": f.get("sample", ""), "gl": f.get("glyphs", 0),
            "st": len(faces), "f": faces[:1], "sum": f.get("summary", ""), "pl": f.get("place"), "ph": bool(f.get("photo")),
            "tg": f.get("tags", []), "pal": f["pal"], **({"xf": extra_families(f)} if extra_families(f) else {}),
            **({"set": set_count(f), "mn": " ".join(x["name"] for _, x in members_of(f)),
                "ms": list_rows(f, faces)} if members_of(f) else {}),   # one list row per style
            **({"fo": 1} if figures_only(f) else {}),
            **({"aa": aa(f)} if aa(f) != "Aa" else {}),   # what its card shows
        })
    js = "window.CATALOG=" + json.dumps({"families": cat["families"], "palette": {k: v[:2] for k, v in USE_PAL.items()}, "icons": {k: v[1] for k, v in ICONS.items()}, "fonts": rows}, ensure_ascii=False, separators=(",", ":")) + ";"
    open(os.path.join(SITE, "assets", "catalog.js"), "w", encoding="utf-8").write(js)


def index_html(cat, sprite):
    fonts = cat["fonts"]
    n_faces = sum(f.get("n_styles", len(f.get("faces", []))) for f in fonts)
    oys = [e["y"] for f in fonts for e in f["events"] if e["lane"] == "type"]
    dys = [f["dy"] for f in fonts if f.get("dy")]
    body = f"""
<div class="homegrid">
  <section class="homelist" aria-label="Typefaces"><p class="fcount"><span class="info" id="count" aria-live="polite"></span><button type="button" class="pill small" id="fclear" hidden>Clear</button></p><div id="grid" class="grid list"></div>
  <footer class="foot"><p class="info">A private archive of the free fonts of Peter Wiegel / CAT Fonts. Fonts © their authors, under the licences bundled in each archive. Texts are new English write-ups; the originals are at <a href="http://www.peter-wiegel.de/">peter-wiegel.de</a>.</p></footer></section>
  <aside class="side" aria-label="Filter">
    <div class="sidehead"><p class="fcount vmode" role="group" aria-label="View"><button type="button" class="pill small" data-v="cards" aria-pressed="false">Cards</button><button type="button" class="pill small on" data-v="preview" aria-pressed="true">Preview</button></p><textarea class="fin settext" id="retype" rows="2" autocomplete="off" spellcheck="false" placeholder="Preview text" aria-label="Type text to set every name"></textarea>
    <div class="picked" id="picked" aria-label="Selected filters"></div></div>
    <details id="fdet" open><summary class="fsum">Filters <svg class="ca pm" viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="8.6" vector-effect="non-scaling-stroke"/><path d="M5.6 10H14.4" vector-effect="non-scaling-stroke"/><path class="v" d="M10 5.6V14.4" vector-effect="non-scaling-stroke"/></svg></summary>
    <div id="fside"></div>
    </details>
    <p class="info about-l">{len(fonts)} typefaces and {n_faces} styles by Peter Wiegel, digitised {min(dys)} to {max(dys)} from type, signs and handwriting dated {min(oys)} to {max(oys)}.</p>
  </aside>
</div>
"""
    return page("Wiegel Archive", body, 0, sprite, "home", "index")


def aa(f):
    """What a font card shows, as Font Book does: 'Aa', or figures for figures-only fonts, or the first two characters it has."""
    c = set(f["faces"][0]["cmap"]) if f.get("faces") else set()
    if f["slug"] in CLOCKS:
        return "3:00"
    if figures_only(f):
        return "12"
    if 0x41 in c:
        return "A" + ("a" if 0x61 in c else "B" if 0x42 in c else "")
    return "".join(chr(x) for x in sorted(c) if x > 0x20)[:2]


def timeline_html(cat, sprite):
    """One stem, today at the top and the past below. A year appears only where something happened. Each font is a card
    (its own 'Aa' and its name, like Font Book). A note (what happened) heads the cards it applies to; fonts sharing a note
    share it. Wiegel's plain digitisations follow as a bulk of cards, headed "Wiegel digitised N fonts" only in a year with
    no notes. The decade strip on top jumps to the first year of a decade."""
    def face_src(f):
        face = f["faces"][0] if f.get("faces") else None
        return ("assets/fonts/" + f["slug"] + "/" + (face.get("web") or os.path.basename(face["path"]))) if face else ""
    def card(f):
        return (f'<a class="fc" href="{flink(f["slug"])}" title="{ESC(f["name"])}">'
                f'<span class="aa" data-src="{face_src(f)}">{ESC(aa(f))}</span><span class="nm">{ESC(f["name"])}</span></a>')
    cards = lambda fs: f'<div class="fcs">{"".join(card(f) for f in sorted(fs, key=lambda f: f["name"].lower()))}</div>'
    order = {"type": 0, "world": 1, "digital": 2}
    notes, bulk = collections.defaultdict(dict), collections.defaultdict(list)   # year -> {note: [fonts]} in lane order; year -> [fonts]
    for f in cat["fonts"]:
        for e in f["events"]:
            if e.get("auto"):
                bulk[e["y"]].append(f)
    for e, f in sorted(((e, f) for f in cat["fonts"] for e in f["events"] if not e.get("auto")), key=lambda t: (order[t[0]["lane"]], t[1]["name"].lower())):
        fs = notes[e["y"]].setdefault(e["what"], [])
        if f not in fs:
            fs.append(f)
    years = sorted(set(notes) | set(bulk), reverse=True)
    rows = []
    for y in years:
        body = "".join(f'<div class="ng"><p class="note">{ESC(w[:1].upper() + w[1:])}</p>{cards(fs)}</div>' for w, fs in notes[y].items())
        if bulk[y]:
            n = len(bulk[y])
            head = "" if notes[y] else f'<p class="dgn">Wiegel digitised <span class="tnum">{n}</span> font{"s" if n > 1 else ""}</p>'
            body += f'<div class="ng">{head}{cards(bulk[y])}</div>'
        rows.append(f'<section class="yr" id="y{y}"><h2 class="yl tnum">{y}</h2><i class="node"></i><div class="yb">{body}</div></section>')
    first = {}
    for y in years:
        first.setdefault(y // 10 * 10, y)
    strip = "".join(f'<a class="dc tnum" href="#y{first[d]}">{d}s</a>' for d in sorted(first, reverse=True))   # only decades with something in them
    body = f"""
<div id="tl">
  <nav class="decs" aria-label="Decades">{strip}</nav>
  <div class="stem"><p class="now">Today</p>{"".join(rows)}</div>
</div>"""
    return page("Timeline — Wiegel Archive", body, 0, sprite, "timeline", "timeline")


def catalogue_html(cat, sprite):
    rows = []
    for f in cat["fonts"]:
        ix = ["A–K", "L–Z", "Fonts 2", "Unlisted"].index(f["section"]) * 1000 + f["pos"]
        st, gl = len(f.get("faces", [])), f.get("glyphs", 0)
        src = f.get("place") or f.get("origin") or ""
        rows.append(
            f'<a class="crow" href="{flink(f["slug"])}" data-no="{f["no"]}" data-name="{ESC(f["name"].lower())}" data-fa="{cat["families"].index(f["family"]) if f["family"] in cat["families"] else 99}" '
            f'data-oy="{f.get("oy") or 9999}" data-dy="{f.get("dy") or 9999}" data-gl="{gl}" data-ix="{ix}">'
            f'<span class="c-no info tnum">{nofmt(f["no"])}</span>'
            f'<span class="c-name">{ESC(f["name"])}</span>'
            f'<span class="c-fa">{ESC(f["family"])}</span>'
            f'<span class="c-oy tnum">{f.get("oy") or ""}</span>'
            f'<span class="c-dy tnum">{f.get("dy") or ""}</span>'
            f'<span class="c-gl info tnum">{gl:,} glyphs</span>'
            f'<span class="c-src" title="{ESC(src)}">{ESC(src)}</span>'
            f'<span class="c-ic">{"".join(icon(c, 18) for c in f["icons"] if c in ICONS)}</span></a>')
    sorts = [("no", "No."), ("name", "Name"), ("fa", "Family"), ("oy", "Original"), ("dy", "Digitised"), ("gl", "Glyphs")]
    head = "".join(f'<button type="button" class="c-{k} sortb" data-k="{k}">{l}</button>' for k, l in sorts)
    body = f"""
<section class="intro"><p class="lead">All {len(cat['fonts'])} typefaces in one list. Sort by any heading. <em>Original</em> is the key date of the source; <em>Digitised</em> is read from the font file.</p>
<label class="t search"><span>Filter</span><input id="tq" type="search" autocomplete="off"></label></section>
<div class="lister" id="cat"><div class="chead">{head}</div><div class="cbody">{''.join(rows)}</div></div>"""
    return page("Catalogue — Wiegel Archive", body, 0, sprite, "catalogue", "about", sub="catalogue")


def images_html(cat, sprite, photo_dir):
    groups = collections.OrderedDict()   # one card per distinct photograph; fonts sharing it are listed together
    for f in cat["fonts"]:
        p = os.path.join(photo_dir, f["slug"] + ".jpg")
        if not f.get("photo") or not os.path.exists(p):
            continue
        groups.setdefault(hashlib.sha1(open(p, "rb").read()).hexdigest(), []).append(f)
    items = []
    for fs in groups.values():
        f0, ph = fs[0], fs[0]["photo"]
        names = ""
        for f in fs:
            face = f["faces"][0] if f.get("faces") else None
            src = ("assets/fonts/" + f["slug"] + "/" + os.path.basename(face["path"])) if face else ""
            names += f'<a class="fn" href="{flink(f["slug"])}" data-src="{src}">{ESC(f["name"])}</a>'
        items.append(f'<figure class="pic"><a href="{flink(f0["slug"])}"><img src="assets/photos/{f0["slug"]}.jpg" alt="{ESC(ph.get("caption",""))}" loading="lazy"></a>'
                     f'{names}<figcaption class="info">{" · ".join(nofmt(f["no"]) for f in fs)} · {ESC(ph.get("caption") or f0.get("place") or "")}</figcaption></figure>')
    body = f"""
<section class="intro"><p class="lead">{len(items)} photographs of the buildings, signs, machines and pages the fonts come from. Each opens its font.</p></section>
<section class="pics" id="pics">{''.join(items)}</section>"""
    return page("Images — Wiegel Archive", body, 0, sprite, "images", "images")


PANGRAM_DE = "Victor jagt zwölf Boxkämpfer quer über den großen Sylter Deich"


# the one arrow: a circle with an arrow, stroke = the one line thickness; class sets the direction (r l u d ne)
def CA(d="r"):
    return (f'<svg class="ca {d}" viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="8.6" vector-effect="non-scaling-stroke"/>'
            '<path d="M1.4 10H15.4M10.6 5.2L15.4 10L10.6 14.8" vector-effect="non-scaling-stroke"/></svg>')
# inside pills: the long arrow without a circle, same stroke
_ARW = '<svg class="arw" viewBox="0 0 18 12" aria-hidden="true"><path d="{}" vector-effect="non-scaling-stroke"/></svg>'
ARROW_L = _ARW.format("M17 6H1M6 1L1 6L6 11")
ARROW_R = _ARW.format("M1 6H17M12 1L17 6L12 11")
_LINK = re.compile(r'<a\b([^>]*)>(.*?)</a>', re.S)
def deco(html):
    """links out end in the up-right arrow, downloads in the down arrow"""
    def one(m):
        a, inner = m.group(1), m.group(2)
        if 'class="ca' in inner: return m.group(0)
        if re.search(r'href="https?:', a): d = "ne"
        elif " download" in a or "assets/docs/" in a: d = "d"
        else: return m.group(0)
        tail = re.match(r"(.*?)([^\s<>]+)\s*$", inner, re.S)   # the last word travels with the arrow, never leaving it alone on a line
        if tail and 'class="t"' not in a:
            return f'<a{a}>{tail.group(1)}<span class="nw">{tail.group(2)}{CA(d)}</span></a>'
        return f'<a{a}>{inner}{CA(d)}</a>'
    return _LINK.sub(one, html)


def lic_name(t):
    """Only the name of the licence embedded in a font file; boilerplate, URLs and jokes are left out."""
    t = t or ""; low = t.lower(); names = []
    if "creative commons" in low:
        v = re.search(r"(\d\.\d)", t)
        names.append("Creative Commons" + (" Attribution" if "namensnennung" in low or "attribution" in low else "")
                     + (" " + v.group(1) if v else "") + (" Germany" if "deutschland" in low else ""))
    if "gpl" in low or "gpj" in low or "general public" in low:
        names.append("GNU GPL" + (" with font exception" if "font exception" in low else ""))
    if "ofl" in low or "open font" in low or "openont" in low:
        v = re.search(r"open font license,? version (\d\.\d)", low)
        names.append("SIL Open Font License" + (" " + v.group(1) if v else ""))
    if not names:
        if "privaten gebrauch" in low or "private use" in low: names.append("Private use only")
        elif "evaluat" in low: names.append("Evaluation only")
        elif any(k in low for k in ("freeware", "alles ist erlaubt", "free software", "freie software", "unlimited permission")): names.append("Freeware")
    return " and ".join(names)


def specimen_blocks(f, faces):
    """Apple-style text styles for text faces; big editable previews for display and odd faces."""
    c = set(f["faces"][0]["cmap"]) if f.get("faces") else set()
    has = lambda s: all(ord(ch) in c for ch in s if not ch.isspace())
    a = f.get("account") or {}
    if f["text"]:
        body_txt = " ".join(x for x in (a.get("what"), a.get("history")) if x) or f.get("summary", "")
        title = PANGRAM_DE if has(PANGRAM_DE) else "Zwölf Boxkämpfer jagen Victor quer über den Sylter Deich"
        if not has(title):
            title = f.get("sample") or f["name"]
        headline = f.get("summary") or f["name"]
        caption = " · ".join(x for x in (f.get("place"), f.get("origin")) if x) or f["name"]
        caption += " — 0123456789 & ? ! (€) ‚§‘"
        blocks = [("Large Title", 128, f["name"], "fit"), ("Title", 80, title, ""), ("Headline", 44, headline, ""),
                  ("Body", 24, body_txt, "cols"), ("Caption", 15, caption, "")]
    else:
        up_ = "".join(chr(x) for x in range(0x41, 0x5B) if x in c)
        lo_ = "".join(chr(x) for x in range(0x61, 0x7B) if x in c)
        dg_ = "".join(chr(x) for x in range(0x30, 0x3A) if x in c)
        blocks = [("Name", 200, f["name"], "fit")]
        if f["slug"] in CLOCKS:   # only typed times show what the font is: clocks
            blocks = [("Clocks", 200, CLOCKS[f["slug"]][0], "fit"), ("Times", 160, CLOCKS[f["slug"]][1], "fit")]
            up_ = lo_ = dg_ = ""
        elif figures_only(f):   # no letters to set its name in: figures, then the sample (times, prices)
            blocks = [("Figures", 200, dg_, "fit")]
            if "".join(ch for ch in ".,:;" if ord(ch) in c): blocks.append(("Sample", 160, " ".join(x for x in ("12:45", "3,50", "19.03.") if all(ord(ch) in c for ch in x)), "fit"))
            dg_ = ""
        if up_: blocks.append(("Capitals", 160, up_, "fit"))
        if lo_ and lo_.upper() != up_ or (lo_ and "gemeine" in f["icons"]): blocks.append(("Lowercase", 160, lo_, "fit"))
        if dg_: blocks.append(("Figures", 160, dg_ + " " + "".join(ch for ch in "&?!€§" if ord(ch) in c), "fit"))
        if f.get("sample") and f["sample"] not in (up_, lo_, f["name"]) and not figures_only(f): blocks.append(("Sample", 160, f["sample"], "fit"))
    out = []
    for i, (role, px, txt, mode) in enumerate(blocks):
        out.append(f'<div class="blk{" " + mode if mode else ""}{" on" if i == 0 else ""}" data-px="{px}" data-role="{role}" data-def="{ESC(txt)}">'
                   f'<span class="vl" aria-hidden="true">{role} <b class="tnum">{px}</b></span>'
                   f'<div class="ed" contenteditable="true" spellcheck="false" style="font-size:{px}px">{ESC(txt)}</div></div>')
    return "".join(out)


def strip_html(f):
    evs = f["events"]
    if not evs:
        return ""
    lo, hi = min(evs[0]["y"], 1900), max(evs[-1]["y"], 2025)
    lo = lo // 50 * 50
    span = max(1, hi - lo)
    dots = "".join(f'<i class="l-{e["lane"]}" style="--x:{(e["y"] - lo) / span * 100:.2f}%" title="{e["y"]}"></i>' for e in evs)
    ticks = "".join(f'<span class="tk tnum" style="--x:{(t - lo) / span * 100:.2f}%">{t}</span>' for t in range(lo, hi + 1, 50 if span > 200 else 25))
    items = "".join(f'<li class="l-{e["lane"]}"><span class="y tnum">{e["y"]}</span><span class="w">{ESC(e["what"])}</span></li>' for e in evs)
    gap = ""
    oy = f.get("oy")
    if oy and f.get("dy") and f["dy"] > oy:
        gap = f'<p class="gap"><span class="tnum">{f["dy"] - oy}</span> years between the original ({oy}) and the digital font ({f["dy"]}).</p>'
    return f'<div class="axis">{dots}{ticks}</div>{gap}<ol class="evs">{items}</ol>'


def sec(label, inner, id_=""):
    return f'<section class="sec"{f" id={id_}" if id_ else ""}><h2 class="lab">{label}</h2><div class="sb">{inner}</div></section>'


def font_html(f, by, sprite, up="../", fragment=False):
    faces = [fonts_css_entry(f, i, x, up) for i, x in enumerate(f.get("faces", []))]
    canon = f["faces"][0] if f.get("faces") else None
    a = f.get("account") or {}
    bg, fg, _ = PALETTE[f["pal"]]
    chips = "".join(f'<li>{icon(c, 48)}<span>{ESC(ICONS[c][1])}</span></li>' for c in f["icons"] if c in ICONS)
    ms = members_of(f)
    set_html, set_n, now = "", 0, ""
    if ms:
        kind = MEMBERS[f["slug"]]["kind"]
        def li(i, x):
            k = x["short"] if kind == "styles" else ""
            txt = f["sample"] if figures_only(f) else x["name"]   # clocks and figures-only fonts show what they draw
            return f'<li data-i="{i}" title="{ESC(x["name"])}"><span class="fn">{ESC(txt)}</span><span class="k">{ESC(k or (x["name"] if txt != x["name"] else ""))}</span></li>'   # shown, not a switch: the style pills in the bar switch
        main = [li(i, x) for i, x in ms if not x.get("other")]
        extra = [li(i, x) for i, x in ms if x.get("other")]
        set_n = len(main)
        now = next((x["short"] for i, x in ms if i == 0), "")
        set_html = (f'<ul class="fl">{"".join(main)}</ul>'
                    + (f'<h3>Also in the download</h3><ul class="fl other">{"".join(extra)}</ul>' if extra else ""))
        set_label = f'Set <span class="info tnum">{set_n} {"styles" if kind == "styles" else "fonts"}</span>'
    dl = "".join(
        f'<li><a href="{up}assets/dl/{urllib.parse.quote(d["local"])}" download>{ESC(d["name"])}</a><span class="sub tnum">{ESC(d["kind"])}{" · " + format(d["bytes"] / 1024, ".0f") + " KB" if d["bytes"] else ""}</span></li>'
        if d["local"] and not HOSTED else f'<li><a href="{URL(d["src"])}">{ESC(d["name"])}</a><span class="sub">original link</span></li>'
        for d in f.get("downloads", []))
    docs = "" if HOSTED else "".join(f'<li><a href="{up}assets/docs/{f["slug"]}/{urllib.parse.quote(os.path.basename(d["path"]))}">{ESC(os.path.basename(d["path"]))}</a></li>' for d in f.get("docs", []))
    ph = f.get("photo")
    photo = ""
    if ph:
        photo = (f'<figure class="photo"><img src="{up}assets/photos/{f["slug"]}.jpg" alt="{ESC(ph.get("caption",""))}" loading="lazy" '
                 f'onerror="this.onerror=null;this.src={ESC(json.dumps(ph["src"]))}"><figcaption><span>{ESC(ph.get("caption",""))}</span>'
                 f'<span class="sub">Photo: {ESC(ph.get("author",""))} · {ESC(ph.get("license",""))} · <a href="{URL(ph.get("page",""))}">source</a></span></figcaption></figure>')
    found = "".join(f'<li><a href="{URL(x["u"])}">{ESC(x.get("t") or x.get("site",""))}</a><span class="sub">{ESC(x.get("site",""))}{" · " + ESC(x["note"]) if x.get("note") else ""}</span></li>' for x in f.get("found", []))
    related = "".join(f'<li><a href="{URL(x["u"])}">{ESC(x["t"])}</a></li>' for x in f.get("related", []))
    maps = f'<p><a class="t" href="{URL(f["maps"])}">Open in Google Maps</a></p>' if f.get("maps") else ""
    prev_, next_ = by.get(f.get("prev")), by.get(f.get("next"))
    plink = lambda g: flink(g["slug"], up) if HOSTED else g["slug"] + ".html"
    glyphs = json.dumps(canon["cmap"][:4000] if canon else [])
    acc = "".join(f'<div class="acc"><h3>{h}</h3><p>{xlink(a[k], f, up, k == "use")}</p></div>' for k, h in (("what", "The typeface"), ("history", "History"), ("use", "In use"), ("notes", "Notes")) if a.get(k))
    if not acc:
        acc = f'<div class="acc"><p>{ESC(f.get("summary",""))}</p></div>'
    n_st, n_gl = (set_count(f) or [len(faces)])[0], f.get("glyphs", 0)
    fpills = [("fa", f["family"]), ("g", f["genre"]), ("st", f'{n_st} style{"s" if n_st != 1 else ""}'), ("gl", f"{n_gl} characters")] + [("tg", t) for t in f.get("tags", [])]
    seen = set()   # one pill per value: a genre equal to the family, or a tag repeating a fact, is shown once
    fpills = [(k, v) for k, v in fpills if v and not (v.lower() in seen or seen.add(v.lower()))]
    pills = "".join(f'<a class="tg" href="{up}index.html#{k}={urllib.parse.quote(v)}">{ESC(v)}</a>' for k, v in fpills if v)
    lic = lic_name(f.get("font_license"))
    facts = (f'<div class="lic">{f"<p>{ESC(lic)}</p>" if lic else ""}<p class="tags">{pills}</p></div>'
             + (f'<ul class="chips">{chips}</ul>' if chips else ""))   # licence → linked small pills → feature chips
    secs = [("specimen", "Specimen")] + ([("set", f"Set of {set_n}")] if ms else []) + [("timeline", "Font history"), ("account", "Account"), ("place", "Place"), ("characters", "Characters"), ("files", "Files")]
    has_place = bool(photo or found or related or maps)
    subnav = (f'<span class="pname">{ESC(f["name"])}</span><span class="secs"><span class="crumb">{ESC(f["family"])}</span>'
              + "".join(f'<a href="#{k}">{l}</a>' for k, l in secs if (k != "place" or has_place) and (k != "timeline" or f["events"]))
              + '</span>')   # on phone the pills scroll under the name, which stays
    has_bold = any("bold" in x["short"].lower() for _, x in (ms or []))
    def style_label(x):
        sh = x["short"]
        plain = sh in ("Regular", "Normal") or x["name"] == f["name"]   # the face with no style of its own
        if plain:
            return "Regular" if has_bold else f["name"]   # Regular beside a Bold (Okay, 28 Oct 2026), else the font's name
        return sh
    styles = [(i, style_label(x)) for i, x in ms] if ms else []   # a font that comes alone has no style pills
    stylenav = ('<span class="styles">' + "".join(f'<button type="button" data-i="{i}"{" class=on aria-pressed=true" if i == 0 else " aria-pressed=false"}>{ESC(l)}</button>' for i, l in styles) + '</span>'
                + '<span class="pnav">'
                + (f'<a href="{plink(prev_)}">{ARROW_L}{ESC(prev_["name"])}</a>' if prev_ else "")
                + (f'<a href="{plink(next_)}">{ESC(next_["name"])}{ARROW_R}</a>' if next_ else "") + '</span>')
    body = f"""
<article class="font" data-slug="{f['slug']}" data-pal="{f['pal']}">
<template id="subnavtpl">{subnav}</template>
<template id="stylenavtpl">{stylenav}</template>
<script type="application/json" id="faces">{JSON(faces)}</script>
<script type="application/json" id="glyphs">{glyphs}</script>
<div class="sheet" id="specimen">
  <div class="blocks{' text' if f['text'] else ' display'}" id="blocks">{specimen_blocks(f, faces)}</div>
  <div class="tools" role="toolbar" aria-label="Specimen controls">
    <div class="sliders">
      <label class="sl"><span class="k">Size</span><output id="szo" class="tnum">128</output><input type="range" id="sz" min="8" max="400" value="128"></label>
      <label class="sl"><span class="k">Leading</span><output id="lho" class="tnum">1.10</output><input type="range" id="lh" min="0.7" max="2" step="0.01" value="1.1"></label>
      <label class="sl"><span class="k">Tracking</span><output id="tro" class="tnum">0</output><input type="range" id="tr" min="-0.1" max="0.4" step="0.005" value="0"></label>
    </div>
  </div>
</div>
{sec(set_label, set_html, "set") if ms else ""}
{sec("Font history", strip_html(f), "timeline") if f["events"] else ""}
{sec("Account", f'<div class="acc-wrap">{acc}</div><p class="orig"><a class="t" href="{URL(f["translate"])}">Read Wiegel’s original in English</a> <a class="t" href="{URL(f["url"])}">Original German page</a></p>', "account")}
{sec("Facts", facts, "facts")}
{sec("Place", photo + f'<div class="placecol">{maps}{f"<h3>Seen elsewhere</h3><ul class=links>{found}</ul>" if found else ""}{f"<h3>Related</h3><ul class=links>{related}</ul>" if related else ""}</div>', "place") if has_place else ""}
{sec("Waterfall", '<div class="waterfall" id="wf"></div>') if f["text"] else ""}
{sec('Characters <span class="tnum" id="gcount"></span>', '<div id="gl" class="gl"></div>', "characters")}
{sec("Files", f'<ul class="dl">{dl}</ul>' + (f'<h3>Bundled documents</h3><ul class="dl">{docs}</ul>' if docs else '') + f'<p class="sub">{ESC(f.get("copyright") or "")}</p>', "files")}
<nav class="pn"><a href="{plink(prev_) if prev_ else '#'}" class="{'' if prev_ else 'off'}">{CA("l")}{ESC(prev_['name'] if prev_ else '')}</a><a href="{plink(next_) if next_ else '#'}" class="{'' if next_ else 'off'}">{ESC(next_['name'] if next_ else '')}{CA("r")}</a></nav>
</article>"""
    if fragment:
        return deco(body)
    return page(f"{f['name']} — Wiegel Archive", body, 1, sprite, "fontpage", "index", f["pal"])


# ── links inside the account texts ───────────────────────────────────────────────
# "In use" names character sets and features in prose; each links to the font list filtered by Wiegel's matching button
USE_TERMS = [   # (pattern, filter group, filter value as the index shows it)
    (r"capital (?:sharp s|ß|ẞ)", "ic", "Capital sharp s"),
    (r"polytonic(?: Greek)?", "ic", "Polytonic Greek"),
    (r"Greek", "ic", "Greek"),
    (r"Cyrillic", "ic", "Cyrillic"),
    (r"[Ee]uro(?! ?\d)", "ic", "Euro sign"),
    (r"(?:large )?extended (?:set|Latin)", "ic", "Extended Latin"),
    (r"long s", "cv", "Long s"),
    (r"UNZ-?1", "ic", "UNZ1 encoding"),
    (r"OpenType", "ic", "OpenType features"),
    (r"Kurrent", "ic", "Kurrent"),
    (r"[Rr]unes?", "ic", "Runes"),
]
_XRX = None


def xlink(text, f, up, use=False):
    """Account text as HTML: other fonts of the archive named in it link to their page; in "In use", feature words
    link to the font list filtered by that feature. First mention per paragraph; names quoted from crawled titles stay plain."""
    global _XRX, _NAMES
    if _XRX is None:   # one pattern for the whole build; longest names first, so "Erikas Büro" wins over "Erika"
        _NAMES = sorted(((x["name"], x["slug"]) for x in json.load(open(os.path.join(DATA, "catalog.json"), encoding="utf-8"))["fonts"]), key=lambda t: -len(t[0]))
        parts = [f"(?P<n{i}>{re.escape(n)})" for i, (n, _) in enumerate(_NAMES)] + [f"(?P<t{i}>{rx})" for i, (rx, _, _) in enumerate(USE_TERMS)]
        _XRX = re.compile(r"(?<![\w'‘’-])(?:" + "|".join(parts) + r")(?![\w'’-])")
    out, pos, seen = [], 0, set()
    for m in _XRX.finditer(text):
        g = m.lastgroup
        if g in seen:
            continue
        if g[0] == "n":
            name, slug = _NAMES[int(g[1:])]
            if slug == f["slug"] or name == f["name"]:
                continue
            href = flink(slug, up)
        else:
            if not use:
                continue
            _, k, v = USE_TERMS[int(g[1:])]
            href = f"{up}index.html#{k}={urllib.parse.quote(v)}"
        seen.add(g)
        words = ESC(m.group(0)).rsplit(" ", 1)   # the last word travels with the arrow, as in deco()
        head = words[0] + " " if len(words) == 2 else ""
        out.append(ESC(text[pos:m.start()]) + f'<a class="xl" href="{href}">{head}<span class="nw">{words[-1]}{CA("r")}</span></a>')
        pos = m.end()
    return "".join(out) + ESC(text[pos:])


def legend_block():
    items = "".join(f'<li>{icon(c, 48)}<div><h3>{ESC(l)}</h3><p>{ESC(d)}</p></div></li>' for c, (_, l, d) in ICONS.items())
    return f"""<section class="prose" id="legend"><h2>Legend</h2>
<p>Wiegel marked every font with small green buttons for its character set and features. Here they are redrawn as line chips in the page’s own colour, at the one line thickness, with the mark cut from the archive’s own type and centred on its ink.</p></section>
<ul class="legend">{items}</ul>"""


def legend_html(sprite):
    return page("Legend — Wiegel Archive", legend_block(), 0, sprite, "legend", "about", sub="legend")


PEOPLE = os.path.join(STATIC, "people")
REFS = [   # (title, url, site · what it is)
    ("CAT Fonts", "http://www.peter-wiegel.de/", "peter-wiegel.de · his site, also at catfonts.de"),
    ("Curriculum vitae", "http://www.peter-wiegel.de/Vitae.html", "peter-wiegel.de · his CV, as PDF"),
    ("Peter Wiegel", "https://www.typografie.info/3/Personen/wiki.html/peter-wiegel-r746/", "Typografie.info · person entry"),
    ("Catfonts-Archiv", "https://www.typografie.info/3/files/file/90-catfonts-archiv/", "Typografie.info · backup of the whole collection, 2024"),
    ("CAT Design Wolgast", "https://luc.devroye.org/fonts-47415.html", "Luc Devroye · type design information page"),
    ("Peter Wiegel", "https://www.klingspor-museum.de/KlingsporKuenstler/Schriftdesigner/Wiegel/PWiegel.pdf", "Klingspor Museum · specimen of his fonts, PDF"),
    ("Peter Wiegel", "https://fontsinuse.com/foundry/182/peter-wiegel", "Fonts In Use · his fonts in use"),
    ("Feroniapi", "https://velvetyne.fr/fonts/feroniapi/", "Velvetyne · Julienne Richard’s redesign of his Feronia, 2025"),
]


def copy_people(out):
    d = os.path.join(out, "assets/people"); os.makedirs(d, exist_ok=True)
    for x in os.listdir(PEOPLE):
        shutil.copy2(os.path.join(PEOPLE, x), d)


def about_html(cat, sprite):
    """About · Peter Wiegel: who he is, the licences, references"""
    refs = "".join(f'<li><a href="{ESC(u)}">{ESC(t)}</a><span class="sub">{ESC(w)}</span></li>' for t, u, w in REFS)
    body = f"""<section class="prose">
<figure class="photo portrait"><img src="assets/people/wiegel.png" width="174" height="215" alt="Peter Wiegel"><figcaption><span class="sub">Photo: peter-wiegel.de</span></figcaption></figure>
<h2>Peter Wiegel</h2>
<p>Born in Hamburg in 1955, Peter Wiegel trained as a car mechanic, studied mechanical engineering at the Fachhochschule Hamburg and worked for years as a laboratory technician in plastics engineering and as a design engineer. From 2002 he worked freelance as an illustrator and web designer in Wolgast, on the Baltic coast, and from 2008 he built his own foundry, CAT Fonts.</p>
<p>A self-described typographic amateur, he made several hundred free typefaces into the 2020s: most of them revivals of German foundry type, school and handwriting models, standardised lettering (DIN, TGL, railway drawings) and lettering recorded from real objects. His site says that since 2022 he has been unable to maintain it for health reasons; it stays online as it is. In 2024 Typografie.info put a backup of the whole collection online, and in 2025 Velvetyne published Feroniapi, a redesign of his Feronia.</p>
<h2>Licences</h2>
<p>Wiegel’s own designs are freeware, commercial use included; modified versions must stay free and take a new name. A large group of blackletter fonts on the second index page are re-encodings of Dieter Steffmann’s digitisations — free for private use; commercial use needs Steffmann’s licence. Each font page shows the licence note from Wiegel’s page and the licence embedded in the font file; the original archives, with their licence files, are kept untouched under Files.</p>
<h2>References</h2>
<ul class="links">{refs}</ul>
</section>"""
    return page("Peter Wiegel — Wiegel Archive", body, 0, sprite, "about", "about", sub="about")


def site_html(cat, sprite):
    """About · This site: the intention in one paragraph, then the colours and the colophon"""
    n = len(cat["fonts"])
    sw = "".join(f'<li><span class="chip-c" style="--b:{v[0]};--f:{v[1]}">Aa</span><span>{ESC(v[2])}</span><span class="sub tnum">{v[0]} / {v[1]}</span></li>' for v in USE_PAL.values())
    body = f"""<section class="prose">
<h2>This site</h2>
<p>A private archive of Peter Wiegel’s free typefaces, made to read, set and compare them in one place, the way a foundry shows its library. Each of the {n} fonts has a live specimen set from the font file itself, an English write-up of Wiegel’s page, the dated history of the original lettering and its digitisation, photographs of the objects it came from, its character set and the original downloads. All of it is generated from Wiegel’s index pages and the font files by one small script; nothing here is an image of type.</p>
<h2>Colour</h2>
<p>The specimen colours are Wiegel’s own, sampled from his site’s stylesheet, banner, buttons and specimen scans. Each family draws from a few of them; every font page lets you switch. Each pair is set light paper on dark ink, with no light repeated; I in the colour picker inverts them all. His green, olive, magenta and crimson grounds are left out because they fight the download green of the feature chips; the lights and darks that are not on his site are shades of his colours.</p>
<ul class="pal">{sw}</ul>
<h2>Colophon</h2>
<p>Interface in Wiegel’s Preussische IV 44, the 1880s Prussian railway lettering that DIN 1451 grew out of, at a single size, with its small capitals for every label; reading text in his Proletarsk. Built {datetime.date.today().isoformat()}.</p>
</section>"""
    return page("This site — Wiegel Archive", body, 0, sprite, "site", "about", sub="site")


UIFONTS = []


def mono_face(by):
    """Erika Type's bold face, the one monospaced text of the site."""
    return next((x for x in (by.get(UI_MONO) or {}).get("faces", []) if x["weight"] >= 700 and not x["italic"]), None)


def ui_font_css(by):
    css = []
    x = mono_face(by)
    if x:
        src = "fonts/" + UI_MONO + "/" + os.path.basename(x["path"])
        UIFONTS.append({"family": "WA Mono", "src": "assets/" + src, "weight": 400, "italic": False})
        css.append(f'@font-face{{font-family:"WA Mono";src:url("{src}");font-display:swap}}')
    for x in ui_faces(by, os.path.join(SITE, "assets")):
        UIFONTS.append(x)
        src = x["src"][len("assets/"):]
        css.append(f'@font-face{{font-family:"{x["family"]}";src:url("{src}");font-weight:{x["weight"]};font-style:{"italic" if x["italic"] else "normal"};font-display:swap}}')
    return "\n".join(css)


def ui_faces(by, assets):
    """WA UI and WA Text: the site's own copies of Preussische IV 44 and Proletarsk (kerned, Turkish added; see
    tools/uifonts.py), written to assets/fonts/ui/. The specimen pages and downloads keep Wiegel's originals."""
    import uifonts
    srcs = {}
    for slug in (UI_DISPLAY, UI_TEXT):
        faces = (by.get(slug) or {}).get("faces", [])
        if faces and os.path.exists(os.path.join(ROOT, faces[0]["path"])):
            srcs[slug] = os.path.join(ROOT, faces[0]["path"])
        else:
            log(f"ui fonts: {slug} has no font file here; WA {'UI' if slug == UI_DISPLAY else 'Text'} falls back to the system face")
    made = uifonts.make(srcs, os.path.join(assets, "fonts", "ui"))
    return [{"family": fam, "src": "assets/fonts/ui/" + os.path.basename(path), "weight": 400, "italic": False}
            for fam, (path, n) in sorted(made.items(), key=lambda kv: kv[0] != "WA Text")]   # WA Text first, as before


def load_files(cat):
    """Extract from raw/archives; without them (dev copy) reuse the file lists of the last full build."""
    if os.path.isdir(RAW) and os.listdir(RAW):
        extract(cat)
        return
    rep = {r["slug"]: r for r in json.load(open(os.path.join(DATA, "build-report.json"), encoding="utf-8"))}
    for f in cat["fonts"]:
        r = rep.get(f["slug"], {})
        f["files"] = [dict(x) for x in r.get("files", [])]   # paths plus the metadata of the last full build (used when a font file is absent)
        f["docs"], f["downloads"] = r.get("docs", []), r.get("downloads", [])
    log("extract: skipped (no raw archives), file lists from build-report.json")


def prepare():
    cat = json.load(open(os.path.join(DATA, "catalog.json"), encoding="utf-8"))
    load_files(cat)
    inventory(cat)
    enrich(cat)
    return cat


def main():
    cat = prepare()
    by = {f["slug"]: f for f in cat["fonts"]}
    # site tree
    for d in ("assets/fonts", "assets/dl", "assets/docs", "assets/photos", "font"):
        os.makedirs(os.path.join(SITE, d), exist_ok=True)
    for f in cat["fonts"]:
        for x in f.get("faces", []):
            d = os.path.join(SITE, "assets/fonts", f["slug"]); os.makedirs(d, exist_ok=True)
            if os.path.exists(os.path.join(ROOT, x["path"])):   # absent in a copy without the font folder
                web_font(os.path.join(ROOT, x["path"]), os.path.join(d, os.path.basename(x["path"])))
        for dd in f.get("downloads", []):
            if dd["local"] and os.path.exists(os.path.join(RAW, dd["local"])):
                shutil.copy2(os.path.join(RAW, dd["local"]), os.path.join(SITE, "assets/dl", dd["local"]))
        for d in f.get("docs", []):
            dd = os.path.join(SITE, "assets/docs", f["slug"]); os.makedirs(dd, exist_ok=True)
            if os.path.exists(os.path.join(ROOT, d["path"])):
                shutil.copy2(os.path.join(ROOT, d["path"]), dd)
    place_photos(cat)
    copy_people(SITE)
    sprite = icon_svgs(cat)
    css = open(os.path.join(STATIC, "app.css"), encoding="utf-8").read().replace("/*UI_FONTS*/", ui_font_css(by))
    open(os.path.join(SITE, "assets/app.css"), "w", encoding="utf-8").write(css)
    shutil.copy2(os.path.join(STATIC, "app.js"), os.path.join(SITE, "assets/app.js"))
    shutil.copy2(os.path.join(STATIC, "blank.woff2"), os.path.join(SITE, "assets/blank.woff2"))
    write_catalog_js(cat)
    W = lambda p, s: open(os.path.join(SITE, p), "w", encoding="utf-8").write(s)
    W("index.html", index_html(cat, sprite))
    W("catalogue.html", catalogue_html(cat, sprite))
    W("timeline.html", timeline_html(cat, sprite))
    W("images.html", images_html(cat, sprite, os.path.join(SITE, "assets", "photos")))
    W("legend.html", legend_html(sprite))
    W("about.html", about_html(cat, sprite))
    W("site.html", site_html(cat, sprite))
    for f in cat["fonts"]:
        W(f"font/{f['slug']}.html", font_html(f, by, sprite))
    # build report
    json.dump([{k: v for k, v in f.items() if k not in ("account",)} | {"faces": [{k2: v2 for k2, v2 in x.items() if k2 != "cmap"} for x in f.get("faces", [])]}
               for f in cat["fonts"]], open(os.path.join(DATA, "build-report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    nofont = [f["slug"] for f in cat["fonts"] if not f.get("faces")]
    log(f"pages: {len(cat['fonts'])} fonts; faces: {sum(len(f.get('faces', [])) for f in cat['fonts'])}; without usable font: {len(nofont)} {nofont[:30]}")


if __name__ == "__main__":
    main()
