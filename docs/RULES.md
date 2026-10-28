# Rules

The design system Okay signed off, and the working rules for changing it. The site is **pixel-perfect as of 28 Oct 2026**: a change that alters rendering needs his explicit go, even when it fixes a bug. Mark every proposal **render-identical** or **changes rendering (because …)**.

## Type and size

- **One interface size:** `--ui: 24px` (18 on phone), set in Wiegel's Preussische IV 44 (`UI_DISPLAY`). Running text in his Proletarsk (`UI_TEXT`, `--read: 28px`). DIN is not used for any label; it survives only as the source of the ſ chip mark, see [ICONS.md](ICONS.md).
- **The interface faces are the site's own copies** (`WA UI`, `WA Text`, built by `tools/uifonts.py` into `assets/fonts/ui/`); the font pages and downloads keep Wiegel's originals. Copies: kerning from `data/ui-kern.json` (Wiegel's Preussische pairs kept, the rest drafted by `tools/uikern.py` with halfkern, plus Okay's corrections in its `ADJUST`), Turkish letters and ẞ drawn from his own parts, Preussische sidebearings centred, its curly quotes on the cap height, its comma turned like his ‚, Proletarsk's uneven sides evened (`TEXT_SPACING`), ff fi fl ffi ffl ligatures (fi and ffi off for `lang="tr"`). New shapes are drawn once by `tools/uidraw.py` into `data/ui-marks.json`. Change spacing by a rule in `uikern.py` or `uifonts.py` and rerun, never by editing the JSON. Both pages offer the copy under Account › On this site (hosted: the artifact's `downloads` capability; the link hides where it is missing).
- **Smallest text** (`--info`, 14px): always caps, letter-spaced `.05em`, one tone (`--ink-3`). Vertical labels are the same text, rotated. One block at the end of `app.css` ("the smallest text") enforces this for every small-text selector, by source order. Do not add colour or opacity to those selectors elsewhere; it will be silently overridden.
- **Specimen ink is never cut.** Each fit line is sized from the line as the browser lays it out (a hidden probe with the face, tracking and features) and from its ink (canvas `actualBoundingBox*`): 97% of the measure, or less when swashes reach past the first or last letter. Ink left of the first letter is indented (`text-indent`), never clipped. Ordinary fonts keep the sizes they had. It re-fits on typing, tracking and feature toggles. A line sized by hand with the slider wraps instead of fitting. Below the floor `2 × --ui` a line wraps (`.wrapped`). `overflow-x: clip` stays only as a guard against typed text; the waterfall is cut only at its right edge. Checked: 0 cut lines on 337 fonts, also after tracking and typing on the 63 swash fonts.
- **Specimens are live type**, never images.

## Line and spacing

- **One line thickness:** `--line = var(--ui) * .105`, the stem of the UI face. Lighter lines come from opacity or colour, never thinner strokes. Deliberate exceptions: link arrows (1px lighter), feature chips (outline proportional to the chip), small tags (`var(--info) * .105`).
- **Rhythm:** rows in the top bar sit 12px above the pill and 14px below to the next line. Paragraphs and list rows have top padding half the bottom (`--pt 8 / --pb 16`); sections the same ratio (`--st 24 / --sbt 48`). The gap above the first font preview is `2 × --st`.
- On the About pages the first heading (or the portrait) sits 48px under the bar: `.prose` padding 16 plus the `h2`/`.portrait` margin 32.
- **One rule is enough.** Never two horizontal rules with nothing between them. A list that opens a section, or a heading that opens a page under the nav, sits on the rule already above it: its own first rule keeps its space (so nothing moves) but not its line (`border-top-color: transparent`). A list that ends a section draws no closing rule; the next section's rule closes it. Not rules, so exempt: the glyph table's cell outlines and the font-page timeline axis. `tools/double_rules.py` finds offenders.

## Colour

- Navigation and content always share one colour pair.
- Pairs are light paper on dark ink, ordered by the light's hue from yellow to pinks, one light each (`PALETTE` in `build.py`). **I** inverts all of them. **M** is mono: black/white plus one accent.
- `--dark` is always the dark of the current pair, inverted or not (the portrait ground uses it).
- Grounds that clash with Wiegel's download green `#05872C` (green, olive, magenta, crimson) are banned, because the feature chips keep that green.

## Navigation

- **Top bar:** Wiegel Archive · **Fonts** · Timeline · Images · About · search field (fills the gap; Enter searches the font list) · the **colour button**, which is the swatch on show (paper/ink of the current colours) and opens a rounded box with an arrow under it: two rows of four, a lightning bolt for invert, M (paper/ink, black and white with one accent), then Wiegel's six pairs · **Random**. The search takes 85% of the free width; C and Random sit flush right.
- **The bar always ends on a rule:** under row 1 on pages without a second row (Fonts, Timeline, Images), under row 2 where there is one.
- **Second row, same pill style:**
  - On font pages: the font name, its family pill, then section pills.
- **Scroll fade:** the bar's fade never lies over the Cards / Preview toggle or the side panel; on the Fonts page the list column fades by itself as it scrolls.
- **Phone bar** (≤ 800px): row 1 keeps the name, then the current page's pill flush right beside a menu button that replaces every other pill and opens a full-screen centred menu: the pages at twice the size and padding, outlines at twice the line too, a short search, Random, and I, M and the colour pairs at the foot as swatches twice as large (the search and colour controls move into it while it is open). No prev/next on phone. Row 2: 8px between pills; the name stays put while its pills scroll under it, fading in at the left once scrolled, and run on past the right margin to the screen's edge; a name wider than half the row takes a row of its own. The About row scrolls the same way.
- **Third row, font pages only** (designed with Okay, 28 Oct 2026): styles left, prev/next flush right; no rule under it. One pill per style in the download, labelled by its style name; the face with no style of its own is "Regular" when the font has a Bold, otherwise the font's name; the current style is a filled pill. Style pills wrap to more lines on desktop with prev/next on the first; on phone prev/next take their own line and the styles are one swiping row, so the sticky bar stays short.
- **Style switching** is done only by the row-3 pills. There is no Style menu in the tools, and the Set list does not switch.
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
  - Row 1 is the bar, row 2 the name, family and sections, row 3 styles and prev/next. The sheet ends with the tools; no info line under them.
  - Previews fit one line where possible. Controls (size, leading, tracking) sit below the previews.
  - **Set** (115 downloads hold several fonts): the members by the names the site gives them (`data/members.json`, drafted by `tools/members.py`, edited by hand; the font files keep their own names). Each is listed in its own face; the list shows, the style pills switch. "Also in the download" lists other designs from the same zip. Row 2 has a "Set of N" pill; the list shows "N fonts"/"N styles" and a **Sets** pill under Family.
  - **Clock fonts** (`CLOCKS` in `build.py`; Stefans Uhr): their letters are a plain stand-in; typed times (h:mm, five-minute steps) become clock faces through OpenType ligatures. Previews, list rows, cards and the specimen show times, never the name.
  - **Figures-only fonts** (no Latin letters, or Wiegel's "Figures only" button): figures and a sample of times, prices and dates, never the name; the list preview is figures too.
  - **No fallbacks:** wherever a Wiegel font is set (list, cards, specimen, waterfall, set list, timeline), a character the font lacks shows as nothing, never in another face (`WA Blank`, a font whose every character is empty). The set list shows what each member has: figures or clocks for figures-only and clock fonts, the name otherwise.
- **Catalogue rows:** No. · the font's own Aa (as on its card, 2 × `--list`, fitted to the column; no heading) · name · family · original · digitised · glyphs. In the glyphs column the feature chips are on the first line and the count under them, both starting where the heading's text starts. The Aa sits on the name's baseline with the same room reserved above it in every row, so rows keep one rhythm. Phone: the Aa leads the row, the name under it.
- **Fonts list rows:** one row (and one card) per font file: a set gives each of its styles a row named like 'Varieté Cabaret', which opens the set's page with that style on (the choice rides in sessionStorage `wa-style`). A font that comes alone has no style pills in the bar. Companions stay under their original and get no row: alternates, initials and word-start forms (`COMPANION` in `build.py`); shadow, 3D, outline and light versions keep their rows. A set made only of such names (Schwaben Alt, Zeichen … Alt) keeps them all. One small-caps line, `NAME · OG year · DG year · family · N fonts`, catalogue number flush right; the name is there because the preview above can be retyped.
- **Timeline:** no intro, the decade strip comes first: small faint pills like Clear, only decades with something in them, no gap before 1800, never filled; they only scroll. One stem, today at the top. A year (24px, the UI size; no new sizes) appears only where something happened. Each note (what happened, in the text face) heads the cards of the fonts it is about; fonts with the same note share it. Plain digitisations follow as a bulk of cards, headed "Wiegel digitised N fonts" only in a year with no notes.
- **Fonts list view:** Cards by default; Preview is remembered only once someone picks it.
- **Font cards** (timeline, and the Fonts list in Cards view): like Font Book's, the font's own 'Aa' and its name in small caps cropped to fit, one card per typeface, outlined like the preview box (radius 17px). One Aa size for every font (72px, the list-preview size; 44px on phone); only a face too wide for the card is set smaller, never cut. Figures-only fonts show figures, symbol fonts their first characters.
- **Fonts list views:** Cards · Preview, small pills flush right in the side column's head, level with Clear. Preview is the list with retypable text; Cards hides the preview box, and the first filter rule (Order) moves up level with the top of the cards, where the box began. The active pill is at full strength, never filled; the choice is remembered per viewer.
- **Peter Wiegel:**
  - The portrait comes first: black and white, cut out, on `--dark`, at its native 174 × 215 (the source is small; never upscale).
  - Then the bio, Licences and References. References are list rows with the site name above in small caps.
- **This site:** one paragraph of intention and a little of how. Then Colour, with the pairs, and Colophon. No process history; that lives in `docs/`.
- **Feature chips:** see [ICONS.md](ICONS.md).
- **Licence (font file)** shows only the licence's name (`lic_name()`).
- **Font history** (the font page's timeline section, so named on its pill and label): cards have no top rule; the year is in the interface size and in its lane colour (Type `--hot`, Digitised `--dl`, Elsewhere `--sky`), with no lane label. The "years between" line is smallest text.
- **Facts:** licence name (reading size) → small pills (family, genre, N styles, N characters, then tags; each value once) → feature chips (48px, 10 across, smallest-text labels top-aligned, so one-line labels start where two-line ones do). Number, dates, source, place, designer field and Wiegel's index are shown elsewhere or dropped.
- **Small pills are links** wherever they show a filterable value: `index.html#fa=`, `#g=`, `#st=`, `#gl=`, `#tg=` (genre, styles, characters and tags filter the list without pills of their own).
- **Timeline dots** sit over the axis and its ticks, with no halo cutting the line.
- **Split fonts** (`SPLIT` in `build.py`): a design that only came inside another download becomes a font of its own at the end of the archive, so no number moves. Barnroof (from Varieté) is 338.
- **Lines that cross or meet** use an opaque ink/paper mix (`color-mix(in oklab, var(--ink) 22%, var(--paper))`), never alpha, so crossings don't darken.
- **Mono face:** Erika Type Bold, Wiegel's typewriter face (`WA Mono`, the glyph codes). No system monospace.
- **Typewriter** is a pill under Family, for fonts tagged typewriter (6), after Dot matrix.

## How to work with Okay

- **Answers:** short bullets, and state the values you used.
- **Vague quantifiers:** follow his scale (a bit ≈ 15%, noticeably ≈ 35%, double = 2×). When unsure, pick the smaller.
- **Measure, don't guess:** Playwright, zoomed pixel crops, real numbers. He checks on Safari on an iPad, so a Chrome measurement can still be off there.
- **Fixes:** no `!important`, magic numbers or patches over an unknown cause; find the upstream reason. The one deliberate `!important` is `[hidden]`. If a fix fails twice, stop and ask.
- **Screenshots:** he annotates them by hand. Read the arrows literally ("touch here", "1/5 shorter", "3px down").
- **Deleting files on the Mac is not permitted.** Move leftovers into `_to_delete/` and tell him.
