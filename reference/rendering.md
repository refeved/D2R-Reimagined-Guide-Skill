# Rendering rules: `{key, args}` → tooltip text

The exporter finalizes every number and ships each property line as
`{key, args[]}`; `strings/<locale>.json` maps `key -> printf template`; the
website splats the args at render time. There is **no descfunc math on either
side** - if a rendered line looks wrong, the mistake is in the splatting, not in
the data. `scripts/d2r_query.py` ports these three files verbatim; read them
before changing any rule here:

| Ported from | Owns |
|---|---|
| `upstream/website/src/utilities/strip-gender-tags.ts` | `[ms]/[fs]/[pl]` variants |
| `upstream/website/src/utilities/format-template.ts` | token set, range collapsing, indexed args, decimals |
| `upstream/website/src/lib/i18n.ts` | `t()` / `line()` / `skillLine()`, decorative suffixes, special keys |
| `upstream/website/src/lib/skill-points.ts` | hard/bonus split and axis selection |

## 1. Order of operations

1. Load the locale table once and strip gender tags from **every value** (done at
   load time, not per line): a value starting with `[` becomes its first non-empty
   segment.
2. Resolve string args: `args` entries that are **strings** are themselves
   translation keys - look them up, then use the result as the `%s` payload.
   Numbers stay numbers.
3. `prepareSpecial(key, template, args)` for the two keys below.
4. `formatTemplate(template, args)` - sequential splat with range collapsing.
5. Append decorative suffixes (`perLevel`, `qualifier`, `classOnly`), then wrap
   for set bonuses (`itemsRequired` / `fullSet`).

Skill lines insert one extra step before 2: pick the numeric values off an axis
(§4), swap in `pluralKey` when the first number is not exactly `1`, then trim the
value list to what the template can actually place (§5).

## 2. Tokens

`%%` literal percent · `%d`/`%D`/`%i` decimal · `%+d` signed decimal ·
`%s`/`%S` string · `%0`..`%9` indexed positional (cross-language word order) ·
`%c1`..`%c9` D2R colour codes, stripped. A missing arg leaves the token visible in
the output - that is deliberate, so gaps stay loud instead of printing `0`.

`%d` is D2's own token for fractional values ("Mana Cost: 2.5",
"+0.375% Deadly Strike"), so integers print bare and everything else keeps up to
15 significant digits. **Never round or truncate a rendered value.**

## 3. `[min, max]` range collapsing

Ranged properties ship **two args per ranged value** (`strModEnhancedDamage`
args `[150, 250]` → "+150-250% Enhanced Damage"); the exporter drops the second
arg when both endpoints are equal, so a surplus count is what tells the renderer
to pair. `pairBudget = max(0, min(len(args) - len(sequentialTokens), numericCount))`
and only the **leading** numeric tokens get to consume a pair - that is why
"Level %d %s …" with `[min, max, skillName]` renders correctly whether or not the
value is a range. The max half of a `%+d` range never carries its own sign.

Indexed templates resolve logical slots first (`resolveIndexedArgs`), otherwise
`%1` would read the far half of `%0`'s range.

Consequence for hand-written prose: an extra number in `args` is not a bug and
not a second stat to quote - it is the high end of a roll.

## 4. Skill axes

`skillLineNumbers` picks one axis per line, then **clamps every index to the last
element of its table**, because the exporter trims constant tails:

| Member | Index | Present when |
|---|---|---|
| `valuesUlvl` | `[skillLevel-1][characterLevel-1]` | formula reads `ulvl` |
| `values2d` | `[hardPoints][bonusLevels]` | formula reads `blvl` |
| `values` | `[level-1]` where `level = hard + bonus` | always written |

Priority is exactly that order; `values` stays populated even when a 2-D axis
exists, so an old consumer keeps rendering (for `valuesUlvl` it is solved at the
**maximum** character level). `characterLevel` omitted means "highest level the
export covers". `values2d` row `0` is real data: an item-granted oskill has no
hard points and the game renders it as all-soft.

Hard points are not soft points - `blvl` is spent points, `lvl` includes gear,
and Reimagined uses the difference as a mechanic (`Fire Mastery`,
`Titans Covenant`, `Valkyrie`), so a single effective-level table overstates a
geared character. Cap constants: `HardPointCap` = the skill's own `maxlvl`,
bonus axis runs to `SKILL_LEVEL_CAP` (100, a site-side constant until the export
carries one), and hard points win when the total is reduced.

## 5. Templates that lost a line

`countNumericSlots(template, stringArgs)` counts placeable numeric slots;
`skillLine` passes only `numbers[:slots]`. A few mod templates have fewer slots
than the data supplies (a "Defense: %d" that lost its companion AR line) and
without the trim the surplus is absorbed as a `[min, max]` pair, printing
"Defense: 25-35" for two unrelated numbers. So a template may legitimately show
less than the row's `values` - quote both when it matters.

## 6. Decorative suffixes

Appended, in this order, each resolved as a translation key:

- `perLevel: true` → `strPerCharacterLevelSuffix`
- `qualifier` → `weapon` `strRuneScopeWeapon`, `shield` `strRuneScopeShield`,
  `armor` `strRuneScopeArmor`
- `classOnly` → the member's own value is a key, appended after a space
- `itemsRequired` → wrapped in `strPartialSetBonus` as `[line, count]`
- `fullSet` → wrapped in `strFullSetBonus` as `[line]`

Two keys need `prepareSpecial` because their template and their args disagree:

- `healperhit` is label-only in every language while its catalog row still carries
  a `[min, max]` pair → prefix the template with `"%d "`.
- `strSkillRandomFromSkillClass` merges the first pair into `min-max` text itself;
  if fewer than two args remain, the trailing `%s` is dropped from the template.

## 7. Roll shapes in `args`

From `upstream/export-tool/docs/WEBSITE-INTEGRATION.md`: damage minimum and
maximum are independent components and keep **two slots even when equal**.
Paired components that each roll use four slots,
`[minimumLow, minimumHigh, maximumLow, maximumHigh]` - templates
`strFireDamageRolls`, `strColdDamageRolls`, `strLightningDamageRolls`,
`strPoisonDamageRolls`, and `strElementalDamageRange` for equipment summaries.
**Poison adds duration in seconds as a fifth argument.**
`strDurabilityRolls` carries current and maximum bounds as four args;
`strDurabilityBonus` is flat. Cold/poison duration lines use native
`StrSkill13`/`StrSkill20` with frames divided by 25, keeping fractions. These are
finalized display values, not calculation inputs.

## 8. Locale resolution

The website resolves a key as `active[locale] → UI_STRINGS[locale] →
UI_STRINGS.enUS → fallback(enUS) → raw key`. `UI_STRINGS`
(`upstream/website/src/utilities/ui-strings.ts`) is site chrome baked into the app,
and it is also the **only** place a few tooltip wrappers exist:
`strPartialSetBonus` (`%s (%d items)`), `strFullSetBonus` (`%s (full set)`),
`strItemsCount`. Without that layer a set bonus would render as the bare key and
lose the bonus text, so the script parses `ui-strings.ts` at run time
(`load_ui_strings()`, standard-library `ast.literal_eval`) and keeps the same chain -
nothing is copied into this repository. `strings <key>` marks such keys
`[site UI_STRINGS only, absent from strings/<locale>.json]`; if the file is ever
missing, the renderer degrades to `active → enUS → raw key` and reports the miss.

29 keys exist **only** in enUS (`status` prints the list) - loot-filter labels
such as `Jewel Pliers`, `Keychain`, `Gem Bag`, plus the short codes `bpl`, `hpf`,
`mpf`. Nothing exists only outside enUS. Unresolved keys are reported on stderr by
every command that renders (`note: N translation key(s) absent in <locale>`);
reporting a raw key is a **translation gap**, never a wrong item name.

Placeholder census over enUS: `%d` 398, `%+d` 272, `%%` 262 occurrences across 250
keys, `%s` 76, one indexed pair (`%0`, `%1`) for Slavic word order.

## 9. Cube recipe identity

`Id` is not the engine row. Per `WEBSITE-INTEGRATION.md` (implemented in
`upstream/export-tool/D2RMultiExport.Lib/Import/CubeRecipeImporter.cs`): take the raw typed
`cubemain.txt` cells `class, op, param, value, input1..input7` (trimmed, empty
strings and original case kept), join with U+001F, hash the UTF-8 bytes with
FNV-1a 64-bit (offset `0xcbf29ce484222325`, prime `0x100000001b3`, unsigned wrap),
emit `cr-` + 16 lowercase hex digits; first collision wins, later rows get `-2`,
`-3` in file order. Test vectors: FNV-1a of `a` = `af63dc4c8601ec8c`; empty
class/op/param/value with inputs `amu`, `ka3` = `cr-8a68ef961baebb59`. Never mint
an id starting with `#` or `restored-` (reserved for the website). Saved build links
key on `Id` and fall back to `#<Index>`; `upstream/website/src/lib/cube-recipe-ids.ts`
resolves old keys through `src/lib/data/cube-recipe-aliases.json` (2012 historical row
numbers, `basis: 2edc09fe4ab877d1`), which is frozen compatibility data, not a
per-export migration.

## 10. What the script prints for a skill

`skill` labels the provenance of every line so a reader can tell what is static:
`axis=` which table was read, `scale`/`scaleCalc` (which `*SymPerCalc` percentage
applies), `valuesCalc` (arg reads another skill's allocation), `selection` and
`classOnly` are echoed as annotations, and the raw `Calculation` cell is printed
verbatim. Explicit `--hard`/`--bonus` pass through the site's own
`clampSkillPoints`, and the header reports the move
(`hard 25 + bonus 75 = level 100  (clamped bonus 100 -> 75)`); `--hard 0` renders as
`hard 0 + bonus 1`, the item-granted-oskill case. `scale`/`scaleCalc`/`valuesCalc`
need a live rank map (`upstream/website/src/lib/skill-calculation.ts`, planner page
`/data/skills`) that this repository does not run - treat the printed numbers as the
exported baseline and point at the planner for the live value.
