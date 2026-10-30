# D2R Reimagined Guide Skill

An AI agent Skill that answers player questions about the **D2R (Diablo II: Resurrected) Reimagined** mod — builds, leveling routes, itemization and runewords.

The skill is a set of markdown files. The agent loads `SKILL.md` as its operating rules and pulls detail from `guides/*.md` only when a question needs it.

## Status

**Scaffold.** The routing rules, answer templates and data formats are written; the mod-specific data is not filled in yet. All `guides/*.md` files are marked `STATUS: scaffold` and contain `TBD` placeholders.

Until that data is added, the skill instructs the agent to refuse to guess mod numbers, so behaviour is safe but not yet informative.

## Layout

```
D2R-Reimagined-Guide-Skill/
├── SKILL.md              # frontmatter + operating rules + question routing
├── guides/
│   ├── builds.md         # build blocks, class role changes vs vanilla
│   ├── progression.md    # level route table, difficulty transitions
│   └── itemization.md    # runeword recipes and changes, farm targets
└── README.md
```

## Install

Clone or copy this repo into a skill directory, keeping the folder name equal to the skill name in `SKILL.md` frontmatter (`d2r-reimagined-guide`):

```powershell
# Personal skill (available in every project)
git clone https://github.com/refeved/D2R-Reimagined-Guide-Skill.git $HOME/.qoder/skills/d2r-reimagined-guide

# Or as a project skill (shared with anyone using that project)
git clone https://github.com/refeved/D2R-Reimagined-Guide-Skill.git .qoder/skills/d2r-reimagined-guide
```

Use `$HOME` (PowerShell) or `~/` (bash) explicitly — a bare `~` is not expanded before `git` sees it in PowerShell.

Restart the session so the skill index is rebuilt.

## Contributing data

1. Pick the guide file that matches the knowledge.
2. Copy the template block at the top of that file and fill it.
3. Record the mod version and how the value was confirmed in the **Source** field — unsourced entries get removed.
4. Keep `SKILL.md` under 500 lines: rules belong there, data belongs in `guides/`.
5. Keep terminology stable: *runeword*, *checkpoint*, *self-found*, *speedlevel*.

## Why the rules are strict

Most bad answers about this mod come from an assistant reusing vanilla D2R numbers (rune word recipes, synergies, resist caps) that the mod has changed. `SKILL.md` therefore forbids unsourced numbers and requires an explicit "needs verification" statement instead.

## License

No license file yet — add one if you intend the guide content to be reusable by others.
