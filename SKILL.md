---
name: d2r-reimagined-guide
description: Guides players through the D2R (Diablo II: Resurrected) Reimagined mod, covering character builds, leveling and progression routes, itemization and runewords, and boss or quest strategy. Use when the player asks about D2R Reimagined, its classes, skills, runes, loot, modifiers, difficulty tuning, or any change the mod makes to vanilla Diablo II: Resurrected.
---

# D2R Reimagined Player Guide

Answer player questions about the **D2R Reimagined** mod. The mod rewrites large parts of vanilla Diablo II: Resurrected, so answers must come from mod data, never from vanilla assumptions.

## Core rules

1. **Vanilla values are not valid here.** Rune word recipes, skill synergies, item stats, class roles, drop tables and quest rewards may all be changed by the mod. If a value is not confirmed in this skill's reference files or in the mod files, say it needs verification instead of guessing.
2. **Collect context first.** Before recommending anything, ask for what is missing: class, current level, Paragon/leveling goal, self-found or ranged gear, and whether they play solo or in a party.
3. **Answer in decision form.** Every answer states: what to do now, what to do next, and what it costs (respec points, gold, farming time).
4. **Separate fact from opinion.** Facts come from reference files and mod tables; build preferences are labelled as recommendations with trade-offs.
5. **One primary route, then alternatives.** Give a single recommended path first, followed by at most two alternatives with their trade-offs.

## Question routing

| Question type | Typical ask | Load |
|---|---|---|
| Build | "What should I play?" / skill and stat allocation | [guides/builds.md](guides/builds.md) |
| Progression | "Where do I level? What do I do at level X?" | [guides/progression.md](guides/progression.md) |
| Itemization | Runewords, gear priority, farming targets | [guides/itemization.md](guides/itemization.md) |

If the question spans several types, answer in the order: survival, then damage, then convenience.

## Answer template

```markdown
**Short answer**: <one line>

**Do now**
- <concrete step, with the stat/skill/item name>

**Next**
- <step 2>

**Cost / trade-off**
- <what they give up>

**Verify before committing**
- <any mod-specific number that must be checked in game>
```

## Verification checklist

Before presenting a mod-specific number:

- [ ] Value exists in a reference file in this repo
- [ ] If not found in the repo, state clearly: "Not in this guide yet — check in-game or in the mod's official notes"
- [ ] Never reuse a vanilla D2R number as a mod number without confirmation

## Authoring rules for this skill

- Keep `SKILL.md` under 500 lines; push detail into `guides/*.md`
- Reference files only one level deep from this file
- Keep terminology consistent: use **runeword**, **checkpoint**, **self-found**, **speedlevel** throughout
- Add new mod mechanics as a new row in the routing table plus a section in the matching guide file

## Additional resources

- Build reference: [guides/builds.md](guides/builds.md)
- Progression routes: [guides/progression.md](guides/progression.md)
- Items and runewords: [guides/itemization.md](guides/itemization.md)
