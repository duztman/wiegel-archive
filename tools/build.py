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
FONT_EXT = (".ttf", ".otf", ".woff", ".woff2")
DOC_EXT = (".pdf", ".txt", ".rtf", ".doc", ".docx", ".odt", ".htm", ".html")
PUA = range(0xE000, 0xF900)
HOSTED = False   # set by tools/hosted.py: single-shell font pages, original download links

def flink(slug, up=""):
    return f"{up}font.html#{slug}" if HOSTED else f"{up}font/{slug}.html"
WRITTEN = set()   # paths written this run (deletion is disabled in the target folder, so we overwrite instead)
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
        "created": created_year(f),
        "cmap": sorted(c for c in cps if c >= 0x20 and c not in PUA and not 0x7F <= c < 0xA0),
        "coverage": [k for k, _, t in COVERAGE if t(cps)],
    }


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
            m = analyse(os.path.join(ROOT, x["path"]))
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
        canon = uniq[0] if uniq else None
        f["sample"] = sample_for(canon["cmap"]) if canon else ""
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
PALETTE = collections.OrderedDict([
    ("sky",     ("#00A3EA", "#000080", "Banner sky / link navy")),
    ("sun",     ("#FDFA00", "#D40051", "Starburst yellow / crimson")),
    ("olive",   ("#687F12", "#FFFF80", "Active button olive / pale yellow")),
    ("violet",  ("#7C00AD", "#FFFF80", "Button violet / pale yellow")),
    ("magenta", ("#E20084", "#FFFFFF", "Focus magenta / white")),
    ("green",   ("#05872C", "#FFFFFF", "Download green / white")),
    ("indigo",  ("#3B2A98", "#FFFF80", "UNZ indigo / pale yellow")),
    ("tan",     ("#D3BFA4", "#800025", "Specimen paper / oxblood")),
    ("navy",    ("#000080", "#FFFF80", "Navy / pale yellow")),
    ("oxblood", ("#800025", "#D3BFA4", "Oxblood / paper")),
    ("crimson", ("#D40051", "#FFFF80", "Crimson / pale yellow")),
    ("pale",    ("#FFFF80", "#000080", "Pale yellow / navy")),
])
# grounds that clash with Wiegel's download green (#05872C), which the feature chips keep:
# contrast ≤ 1.15 : 1 — green itself, olive, and the complementary magenta and crimson
NO_GREEN = {"green", "olive", "magenta", "crimson"}
USE_PAL = collections.OrderedDict((k, v) for k, v in PALETTE.items() if k not in NO_GREEN)
FAM_PAL = {
    "Blackletter": ["tan", "oxblood", "navy", "pale"],
    "Handwriting": ["pale", "sky", "indigo"],
    "Norm & Sans": ["sun", "sky", "navy"],
    "Serif":       ["oxblood", "tan", "pale"],
    "Display":     ["violet", "sun", "sky", "indigo"],
    "Technical":   ["sun", "navy", "pale"],
    "Symbols":     ["violet", "sky", "indigo"],
    "Other":       ["indigo", "tan", "sky"],
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


def enrich(cat):
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


NAVPAL = {"home": ("#00A3EA", "#000080"), "timeline": ("#FDFA00", "#D40051"), "catalogue": ("#05872C", "#FFFFFF"),
          "legend": ("#687F12", "#FFFF80"), "about": ("#D3BFA4", "#800025"), "images": ("#7C00AD", "#FFFF80"), "fontpage": ("#00A3EA", "#000080")}
NAV = [("index", "Index", "index.html"), ("timeline", "Timeline", "timeline.html"), ("images", "Images", "images.html"), ("catalogue", "Catalogue", "catalogue.html"),
       ("about", "About", "about.html")]


THEME_JS = """(function(){var P=%s,A={dark:["#00A3EA","#FDFA00","#E20084","#2FB35A","#FF3D7F","#B04CFF"],light:["#0079B8","#E20084","#05872C","#D40051","#7C00AD"]},r=document.documentElement,m;
try{m=localStorage.getItem("wa-mode")}catch(e){}r.dataset.mode=m=(m==="mono"?"mono":"random");
var pick=function(a){return a[Math.floor(Math.random()*a.length)]};
window.WA_PAL=P;window.WA_theme=function(pair){var s=r.style;
 if(!pair&&r.dataset.mode==="random"){var c=s.getPropertyValue("--paper"),L=Object.values(P).filter(function(x){return x[0]!==c});pair=pick(L.length?L:Object.values(P))}
 if(pair){s.setProperty("--paper",pair[0]);s.setProperty("--ink",pair[1]);s.setProperty("--hot",pair[1]);r.dataset.on="pair"}
 else{s.removeProperty("--paper");s.removeProperty("--ink");var d=matchMedia("(prefers-color-scheme: dark)").matches;s.setProperty("--hot",pick(d?A.dark:A.light));r.dataset.on="mono"}};
window.WA_theme(window.WA_FONTPAL&&r.dataset.mode==="random"?P[window.WA_FONTPAL]:null)})();"""


def page(title, body, depth=0, sprite="", cls="", cur="", fontpal=""):
    up = "../" * depth
    links = "".join(f'<a class="{"on" if k == cur else ""}" href="{up}{href}"{" aria-current=page" if k == cur else ""}>{label}</a>' for k, label, href in NAV)
    return deco(f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex,nofollow">
<title>{ESC(title)}</title>
<link rel="stylesheet" href="{up}assets/app.css">
<script>window.ROOT="{up}";window.HOSTED={"true" if HOSTED else "false"};window.UIFONTS={json.dumps(UIFONTS)};window.WA_FONTPAL={json.dumps(fontpal)};{THEME_JS % json.dumps({k: v[:2] for k, v in USE_PAL.items()})}</script>
</head><body class="p-{cls}">
{sprite}
<header class="top" id="top">
<nav class="nav1" aria-label="Site"><a class="home" href="{up}index.html">Wiegel Archive</a>{links}<form class="nsearch" role="search" action="{up}index.html"><input class="fin" id="nq" type="search" name="q" autocomplete="off" enterkeyhint="search" placeholder="Search" aria-label="Search the archive"></form><span class="modes"><button class="mode" type="button" data-m="random" title="Colours: a random pair of Wiegel's colours on every page" aria-label="Random colours">R</button><button class="mode" type="button" data-m="mono" title="Colours: black and white with one bright accent" aria-label="Mono colours">M</button><a class="rndfont" href="{up}index.html" id="rndfont" title="Open a random font">Random</a></span></nav>
<nav class="nav2" id="subnav" aria-label="This font"></nav>
</header>
<main>{body}
<footer class="foot"><p class="info">A private archive of the free fonts of Peter Wiegel / CAT Fonts. Fonts © their authors, under the licences bundled in each archive. Texts are new English write-ups; the originals are at <a href="http://www.peter-wiegel.de/">peter-wiegel.de</a>.</p></footer>
</main>
<script src="{up}assets/catalog.js"></script><script src="{up}assets/app.js"></script>
</body></html>""")


def fonts_css_entry(f, i, x, up):
    src = up + "assets/fonts/" + f["slug"] + "/" + os.path.basename(x["path"])
    return {"id": f"wa-{f['slug']}-{i}", "src": src, "style": x["style"], "weight": x["weight"], "italic": x["italic"], "glyphs": x["chars"], "feats": x["feats"], "full": x["full"]}


def write_catalog_js(cat):
    rows = []
    for f in cat["fonts"]:
        faces = [fonts_css_entry(f, i, x, "") for i, x in enumerate(f.get("faces", []))]
        rows.append({
            "s": f["slug"], "n": f["name"], "no": f["no"], "fa": f["family"], "g": f["genre"], "e": f.get("decade"),
            "y": f.get("oy"), "dy": f.get("dy"), "sec": f["section"], "p": f["pos"], "of": f["of"],
            "ic": f["icons"], "cv": f.get("coverage", []), "sm": f.get("sample", ""), "gl": f.get("glyphs", 0),
            "st": len(faces), "f": faces[:1], "sum": f.get("summary", ""), "pl": f.get("place"), "ph": bool(f.get("photo")),
            "tg": f.get("tags", []), "pal": f["pal"],
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
  <section class="homelist" aria-label="Typefaces"><p class="fcount"><span class="info" id="count"></span><button type="button" class="pill small" id="fclear" hidden>Clear</button></p><div id="grid" class="grid list" aria-live="polite"></div>
  <footer class="foot"><p class="info">A private archive of the free fonts of Peter Wiegel / CAT Fonts. Fonts © their authors, under the licences bundled in each archive. Texts are new English write-ups; the originals are at <a href="http://www.peter-wiegel.de/">peter-wiegel.de</a>.</p></footer></section>
  <aside class="side" aria-label="Filter">
    <div class="sidehead"><textarea class="fin settext" id="retype" rows="2" autocomplete="off" spellcheck="false" placeholder="Write here to change texts" aria-label="Type text to set every name"></textarea>
    <div class="picked" id="picked" aria-label="Selected filters"></div></div>
    <details id="fdet" open><summary class="fsum">Filters <svg class="ca pm" viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="8.6" vector-effect="non-scaling-stroke"/><path d="M5.6 10H14.4" vector-effect="non-scaling-stroke"/><path class="v" d="M10 5.6V14.4" vector-effect="non-scaling-stroke"/></svg></summary>
    <div class="frow2"><input class="fin" id="q" type="search" autocomplete="off" placeholder="Search" aria-label="Search names, places, tags"><label for="q" class="sic" aria-hidden="true"><svg viewBox="0 0 24 24" width="22" height="22"><circle cx="10" cy="10" r="6.5" vector-effect="non-scaling-stroke"/><path d="M15 15l5.5 5.5" vector-effect="non-scaling-stroke"/></svg></label></div>
    <div id="fside"></div>
    </details>
    <p class="info about-l">{len(fonts)} typefaces and {n_faces} styles by Peter Wiegel, digitised {min(dys)} to {max(dys)} from type, signs and handwriting dated {min(oys)} to {max(oys)}.</p>
  </aside>
</div>
"""
    return page("Wiegel Archive", body, 0, sprite, "home", "index")


def timeline_html(cat, sprite):
    ev = collections.defaultdict(lambda: collections.defaultdict(list))
    for f in cat["fonts"]:
        for e in f["events"]:
            ev[e["y"]][e["lane"]].append((f, e))
    years = sorted(ev)
    # decade overview
    dec = collections.Counter()
    for y in years:
        d = y // 10 * 10 if y >= 1800 else (y // 100 * 100)
        dec[d] += sum(len(v) for v in ev[y].values())
    mx = max(dec.values())
    first_y = {}
    for y in years:
        d = y // 10 * 10 if y >= 1800 else (y // 100 * 100)
        first_y.setdefault(d, y)
    scale = "".join(f'<a href="#y{first_y[d]}" class="dec" style="--h:{max(6, round(100 * n / mx))}%"><i></i><span class="tnum">{d}{"s" if d < 1800 else ""}</span></a>' for d, n in sorted(dec.items()))
    rows = []
    for y in years:
        cells = []
        for k, _ in LANES:
            items = []
            for f, e in ev[y][k]:
                face = f["faces"][0] if f.get("faces") else None
                src = ("assets/fonts/" + f["slug"] + "/" + os.path.basename(face["path"])) if face else ""
                if e.get("auto"):
                    items.append(f'<a class="ev auto" href="{flink(f["slug"])}" data-s="{f["slug"]}"><span class="fn" data-src="{src}">{ESC(f["name"])}</span></a>')
                else:
                    items.append(f'<a class="ev" href="{flink(f["slug"])}" data-s="{f["slug"]}"><span class="fn" data-src="{src}">{ESC(f["name"])}</span><span class="w">{ESC(e["what"])}</span></a>')
            cells.append(f'<div class="lane l-{k}" data-lane="{dict(LANES)[k]}">{"".join(items)}</div>')
        rows.append(f'<div class="tl-row" id="y{y}"><div class="tl-y tnum">{y}</div>{"".join(cells)}</div>')
    n_ev = sum(len(f["events"]) for f in cat["fonts"])
    body = f"""
<section class="intro">
  <p class="lead">{n_ev} dated events across {len(years)} years. <em>Type</em>: when the original letters were cut, cast, drawn or standardised. <em>Digitised</em>: when the font file was made, read from the file itself. <em>Elsewhere</em>: the buildings, signs and lives around them. Point at a name to see where else it appears.</p>
  <nav class="scale" aria-label="Jump to decade">{scale}</nav>
</section>
<section class="tl" id="tl">
  <div class="tl-head"><span></span>{"".join(f'<span>{l}</span>' for _, l in LANES)}</div>
  {"".join(rows)}
</section>"""
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
    return page("Catalogue — Wiegel Archive", body, 0, sprite, "catalogue", "catalogue")


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
            '<path d="M5.6 10H14M10.6 6.6L14 10L10.6 13.4" vector-effect="non-scaling-stroke"/></svg>')
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
        return f'<a{a}>{inner}{CA(d)}</a>'
    return _LINK.sub(one, html)


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
        if up_: blocks.append(("Capitals", 160, up_, "fit"))
        if lo_ and lo_.upper() != up_ or (lo_ and "gemeine" in f["icons"]): blocks.append(("Lowercase", 160, lo_, "fit"))
        if dg_: blocks.append(("Figures", 160, dg_ + " " + "".join(ch for ch in "&?!€§" if ord(ch) in c), "fit"))
        if f.get("sample") and f["sample"] not in (up_, lo_, f["name"]): blocks.append(("Sample", 160, f["sample"], "fit"))
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
    items = "".join(f'<li class="l-{e["lane"]}"><span class="y tnum">{e["y"]}</span><span class="w">{ESC(e["what"])}</span><span class="ln">{dict(LANES)[e["lane"]]}</span></li>' for e in evs)
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
    icons = "".join(f'<li>{icon(c, 24)}<span>{ESC(ICONS[c][1])}</span></li>' for c in f["icons"] if c in ICONS)
    styles = "".join(f'<option value="{i}">{ESC(x["style"])}</option>' for i, x in enumerate(faces))
    feats = "".join(f'<label class="feat"><input type="checkbox" value="{t}"{" checked" if t in ("liga", "calt", "kern") else ""}><span>{t}</span></label>'
                    for t in f.get("feats", []) if re.match(r"^(liga|dlig|calt|salt|ss\d\d|swsh|smcp|c2sc|onum|lnum|tnum|frac|hist|kern|cv\d\d|zero)$", t))
    sw = "".join(f'<button type="button" class="sw{" on" if k == f["pal"] else ""}" data-p="{k}" style="--b:{v[0]};--f:{v[1]}" title="{ESC(v[2])}" aria-label="{ESC(v[2])}"></button>' for k, v in USE_PAL.items())
    sw += '<button type="button" class="sw plain" data-p="plain" title="Paper / ink" aria-label="Paper and ink"></button>'
    dl = "".join(
        f'<li><a href="{up}assets/dl/{urllib.parse.quote(d["local"])}" download>{ESC(d["name"])}</a><span class="sub tnum">{ESC(d["kind"])}{" · " + format(d["bytes"] / 1024, ".0f") + " KB" if d["bytes"] else ""}</span></li>'
        if d["local"] and not HOSTED else f'<li><a href="{ESC(d["src"])}">{ESC(d["name"])}</a><span class="sub">original link</span></li>'
        for d in f.get("downloads", []))
    docs = "" if HOSTED else "".join(f'<li><a href="{up}assets/docs/{f["slug"]}/{urllib.parse.quote(os.path.basename(d["path"]))}">{ESC(os.path.basename(d["path"]))}</a></li>' for d in f.get("docs", []))
    ph = f.get("photo")
    photo = ""
    if ph:
        photo = (f'<figure class="photo"><img src="{up}assets/photos/{f["slug"]}.jpg" alt="{ESC(ph.get("caption",""))}" loading="lazy" '
                 f'onerror="this.onerror=null;this.src=\'{ESC(ph["src"])}\'"><figcaption><span>{ESC(ph.get("caption",""))}</span>'
                 f'<span class="sub">Photo: {ESC(ph.get("author",""))} · {ESC(ph.get("license",""))} · <a href="{ESC(ph.get("page",""))}">source</a></span></figcaption></figure>')
    found = "".join(f'<li><a href="{ESC(x["u"])}">{ESC(x.get("t") or x.get("site",""))}</a><span class="sub">{ESC(x.get("site",""))}{" — " + ESC(x["note"]) if x.get("note") else ""}</span></li>' for x in f.get("found", []))
    related = "".join(f'<li><a href="{ESC(x["u"])}">{ESC(x["t"])}</a></li>' for x in f.get("related", []))
    maps = f'<p><a class="t" href="{ESC(f["maps"])}">Open in Google Maps</a></p>' if f.get("maps") else ""
    prev_, next_ = by.get(f.get("prev")), by.get(f.get("next"))
    plink = lambda g: flink(g["slug"], up) if HOSTED else g["slug"] + ".html"
    meta_rows = [("Number", nofmt(f["no"])), ("Family", f["family"]), ("Genre", f["genre"]), ("Original", str(f["oy"]) if f.get("oy") else None),
                 ("Digitised", f'{f["dy"]} by {f["dwho"]}' if f.get("dy") else None), ("Source", f.get("origin")), ("Place / object", f.get("place")),
                 ("Designer field", f.get("designer")), ("Styles", str(len(faces))), ("Characters", f'{f.get("glyphs",0):,}'),
                 ("Licence (page)", f.get("license")), ("Licence (font file)", (f.get("font_license") or "")[:240]),
                 ("Wiegel's index", f'{f["section"]}, {f["pos"]} of {f["of"]}')]
    meta = "".join(f'<div{" class=wide" if len(v) > 34 else ""}><dt>{ESC(k)}</dt><dd>{ESC(v)}</dd></div>' for k, v in meta_rows if v)
    glyphs = json.dumps(canon["cmap"][:4000] if canon else [])
    acc = "".join(f'<div class="acc"><h3>{h}</h3><p>{ESC(a[k])}</p></div>' for k, h in (("what", "The typeface"), ("history", "History"), ("use", "In use"), ("notes", "Notes")) if a.get(k))
    if not acc:
        acc = f'<div class="acc"><p>{ESC(f.get("summary",""))}</p></div>'
    tags = "".join(f'<span class="tg">{ESC(t)}</span>' for t in f.get("tags", []))
    secs = [("specimen", "Specimen"), ("timeline", "Timeline"), ("account", "Account"), ("place", "Place"), ("characters", "Characters"), ("files", "Files")]
    has_place = bool(photo or found or related or maps)
    subnav = (f'<span class="pname">{ESC(f["name"])}</span><span class="crumb">{ESC(f["family"])}</span>'
              + "".join(f'<a href="#{k}">{l}</a>' for k, l in secs if (k != "place" or has_place) and (k != "timeline" or f["events"]))
    )
    pnav = ('<nav class="pnav" aria-label="Previous and next font">'
            + (f'<a href="{plink(prev_)}">{ARROW_L}{ESC(prev_["name"])}</a>' if prev_ else "")
            + (f'<a href="{plink(next_)}">{ESC(next_["name"])}{ARROW_R}</a>' if next_ else "") + '</nav>')
    years_lbl = f" {CA()} ".join(str(x) for x in (f.get("oy"), f.get("dy")) if x)
    body = f"""
<article class="font" data-slug="{f['slug']}" data-pal="{f['pal']}">
<template id="subnavtpl">{subnav}</template>
<script type="application/json" id="faces">{json.dumps(faces)}</script>
<script type="application/json" id="glyphs">{glyphs}</script>
<div class="sheet" id="specimen">
  {pnav}
  <div class="blocks{' text' if f['text'] else ' display'}" id="blocks">{specimen_blocks(f, faces)}</div>
  <div class="tools" role="toolbar" aria-label="Specimen controls">
    <div class="sliders">
      <label class="sl"><span class="k">Size</span><output id="szo" class="tnum">128</output><input type="range" id="sz" min="8" max="400" value="128"></label>
      <label class="sl"><span class="k">Leading</span><output id="lho" class="tnum">1.10</output><input type="range" id="lh" min="0.7" max="2" step="0.01" value="1.1"></label>
      <label class="sl"><span class="k">Tracking</span><output id="tro" class="tnum">0</output><input type="range" id="tr" min="-0.1" max="0.4" step="0.005" value="0"></label>
    </div>
    <div class="opts">
      {f'<label>Style <select id="style">{styles}</select></label>' if len(faces) > 1 else ''}
      {f'<span class="feats">{feats}</span>' if feats else ''}
      <span class="sws" role="group" aria-label="Colours from Wiegel's site">{sw}</span>
      <button type="button" id="invert" class="t">Invert</button>
      <button type="button" id="reset" class="t">Reset</button>
    </div>
  </div>
  <header class="fhead">
    <p class="kicker info tnum"><span>{nofmt(f['no'])}</span><span>{ESC(f['family'])}</span><span>{years_lbl}</span></p>
    <ul class="icons-row">{icons}</ul>
  </header>
</div>
{sec("Timeline", strip_html(f), "timeline") if f["events"] else ""}
{sec("Account", f'<div class="acc-wrap">{acc}</div><p class="orig"><a class="t" href="{ESC(f["translate"])}">Read Wiegel’s original in English</a> <a class="t" href="{ESC(f["url"])}">Original German page</a></p>', "account")}
{sec("Facts", f'<dl class="facts">{meta}</dl>' + (f'<div class="tags">{tags}</div>' if tags else ''))}
{sec("Place", photo + f'<div class="placecol">{maps}{f"<h3>Seen elsewhere</h3><ul class=links>{found}</ul>" if found else ""}{f"<h3>Related</h3><ul class=links>{related}</ul>" if related else ""}</div>', "place") if has_place else ""}
{sec("Waterfall", '<div class="waterfall" id="wf"></div>') if f["text"] else ""}
{sec('Characters <span class="tnum" id="gcount"></span>', '<div id="gl" class="gl"></div>', "characters")}
{sec("Files", f'<ul class="dl">{dl}</ul>' + (f'<h3>Bundled documents</h3><ul class="dl">{docs}</ul>' if docs else '') + f'<p class="sub">{ESC(f.get("copyright") or "")}</p>', "files")}
<nav class="pn"><a href="{plink(prev_) if prev_ else '#'}" class="{'' if prev_ else 'off'}">{CA("l")}{ESC(prev_['name'] if prev_ else '')}</a><a href="{plink(next_) if next_ else '#'}" class="{'' if next_ else 'off'}">{ESC(next_['name'] if next_ else '')}{CA("r")}</a></nav>
</article>"""
    if fragment:
        return deco(body)
    return page(f"{f['name']} — Wiegel Archive", body, 1, sprite, "fontpage", "index", f["pal"])


def legend_block():
    items = "".join(f'<li>{icon(c, 48)}<div><h3>{ESC(l)}</h3><p>{ESC(d)}</p></div></li>' for c, (_, l, d) in ICONS.items())
    return f"""<section class="prose" id="legend"><h2>Legend</h2>
<p>Wiegel marked every font with small green buttons for its character set and features. Here they are redrawn as line chips in the page’s own colour, at the one line thickness, with the mark cut from the archive’s own type and centred on its ink.</p></section>
<ul class="legend">{items}</ul>"""


def legend_html(sprite):
    """the legend now lives on the About page; this keeps old links working"""
    return '<!doctype html><meta charset="utf-8"><title>Legend — Wiegel Archive</title><meta http-equiv="refresh" content="0;url=about.html#legend"><a href="about.html#legend">Legend</a>'


def about_html(cat, sprite):
    n = len(cat["fonts"])
    sw = "".join(f'<li><span class="chip-c" style="--b:{v[0]};--f:{v[1]}">Aa</span><span>{ESC(v[2])}</span><span class="sub tnum">{v[0]} / {v[1]}</span></li>' for v in USE_PAL.values())
    body = f"""<section class="intro"><p class="lead">A working archive of the free typefaces of Peter Wiegel, built for reading, setting and comparing them.</p></section>
<section class="prose">
<h2>Peter Wiegel</h2>
<p>A self-described typographic amateur from Hamburg, later based in Wolgast, Peter Wiegel built CAT Fonts from the late 2000s into the 2020s: several hundred free typefaces, most of them revivals of German foundry type, school and handwriting models, standardised lettering (DIN, TGL, railway drawings) and lettering recorded from real objects. His site says that since 2022 he has been unable to maintain it for health reasons; it stays online as it is.</p>
<h2>Licences</h2>
<p>Wiegel’s own designs are freeware, commercial use included; modified versions must stay free and take a new name. A large group of blackletter fonts on the second index page are re-encodings of Dieter Steffmann’s digitisations — free for private use; commercial use needs Steffmann’s licence. Each font page shows the licence note from Wiegel’s page and the licence embedded in the font file; the original archives, with their licence files, are kept untouched under Files.</p>
<h2>This archive</h2>
<p>{n} typefaces scraped with Apify from all three of Wiegel’s index pages. The texts are new English write-ups of each page — facts regrouped, not translations — with a link to the original and to a machine translation of it. Photos of the buildings, signs and objects are freely licensed and credited; other sightings are linked, not copied. Specimens are set live from the font files; nothing here is an image of type. Digitisation years are read from each font file’s copyright line, or its creation date when that is missing.</p>
<h2>Colour</h2>
<p>The specimen colours are Wiegel’s own, sampled from his site’s stylesheet, banner, buttons and specimen scans. Each family draws from a few of them; every font page lets you switch. Grounds that fight his download green — the green itself, olive, magenta and crimson — are left out, so the feature chips always read.</p>
<ul class="pal">{sw}</ul>
<h2>Method</h2>
<p>Planned with the Elephant–Goldfish model: one long-context design session wrote <code>docs/designs/archive.md</code>; stateless reviewers attacked it before code was written. Version 3 followed a study of Lineto, Grilli Type, Optimo, Herzog &amp; de Meuron, Klim, Commercial Type, Radim Peško, Caruso St John and others: one interface size, a persistent tag menu, lanes for time, colour grounds for type.</p>
<h2>Colophon</h2>
<p>Interface in Wiegel’s Preussische IV 44, the 1880s Prussian railway lettering that DIN 1451 grew out of, at a single size, with its small capitals for every label; reading text in his Proletarsk. Built {datetime.date.today().isoformat()}.</p>
</section>
{legend_block()}"""
    return page("About — Wiegel Archive", body, 0, sprite, "about", "about")


UIFONTS = []


def ui_font_css(by):
    css = []
    for slug, fam in ((UI_TEXT, "WA Text"), (UI_DISPLAY, "WA UI")):
        f = by.get(slug)
        for x in (f or {}).get("faces", []):
            src = "fonts/" + slug + "/" + os.path.basename(x["path"])
            UIFONTS.append({"family": fam, "src": "assets/" + src, "weight": x["weight"], "italic": x["italic"]})
            css.append(f'@font-face{{font-family:"{fam}";src:url("{src}");font-weight:{x["weight"]};font-style:{"italic" if x["italic"] else "normal"};font-display:swap}}')
    return "\n".join(css)


def load_files(cat):
    """Extract from raw/archives; without them (dev copy) reuse the file lists of the last full build."""
    if os.path.isdir(RAW) and os.listdir(RAW):
        extract(cat)
        return
    rep = {r["slug"]: r for r in json.load(open(os.path.join(DATA, "build-report.json"), encoding="utf-8"))}
    for f in cat["fonts"]:
        r = rep.get(f["slug"], {})
        f["files"] = [{k: v for k, v in x.items() if k in ("path", "orig", "sha1", "from")} for x in r.get("files", [])]
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
            shutil.copy2(os.path.join(ROOT, x["path"]), d)
        for dd in f.get("downloads", []):
            if dd["local"] and os.path.exists(os.path.join(RAW, dd["local"])):
                shutil.copy2(os.path.join(RAW, dd["local"]), os.path.join(SITE, "assets/dl", dd["local"]))
        for d in f.get("docs", []):
            dd = os.path.join(SITE, "assets/docs", f["slug"]); os.makedirs(dd, exist_ok=True)
            shutil.copy2(os.path.join(ROOT, d["path"]), dd)
    place_photos(cat)
    sprite = icon_svgs(cat)
    css = open(os.path.join(STATIC, "app.css"), encoding="utf-8").read().replace("/*UI_FONTS*/", ui_font_css(by))
    open(os.path.join(SITE, "assets/app.css"), "w", encoding="utf-8").write(css)
    shutil.copy2(os.path.join(STATIC, "app.js"), os.path.join(SITE, "assets/app.js"))
    write_catalog_js(cat)
    W = lambda p, s: open(os.path.join(SITE, p), "w", encoding="utf-8").write(s)
    W("index.html", index_html(cat, sprite))
    W("catalogue.html", catalogue_html(cat, sprite))
    W("timeline.html", timeline_html(cat, sprite))
    W("images.html", images_html(cat, sprite, os.path.join(SITE, "assets", "photos")))
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
