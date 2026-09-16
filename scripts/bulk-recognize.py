"""Given a base folder, perform OCR on all contained images.

Output is given in an accompanying TXT file with the same name
but different extension as the image."""

import argparse
from pathlib import Path

import pytesseract


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "basedir",
        metavar="PATH/TO/IMAGES_DIR",
        type=Path,
        help="text image file to recognize",
    )
    args = parser.parse_args()

    dir = args.basedir

    pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"
    for img in dir.iterdir():
        if img.is_dir() or img.suffix != ".png":
            continue

        outfile = dir / f"{img.stem}.gt.txt"
        # don't overwrite already-created GT.TXT files
        if outfile.is_file():
            continue

        outfile.write_text(pytesseract.image_to_string(str(img), lang="Latin_afr"))


if __name__ == "__main__":
    main()
