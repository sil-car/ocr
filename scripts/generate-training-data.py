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

from matplotlib import font_manager
from pathlib import Path


# Global variables.
writing_system_name = 'Latin_afr'

variables = {
    # More info to be considered here:
    # https://docs.google.com/spreadsheets/d/1sltGTvYpa1OvK3XqQy1UivA6nYyZCCdWfLrnAXHmTm4
    'cases': [
        'lower', 'upper',
    ],
    'consonants': [
        # Includes:
        #   - nasalized consonants
        #   - possibility that consonants take top diacritics b/c grammatical tone
        #   - all consonants present on the CMB Multilingual keyboard
        "b", "c", "d", "f", "g",
        "h", "j", "k", "l", "m",
        "n", "p", "q", "r", "s",
        "t", "v", "w", "x", "z",
        "ɓ", "ɗ", "m̃", "ñ", "ŋ", "ŋ̃", "ẅ", "ꞌ",
    ],
    'diac_top': [
        # Includes all combining diacritics present on the CMB Multilingual keyboard.
        b'\\u0300', # combining grave accent
        b'\\u0301', # combining acute accent
        b'\\u0302', # combining circumflex
        b'\\u0303', # combining tilde above
        b'\\u0304', # combining macron
        b'\\u0308', # combining diaeresis
        b'\\u0327', # combining cedilla
        b'\\u030d', # combining vert. line above
        b'\\u1dc4', # combining macron-acute
        b'\\u1dc5', # combining grave-macron
        b'\\u1dc6', # combining macron-grave
        b'\\u1dc7', # combining acute-macron
    ],
    'diac_bot': [
        # Includes all combining diacritics present on the CMB Multilingual keyboard.
        b'\\u0323', # combining dot below
        b'\\u0327', # combining cedilla
        b'\\u0330', # combining tilde below
    ],
    'fonts': [
        'Andika Afr',
        'Charis SIL',
        'DejaVu Sans',
        'DejaVu Serif',
        'Doulos SIL',
        'Gentium',
        # 'Abyssinica SIL', # mainly for Ethiopic script
        # 'Arial', # doesn't handle all characters
        # 'Carlito', # doesn't handle all characters
        # 'Comic Sans MS', # doesn't handle all characters
        # 'Galatia SIL', # mainly for basic Latin and Greek
        # 'Liberation Sans', # doesn't handle all characters
        # 'Times New Roman', # doesn't handle all characters
    ],
    'styles': [
        'Regular',
        'Bold',
        'Italic',
        'Bold Italic'
    ],
    'vowels': [
        # Includes all vowels present on the CMB Multilingual keyboard.
        "a", "e", "i", "o", "u",
        "ɛ", "æ", "ɑ", "ə", "ı", "ɨ", "ɔ", "ø", "œ", "ʉ",
    ],
}


# Function definitions.
def show_character_combinations(vs):
    # Calculate total number of unique vowel+diacritic characters.
    num_vowels = len(vs.get('vowels'))
    num_top_diac = len(vs.get('diac_top'))
    num_bot_diac = len(vs.get('diac_bot'))
    # Vowels can receive both top and bottom diacritics.
    num_vowel_combos = (num_top_diac + 1) * (num_bot_diac + 1) * num_vowels

    # Get total number of consonants.
    num_consonants = len(vs.get('consonants'))
    # Consonants can receive top diacritics b/c of grammatical tone markings.
    num_consonant_combos = (num_top_diac + 1) * num_consonants

    # Calculate total number of all characters.
    num_chars = num_consonant_combos + num_vowel_combos

    # Calculate total number of unique displayed characters.
    num_fonts = len(vs.get('fonts'))
    num_styles = len(vs.get('styles'))
    num_cases = len(vs.get('cases'))
    combinations = num_chars * num_fonts * num_styles * num_cases

    print(f"Character list:")
    print(f"Consonants: {', '.join(vs.get('consonants'))}")
    print(f"Vowels: {', '.join(vs.get('vowels'))}")
    print(f"Top diacritics: {b', '.join(vs.get('diac_top'))}")
    print(f"Bottom diacritics: {b', '.join(vs.get('diac_bot'))}")
    print()
    print(f"Character counts:")
    print(f"{num_vowel_combos}\tvowels with or without top or bottom diacritics")
    print(f"{num_consonant_combos}\tconsonants with or without top diacritics")
    print(f"-" * 40)
    print(f"{num_chars}\ttotal unique characters")
    print()
    print(f"{num_fonts}\tfonts")
    print(f"{num_styles}\tstyles")
    print(f"{num_cases}\tcases (upper/lower)")
    print(f"-" * 40)
    print(f"{combinations}\t total possible combinations")

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

def get_available_fonts():
    # https://stackoverflow.com/a/68810954
    fonts = {}
    fpaths = font_manager.findSystemFonts()
    for p in fpaths:
        try:
            f = font_manager.get_font(p)
        except RuntimeError:
            continue
        if not fonts.get(f.family_name):
            fonts[f.family_name] = {}
        fonts[f.family_name][f.style_name] = p
    return fonts

def generate_text_line_chars(vs, length=40, vowel_wt=1, top_dia_wt=0.5, bot_dia_wt=0.2):
    """return a line of given length with a random mixture of valid charachers"""
    # choices:
    #   - lower or upper case
    #   - consonant or vowel
    #   - 0 or 1 top diacritic
    #   - 0 or 1 bottom diacritic
    s = b''
    for i in range(length):
        # Choose between lower or upper case.
        # upper = get_binary_choice(wt=0.1)
        upper = get_binary_choice(wt=1)

        # Choose between consonant or vowel.
        c_bases = ['consonants', 'vowels']
        # n = get_binary_choice(wt=vowel_wt)
        n = get_binary_choice(wt=1)
        # print(f"c/v choice: {n}")
        c_base = c_bases[n]

        # Choose character index from base.
        n = get_random_index(len(vs.get(c_base)))
        # print(f"{c_base} index: {n}")
        c = vs.get(c_base)[n]
        if upper:
            c = c.upper()
        u = c.encode('unicode-escape')
        dt = None
        db = None
        if c_base == 'vowels':
            # accept_dt = get_binary_choice(wt=top_dia_wt)
            accept_dt = get_binary_choice(wt=1)
            n = get_random_index(len(vs.get('diac_top')))
            # print(f"dt choice: {accept_dt}")
            # if accept_dt:
            #     print(f"dt index: {n}")
            dt = vs.get('diac_top')[n] if accept_dt == 1 else None
            # accept_db = get_binary_choice(wt=bot_dia_wt)
            accept_db = get_binary_choice(wt=1)
            n = get_random_index(len(vs.get('diac_bot')))
            # print(f"db choice: {accept_db}")
            # if accept_db:
            #     print(f"db index: {n}")
            db = vs.get('diac_bot')[n] if accept_db else None
        if dt:
            u += dt
        if db:
            u += db
        s += u
    return s.decode('unicode-escape')

def generate_text_line_png(chars, fontfile):
    with fitz.open() as doc:
        # TODO: Set page width based on font's needs?
        page = doc.new_page(width=350, height=20)
        page.insert_font(fontname='test', fontfile=fontfile)
        pt = fitz.Point(5, 15)
        rc = page.insert_text(pt, chars, fontname='test')
        pix = page.get_pixmap()
        return pix

def generate_training_data_pair(chars, fontname, fontstyle, fontfile):
    name = f"{time.time()}-{fontname.replace(' ', '_')}-{fontstyle.replace(' ', '_')}"
    txtdata = chars
    pngdata = generate_text_line_png(chars, fontfile)
    return name, txtdata, pngdata

def verify_fonts(vs):
    installed_fonts = get_available_fonts()
    missing_fonts = []
    for f in vs.get('fonts'):
        if f not in installed_fonts.keys():
            missing_fonts.append(f)
    if len(missing_fonts) > 0:
        print(f"ERROR: Not all required fonts are installed:")
        for m in missing_fonts:
            print(f"  - {m}")
        exit(1)

def choose_font():
    pass

def save_training_data_pair(gt_dir, name, txtdata, pngdata):
    txtfile = gt_dir / f"{name}.gt.txt"
    pngfile = gt_dir / f"{name}.png"

    # Write out file contents.
    txtfile.write_text(txtdata)
    pngdata.save(pngfile)

def get_parsed_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-c', '--combinations',
        action='store_true',
        help="output character list and counts, then exit",
    )
    parser.add_argument(
        '-i', '--iterations',
        type=int,
        help="create \"i\" iterations of ground truth data",
    )
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
    return parser.parse_args()

def main():
    ground_truth_dir = get_ground_truth_dir(writing_system_name)

    system_fonts = get_available_fonts()
    verify_fonts(variables)
    # for n, s in system_fonts.items():
    #     print(n, s)
    # exit()

    # Handle command args.
    args = get_parsed_args()

    if args.combinations:
        show_character_combinations(variables)
        exit()

    if not args.iterations:
        args.iterations = 1
    if args.reset:
        reset_ground_truth(ground_truth_dir)
        exit()

    # Generate data.
    for i in range(args.iterations):
        char_line = generate_text_line_chars(variables)

        # Choose font family.
        n = get_random_index(len(variables.get('fonts')))
        font_fam = variables.get('fonts')[n]

        # Choose font style.
        n = get_random_index(len(variables.get('styles')))
        font_sty = variables.get('styles')[n]
        fontfile = system_fonts.get(font_fam).get(font_sty)
        if not fontfile: # not all fonts include all styles
            continue

        # Generate files.
        name, txtdata, pngdata = generate_training_data_pair(char_line, font_fam, font_sty, fontfile)
        if args.simulate:
            # TODO: Is there some way to verify TXT and PNG file contents without saving them to disk?
            print("INFO: Simulation; no files generated.")
            continue
        else:
            save_training_data_pair(ground_truth_dir, name, txtdata, pngdata)


if __name__ == '__main__':
    main()
