"""The two interface faces, as copies made for this site only (WA UI, WA Text).

Wiegel's originals stay untouched for the specimen pages and downloads. The copies get:
- Preussische IV 44 (WA UI): Ğ ğ İ Ş ş built from Wiegel's own parts (breve from Й/й, dot from i, cedilla from Ç/ç);
  ’ ‘ “ ” lowered to the band of his straight quotes (x-height to cap height); sidebearings centred
  (he set every letter flush left, all its space on the right).
- both: kerning from data/ui-kern.json (Wiegel's own pairs kept, the rest drafted with halfkern and reviewed),
  written as GPOS; the legacy kern table is dropped.
- Proletarsk (WA Text): İ redrawn with the dot of his i (his own İ has the dot under the letter).
build.py and hosted.py call make(); by hand: python3 tools/uifonts.py fonts OUT_DIR
"""
import json, os, sys, unicodedata
from fontTools.ttLib import TTFont
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.boundsPen import ControlBoundsPen
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAMILY = {"preussische": "WA UI", "proletarsk": "WA Text"}   # build.UI_DISPLAY, build.UI_TEXT
KERN = os.path.join(ROOT, "data", "ui-kern.json")
MARKS = os.path.join(ROOT, "data", "ui-marks.json")   # the cedilla, cut once from Wiegel's Ç/ç (see its _note)


def _contours(gs, name):
    """A glyph's contours as recorded pen calls, one tuple per contour (TrueType: no composites in these faces)."""
    p = RecordingPen()
    gs[name].draw(p)
    out, cur = [], []
    for op, args in p.value:
        cur.append((op, args))
        if op in ("closePath", "endPath"):
            out.append(tuple(cur))
            cur = []
    return out


def _ybox(contours):
    b = ControlBoundsPen(None)
    for c in contours:
        for op, args in c:
            getattr(b, op)(*args)
    return b.bounds[1], b.bounds[3]


def _xmid(contours):
    b = ControlBoundsPen(None)
    for c in contours:
        for op, args in c:
            getattr(b, op)(*args)
    return (b.bounds[0] + b.bounds[2]) / 2


def turkish(f, redraw=()):
    """Ğ ğ İ Ş ş from Wiegel's own parts: the breve of Й/й, the dot of i, the cedilla of Ç/ç. Each mark keeps its
    height, and its place relative to the ink centre of the letter it came from."""
    gs = f.getGlyphSet()
    cm = f.getBestCmap()
    n = lambda c: cm[ord(c)]
    marks = json.load(open(MARKS, encoding="utf-8"))
    made = []

    def mark_of(accented, base):   # the contours of accented wholly above base (the letter inside is not always his plain one)
        top = _ybox(_contours(gs, n(base)))[1]
        return [c for c in _contours(gs, n(accented)) if _ybox([c])[0] > top]

    def cedilla(key):
        return [tuple((op, [tuple(pt) for pt in args]) for op, args in c) for c in marks[key]]

    def build(new, uni, base, mark, mark_from, dy=0):
        if uni in cm and chr(uni) not in redraw:
            return
        if uni in cm:
            new = cm[uni]   # redraw an existing glyph in place, under its own name
        body = _contours(gs, n(base))
        dx = _xmid(body) - _xmid(_contours(gs, n(mark_from)))
        pen = TTGlyphPen(None)
        for c in body:
            for op, args in c:
                getattr(pen, op)(*args)
        tp = TransformPen(pen, (1, 0, 0, 1, dx, dy))   # the mark as separate contours over the letter, as Wiegel draws Ö and Й
        for c in mark:
            for op, args in c:
                getattr(tp, op)(*args)
        g = pen.glyph()
        if new not in f["glyf"].glyphs:
            f.setGlyphOrder(f.getGlyphOrder() + [new])
        f["glyf"][new] = g
        g.recalcBounds(f["glyf"])
        f["hmtx"][new] = (f["hmtx"][n(base)][0], g.xMin)
        for t in f["cmap"].tables:
            if t.isUnicode():
                t.cmap[uni] = new
        made.append(chr(uni))

    need = lambda u: u not in cm or chr(u) in redraw
    if need(0x11E): build("Gbreve", 0x11E, "G", mark_of("Й", "И"), "И")
    if need(0x11F): build("gbreve", 0x11F, "g", mark_of("й", "и"), "и")
    if need(0x130):   # the dot of i, at the height of the dots on Ö
        dot = mark_of("i", "ı")
        dy = _ybox(mark_of("Ö", "O"))[0] - _ybox(dot)[0]
        build("Idotaccent", 0x130, "I", dot, "ı", dy=dy)
    if need(0x15E): build("Scedilla", 0x15E, "S", cedilla("cedilla_uc"), "C")
    if need(0x15F): build("scedilla", 0x15F, "s", cedilla("cedilla_lc"), "c")
    return made


def quotes(f):
    """’ ‘ “ ” down to the band of Wiegel's straight quotes (' and \"): their tops on the cap height."""
    cm = f.getBestCmap()
    glyf = f["glyf"]
    top = glyf[cm[ord("'")]].yMax
    for c in "‘’“”":
        g = glyf[cm[ord(c)]]
        dy = top - g.yMax
        if dy:
            g.coordinates.translate((0, dy))
            g.recalcBounds(glyf)
    return top


def _base(f, name, rev):
    """The glyph whose sidebearings a glyph follows: the base letter of an accented one (À → A, Й → И), else itself."""
    u = rev.get(name)
    if u is None:
        return name
    d = unicodedata.decomposition(chr(u)).split()
    if d and not d[0].startswith("<"):
        b = int(d[0], 16)
        cm = f.getBestCmap()
        if b in cm:
            return cm[b]
    return {"Gbreve": "G", "gbreve": "g", "Idotaccent": "I", "Scedilla": "S", "scedilla": "s"}.get(name, name)


def centre(f):
    """Wiegel set every glyph flush left (left sidebearing 0, all its space on the right). Split that space evenly;
    an accented glyph moves with its base letter so the accent stays put. Advances do not change."""
    glyf, hm = f["glyf"], f["hmtx"]
    rev = {}
    for u, n in f.getBestCmap().items():
        rev.setdefault(n, u)
    shift = {}
    for n in f.getGlyphOrder():
        g = glyf[n]
        if g.numberOfContours:
            adv, lsb = hm[n]
            shift[n] = round((adv - g.xMax - lsb) / 2)
    moved = 0
    for n in f.getGlyphOrder():
        g = glyf[n]
        if not g.numberOfContours or g.isComposite():
            continue
        dx = shift.get(_base(f, n, rev), shift[n])
        if dx:
            g.coordinates.translate((dx, 0))
            g.recalcBounds(glyf)
            hm[n] = (hm[n][0], g.xMin)
            moved += 1
    return moved


def respace(f, rules):
    """Set chosen sides of chosen letters to a sidebearing taken from another of Wiegel's letters.
    rules: {char: (left, right)}, each a (char, side) to copy from, or None to keep. The ink does not move relative to
    the advance's other side; accented forms move with their base letter. Returns {char: (old, new)} for the report."""
    cm = f.getBestCmap()
    glyf, hm = f["glyf"], f["hmtx"]
    side = lambda c, s: hm[cm[ord(c)]][1] if s == "L" else hm[cm[ord(c)]][0] - glyf[cm[ord(c)]].xMax
    plan, report = {}, {}
    for c, (l, r) in rules.items():
        n = cm[ord(c)]
        ol, orr = side(c, "L"), side(c, "R")
        nl = side(*l) if l else ol
        nr = side(*r) if r else orr
        plan[n] = (nl - ol, (nl - ol) + (nr - orr))   # (shift of the ink, change of the advance)
        report[c] = ((ol, orr), (nl, nr))
    rev = {}
    for u, n in cm.items():
        rev.setdefault(n, u)
    for n in f.getGlyphOrder():
        b = _base(f, n, rev)
        if b not in plan:
            continue
        dx, dadv = plan[b]
        g = glyf[n]
        if g.numberOfContours and not g.isComposite():
            g.coordinates.translate((dx, 0))
            g.recalcBounds(glyf)
        adv, _ = hm[n]
        hm[n] = (adv + dadv, g.xMin if g.numberOfContours else 0)
    return report


def ligatures(f, keys):
    """f_i, f_l from data/ui-marks.json (drawn by tools/uidraw.py). Advance: the right letter's ink end plus its own
    right sidebearing, so the ligature takes the respaced ı or l with it. Returns the GSUB rules."""
    marks = json.load(open(MARKS, encoding="utf-8"))
    cm = f.getBestCmap()
    glyf, hm = f["glyf"], f["hmtx"]
    subs = []
    for key in keys:
        m = marks[key]
        pen = TTGlyphPen(None)
        for c in m["contours"]:
            for op, args in c:
                getattr(pen, op)(*[tuple(pt) for pt in args])
        g = pen.glyph()
        r = cm[ord(m["right"])]
        f.setGlyphOrder(f.getGlyphOrder() + [key])
        glyf[key] = g
        g.recalcBounds(glyf)
        rsb = hm[r][0] - glyf[r].xMax
        hm[key] = (g.xMax + rsb, g.xMin)
        typed = key.split("_")[1]   # what is typed: f then i (the drawing uses ı, the i without its dot) or f then l
        subs.append(f"sub {cm[ord('f')]} {cm[ord(typed)]} by {key};")
    return subs


def kern(f, pairs, subs=()):
    """Replace the font's kerning with pairs ({"AV": -60, …}, characters → font units), as a GPOS kern feature."""
    cm = f.getBestCmap()
    lines = []
    for p, v in sorted(pairs.items()):
        if v and len(p) == 2 and all(ord(c) in cm for c in p):
            lines.append(f"pos {cm[ord(p[0])]} {cm[ord(p[1])]} {int(v)};")
    for t in ("kern", "GPOS", "GSUB", "hdmx", "LTSH", "VDMX"):   # the device tables hold per-size advances of the old glyph set
        if t in f:
            del f[t]
    fea = "languagesystem DFLT dflt;\nlanguagesystem latn dflt;\nlanguagesystem cyrl dflt;\nfeature kern {\n" + "\n".join(lines) + "\n} kern;\n"
    if subs:   # fi drops the dot of i, so it reads ı in Turkish: text marked lang="tr" keeps fl only
        fea = fea.replace("languagesystem cyrl dflt;", "languagesystem latn TRK;\nlanguagesystem cyrl dflt;")
        names = []
        for i, rule in enumerate(subs):
            names.append((f"L{i}", " f_i;" in rule))
            fea += f"lookup L{i} {{ {rule} }} L{i};\n"
        use = lambda tr: " ".join(f"lookup {n};" for n, dotless in names if not (tr and dotless))
        fea += f"feature liga {{\n script DFLT; language dflt; {use(False)}\n script latn; language dflt; {use(False)}\n language TRK exclude_dflt; {use(True)}\n}} liga;\n"
    addOpenTypeFeaturesFromString(f, fea)
    return len(lines)


def rename(f, family):
    """A modified copy gets its own name (CC BY and OFL ask that it not pass for the original); the credits stay."""
    nt = f["name"]
    for r in list(nt.names):
        if r.nameID in (1, 3, 4, 6, 16, 17, 21, 22):
            nt.removeNames(nameID=r.nameID)
    ps = family.replace(" ", "")
    for i, s in ((1, family), (2, "Regular"), (3, ps + "-Regular;wiegel-archive"), (4, family), (6, ps + "-Regular")):
        nt.setName(s, i, 3, 1, 0x409)
    note = "Modified for the Wiegel Archive site (kerning, sidebearings, Turkish letters). " + (nt.getDebugName(10) or "")
    nt.setName(note.strip(), 10, 3, 1, 0x409)


# Proletarsk's uneven sides, set from his own n, o, x, t and f (Okay, 28 Oct: "hd, kt too close; k trips up the system").
# Straight stems as n, bowls as o; k's leg as x's; l's tail as t's; t's crossbar as f's; quotes as o's round side.
TEXT_SPACING = {
    "h": (None, ("n", "R")),
    "b": (None, ("o", "R")), "p": (None, ("o", "R")),
    "d": (("o", "L"), None), "q": (("o", "L"), None),
    "k": (None, ("x", "R")),
    "l": (None, ("t", "R")),
    "t": (("f", "L"), None),
    "'": (("o", "L"), ("o", "R")), '"': (("o", "L"), ("o", "R")),
    "‘": (("o", "L"), ("o", "R")), "’": (("o", "L"), ("o", "R")),
    "“": (("o", "L"), ("o", "R")), "”": (("o", "L"), ("o", "R")),
}


def make(srcs, out_dir, kerning=True):
    """srcs: {slug: path of Wiegel's font file}. Writes WA-UI.ttf and WA-Text.ttf; returns {family: (path, pairs)}."""
    data = json.load(open(KERN, encoding="utf-8"))
    os.makedirs(out_dir, exist_ok=True)
    made = {}
    for slug, src in srcs.items():
        family = FAMILY[slug]
        f = TTFont(src, recalcTimestamp=False)
        subs = []
        if slug == "proletarsk":
            turkish(f, redraw="İ")   # Wiegel's İ carries its dot under the I
            respace(f, TEXT_SPACING)
            subs = ligatures(f, ("f_i", "f_l"))
        if slug == "preussische":
            turkish(f)
            quotes(f)
            centre(f)
        n = kern(f, data[slug] if kerning else {}, subs)
        rename(f, family)
        out = os.path.join(out_dir, family.replace(" ", "-") + ".ttf")   # ttf like the other UI faces: no brotli needed on either machine
        f.save(out)
        made[family] = (out, n)
    return made


if __name__ == "__main__":
    srcs = {}
    for slug in FAMILY:
        d = os.path.join(sys.argv[1], slug)
        srcs[slug] = os.path.join(d, sorted(x for x in os.listdir(d) if x.lower().endswith((".ttf", ".otf")))[0])
    for fam, (out, n) in make(srcs, sys.argv[2]).items():
        print(f"{fam}: {n} pairs → {out}")
