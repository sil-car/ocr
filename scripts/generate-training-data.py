#!/usr/bin/env python3

"""generate tesseract training data to fine tune the Latin script for use in African languages"""

# https://tesseract-ocr.github.io/tessdoc/tess5/TrainingTesseract-5.html
# Generate training data for Tesseract:
#   - data folder: "data/training/Latin_afr-ground-truth"
#   - image files of individual lines of text: "img.tif|img.png"
#   - text files of individual lines of text: "img.gt.txt"

import argparse
import fitz # PyMuPDF: https://pymupdf.readthedocs.io/en/latest/
import random
import time

from pathlib import Path


# Global variables.
writing_system_name = 'Latin_afr'

variables = {
    'cases': [
        'lower', 'upper'
    ],
    'consonants': [
        "ɓ", "ɗ", "ŋ"
    ],
    'diac_top': [
        b'\\u0300', # combining grave accent
        b'\\u0301', # combining acute accent
        b'\\u0302', # combining circumflex
        b'\\u0303', # combining tilde
        b'\\u0308', # combining diaeresis
    ],
    'diac_bot': [
        b'\\u0327', # combining cedilla
    ],
    'fonts': [
        'Arial',
        'Times New Roman',
        'Liberation Sans',
        'Abyssinica SIL',
        'Andika SIL',
        'Charis SIL',
    ],
    'styles': [
        'regular',
        'bold',
        'italic',
    ],
    'vowels': [
        "a", "e", "i", "o", "u",
        "ɛ", "ə", "ı", "ɨ", "ɔ", "ʉ",
    ],
}


# Function definitions.
def get_git_root(path):
    """find repository root from the path's parents"""
    # https://stackoverflow.com/a/67516092
    for path in Path(path).resolve().parents:
        # Check whether "path/.git" exists and is a directory
        git_dir = path / ".git"
        if git_dir.is_dir():
            return path

def get_ground_truth_dir(script):
    return get_git_root(__file__) / 'data' / 'training'  / f'{script}-ground-truth'

def reset_ground_truth(gt_dir_path):
    """delete all files in the ground-truth folder except .placeholder file"""
    for c in gt_dir_path.iterdir():
        if c.name == '.placeholder':
            continue
        c.unlink()

def get_random_index(num_opt):
    # return random index from integer range
    return random.randrange(num_opt)

def get_binary_choice(wt=1):
    # Outcome is biased towards '1' or 'yes' if wt >= 1, towards 'no' if wt < 1.
    if wt < 1: # bias towards 0
        return 1 if random.randrange(int(1/wt) + 1) == 0 else 0
    else: # bias towards 1
        return 0 if random.randrange(wt + 1) == 0 else 1

def generate_text_line_chars(vars, length=40, vowel_wt=1, top_dia_wt=0.5, bot_dia_wt=0.2):
    """return a line of given length with a random mixture of valid charachers"""
    s = b''
    for i in range(length):
        upper = get_binary_choice(wt=0.1)
        # Choose between consonant or vowel.
        c_bases = ['consonants', 'vowels']
        n = get_binary_choice(wt=vowel_wt)
        # print(f"c/v choice: {n}")
        c_base = c_bases[n]
        # Choose character index from base.
        n = get_random_index(len(vars.get(c_base)))
        # print(f"{c_base} index: {n}")
        c = vars.get(c_base)[n]
        if upper:
            c = c.upper()
        u = c.encode('unicode-escape')
        dt = None
        db = None
        if c_base == 'vowels':
            accept_dt = get_binary_choice(wt=top_dia_wt)
            n = get_random_index(len(vars.get('diac_top')))
            # print(f"dt choice: {accept_dt}")
            # if accept_dt:
            #     print(f"dt index: {n}")
            dt = vars.get('diac_top')[n] if accept_dt == 1 else None
            accept_db = get_binary_choice(wt=bot_dia_wt)
            n = get_random_index(len(vars.get('diac_bot')))
            # print(f"db choice: {accept_db}")
            # if accept_db:
            #     print(f"db index: {n}")
            db = vars.get('diac_bot')[n] if accept_db else None
        if dt:
            u += dt
        if db:
            u += db
        s += u
    return s.decode('unicode-escape')

def generate_text_line_png(chars, fontfile):
    with fitz.open() as doc:
        page = doc.new_page(width=250, height=20)
        page.insert_font(fontname="charis", fontfile=fontfile)
        pt = fitz.Point(5, 15)
        rc = page.insert_text(pt, chars, fontname='charis')
        pix = page.get_pixmap()
        # pix.save(outfile)
        return pix

def generate_text_line_txt(chars):
    if not outfile.is_file():
        outfile.touch()
    with outfile.open('w') as f:
        # f.write(chars)
        return f

def generate_training_data_pair(chars, fontfile):
    name = time.time()
    txtdata = chars
    pngdata = generate_text_line_png(chars, fontfile)
    return name, txtdata, pngdata

def save_training_data_pair(gt_dir, name, txtdata, pngdata):
    txtfile = gt_dir / f"{name}.gt.txt"
    pngfile = gt_dir / f"{name}.png"

    # Write out file contents.
    txtfile.write_text(txtdata)
    pngdata.save(pngfile)

def get_parsed_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-n', '--simulate',
        action='store_true',
        help="generate training data without saving it to disk"
    )
    parser.add_argument(
        '-r', '--reset',
        action='store_true',
        help=reset_ground_truth.__doc__
    )
    parser.add_argument(
        '-i', '--iterations',
        type=int,
        help="create \"i\" iterations of ground truth data",
    )
    return parser.parse_args()

def main():
    combinations = 1
    for k, v in variables.items():
        ct = len(v)
        if k == 'diac_top' or k == 'diac_bot': # allow for no diacritic
            ct += 1
        combinations *= ct
    # print(f"Total possible combinations = {combinations}")
    ground_truth_dir = get_ground_truth_dir(writing_system_name)
    args = get_parsed_args()
    if not args.iterations:
        args.iterations = 1
    if args.reset:
        reset_ground_truth(ground_truth_dir)
        exit()

    # Generate data.
    for i in range(args.iterations):
        char_line = generate_text_line_chars(variables)
        charis_reg = '/usr/share/fonts/truetype/charis/CharisSIL-Regular.ttf'

        name, txtdata, pngdata = generate_training_data_pair(char_line, charis_reg)
        if args.simulate:
            # TODO: Is there some way to verify TXT and PNG file contents without saving them to disk?
            print("INFO: Simulation; no files generated.")
            continue
        else:
            save_training_data_pair(ground_truth_dir, name, txtdata, pngdata)


if __name__ == '__main__':
    main()
