# Wiegel Archive — design spec (EGM Elephant draft)

Status: draft v1 · 2026-10-27 · owner: Okay

## 1. Problem

Peter Wiegel's CAT Fonts site (peter-wiegel.de) hosts ~350 freeware typefaces (fraktur, kurrent, school scripts, DIN/norm lettering, signage revivals, display faces). The site is a 2009-era table layout with ad-blocker nags, PNG specimens and no way to sort, compare or type-test. The goal is a private, local, archival copy that presents the whole body of work as a contemporary specimen site (reference register: Klim, Lineto, Swiss Typefaces) while staying faithful to the source.

Hard constraints
- Runs locally on Okay's Mac: `~/Sites/wiegel-archive`. No server code, no build-time network.
- Shell environments cannot reach peter-wiegel.de; all scraping goes through Apify/Exa (cloud), binaries arrive as one ZIP via a browser download.
- Copyright: fonts are freeware with redistribution allowed (Wiegel's FAQ + bundled OFL/GPL files) → archived in full. Wiegel's prose is not re-published: each font gets an English summary written fresh, plus facts (years, origin, place, features), plus a deep link to the original page and its position in his index. Original specimen PNGs are not copied; specimens are rendered live from the font files.

Non-goals
- Not a public site. Not a mirror of his HTML. No CMS, no framework, no analytics.

## 2. Data model

`data/catalog.json` — array of Font:

```
{
  slug, name, url (source page), section ("A–K" | "L–Z" | "Fonts 2"), index_pos,
  genre (raw), family (grouped, see §3), tags[], years[{y, what}], decade (earliest y),
  origin, place, license, lang, summary (fresh English),
  icons[] (fopro codes), zips[{u, k}], files[{path, format, family, style, glyphs, scripts[], metrics}],
  prev, next, photo {src, author, license, source} | null
}
```

`files[].metrics` is computed at build time with fontTools: unitsPerEm, ascender, descender, capHeight, xHeight, and `ink` = bbox of the specimen string "Hamburgefonstiv" in font units. These drive optical fitting (§5.2).

## 3. Grouping

- family: Blackletter (fraktur, schwabacher, textura, rotunda) · Handwriting (kurrent, school-script, script) · Norm & Sans (din-norm, sans, grotesk) · Serif (serif, slab) · Display (decorative, display) · Technical (typewriter, dot-matrix/led, stencil, monoline) · Symbols (dingbat) · Other.
- era: decade of earliest referenced year (historic source date), "undated" otherwise.
- versions: one font may ship several archives/formats (TTF, OTF with ligatures, UNZ-1 encoded variant); shown as rows under one entry.
- coverage: from fopro icons (Euro, capital ß, Greek, polytonic, Cyrillic, ext. Cyrillic, Irish, runes, long-s) and from the actual cmap.
- place: entries derived from a building/sign/vehicle get a "Found in" annotation and, when Wiegel provides no image, a freely licensed photo (Wikimedia Commons) with author + licence line.

## 4. Pages

- `index.html` — masthead set in a Wiegel norm sans; live counter (fonts, cuts, glyphs); a filterable specimen grid (family, era, coverage chips + text field that retypes every card).
- `catalogue.html` — the table: name · family · era · years · origin · place · formats · coverage icons · source page. Sortable columns, sticky header, tabular figures.
- `fonts/<slug>.html` — one per font:
  1. Hero: name, live editable line, size slider (12–240 px), leading, tracking, style switch if multiple files.
  2. Facts column: summary, origin, years as a mini timeline, place + photo, licence, "On peter-wiegel.de: section · position n of N · original page ↗", prev/next in Wiegel's own order.
  3. Waterfall 12/16/24/36/60/96 px.
  4. Glyph set from the real cmap, grouped by Unicode block; hover enlarges.
  5. Downloads: every archive, with format badge and size.
- `timeline.html` — fonts plotted by source year.
- `legend.html` — the redrawn icon system with Wiegel's meaning restated in English.
- `about.html` — Wiegel's licence terms summarised, archive colophon, method.

## 5. Visual system

5.1 Type
- UI: one of Wiegel's own norm/sans faces (candidate: his DIN 1451 revivals) for headings, labels and figures; body text falls back to the system UI stack where his faces lack coverage. Final pick made after a cmap/metrics check at build time; criterion = Latin-1 + ß + tabular-feeling digits + legible at 13 px.
- Scale: modular 1.25 from 14 px base; 4 px baseline grid; all vertical rhythm in multiples of 4.

5.2 Optical fitting (the "ink centre" rule)
- Every specimen cell has a fixed box. A font's sample is scaled so its ink height (capHeight→baseline, or measured ink bbox when caps metrics are absent/garbage) fills a target fraction (0.62) of the box, and is centred by ink centre, not em box: `translateY = boxCentre − (inkTop+inkBottom)/2`. Same horizontally for single words.
- Overshoot-heavy faces (fraktur, scripts) use measured ink, not declared metrics.
- Numbers: tabular figures where present; table columns right-aligned on figures.

5.3 Grid & spacing
- 12-column grid, 24 px gutters, 4 px baseline; spacing tokens 4/8/12/16/24/32/48/64/96.
- Equal visual spacing: list items spaced by ink-to-ink distance, not box-to-box; icon rows use one fixed advance.

5.4 Icons (Wiegel's green feature buttons, reinterpreted)
- 24×24 SVG, 2 px stroke on integer coordinates (pixel-grid aligned), 2 px corner radius, 1 colour (`--accent`, a calm green in oklch), rendered at 1× or exact 2×. Each icon = rounded square chip + glyph-based mark (e.g. "€", "ẞ", "Ω", "Ж", "ſ") set in the font family the archive uses for UI, outlined once to SVG paths at build time? → No: kept as text inside the SVG to stay simple; optical centre nudged per glyph.

5.5 Colour
- Paper `#F4F2EC`, ink `#111`, rule `#11111122`, accent green `oklch(0.62 0.13 150)`; dark mode inverts paper/ink, keeps accent.

## 6. Build

- `tools/build.py` (python3 stdlib + fontTools from pip) reads `data/catalog.json` + `fonts/**`, writes `site/`.
- Steps: unzip archives → inventory font files → measure metrics/cmap → choose UI face → render pages from Python string templates → write `site/assets/app.css`, `app.js`.
- `serve.command` (double-click) runs `python3 -m http.server 8787 -d site` and opens the browser.

## 7. Implementation plan (files)

- `data/catalog.json` — from the Apify crawl via extraction agents.
- `raw/archive.zip` → `fonts/<slug>/…` — from the Apify bulk downloader.
- `tools/build.py`, `tools/templates.py`, `site/assets/{app.css,app.js,icons.svg}`.
- `docs/designs/archive.md` — this file.

## 8. Alternatives considered

- Wrapping Wiegel's original HTML in a new theme: rejected (copies his text wholesale; inherits table soup).
- Astro/Next static site: rejected — adds a Node toolchain for a one-person local archive; stdlib Python is enough.
- Showing his PNG specimens: rejected in favour of live rendering, which is the point of a type site and avoids copying images.

## 10. v2 resolutions (after Goldfish review: comprehension, hostile critic, readiness = NO-GO → resolved below)

Priority order (critic's step-back accepted): 1) unpack legacy archives correctly, 2) don't freeze the browser, 3) polish.

Layout
- Source: `fonts/<slug>/` (extracted originals, never modified). Output: `site/index.html`, `site/catalogue.html`, `site/font/<slug>.html`, `site/legend.html`, `site/about.html`, `site/assets/{app.css,app.js,catalog.js,icons.svg}`, `site/assets/fonts/<slug>/<file>` (original binaries, copied, not converted), `site/assets/dl/<archive>.zip`.
- `catalog.js` (`window.CATALOG=…`) instead of fetch → works from file:// too. `serve.command` tries ports 8787–8797.

Archives
- Zip names without UTF-8 flag: re-decode cp437→cp850 (fallback cp1252), NFC-normalise, write ASCII-folded names, keep `orig_name`. Reject `..`/absolute paths, skip `__MACOSX`, `Thumbs.db`.
- `.exe`: try `zipfile` (SFX); `.rar`: `bsdtar`/`unar` if present; else `status:"manual"` + visible badge. Never execute.
- Dedupe by SHA-1. Canonical file per entry: OTF > TTF, then highest `head.fontRevision`. UNZ-1 variants labelled; PUA (U+E000–F8FF) excluded from coverage counts.

Rendering & performance
- CSS family names synthetic: `wa-<slug>-<n>`. Fonts registered lazily in JS via `FontFace` + IntersectionObserver; retype field debounced 150 ms, applied to visible cards only.
- Ink fitting moves to runtime: after `document.fonts.load()`, measure the shaped string with canvas `measureText()` (actualBoundingBox*). Fit on max(cap ink, x ink) not swashes; scale clamped 0.5–2× of median; overflow clipped. Per-font `fit` override field.
- Per-font sample from cmap: "Hamburgefonstiv" if lowercase exists, else "HAMBURG", else first 8 mapped non-space glyphs.
- Glyph grid excludes empty glyphs; plus a Features strip listing GSUB liga/dlig/calt/salt with live on/off.

Type & tokens
- UI face hard-coded (pinned after a cmap check): Wiegel face for masthead and headings ≥ 18 px only; labels, tables, body in `system-ui` with `tabular-nums`. Metric overrides on the display face.
- Tokens: `--paper #F4F2EC / #111`, `--ink #111 / #F4F2EC`, `--rule: color-mix(in oklab, var(--ink) 14%, transparent)`, `--accent oklch(0.52 0.12 150)` (text-safe), `--accent-fill oklch(0.62 0.13 150)`. Space `--s1..--s9` = 4 8 12 16 24 32 48 64 96. Type `--fs0..--fs5` = 14·1.25ⁿ rounded. Dark via `prefers-color-scheme` + `[data-theme]` toggle. `text-box: trim-both cap alphabetic` where supported; ink-to-ink spacing dropped.

Icons
- Glyph marks outlined to paths at build (fontTools SVGPathPen) from the UI face; table `code → {mark, label_en}` in `tools/icons.py`; sprite inlined per page. Crisp claim limited to 1×/2×.

Data
- Catalog validated in build (required fields, years 1400–2026). Years split into `source_years[]` and `release_year`. prev/next and index position derived from the order of Wiegel's index pages, not from agent output. Summaries are fresh English (no verbatim reuse of Wiegel's prose); facts shown with a link to the source page.
- Photos: fetched before build into `data/photos/<slug>.jpg` with author/licence; build never touches the network. Deferred to v2 unless cheap.
- Scope v1: index grid, catalogue table, font pages, legend, about. Timeline deferred.

## 9. Open questions

- Which of his faces holds up at 13 px for UI labels?
- How many pages actually point to places/buildings (photo budget)?
- Do some archives contain only .exe/.rar, needing manual handling?

## 11. v3 — one interface size, lanes for time, colour grounds

Study (built-in browser, measured CSS): Lineto (one size 17px, tag-stack menu, three-lane timeline), Grilli (one size, label column, per-style lines), Optimo (one size 12px, black name index, per-block testers), Herzog & de Meuron (one size 23px, catalogue numbers, Filter → category → value), Klim (colour band per family), Commercial Type (Vault), Radim Peško (names in their own face), Caruso St John (years under projects).

Decisions:
- Interface: DIN 1451 alte Mittelschrift at a single 24px (18px on phones); hierarchy from colour, rules and position. Reading text in CAT Linz 28px.
- Menu: fixed tag stack; on font pages it expands to family → font → sections → previous/next.
- Timeline page: lanes Type | Digitised | Elsewhere. Events from the page write-ups, classified by keyword; every font also gets its digitisation year from the font file's copyright line (fallback head.created, 1995–2023 only).
- Font page: a coloured sheet (12 pairs sampled from peter-wiegel.de, chosen per family by a stable hash; switchable). Text faces get Large Title / Title / Headline / Body / Caption blocks; display and odd faces get Name / Capitals / Lowercase / Figures at large sizes. One toolbar binds to the active block.
- Index: Grid or List (names in their own face), step filter (Family, Original, Digitised, Script, Features, Place, Order), catalogue numbers in Wiegel's order.
