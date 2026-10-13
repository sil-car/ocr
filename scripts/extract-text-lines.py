#!/usr/bin/env python3

"""Extract a reproducible, coverage-aware random sample of text lines from
source texts (e.g. published NTs) for synthetic OCR training data.

Each SOURCE_DIR holds the texts of one language and is named like the
language folders in the ocr repo (e.g. "gbp_gbeya"). USFM files (.usfm, .sfm)
and plain-text files (.txt, paragraphs separated by blank lines) are read.

For each language the script writes to OUT_DIR:
  <lang>.txt           selected lines, shuffled, no references
  <lang>.coverage.tsv  count of each non-ASCII grapheme in the selection
  <lang>.json          manifest: args, seed, source file hashes, stats

Across all languages it also writes:
  all.txt              every selected line, de-duplicated and shuffled
  all.coverage.tsv     every grapheme: total count, source-pool count and
                       per-language breakdown, flagged against --total-min-count
  all.json             manifest for the combined set

Text is NFC-normalized, then look-alike code points are replaced with their
standard form using [properties.codepoint_map] in the repo's
data/Latin_afr/config.toml (e.g. Greek alpha -> Latin alpha), so the output
uses the same code points as the training and evaluation data.

Output is deterministic for a given seed, arguments, codepoint map and source
files, so the sources themselves never need to be committed anywhere public.

With --report-unhandled, nothing is selected or written except
unhandled.tsv and unhandled-by-language.tsv in OUT_DIR: an audit of the code
points in the wrapped source lines that are outside the character inventory
(see allowed_code_points), and how many lines a filter would drop.
"""

import argparse
import hashlib
import json
import random
import sys
import tomllib
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import regex

USFM_SUFFIXES = {".usfm", ".sfm"}
TEXT_SUFFIXES = {".txt"}
# Lines starting with these markers are not running text.
USFM_SKIP_MARKERS = {
    "id", "ide", "h", "toc1", "toc2", "toc3", "toca1", "toca2", "toca3",
    "rem", "usfm", "sts", "mt", "mt1", "mt2", "mt3", "mt4", "ms", "ms1",
    "ms2", "mr", "s", "s1", "s2", "s3", "s4", "sr", "r", "d", "cl", "cp",
    "imt", "imt1", "imt2", "is", "is1", "is2", "ip", "iot", "io", "io1",
    "io2", "ior", "ie", "periph",
}
# Older pre-USFM typesetting files (e.g. nga_ngbaka, 1980s) also use these
# for non-running text: book title parts (st, g, G), printout/page headers (H,
# U, P0002p), figure captions and the text set around them (f without f*, z,
# su), glossary headwords (W), and numbered heading levels (\{1}, \{2}, ...).
LEGACY_SKIP_MARKERS = {"st", "g", "G", "H", "U", "W", "z", "su", "y"}
LEGACY_SKIP_RE = regex.compile(r"\\(?:P\d+p|\{\d+\})")
# Plain-text exports (e.g. Paratext) wrap verse numbers in zero width spaces:
# "\u200b5\u200bƐni ...". Also matches ranges and parts like 5-6, 5a.
ZWSP_VERSE_RE = regex.compile(r"\u200b\d+[a-z]?(?:[-\u2013,]\d+[a-z]?)*\u200b")
# Markers that start a new paragraph (line breaks happen there in print).
# "\p[" / "\p(" are legacy paragraph markers followed by a bracket.
USFM_PARA_MARKERS = r"p|m|pi\d?|mi|nb|q\d?|qr|qc|qm\d?|li\d?|pc|pr|pm|b"
MIN_LINE_CHARS = 10
# The repo's config, found relative to this script (scripts/ -> repo root).
CONFIG_FILE = Path(__file__).resolve().parents[1] / "data" / "Latin_afr" / "config.toml"
# Language folder names follow the repo convention "iso_name", e.g. "gbp_gbeya".
LANG_DIR_RE = regex.compile(r"^[a-z]{3}_[\w-]+$")


def load_properties(config_file=CONFIG_FILE):
    """return the [properties] table of the repo's config.toml"""
    try:
        with config_file.open("rb") as f:
            return tomllib.load(f).get("properties", {})
    except FileNotFoundError:
        print(f"Error: config file not found: {config_file}", file=sys.stderr)
        sys.exit(1)


PROPERTIES = load_properties()


def load_codepoint_map(props=PROPERTIES, config_file=CONFIG_FILE):
    """return a str.translate() table from [properties.codepoint_map]

    Each key must be a single code point (a longer key would silently never
    match); each value is a single code point, or "" to delete the key.
    """
    table = {}
    for k, v in props.get("codepoint_map", {}).items():
        if len(k) != 1 or len(v) > 1:
            print(
                "Error: codepoint_map keys must be single code points and "
                "values single code points or \"\"; got "
                f"{k!r} = {v!r} in {config_file}",
                file=sys.stderr,
            )
            sys.exit(1)
        table[ord(k)] = v
    return table


CODEPOINT_MAP = load_codepoint_map()


def allowed_code_points(props=PROPERTIES):
    """return the set of code points in the character inventory

    The inventory is checked per code point (on NFD text), not per grapheme:
    any listed diacritic may go on any listed letter, as on the keyboard, so
    e.g. c + cedilla and s + dot below are allowed. It contains:
      - consonants and vowels, and their upper-case forms
      - top and bottom diacritics
      - numbers, punctuation and space
      - all printable ASCII (U+0020-U+007E)
    """
    allowed = {chr(cp) for cp in range(0x20, 0x7F)}
    for c in props.get("consonants", []) + props.get("vowels", []):
        allowed.add(c)
        allowed.update(c.upper())
    diacritics = props.get("diacritics", {})
    allowed.update(diacritics.get("top", []))
    allowed.update(diacritics.get("bottom", []))
    for key in ("numbers", "punctuation", "space"):
        allowed.update(props.get(key, []))
    # Entries are meant to be single code points; split any that aren't.
    return {cp for item in allowed for cp in unicodedata.normalize("NFD", item)}


ALLOWED = allowed_code_points()


def unhandled_code_points(line):
    """return the code points of line (NFD) that are not in ALLOWED"""
    return [c for c in unicodedata.normalize("NFD", line) if c not in ALLOWED]


def nfc(s):
    """NFC, then look-alike code points replaced (CODEPOINT_MAP), then NFC
    again in case a replacement can combine with a following mark."""
    s = unicodedata.normalize("NFC", s).translate(CODEPOINT_MAP)
    return unicodedata.normalize("NFC", s)


def codepoint_map_for_manifest():
    """CODEPOINT_MAP as {"U+03B1": "U+0251", "U+200B": ""} for the JSON
    manifests ("" = deleted)."""
    return {
        f"U+{k:04X}": f"U+{ord(v):04X}" if v else ""
        for k, v in sorted(CODEPOINT_MAP.items())
    }


def graphemes(s):
    return regex.findall(r"\X", s)


def is_target(g):
    """Graphemes with any non-ASCII code point (same split as the planned
    non-ASCII accuracy metric)."""
    return any(ord(c) > 127 for c in g)


# ---------------------------------------------------------------- reading


def marker_units(text):
    """Group lines into units: a line starting with a backslash plus the
    unmarked lines that follow it. Hard-wrapped files (common in older SFM)
    continue a heading or caption on the next line without a marker, so
    skipping must apply to the whole unit, not just its first line."""
    units = []
    for line in text.splitlines():
        if line.lstrip().startswith("\\") or not units:
            units.append([line])
        else:
            units[-1].append(line)
    return ["\n".join(u) for u in units]


def skip_unit(unit):
    u = unit.lstrip()
    m = regex.match(r"\\(\w+)", u)
    name = m.group(1) if m else None
    if name in USFM_SKIP_MARKERS or name in LEGACY_SKIP_MARKERS:
        return True
    if LEGACY_SKIP_RE.match(u):
        return True
    # Legacy figure caption: "\f text" with no closing \f* (a real USFM
    # footnote always has one and is removed further down instead).
    if name == "f" and "\\f*" not in unit:
        return True
    # Legacy typesetter notes (English picture descriptions, "End of Tape
    # Three Side One^"): marked with {[}o{]} or ending in "^".
    return "{[}o{]}" in unit or regex.search(r"\^\s*$", unit)


def legacy_cleanup(t):
    """Normalise constructs of older (pre-USFM) SFM typesetting files. These
    patterns do not occur in standard USFM, so this is a no-op there."""
    # A printout header (\H ...) accidentally joined onto a text line.
    t = regex.sub(r"\\H\s.*$", "", t, flags=regex.M)
    # Typesetter codes: {[}b06{]}, {[}w1200{]}, stray {[} / {]}, {1}, {<}.
    t = regex.sub(r"\{\[\}[^\s{}]*\{\]\}|\{\[\}|\{\]\}|\{[^{}\s]\}", "", t)
    # Leftovers of damaged codes ("{[ga", "}b07"); braces are never text.
    t = regex.sub(r"\{\[?|\]?\}(?:b\d+)?", "", t)
    # Quote markers: \<< opens a quoted paragraph with «, \>> closes with ».
    # \< and \> are the single-quote equivalents; their printed glyph is not
    # known, so they only mark the paragraph start / are dropped.
    # Markers that continue running text also eat the line break before
    # them, so a marker alone on a line never leaves a blank line behind
    # (a blank line would split the paragraph).
    t = regex.sub(r"\\<<", "\n\n«", t)
    t = regex.sub(r"\s*\\>>", " »", t)
    t = regex.sub(r"\\<", "\n\n", t)
    t = regex.sub(r"\s*\\>", " ", t)
    # \u, \u12, \u1,2: page/column continuation codes inside running text.
    t = regex.sub(r"\s*\\u(?![A-Za-z])\s*[\d,]*", " ", t)
    # A bare backslash starting a continuation line.
    t = regex.sub(r"\s*\\(?=\s|$)", " ", t)
    return t


def usfm_paragraphs(text):
    """Return a list of paragraphs (plain text) from a USFM book."""
    t = "\n".join(u for u in marker_units(text) if not skip_unit(u))
    t = legacy_cleanup(t)
    # Footnotes, endnotes, cross references.
    t = regex.sub(r"\\(f|fe|x|ef|ex)\s.*?\\\1\*", " ", t, flags=regex.S)
    # \w word|lemma="..."\w*  ->  word
    t = regex.sub(r"\\\+?w\s+([^|\\]*?)(\|[^\\]*)?\\\+?w\*", r"\1", t)
    # Chapter and verse numbers (incl. alternates \ca ... \ca*, \va ... \va*).
    t = regex.sub(r"\\(ca|va|vp)\s.*?\\\1\*", " ", t, flags=regex.S)
    t = regex.sub(r"\\c\s+\S+", "\n\n", t)
    t = regex.sub(r"\\v\s+\S+", " ", t)
    # Paragraph markers become paragraph breaks.
    t = regex.sub(rf"\\({USFM_PARA_MARKERS})(?=\s|$|[\[(])", "\n\n", t)
    # Any remaining marker (character styles etc.) is dropped, text kept.
    t = regex.sub(r"\\\+?[A-Za-z0-9]+\*?", " ", t)
    return plain_paragraphs(t)


def plain_paragraphs(text):
    paras = []
    for block in regex.split(r"\n\s*\n", text):
        p = " ".join(block.split())
        if p:
            paras.append(nfc(p))
    return paras


def read_sources(src_dir):
    """Return (paragraphs, {relative path: sha256}) for one language."""
    paras, hashes = [], {}
    files = sorted(
        p for p in src_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in USFM_SUFFIXES | TEXT_SUFFIXES
    )
    for p in files:
        data = p.read_bytes()
        hashes[str(p.relative_to(src_dir))] = hashlib.sha256(data).hexdigest()
        text = data.decode("utf-8-sig")
        # Before parsing: the map later deletes the zero width spaces, which
        # would leave the number stuck to the next word ("5Ɛni").
        text = ZWSP_VERSE_RE.sub(" ", text)
        if p.suffix.lower() in USFM_SUFFIXES:
            paras.extend(usfm_paragraphs(text))
        else:
            paras.extend(plain_paragraphs(text))
    return paras, hashes


# ---------------------------------------------------------------- wrapping


def wrap_paragraph(para, rng, min_w, max_w):
    """Greedy word wrap with a random target width per line, so the sample
    has the mix of line lengths found in real columns and pages."""
    lines, current = [], ""
    width = rng.randint(min_w, max_w)
    for word in para.split():
        candidate = f"{current} {word}" if current else word
        if current and len(graphemes(candidate)) > width:
            lines.append(current)
            current = word
            width = rng.randint(min_w, max_w)
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def build_pool(paras, rng, min_w, max_w):
    """Wrap all paragraphs; keep the stream order (needed for adjacency
    checks), drop short and duplicate lines."""
    pool, seen = [], set()
    for para in paras:
        for line in wrap_paragraph(para, rng, min_w, max_w):
            if len(line) < MIN_LINE_CHARS or line in seen:
                pool.append(None)  # keep position so neighbours stay neighbours
                continue
            if not any(ch.isalpha() for ch in line):
                pool.append(None)
                continue
            seen.add(line)
            pool.append(line)
    return pool


# ---------------------------------------------------------------- selection


def select_lines(pool, n, rng, min_count, coverage_share, no_adjacent):
    """Pick n lines. Phase 1 spends up to coverage_share * n lines raising
    rare non-ASCII graphemes toward min_count; phase 2 fills the rest at
    random so the sample keeps a natural distribution."""
    g_cache = {i: graphemes(l) for i, l in enumerate(pool) if l}
    index = defaultdict(list)
    for i, gs in g_cache.items():
        for g in set(gs):
            if is_target(g):
                index[g].append(i)

    selected, counts = set(), Counter()

    def eligible(i):
        if i in selected:
            return False
        if no_adjacent and (i - 1 in selected or i + 1 in selected):  # noqa
            return False
        return True

    def take(i):
        selected.add(i)
        counts.update(g_cache[i])

    # Phase 1: coverage. Always work on the grapheme with the fewest
    # available candidate lines first; it is the hardest to satisfy.
    budget = int(n * coverage_share)
    exhausted = set()
    while budget > 0 and len(selected) < n:
        needy = [
            g for g in index
            if counts[g] < min_count and g not in exhausted
        ]
        if not needy:
            break
        g = min(needy, key=lambda x: (len(index[x]), x))
        cands = [i for i in index[g] if eligible(i)]
        if not cands:
            exhausted.add(g)
            continue
        take(rng.choice(cands))
        budget -= 1
    phase1 = len(selected)

    # Phase 2: uniform random fill.
    order = list(g_cache)
    rng.shuffle(order)
    for i in order:
        if len(selected) >= n:
            break
        if eligible(i):
            take(i)
    if no_adjacent and len(selected) < n:
        print(
            "  WARNING: not enough non-adjacent lines; relaxing adjacency rule",
            file=sys.stderr,
        )
        for i in order:
            if len(selected) >= n:
                break
            if i not in selected:
                take(i)

    lines = [pool[i] for i in selected]
    rng.shuffle(lines)  # output order carries no source order
    return lines, counts, phase1, index


# ---------------------------------------------------------------- audit


def show_code_point(c):
    """printable form of a code point; combining marks get a dotted circle"""
    if unicodedata.combining(c):
        return f"\u25cc{c}"
    if c == " ":
        return "\u2423"
    if not c.isprintable():
        return ""
    return c


def audit_pool(pool):
    """return (lines checked, lines with unhandled code points, per code
    point: [occurrences, lines, first example line])"""
    checked = dropped = 0
    per_cp = {}
    for line in pool:
        if not line:
            continue
        checked += 1
        bad = unhandled_code_points(line)
        if not bad:
            continue
        dropped += 1
        for c, n in Counter(bad).items():
            entry = per_cp.setdefault(c, [0, 0, line])
            entry[0] += n
            entry[1] += 1
    return checked, dropped, per_cp


def write_audit(out_dir, results):
    """results: {lang: (checked, dropped, per_cp)}"""
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = ["language\tpool_lines\tlines_with_unhandled\tshare"]
    for lang, (checked, dropped, _) in sorted(results.items()):
        share = dropped / checked if checked else 0
        rows.append(f"{lang}\t{checked}\t{dropped}\t{share:.2%}")
    (out_dir / "unhandled-by-language.tsv").write_text(
        "\n".join(rows) + "\n", encoding="utf-8"
    )

    total = defaultdict(lambda: [0, 0])
    by_lang = defaultdict(dict)
    example = {}
    for lang, (_, _, per_cp) in sorted(results.items()):
        for c, (n, lines, ex) in per_cp.items():
            total[c][0] += n
            total[c][1] += lines
            by_lang[c][lang] = lines
            example.setdefault(c, ex)
    rows = ["code_point\tchar\tname\tcount\tlines\tby_language\texample"]
    for c in sorted(total, key=lambda x: (-total[x][1], x)):
        n, lines = total[c]
        langs = " ".join(
            f"{lang.split('_')[0]}:{k}" for lang, k in sorted(by_lang[c].items())
        )
        name = unicodedata.name(c, "")
        rows.append(
            f"U+{ord(c):04X}\t{show_code_point(c)}\t{name}\t{n}\t{lines}"
            f"\t{langs}\t{example[c]}"
        )
    (out_dir / "unhandled.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    return total


# ---------------------------------------------------------------- output


def write_outputs(out_dir, lang, lines, counts, index, min_count, manifest):
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{lang}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    rows = ["grapheme\tcode_points\tcount\tpool_lines\tstatus"]
    for g in sorted(index, key=lambda x: (counts[x], x)):
        cps = " ".join(f"U+{ord(c):04X}" for c in g)
        status = "ok" if counts[g] >= min_count else "LOW: needs synthetic"
        rows.append(f"{g}\t{cps}\t{counts[g]}\t{len(index[g])}\t{status}")
    (out_dir / f"{lang}.coverage.tsv").write_text(
        "\n".join(rows) + "\n", encoding="utf-8"
    )
    (out_dir / f"{lang}.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def write_combined(out_dir, name, per_lang, pool_counts, seed, total_min):
    """per_lang: {lang: list of selected lines}; pool_counts: {lang: Counter
    of graphemes in that language's whole source pool}."""
    rng = random.Random(f"{seed}:{name}")
    lines, seen = [], set()
    for lang in sorted(per_lang):
        for line in per_lang[lang]:
            if line not in seen:
                seen.add(line)
                lines.append(line)
    rng.shuffle(lines)
    (out_dir / f"{name}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    sel_by_lang = {
        lang: Counter(g for l in ls for g in graphemes(l))
        for lang, ls in per_lang.items()
    }
    total = sum(sel_by_lang.values(), Counter())
    pool_total = sum(pool_counts.values(), Counter())
    every = set(total) | set(pool_total)

    rows = ["grapheme\tcode_points\tnon_ascii\tcount\tpool_count\tby_language\tstatus"]
    for g in sorted(every, key=lambda x: (total[x], x)):
        cps = " ".join(f"U+{ord(c):04X}" for c in g)
        by_lang = " ".join(
            f"{lang.split('_')[0]}:{c[g]}"
            for lang, c in sorted(sel_by_lang.items()) if c[g]
        )
        status = "ok" if total[g] >= total_min else "LOW: needs synthetic"
        shown = "␣" if g == " " else g
        rows.append(
            f"{shown}\t{cps}\t{'yes' if is_target(g) else 'no'}\t{total[g]}"
            f"\t{pool_total[g]}\t{by_lang}\t{status}"
        )
    (out_dir / f"{name}.coverage.tsv").write_text(
        "\n".join(rows) + "\n", encoding="utf-8"
    )

    low = sorted(g for g in every if is_target(g) and total[g] < total_min)
    manifest = {
        "name": name,
        "seed": f"{seed}:{name}",
        "languages": {lang: len(ls) for lang, ls in sorted(per_lang.items())},
        "lines": len(lines),
        "duplicates_removed": sum(len(ls) for ls in per_lang.values()) - len(lines),
        "total_min_count": total_min,
        "codepoint_map": codepoint_map_for_manifest(),
        "low_non_ascii_graphemes": low,
    }
    (out_dir / f"{name}.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return lines, low


def language_name(src):
    """Name outputs after the nearest folder (src or a parent) that looks
    like a language folder, so "sources/gbp_gbeya/usfm" -> "gbp_gbeya".
    Falls back to the resolved folder name (never "" for ".")."""
    resolved = src.resolve()
    for p in (resolved, *resolved.parents):
        if LANG_DIR_RE.match(p.name):
            return p.name
    return resolved.name


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("source_dir", nargs="+", type=Path,
                    help="one folder of source texts per language, e.g. sources/gbp_gbeya")
    ap.add_argument("-o", "--out-dir", type=Path, required=True,
                    help="output folder, e.g. ocr-data/lines")
    ap.add_argument("-n", "--lines", type=int, default=2500,
                    help="lines to select per language [2500]")
    ap.add_argument("-s", "--seed", default="1",
                    help="base random seed; combined with the language name [1]")
    ap.add_argument("--min-width", type=int, default=35,
                    help="min target line width in graphemes [35]")
    ap.add_argument("--max-width", type=int, default=75,
                    help="max target line width in graphemes [75]")
    ap.add_argument("--min-count", type=int, default=100,
                    help="target occurrences of each non-ASCII grapheme [100]")
    ap.add_argument("--coverage-share", type=float, default=0.3,
                    help="max share of lines chosen for coverage [0.3]")
    ap.add_argument("--total-min-count", type=int, default=1000,
                    help="target occurrences of each non-ASCII grapheme across "
                         "all languages; lower ones are flagged LOW [1000]")
    ap.add_argument("--combined-name", default="all",
                    help='basename of the combined output files ["all"]')
    ap.add_argument("--allow-adjacent", action="store_true",
                    help="allow lines that follow each other in the source")
    ap.add_argument("--report-unhandled", action="store_true",
                    help="only audit code points outside the character inventory: "
                         "write unhandled.tsv and unhandled-by-language.tsv to "
                         "OUT_DIR, select nothing and leave other outputs alone")
    args = ap.parse_args()

    # Resolve language names up front and refuse to run if two source
    # folders would write to the same output files.
    jobs = {}
    for src in args.source_dir:
        if not src.is_dir():
            print(f"Error: not a directory: {src}", file=sys.stderr)
            sys.exit(1)
        lang = language_name(src)
        if lang == args.combined_name:
            print(
                f'Error: {src} maps to "{lang}", the same name as the combined '
                "output; use --combined-name to pick another.",
                file=sys.stderr,
            )
            sys.exit(1)
        if lang in jobs:
            print(
                f"Error: {jobs[lang]} and {src} both map to language "
                f'"{lang}"; outputs would overwrite each other.',
                file=sys.stderr,
            )
            sys.exit(1)
        jobs[lang] = src

    per_lang, pool_counts, audit = {}, {}, {}
    for lang, src in jobs.items():
        print(f"{lang}:")
        # Per-language seed: adding a language never changes another's sample.
        seed = f"{args.seed}:{lang}"
        rng = random.Random(seed)

        paras, hashes = read_sources(src)
        if not paras:
            print("  no text found; skipping", file=sys.stderr)
            continue
        pool = build_pool(paras, rng, args.min_width, args.max_width)
        available = sum(1 for l in pool if l)
        if args.report_unhandled:
            audit[lang] = audit_pool(pool)
            checked, dropped, _ = audit[lang]
            print(f"  {checked} lines in pool, {dropped} with unhandled code points "
                  f"({dropped / checked:.1%})" if checked else "  0 lines in pool")
            continue
        lines, counts, phase1, index = select_lines(
            pool, args.lines, rng, args.min_count,
            args.coverage_share, not args.allow_adjacent,
        )
        low = sorted(g for g in index if counts[g] < args.min_count)
        per_lang[lang] = lines
        pool_counts[lang] = Counter(g for l in pool if l for g in graphemes(l))

        manifest = {
            "language": lang,
            "seed": seed,
            "args": {k: (str(v) if isinstance(v, Path) else v)
                     for k, v in vars(args).items() if k != "source_dir"},
            "codepoint_map": codepoint_map_for_manifest(),
            "sources": hashes,
            "pool_lines": available,
            "selected_lines": len(lines),
            "coverage_lines": phase1,
            "sampled_fraction": round(len(lines) / available, 4),
            "low_graphemes": low,
        }
        write_outputs(args.out_dir, lang, lines, counts, index,
                      args.min_count, manifest)
        print(f"  {available} lines in pool, {len(lines)} selected "
              f"({phase1} for coverage, {manifest['sampled_fraction']:.1%} of pool)")
        if low:
            print(f"  below {args.min_count}: {' '.join(low)}")

    if args.report_unhandled:
        if audit:
            total = write_audit(args.out_dir, audit)
            checked = sum(a[0] for a in audit.values())
            dropped = sum(a[1] for a in audit.values())
            print(f"all: {dropped} of {checked} lines with unhandled code points "
                  f"({dropped / checked:.1%})" if checked else "all: no lines")
            top = sorted(total, key=lambda c: -total[c][1])[:15]
            if top:
                print("  most lines: " + "  ".join(
                    f"U+{ord(c):04X} {show_code_point(c)} ({total[c][1]})" for c in top))
            print(f"  details: {args.out_dir / 'unhandled.tsv'}")
        return

    if per_lang:
        lines, low = write_combined(
            args.out_dir, args.combined_name, per_lang, pool_counts,
            args.seed, args.total_min_count,
        )
        print(f"{args.combined_name}: {len(lines)} lines from {len(per_lang)} languages")
        if low:
            print(f"  non-ASCII below {args.total_min_count}: {' '.join(low)}")


if __name__ == "__main__":
    main()
