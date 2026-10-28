# Font page redesign: handoff to the build agent

Made 28 Oct 2026 with Okay in a design session (mock: `Font Page.dc.html`, Varieté). Okay has signed it off. **Every item below changes rendering** (Okay's go is given here). Apply it in `tools/build.py` (`font_html`, `strip_html`, `page`) and `tools/static/app.css` / `app.js`, then update `docs/RULES.md` with the "Rules" section below.

Do **not** port the placeholder data used to fill the mock (see the end of this file).

---

## 1. Top bar: third row on font pages, styles + prev/next

- The second row (`.nav2`) is unchanged: name · family pill · section pills.
- **New third row** directly under it, inside `.top` (so it is sticky with the bar):
  - Left: one pill per style in the download (the family's members), `flex: 1 1 0; min-width: 0; display: flex; flex-wrap: wrap; gap: 8px`.
    - Label = style name only, the family name stripped ("Artist", "Cabaret" …). The base face keeps the full name ("Varieté").
    - Pill style = `.nav2 a` (outline in currentColor, 40% ink). The **current style is filled** like `.crumb`, but at full opacity: `background: var(--navfg); color: var(--navbg)`.
    - Clicking a pill swaps the specimen face (what the `#style` select did: `load(F[n])` → `applyFace(); fitBlocks(); drawGlyphs()`).
  - Right: prev/next pills (the current `.pnav` links, same style and arrows), `flex: none; white-space: nowrap; gap: 8px`.
  - Row: `display: flex; align-items: flex-start; gap: 8px 24px; padding: 12px 0 14px`, with **no rule under it** (the rule under row 2 stays).
  - Many styles **wrap** to second and third lines on the left. Prev/next stay top-right. No horizontal scroll on this row.
- **Remove** `.pnav` from the top of `.sheet`, and **remove** the Style `<select>` (`.opts`) from `.tools`.
- The first `.blk` keeps `padding-top: calc(var(--st) * 2)`, now measured from the bar.
- `--navh` already follows the header height through the ResizeObserver. Sticky `.lab` (`top: calc(var(--navh) + 16px)`) and `.gblock .vlab` follow it automatically; check them with three wrapped style rows.
- The fade under the bar (`.top::after`, 36px gradient, shown on `.scrolled`) stays as is.

## 2. Specimen sheet: the info line under the tools

- The `.fhead` kicker (number · family · years) and the icons row **are removed** from the sheet. `.fhead` stays only as spacing (`padding: var(--st) 0 var(--sbt)`), or can go if nothing else lands there; check the gap to the Timeline rule.
- The feature chips move to Facts (§4).

## 3. Timeline section

- `.sec` for Timeline gets the normal `border-top` (`.sheet + .sec { border-top: 0 }` goes).
- **Axis:** the rule and tick lines must not show overlaps. Use an **opaque** mix instead of the alpha `--rule`:
  `color-mix(in oklab, var(--ink) 22%, var(--paper))` for `.axis` border-bottom and `.axis .tk::after`.
- **Gap line** (`.gap`, "N years between the original … and the digital font …"): now **smallest text**. Add `.gap` to the smallest-text block (14px, caps, `.05em`, `--ink-3`), keep `margin: 32px 0 0`.
- **Event cards** (`.evs li`):
  - No `border-top`.
  - `.y` (year): `font: var(--ui)/1.25 var(--uiface)`, coloured by lane: `var(--c)` (Type `--hot`, Digitised `--dl`, Elsewhere `--sky`). **Take `.evs .y` out of the smallest-text block**, or that block will override it.
  - `.w` unchanged (24px Proletarsk).
  - `.ln` (lane name under the sentence) **removed**.

## 4. Facts section: new order and form

Remove the `dl.facts` card grid. The section body becomes `display: grid; gap: 32px`:

1. **Licence + pills** (one group, `display: grid; gap: 4px`):
   - Licence name (`lic_name()`): `font: 400 var(--read)/1.3 var(--text)`. No "Licence" label above it.
   - Directly under it, one row of **small pills** (`.tg` style: 14px caps, `padding: 5px 10px 2px 14px`, `box-shadow: inset 0 0 0 calc(var(--info) * .105) currentColor`), `flex-wrap: wrap; gap: 6px`:
     - Fact pills first: **Family** · **Genre** · **"N styles"** · **"N characters"**.
     - Then the page's **tags**.
     - All are **links** to the font list filtered by that value (same mechanism as `index.html#ic=` / `#cv=`; tags need their own filter key). Hover inside `@media (hover: hover)`: fill `var(--ink)`, text `var(--paper)`, no outline.
2. **Feature chips grid** (moved here from the sheet):
   - `ul`: `display: grid; grid-template-columns: repeat(auto-fill, minmax(max(64px, calc((100% - 9 * 16px) / 10)), 1fr)); gap: 24px 16px`, which gives **10 across** at full width and fewer when narrow.
   - Each `li`: `display: grid; gap: 8px; justify-items: start`. Chip `icon(code, 48)`: the outline scales with the chip (rule from ICONS.md), so do not use a non-scaling stroke. Label under it in **smallest text**; two lines are fine.
- **Dropped from Facts:** Number, Original, Digitised, Source, Place / object, Designer field, Wiegel's index, Licence (page). They are shown elsewhere or are unimportant.

## 5. Mono text: Wiegel's Erika Type Bold

- The glyph-grid hex codes (`.gl .g span`, currently `11px var(--mono)`) use **Erika Type Bold** (Wiegel's `erikatype`, the bold face).
- Register it like the UI faces: `ui_font_css()` / `UIFONTS` as `"WA Mono"`, and set `--mono: "WA Mono", ui-monospace, "SF Mono", Menlo, monospace`.
- Size and caps are unchanged.

## 6. Chip mark ẞ

- In the mock, the ẞ mark looked thin because the mock drew marks as text. In the build, marks are outlines cut from the pool fonts (`icon_svgs`). **Check** that ẞ is cut from the same weight as the others (ICONS.md names DIN as its source). Only if it is still visibly lighter, pick a heavier pool font for that one mark. No stroke hacks.

---

## Rules (merge into docs/RULES.md)

- **Navigation › Font pages:** rows are (1) the bar, (2) name · family · sections, (3) styles left, prev/next flush right. Row 3 has no rule under it. Style pills wrap to more lines, and prev/next stay on the first line. The current style is a filled pill.
- **Style switching** is done only by the row-3 pills. There is no Style menu in the tools.
- **Lines:** a rule that crosses or meets another rule uses an opaque ink/paper mix, never alpha, so crossings don't darken.
- **Timeline cards:** no top rule. The year is in the interface size and in its lane colour. There is no lane label (the colour carries it). The "years between" line is smallest text.
- **Facts:** Licence (reading size) → small pills (family, genre, styles, characters, then tags; all are links) → feature chips (48px, 10 across, smallest-text labels).
- **Small pills are links** wherever they show a filterable value.
- **Mono face:** Erika Type Bold, Wiegel's typewriter face. No system monospace.
- Add `.gap` to the smallest-text block, and take `.evs .y` out of it.

## Not to port (placeholder data in the mock)

- Varieté's **original date 1928** and its Type event ("Lettering of a Berlin variety theatre poster…"). It was invented to show a two-event timeline.
- **Seven extra chips** (Capital sharp s, OpenType features, OpenType ligatures, Extended Latin, Greek, Cyrillic, Blackletter set). Varieté really has Standard layout, Euro sign and Capitals only.
- The mock's **lilac** pair for Varieté (the real pair comes from `pal_for`).
- The mock's 2-line "full" / "almost empty" info-line variants: superseded by §2.
