---
name: d2r-reimagined-guide
description: Answers Diablo II: Resurrected Reimagined mod questions strictly from the mod's own official data - runewords, unique and set items, cube recipes, Horadric crafting, skill numbers and synergies, drop eligibility, monster stats, IAS frames, loot filters, patch notes, class changes, build and progression advice. Use whenever the player asks about D2R Reimagined, its classes, skills, runes, items, modifiers, farming targets or difficulty tuning, or about any change the mod makes to vanilla Diablo II: Resurrected. Handles English and Chinese (zhCN) item and skill names.
---

# D2R Reimagined Player Guide

Answer player questions about the **D2R Reimagined** mod using only the official
data that `west update` syncs into `upstream/`. The mod rewrites large parts of
vanilla Diablo II: Resurrected, so a vanilla number is never a valid answer, and
this repository holds **no hand-written game data of its own**.

## The three official sources

| Repo (under `upstream/`) | Owns | Never use it for |
|---|---|---|
| `website/static/data/` | every number: uniques, sets, runewords, cube recipes, skills, drops, monster life, IAS, loot filters, localized names | narrative strategy, patch history |
| `wiki-content/` | prose: patch notes, class changes, community builds, FAQ, map/crafting guides | exact values (tables there are hand-copied and lag) |
| `export-tool/docs/` | field semantics and calculation contracts, engine row rules, known export limits | game content itself |

Doubt between sources: the keyed JSON wins. It is generated from the mod's own
`.txt` tables.

## Prerequisite

```powershell
python scripts/d2r_query.py status
```

Reports what is synced, what the export manifest claims, and the version markers.
If `upstream/` is missing, run `python -m west update` (see
[reference/upstream.md](reference/upstream.md)) before answering anything.

## Question routing

| Player asks | Run | Then read |
|---|---|---|
| Any number, name or recipe, exact value wanted | `find <term>` to locate it, then `item` / `runeword` / `skill` / `cube` | [reference/rendering.md](reference/rendering.md) |
| "What does this rune-word need?" / rune order, valid base | `runeword <name>` (`--list` to browse) | reference/rendering.md |
| Skill damage, mana, duration, synergy at a rank | `skill <class> "<name>" --rank 40` (`--hard`/`--bonus`/`--ulvl`) | reference/rendering.md |
| Cube / Horadric crafting, upgrade or enchant recipe | `cube <item or cr-id>` | reference/data-map.md |
| "Where do I farm X?" / drop gates, treasure classes | `drop <item>`, `drop --source <monster>`, `drop --tc <name>` | reference/gaps.md |
| Monster life, resistances, boss stats | `monster <name>` | reference/data-map.md |
| Class changes, patch history, build write-ups, strategy | `wiki <term>` then `wiki --show <path>` | [reference/data-map.md](reference/data-map.md) |
| Which version is current? | `status` (the version marker is unreliable, see gaps.md) | [reference/gaps.md](reference/gaps.md) |
| English/Chinese term mapping | `strings <key> --locale zhCN` or any command with `--locale zhCN` | reference/rendering.md |
| Is the synced data byte-true? | `integrity` | [reference/upstream.md](reference/upstream.md) |

Commands live in `scripts/d2r_query.py`; `python scripts/d2r_query.py --help` and
`<subcommand> --help` list every flag. Pass `--locale zhCN` before or after the
subcommand; Chinese names are searchable (`item 悔恨`, `find 凤凰`).

## Answer template

```markdown
**Short answer**: <one line, with the exact figure or item name>

**The numbers** (<source: keyed JSON record / wiki page>)
- <rendered line from the data, verbatim>

**Do now** -> <step>
**Next**    -> <step>
**Cost**    -> <respec points, gold, farming time>

**Caveats**  -> <anything the bundle cannot answer, quoted from reference/gaps.md>
```

Prefer one recommended route, then at most two alternatives with their
trade-offs. Answer in the order: survival, then damage, then convenience.
Separate fact from opinion: figures come from the data, build preferences are
labelled as recommendations.

## Hard rules

1. **Never invent or recall a mod value.** Only quote what a command printed, a
   wiki page states, or an official doc defines. No number at all beats a wrong
   one.
2. **Never recompute an official algorithm.** Drop probability, monster HP, IAS
   and BBE skill formulas are computed by the website at run time. Report the raw
   contributors and point at the online calculator.
3. `ConditionRuntime: true`, an unrecognized condition, or any unsupported
   expression stays **unavailable - never false and never 0%**
   (`export-tool/docs/DROP-CALCULATOR.md`).
4. In `drop-calculator.json`, every `Items[]` row has an empty `Condition`, and
   named (unique/set) items appear in **no** `TreasureClasses[].Entries`: they are
   gated by quality rolls, ilvl and rarity, not by TC membership.
5. A set parent's `ItemLevel: 1` is a legacy placeholder (`sets.txt` has no `lvl`
   column). Quote the individual `SetItems[]` levels instead.
6. `args` / `values` are finalized values. Do not round them to make prose
   prettier; `24.5` mana cost and `0.375` per-level growth are exact.
7. Identifiers are **engine row indexes**: only a source line whose first cell is
   exactly `Expansion` is dropped, and the informational `*Id` / `*hcIdx` columns
   are never used (they drift on hundreds of rows).
8. Manifest hashes prove the bytes match each other, nothing more - not the
   source version, not freshness. Check the actual patch-note page for a version.
9. Never write to, reformat or add files under `upstream/`; it is a synced
   dependency. Never add hand-written game data to this repository either.
10. Missing `NameKey` means "no translation", not "name unknown": render the row's
    `FallbackName`. Internal identifiers such as `Bow 1` or `of Cinders` are names,
    not translation gaps. A row's `Index` may itself be an identifier whose visible
    name differs (26 runewords, e.g. `Black1` → Black / 黑锤); the commands print
    `Index (display)` - quote both.

## Windows console note

The script writes UTF-8. On a GBK codepage PowerShell shows Chinese as mojibake;
fix the terminal, not the data:

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
```

## Additional resources

- Which file holds what, with exact fields and counts: [reference/data-map.md](reference/data-map.md)
- How `{key, args}` lines become tooltip text, axis rules: [reference/rendering.md](reference/rendering.md)
- What the official data cannot answer: [reference/gaps.md](reference/gaps.md)
- west workflow and the three dependencies: [reference/upstream.md](reference/upstream.md)
