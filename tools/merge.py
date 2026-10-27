#!/usr/bin/env python3
"""Merge extraction slices + photo research into data/catalog.json.

Order, section and prev/next come from Wiegel's own index pages, not from agent output.
"""
import json, glob, re, os, urllib.parse, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data")

FAMILY = {
    "fraktur": "Blackletter", "schwabacher": "Blackletter", "textura": "Blackletter", "rotunda": "Blackletter",
    "kurrent": "Handwriting", "school-script": "Handwriting", "script": "Handwriting",
    "din-norm": "Norm & Sans", "sans": "Norm & Sans", "grotesk": "Norm & Sans",
    "serif": "Serif", "slab": "Serif",
    "display": "Display", "decorative": "Display",
    "typewriter": "Technical", "dot-matrix/led": "Technical", "stencil": "Technical", "monoline": "Technical",
    "dingbat": "Symbols",
}
FAMILY_ORDER = ["Blackletter", "Handwriting", "Norm & Sans", "Serif", "Display", "Technical", "Symbols", "Other"]
# a year counts as "the typeface's year" when its note is about the type itself
NOT_TYPE = re.compile(r"\b(born|dies|died|death|founded|firm|company|incorporat|closes|closed|taken over|partnership|joins|classes|birth)\b", re.I)
STRONG = re.compile(r"\b(issu\w*|releas\w*|publish\w*|cut|cast|designs?|designed|drawn|draws|digiti\w*|introduc\w*|appear\w*)\b", re.I)
WEAK = re.compile(r"\b(font|type\w*|face|script|alphabet|letter\w*|sign\w*|plate|standard|DIN|TGL|opened|installed)\b", re.I)


class _TypeYear:
    """search(note) is truthy when a dated note is about the typeface itself; .rank gives priority."""
    @staticmethod
    def rank(note):
        if NOT_TYPE.search(note):
            return 9
        if STRONG.search(note):
            return 0
        if WEAK.search(note):
            return 1
        return 9

    def search(self, note):
        return self.rank(note) < 9


TYPE_YEAR = _TypeYear()
SECTIONS = [
    ("Fonts/index.html", "A–K"),
    ("Fonts/L_bis_Z.html", "L–Z"),
    ("fonts2.html", "Fonts 2"),
]


def norm(u):
    u = (u or "").split("#")[0].strip()
    u = u.replace("https://", "http://")
    return u.lower()


def slugify(url):
    stem = url.split("#")[0].rstrip("/").rsplit("/", 1)[-1]
    stem = re.sub(r"\.html?$", "", stem, flags=re.I)
    s = re.sub(r"[^A-Za-z0-9]+", "-", stem).strip("-").lower()
    return s or "font"


def main():
    recs = [json.loads(l) for f in sorted(glob.glob(os.path.join(D, "parts", "*.jsonl"))) for l in open(f, encoding="utf-8")]
    by_url = {norm(r["url"]): r for r in recs}

    # order from index pages
    order, section_of = [], {}
    for path, label in SECTIONS:
        idx = by_url.get(norm("http://www.peter-wiegel.de/" + path))
        for u in (idx or {}).get("order") or []:
            k = norm(u)
            if k in by_url and k not in section_of:
                section_of[k] = label
                order.append(k)

    fonts = [r for r in recs if r.get("type") == "font"]
    # fonts not reached from an index go last, alphabetically
    rest = sorted((norm(r["url"]) for r in fonts if norm(r["url"]) not in section_of),
                  key=lambda k: by_url[k].get("name", "").lower())
    for k in rest:
        section_of[k] = "Unlisted"
    order += rest

    photos = {}
    for f in ("photos_a.json", "photos_b.json", "photos_c.json"):
        p = os.path.join(D, f)
        if os.path.exists(p):
            for x in json.load(open(p, encoding="utf-8")):
                photos[norm(x["url"])] = x

    out, slugs = [], collections.Counter()
    pos_in = collections.Counter()
    for k in order:
        r = by_url[k]
        if r.get("type") != "font":
            continue
        slug = slugify(r["url"])
        slugs[slug] += 1
        if slugs[slug] > 1:
            slug = f"{slug}-{slugs[slug]}"
        sec = section_of[k]
        pos_in[sec] += 1
        years = sorted({int(y["y"]) for y in r.get("years") or [] if str(y.get("y", "")).isdigit() and 1400 <= int(y["y"]) <= 2026})
        typey = sorted((TYPE_YEAR.rank(y.get("what", "")), int(y["y"])) for y in r.get("years") or []
                       if str(y.get("y", "")).isdigit() and 1400 <= int(y["y"]) <= 2026 and TYPE_YEAR.search(y.get("what", "")))
        key_year = typey[0][1] if typey else (years[0] if years else None)
        ph = photos.get(k, {})
        acc = r.get("account") if isinstance(r.get("account"), dict) else None
        out.append({
            "slug": slug,
            "name": r.get("name") or slug,
            "url": r["url"].split("#")[0],
            "translate": "https://translate.google.com/translate?sl=de&tl=en&u=" + urllib.parse.quote(r["url"].split("#")[0], safe=""),
            "section": sec,
            "pos": pos_in[sec],
            "genre": r.get("genre") or "other",
            "family": FAMILY.get(r.get("genre") or "", "Other"),
            "tags": r.get("tags") or [],
            "years": [{"y": int(y["y"]), "what": y.get("what", "")} for y in r.get("years") or [] if str(y.get("y", "")).isdigit()],
            "year": key_year,
            "decade": (key_year // 10 * 10) if key_year else None,
            "origin": r.get("origin"),
            "place": r.get("place"),
            "license": r.get("license"),
            "summary": r.get("summary", ""),
            "account": acc,
            "icons": r.get("icons") or [],
            "zips": [{"u": z["u"], "k": z.get("k", "")} if isinstance(z, dict) else {"u": z, "k": ""} for z in r.get("zips") or []],
            "photo": ph.get("photo"),
            "found": ph.get("found") or [],
            "related": ph.get("related") or [],
            "maps": ph.get("maps"),
        })

    # prev/next in Wiegel's order
    for i, f in enumerate(out):
        f["prev"] = out[i - 1]["slug"] if i else None
        f["next"] = out[i + 1]["slug"] if i + 1 < len(out) else None

    totals = collections.Counter(f["section"] for f in out)
    for f in out:
        f["of"] = totals[f["section"]]

    json.dump({"families": FAMILY_ORDER, "fonts": out}, open(os.path.join(D, "catalog.json"), "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(len(out), "fonts;", dict(totals), "; with photo:", sum(1 for f in out if f["photo"]),
          "; families:", dict(collections.Counter(f["family"] for f in out)))


if __name__ == "__main__":
    main()
