# What the official bundles cannot answer

Read this before writing "there is no X in the mod": most apparent gaps are
documented boundaries of the export, not missing content. Every item below was
verified against the synced bundles; `west update` can shift the counts, so
re-check with `python scripts/d2r_query.py status` and `integrity`.

## 1. Version markers disagree with the wiki

`upstream/wiki-content/latestversion.txt` says `3.0.4 (March 11, 2026)` while
`Patch_Notes/3-1-0.html` is dated 2026-10-29 and titled "Patch 3.1.0" - `status`
prints this as a `CONFLICT` line. **Never quote `latestversion.txt` as the current
version.** Newest = highest-numbered `Patch_Notes/<version>` page by its `date`
metadata. Manifest hashes only prove the synced bytes match each other; they say
nothing about freshness, and nothing about which mod version produced them.

## 2. Skill numbers that need a live game

The exporter evaluates only `Difficulty` (fixed to the configured branch, Hell),
`ulvl`, minion-level `sklvl` and `mps`. It cannot resolve (`SKILL-CALCULATIONS.md`):

- `sctk` - the channeling tick, derived from cast rate, which the export does not model;
- `rand(a,b)` - rolled per cast, deliberately failing so nobody exports a fake average;
- the **seven** other `cond` conditions that interrogate a live unit (`Difficulty` is
  the only one of BBE's eight a static export can answer).

`Calculation` cells are therefore shipped raw; `scripts/d2r_query.py` prints them
verbatim and runs no evaluator. The website's planner
(`src/lib/skill-calculation.ts`, page `/data/skills`) resolves them with a live rank
map, and it has its own blind spots (`upstream/website/docs/SKILL-PLANNER.md`):
`valuesCalc` cells using `pstN`/`astN` (skills.txt `passivecalc`/`aurastatcalc`),
`pnma`/`pxma`/`edmn`/`edmx` (damage columns), `sklvl(...)` of a skill outside the
export, or `miss(...)` (missiles.txt) keep the no-other-points table. So a synergy
line can legitimately ignore how many points the other skill has.

Description text is fixed to Hell: there is no difficulty axis in
`Descriptions`, so never present a Normal/Nightmare figure from this bundle.

## 3. Drop rates, monster life, IAS results

The bundles are **inputs**; all three calculators compute on the website and their
output is not in this repository:

- **drops** - `src/lib/drop-calculator.ts` (item → sources) and
  `monster-drop-calculator.ts` (source → loot table) in browser Web Workers,
  page `/data/drop-calculator`. Their stated assumptions:
  `QuestFlagEx` conditions assumed met, monsters ordinary and non-terrorized,
  quest-boss quest drops active, no unique already dropped this game, item level =
  exported monster level (no separate area-level input), and rare/magic quality,
  affixes, gold and stack sizes are not modeled - a failed unique or set roll counts
  as a miss, not a downgraded item.
- **monster life** - "the exporter does not pre-compute HP"
  (`export-tool/docs/HEALTH-CALCULATOR.md`); synthesis is
  `src/lib/health-calculator.ts`, page `/data/health-calculator`.
- **attack speed** - the exporter solves the 100-level speed curves, but the integer
  frame simulation (`src/lib/ias-calculator.ts`, page `/data/ias-calculator`) does
  the two-stage diminishing arithmetic. Unsolved curves are `null` and reported in
  `extras/import-report.txt` with a `CalcTrace` root cause - never silently zero.

`drop` and `monster` in `scripts/d2r_query.py` therefore print raw contributions
plus the disclaimer. Quote eligibility and gates, then send the player to the
calculator for a percentage.

**"Unavailable" is not 0%.** `ConditionRuntime: true`, an unrecognized condition or
any unsupported expression stays unavailable (`DROP-CALCULATOR.md`); treating it as
false or zero is the single most common wrong answer about this mod.

## 4. Rows that exist in one bundle and not another

- 29 of the 1442 `uniques.json` rows are `Enabled: false` (retired or disabled
  entries; `runewords.json` has none).
- 22 uniques have **no** `drop-calculator.json` `Items[]` row: dev/test entries
  (`Thunderstep Test Staff`, `t2`-`t7 Splash Charm`), quiver/bolt-case variants and
  `Barilzar's Mazed Band`. Absent there means the drop tool does not list them, not
  that the item cannot exist.
- The set `Warlord's Glory` (5 pieces) has no drop `Items[]` row either; its
  namesake piece `Warlord's Pike` belongs to `Talonrage's Fury` and does drop.
- `SetItems[]` rows carry **no** `Enabled` member (only unique rows do) and set
  parents have no `ItemLevel` of their own beyond the legacy `1`.
- Runewords are crafted, not dropped: only 4 of 220 have a `unique:` row in the drop
  bundle, and each of those is a name collision with a unique item
  (`Serendipity`, `Voice of Reason`, `Crescent Moon`, `Sanctuary`). Never answer
  "where do I farm <runeword>" from `drop`.
- Every `Items[]` row has an empty `Condition`, and named (unique/set) items appear
  in **no** `TreasureClasses[].Entries` - quality rolls, ilvl and rarity gate them.
- In `cube-recipes.json`, `NumInputs > ResolvedInputsCount` marks a recipe that
  references codes the data does not carry.

## 5. Translation, name and art boundaries

- 13 locales, enUS 6235 keys, every other locale 6206: **29 keys are enUS-only**
  (loot-filter labels such as `Jewel Pliers`, `Keychain`, `Gem Bag`, and the codes
  `bpl`, `hpf`, `mpf`). Nothing exists only outside enUS.
- A few tooltip wrappers are not translation-table content at all:
  `strPartialSetBonus`, `strFullSetBonus` and `strItemsCount` live only in the site's
  `src/utilities/ui-strings.ts`. They are read from there at run time - if `upstream/`
  is not synced, set bonuses lose their "(N items)" wrapper.
- 11 keys fall through to the CASC base strings because the mod does not ship them
  (`extras/casc-fallback-report.txt`): `Nihlathak`, `fire`, `StrSkillRunWalkRange`,
  `SkillNameCubeLoot`, `SkillNameEmoteWheel`, `SkillNameInteract`, `SkillNameLoot`,
  `SkillNameMap`, `SkillNameRunToggle`, `SkillNameShowItems`, `SkillNameSwapWeapons`.
  `extras/missing-translations.txt` lists 0, so a raw key is one of these cases.
- 1314 named item variants are drawn with base artwork
  (`extras/asset-report.txt`, 0 unresolved, 0 collisions). A unique looking like its
  base in-game is expected, not a bug.
- Names move between versions: vanilla `Thunderstrike` and `Stormfire Chained` do not
  exist here, and the Chinese `悔恨` resolves to the mod's unique `Ruemonger`. Search
  both languages (`find <term>`, `strings <key> --locale zhCN`) and quote the
  `Index` (the engine-side English name) next to any translated name.
- 26 of the 220 runeword rows are addressed by a row identifier whose player-visible
  name is different: `Black1` → `Black` (zhCN 黑锤), `Steel1` → `Steel`,
  `Runeword180` → `Coven`. The vanilla name may simply be gone (there is no
  `Blackout`), so `runeword Blackout` correctly finds nothing while
  `find Black` shows the row. `runeword`/`find`/`runeword --list` print
  `Index (display)` whenever the two differ.
- `Type` / `Types[].Index` / `EquipmentType` hold itemtypes codes that are also
  translation keys; internal identifiers like `Bow 1` or `of Cinders` are names, not
  missing translations.

## 6. Prose gaps in `wiki-content`

- 90 `.html` + 36 `.md` pages: **84 html pages have no `.md` twin** and 30 `.md` have
  no `.html` twin. Class pages (`Amazon.html` … `Warlock.html`), `Patch_Notes` 2-x and
  the `Items/*` pages are html-only. Index both or you will "find" nothing.
- **No Warlock builds.** `Builds/` holds 7 class folders (Amazon, Assassin, Barbarian,
  Druid, Necromancer, Paladin, Sorceress) and `Builds/Warlock.html` is a 217-byte empty
  index; the class's changes page (root `Warlock.html`, 3088 bytes) exists. Say the
  write-up does not exist and build the answer from `skills`/`runeword` data instead.
- `Items/Runes.html` is a rune list: only a handful of the 220 runewords appear in it.
  Use `runeword --list` for the catalog.
- Install directories (`installguides/`, `easyinstall/`, `newbieguide/`,
  `qualityupgrading/`, `Items/*/`, `DesktopLauncher/`) are image dumps with no step
  text; the instructions live inside the screenshots, so they are not queryable here.
- `recipes/*-old.md` are superseded; `wiki` excludes them unless `--include-old`.
- Community builds under `Builds/` are player-authored prose: their numbers lag the
  data. Quote them as opinion, verify every figure with a command.
- Server-side features of the website (ladders, characters, trade, saved builds,
  global chat) are app data behind authentication: nothing in these bundles describes
  a player's progress.

## 7. Nothing here is hand-written

This repository stores no game data of its own; if a question needs a fact that none
of the commands and pages produce, the correct answer is "the official data does not
cover that - verify in-game", with the specific reason quoted from this file.
