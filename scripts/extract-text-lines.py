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

Output is deterministic for a given seed, arguments and source files, so the
sources themselves never need to be committed anywhere public.
"""

import argparse
import hashlib
import json
import random
import sys
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
# Markers that start a new paragraph (line breaks happen there in print).
# "\p[" / "\p(" are legacy paragraph markers followed by a bracket.
USFM_PARA_MARKERS = r"p|m|pi\d?|mi|nb|q\d?|qr|qc|qm\d?|li\d?|pc|pr|pm|b"
MIN_LINE_CHARS = 10
# Language folder names follow the repo convention "iso_name", e.g. "gbp_gbeya".
LANG_DIR_RE = regex.compile(r"^[a-z]{3}_[\w-]+$")


def nfc(s):
    return unicodedata.normalize("NFC", s)


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

    per_lang, pool_counts = {}, {}
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
