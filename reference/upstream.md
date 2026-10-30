# Syncing and validating the upstream bundles

This repository stores **no game data**. The official content arrives through a
Zephyr **west** workspace, and everything under `upstream/` is git-ignored,
read-only reference material owned by the D2R-Reimagined organisation.

## 1. Workspace layout

`.west/config` and `west.yml` are committed, so the repository **is** the west
workspace: `.west/config` declares `path = .`, `file = west.yml`.

```ini
[manifest]
path = .
file = west.yml
```

**Never run `west init` here** - it wants an empty workspace and would rewrite the
manifest. A fresh clone needs only:

```powershell
pip install west                        # PyPI package `west` (Zephyr meta-tool)
python -m west update                   # ~195 MB into upstream/
python scripts/d2r_query.py integrity   # must end in a green verdict
```

`python -m west` is used everywhere because a pip-installed `west.exe` often lands
outside `PATH` (Scripts folder not registered); `west --version` then fails while
`python -m west --version` reports `West version: v1.5.0`.

## 2. The three projects

| Manifest name | Path | Revision | Size | Owns |
|---|---|---|---|---|
| `wiki-content` | `upstream/wiki-content` | `main` | 149 MB | wiki prose + ~530 images |
| `d2r-reimagined-website` | `upstream/website` | `master` | 38 MB | `static/data/` bundles + the renderer/calculators |
| `d2r-multi-export-tool` | `upstream/export-tool` | `main` | 7 MB | `docs/` field semantics + the exporter itself |

All three come from one remote, `https://github.com/D2R-Reimagined`, declared as
manifest default `remote: d2r-reimagined`. Consequence: inside each synced project
**the remote is named `d2r-reimagined`, not `origin`** -
`git -C upstream/website log d2r-reimagined/master` is the working form.

## 3. Shallow clones and HEAD state

- `clone-depth: 1` in `west.yml` is the manifest key for shallow cloning, and it
  applies **only on the first clone** of a project.
- `west update` has **no `--depth` option**; `-o/--fetch-opt` passes extra flags to
  `git fetch`, so a re-fetch stays shallow with `west update -o=--depth=1 -n`.
  `-n/--narrow` pairs with it: fetch only the manifest revision and skip `--tags`
  (with a SHA revision some hosts reject it). `-f/--fetch smart` is the default and
  skips fetching when the manifest revision is already a SHA; this manifest names
  branches, so every update does fetch.
- After an update each project sits on a **detached HEAD** at the manifest revision
  (that is west's default checkout mode); `--rebase`/`--keep-descendants` only matter
  if a branch was checked out deliberately. `scripts/d2r_query.py status` reads
  `.git/HEAD` directly (loose ref, else `packed-refs`) and prints `detached @
  5c9e81794` style lines - use them as the sync fingerprint when comparing sessions.
- Updating is idempotent: `west update` fast-forwards only what moved. Do not
  rebase, commit, stash or clean inside `upstream/`; local edits there are reference
  noise that the next update silently discards.

## 4. Integrity: what `integrity` actually proves

`manifest.json` (schema 2) lists 886 `Files[]` entries with `{Path, Bytes, Sha256,
Producer}` and never lists the manifest itself. `integrity` compares the synced tree
against that list in both directions and classifies each file:

- **exact match** - bytes and SHA equal as stored;
- **EOL-only** - the payload differs solely by CRLF↔LF; currently the 5
  `extras/*.txt` reports, because this machine has `core.autocrlf = true`;
- **failure** - anything else, plus declared-but-missing and present-but-undeclared.

The current sync is 881 exact + 5 EOL-only + 0 missing + 0 undeclared. Two rules
follow from this:

1. Always normalize CRLF→LF before hashing or byte-comparing an exported file, or
   `core.autocrlf` produces false alarms on every text file.
2. A passing hash proves the file is the file the exporter wrote. It proves
   **nothing** about which mod version that was, or whether the data is current -
   see [gaps.md](gaps.md) §1.

## 5. PowerShell notes on this machine

- `&&` is not a statement separator in Windows PowerShell 5.x; use `;`.
- `python script.py 2>&1` turns the script's stderr lines into PowerShell
  `NativeCommandError` records. Run without redirection, or read `$LASTEXITCODE`
  instead of the error stream.
- A GBK console renders the script's UTF-8 output as mojibake. The bytes are
  correct; fix the terminal: `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8`.
- Non-ASCII filenames print with octal escapes (`\345\215\260…`); set
  `git config core.quotepath false` for readable Chinese names.

## 6. When something looks missing

1. `python scripts/d2r_query.py status` - are all three projects synced, is every
   manifest step `Written`, what do the bundles count?
2. `python scripts/d2r_query.py integrity` - is the tree byte-true?
3. Read `upstream/website/static/data/extras/*.txt` - the exporter's own diagnosis
   (`import-report`, `casc-fallback-report`, `missing-translations`, `asset-report`,
   `source-report`).
4. Read [gaps.md](gaps.md) - most "missing" content is a documented boundary.
5. Only then suspect the sync: `python -m west update` again, and if a project is
   genuinely broken, `python -m west update -o=--depth=1 -n` after deleting its
   folder.
