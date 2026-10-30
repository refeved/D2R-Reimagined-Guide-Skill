# D2R Reimagined Guide Skill

An AI agent Skill that answers player questions about the **D2R (Diablo II:
Resurrected) Reimagined** mod - runewords, unique and set items, cube recipes,
skill numbers, drop eligibility, monster stats, patch history, builds - strictly
from the mod's **own official data**.

The repository deliberately contains **no hand-written game data**. Everything
factual is synced from the D2R-Reimagined organisation by [west](https://docs.zephyrproject.org/latest/application/west_commands/index.html),
and the skill only reads, slices and renders it. English and Chinese (zhCN) names
both work.

## Layout

```
D2R-Reimagined-Guide-Skill/
├── SKILL.md                    # frontmatter, routing table, hard rules, answer template
├── reference/
│   ├── data-map.md             # which file holds what: roots, shapes, fields, counts
│   ├── rendering.md            # how {key, args} becomes tooltip text (website rules)
│   ├── gaps.md                 # what the official data cannot answer
│   └── upstream.md             # west workflow and integrity checking
├── scripts/
│   └── d2r_query.py            # read-only query tool, Python standard library only
├── west.yml                    # manifest: the three official upstream repos
├── .west/config                # workspace marker (path = .), committed on purpose
└── upstream/                   # synced official content - git-ignored, ~195 MB
```

## Setup

```powershell
# 1. install the skill (folder name must match SKILL.md frontmatter)
git clone https://github.com/refeved/D2R-Reimagined-Guide-Skill.git $HOME/.qoder/skills/d2r-reimagined-guide
cd $HOME/.qoder/skills/d2r-reimagined-guide

# 2. sync the official data (this repository is already a west workspace - do not run `west init`)
pip install west
python -m west update

# 3. prove the sync is byte-true, then look around
python scripts/d2r_query.py integrity
python scripts/d2r_query.py status
```

Use `$HOME` (PowerShell) or `~/` (bash) explicitly - a bare `~` is not expanded
before `git` sees it in PowerShell. Restart the session so the skill index rebuilds.

`python -m west` is used instead of `west` because a pip-installed `west.exe` often
lands outside `PATH`. `python` may need to be `py` or `python3` on your machine; the
script needs no third-party package.

## The query tool

```powershell
python scripts/d2r_query.py <command> [args] [--locale zhCN]
```

| Command | Answers |
|---|---|
| `status` | what is synced, manifest state, bundle sizes, locale coverage, version markers |
| `integrity` | every `manifest.json` file, byte-by-byte (CRLF-normalized) |
| `find <term>` | locate a name or code across every catalog |
| `item <name>` | one unique or set item, lines rendered |
| `runeword <name>` | runes, valid bases, properties (`--list` to browse) |
| `skill <class> <name>` | description lines at `--rank` / `--hard` / `--bonus` / `--ulvl` |
| `cube <item or cr-id>` | Horadric cube recipes |
| `strings <key>` | raw translation templates, per locale |
| `wiki <term>` | search the official wiki (`.md` and `.html`), `--show <path>` to read |
| `drop <item>` | drop eligibility and gates - never a probability |
| `monster <name>` | raw monster life contributors - never a computed HP |

It never prints a whole bundle (the largest is 5.7 MB) and never recomputes an
official algorithm; probabilities, HP and attack speed stay on the official
calculator pages.

## Data sources

`upstream/` holds three read-only clones from `https://github.com/D2R-Reimagined`
and belongs to that project, not to this repository:

- `wiki-content` - prose: patch notes, class changes, community builds, guides
- `website` - `static/data/keyed/*.json` plus `static/data/strings/<locale>.json`:
  every number, and the TypeScript that renders and calculates with them
- `export-tool` - `docs/`: field semantics, calculation contracts, export limits

Distrust the wiki when it disagrees with the keyed JSON: the JSON is generated from
the mod's own tables, the prose is hand-copied.

## Contributing

1. Never add a hand-written game-data file, and never edit anything under
   `upstream/`.
2. Quote facts from a command's output or a wiki page, and cite which.
3. Put detail in `reference/*.md`, keep `SKILL.md` short (rules and routing only).
4. Re-run `status` and `integrity` after every `west update` and refresh any count
   you cite; counts in the reference files describe the current sync, not a
   contract.
5. Keep terminology stable: *runeword*, *hard point*, *bonus level*, *treasure
   class*, *engine row*, *self-found*.

## Why the rules are strict

Most bad answers about this mod come from an assistant reusing vanilla D2R numbers
(rune-word recipes, synergies, resist caps) that the mod has changed, or from
treating an unevaluable drop condition as "0%". The skill therefore forbids
unsourced numbers and requires naming the boundary from `reference/gaps.md`
instead.

## License

No license file yet. The synced upstream content stays under whatever terms the
D2R-Reimagined project sets; add a license for this repository's own text if you
intend it to be reusable.
