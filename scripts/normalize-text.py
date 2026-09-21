"""Normalize all the text in the given list of files according to the desired format."""


import argparse
from pathlib import Path
from unicodedata import normalize


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "file",
        metavar="/PATH/TO/FILE",
        type=Path,
        nargs="+",help="files to normalize"
    )
    ap.add_argument(
        "--form",
        default="NFD",
        help="normalization form"
    )
    args = ap.parse_args()
    for p in args.file:
        if not p.is_file():
            print(f"Error: File not found: {p}")
            continue
        # Read file into memory, iterate over lines.
        text = p.read_text()
        final_newline = text[-1] == "\n"
        lines = text.splitlines()
        new_lines = []
        for i, line in enumerate(lines):
            nline = normalize(args.form, line)
            if nline != line:
                new_lines.append(nline)
            else:
                new_lines.append(line)
        if new_lines != lines:
            new_text = "\n".join(new_lines)
            if final_newline:
                new_text += "\n"
            p.write_text(new_text)


if __name__ == "__main__":
    main()
