# Wiegel Archive: handoff for the next agent

State at 28 Oct 2026, 05:50 (Istanbul). Written after a long design session with Okay, the owner, who directs the design closely. Read this, then `docs/designs/archive.md` (the original design doc and its v3 decisions).

## What it is

A private, typographic showcase of Peter Wiegel's free fonts (CAT Fonts, peter-wiegel.de): 337 entries, 598 font files, each with a live specimen page, an English write-up, the timeline of the original lettering and its digitisation, photos of the source objects, the character set, and the original downloads.

- **Full build:** on Okay's Mac at `~/Sites/wiegel-archive`, opened with "Open Wiegel Archive.command". The Mac folder is **not a git repo**; it is kept in step by copying files into it and running `python3 tools/build.py` there.
- **Hosted copy:** private claude.ai artifact https://claude.ai/artifact/9XpQGH3LqFMUfXSGQkgQiG (Version 57 at time of writing). One font file per entry, to save space.
- **Source repo:** `duztman/wiegel-archive` on GitHub (currently public; Okay may make it private).

## Screenshots

Current state, 1366 × 1024 unless noted, in this folder:

| File | Shows |
|---|---|
| `01-index.png` | Index: font list on the left, filter column on the right |
| `02-index-filtered.png` | Index with a filter on: selected tag pinned under the write box, live counts, dimmed empty pills |
| `03-font-page.png` | Font page top: name in the section bar, prev/next row, previews, sliders |
| `04-font-account-links.png` | Account text and links out with the circled arrow |
| `05-characters.png` | Character grid with vertical block labels |
| `06-colour-picker-open.png` | The C colour picker open in the top bar |
| `07-catalogue.png` | Catalogue lister |
| `08-timeline.png` | Timeline |
| `09-images.png` | Images page |
| `10-about-legend.png` | About page with the feature-icon legend |
| `11-phone-font-page.png` | Font page on a phone (390 wide) |

The whole evening's progression is on the Mac in `~/Sites/wiegel-archive/docs/screenshots/2026-10-28/`: 260 screenshots (Okay's annotated ones plus every check) indexed in its `README.md` against Okay's messages, and `main-page-versions/` with the index page of 46 successive builds.

## How it is built

- `tools/build.py`: Python static build (stdlib + fontTools). Reads `data/catalog.json` and the font files, writes `site/`. ~2 s.
- `tools/static/app.css`, `tools/static/app.js`: all styling and behaviour; vanilla, no framework.
- `tools/hosted.py`: builds the artifact version into `hosted/` (single `font.html#slug` shell plus `pages/pN.json` packs, one face per font).
- Fonts load via `fetch` + `FontFace` (works where CSS font URLs are blocked).

### Publishing a change (the loop used all night)

1. Edit `tools/…`, run `python3 tools/build.py`, check with Playwright against a local server on `site/` (port 8810).
2. `python3 tools/hosted.py`, then copy every changed file from `hosted/` to `/home/claude/wiegel-hosted/` (compare with `cmp`; skip `hosted/index.html`, the artifact's page is `main.html`).
3. Publish with the Artifact tool: `file_path` `/home/claude/wiegel-hosted/main.html` plus a `files` map of the changed files. If it refuses a file you have not read this session, read it from the artifact first.
4. `git commit` and `git push` in `/home/claude/wiegel-archive`.
5. Copy the changed `tools/` files to the Mac with `device_commit_files` (force) and run `python3 tools/build.py` there via `device_bash`.

**Deleting files on the Mac is not permitted.** Move leftovers into a `_to_delete/` folder and tell Okay.

## The design system (rules Okay set; keep them)

- **One interface size:** `--ui: 24px` (18 on phone), set in Wiegel's Preussische IV 44. Running text in his Proletarsk (`--read`). DIN is no longer used anywhere in the interface.
- **One line thickness:** `--line = var(--ui) * .105`, the stem of the UI face. Lighter lines are made with opacity or colour, never with thinner strokes. Exceptions, each deliberate: link arrows are 1px lighter; feature chips use a proportional outline; small tags use `var(--info) * .105`.
- **Smallest text** (`--info`, 14px): always caps, letter-spaced `.05em`, one tone (`--ink-3`). Vertical labels use exactly this style, rotated.
- **Spacing rhythm:** rows in the top bar are 12px above the pill, 14px below to the next line. Paragraphs/list items: top padding half the bottom (`--pt 8 / --pb 16`). Gap above the first font preview is `2 × --st`.
- **Colour:** navigation and content always share one colour pair. Pairs are light paper / dark ink, ordered by the light's hue from yellow to pinks, one light each (`PALETTE` in `build.py`). **I** inverts all of them. Grounds that clash with Wiegel's download green `#05872C` (green, olive, magenta, crimson) are banned because the feature chips keep that green.
- **Top bar:** Wiegel Archive · Index · Timeline · Images · Catalogue · About · search field (fills the gap; Enter searches the index) · **C** (colour picker that grows left out of the circle, eased, with a faint glow; remembers the pick on every page; tapping the picked pair again forgets it) · **M** (mono: black/white plus one accent) · **Random** (opens a random font). Pills in the bar never fill on touch; hover styles only apply on hover devices.
- **Pill labels are centred by script** (`inkCenter` in `app.js`): words sit on their cap band (baseline to cap height); single letters in circles sit on their ink box; then every label is nudged 2px right (`NUDGE`, tuned by eye on Okay's iPad); a measured 0.029em raster correction lifts glyphs. Small pills (`.tg`, `.pill.small`) are not scripted: CSS padding puts their label 1px down and 2px right.
- **Arrows:** inside pills, a long arrow without a circle (`.arw`). Everywhere else one circled arrow (`.ca`, direction by class `ne r l u d`). The ring is 7/6 of the x-height (cap height in caps lines), centred on that band; the shaft starts on the ring. Links out get `ne`, downloads `d`, added automatically by `deco()` in `build.py`; the last word of a link always stays with its arrow.
- **No underlines anywhere.**
- **Vertical labels** start at the cap height of the first line beside them (`capAlign`, measured from the laid-out first letter after the real font loads). Glyph-block labels start and stick at the same height as their section heading.
- **Index:** two independent full-height scrolling columns under the bar; the top fade only appears once the list scrolls. The right column has a pinned head: write box, then selected tags (filled in the outline colour, letters in the full accent, short-armed X), then search. Filter pills show live counts; pills that would give zero results are dimmed and disabled. Filtering always returns the list to the top.
- **Font page:** row 1 the bar; row 2 the font name, its family pill and section pills; row 3 prev/next flush right (scrolls away). Previews fit one line where possible (floor 2 × `--ui`, then wrap). Controls (size, leading, tracking) are below the previews; the kern/swatch/invert/reset line was removed.
- **Feature chips** (icons for character set and features): Wiegel's green, outline proportional to the chip, marks cut from the archive's own type, sized to one optical size and centred on their ink.
- **Licence (font file)** shows only the licence's name (`lic_name()`); the 16 "Have fun and enjoy" entries show no row.

## How Okay works (read before changing anything)

- Short bullet answers; state the values you used. Vague quantifiers follow his scale (a bit ≈ 15%, noticeably ≈ 35%, double = 2×); when unsure pick the smaller.
- Measure, don't guess: check with Playwright, zoomed pixel crops, real numbers. He uses Safari on an iPad; things that measure right in Chrome can be off there (that is why `NUDGE` exists).
- No `!important`, magic numbers or patches over an unknown cause. Find the upstream reason. If a fix fails twice, stop and ask.
- He annotates screenshots by hand; read the arrows literally ("touch here", "1/5 shorter", "3px down").

## Open work

1. **Families inside one download** (agreed): 114 entries hold several fonts (Baltic Fonts holds 12). Replace the Style menu, which labels every member "Regular", with a Family block listing each member in its own face; show "12 fonts" on index rows; include all members in the hosted copy (about +46 MB).
2. **Families across posts** (agreed, waiting on Okay's check of the example): a hand-checked list of real families spread over separate Wiegel posts, e.g. Rastenburg / Rastenburg Band (peter-wiegel.de/Rastenburg.html and /RastenburgBand.html), Typographer Fraktur / Gotisch / Rotunda / Textur, Fibel Nord / Süd / Vienna, Bernardo Moda / Contrast. Do not group by first word (CAT, Fette, Neue and Peter are not families). Mark these as "from separate posts" and link siblings on each page.
3. **Code audit:** Okay asked for a big one next.
4. **Small open questions:** whether "Licence (page)" notes should also be cut to a name; Safari check of the cap-band pill centring; the 3% gap between the font's x-height metric and its drawn x-height in the arrow sizing.
