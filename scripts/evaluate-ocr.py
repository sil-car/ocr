#!/usr/bin/env python3

import argparse
import csv
import jiwer
import os
import pytesseract
import sys
import unicodedata

from pathlib import Path
from PIL import Image


def validate_filelike_input(input_text, ftype='file'):
    input_path = Path(input_text)
    input_full_path = input_path.expanduser().resolve()
    if ftype == 'file' and not input_full_path.is_file():
        # print(f"Error: Could not find file: {input_text}")
        input_full_path = False
    elif ftype == 'dir' and not input_full_path.is_dir():
        # print(f"Error: Could not find folder: {input_text}")
        input_full_path = False
    return input_full_path

def convert_to_nfc(chars):
    return unicodedata.normalize('NFC', chars)

def convert_to_nfd(chars):
    return unicodedata.normalize('NFC', chars)

def get_timestamp(file_path):
    return str(file_path.stat().st_mtime)

def compare_text_files(truth_file, hypothesis_file):
    """
    Calculate and return CER between two text files.
    """
    with open(truth_file) as t:
        truth = convert_to_nfc(t.read())

    with open(hypothesis_file) as h:
        hypothesis = convert_to_nfc(h.read())

    cer_default_transform = jiwer.transforms.Compose([
            jiwer.transforms.Strip(),
            jiwer.transforms.ReduceToListOfListOfChars(),
    ])

    result = jiwer.cer(
        truth, hypothesis,
        return_dict=True,
        truth_transform=cer_default_transform,
        hypothesis_transform=cer_default_transform,
    )
    # Ref. for CER/WER:
    #   CER = (S + D + I) / (S + D + H)
    #   https://github.com/jitsi/jiwer/blob/33067d50224717e20da0ec1a3ae388b9f5a0327d/jiwer/measures.py#L207
    H = result.get('hits')
    S = result.get('substitutions')
    D = result.get('deletions')
    I = result.get('insertions')
    # Ref. for 'hits' calculation:
    #   H = N - (S + D)
    #   https://github.com/jitsi/jiwer/blob/33067d50224717e20da0ec1a3ae388b9f5a0327d/jiwer/measures.py#L373
    N = S + D + H
    result['number-truth'] = N
    return result

def get_all_ocr_models(tessdata_dir):
    model_files = tessdata_dir.glob('Latin*.traineddata')
    return [f.stem for f in model_files if f.stem != 'Latin_afr']

def run_ocr(infile_path, model, outfile_path):
    print(f"Recognizing text from {infile_path.name} using model {model}...")
    with Image.open(infile_path) as img:
        htext = pytesseract.image_to_string(img, lang=model)
    outfile_path.write_text(htext)

def main():
    description = "Provide CER between a reference text file and a hypothesis text file."
    parser = argparse.ArgumentParser(
        description=description,
        # formatter_class=argparse.RawDescriptionHelpFormatter,
        )
    # parser.add_argument(
    #     '-d', '--dir',
    #     nargs=1,
    #     type=str,
    #     help="directory containing the two text files to compare",
    # )
    parser.add_argument(
        '-l', '--model',
        nargs=1,
        type=str,
        help="name of tesseract model used to create hypothesis file",
    )
    # parser.add_argument(
    #     '-s', '--update-spreadsheet',
    #     action='store_true',
    #     help="update spreadsheet with character comparison data",
    # )
    parser.add_argument(
        '-t', '--truth',
        nargs=1,
        type=str,
        help="path to original (reference) text file",
    )
    parser.add_argument(
        '-o', '--hypothesis',
        nargs=1,
        type=str,
        help="path to recognized (hypothesis) text file",
    )
    parser.add_argument(
        "image_file",
        nargs=1,
        help="image file on which tesseract is to be tested; can also be a .gt.txt file",
    )

    args = parser.parse_args()
    # Set env variables.
    tessdata_dir = Path(__file__).parents[1] / 'tessdata'
    os.environ['TESSDATA_PREFIX'] = str(tessdata_dir)

    # Simple comparison if truth and hypothesis files given.
    if args.truth and args.hypothesis:
        truth = validate_filelike_input(args.truth[0])
        if truth is False:
            print(f"Error: Could not find file: {args.truth[0]}")
            exit(1)
        hypothesis = validate_filelike_input(args.hypothesis[0])
        if hypothesis is False:
            print(f"Error: Could not find file: {args.hypothesis[0]}")
            exit(1)
        results = compare_text_files(truth, hypothesis)
        for k, v in results.items():
            print(f"{k}: {v}")
        exit()

    # Set default evaluation folder and data CSV file.
    eval_dir = Path(__file__).parents[1] / 'data' / 'evaluation'
    data_csv = eval_dir / 'data.csv'
    csv_fieldnames = [
        'timestamp', 'iso_lang', 'image-file', 'truth-text-file', 'model',
        'ocr-text-file', 'cer', 'number-truth', 'substitutions', 'deletions',
        'insertions', 'hits'
    ]

    if not data_csv.is_file():
        data_csv.touch()
        with open(data_csv, 'w', newline='') as c:
            dwriter = csv.DictWriter(c, fieldnames=csv_fieldnames)
            dwriter.writeheader()

    # Set default language model.
    if not args.model:
        args.model = ['Latin']

    # Ensure image_file has been passed.
    if not args.image_file:
        print(f"Error: No image file given.")
        exit(1)

    model_names = [args.model[0]]
    if model_names == ['all']:
        model_names = get_all_ocr_models(tessdata_dir)

    image_file = validate_filelike_input(args.image_file[0])
    if image_file is False:
        print(f"Error: Could not find file: {args.image_file[0]}")
        exit(1)
    base_dir = image_file.parent
    if str(image_file).split('.')[-2:] == ['gt', 'txt']:
        # Input file (args.image_file) actually a .gt.txt file.
        t_file = image_file
        stem = Path(str(t_file).replace('.gt', '')).stem
        image_file = Path(str(t_file).replace('.gt.txt', '.png'))
    elif image_file.suffix == '.png':
        input_ext = '.png'
        t_file = base_dir / f"{image_file.stem}.gt.txt"
        stem = image_file.stem
    else:
        print(f"Error: Invalid image_file: {args.image_file}")
        exit(1)
    truth = validate_filelike_input(t_file)
    if truth is False:
        print(f"Error: Could not find file: {t_file}")
        exit(1)
    for model_name in model_names:
        h_file = base_dir / f"{stem}.{model_name}.txt"
        hypothesis = validate_filelike_input(h_file)
        if hypothesis is False:
            run_ocr(image_file, model_name, h_file)
            hypothesis = validate_filelike_input(h_file)
            if hypothesis is False:
                print(f"Error: File not properly created: {str(h_file)}")

        with open(data_csv) as c:
            reader = csv.reader(c)
            timestamps = [r[0] for r in reader]

        # Initialize the CSV data.
        results = {}
        results['timestamp'] = get_timestamp(hypothesis) # UID for CSV entries

        if results.get('timestamp') not in timestamps:
            # Complete the rest of the CSV data.
            results['iso_lang'] = base_dir.name
            results['image-file'] = str(image_file)
            results['truth-text-file'] = str(t_file)
            results['model'] = model_name
            results['ocr-text-file'] = str(h_file)

            results.update(compare_text_files(truth, hypothesis))
            results['cer'] = round(results.get('cer'), 4)
            with open(data_csv, 'a', newline='') as c:
                dwriter = csv.DictWriter(c, fieldnames=csv_fieldnames)
                dwriter.writerow(results)

if __name__ == '__main__':
    main()
