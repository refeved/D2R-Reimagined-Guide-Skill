#!/usr/bin/env python3
"""Read-only query helper for the official D2R Reimagined data bundles.

The bundles are the ones `west update` syncs into `upstream/`:

  upstream/website/static/data   keyed JSON + localized strings + extras reports
  upstream/wiki-content          wiki pages (.md frontmatter / .html comment metadata)
  upstream/export-tool           field semantics and calculation contracts (docs/)

This script never invents a value and never recomputes an official algorithm. It
slices one record out of a bundle and renders it with the website's own template
rules (ported from src/lib/i18n.ts, src/lib/skill-points.ts and
src/utilities/format-template.ts; the site's UI_STRINGS layer in
src/utilities/ui-strings.ts is parsed from upstream at run time). Large bundles are
loaded lazily, only for the commands that need them, and are never printed in full.
"""

import argparse
import ast
import hashlib
import html as html_lib
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
UPSTREAM = REPO / "upstream"
DATA = UPSTREAM / "website" / "static" / "data"
KEYED = DATA / "keyed"
STRINGS = DATA / "strings"
EXTRAS = DATA / "extras"
MANIFEST = DATA / "manifest.json"
WIKI = UPSTREAM / "wiki-content"
EXPORT_TOOL = UPSTREAM / "export-tool"
UI_STRINGS_FILE = UPSTREAM / "website" / "src" / "utilities" / "ui-strings.ts"

PROJECTS = {
    "wiki-content": WIKI,
    "d2r-reimagined-website": UPSTREAM / "website",
    "d2r-multi-export-tool": EXPORT_TOOL,
}

DISCLAIMERS = {
    "drop": (
        "probabilities are NOT in this bundle: the website computes them at run time "
        "(upstream/website/src/lib/drop-calculator.ts, page /data/drop-calculator). "
        "Empty Condition on Items[] means no exported gate, not 'never drops'. "
        "ConditionRuntime/unknown conditions stay unavailable - never 0%."
    ),
    "monster": (
        "the exporter does not pre-compute HP (export-tool/docs/HEALTH-CALCULATOR.md): "
        "these are raw contributors only. Synthesis lives in "
        "upstream/website/src/lib/health-calculator.ts (page /data/health-calculator)."
    ),
    "skill": (
        "Calculation values are raw BBE source cells; this tool has no BBE evaluator. "
        "scale/scaleCalc/valuesCalc need live rank maps (website skill-calculation.ts). "
        "Description difficulty is fixed to Hell by the exporter, there is no difficulty axis."
    ),
}


def die(message, hint=""):
    sys.stderr.write("error: %s\n" % message)
    if hint:
        sys.stderr.write("hint: %s\n" % hint)
    raise SystemExit(2)


def require_upstream():
    if not KEYED.is_dir():
        die(
            "official data bundles are not present (%s)" % KEYED,
            "run `west update` in the repository root first "
            "(see reference/upstream.md; python -m west update if west is not on PATH)",
        )


# --------------------------------------------------------------------------
# bundle access
# --------------------------------------------------------------------------

_JSON_CACHE = {}


def load_keyed(name):
    path = KEYED / (name + ".json")
    if name not in _JSON_CACHE:
        if not path.is_file():
            die("missing keyed bundle %s" % path.name, "run `west update`")
        try:
            with path.open(encoding="utf-8-sig") as handle:
                _JSON_CACHE[name] = json.load(handle)
        except ValueError as error:
            die("cannot parse %s: %s" % (path.name, error))
    return _JSON_CACHE[name]


def load_strings(locale):
    path = STRINGS / ("%s.json" % locale)
    if not path.is_file():
        available = ", ".join(sorted(p.stem for p in STRINGS.glob("*.json")))
        die("unknown locale %r (available: %s)" % (locale, available))
    with path.open(encoding="utf-8-sig") as handle:
        raw = json.load(handle)
    return {key: strip_gender_tags(value) for key, value in raw.items()}


_UI_CACHE = None


def load_ui_strings():
    """Parse the website's own UI_STRINGS table, the second lookup layer it uses.

    A few tooltip wrappers (`strPartialSetBonus`, `strFullSetBonus`,
    `strPerCharacterLevelSuffix`, ...) live only in
    `upstream/website/src/utilities/ui-strings.ts`, not in `strings/<locale>.json`,
    exactly like the site's chrome. It is read from upstream at run time so this
    repository stays free of copied game text; when the file is absent the renderer
    simply falls back to enUS and reports the key.
    """
    global _UI_CACHE
    if _UI_CACHE is None:
        _UI_CACHE = {}
        if UI_STRINGS_FILE.is_file():
            text = UI_STRINGS_FILE.read_text(encoding="utf-8", errors="replace")
            start = text.find("= {", text.find("UI_STRINGS"))
            end = text.rfind("}")
            if start != -1 and end > start:
                try:
                    parsed = ast.literal_eval(text[start + 2:end + 1])
                except (ValueError, SyntaxError):
                    parsed = None
                if isinstance(parsed, dict):
                    _UI_CACHE = {
                        code: {key: strip_gender_tags(value) for key, value in table.items()}
                        for code, table in parsed.items() if isinstance(table, dict)
                    }
    return _UI_CACHE


# --------------------------------------------------------------------------
# template rendering, ported from the website
# --------------------------------------------------------------------------

SEQ = re.compile(r"%(?:\+d|d|D|s|S|i|c\d|\d|%)")
GENDER_TAG = re.compile(r"\[[a-z]{2}\]")
NUMERIC_TOKENS = {"%+d", "%d", "%D", "%i"}


def strip_gender_tags(value):
    """First non-empty variant of a `[ms]/[fs]/[pl]` tagged string."""
    if not value or value[0] != "[":
        return value
    for part in GENDER_TAG.split(value):
        if part:
            return part
    return value


def is_numeric_token(token):
    return token in NUMERIC_TOKENS


def count_numeric_slots(template, string_args=0):
    tokens = SEQ.findall(template)
    indexed = [m for m in tokens if re.fullmatch(r"%\d", m)]
    if indexed:
        slots = max([int(m[1]) + 1 for m in indexed] or [0])
        return max(slots - string_args, 0)
    return len([m for m in tokens if is_numeric_token(m)])


def format_decimal(value):
    if isinstance(value, bool):
        return "1" if value else "0"
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        return str(value)
    if number.is_integer() and abs(number) < 1e16:
        return str(int(number))
    return repr(float("%.15g" % number))


def format_arg(value, token):
    if value is None:
        return ""
    if token == "%+d":
        try:
            number = float(value)
        except (TypeError, ValueError):
            return str(value)
        return ("+" if number >= 0 else "") + format_decimal(number)
    if token in ("%d", "%D", "%i"):
        try:
            return format_decimal(float(value))
        except (TypeError, ValueError):
            return str(value)
    if token in ("%s", "%S"):
        return str(value)
    return str(value)


def resolve_indexed_args(args, slots, surplus):
    resolved = []
    position = 0
    budget = surplus
    for _ in range(slots):
        low = args[position] if position < len(args) else None
        high = args[position + 1] if position + 1 < len(args) else None
        if (
            budget > 0
            and isinstance(low, (int, float)) and not isinstance(low, bool)
            and isinstance(high, (int, float)) and not isinstance(high, bool)
        ):
            low_text = format_decimal(low)
            resolved.append(low_text if low == high else "%s-%s" % (low_text, format_decimal(high)))
            position += 2
            budget -= 1
        else:
            resolved.append(format_arg(args[position] if position < len(args) else None, "%0"))
            position += 1
    return resolved


def format_template(template, args=()):
    """Positional D2R template renderer with [min, max] range collapsing."""
    if not template:
        return ""
    args = list(args)
    tokens = SEQ.findall(template)
    sequential = [
        m for m in tokens if m != "%%" and not re.fullmatch(r"%\d", m) and not re.fullmatch(r"%c\d", m)
    ]
    numeric_count = len([m for m in sequential if is_numeric_token(m)])
    pair_budget = max(0, min(len(args) - len(sequential), numeric_count))

    indexed_tokens = [m for m in tokens if re.fullmatch(r"%\d", m)]
    indexed_slots = max([int(m[1]) + 1 for m in indexed_tokens] or [0])
    resolved_indexed = (
        resolve_indexed_args(args, indexed_slots, len(args) - indexed_slots)
        if indexed_tokens and len(args) > indexed_slots
        else None
    )

    position = 0

    def replace(match):
        nonlocal pair_budget, position
        token = match.group(0)
        if token == "%%":
            return "%"
        if re.fullmatch(r"%\d", token):
            index = int(token[1])
            if resolved_indexed is not None:
                return resolved_indexed[index] if index < len(resolved_indexed) else ""
            return format_arg(args[index] if index < len(args) else None, token)
        if re.fullmatch(r"%c\d", token):
            return ""
        if is_numeric_token(token) and pair_budget > 0:
            pair_budget -= 1
            low = args[position] if position < len(args) else None
            high = args[position + 1] if position + 1 < len(args) else None
            position += 2
            low_text = format_arg(low, token)
            if (
                isinstance(low, (int, float)) and not isinstance(low, bool)
                and isinstance(high, (int, float)) and not isinstance(high, bool)
                and low != high
            ):
                high_token = "%d" if token == "%+d" else token
                return "%s-%s" % (low_text, format_arg(high, high_token))
            return low_text
        value = args[position] if position < len(args) else None
        position += 1
        return format_arg(value, token)

    return SEQ.sub(replace, template)


def prepare_special(key, template, args):
    if key == "healperhit" and args:
        # Label-only synthetic string whose catalog row still carries a min/max pair.
        return "%d " + template, list(args)
    if key != "strSkillRandomFromSkillClass" or len(args) < 2:
        return template, list(args)

    def is_number(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool)

    if not (is_number(args[0]) and is_number(args[1])):
        if len(args) < 3:
            template = re.sub(r"\s*%s\s*$", "", template)
        return template, list(args)
    low, high, rest = int(args[0]), int(args[1]), list(args[2:])
    numeric = str(low) if low == high else "%d-%d" % (low, high)
    if len(rest) < 2:
        template = re.sub(r"\s*%s\s*$", "", template)
    return template, [numeric] + rest


class Renderer:
    """Resolves `{key, args}` lines the way the website does.

    Lookup chain, copied from `src/lib/i18n.ts` `lookup()`:
    active locale strings -> UI_STRINGS[locale] -> UI_STRINGS.enUS -> enUS strings
    -> the raw key (recorded as a miss).
    """

    def __init__(self, locale="enUS"):
        self.locale = locale
        self.active = load_strings(locale)
        self.fallback = self.active if locale == "enUS" else load_strings("enUS")
        tables = load_ui_strings()
        self.ui_active = tables.get(locale, {})
        self.ui_enus = tables.get("enUS", {})
        self.missing = []

    def lookup(self, key):
        if not key:
            return ""
        value = (self.active.get(key) or self.ui_active.get(key)
                 or self.ui_enus.get(key) or self.fallback.get(key))
        if value is None:
            self.missing.append(key)
            return key
        return value

    def opt(self, key):
        """Translate when the bundle has a string for it, otherwise None (no miss report)."""
        if not key:
            return None
        return (self.active.get(key) or self.ui_active.get(key)
                or self.ui_enus.get(key) or self.fallback.get(key))

    def line(self, entry):
        """A KeyedLine: {key, args, perLevel?, qualifier?, classOnly?, itemsRequired?, fullSet?}."""
        if not entry:
            return ""
        raw_args = entry.get("args") or []
        args = [self.lookup(a) if isinstance(a, str) else a for a in raw_args]
        key = entry.get("key") or ""
        template, args = prepare_special(key, self.lookup(key), args)
        result = format_template(template, args)
        if entry.get("perLevel"):
            result += self.lookup("strPerCharacterLevelSuffix")
        qualifier = entry.get("qualifier")
        if qualifier:
            suffix = {
                "weapon": "strRuneScopeWeapon",
                "shield": "strRuneScopeShield",
                "armor": "strRuneScopeArmor",
            }.get(qualifier)
            if suffix:
                result += self.lookup(suffix)
        if entry.get("classOnly"):
            result += " " + self.lookup(entry["classOnly"])
        if entry.get("itemsRequired"):
            result = format_template(self.lookup("strPartialSetBonus"), [result, entry["itemsRequired"]])
        elif entry.get("fullSet"):
            result = format_template(self.lookup("strFullSetBonus"), [result])
        return result

    def skill_line(self, entry, points):
        if not entry:
            return ""
        numbers = skill_line_numbers(entry, points)
        key = entry.get("key") or ""
        if entry.get("pluralKey") and (not numbers or numbers[0] != 1):
            key = entry["pluralKey"]
        template = self.lookup(key)
        strings = [self.lookup(a) for a in (entry.get("args") or [])]
        slots = count_numeric_slots(template, len(strings))
        return format_template(template, list(strings) + list(numbers[:slots]))

    def report_missing(self):
        if self.missing:
            unique = sorted(set(self.missing))
            sys.stderr.write(
                "note: %d translation key(s) absent in %s, shown as raw keys: %s\n"
                % (len(unique), self.locale, ", ".join(unique[:12]) + (" ..." if len(unique) > 12 else ""))
            )


# --------------------------------------------------------------------------
# skill axis selection, ported from src/lib/skill-points.ts
# --------------------------------------------------------------------------

SKILL_LEVEL_CAP = 100


def clamp_integer(value, low, high):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return low
    return min(max(number, low), max(low, high))


def skill_hard_point_cap(skill):
    descriptions = (skill or {}).get("Descriptions") or {}
    cap = descriptions.get("HardPointCap")
    if cap is None:
        cap = (skill or {}).get("MaxLevel") or 20
    return cap


def skill_bonus_cap(hard):
    """Bonus levels still available once `hard` points are spent (website skillBonusCap)."""
    try:
        spent = int(hard)
    except (TypeError, ValueError):
        spent = 0
    return max(SKILL_LEVEL_CAP - max(0, spent), 0)


def clamp_skill_points(skill, points):
    """Website clampSkillPoints: hard points to 0..min(cap, 100), bonus to what is left.

    Hard points win, so raising them trims the bonus; a skill always keeps at least
    one level (bonus floors at 1 when there are no hard points).
    """
    hard = clamp_integer(points.get("hard"), 0, min(skill_hard_point_cap(skill), SKILL_LEVEL_CAP))
    bonus = clamp_integer(points.get("bonus"), 1 if hard == 0 else 0, skill_bonus_cap(hard))
    clamped = {"hard": hard, "bonus": bonus}
    if points.get("characterLevel") is not None:
        clamped["characterLevel"] = points["characterLevel"]
    return clamped


def skill_points_from_rank(skill, rank):
    level = max(int(rank or 1), 1)
    hard = min(level, skill_hard_point_cap(skill))
    return clamp_skill_points(skill, {"hard": hard, "bonus": level - hard})


def skill_line_numbers(line, points):
    hard = max(int(points.get("hard") or 0), 0)
    bonus = max(int(points.get("bonus") or 0), 0)
    character_level = points.get("characterLevel")

    values_ulvl = line.get("valuesUlvl")
    if values_ulvl:
        level = max(hard + bonus, 1) - 1
        clvl = float("inf") if character_level is None else max(int(character_level or 1), 1) - 1
        numbers = []
        for rows in values_ulvl:
            row = rows[min(level, len(rows) - 1)] if rows else []
            numbers.append(row[min(int(clvl), len(row) - 1)] if row else 0)
        return numbers

    values_2d = line.get("values2d")
    if values_2d:
        numbers = []
        for rows in values_2d:
            row = rows[min(hard, len(rows) - 1)] if rows else []
            numbers.append(row[min(bonus, len(row) - 1)] if row else 0)
        return numbers

    index = max(hard + bonus, 1) - 1
    return [table[min(index, len(table) - 1)] if table else 0 for table in (line.get("values") or [])]


def axis_of(line):
    if line.get("valuesUlvl"):
        return "valuesUlvl"
    if line.get("values2d"):
        return "values2d"
    if line.get("values"):
        return "values"
    return "args-only"


# --------------------------------------------------------------------------
# wiki metadata
# --------------------------------------------------------------------------

META_KEYS = ("title", "description", "published", "date", "tags", "editor", "dateCreated")
_MD_META = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.S)
_HTML_META = re.compile(r"\A<!--\s*\n(.*?)\n-->\s*", re.S)


def parse_wiki_meta(text):
    match = _MD_META.match(text) or _HTML_META.match(text)
    meta = {}
    body_start = 0
    if match:
        body_start = match.end()
        for line in match.group(1).splitlines():
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            key = key.strip()
            if key in META_KEYS:
                meta[key] = value.strip()
    return meta, body_start


BLOCK_TAGS = re.compile(
    r"</?(?:p|div|br|ul|ol|li|h[1-6]|table|tr|blockquote|pre|hr|section|article)\b[^>]*>",
    re.I,
)
TD_TAG = re.compile(r"</?(?:td|th)\b[^>]*>", re.I)
ANY_TAG = re.compile(r"<[^>]+>")


def html_to_text(fragment):
    text = BLOCK_TAGS.sub("\n", fragment)
    text = TD_TAG.sub(" | ", text)
    text = re.sub(r"<style\b.*?</style>", "", text, flags=re.S | re.I)
    text = re.sub(r"<script\b.*?</script>", "", text, flags=re.S | re.I)
    text = ANY_TAG.sub("", text)
    text = html_lib.unescape(text).replace("\u00a0", " ")
    lines = [line.strip() for line in text.splitlines()]
    out, blank = [], 0
    for line in lines:
        if line:
            out.append(line)
            blank = 0
        else:
            blank += 1
            if blank == 1 and out:
                out.append("")
    return "\n".join(out).strip()


def iter_wiki_pages():
    if not WIKI.is_dir():
        die("wiki content is not synced (%s)" % WIKI, "run `west update`")
    for path in sorted(WIKI.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in (".md", ".html"):
            continue
        if any(part in (".git", ".idea") for part in path.relative_to(WIKI).parts):
            continue
        rel = path.relative_to(WIKI).as_posix()
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        meta, _ = parse_wiki_meta(text)
        yield rel, path, meta, text


# --------------------------------------------------------------------------
# shared helpers
# --------------------------------------------------------------------------

def vanilla_flag(row):
    value = row.get("Vanilla", "")
    return {"Y": "vanilla", "N": "mod-added"}.get(value, value or "unknown")


def normalized(value):
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    return re.sub(r"\s+", " ", value.strip()).lower()


def matches(needles, haystacks):
    cleaned_hay = [normalized(h) for h in haystacks if h]
    return all(any(n in h for h in cleaned_hay) for n in needles)


def unique_rows():
    for row in load_keyed("uniques"):
        yield row


def set_item_rows():
    for parent in load_keyed("sets"):
        for item in parent.get("SetItems") or []:
            yield parent["Index"], item


def skill_rows():
    for group in load_keyed("skills"):
        for tab in group.get("Tabs") or []:
            for skill in tab.get("Skills") or []:
                yield group, tab, skill


_SKILL_BY_ID = None


def skill_by_id():
    """engine row index -> skill code, for resolving PrerequisiteIds."""
    global _SKILL_BY_ID
    if _SKILL_BY_ID is None:
        _SKILL_BY_ID = {skill.get("Id"): skill.get("Code") for _, _, skill in skill_rows()}
    return _SKILL_BY_ID


def print_pairs(title, pairs):
    print(title)
    for key, value in pairs:
        if value is None or value == "" or value == []:
            continue
        print("  %-18s %s" % (key, value))


def named(renderer, index):
    """Engine row name, plus its display string when the locale table renames it.

    Several rows are addressed by a row identifier whose player-visible name is
    different (runeword 'Black1' renders as 'Black' / 黑锤), so a bare Index
    would look like an unknown item.
    """
    index = index or ""
    display = renderer.lookup(index) if index else ""
    return index if display == index else "%s (%s)" % (index, display)


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------

def read_git_head(path):
    head_file = path / ".git" / "HEAD"
    if not head_file.is_file():
        return "?"
    raw = head_file.read_text(encoding="utf-8", errors="replace").strip()
    if raw.startswith("ref: "):
        ref = raw[5:]
        loose = path / ".git" / ref.replace("/", os.sep)
        if loose.is_file():
            return "%s @ %s" % (ref.split("/")[-1], loose.read_text(errors="replace").strip()[:9])
        packed = path / ".git" / "packed-refs"
        if packed.is_file():
            for line in packed.read_text(errors="replace").splitlines():
                if line.startswith("#") or " " not in line:
                    continue
                sha, _, name = line.partition(" ")
                if name.strip() == ref:
                    return "%s @ %s" % (ref.split("/")[-1], sha[:9])
        return "%s @ ?" % ref.split("/")[-1]
    return "detached @ %s" % raw[:9]


def _key_list(keys, limit=12):
    if not keys:
        return "none"
    text = ", ".join(keys[:limit])
    return text + (" ... +%d more" % (len(keys) - limit) if len(keys) > limit else "")


def cmd_status(args):
    require_upstream()
    print("== west projects ==")
    for name, path in PROJECTS.items():
        if not (path / ".git").exists():
            print("  %-24s NOT SYNCED (%s)" % (name, path.relative_to(REPO)))
            continue
        print("  %-24s %s" % (name, read_git_head(path)))

    if not MANIFEST.is_file():
        die("manifest.json is missing", "run `west update`")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    print("\n== export manifest ==")
    print("  SchemaVersion %s   Succeeded %s   Complete %s"
          % (manifest.get("SchemaVersion"), manifest.get("Succeeded"), manifest.get("Complete")))
    steps = manifest.get("Steps") or []
    files = manifest.get("Files") or []
    tally = {}
    for step in steps:
        tally[step.get("Status", "?")] = tally.get(step.get("Status", "?"), 0) + 1
    print("  Steps %d %s   Files[] %d" % (len(steps), tally, len(files)))
    for step in steps:
        if step.get("Status") != "Written":
            print("    NOT-WRITTEN %-28s %s  %s"
                  % (step.get("Producer"), step.get("Status"), step.get("Message", "")))
    producers = {}
    for entry in files:
        producers[entry.get("Producer", "?")] = producers.get(entry.get("Producer", "?"), 0) + 1
    print("  producers: " + ", ".join("%s=%d" % kv for kv in sorted(producers.items())))

    print("\n== keyed bundles ==")
    for path in sorted(KEYED.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except ValueError:
            print("  %-28s PARSE ERROR" % path.name)
            continue
        size = path.stat().st_size
        if isinstance(payload, list):
            print("  %-28s list   %5d rows  %6.1f MB" % (path.name, len(payload), size / 1048576))
        elif isinstance(payload, dict):
            shape = ", ".join("%s:%s" % (k, len(v) if isinstance(v, (list, dict)) else v)
                              for k, v in list(payload.items())[:6])
            print("  %-28s object %6.1f MB  %s" % (path.name, size / 1048576, shape))

    print("\n== translations ==")
    locales = sorted(p.stem for p in STRINGS.glob("*.json"))
    counts = {}
    key_sets = {}
    for locale in locales:
        table = json.loads((STRINGS / ("%s.json" % locale)).read_text(encoding="utf-8-sig"))
        counts[locale] = len(table)
        key_sets[locale] = set(table)
    baseline = counts.get("enUS", 0)
    print("  %d locales; enUS has %d keys" % (len(locales), baseline))
    print("  " + ", ".join("%s=%d%s" % (k, v, "(-%d)" % (baseline - v) if v < baseline else "")
                           for k, v in sorted(counts.items())))
    others = set().union(*[key_sets[k] for k in locales if k != "enUS"]) if locales else set()
    enus_only = sorted(key_sets.get("enUS", set()) - others)
    other_only = sorted(others - key_sets.get("enUS", set()))
    print("  keys only in enUS (other locales show the raw key): %s" % _key_list(enus_only))
    print("  keys only outside enUS (absent from enUS itself): %s" % _key_list(other_only))

    print("\n== wiki ==")
    md = html = 0
    newest = []
    if WIKI.is_dir():
        for rel, path, meta, _ in iter_wiki_pages():
            if rel.lower().endswith(".md"):
                md += 1
            else:
                html += 1
            folder = rel.split("/")[0]
            if folder in ("Patch_Notes",) and re.match(r"^\d", rel.split("/")[-1]):
                newest.append((meta.get("date", ""), rel, meta.get("title", "")))
        print("  pages: %d .md + %d .html (html-only pages carry metadata in an HTML comment)" % (md, html))
        marker = WIKI / "latestversion.txt"
        declared = marker.read_text(errors="replace").strip() if marker.is_file() else "(absent)"
        newest.sort(reverse=True)
        print("  latestversion.txt: %s" % declared)
        print("  newest Patch_Notes pages by date:")
        for date, rel, title in newest[:3]:
            print("    %-42s %-16s %s" % (rel, date[:10], title))
        if newest:
            top = re.findall(r"(\d+)\.(\d+)\.(\d+)", newest[0][2] + " " + newest[0][1])
            stamp = re.findall(r"(\d+)\.(\d+)\.(\d+)", declared)
            if top and stamp and tuple(top[0]) != tuple(stamp[0]):
                print("  CONFLICT: latestversion.txt says %s but %s is dated %s and titled %r"
                      % (declared, newest[0][1], newest[0][0][:10], newest[0][2]))
    else:
        print("  wiki content not synced")

    print("\n== extras reports (official self-diagnosis) ==")
    if EXTRAS.is_dir():
        for path in sorted(EXTRAS.glob("*.txt")):
            first = path.read_text(encoding="utf-8", errors="replace").splitlines()
            print("  %-28s %6.1f KB  %s" % (path.name, path.stat().st_size / 1024,
                                            (first[0] if first else "").strip()))


def cmd_integrity(args):
    require_upstream()
    if not MANIFEST.is_file():
        die("manifest.json is missing", "run `west update`")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    declared = manifest.get("Files") or []
    print("manifest Succeeded=%s Complete=%s; verifying %d declared files"
          % (manifest.get("Succeeded"), manifest.get("Complete"), len(declared)))

    missing, eol_only, failures, seen = [], [], [], set()
    for entry in declared:
        rel = entry.get("Path", "").replace("/", os.sep)
        seen.add(os.path.normcase(entry.get("Path", "")))
        path = DATA / rel
        if not path.is_file():
            missing.append(entry["Path"])
            continue
        raw = path.read_bytes()
        want_bytes = entry.get("Bytes")
        want_sha = (entry.get("Sha256") or "").lower()
        size_ok = want_bytes is None or int(want_bytes) == len(raw)
        sha_ok = not want_sha or hashlib.sha256(raw).hexdigest() == want_sha
        if size_ok and sha_ok:
            continue
        lf = raw.replace(b"\r\n", b"\n")
        lf_ok = (want_bytes is None or int(want_bytes) == len(lf)) and (
            not want_sha or hashlib.sha256(lf).hexdigest() == want_sha)
        if lf_ok:
            eol_only.append((entry["Path"], want_bytes, len(raw)))
        else:
            failures.append((entry["Path"], want_bytes, len(raw), size_ok, sha_ok))
    ok = len(declared) - len(missing) - len(eol_only) - len(failures)
    print("  exact match %d/%d" % (ok, len(declared)))
    print("  missing %d, real byte/sha mismatch %d" % (len(missing), len(failures)))
    if eol_only:
        print("  EOL-only mismatch %d  (working tree is CRLF, the exporter hashed the LF payload; "
              "core.autocrlf=true, the content is identical)" % len(eol_only))
        for rel, want, got in eol_only[: args.show]:
            print("    EOL   %-44s declared %s bytes, working tree %s" % (rel, want, got))
    for rel, want, got, size_ok, sha_ok in failures[: args.show]:
        print("    FAIL  %-44s declared %s bytes, found %s (size ok=%s, sha ok=%s)"
              % (rel, want, got, size_ok, sha_ok))
    for rel in missing[: args.show]:
        print("    MISS  %s" % rel)

    undeclared = []
    for path in DATA.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(DATA).as_posix()
        if rel == "manifest.json":
            continue
        if os.path.normcase(rel) not in seen:
            undeclared.append(rel)
    print("  on disk but not declared: %d" % len(undeclared))
    for rel in sorted(undeclared)[: args.show]:
        print("    EXTRA %s" % rel)
    verdict = not (missing or failures)
    print("verdict: %s" % ("data present and byte-true" if verdict else "INCOMPLETE"))
    return 0 if verdict else 1


def cmd_find(args):
    require_upstream()
    renderer = Renderer(args.locale)
    needles = [normalized(n) for n in args.terms]
    hits = []

    for row in load_keyed("uniques"):
        if matches(needles, [row.get("Index"), row.get("Code"), renderer.lookup(row.get("Index", ""))]):
            hits.append(("unique", named(renderer, row.get("Index")),
                         "enabled" if row.get("Enabled") else "DISABLED", vanilla_flag(row)))
    for parent in load_keyed("sets"):
        if matches(needles, [parent.get("Index"), renderer.lookup(parent.get("Index", ""))]):
            hits.append(("set", named(renderer, parent.get("Index")),
                         "%d items" % len(parent.get("SetItems") or []), vanilla_flag(parent)))
        for item in parent.get("SetItems") or []:
            if matches(needles, [item.get("Index"), renderer.lookup(item.get("Index", ""))]):
                hits.append(("set-item", "%s / %s" % (parent["Index"], named(renderer, item["Index"])),
                             "code %s" % item.get("Code"), vanilla_flag(item)))
    for row in load_keyed("runewords"):
        if matches(needles, [row.get("Index"), renderer.lookup(row.get("Index", "")), row.get("Code")]):
            hits.append(("runeword", named(renderer, row.get("Index")),
                         " + ".join(renderer.lookup(r.get("NameKey", "")) for r in row.get("Runes") or []),
                         vanilla_flag(row)))
    for group, tab, skill in skill_rows():
        if matches(needles, [skill.get("Code"), skill.get("NameKey"),
                             renderer.lookup(skill.get("NameKey", "")), group.get("Class")]):
            hits.append(("skill", "%s / %s" % (group.get("Class"), skill.get("Code")),
                         "Id %s" % skill.get("Id"), "tab %s" % renderer.lookup(tab.get("NameKey", ""))))
    for row in load_keyed("armors") + load_keyed("weapons"):
        if matches(needles, [row.get("NameKey"), renderer.lookup(row.get("NameKey", "")),
                             row.get("NormCode"), row.get("EquipmentType")]):
            hits.append(("base", row.get("NameKey"), "code %s" % row.get("NormCode"),
                         "ilvl %s / req %s" % (row.get("ItemLevel"), row.get("RequiredLevel"))))
    for row in load_keyed("cube-recipes"):
        rendered = " | ".join(
            renderer.line(entry) for entry in (row.get("Notes") or []) + (row.get("Details") or [])
        )
        tokens = " ".join(str(inp.get("RawToken", "")) for inp in row.get("Inputs") or [])
        if matches(needles, [row.get("Id"), row.get("Description"), rendered, tokens]):
            hits.append(("cube", "%s (index %s)" % (row.get("Id"), row.get("Index")),
                         "%d inputs" % len(row.get("Inputs") or []), rendered[:60] or "-"))

    if not hits:
        print("no official record matched %s" % " ".join(args.terms))
        print("try `wiki %s` for narrative pages, or `find` with a shorter term"
              % " ".join(args.terms))
    else:
        print("%d match(es):" % len(hits))
        for kind, ident, detail, extra in hits[: args.limit]:
            print("  %-10s %-44s %-22s %s" % (kind, ident, detail, extra))
        if len(hits) > args.limit:
            print("  ... %d more (raise --limit)" % (len(hits) - args.limit))
    renderer.report_missing()


def resolve_named(rows, name, key_getter=None, renderer=None):
    needles = [normalized(n) for n in name]
    exact, partial = [], []
    for row in rows:
        label = key_getter(row) if key_getter else row.get("Index", "")
        haystack = [label, row.get("Code") if isinstance(row, dict) else None]
        if renderer and label:
            haystack.append(renderer.lookup(label))
        if all(any(n == normalized(h) for h in haystack if h) for n in needles):
            exact.append(row)
        elif matches(needles, haystack):
            partial.append(row)
    return exact or partial


def cmd_item(args):
    require_upstream()
    renderer = Renderer(args.locale)

    uniques = resolve_named(load_keyed("uniques"), args.name, renderer=renderer)
    sets = resolve_named(load_keyed("sets"), args.name, renderer=renderer)
    set_items = []
    for parent in load_keyed("sets"):
        for item in parent.get("SetItems") or []:
            item = dict(item)
            item["_set"] = parent["Index"]
            set_items.append(item)
    set_items = resolve_named(set_items, args.name, renderer=renderer)

    if not (uniques or sets or set_items):
        print("no unique or set record matches %s" % " ".join(args.name))
        print("runes and base items live in `runeword` and `find`; set bonuses live in `item <set name>`")
        renderer.report_missing()
        return 1

    for parent in sets:
        print("== SET %s ==" % parent.get("Index"))
        print_pairs("  head", [
            ("vanilla", vanilla_flag(parent)),
            ("set items", ", ".join(i.get("Index", "") for i in parent.get("SetItems") or [])),
            ("parent ItemLevel", "%s  (legacy: sets.txt has no lvl column - never quote this as the base level)"
             % parent.get("ItemLevel")),
        ])
        if parent.get("PartialBonuses"):
            print("  partial bonuses:")
            for entry in parent["PartialBonuses"]:
                print("    - %s" % renderer.line(entry))
        if parent.get("FullBonuses"):
            print("  full set bonuses:")
            for entry in parent["FullBonuses"]:
                print("    - %s" % renderer.line(entry))
        print()

    for row in set_items + uniques:
        is_set_item = "_set" in row
        print("== %s %s ==" % ("SET ITEM" if is_set_item else "UNIQUE", row.get("Index")))
        equipment = row.get("Equipment") or {}
        base_key = equipment.get("NameKey") or row.get("Code") or ""
        print_pairs("  head", [
            ("type", "%s -> base %s" % (renderer.opt(row.get("Type")) or row.get("Type"),
                                          renderer.lookup(base_key) if base_key else "-")),
            ("code", row.get("Code")),
            ("vanilla", vanilla_flag(row)),
            ("enabled", "yes" if row.get("Enabled", True) else "NO (not in the current data set)"),
            ("item level", row.get("ItemLevel")),
            ("required level", row.get("RequiredLevel")),
            ("rarity", row.get("Rarity")),
            ("set", row.get("SetName") or row.get("_set") or ""),
            ("enhanced flag", "DamageArmorEnhanced=%s (source column, not a display value)"
             % row.get("DamageArmorEnhanced")),
        ])
        base_lines = equipment.get("Lines") or []
        if base_lines:
            print("  base affinity:")
            for entry in base_lines:
                print("    - %s" % renderer.line(entry))
        if row.get("Lines"):
            print("  affix lines:")
            for entry in row["Lines"]:
                suffix = ""
                if entry.get("selection"):
                    sel = entry["selection"]
                    suffix = "   [selection %s %s..%s]" % (sel.get("stat"), sel.get("min"), sel.get("max"))
                print("    - %s%s" % (renderer.line(entry), suffix))
        if row.get("SetBonuses"):
            print("  set bonuses by count:")
            for group in row["SetBonuses"]:
                for entry in group or []:
                    print("    - %s" % renderer.line(entry))
        print()
    renderer.report_missing()
    return 0


def cmd_runeword(args):
    require_upstream()
    renderer = Renderer(args.locale)
    rows = load_keyed("runewords")
    if args.list:
        for row in rows:
            print("  %-38s %-10s %s" % (named(renderer, row.get("Index")), vanilla_flag(row),
                                        " + ".join(renderer.lookup(r.get("NameKey", ""))
                                                   for r in row.get("Runes") or [])))
        return 0

    hits = resolve_named(rows, args.name, renderer=renderer)
    if len(hits) > 1 and not args.all:
        print("ambiguous, %d candidates (use --all):" % len(hits))
        for row in hits[: 20]:
            print("  - %s" % named(renderer, row.get("Index")))
        return 1
    if not hits:
        print("no runeword matches %s" % " ".join(args.name))
        return 1

    for row in hits:
        runes = [renderer.lookup(r.get("NameKey", "")) for r in row.get("Runes") or []]
        display = renderer.lookup(row.get("Index", ""))
        print("== RUNEWORD %s%s ==" % (row.get("Index"),
                                      "" if display == row.get("Index") else " (%s)" % display))
        print_pairs("  head", [
            ("runes", " > ".join(runes)),
            ("rune ilvl", ", ".join(str(r.get("ItemLevel")) for r in row.get("Runes") or [])),
            ("bases", ", ".join("%s%s"
                                % (renderer.opt(t.get("Index")) or t.get("Name"),
                                   "" if not t.get("Class") else " (%s)" % t["Class"])
                                for t in row.get("Types") or [])),
            ("required level", row.get("RequiredLevel")),
            ("item level", row.get("ItemLevel")),
            ("vanilla", vanilla_flag(row)),
            ("rarity", row.get("Rarity")),
            ("enabled", "yes" if row.get("Enabled", True) else "NO"),
            ("code", row.get("Code")),
        ])
        print("  properties:")
        for entry in row.get("Lines") or []:
            print("    - %s" % renderer.line(entry))
        print()
    renderer.report_missing()
    return 0


def cmd_skill(args):
    require_upstream()
    renderer = Renderer(args.locale)
    needles = [normalized(n) for n in args.name]
    group_needle = normalized(args.cls) if args.cls else None
    found = []
    for group, tab, skill in skill_rows():
        if group_needle and not matches([group_needle], [group.get("Class"), group.get("ClassCode")]):
            continue
        haystack = [skill.get("Code"), skill.get("NameKey"), renderer.lookup(skill.get("NameKey", "")),
                    group.get("Class"), group.get("ClassCode"), renderer.lookup(group.get("NameKey", ""))]
        if matches(needles, haystack):
            found.append((group, tab, skill))
    if not found:
        print("no skill matches %s%s" % (" ".join(args.name), " in class %s" % args.cls if args.cls else ""))
        print("`skill --list [class]` prints every skill code")
        renderer.report_missing()
        return 1
    if args.list:
        for group, tab, skill in found:
            print("  %-12s %-28s %-4s %s"
                  % (group.get("ClassCode"), skill.get("Code"), skill.get("Id"),
                     renderer.lookup(skill.get("NameKey", ""))))
        return 0
    if len(found) > 1 and not args.all:
        print("ambiguous, %d candidates (use --all or pass the class):" % len(found))
        for group, _, skill in found[:20]:
            print("  - %s / %s" % (group.get("Class"), skill.get("Code")))
        return 1

    for group, tab, skill in found:
        descriptions = skill.get("Descriptions") or {}
        cap = skill_hard_point_cap(skill)
        rank = args.rank if args.rank is not None else min(skill.get("MaxLevel") or cap, cap)
        points = skill_points_from_rank(skill, rank)
        requested = []
        if args.hard is not None:
            requested.append(("hard", int(args.hard)))
            points["hard"] = max(int(args.hard), 0)
        if args.bonus is not None:
            requested.append(("bonus", int(args.bonus)))
            points["bonus"] = max(int(args.bonus), 0)
        if requested:
            points = clamp_skill_points(skill, points)
        if args.ulvl is not None:
            points["characterLevel"] = int(args.ulvl)
        print("== SKILL %s (%s / %s) ==" % (renderer.lookup(skill.get("NameKey", "")),
                                            group.get("Class"), skill.get("Code")))
        prereq_names = [skill_by_id().get(pid, "id %s" % pid) for pid in skill.get("PrerequisiteIds") or []]
        print_pairs("  head", [
            ("engine Id", "%s  (skills.txt row index, not the *Id column)" % skill.get("Id")),
            ("element", skill.get("ElementType")),
            ("required char level", skill.get("RequiredLevel")),
            ("max points (maxlvl)", skill.get("MaxLevel")),
            ("tab", "%s / page %s  cell r%s c%s"
             % (renderer.lookup(tab.get("NameKey", "")), tab.get("Page"), skill.get("Row"), skill.get("Column")),
             ),
            ("prerequisites", ", ".join(prereq_names) or "none"),
            ("icon", skill.get("Icon")),
            ("axes", "HardPointCap %s, Descriptions.MaxLevel %s, CharacterLevelCap %s"
             % (descriptions.get("HardPointCap"), descriptions.get("MaxLevel"),
                descriptions.get("CharacterLevelCap"))),
            ("shown at", "hard %s + bonus %s = level %s%s%s"
             % (points["hard"], points["bonus"], points["hard"] + points["bonus"],
                "" if "characterLevel" not in points else ", char level %s" % points["characterLevel"],
                "".join("  (clamped %s %s -> %s)" % (name, wanted, points[name])
                        for name, wanted in requested
                        if wanted != points[name]))),
        ])
        short_key = skill.get("ShortDescriptionKey")
        long_key = skill.get("DescriptionKey")
        if short_key:
            print("  short description: %s" % renderer.lookup(short_key))
        if long_key and long_key != short_key:
            print("  description: %s" % renderer.lookup(long_key))
        for bucket in ("Stats", "Details", "Synergies"):
            entries = descriptions.get(bucket) or []
            if not entries:
                continue
            print("  %s:" % bucket.lower())
            for entry in entries:
                extra = []
                used = axis_of(entry)
                if used not in ("args-only",):
                    extra.append("axis=%s" % used)
                for scale_key in ("scale", "scaleCalc"):
                    if entry.get(scale_key):
                        extra.append("%s=%s" % (scale_key, entry[scale_key]))
                if entry.get("valuesCalc"):
                    extra.append("valuesCalc=%s" % entry["valuesCalc"])
                if entry.get("selection"):
                    extra.append("selection=%s" % entry["selection"])
                if entry.get("classOnly"):
                    extra.append("classOnly=%s" % entry["classOnly"])
                print("    - %s%s" % (renderer.skill_line(entry, points),
                                      ("   [%s]" % "; ".join(extra)) if extra else ""))
        calculation = skill.get("Calculation") or {}
        if calculation:
            print("  calculation (raw BBE, not evaluated here):")
            for label in ("Params", "Calcs"):
                if calculation.get(label):
                    print("    %-8s %s" % (label, calculation[label]))
            for label in ("PhysicalDamage", "ElementalDamage", "ElementalLength"):
                if calculation.get(label):
                    print("    %-16s %s" % (label, calculation[label]))
        print("  note: %s" % DISCLAIMERS["skill"])
        print()
    renderer.report_missing()
    return 0


def cmd_cube(args):
    require_upstream()
    renderer = Renderer(args.locale)
    rows = load_keyed("cube-recipes")
    needle = args.term

    if re.fullmatch(r"cr-[0-9a-f]{16}(-\d+)?", needle, re.I):
        hits = [row for row in rows if (row.get("Id") or "").lower() == needle.lower()]
    elif needle.isdigit():
        hits = [row for row in rows if str(row.get("Index")) == needle]
    else:
        needles = [normalized(needle)]
        hits = []
        for row in rows:
            parts = []
            for entry in list(row.get("Inputs") or []) + list((row.get("Outputs") or {}).values()):
                name = entry.get("Name") or {}
                parts.append(renderer.line(name))
                parts.append(str(entry.get("RawToken", "")))
            for group in ("Notes", "Details"):
                for line in row.get(group) or []:
                    parts.append(renderer.line(line))
            parts.append(row.get("Description") or "")
            if matches(needles, parts):
                hits.append(row)
    if not hits:
        print("no cube recipe matches %r" % needle)
        print("accepts a `cr-...` id, a cubemain row index, or a text fragment from input/output/note names")
        renderer.report_missing()
        return 1

    for row in hits[: args.limit]:
        print("== CUBE %s (cubemain row %s) ==" % (row.get("Id"), row.get("Index")))
        print_pairs("  head", [
            ("op/param/value", "%s / %s / %s" % (row.get("Op"), row.get("Param"), row.get("Value"))),
            ("required class", row.get("RequiredClass") or "any"),
            ("inputs", "%d declared / %d resolved" % (row.get("NumInputs") or 0,
                                                     row.get("ResolvedInputsCount") or 0)),
            ("enabled", "yes" if row.get("Enabled", True) else "NO"),
        ])
        for entry in row.get("Inputs") or []:
            qualifiers = ", ".join(renderer.line(q) for q in entry.get("Qualifiers") or [])
            print("    in  %d x %-28s [%s]%s"
                  % (entry.get("Quantity", 1), renderer.line(entry.get("Name") or {}),
                     entry.get("RawToken", ""), " " + qualifiers if qualifiers else ""))
        for slot, entry in (row.get("Outputs") or {}).items():
            print("    out %s: %d x %s" % (slot, entry.get("Quantity", 1), renderer.line(entry.get("Name") or {})))
            for line in entry.get("Lines") or []:
                print("          - %s" % renderer.line(line))
        for group in ("Notes", "Details"):
            for line in row.get(group) or []:
                print("    %-5s %s" % (group.lower(), renderer.line(line)))
        print("  note: Id is FNV-1a over the raw cubemain cells (U+001F joined); it is a stable "
              "identity, not a row number. See export-tool/docs/WEBSITE-INTEGRATION.md")
        print()
    if len(hits) > args.limit:
        print("... %d more matches (raise --limit)" % (len(hits) - args.limit))
    renderer.report_missing()
    return 0


def cmd_strings(args):
    require_upstream()
    locales = args.locale.split(",") if not args.all_locales else sorted(
        p.stem for p in STRINGS.glob("*.json"))
    for locale in locales:
        table = load_strings(locale)
        ui_table = load_ui_strings().get(locale, {})
        print("== %s ==" % locale)
        for key in args.keys:
            template = table.get(key)
            origin = ""
            if template is None:
                template = ui_table.get(key)
                origin = "   [site UI_STRINGS only, absent from strings/%s.json]" % locale
            if template is None:
                print("  %-32s (absent)" % key)
                continue
            tokens = SEQ.findall(template)
            print("  %-32s %s%s" % (key, template, origin))
            if args.slots:
                print("  %-32s placeholders: %s" % ("", ", ".join(tokens) or "none"))
    if args.args:
        renderer = Renderer(locales[0])
        for key in args.keys:
            entry = {"key": key, "args": json.loads(args.args)}
            print("rendered: %s" % renderer.line(entry))
        renderer.report_missing()
    return 0


def cmd_wiki(args):
    require_upstream()
    if args.show:
        target = normalized(args.show)
        for rel, path, meta, text in iter_wiki_pages():
            if (normalized(rel) == target or Path(rel).stem.lower() == target
                    or Path(rel).name.lower() == target):
                _, body_start = parse_wiki_meta(text)
                body = text[body_start:]
                if path.suffix.lower() == ".html":
                    body = html_to_text(body)
                print("--- %s  (%s)" % (rel, meta.get("date", "")[:10]))
                emitted = 0
                for line in body.splitlines():
                    if args.grep and normalized(args.grep) not in normalized(line):
                        continue
                    print(line)
                    emitted += 1
                    if emitted >= args.max_lines:
                        print("... stopped at %d lines (raise --max-lines)" % args.max_lines)
                        break
                if not emitted:
                    print("(no line matches --grep %r)" % args.grep)
                return 0
        die("wiki page not found: %s" % args.show, "search it first with `wiki <term>`")

    needles = [normalized(n) for n in args.terms]
    rows = []
    for rel, path, meta, _ in iter_wiki_pages():
        if args.since and meta.get("date", "") < args.since:
            continue
        if not args.include_old and rel.startswith("recipes/") and rel.endswith("-old.md"):
            continue
        haystack = [rel, meta.get("title"), meta.get("description"), meta.get("tags")]
        if not needles or matches(needles, haystack):
            rows.append((meta.get("date", ""), rel, meta.get("title", ""),
                         "md" if path.suffix.lower() == ".md" else "html",
                         meta.get("published", ""), meta.get("tags", "")))
    rows.sort(reverse=True)
    if not rows:
        print("no wiki page matches %s" % " ".join(args.terms))
        return 1
    print("%d page(s), newest first:" % len(rows))
    for date, rel, title, form, published, tags in rows[: args.limit]:
        print("  %-10s %-5s %-46s %s%s" % (date[:10], form, rel, title,
                                           "" if published == "true" else "  [published: %s]" % published))
        if args.verbose and tags:
            print("  %-10s %-5s %-46s tags: %s" % ("", "", "", tags))
    if len(rows) > args.limit:
        print("  ... %d more (raise --limit, or add --show <path> to read one)" % (len(rows) - args.limit))
    return 0


def cmd_drop(args):
    require_upstream()
    renderer = Renderer(args.locale)
    bundle = load_keyed("drop-calculator")
    items = bundle.get("Items") or []
    classes = bundle.get("TreasureClasses") or []
    sources = bundle.get("Sources") or []
    bases = {row.get("Code"): row for row in bundle.get("Bases") or []}

    if args.tc:
        needles = [normalized(args.tc)]
        hits = [row for row in classes if matches(needles, [row.get("Code"), row.get("Group")])]
        if not hits:
            print("no treasure class matches %r" % args.tc)
            return 1
        for row in hits[: args.limit]:
            print("== TREASURECLASS %s ==" % row.get("Code"))
            print_pairs("  head", [
                ("group", row.get("Group")),
                ("level", "%s (band width is dropGeneratedTreasureClassLevelStep=3)" % row.get("Level")),
                ("picks", row.get("Picks")),
                ("unique/set slot", "%s / %s (economy indexes, not percentages)" % (row.get("Unique"), row.get("Set"))),
                ("noDrop", row.get("NoDrop")),
                ("quest flags", "%s / %s" % (row.get("QuestFlag") or "-", row.get("QuestFlagEx") or "-")),
                ("condition", row.get("Condition") or "(empty)"),
                ("condition difficulties", row.get("ConditionDifficulties")),
                ("conditionRuntime", row.get("ConditionRuntime")),
            ])
            entries = row.get("Entries") or []
            print("  entries (%d):" % len(entries))
            for entry in entries[: args.entry_limit]:
                label = renderer.lookup((bases.get(entry.get("Code")) or {}).get("NameKey", "")) or ""
                print("    %-10s weight %s  %s" % (entry.get("Code"), entry.get("Weight"), label))
            if len(entries) > args.entry_limit:
                print("    ... %d more" % (len(entries) - args.entry_limit))
            print("  note: %s" % DISCLAIMERS["drop"])
            print()
        return 0

    if args.source:
        needles = [normalized(n) for n in args.source]
        hits = [row for row in sources
                if matches(needles, [row.get("Id"), row.get("NameKey"), renderer.lookup(row.get("NameKey", "")),
                                     row.get("AreaKey"), renderer.lookup(row.get("AreaKey", ""))])]
        print("%d source row(s) match %s" % (len(hits), " ".join(args.source)))
        for row in hits[: args.limit]:
            print("  %-28s %-18s diff %s kind %-10s lvl %-4s TC %s"
                  % (row.get("Id"), renderer.lookup(row.get("NameKey", "")), row.get("Difficulty"),
                     row.get("Kind"), row.get("Level"), row.get("TreasureClass")))
        if len(hits) > args.limit:
            print("  ... %d more (raise --limit)" % (len(hits) - args.limit))
        print("note: %s" % DISCLAIMERS["drop"])
        return 0

    needles = [normalized(n) for n in args.name]
    hits = []
    for row in items:
        haystack = [row.get("Id"), row.get("NameKey"), renderer.lookup(row.get("NameKey", "")), row.get("Code")]
        if matches(needles, haystack):
            hits.append(row)
    if not hits:
        print("no drop-eligible item matches %s" % " ".join(args.name))
        print("the bundle covers named items (unique/set), runes and some misc; "
              "magic/rare/gold are generated, not listed here")
        renderer.report_missing()
        return 1
    for row in hits[: args.limit]:
        base = bases.get(row.get("Code")) or {}
        print("== DROP %s ==" % row.get("NameKey"))
        print_pairs("  head", [
            ("id", row.get("Id")),
            ("quality", row.get("Quality")),
            ("base", "%s (%s)" % (row.get("Code"), renderer.lookup(base.get("NameKey", "")) or "-")),
            ("item level", "%s  (named ilvl)" % row.get("Level")),
            ("rarity", "%s  (relative weight within its quality group)" % row.get("Rarity")),
            ("random", row.get("Random")),
            ("condition", row.get("Condition") or "(empty in this bundle)"),
            ("condition difficulties", row.get("ConditionDifficulties")),
            ("conditionRuntime", row.get("ConditionRuntime")),
        ])
        linked = sum(1 for tc in classes if any(e.get("Code") == row.get("Code") for e in tc.get("Entries") or []))
        print("  treasure classes listing base code %r: %d (weighted generation, not this item's chance)"
              % (row.get("Code"), linked))
        print("  note: %s" % DISCLAIMERS["drop"])
        print()
    if len(hits) > args.limit:
        print("... %d more matches (raise --limit)" % (len(hits) - args.limit))
    renderer.report_missing()
    return 0


def cmd_monster(args):
    require_upstream()
    renderer = Renderer(args.locale)
    bundle = load_keyed("health-calculator")
    monsters = bundle.get("Monsters") or []
    needles = [normalized(n) for n in args.name]
    hits = [row for row in monsters
            if matches(needles, [row.get("Id"), row.get("NameKey"), row.get("FallbackName"),
                                 renderer.lookup(row.get("NameKey", ""))])]
    if not hits:
        print("no monster row matches %s" % " ".join(args.name))
        print("ids come from monstats.txt (engine row order), e.g. `skeleton1`")
        renderer.report_missing()
        return 1
    areas = {row.get("Id"): row for row in bundle.get("Areas") or []}
    levels = {row.get("Level"): row for row in bundle.get("Levels") or []}
    for row in hits[: args.limit]:
        print("== MONSTER %s (%s) ==" % (row.get("FallbackName") or row.get("Id"), row.get("Id")))
        print_pairs("  head", [
            ("name key", "%s -> %s" % (row.get("NameKey") or "(absent: no translation, render FallbackName)",
                                        renderer.lookup(row.get("NameKey", "")) if row.get("NameKey") else "")),
            ("flags", "enabled %s killable %s boss %s noRatio %s align %s"
             % (row.get("Enabled"), row.get("Killable"), row.get("Boss"), row.get("NoRatio"), row.get("Align"))),
            ("monProp", row.get("MonProp")),
            ("damageRegen", row.get("DamageRegen")),
        ])
        for index, stats in enumerate(row.get("Stats") or []):
            difficulty = ("normal", "nightmare", "hell")[index] if index < 3 else str(index)
            multipliers = levels.get(stats.get("Level")) or {}
            print("  %s: level %s  HP %s-%s  resist P/M/F/L/C/Po = %s/%s/%s/%s/%s/%s"
                  % (difficulty, stats.get("Level"), stats.get("MinHP"), stats.get("MaxHP"),
                     stats.get("PhysicalResist"), stats.get("MagicResist"), stats.get("FireResist"),
                     stats.get("LightningResist"), stats.get("ColdResist"), stats.get("PoisonResist")))
            if multipliers:
                print("         monlvl[%s] HP=%s LHP=%s"
                      % (difficulty, (multipliers.get("HP") or [None] * 3)[index],
                         (multipliers.get("LHP") or [None] * 3)[index]))
        for index, ids in enumerate(row.get("Areas") or []):
            difficulty = ("normal", "nightmare", "hell")[index] if index < 3 else str(index)
            names = []
            for area_id in (ids or [])[: args.limit]:
                area = areas.get(area_id) or {}
                names.append(renderer.lookup(area.get("NameKey", "")) or str(area_id))
            if ids:
                print("  areas %s: %s%s" % (difficulty, ", ".join(names),
                                            "" if len(ids) <= args.limit else " (+%d more)" % (len(ids) - args.limit)))
        print("  rules: %s" % (bundle.get("Rules") or {}))
        print("  bonuses: %s" % (bundle.get("Bonuses") or {}))
        print("  note: %s" % DISCLAIMERS["monster"])
        print()
    if len(hits) > args.limit:
        print("... %d more matches (raise --limit)" % (len(hits) - args.limit))
    renderer.report_missing()
    return 0


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        prog="d2r_query.py",
        description="Query the official D2R Reimagined data bundles (read-only).",
        epilog="Data never leaves upstream/: this tool only slices and renders official records. "
               "--locale works both before the subcommand and after it.",
    )
    parser.add_argument("--locale", default="enUS", help="translation locale (enUS, zhCN, zhTW, ...)")
    sub = parser.add_subparsers(dest="command", required=True)

    def with_locale(handle):
        # argparse.SUPPRESS keeps the parent value when --locale is given before the subcommand.
        handle.add_argument("--locale", default=argparse.SUPPRESS, help="translation locale")
        return handle

    sub.add_parser("status", help="what is synced, what the manifest claims, version markers")

    handle = sub.add_parser("integrity", help="verify every manifest Files[] entry byte-by-byte")
    handle.add_argument("--show", type=int, default=10, help="max problems to list")

    handle = with_locale(sub.add_parser("find", help="search every catalog by name or code"))
    handle.add_argument("terms", nargs="+")
    handle.add_argument("--limit", type=int, default=40)

    handle = with_locale(sub.add_parser("item", help="one unique or set record, lines rendered"))
    handle.add_argument("name", nargs="+")

    handle = with_locale(sub.add_parser("runeword", help="one runeword, runes/bases/lines rendered"))
    handle.add_argument("name", nargs="*")
    handle.add_argument("--list", action="store_true", help="list all runewords")
    handle.add_argument("--all", action="store_true", help="print every match")

    handle = with_locale(sub.add_parser("skill", help="one skill's description lines at chosen ranks"))
    handle.add_argument("name", nargs="*")
    handle.add_argument("--class", dest="cls", help="limit to a class (name or code)")
    handle.add_argument("--list", action="store_true", help="list matches instead of rendering")
    handle.add_argument("--all", action="store_true", help="render every match")
    handle.add_argument("--rank", type=int, help="total levels, split into hard points first")
    handle.add_argument("--hard", type=int, help="hard points spent (0 = item-granted oskill)")
    handle.add_argument("--bonus", type=int, help="+skills bonus levels")
    handle.add_argument("--ulvl", type=int, help="character level for valuesUlvl lines")

    handle = with_locale(sub.add_parser("cube", help="cube recipes by cr-id, row index or text"))
    handle.add_argument("term")
    handle.add_argument("--limit", type=int, default=12)

    handle = with_locale(sub.add_parser("strings", help="raw translation templates for one or more keys"))
    handle.add_argument("keys", nargs="+")
    handle.add_argument("--all-locales", action="store_true", help="dump the key across every locale")
    handle.add_argument("--slots", action="store_true", help="list the placeholders found")
    handle.add_argument("--args", help="JSON array of args, rendered with this template")

    handle = sub.add_parser("wiki", help="search the official wiki (md + html)")
    handle.add_argument("terms", nargs="*")
    handle.add_argument("--show", help="print one page's text by path or stem")
    handle.add_argument("--grep", help="with --show, keep only lines containing this")
    handle.add_argument("--max-lines", dest="max_lines", type=int, default=160)
    handle.add_argument("--since", help="only pages dated from this ISO date on")
    handle.add_argument("--include-old", dest="include_old", action="store_true",
                        help="also index recipes/*-old.md (superseded pages)")
    handle.add_argument("--limit", type=int, default=40)
    handle.add_argument("-v", "--verbose", action="store_true", help="also print tags")

    handle = with_locale(sub.add_parser("drop", help="drop eligibility (never probabilities)"))
    handle.add_argument("name", nargs="*", help="named item to look up")
    handle.add_argument("--tc", help="dump treasure class rows matching this name")
    handle.add_argument("--source", nargs="+", help="list monster/area source rows matching this")
    handle.add_argument("--entry-limit", dest="entry_limit", type=int, default=20)
    handle.add_argument("--limit", type=int, default=12)

    handle = with_locale(sub.add_parser("monster", help="raw monster life contributors (no HP synthesis)"))
    handle.add_argument("name", nargs="+")
    handle.add_argument("--limit", type=int, default=10)

    return parser


HANDLERS = {
    "status": cmd_status,
    "integrity": cmd_integrity,
    "find": cmd_find,
    "item": cmd_item,
    "runeword": cmd_runeword,
    "skill": cmd_skill,
    "cube": cmd_cube,
    "strings": cmd_strings,
    "wiki": cmd_wiki,
    "drop": cmd_drop,
    "monster": cmd_monster,
}


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = HANDLERS[args.command]
    result = handler(args)
    return int(result or 0)


if __name__ == "__main__":
    raise SystemExit(main())
