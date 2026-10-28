# Rules

The design system Okay signed off, and the working rules for changing it. The site is **pixel-perfect as of 28 Oct 2026**: a change that alters rendering needs his explicit go, even when it fixes a bug. Mark every proposal **render-identical** or **changes rendering (because …)**.

## Type and size

- **One interface size:** `--ui: 24px` (18 on phone), set in Wiegel's Preussische IV 44 (`UI_DISPLAY`). Running text in his Proletarsk (`UI_TEXT`, `--read: 28px`). DIN is not used for any label; it survives only as the source of two chip marks (ẞ, ſ), see [ICONS.md](ICONS.md).
- **Smallest text** (`--info`, 14px): always caps, letter-spaced `.05em`, one tone (`--ink-3`). Vertical labels are the same text, rotated. One block at the end of `app.css` ("the smallest text") enforces this for every small-text selector, by source order. Do not add colour or opacity to those selectors elsewhere; it will be silently overridden.
- **Specimen ink is never cut vertically:** fit lines and waterfall lines clip sideways only (`overflow-x: clip`).
- **Specimens are live type**, never images. The page sizes each fit line with canvas `measureText` to 97% of the measure, floor `2 × --ui`; below the floor the line wraps instead (`.wrapped`).

## Line and spacing

- **One line thickness:** `--line = var(--ui) * .105`, the stem of the UI face. Lighter lines come from opacity or colour, never thinner strokes. Deliberate exceptions: link arrows (1px lighter), feature chips (outline proportional to the chip), small tags (`var(--info) * .105`).
- **Rhythm:** rows in the top bar sit 12px above the pill and 14px below to the next line. Paragraphs and list rows have top padding half the bottom (`--pt 8 / --pb 16`); sections the same ratio (`--st 24 / --sbt 48`). The gap above the first font preview is `2 × --st`.
- On the About pages the first rule (or the portrait) sits 48px under the bar: `.prose` padding 16 plus the `h2`/`.portrait` margin 32.

## Colour

- Navigation and content always share one colour pair.
- Pairs are light paper on dark ink, ordered by the light's hue from yellow to pinks, one light each (`PALETTE` in `build.py`). **I** inverts all of them. **M** is mono: black/white plus one accent.
- `--dark` is always the dark of the current pair, inverted or not (the portrait ground uses it).
- Grounds that clash with Wiegel's download green `#05872C` (green, olive, magenta, crimson) are banned, because the feature chips keep that green.

## Navigation

- **Top bar:** Wiegel Archive · **Fonts** · Timeline · Images · About · search field (fills the gap; Enter searches the font list) · **C** (colour picker that grows left out of the circle) · **M** · **Random**.
- **Second row, same pill style:**
  - On font pages: the font name, its family pill, then section pills.
  - On the About pages: **Peter Wiegel** (`about.html`) · **This site** (`site.html`) · **Legend** (`legend.html`) · **Catalogue** (`catalogue.html`). The About pill stays lit on all four.
- Pills never fill on touch. Hover styles go inside `@media (hover: hover)`; the audit lists rules that still break this.
- **Pill labels are centred by script** (`inkCenter` in `app.js`):
  - Words sit on their cap band.
  - Single letters in circles sit on their ink box.
  - Every label is then nudged 2px right (`NUDGE`, tuned on Okay's iPad).
  - Small pills are not scripted: CSS padding sets them 1px down and 2px right.

## Arrows and links

- Inside pills: a long arrow without a circle (`.arw`).
- Everywhere else: one circled arrow (`.ca`, direction class `ne r l u d`).
  - The ring is 7/6 of the x-height (cap height in caps lines), centred on that band.
  - Links out get `ne` and downloads get `d`, added by `deco()` in `build.py`.
  - The last word of a link always stays with its arrow.
- Links inside running text (font names, "In use" features) carry the circled → (`r`): it goes somewhere inside the archive. Links out carry ↗ (`ne`).
- No underlines anywhere.

## Pages

- **Fonts (index):**
  - Two independent full-height scrolling columns.
  - The right column has a pinned head: write box, selected tags, search.
  - Filter pills show live counts. Pills that would give zero results are dimmed and disabled.
  - Filtering returns the list to the top.
- **Font page:**
  - Row 1 is the bar, row 2 the name, family and sections, row 3 prev/next flush right.
  - Previews fit one line where possible. Controls (size, leading, tracking) sit below the previews.
- **Peter Wiegel:**
  - The portrait comes first: black and white, cut out, on `--dark`, at its native 174 × 215 (the source is small; never upscale).
  - Then the bio, Licences and References. References are list rows with the site name above in small caps.
- **This site:** one paragraph of intention and a little of how. Then Colour, with the pairs, and Colophon. No process history; that lives in `docs/`.
- **Feature chips:** see [ICONS.md](ICONS.md).
- **Licence (font file)** shows only the licence's name (`lic_name()`).

## How to work with Okay

- **Answers:** short bullets, and state the values you used.
- **Vague quantifiers:** follow his scale (a bit ≈ 15%, noticeably ≈ 35%, double = 2×). When unsure, pick the smaller.
- **Measure, don't guess:** Playwright, zoomed pixel crops, real numbers. He checks on Safari on an iPad, so a Chrome measurement can still be off there.
- **Fixes:** no `!important`, magic numbers or patches over an unknown cause; find the upstream reason. The one deliberate `!important` is `[hidden]`. If a fix fails twice, stop and ask.
- **Screenshots:** he annotates them by hand. Read the arrows literally ("touch here", "1/5 shorter", "3px down").
- **Deleting files on the Mac is not permitted.** Move leftovers into `_to_delete/` and tell him.
