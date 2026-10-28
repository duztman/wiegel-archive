#!/usr/bin/env python3
"""Hosted copy of the Wiegel Archive for viewing away from the Mac.

Same pages and data as tools/build.py, packed to fit a static host's file limit:
- font pages are one shell (font.html#slug) that loads its body from pages/pN.json
- one style per font (the canonical face); every style stays in the local build
- downloads link to the original archives on peter-wiegel.de
- photos are resized to 1600px

Writes hosted/ next to site/. Run after tools/build.py has extracted the fonts.
"""
import collections, io, json, os, re, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build as B

OUT = os.path.join(B.ROOT, "hosted")
PACK = 20


def strip_document(html):
    """Main page is wrapped by the host: keep title, metas, styles and body content only."""
    html = re.sub(r"(?is)<!doctype[^>]*>", "", html)
    html = re.sub(r"(?is)</?html[^>]*>|</?head>|</body>", "", html)
    html = re.sub(r"(?is)<body([^>]*)>", r'<div\1 id="page">', html, count=1)
    return html.strip() + "\n</div>"


def web_woff2(slug, x):
    """A set member for the hosted copy, as woff2 bytes: from the font file, or the prepared woff2 in fonts-web/ (a copy without the font folder)."""
    src = os.path.join(B.ROOT, x["path"])
    if os.path.exists(src):
        from fontTools.ttLib import TTFont
        t = TTFont(src, fontNumber=0, recalcTimestamp=False)
        names = t["name"].names
        if sum(len(r.toBytes()) for r in names) > 0xFFFF:
            t["name"].names = [r for r in names if r.platformID != 1]   # as B.web_font: browsers reject name tables over 64 KB
        t.flavor = "woff2"
        b = io.BytesIO(); t.save(b)
        return b.getvalue()
    seed = os.path.join(B.ROOT, "fonts-web", slug, x["web"])
    if os.path.exists(seed):
        return open(seed, "rb").read()
    print(f"hosted: missing member font {slug}/{x['web']}")
    return None


SETS_PER_PACK = 2   # packs are named .woff2 because the artifact host serves only known types; they are not single fonts. The artifact holds at most 511 files: 337 faces + pages + photos leave room for ~60 packs, not 261 member files


def write_pack(dst, items):
    """Several woff2 files in one: a 4-byte little-endian header length, a JSON index {name: [offset, length]}, then the fonts.
    app.js loads 'pack.woff2#name' by slicing it out (loadSrc)."""
    idx, blobs, off = {}, [], 0
    for name, b in items:
        idx[name] = [off, len(b)]; blobs.append(b); off += len(b)
    head = json.dumps(idx, separators=(",", ":")).encode()
    with open(dst, "wb") as o:
        o.write(len(head).to_bytes(4, "little")); o.write(head)
        for b in blobs:
            o.write(b)


def main():
    B.HOSTED = True
    cat = B.prepare()
    n_sets = 0
    for f in cat["fonts"]:
        f["n_styles"] = len(f.get("faces", []))
        if B.members_of(f):   # a set keeps every member, the extra ones as woff2 (a third of the size), packed per two sets (see SETS_PER_PACK)
            k = n_sets // SETS_PER_PACK; n_sets += 1
            for x in f["faces"][1:]:
                x["web"] = os.path.splitext(os.path.basename(x["path"]))[0] + ".woff2"
                x["websrc"] = f"assets/sets/s{k}.woff2#{f['slug']}/{x['web']}"
        else:
            f["faces"] = f.get("faces", [])[:1]
    by = {f["slug"]: f for f in cat["fonts"]}
    os.makedirs(OUT, exist_ok=True)
    for d in ("assets/fonts", "assets/photos", "pages"):
        os.makedirs(os.path.join(OUT, d), exist_ok=True)

    # fonts: the canonical face, every member of a set, every UI face
    keep = {(f["slug"], os.path.basename(x["path"])): x["path"] for f in cat["fonts"] for x in f["faces"] if not x.get("web")}
    packs = collections.defaultdict(list)   # no temporary files and nothing deleted: the Mac's folder does not allow deleting
    for f in cat["fonts"]:
        for x in f["faces"]:
            if x.get("web"):
                b = web_woff2(f["slug"], x)
                file, name = x["websrc"].split("#")
                if b:
                    packs[file].append((name, b))
    os.makedirs(os.path.join(OUT, "assets/sets"), exist_ok=True)
    for file, items in packs.items():
        write_pack(os.path.join(OUT, file), items)
    full = json.load(open(os.path.join(B.DATA, "catalog.json"), encoding="utf-8"))
    for f in full["fonts"]:
        if f["slug"] in (B.UI_TEXT, B.UI_DISPLAY, B.UI_DIN):
            for name in os.listdir(os.path.join(B.FONTS, f["slug"])):
                if name.lower().endswith(B.FONT_EXT):
                    keep[(f["slug"], name)] = os.path.join("fonts", f["slug"], name)
    for (slug, name), path in keep.items():
        d = os.path.join(OUT, "assets/fonts", slug)
        os.makedirs(d, exist_ok=True)
        B.web_font(os.path.join(B.ROOT, path), os.path.join(d, name))

    # photos, smaller
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    src = os.path.join(B.SITE, "assets", "photos")
    for f in cat["fonts"]:
        p = os.path.join(src, f["slug"] + ".jpg")
        if f.get("photo") and os.path.exists(p):
            im = Image.open(p)
            im.thumbnail((1600, 1600))
            im.convert("RGB").save(os.path.join(OUT, "assets/photos", f["slug"] + ".jpg"), "JPEG", quality=82, optimize=True, progressive=True)

    # UI font list for the pages (as build.ui_font_css would collect)
    B.UIFONTS.clear()
    real_by = {f["slug"]: f for f in cat["fonts"]}
    for slug, fam in ((B.UI_TEXT, "WA Text"), (B.UI_DISPLAY, "WA UI")):
        for name in sorted(os.listdir(os.path.join(OUT, "assets/fonts", slug))):
            B.UIFONTS.append({"family": fam, "src": f"assets/fonts/{slug}/{name}",
                              "weight": 700 if re.search(r"(bold|fett|_g\b|-b\b)", name, re.I) else 400,
                              "italic": bool(re.search(r"(italic|kursiv)", name, re.I))})

    mono = B.mono_face(real_by)   # Erika Type Bold for the glyph codes, as woff2
    if mono:
        mx = dict(mono, web=os.path.splitext(os.path.basename(mono["path"]))[0] + ".woff2")
        b = web_woff2(B.UI_MONO, mx)
        if b:
            os.makedirs(os.path.join(OUT, "assets/fonts", B.UI_MONO), exist_ok=True)
            open(os.path.join(OUT, "assets/fonts", B.UI_MONO, mx["web"]), "wb").write(b)
            B.UIFONTS.append({"family": "WA Mono", "src": f"assets/fonts/{B.UI_MONO}/{mx['web']}", "weight": 400, "italic": False})

    sprite = B.icon_svgs(cat)
    css = open(os.path.join(B.STATIC, "app.css"), encoding="utf-8").read().replace("/*UI_FONTS*/", "")
    open(os.path.join(OUT, "assets/app.css"), "w", encoding="utf-8").write(css)
    shutil.copy2(os.path.join(B.STATIC, "app.js"), os.path.join(OUT, "assets/app.js"))
    shutil.copy2(os.path.join(B.STATIC, "blank.woff2"), os.path.join(OUT, "assets/blank.woff2"))
    site_backup = B.SITE
    B.SITE = OUT
    B.write_catalog_js(cat)
    B.SITE = site_backup

    W = lambda p, s: open(os.path.join(OUT, p), "w", encoding="utf-8").write(s)
    home = B.index_html(cat, sprite)
    W("index.html", home)
    W("main.html", strip_document(home))
    W("catalogue.html", B.catalogue_html(cat, sprite))
    W("timeline.html", B.timeline_html(cat, sprite))
    W("images.html", B.images_html(cat, sprite, os.path.join(OUT, "assets", "photos")))
    W("legend.html", B.legend_html(sprite))
    W("about.html", B.about_html(cat, sprite))
    W("site.html", B.site_html(cat, sprite))
    B.copy_people(OUT)
    W("font.html", B.page("Wiegel Archive — Font", '<div id="fontshell"><p class="lead">Loading…</p></div><script>window.PACK=%d</script>' % PACK, 0, sprite, "fontpage", "index"))
    packs = {}
    for i, f in enumerate(cat["fonts"]):
        packs.setdefault(i // PACK, {})[f["slug"]] = B.font_html(f, by, "", up="", fragment=True)
    for k, v in packs.items():
        W(f"pages/p{k}.json", json.dumps(v, ensure_ascii=False, separators=(",", ":")))

    n = sum(len(fs) for _, _, fs in os.walk(OUT))
    size = sum(os.path.getsize(os.path.join(r, x)) for r, _, fs in os.walk(OUT) for x in fs)
    print(f"hosted: {n} files, {size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
