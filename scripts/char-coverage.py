#!/usr/bin/env python3
"""
Recursively scan *.gt.txt files under a directory and print a
three-column report: Unicode codepoint, the character itself, and its
total occurrence count.

If --reference-config is given (a Latin_afr-style config.toml with a
[properties] table: consonants, vowels, numbers, punctuation, space,
diacritics.top, diacritics.bottom), the report also includes any
character defined there that occurs zero times in the data, so
under-covered characters are visible instead of silently absent.

Upper/lower case variants are generated automatically for consonants
and vowels (the config is assumed to list only one case). Diacritics,
numbers, punctuation, and space are used as-is, with no case variants.

Usage:
    ./char_coverage.py [root_dir] [--reference-config PATH]
                        [--sort count|codepoint]

Defaults:
    root_dir           = data/evaluation/full-coverage-set
    reference-config   = data/Latin_afr/config.toml (only used if present)
    sort               = count (ascending, so zero-count rows are easy to spot)
"""

import argparse  # noqa I001
import sys
import tomllib
from collections import Counter
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "root_dir",
        nargs="?",
        default="data/evaluation/full-coverage-set",
        help="Directory to search recursively for *.gt.txt files "
             "(default: %(default)s)",
    )
    p.add_argument(
        "--reference-config",
        default="data/Latin_afr/config.toml",
        help="TOML file defining the full valid character set, used to "
             "surface characters with zero occurrences. Pass "
             "--no-reference to skip this. (default: %(default)s)",
    )
    p.add_argument(
        "--no-reference",
        action="store_true",
        help="Don't load a reference config; report only characters "
             "actually found in the data.",
    )
    p.add_argument(
        "--sort",
        choices=["count", "codepoint"],
        default="count",
        help="Sort by occurrence count (ascending, so gaps surface first) "
             "or by codepoint (default: %(default)s)",
    )
    return p.parse_args()


def count_characters(root_dir: Path) -> Counter:
    counts = Counter()
    gt_files = sorted(root_dir.rglob("*.gt.txt"))

    if not gt_files:
        print(f"warning: no *.gt.txt files found under {root_dir}", file=sys.stderr)
        return counts

    exclude = {"\n", "\r"}

    for path in gt_files:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as e:
            print(f"warning: skipping {path} ({e})", file=sys.stderr)
            continue
        for ch in text:
            if ch in exclude:
                continue
            counts[ch] += 1

    return counts


def _flatten_to_chars(value) -> str:
    """Collect every leaf string in a TOML value (str, or list of str,
    nested lists) into one concatenated string of characters."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(_flatten_to_chars(v) for v in value)
    return ""


def load_reference_chars(config_path: Path) -> set:
    """Return the full set of valid characters defined in config.toml,
    with upper/lower case variants added for consonants and vowels."""
    with config_path.open("rb") as f:
        config = tomllib.load(f)

    props = config.get("properties", {})
    if not props:
        print(
            f"warning: no [properties] table found in {config_path}",
            file=sys.stderr,
        )
        return set()

    chars = set()

    # Categories that get both-case variants.
    for key in ("consonants", "vowels"):
        base = _flatten_to_chars(props.get(key, ""))
        for ch in base:
            chars.add(ch)
            chars.add(ch.upper())
            chars.add(ch.lower())

    # Categories used as-is (no case variants).
    diacritics = props.get("diacritics", {})
    for key, value in (
        ("numbers", props.get("numbers", "")),
        ("punctuation", props.get("punctuation", "")),
        ("space", props.get("space", "")),
        ("diacritics.top", diacritics.get("top", "")),
        ("diacritics.bottom", diacritics.get("bottom", "")),
    ):
        for ch in _flatten_to_chars(value):
            chars.add(ch)

    return chars


def graphical_repr(ch: str) -> str:
    """Return a displayable form of ch, substituting visible symbols
    for characters that would otherwise disrupt column alignment or
    be invisible (plain space, combining marks)."""
    replacements = {
        " ": "\u2423",   # OPEN BOX, to make plain space visible
        "\t": "\\t",
        "\n": "\\n",
        "\r": "\\r",
    }
    if ch in replacements:
        return replacements[ch]
    # Combining marks render invisibly/oddly on their own; pair with a
    # dotted circle (U+25CC) so the mark is actually visible.
    import unicodedata
    if unicodedata.category(ch).startswith("M"):
        return "\u25CC" + ch
    return ch


def main():
    args = parse_args()
    root_dir = Path(args.root_dir)

    if not root_dir.is_dir():
        print(f"error: {root_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    counts = count_characters(root_dir)

    reference_chars = set()
    if not args.no_reference:
        config_path = Path(args.reference_config)
        if config_path.is_file():
            reference_chars = load_reference_chars(config_path)
        else:
            print(
                f"warning: reference config {config_path} not found; "
                "reporting only characters found in the data",
                file=sys.stderr,
            )

    all_chars = set(counts) | reference_chars
    for ch in all_chars:
        counts.setdefault(ch, 0)

    if args.sort == "count":
        items = sorted(counts.items(), key=lambda kv: (kv[1], kv[0]))
    else:
        items = sorted(counts.items(), key=lambda kv: kv[0])

    for ch, n in items:
        codepoint = f"U+{ord(ch):04X}"
        print(f"{codepoint}\t{graphical_repr(ch)}\t{n}")


if __name__ == "__main__":
    main()
