#!/usr/bin/env python3
"""Evaluate all provided language models with all provided test documents."""

import csv
import jiwer
import os
import pytesseract
import unicodedata

from pathlib import Path
from PIL import Image

repo_dir_path = Path(__file__).parents[1]
MODELS_DIR_PATH = repo_dir_path / "tessdata"
MODELS = [m.stem for m in MODELS_DIR_PATH.glob("*.traineddata")]
MODELS.sort()

EVALUATION_DIR_PATH = repo_dir_path / "data" / "evaluation"
GT_FILES = [f for f in EVALUATION_DIR_PATH.rglob("**/*.gt.txt")]
GT_FILES.sort()


def get_timestamp(file_path):
    if file_path.is_file():
        return str(file_path.stat().st_mtime)


def convert_to_nfd(chars):
    return unicodedata.normalize("NFD", chars)


def compare_text_files(truth_file, hypothesis_file):
    """
    Calculate and return CER between two text files.
    """
    with open(truth_file) as t:
        truth = convert_to_nfd(t.read())

    with open(hypothesis_file) as h:
        hypothesis = convert_to_nfd(h.read())

    cer_default_transform = jiwer.transforms.Compose(
        [
            jiwer.transforms.Strip(),
            jiwer.transforms.ReduceToListOfListOfChars(),
        ]
    )

    result = jiwer.process_characters(
        reference=truth,
        hypothesis=hypothesis,
        reference_transform=cer_default_transform,
        hypothesis_transform=cer_default_transform,
    )
    # Ref. for CER/WER:
    #   CER = (S + D + I) / (S + D + H)
    #   https://github.com/jitsi/jiwer/blob/33067d50224717e20da0ec1a3ae388b9f5a0327d/jiwer/measures.py#L207
    # H = result.get("hits")
    H = result.hits
    # S = result.get("substitutions")
    S = result.substitutions
    # D = result.get("deletions")
    D = result.deletions
    # I = result.get("insertions")
    # Ref. for 'hits' calculation:
    #   H = N - (S + D)
    #   https://github.com/jitsi/jiwer/blob/33067d50224717e20da0ec1a3ae388b9f5a0327d/jiwer/measures.py#L373
    N = S + D + H
    return {
        "cer": result.cer,
        "deletions": result.deletions,
        "hits": result.hits,
        "insertions": result.insertions,
        "number-truth": N,
        "substitutions": result.substitutions,
    }


def run_ocr(infile_path, model, outfile_path):
    # print(f"Recognizing text from {infile_path.name} using model {model}...")
    with Image.open(infile_path) as img:
        htext = pytesseract.image_to_string(
            img, lang=model, config="-c page_separator=''"
        )
    outfile_path.write_text(htext)


def main():
    # Set MODELS dir as TESDDATA_PREVIX in ENV.
    os.environ["TESSDATA_PREFIX"] = str(MODELS_DIR_PATH)

    data_csv = EVALUATION_DIR_PATH / "data.csv"
    csv_fieldnames = [
        "timestamp",
        "iso_lang",
        "image-file",
        "truth-text-file",
        "model",
        "ocr-text-file",
        "cer",
        "number-truth",
        "substitutions",
        "deletions",
        "insertions",
        "hits",
    ]

    # Ensure data.csv exists.
    if not data_csv.is_file():
        data_csv.touch()
        with open(data_csv, "w", newline="") as c:
            dwriter = csv.DictWriter(c, fieldnames=csv_fieldnames)
            dwriter.writeheader()

    # Run evaluations.
    for model_name in MODELS:
        print(f"Using model: {model_name}")
        for gt_file in GT_FILES:
            basename = Path(str(gt_file).replace(".gt.txt", ""))
            image_file = Path(f"{basename}.png")
            out_file = Path(f"{basename}.{model_name}.txt")
            print(f" - Evaluating file: {image_file.name}")

            # Ensure image_file has been OCR'd.
            if not out_file.is_file():
                print(f" - Creating file: {out_file.name}")
                run_ocr(image_file, model_name, out_file)

            # Get current data from CSV file.
            with open(data_csv) as c:
                reader = csv.reader(c)
                timestamps = [r[0] for r in reader]

            timestamp = get_timestamp(out_file)

            if timestamp not in timestamps:
                # Initialize the CSV data.
                results = {}
                results["timestamp"] = get_timestamp(out_file)  # UID for CSV entries

                # Complete the rest of the CSV data.
                results["iso_lang"] = gt_file.parent.name.split("_")[0]
                results["image-file"] = str(image_file)
                results["truth-text-file"] = str(gt_file)
                results["model"] = model_name
                results["ocr-text-file"] = str(out_file)

                results.update(compare_text_files(gt_file, out_file))
                results["cer"] = round(results.get("cer"), 4)
                with open(data_csv, "a", newline="") as c:
                    dwriter = csv.DictWriter(c, fieldnames=csv_fieldnames)
                    dwriter.writerow(results)


if __name__ == "__main__":
    main()
