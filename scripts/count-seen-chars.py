#!/usr/bin/env python3

"""Count how often each character was seen in training up to a given iteration.

tesstrain shuffles the training lines into list.train, and lstmtraining with
--sequential_training reads them in that order, one line per training
iteration, starting again from the top after the last line. So the lines seen
by iteration X are the first X entries of list.train (wrapping around). For
each entry, the ground truth is the ".gt.txt" file next to its ".lstmf" file.

Counts are per NFC code point, the way tesseract's unicharset splits text
(precomposed letters are their own characters; other combinations are a base
letter plus a combining mark), so they can be compared with
generate-training-data.py --min-char-count.

The iteration can be given directly or taken from a checkpoint file name,
e.g. "Latin_afr_4.084_130_200.checkpoint" -> 200 (the last number, training
iterations).

Output: a table of code points, fewest seen first, with the count seen up to
the iteration and the count in the whole list. By default only non-ASCII code
points are listed; use --all for every code point.
"""

import argparse
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

CHECKPOINT_RE = re.compile(r"_(\d+)\.checkpoint$")


def iterations_from(value):
    """return an iteration count from a number or a checkpoint file name"""
    if value.isdigit():
        return int(value)
    m = CHECKPOINT_RE.search(value)
    if not m:
        raise argparse.ArgumentTypeError(
            f"not a number or a checkpoint name ending in _<iterations>.checkpoint: {value}"
        )
    return int(m.group(1))


def find_gt(lstmf, list_file):
    """return the .gt.txt path for an .lstmf entry of list.train, or None

    Entries are usually absolute; relative ones are tried from the current
    folder and from the list file's folder and its parents.
    """
    # String surgery, not with_suffix(): older file names contain dots.
    rel = Path(lstmf.removesuffix(".lstmf") + ".gt.txt")
    if rel.is_absolute():
        return rel if rel.is_file() else None
    for base in (Path.cwd(), list_file.parent, *list_file.resolve().parents):
        p = base / rel
        if p.is_file():
            return p
    return None


def show(c):
    """printable form of a code point; combining marks get a dotted circle"""
    if unicodedata.combining(c):
        return f"◌{c}"
    if c == " ":
        return "␣"
    return c if c.isprintable() else ""


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("list_train", type=Path,
                    help="tesstrain's list.train, e.g. ~/tesstrain/data/Latin_afr/list.train")
    ap.add_argument("iterations", type=iterations_from,
                    help="training iterations, or a checkpoint file name")
    ap.add_argument("-m", "--min-count", type=int, default=300,
                    help="flag code points seen fewer times than this [300]")
    ap.add_argument("-a", "--all", action="store_true",
                    help="list ASCII code points too")
    ap.add_argument("-o", "--output", type=Path,
                    help="also write the table to this TSV file")
    args = ap.parse_args()

    entries = [
        line.strip()
        for line in args.list_train.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not entries:
        print(f"Error: no entries in {args.list_train}", file=sys.stderr)
        sys.exit(1)

    # Read each ground truth once; count how many times each entry was seen.
    texts, missing = [], 0
    for e in entries:
        gt = find_gt(e, args.list_train)
        if gt is None:
            missing += 1
            texts.append("")
        else:
            texts.append(unicodedata.normalize(
                "NFC", gt.read_text(encoding="utf-8").strip()))
    if missing:
        print(f"WARNING: no .gt.txt found for {missing} of {len(entries)} entries",
              file=sys.stderr)

    full_passes, rest = divmod(args.iterations, len(entries))
    seen, total = Counter(), Counter()
    for i, t in enumerate(texts):
        c = Counter(t)
        total.update(c)
        times = full_passes + (1 if i < rest else 0)
        if times:
            for cp, n in c.items():
                seen[cp] += n * times

    rows = [
        (seen[cp], total[cp], cp)
        for cp in total
        if not cp.isspace() and (args.all or ord(cp) > 127)
    ]
    rows.sort(key=lambda r: (r[0], r[2]))
    below = [r for r in rows if r[0] < args.min_count]

    passes = args.iterations / len(entries)
    print(f"{args.iterations} iterations = {passes:.2f} passes through "
          f"{len(entries)} training lines.")
    print(f"{len(rows) - len(below)} of {len(rows)} "
          f"{'' if args.all else 'non-ASCII '}code points seen at least "
          f"{args.min_count} times; {len(below)} below.")

    header = "code_point\tchar\tname\tseen\tin_list\tstatus"
    lines = [header] + [
        f"U+{ord(cp):04X}\t{show(cp)}\t{unicodedata.name(cp, '')}\t{s}\t{t}"
        f"\t{'LOW' if s < args.min_count else 'ok'}"
        for s, t, cp in rows
    ]
    if args.output:
        args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Table written to {args.output}")
    # On screen: the code points below the minimum (or the 20 least seen).
    print()
    for line in lines[: 1 + max(len(below), min(20, len(rows)))]:
        print(line)


if __name__ == "__main__":
    main()
