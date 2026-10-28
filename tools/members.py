#!/usr/bin/env python3
"""Draft data/members.json: the display names of the fonts inside each multi-font download.

The site shows families by given names (Variété Cabaret, Bold, Italic), not by the font files' own
naming. Run once to draft; the file is then edited by hand and the build reads it. Re-running keeps
every entry that already exists and only drafts new ones.

  python3 tools/members.py            # draft missing entries
  python3 tools/members.py --print    # list what the site will show
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(DATA, "members.json")
STYLE_ORDER = ["Thin", "Light", "Regular", "Normal", "Book", "Medium", "Semibold", "Bold", "Heavy", "Black"]


def repair(s):
    """Mac name records written in Latin-1 read back as MacRoman: 'VarietÈ' -> 'Varieté'. Only when the result is clean."""
    try:
        t = s.encode("mac_roman").decode("latin-1")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s
    return t if t != s and not re.search(r"[\x80-\x9f]", t) else s


def clean(s):
    """Separators and repeats only ('Bold Bold', 'Condensed Condensed'); joined names are fixed by hand in RENAME."""
    w = s.replace("_", " ").split()
    out = []
    for x in w:
        if out and x.lower() == out[-1].lower():
            continue
        out.append(x)
    while len(out) > 1 and out[-1].lower() in ("regular", "normal", "medium"):
        out.pop()
    return " ".join(out)


# hand corrections, 28 Oct 2026: names the site shows (the font files keep their own)
RENAME = {
    ("wiegellatein", "WiegelLateinMedium.ttf"): "Wiegel Latein Medium",
    ("gl-nummernschild", "GL-Nummernschild-Eng.ttf"): "GL Nummernschild Eng", ("gl-nummernschild", "GL-Nummernschild-B-Eng.ttf"): "GL Nummernschild Eng Italic",
    ("gl-nummernschild", "GL-Nummernschild-Mtl.ttf"): "GL Nummernschild Mtl", ("gl-nummernschild", "GL-Nummernschild-B_Mtl.ttf"): "GL Nummernschild Mtl Italic",
    ("typographerfraktur", "TypographerFraktur-Medium_UNZ1.ttf"): "Typographer Fraktur UNZ1", ("typographerfraktur", "TypographerFrakturUNZ1-Medium.ttf"): "Typographer Fraktur UNZ1, second cut",
    ("titillium", "TitilliumMaps29L-1wt.otf"): "Titillium Maps 29L 1",
    ("titillium", "TitilliumText22L-1wt.otf"): "Titillium Text 22L 1",
    ("titillium", "TitilliumMaps29L-250wt.otf"): "Titillium Maps 29L 250",
    ("titillium", "TitilliumText22L-250wt.otf"): "Titillium Text 22L 250",
    ("titillium", "TitilliumMaps29L-400wt.otf"): "Titillium Maps 29L 400",
    ("titillium", "TitilliumText22L-400wt.otf"): "Titillium Text 22L 400",
    ("titillium", "TitilliumMaps29L-600wt.otf"): "Titillium Maps 29L 600",
    ("titillium", "TitilliumText22L-600wt.otf"): "Titillium Text 22L 600",
    ("titillium", "TitilliumMaps29L-800wt.otf"): "Titillium Maps 29L 800",
    ("titillium", "TitilliumText22L-800wt.otf"): "Titillium Text 22L 800",
    ("titillium", "TitilliumMaps29L-999wt.otf"): "Titillium Maps 29L 999",
    ("titillium", "TitilliumText22L-999wt.otf"): "Titillium Text 22L 999",
    ("titillium", "TitilliumTitle20.otf"): "Titillium Title 20",
    ("5by7", "5by7light.ttf"): "5by7 Light", ("baltic", "Baltic_Belt.ttf"): "Fehmarn Belt",
    ("beroga", None): {"Beroga Fettig Bold": "Beroga Fettig"}, ("casasans", None): {"Casa Sans Fettig Bold": "Casa Sans Fettig"},
    ("fundamental", None): {"Fundamental Brigade Scvhlank": "Fundamental Brigade Schlank"},
    ("men-nefer", None): {"Men Nefer Black Bold": "Men Nefer Black"},
    ("mutterkrause", None): {"Mutter Krause Halbfett Bold": "Mutter Krause Halbfett", "Mutter Krause Buch Bold": "Mutter Krause Buch"},
    ("leipzig", None): {"Leipzig Fraktur Heavy Extra Bold": "Leipzig Fraktur Heavy", "Leipzig Fraktur Heavy ExtraBold": "Leipzig Fraktur Heavy"},
    ("nathan", None): {"Nathan Alternates Condensed": "Nathan Alternates Condensed", "Nathan Alternates-Semi-expanded Semi-expanded": "Nathan Alternates Semi-expanded",
                       "Nathan Expandet Expanded": "Nathan Expanded", "Nathan Semi Expandet Semi-expanded": "Nathan Semi-expanded",
                       "Nathan Alternates Expanded Expanded": "Nathan Alternates Expanded", "Nathan Condensed Condensed": "Nathan Condensed",
                       "Nathan Alternates Condensed Condensed": "Nathan Alternates Condensed"},
    ("mainzerfraktur", None): {"Bertholdr Mainzer Fraktur": "Berthold Mainzer Fraktur"},
    ("maass", None): {"Maassslicer": "Maass Slicer", "Maassslicer3 D": "Maass Slicer 3D", "Maassslicer3D": "Maass Slicer 3D"},
    ("preussischevi9", None): {"Schattern von Preussische VI 9": "Preussische VI 9 Schatten B"},
    ("5by7", None): {"5by7light": "5by7 Light"}, ("schraubenkiste", None): {"Schraubenkiste2": "Schraubenkiste 2"},
    ("mutterkrause", None): {"Mutter Krause Halbfett Bold": "Mutter Krause Halbfett", "MutterKrauseBuch Bold": "Mutter Krause Buch", "MutterKrauseBuch": "Mutter Krause Buch"},
    ("humboldt", None): {"HumboldtFrakturUNZ1A": "Humboldt Fraktur UNZ1A", "HumboldtFrakturUNZ1L": "Humboldt Fraktur UNZ1L", "HumboldtFrakturUNZ1L Italic": "Humboldt Fraktur UNZ1L Italic"},
    ("centreclaws", None): {"CentreClaws": "Centre Claws", "CentreClawsBeam1": "Centre Claws Beam 1", "CentreClawsSlant": "Centre Claws Slant"},
    ("doergon", None): {"DoergonBackshift": "Doergon Backshift"},
    ("ronaldsongothic", None): {"RonaldsonGothic": "Ronaldson Gothic", "RonaldsonGothicLicht": "Ronaldson Gothic Licht"},
    ("makushka", None): {"MakushkaKontura": "Makushka Kontura", "MakushkaQuadriga": "Makushka Quadriga"},
    ("kaufhalle", None): {"kaufhalle blech": "Kaufhalle Blech", "kaufhalle": "Kaufhalle"},
    ("vis-a-vis", None): {"ViaAVis Bold": "Via-A-Vis Bold"},
    ("titillium", None): {}, ("fetteunz", None): {"Fette classic UNZ Fraktur": "Fette Classic UNZ Fraktur"},
    ("bienchen", None): {"Bienchen SAS OpenType": "Bienchen SAS OpenType"},
}
OTHER = {("alpha54", "Beta54"), ("imran", "Simple Print"), ("rundgotisch", "Tyskland45"), ("tyskland45", "Austria45"), ("variete", "Barnroof")}
FIRST = {"variete": "Variete.ttf", "kleinsemmeringhofstaetten": None, "rundgotisch": None}
ORDER = {"titillium": ["Maps 29L 1", "Maps 29L 400", "Maps 29L 800", "Maps 29L 999", "Text 22L 1", "Text 22L 250", "Text 22L 400", "Text 22L 600", "Text 22L 800", "Text 22L 999", "Title"], "kleinsemmeringhofstaetten": ["Kleinsemmering", "Hofstaetten"], "verfont": ["Hundert", "Zweihundert", "Dreihundert", "Vierhundert"], "verfont2": ["Hundert", "Zweihundert", "Dreihundert"]}


def words(s):
    return s.replace("-", " ").split()


def draft(entry):
    faces = entry.get("faces", [])
    fam = [repair(x.get("family") or "") for x in faces]
    styles = [repair(x.get("style") or "Regular") for x in faces]
    files = [os.path.basename(x["path"]) for x in faces]
    if len(set(fam)) == 1:   # one design in several weights / italics
        kind = "styles"
        names = [("Regular" if s.lower() in ("", "normal") else s) for s in styles]
        short = names
    else:                    # several designs under one name
        kind = "collection"
        base = words(repair(entry["name"]))
        names, short = [], []
        for f, s in zip(fam, styles):
            full = clean(f + ("" if s in ("Regular", "Normal", "normal", "") else " " + s))
            w = words(full)
            k = 0
            while k < min(len(w), len(base)) and w[k].lower() == base[k].lower():
                k += 1
            names.append(full)
            short.append(" ".join(w[k:]) or full)
    mem = []
    slug = entry["slug"]
    for i, (fl, n, sh, x) in enumerate(zip(files, names, short, faces)):
        fix = RENAME.get((slug, fl)) or RENAME.get((slug, None), {})
        n = fix if isinstance(fix, str) else fix.get(n, n)
        if kind == "collection":
            base = words(repair(entry["name"]))
            w = words(n); k = 0
            while k < min(len(w), len(base)) and w[k].lower() == base[k].lower():
                k += 1
            sh = " ".join(w[k:]) or n
        m = {"file": fl, "name": n, "short": sh}
        if (slug, n) in OTHER:
            m["other"] = True   # a different design that came in the same download (e.g. Barnroof in Variété)
        mem.append(m)
    if kind == "styles":
        rank = lambda m, x: (x.get("italic", False), STYLE_ORDER.index(m["name"].split()[0]) if m["name"].split()[0] in STYLE_ORDER else 5, x.get("weight", 400))
        order = sorted(range(len(mem)), key=lambda i: rank(mem[i], faces[i]))
        mem = [mem[i] for i in order]
    else:
        main = [m for m in mem if not m.get("other")]
        first = [m for m in main if m["file"] == FIRST.get(slug)] or main[:1]
        rest = [m for m in main if m is not first[0]]
        if slug in ORDER:
            rk = lambda m: next((i for i, w in enumerate(ORDER[slug]) if w in m["name"]), 99)
            first, rest = [], sorted(main, key=lambda m: (rk(m), m["name"]))
        else:
            rest.sort(key=lambda m: m["name"].lower())
        mem = first + rest + [m for m in mem if m.get("other")]
    dup = [m["name"] for m in mem if [x["name"] for x in mem].count(m["name"]) > 1]
    if dup:
        print(f"members: {slug}: same name twice, fix by hand: {sorted(set(dup))}")
    return {"kind": kind, "members": mem}


def main():
    rep = json.load(open(os.path.join(DATA, "build-report.json"), encoding="utf-8"))
    have = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    for e in rep:
        if len(e.get("faces", [])) > 1 and e["slug"] not in have:
            have[e["slug"]] = draft(e)
    have = dict(sorted(have.items()))
    if "--print" in sys.argv:
        for s, v in have.items():
            print(f"{s:24} {v['kind']:10} " + " · ".join(m["name"] + (" [other]" if m.get("other") else "") for m in v["members"]))
        return
    json.dump(have, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"members: {len(have)} entries in {os.path.relpath(OUT, ROOT)}")


if __name__ == "__main__":
    main()
