#!/usr/bin/env python3
"""Hosted copy of the Wiegel Archive for viewing away from the Mac.

Same pages and data as tools/build.py, packed to fit a static host's file limit:
- font pages are one shell (font.html#slug) that loads its body from pages/pN.json
- one style per font (the canonical face); every style stays in the local build
- downloads link to the original archives on peter-wiegel.de
- photos are resized to 1600px

Writes hosted/ next to site/. Run after tools/build.py has extracted the fonts.
"""
import io, json, os, re, shutil, sys
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


def main():
    B.HOSTED = True
    cat = B.prepare()
    for f in cat["fonts"]:
        f["faces"] = f.get("faces", [])[:1]
    by = {f["slug"]: f for f in cat["fonts"]}
    os.makedirs(OUT, exist_ok=True)
    for d in ("assets/fonts", "assets/photos", "pages"):
        os.makedirs(os.path.join(OUT, d), exist_ok=True)

    # fonts: canonical face only, plus every UI face
    keep = {(f["slug"], os.path.basename(x["path"])): x["path"] for f in cat["fonts"] for x in f["faces"]}
    full = json.load(open(os.path.join(B.DATA, "catalog.json"), encoding="utf-8"))
    for f in full["fonts"]:
        if f["slug"] in (B.UI_TEXT, B.UI_DISPLAY, B.UI_DIN):
            for name in os.listdir(os.path.join(B.FONTS, f["slug"])):
                if name.lower().endswith(B.FONT_EXT):
                    keep[(f["slug"], name)] = os.path.join("fonts", f["slug"], name)
    for (slug, name), path in keep.items():
        d = os.path.join(OUT, "assets/fonts", slug)
        os.makedirs(d, exist_ok=True)
        shutil.copy2(os.path.join(B.ROOT, path), os.path.join(d, name))

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
    for slug, fam in ((B.UI_TEXT, "WA Text"), (B.UI_DISPLAY, "WA UI"), (B.UI_DIN, "WA DIN")):
        for name in sorted(os.listdir(os.path.join(OUT, "assets/fonts", slug))):
            B.UIFONTS.append({"family": fam, "src": f"assets/fonts/{slug}/{name}",
                              "weight": 700 if re.search(r"(bold|fett|_g\b|-b\b)", name, re.I) else 400,
                              "italic": bool(re.search(r"(italic|kursiv)", name, re.I))})

    sprite = B.icon_svgs(cat)
    css = open(os.path.join(B.STATIC, "app.css"), encoding="utf-8").read().replace("/*UI_FONTS*/", "")
    open(os.path.join(OUT, "assets/app.css"), "w", encoding="utf-8").write(css)
    shutil.copy2(os.path.join(B.STATIC, "app.js"), os.path.join(OUT, "assets/app.js"))
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
