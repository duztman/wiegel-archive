# Using this shell for another archive

Status: **brief only, nothing extracted yet.** Making the build generic is a real refactor of `tools/build.py`, which has about 12 Wiegel-specific seams. Run it as an Elephant–Goldfish design first (see the end of this file); do not start by editing code.

## What carries over unchanged

- The page set: font list with filters, font page (live specimen, sliders, waterfall, characters, files), timeline lanes, images, catalogue lister, about pages, legend.
- The design system in [RULES.md](RULES.md): one size, one line, pill navigation, circled arrows, colour pairs shared by bar and content.
- `app.js` almost entirely: fonts load through `fetch` + `FontFace`, fit lines are measured with canvas, pills are ink-centred.
- The chip method in [ICONS.md](ICONS.md).
- The hosted packing (`hosted.py`): one face per font, one `font.html#slug` shell, bodies in `pages/pN.json`, fitted to an artifact's file limits.

## Seams: Wiegel-specific values to lift into one config

| # | Seam | Where now |
|---|---|---|
| 1 | Interface and reading faces, and the family names `WA UI` / `WA Text` | `UI_TEXT`, `UI_DISPLAY`, `UI_DIN` (build.py:21-23); hosted keep-list |
| 2 | Colour pairs, family → pair, accents, download green | `PALETTE`, `FAM_PAL`, `TEXT_FAMS`, `THEME_JS` accent arrays; CSS `--dl`, `--hot`, `--sky` |
| 3 | Navigation and page titles ("Wiegel Archive") | `NAV`, `ABOUT`, `page()`, app.js title strings |
| 4 | Licence naming | `lic_name()` (German phrases, typo-tolerant), the licence paragraph |
| 5 | Third-party rules (Steffmann re-encodings) | `digitised()`, auto timeline events, year windows 1990/1995–2023 |
| 6 | Feature codes | `ICONS`, the `is_text` odd-icon set, `specimen_blocks` |
| 7 | Classifiers | `lane_of` keywords (German, DIN/TGL), the variant regex in `inventory()` |
| 8 | Index sections and genres | section names (build.py `catalogue_html`, merge.py `SECTIONS`), `FAMILY`, `FAMILY_ORDER`, year regexes |
| 9 | Fixed text | `PANGRAM_DE`, "Read Wiegel's original", Google Translate de→en, "Wiegel's index" row, app.js `ORDERS` |
| 10 | Prose | `REFS`, `about_html`, `site_html`, the footer (written twice) |
| 11 | Encoding | `ascii_name` umlaut map, cp850 zip names |
| 12 | Storage keys | `wa-` localStorage keys and FontFace id prefix |

**Proposal:** a single `archive.toml` per archive (faces, palette, nav, texts, sections, feature codes, licence patterns), plus a small `rules.py` hook file for the logic seams (4, 5, 7). `build.py` then reads both and keeps no names of its own.

## The pipeline, stage by stage

Only stages 3–6 are in this repo. Stages 1–2 ran as cloud scraping and agent extraction, and their raw outputs are not committed (`data/parts/` is ignored).

1. **Scrape** the designer's index pages and every font page (Apify; the shells cannot reach the site). Keep page order: it becomes `section`, `pos`, `prev`/`next`.
2. **Extract** each page into a JSONL record (`data/parts/*.jsonl`). The fields are those of a catalog entry: name, years with notes, origin, place, summary/account written fresh in English, icons, licence note, download URLs.
3. **Merge**: `python3 tools/merge.py` → `data/catalog.json` (order from the index pages, families, the "type year").
4. **Collect binaries**: the download ZIPs go in `raw/archives/`, photo research results in `raw/photos/*.zip`. On a Mac these come through a browser download.
5. **Build**: `python3 tools/build.py` → `site/`. It extracts the archives into `fonts/`, analyses every font file with fontTools, places photos, writes pages, and rewrites `data/build-report.json`.
6. **Host**: `python3 tools/hosted.py` → `hosted/`, then publish (see the handoff).

## Running it as an Elephant–Goldfish design

[EGM](https://github.com/google/elephant-goldfish-model) (Google, Apache-2.0) splits design from review:

- **Elephant:** one long-context session designs and writes the doc, and writes no code.
- **Goldfish:** fresh zero-context reviewers attack the doc before any code is written.

In Claude Code it installs as a plugin:

```
claude plugin marketplace add google/elephant-goldfish-model
claude plugin install egm@egm
```

The flow:
1. `/egm:egm-brainstorm` → `concepts_brief.md`
2. `/egm:egm-draft` → `design_draft.md`
3. `/egm:egm-review` → five reviewer passes

Where the plugin cannot be installed (as in the cloud session of 28 Oct), do the same by hand: spawn fresh subagents that get file paths and the brief, never your conclusions.

**Suggested brief:** "Make tools/ archive-agnostic. Every seam in docs/REUSE.md moves to archive.toml or rules.py. The Wiegel build must stay byte-identical. Acceptance: hosted.py output hashes unchanged."
