# Feature chips (icons)

Wiegel marks each font with small green buttons for its character set and features. The archive redraws them as **line chips**:
- in his download green (`--dl`, `#05872C`)
- at the one line thickness
- with the mark **cut from the archive's own type** (no icon font, no hand-drawn SVG)

## Where it lives

| What | Where |
|---|---|
| The codes, marks, labels and descriptions | `ICONS` in `tools/build.py` (Wiegel's own codes: `standard`, `unz`, `kyrill`, …) |
| Which font gets which codes | `data/catalog.json` → `fonts[].icons` (from his page) |
| Sprite generation | `icon_svgs(cat)` in `tools/build.py`, inlined into every page as `<symbol id="i-<code>">` |
| Use in markup | `icon(code, size)` → `<svg class="ic"><use href="#i-code"/></svg>` |
| Styles | `.ic`, `.chip`, `.mark`, `.mark-t` in `tools/static/app.css` |
| The public key | the Legend page (`legend_block()`) |

## How a mark is made

1. **Pick a font.** The pool is the UI face (Wiegel's Preussische IV 44 file), then the site's copy of it (`WA UI`, which adds ẞ: the capital sharp s mark comes from there), then Alte DIN 1451, then Proletarsk, then up to six archive fonts that cover Greek, Cyrillic and long s. The first one that has every character of the mark wins.
2. **Outline.** Each glyph is drawn with fontTools into an SVG path (`SVGPathPen`), advancing by the glyph width.
3. **One optical size.** Scale is set by the geometric mean of the ink box, `10.5 / √(w·h)`, then capped to fit a 15 × 12 field. A slim `i` and a wide `UNZ` read as the same size.
4. **Centre on the ink's weight**, not its box: the area centroid (`StatisticsPen`), clamped to a 4.5-unit margin inside the 24-unit chip. Offsets are rounded to quarter units.
5. **Chip:** a 22.5-unit rounded square (`rx 5.5`) at the line thickness; the mark is filled.
6. **Fallback:** if no pool font has the characters, the mark is live `<text>` in the UI face. Today that applies to 4 marks: `kapitaelchen` (Aᴀ), `runen` (ᚱ), `spezial` (✱), `color` (▚).

## Adding or changing a chip

1. Add or edit the row in `ICONS`: `code: (mark, label, description)`. Keep descriptions to one sentence.
2. If the mark needs a script the pool lacks, add a covering font to the pool in `icon_svgs`. Do not hand-draw it.
3. Run the build and check the Legend page, and one font page that uses the chip, at 24 and 48 px. Zoom the screenshot: the mark should look as heavy as its neighbours.
4. The cloud build and the Mac build must give the same sprite. If a pool font fails to load in one of them (the exception is silent today, see the audit), the mark is cut from a different font.

## Making chips for another archive

The method is the reusable part. The codes and texts are Wiegel's. For another designer:
- replace `ICONS` with that site's own feature vocabulary
- choose a pool face that matches the new interface face
- keep steps 3–5 as they are
