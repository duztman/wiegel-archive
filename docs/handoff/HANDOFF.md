# Wiegel Archive: handoff for the next agent

State at 28 Oct 2026, afternoon (Istanbul), artifact v59. Okay (the owner) directs the design closely; the site is signed off as **pixel-perfect**. Read in this order:
1. this file
2. [../RULES.md](../RULES.md): the design system and how to work with Okay
3. [../audits/2026-10-28.md](../audits/2026-10-28.md): open findings
4. [../ICONS.md](../ICONS.md) and [../REUSE.md](../REUSE.md) when relevant

`docs/designs/archive.md` is the original v1 design; sections 1–10 are superseded and are kept as history.

## What it is

A private typographic showcase of Peter Wiegel's free fonts (CAT Fonts, peter-wiegel.de). There are 337 entries: 598 faces from 642 font files. Each entry has:
- a live specimen page
- an English write-up
- the timeline of the original lettering and its digitisation
- photos of the source objects
- the character set
- the original downloads

## Where it lives

There are three copies. They must stay in step: the same `tools/` builds byte-identical `hosted/` output in all of them (checked on 28 Oct).

| Copy | Where | Notes |
|---|---|---|
| **Mac** (full build) | `~/Sites/wiegel-archive` on Okay's Mac. Open with "Open Wiegel Archive.command" | Has all fonts, raw archives and photos. **Not a git repo.** |
| **Repo** | `duztman/wiegel-archive` (GitHub), branch `main` | `tools/`, `data/`, `docs/`. Fonts, raw files, `site/` and `hosted/` are git-ignored. |
| **Hosted** | private claude.ai artifact https://claude.ai/artifact/9XpQGH3LqFMUfXSGQkgQiG (v59 on 28 Oct) | One face per font. Its page is `main.html`. |

## Pages

- **Top bar:** Wiegel Archive · **Fonts** · Timeline · Images · About · search · C · M · Random.
- **Fonts** (`index.html`): the list and filters.
- **Font pages:** `font/<slug>.html` locally; `font.html#<slug>` in the hosted copy, with bodies in `pages/pN.json`.
- **About** has its own second row:
  - **Peter Wiegel** (`about.html`): portrait, bio, licences, references
  - **This site** (`site.html`): one paragraph, colour, colophon
  - **Legend** (`legend.html`): the feature chips
  - **Catalogue** (`catalogue.html`): the sortable list
- **Links inside the texts** (`xlink()` in `build.py`): a font of the archive named in an account paragraph or the Source fact links to its page; in "In use", feature words (Greek, Cyrillic, euro, capital ß, extended set, long s, UNZ1, OpenType, Kurrent, runes; `USE_TERMS`) link to the font list filtered by Wiegel's matching button, via `index.html#ic=<label>` (or `#cv=`), which `app.js` applies and then clears from the address. First mention per paragraph; names inside quotes stay plain. 455 links on 248 font pages.
- Data for the About pages lives in `build.py`: `REFS`, `about_html()`, `site_html()`. The portrait is `tools/static/people/wiegel.png`, from his own site, made black and white and cut out. Its ground is `--dark`.

## Screenshots

These are in this folder, taken at 1366 × 1024 (phone 390 × 844) in the "sun" pair, after the 28 Oct nav change:

| File | Shows |
|---|---|
| `01-index.png` | Fonts: list on the left, filter column on the right |
| `02-index-filtered.png` | A filter on: the tag pinned under the write box, live counts |
| `03-font-page.png` | Font page top: name row, prev/next, previews |
| `04-font-account-links.png` | Account text and links out with the circled arrow |
| `05-characters.png` | Character grid with vertical block labels |
| `06-colour-picker-open.png` | The C colour picker open |
| `07-catalogue.png` | About › Catalogue |
| `08-timeline.png` | Timeline |
| `09-images.png` | Images |
| `10-about-peter.png` | About › Peter Wiegel |
| `11-phone-font-page.png` | Font page on a phone |
| `12-this-site.png` | About › This site |
| `13-legend.png` | About › Legend |

The progression of 27–28 Oct (260 screenshots, indexed against Okay's messages) is on the Mac in `docs/screenshots/2026-10-28/`.

## How it is built

- **`tools/merge.py`:** extraction slices (`data/parts/*.jsonl`, not committed) plus photo research → `data/catalog.json`. Order, section and prev/next come from Wiegel's own index pages.
- **`tools/build.py`:** Python, stdlib plus fontTools; ~15 s on the Mac.
  1. Extracts `raw/archives` into `fonts/`.
  2. Analyses every font file.
  3. Places photos from `raw/photos/*.zip`.
  4. Writes `site/`.
  5. **Rewrites `data/build-report.json`**.
- **Fallbacks** (for copies without the raw files):
  - Without `raw/archives`, file lists come from `build-report.json`.
  - When a font file is absent, `inventory()` uses the metadata recorded there (cmap, metrics, names).
  - This is what lets the cloud session build the hosted copy without the 158 MB font folder. In the cloud copy `build.py main()` itself still crashes, because it copies every face; use `hosted.py` there.
- **`tools/uifonts.py`:** the interface faces `WA UI` and `WA Text` (site-only copies of Preussische IV 44 and Proletarsk) into `assets/fonts/ui/`; `build.py` and `hosted.py` call it. Reads `data/ui-kern.json` and `data/ui-marks.json`; needs only fontTools.
  - Redrafting the kerning: `python3 tools/uikern.py fonts HALFKERN KERNING_PAIRS` (clones of behdad/halfkern and andre-fuchs/kerning-pairs; halfkern needs pycairo, freetype-py, uharfbuzz, scipy, scikit-fmm). Okay's corrections live in its `ADJUST`.
  - Redrawing new shapes (Turkish marks, ẞ, ligatures, comma): `python3 tools/uidraw.py fonts` (needs skia-pathops).
- **`tools/hosted.py`:** builds `hosted/`: one face per font, the `font.html#slug` shell, `pages/pN.json` packs of 20, photos at 1600 px.
- **`tools/static/app.css`, `app.js`:** all styling and behaviour, vanilla. Fonts load through `fetch` + `FontFace`.

## Publishing a change

1. **Edit `tools/…` in the repo clone.** Check with Playwright against a local server on `hosted/`, e.g. `python3 -m http.server 8765`. Set `localStorage` `wa-mode=mono`, or a pair, for repeatable colours.
2. **Build the hosted copy in the cloud** (no Mac needed):
   1. Restore the publish folder: `Artifact read` the artifact into `/home/claude/wiegel-hosted/`.
   2. Seed the fonts: copy `wiegel-hosted/assets/fonts/*` into `wiegel-archive/fonts/`.
   3. Seed the photos: copy `wiegel-hosted/assets/photos/*.jpg` into `wiegel-archive/site/assets/photos/`.
   4. Seed the set members: their woff2 files go in `fonts-web/<slug>/` (gitignored; on the Mac they come from the TTFs). Without them, `hosted.py` reports each missing member.
   5. Run `python3 tools/hosted.py`.
3. **Copy what changed** from `hosted/` to `/home/claude/wiegel-hosted/` (compare with `cmp`). Skip `index.html` (the artifact's page is `main.html`).
   - **Never copy photos from a cloud build.** It re-encodes the already-resized JPEGs, so they differ by bytes but are not real changes.
4. **Publish:** the artifact holds at most **511 files** (one publish sends at most 255). That is why set members ship as 56 packs (`assets/sets/sN.woff2`, two sets each; `write_pack()` in `hosted.py`, read by `bytes()` in `app.js`), not 261 files. They are named `.woff2` because the host serves only known types. Artifact `url` = the artifact, `file_path` = `/home/claude/wiegel-hosted/main.html`, `files` = map of the changed files. Read the artifact (no `path`) once per session first.
5. **Commit and push** in `/home/claude/wiegel-archive`, using a branch, then fast-forward `main`.
6. **Update the Mac.** The Mac's shell reaches GitHub raw but not the cloud container, and this session had no file-commit tool.
   1. Back up the old files first: `cp` them into `_to_delete/tools-before-<date>/`.
   2. Pull each changed file: `curl -sSf -o tools/<file> https://raw.githubusercontent.com/duztman/wiegel-archive/main/tools/<file>`.
   3. Run `python3 tools/build.py && python3 tools/hosted.py` there.
7. **Regression check before publishing:** deterministic screenshots of every page and 20 fonts at 1366 and 390 (`sun` pair), before and after, compared pixel by pixel. Lazy images and font loads make a few shots noisy: repeat a differing shot before believing it. Note that `goto` between `font.html#a` and `font.html#b` is a hash change in the same document, not a reload.
8. **Verify the copies agree:** `shasum -a 256` of `hosted/*.html` and `hosted/assets/app.css` on the Mac must equal the cloud build.

**Artifact capabilities:** the hosted artifact declares `downloads` (since v81, for the WA UI / WA Text links under Account). Publish without `capabilities` to keep it; passing `{}` clears it and the links hide.

**Deleting files on the Mac is not permitted.** Move leftovers into `_to_delete/` and tell Okay.

## Process: Elephant–Goldfish

Design work follows the [Elephant–Goldfish Model](https://github.com/google/elephant-goldfish-model):
- One context-rich session (the Elephant) designs and writes the document.
- Zero-context reviewers (Goldfish) attack it before any code.

The 28 Oct audit used three Goldfish subagents (CSS, JS, build and drift) plus direct measurement. See [../REUSE.md](../REUSE.md) for install commands and a ready brief.

## Open work

1. **Audit decisions still open** (see the status table in [../audits/2026-10-28.md](../audits/2026-10-28.md)): ink crossing block rules in 19 fonts; C/M "on" state; pill re-centring after rotation; sticky hover on touch. (Swash fitting: done, indent.)
2. **Member names to check** in `data/members.json`, e.g. "Typographer Fraktur UNZ1, second cut", "Preussische VI 9 Schatten B".
3. **Families across posts** (agreed; waiting on Okay's check): a hand-checked sibling list.
   - Examples: Rastenburg / Rastenburg Band; Typographer Fraktur / Gotisch / Rotunda / Textur; Fibel Nord / Süd / Vienna; Bernardo Moda / Contrast.
   - Do not group by first word.
4. **Small open questions:**
   - "Licence (page)" notes cut to a name?
   - The Safari check of cap-band pill centring.
   - The 3% x-height gap in arrow sizing.
5. **Another archive in the same shell:** brief in [../REUSE.md](../REUSE.md).
