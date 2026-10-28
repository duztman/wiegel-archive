"""Draws the few new shapes of the interface faces once, from Wiegel's own outlines, into data/ui-marks.json.

Run by hand when a drawing changes (needs skia-pathops: pip install skia-pathops); build.py and hosted.py only read
the JSON, so neither machine needs a boolean library.
- cedilla_uc / cedilla_lc (Preussische IV 44): the part of his Ç and ç below y=40, for Ş and ş.
- f_f, f_i, f_l, f_f_i, f_f_l (Proletarsk), as Okay drew them in words on 28 Oct: the f's top runs on over the i
  where its dot was, the dot becoming the bar's round end; the crossbar runs through every f into the top of the i;
  an f before f joins its top to the next f's arch; before l the top runs into the l. The f's sloped terminal goes.
- Germandbls (Preussische): the capital ẞ, from his ß, 7 and Z (see the comment at its code).
- comma (Preussische): the shape of his ‚ (his comma points the other way from his ’ and ‚).
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
    g, hm = pl["glyf"], pl["hmtx"]
    on = lambda ch: [p for p, q in zip(*[g[cm[ord(ch)]].getCoordinates(g)[i] for i in (0, 2)]) if q & 1]
    fpts = on("f")
    top = max(y for x, y in fpts)                                   # 1464
    flat = max(x for x, y in fpts if y == top)                      # 599: end of the flat top, where the terminal starts
    band = sorted({y for x, y in fpts if x == flat})                # the top bar's thickness at its end: 1289..1464
    xmin = min(x for x, y in fpts)
    bar = sorted({y for x, y in fpts if x == xmin})                 # the crossbar: 894..1069
    adv = lambda ch: hm[cm[ord(ch)]][0]
    body = op(path(gs, "f"), box(-1000, -1000, flat, 3000), pathops.PathOp.INTERSECTION)   # f without its sloped terminal

    def stem_left(ch, x0):   # left side of a letter's stem, placed at x0
        return x0 + min(x for x, y in on(ch) if y > 0)

    def lig(word):
        """Okay, 28 Oct: f's top runs on to where the i's dot was (the dot becomes its round end); the crossbar runs
        through every f into the top of the i; an f followed by f joins its top to the next f's arch; fl joins the l's top."""
        x, u, parts = 0, None, []
        for i, ch in enumerate(word):
            nxt = word[i + 1] if i + 1 < len(word) else None
            if ch == "f":
                parts.append(op(body, box(-1000, -1000, 4000, 4000), pathops.PathOp.INTERSECTION) if not x else
                             op(path(gs, "f", (1, 0, 0, 1, x, 0)), box(x - 1000, -1000, x + flat, 3000), pathops.PathOp.INTERSECTION))
                if nxt == "f":
                    parts.append(box(x + flat - 1, band[0], x + adv("f") + flat, band[1]))       # top into the next f's arch
                    parts.append(box(x + xmin, bar[0], x + adv("f") + flat, bar[1]))             # crossbar through
                elif nxt == "i":
                    ix = x + adv("f")
                    parts.append(op(path(gs, cm[ord("i")], (1, 0, 0, 1, ix, 0)), box(-1000, -1000, 9000, 9000), pathops.PathOp.INTERSECTION))   # i with its dot: the dot is the bar's round end
                    dl, dr = ix + min(px for px, py in on("i") if py > bar[1]), ix + max(px for px, py in on("i") if py > bar[1])
                    parts.append(box(x + flat - 1, band[0], (dl + dr) / 2, band[1]))               # top bar on to the dot's centre
                    parts.append(box(x + xmin, bar[0], stem_left("i", ix) + 1, bar[1]))           # crossbar into the i's top
                elif nxt == "l":
                    lx = x + adv("f")
                    parts.append(path(gs, cm[ord("l")], (1, 0, 0, 1, lx, 0)))
                    parts.append(box(x + flat - 1, band[0], stem_left("l", lx) + 1, band[1]))    # top bar into the l
                x += adv(ch)
        u = parts[0]
        for p in parts[1:]:
            u = op(u, p, pathops.PathOp.UNION)
        return u

    for word in ("ff", "fi", "fl", "ffi", "ffl"):
        out["_".join(word)] = {"letters": word, "contours": contours(lig(word))}
    # ẞ (Preussische), Okay 28 Oct: his ß is already cap-height. Kept: its stem with the chamfered top-left corner, and its
    # lower bowl. New, from his own parts: a flat top with a square corner like his 7 and Z, and from that corner a diagonal
    # at his Z's slope and stroke (106 units across), down into the top of the lower bowl.
    gs = pr.getGlyphSet()
    g, cmp_ = pr["glyf"], pr.getBestCmap()
    sz = path(gs, "germandbls")
    co, _, fl = g["germandbls"].getCoordinates(g)
    pts = [p for p, q in zip(co, fl) if q & 1]
    right = max(x for x, y in pts)                       # 367
    capt = max(y for x, y in pts)                        # 735
    stem = min(x for x, y in pts if x > 0 and y == 0)    # 104: the stem's right side
    notch = [p for p in pts if p[0] < right and 400 < p[1] < 500 and p[0] > 300][0]   # (327, 473): where his two bowls meet
    zco, _, zfl = g["Z"].getCoordinates(g)
    zp = [p for p, q in zip(zco, zfl) if q & 1]
    top_in = [p for p in zp if p[1] == max(y for x, y in zp if y < capt) and p[0] > 0][0]   # (209, 630): diagonal leaves the bar
    bar_y = top_in[1]
    low = [p for p in zp if p[1] == min(y for x, y in zp if y > 0) and p[0] > 0][0]        # (105, 105): diagonal reaches the foot
    slope = (top_in[0] - 0) / (bar_y - low[1])           # his Z: x per unit of y along the diagonal
    width = 315 - top_in[0]                              # the diagonal's horizontal stroke in his Z (106)
    flat0 = min(x for x, y in pts if y == capt)          # 157: where his ß's flat top begins, after the chamfered corner
    left_part = op(sz, box(-1000, -1000, flat0, 3000), pathops.PathOp.INTERSECTION)
    bowl = op(sz, box(-1000, -1000, 3000, notch[1]), pathops.PathOp.INTERSECTION)
    top = box(flat0 - 1, bar_y, right, capt)
    yb = notch[1] - (capt - bar_y)                       # the diagonal ends a stroke below the notch, inside the bowl's top
    diag = pathops.Path(); dp = diag.getPen()
    dp.moveTo((right, bar_y)); dp.lineTo((right - width, bar_y))
    dp.lineTo((right - width - slope * (bar_y - yb), yb)); dp.lineTo((right - slope * (bar_y - yb), yb)); dp.closePath()
    u = left_part
    for q in (bowl, top, diag):
        u = op(u, q, pathops.PathOp.UNION)
    out["Germandbls"] = contours(u)
    # Preussische's comma points down to the right; his ’ and ‚ point down to the left. The comma takes the ‚ shape.
    gs = pr.getGlyphSet()
    out["comma"] = contours(path(gs, "quotesinglbase"))
    json.dump(out, open(OUT, "w"), indent=0)
    print("wrote", OUT, sorted(k for k in out if k != "_note"))


if __name__ == "__main__":
    main(sys.argv[1])
