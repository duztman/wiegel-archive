"""Drafts data/ui-kern.json, the kerning of the two interface copies (tools/uifonts.py applies it).

1. Build both copies without kerning (Turkish letters, spacing and ligatures in place).
2. halfkern (Behdad Esfahbod, Apache-2.0; default settings, which apply half of a measured negative kern) measures
   every pair of André Fuchs's ranked list (MIT; 24 languages including Turkish) plus every letter against quotes and
   punctuation. Only negative values are kept: in these faces the positive ones came from descenders and accents that
   tuck under a neighbour without touching it (Proletarsk j, Preussische î).
3. Preussische: Wiegel's own 186 pairs replace the drafts for those pairs. Proletarsk: his 6 pairs are dropped
   (o–x and z–e pulled letters together by 6% of the em).
4. Okay's corrections (ADJUST), applied to the drafted values by measuring the ink gap of each pair.
Usage: python3 tools/uikern.py fonts HALFKERN_DIR KERNING_PAIRS_DIR   (clones of behdad/halfkern, andre-fuchs/kerning-pairs)
"""
import json, os, subprocess, sys, tempfile, unicodedata
from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import DecomposingRecordingPen

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import uifonts

ROUND = "acdegoqs"   # lowercase with a round (or s-shaped) left side
# Okay, 28 Oct 2026, on proof 1: "r with round shapes need to be a little closer, with Ys and Ts as well".
# "A little" is 15% (RULES.md): each listed pair's narrowest ink gap shrinks by 15%.
ADJUST = [("proletarsk", "r", ROUND, 0.15), ("preussische", "r", ROUND, 0.15),   # proof 2: "rs also too far apart" (Preussische)
           ("proletarsk", "TY", ROUND, 0.15), ("preussische", "TY", ROUND, 0.15)]


DRAFT = r"""
import sys, json
sys.path.insert(0, sys.argv[4])
import kern_pair as K, cairoft
font, pairs, out = sys.argv[1:4]
K.FONT_FACE = cairoft.create_cairo_font_face_for_file(font, 0)
K.HB_FONT = K.create_hb_font(font)
cmap, upem = K.HB_FONT.face.unicodes, K.HB_FONT.face.upem
lo, hi = K.find_s()
res = {}
for p in json.load(open(pairs)):
    if any(ord(c) not in cmap for c in p): continue
    l = K.create_blurred_surface_for_text_cached(p[0]); r = K.create_blurred_surface_for_text_cached(p[1])
    if l is None or r is None: continue
    k, _ = K.kern_pair(l, r, lo, hi, blurred=True)
    if k: res[p] = round(k / K.FONT_SIZE * upem)
json.dump(res, open(out, "w"))
"""


def draft(font, pairs, halfkern):
    """halfkern in its own process per font: it keeps the font and its calibration in module globals."""
    d = tempfile.mkdtemp()
    pj, oj = os.path.join(d, "pairs.json"), os.path.join(d, "out.json")
    json.dump(pairs, open(pj, "w"))
    subprocess.run([sys.executable, "-I", "-c", DRAFT, font, pj, oj, halfkern], check=True)
    return json.load(open(oj))


def pair_list(fuchs):
    ranked = [p for p in json.load(open(os.path.join(fuchs, "result", "relevant_kerning_raw.json"))) if " " not in p]
    extra = []
    for p in ranked:
        for a, b in (("'", "’"), ('"', "”")):
            if a in p:
                extra.append(p.replace(a, b))
    for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzÇĞİÖŞÜçğıöşü":
        extra += [c + q for q in "’‘“”'\""] + [q + c for q in "’‘“”'\""] + [c + p for p in ".,:;)-"] + [p + c for p in "(-"]
    return list(dict.fromkeys(ranked + extra))


def extents(font):
    """Per glyph: {y: (leftmost x, rightmost x)} of the ink on scanlines every 8 units."""
    gs = font.getGlyphSet()
    cache = {}

    def of(name):
        if name in cache:
            return cache[name]
        pen = DecomposingRecordingPen(gs)
        gs[name].draw(pen)
        segs, cur, start = [], None, None
        for op, args in pen.value:
            if op == "moveTo":
                cur = start = args[0]
            elif op == "lineTo":
                segs.append((cur, args[0])); cur = args[0]
            elif op == "qCurveTo":
                pts = [cur] + list(args)
                if args[-1] is None:
                    pts = pts[:-1] + [pts[1]]
                on = [pts[0]]
                for i in range(1, len(pts) - 2):   # implied on-curve points
                    on.append(((pts[i][0] + pts[i + 1][0]) / 2, (pts[i][1] + pts[i + 1][1]) / 2))
                on.append(pts[-1])
                for i in range(len(on) - 1):
                    a, c, b = on[i], pts[i + 1], on[i + 1]
                    prev = a
                    for t in (j / 8 for j in range(1, 9)):
                        q = ((1 - t) ** 2 * a[0] + 2 * t * (1 - t) * c[0] + t * t * b[0], (1 - t) ** 2 * a[1] + 2 * t * (1 - t) * c[1] + t * t * b[1])
                        segs.append((prev, q)); prev = q
                cur = pts[-1]
            elif op in ("closePath", "endPath"):
                if cur and start and cur != start:
                    segs.append((cur, start))
                cur = None
        ext = {}
        for (x0, y0), (x1, y1) in segs:
            if y0 == y1:
                continue
            for y in range(int(min(y0, y1)) // 8 * 8, int(max(y0, y1)) + 1, 8):
                if min(y0, y1) <= y < max(y0, y1):
                    x = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
                    a, b = ext.get(y, (x, x))
                    ext[y] = (min(a, x), max(b, x))
        cache[name] = ext
        return ext
    return of


def gap(font, of, l, r, k):
    cm = font.getBestCmap()
    nl, nr = cm[ord(l)], cm[ord(r)]
    adv = font["hmtx"][nl][0]
    el, er = of(nl), of(nr)
    ys = set(el) & set(er)
    return min(adv - el[y][1] + k + er[y][0] for y in ys) if ys else None


def main(fonts, halfkern, fuchs):
    srcs = {}
    for slug in uifonts.FAMILY:
        d = os.path.join(fonts, slug)
        srcs[slug] = os.path.join(d, sorted(x for x in os.listdir(d) if x.lower().endswith((".ttf", ".otf")))[0])
    tmp = tempfile.mkdtemp()
    built = uifonts.make(srcs, tmp, kerning=False)
    pairs = pair_list(fuchs)
    out = {"_note": "Kerning of the interface copies in font units, drafted by tools/uikern.py (see its docstring: halfkern over "
                    "André Fuchs's ranked pairs, negative values only, Wiegel's own Preussische pairs kept, Okay's corrections "
                    "from ADJUST). Rerun uikern.py rather than editing by hand; hand edits are lost on the next draft."}
    for slug, fam in uifonts.FAMILY.items():
        path = built[fam][0]
        values = {p: v for p, v in draft(path, pairs, halfkern).items() if v < 0}
        if slug == "preussische":
            w = TTFont(srcs[slug])
            rev = {}
            for u, n in w.getBestCmap().items():
                rev.setdefault(n, chr(u))
            values.update({rev[a] + rev[b]: v for (a, b), v in w["kern"].kernTables[0].kernTable.items() if a in rev and b in rev})
        font = TTFont(path)
        cm = font.getBestCmap()
        of = extents(font)
        base = lambda c: unicodedata.normalize("NFD", c)[0]
        for face, lefts, rights, share in ADJUST:
            if face != slug:
                continue
            for u in cm:
                for l in lefts:
                    r = chr(u)
                    if not r.islower() or base(r) not in rights:
                        continue
                    k = values.get(l + r, 0)
                    g = gap(font, of, l, r, k)
                    if g and g > 0:
                        values[l + r] = round(k - share * g)
        out[slug] = dict(sorted(values.items()))
        print(slug, len(values), "pairs")
    json.dump(out, open(uifonts.KERN, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main(*sys.argv[1:4])
