# tools/

| File | Does | Run |
|---|---|---|
| `merge.py` | Extraction slices (`data/parts/*.jsonl`) + photo research → `data/catalog.json`. Order, sections, prev/next from Wiegel's index pages; families; the typeface's year. | `python3 tools/merge.py` |
| `build.py` | `catalog.json` + `raw/archives` + `raw/photos` → `fonts/`, `site/`, `data/build-report.json`. Analyses fonts (fontTools), cuts the feature-chip sprite, writes every page. | `python3 tools/build.py` (Mac; needs the raw files) |
| `hosted.py` | Imports `build.py`; writes `hosted/` for the claude.ai artifact: one face per font, `font.html#slug` + `pages/pN.json`, photos 1600 px. Works without raw files (falls back to `build-report.json`). | `python3 tools/hosted.py` |
| `static/app.css` | All styling. Tokens in `:root`; the "smallest text" block at the end wins by source order. | — |
| `static/app.js` | All behaviour: font loading (`fetch` + `FontFace`), list and filters, fitting, pill ink-centring, colour pairs, hosted font shell. | — |
| `static/people/` | Portrait(s) for the About page, copied to `assets/people/`. | — |

Rules for changes: [../docs/RULES.md](../docs/RULES.md). Publishing loop: [../docs/handoff/HANDOFF.md](../docs/handoff/HANDOFF.md).
