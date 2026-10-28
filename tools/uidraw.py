"""Draws the few new shapes of the interface faces once, from Wiegel's own outlines, into data/ui-marks.json.

Run by hand when a drawing changes (needs skia-pathops: pip install skia-pathops); build.py and hosted.py only read
the JSON, so neither machine needs a boolean library.
- cedilla_uc / cedilla_lc (Preussische IV 44): the part of his Ç and ç below y=40, for Ş and ş.
- f_i / f_l (Proletarsk): his f arch mirrored about the end of its flat top, so it comes down into the stem of ı or l.
  The f's own sloped terminal goes; its crossbar stays. The right stem keeps ı's or l's own foot (l its tail).
Usage: python3 tools/uidraw.py fonts
"""
import json, os, sys
import pathops
from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.reverseContourPen import ReverseContourPen
from fontTools.pens.transformPen import TransformPen

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "ui-marks.json")


def path(gs, name, m=(1, 0, 0, 1, 0, 0)):
    p = pathops.Path()
    gs[name].draw(TransformPen(p.getPen(), m))
    return p


def box(x0, y0, x1, y1):
    p = pathops.Path(); pen = p.getPen()
    pen.moveTo((x0, y0)); pen.lineTo((x1, y0)); pen.lineTo((x1, y1)); pen.lineTo((x0, y1)); pen.closePath()
    return p


def op(a, b, kind):
    return pathops.op(a, b, kind)


def contours(p):
    """Recorded contours, clockwise as TrueType wants them (pathops winds the other way), integer coordinates."""
    rec = RecordingPen()
    p.draw(ReverseContourPen(rec))
    out, cur = [], []
    for o, a in rec.value:
        cur.append([o, [[round(x), round(y)] for x, y in a]])
        if o in ("closePath", "endPath"):
            out.append(cur); cur = []
    return out


def first(f, folder):
    d = os.path.join(folder)
    return TTFont(os.path.join(d, sorted(x for x in os.listdir(d) if x.lower().endswith((".ttf", ".otf")))[0]))


def main(fonts):
    out = {"_note": "New shapes for the interface copies (tools/uifonts.py), drawn by tools/uidraw.py from Wiegel's outlines; "
                    "font units of the face they belong to. Clockwise contours. Edit by rerunning uidraw.py, not by hand."}
    pr = first(None, os.path.join(fonts, "preussische"))
    gs = pr.getGlyphSet()
    for key, g in (("cedilla_uc", "Ccedilla"), ("cedilla_lc", "ccedilla")):
        out[key] = contours(op(path(gs, g), box(-1000, -1000, 2000, 40), pathops.PathOp.INTERSECTION))

    pl = first(None, os.path.join(fonts, "proletarsk"))
    gs = pl.getGlyphSet()
    cm = pl.getBestCmap()
    g = pl["glyf"]
    xh = pl["OS/2"].sxHeight                       # 1069: where the arch meets the stem
    f = g[cm[ord("f")]]
    co, ends, fl = f.getCoordinates(g)
    top = max(y for x, y in co)
    axis = max(x for (x, y), q in zip(co, fl) if q & 1 and y == top)   # end of the flat top (599): the arch turns here
    stem = sorted({x for (x, y), q in zip(co, fl) if q & 1 and y < 0})  # the f stem's two sides (189, 364)
    body = op(path(gs, "f"), box(-1000, -1000, axis, 3000), pathops.PathOp.INTERSECTION)          # f without its terminal
    arch = op(path(gs, "f"), box(stem[0], xh, axis, 3000), pathops.PathOp.INTERSECTION)            # the quarter arch above x-height
    mirror = path(gs, "f", (-1, 0, 0, 1, 2 * axis, 0))
    arch_r = op(mirror, box(axis, xh, 2 * axis - stem[0], 3000), pathops.PathOp.INTERSECTION)      # the same arch coming down on the right
    right_l = 2 * axis - stem[1]                    # left side of the right stem (834)
    for key, ch in (("f_i", "ı"), ("f_l", "l")):
        n = cm[ord(ch)]
        rco, _, rfl = g[n].getCoordinates(g)
        rx = min(x for (x, y), q in zip(rco, rfl) if q & 1 and y > 0)   # the letter's stem, left side
        leg = op(path(gs, n, (1, 0, 0, 1, right_l - rx, 0)), box(-1000, -1000, 4000, xh + 1), pathops.PathOp.INTERSECTION)
        u = op(op(body, arch_r, pathops.PathOp.UNION), leg, pathops.PathOp.UNION)
        out[key] = {"right": ch, "shift": right_l - rx, "contours": contours(u)}
    json.dump(out, open(OUT, "w"), indent=0)
    print("wrote", OUT, {k: (len(v) if isinstance(v, list) else len(v["contours"])) for k, v in out.items() if k != "_note"})


if __name__ == "__main__":
    main(sys.argv[1])
