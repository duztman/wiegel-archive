# data/

| File | What | Written by |
|---|---|---|
| `catalog.json` | The archive: `families` + `fonts[]` (slug, name, section/pos/prev/next, family, genre, years, origin, place, account, icons, licence, photo, found/related links, zips). | `tools/merge.py` |
| `build-report.json` | Per font: every font file with its analysed metadata (cmap, metrics, names, licence, coverage), docs and downloads. Lets copies without the raw files rebuild. **Rewritten by every full build.** | `tools/build.py` |
| `zip_urls.json`, `dl_urls.json` | Download URLs found on Wiegel's pages. | scraping (stage 1) |
| `photo_urls.json`, `photos_[abc].json`, `places*.json` | Photo and place research: freely licensed photos with author, licence, source page; sightings to link, not copy. | research (stage 2) |
| `parts/` (ignored) | Per-page extraction slices, JSONL. Not committed. | extraction agents |
| `photos/` (ignored) | Local photo cache. | — |
