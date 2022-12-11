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
import subprocess
import tempfile
import time

from matplotlib import font_manager
from pathlib import Path
from PIL import Image


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
        "ɓ", "ɗ", "ŋ", "ẅ", "ꞌ", "ʼ",
    ],
    'diac_top': [
        # Includes all combining diacritics present on the CMB Multilingual keyboard.
        b'\\u0300', # combining grave accent
        b'\\u0301', # combining acute accent
        b'\\u0302', # combining circumflex
        b'\\u0303', # combining tilde above
        b'\\u0304', # combining macron
        b'\\u0308', # combining diaeresis
        b'\\u030c', # combining caron
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
        'Andika',
        'Andika Compact',
        'Charis SIL',
        'Charis SIL Compact',
        'DejaVu Sans',
        'DejaVu Serif',
        'Doulos SIL',
        'Gentium',
        # 'Abyssinica SIL', # mainly for Ethiopic script
        # 'Andika New Basic', # doesn't handle all characters
        # 'Arial', # doesn't handle all characters
        # 'Carlito', # doesn't handle all characters
        # 'Comic Sans MS', # doesn't handle all characters
        # 'Galatia SIL', # mainly for basic Latin and Greek
        # 'Liberation Sans', # doesn't handle all characters
        # 'Noto Sans', # doesn't properly handle combined accents
        # 'Noto Serif', # doesn't properly handle combined accents
        # 'Times New Roman', # doesn't handle all characters
    ],
    'numbers': ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'],
    'space': [' '],
    'styles': [
        'Regular',
        'Bold',
        'Italic',
        'Bold Italic'
    ],
    'punctuation': [
        # TODO: This compiled without much effort. Some chars could be missing.
        '!', '"', "'", "(", ")", ",", "-", ".", ":", ";", "?",
        "[", "]", "¡", "«", "»", "“", "”", "‹", "›"
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

    # Get number of numbers & punctuation characters.
    num_numbers = len(vs.get('numbers'))
    num_punctuation_chars = len(vs.get('space')) + len(vs.get('punctuation'))

    # Calculate total number of all characters.
    num_cased_chars = num_consonant_combos + num_vowel_combos
    num_uncased_chars = num_numbers + num_punctuation_chars
    num_chars = num_cased_chars + num_uncased_chars

    # Calculate total number of unique displayed characters.
    num_fonts = len(vs.get('fonts'))
    num_styles = len(vs.get('styles'))
    num_cases = len(vs.get('cases'))
    # combinations = num_chars * num_fonts * num_styles * num_cases
    combinations = (num_cased_chars * num_cases + num_uncased_chars) * num_fonts * num_styles

    print(f"Character list:")
    print(f"Consonants: {''.join(vs.get('consonants'))}")
    print(f"Vowels: {''.join(vs.get('vowels'))}")
    print(f"Top diacritics: {b', '.join(vs.get('diac_top'))}")
    print(f"Bottom diacritics: {b', '.join(vs.get('diac_bot'))}")
    print(f"Numbers: {''.join(vs.get('numbers'))}")
    print(f"Punctuation: {''.join(vs.get('punctuation'))}")
    print()
    print(f"Character counts:")
    print(f"{num_vowel_combos}\tvowels with or without top or bottom diacritics")
    print(f"{num_consonant_combos}\tconsonants with or without top diacritics")
    print(f"{num_numbers}\tnumbers")
    print(f"{num_punctuation_chars}\tpunctuation characters")
    print(f"-" * 40)
    print(f"{num_chars}\ttotal unique characters")
    print()
    print(f"{num_fonts}\tfonts")
    print(f"{num_styles}\tstyles (not all fonts support all styles)")
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

def get_binary_choice(prob=0.5):
    # 1 == yes/true; 0 = no/false
    # prob of 1.0 = always yes/true; prob of 0.0 = never yes/true
    # https://stackoverflow.com/a/5887040
    return random.random() < prob

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

def find_extent(pil_img, axis='x', etype='max'):
    extent = None
    # Set dimensions.
    if axis == 'x':
        d1, d2 = pil_img.size
    elif axis == 'y':
        d2, d1 = pil_img.size
    # Set ranges.
    if etype == 'min':
        r1 = range(d1)
        r2 = range(d2)
    elif etype == 'max':
        r1 = range(d1-1, -1, -1)
        r2 = range(d2-1, -1, -1)
    # Find extent.
    for x in r1:
        if extent:
            break
        for y in r2:
            if axis == 'x':
                pixel = pil_img.getpixel((x, y))
            elif axis == 'y':
                pixel = pil_img.getpixel((y, x))
            if pixel[0] < 255:
                extent = x
                break
    return extent

def get_box_extents_pil(pil_img):
    x_min = find_extent(pil_img, axis='x', etype='min')
    y_min = find_extent(pil_img, axis='y', etype='min')
    x_max = find_extent(pil_img, axis='x', etype='max')
    y_max = find_extent(pil_img, axis='y', etype='max')
    return x_min, y_min, x_max, y_max

def get_random_c_type(index, length, options, last_c_type):
    c_type = None
    for t, p in sorted(options.items(), key=lambda kv: (kv[1], kv[0])):
        if get_binary_choice(p):
            c_type = t
            break
    if not c_type: # fall back to consonant
        c_type = 'consonants'
    return c_type

def set_data_filename(fontname, fontstyle):
    return f"{time.time()}-{fontname.replace(' ', '_')}-{fontstyle.replace(' ', '_')}"

def generate_text_line_random_chars(vs, length=40):
    """return a line of given length with a random mixture of valid charachers"""
    # choices:
    #   - lower or upper case
    #   - consonant or vowel
    #   - 0 or 1 top diacritic
    #   - 0 or 1 bottom diacritic
    s = b''
    for i in range(length):
        # Choose between lower or upper case.
        upper = get_binary_choice(p=0.5)

        # Choose between consonant or vowel.
        c_bases = ['consonants', 'vowels']
        n = get_binary_choice(p=0.5)
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
            accept_dt = get_binary_choice(p=0.5)
            n = get_random_index(len(vs.get('diac_top')))
            # print(f"dt choice: {accept_dt}")
            # if accept_dt:
            #     print(f"dt index: {n}")
            dt = vs.get('diac_top')[n] if accept_dt == 1 else None
            accept_db = get_binary_choice(p=0.5)
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

def generate_text_line_weighted_chars(vs, length=40, vowel_wt=1, top_dia_wt=0.5, bot_dia_wt=0.2):
    """return a line of given length with a weighted mixture of valid charachers"""
    # Define probabilities.
    # Base characters; should equal 100%,
    p_space = 0.13
    p_num   = 0.02
    p_punct = 0.05
    p_vowel = 0.40
    p_conso = 0.40
    # Modifications to base characters.
    p_upper = 0.10 # of all consonants & vowels
    p_vtpdi = 0.25 # of vowels (vowel top diacritic)
    p_vbtdi = 0.10 # of vowels (vowel bottom diacritic)
    p_ctpdi = 0.05 # of consonants (consonant top diacritic)
    # Special probability adjustments.
    p_a     = 0.002 # to overcome over-recognized alphas
    p_schwa = 0.002 # to overcome open-o being paired with schwa
    p_y     = 0.002 # to overcome over-recognized 'v' in place of 'y'

    default_options = {
        'consonants': p_conso,
        'numbers': p_num,
        'punctuation': p_punct,
        'space': p_space,
        'vowels': p_vowel,
    }

    s = b''
    last_c_type = None
    last_u = None
    for i in range(length):
        options = default_options.copy()
        # Special treatment for 'space'.
        if i == 0 or i == length - 1 or last_c_type == 'space':
            # Shouldn't be a space at beginning or end of string, or after another space.
            options.pop('space')
        # Get base character type.
        c_type = get_random_c_type(i, length, options, last_c_type)
        last_c_type = c_type
        c_opts = vs.get(c_type)
        c = c_opts[get_random_index(len(c_opts))]

        # Special treatment to improve recognition of some characters.
        if c_type == 'consonants' and c != 'y' and get_binary_choice(p_y):
            c = 'y'
        if c_type == 'vowels':
            if c != 'a':
                if get_binary_choice(p_a):
                    c = 'a'
            elif c != 'ə':
                if get_binary_choice(p_schwa):
                    c = 'ə'

        # Set case.
        if c_type in ['consonants', 'vowels'] and get_binary_choice(p_upper):
            c = c.upper()

        u = c.encode('unicode-escape')

        # Set diacritics.
        use_bot_diac = False
        use_top_diac = False
        if c_type == 'consonants':
            use_top_diac = get_binary_choice(p_ctpdi)
        elif c_type == 'vowels':
            use_top_diac = get_binary_choice(p_vtpdi)
            use_bot_diac = get_binary_choice(p_vbtdi)
        # Add lower diacritics first: https://www.unicode.org/reports/tr15/#Examples
        if use_bot_diac:
            diac_bot_list = vs.get('diac_bot')
            u += diac_bot_list[get_random_index(len(diac_bot_list))]
        if use_top_diac:
            diac_top_list = vs.get('diac_top')
            u += diac_top_list[get_random_index(len(diac_top_list))]

        # Add characters to string.
        last_u = u
        s += u

    return s.decode('unicode-escape')

def generate_text_line_png(chars, fontfile):
    with fitz.open() as doc:
        # TODO: Set page width based on font's needs?
        page = doc.new_page(width=350, height=21)
        page.insert_font(fontname='test', fontfile=fontfile)
        # Only built-in PDF fonts are supported by get_text_length();
        #   have to crop the box outside of fitz/muPDF.
        #   Ref: https://pymupdf.readthedocs.io/en/latest/functions.html#get_text_length
        # text_length = fitz.get_text_length(chars, fontname='test')
        pt = fitz.Point(5, 16)
        rc = page.insert_text(pt, chars, fontname='test')
        # Use dpi to give optimum character height (default seems to be 100):
        #   Ref: https://groups.google.com/g/tesseract-ocr/c/Wdh_JJwnw94/m/24JHDYQbBQAJ
        opt_char_ht = 40 # a proxy; actual char ht is a few px more b/c spacing
        dpi=int((88/13)*opt_char_ht - 636/13) # calculated using (22, 100), (35, 188)
        pix = page.get_pixmap(dpi=dpi)

    # Crop the pixmap to remove extra whitespace.
    # Convert to PIL Image.
    #   Ref: https://github.com/pymupdf/PyMuPDF/issues/322#issuecomment-512561756
    img = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
    # Get boundary extents.
    box_extents = list(get_box_extents_pil(img))
    # Add padding around text.
    pad = 3
    for i in range(len(box_extents)):
        if i < 2: # left & top
            box_extents[i] -= pad
        else: # right & bottom
            box_extents[i] += pad
    # Crop and return the image.
    return img.crop(box_extents)

# def generate_training_data_pair(chars, fontname, fontstyle, fontfile):
def generate_training_data_pair(chars, fontfile):
    # name = set_data_filename(fontname, fontstyle)
    pngdata = generate_text_line_png(chars, fontfile)
    # return name, txtdata, pngdata
    return chars, pngdata

def generate_text2image_data_pair(basedir, filename, chars, fontname, fontstyle):
    if fontstyle == 'Regular':
        font = fontname
    else:
        font = f"{fontname} {fontstyle}"

    # Create tempfile for chars & use it to create TIFF image with text2image.
    # Ref: https://stackoverflow.com/a/15235559
    with tempfile.NamedTemporaryFile(mode='w+') as f:
        f.write(chars)
        f.flush()
        cmd = [
            'text2image',
            f"--text={f.name}",
            f"--outputbase={basedir}/{filename}",
            f"--fonts_dir=/usr/share/fonts",
            f"--font={font}"
        ]
        result = subprocess.run(cmd)

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
    parser.add_argument(
        '-t', '--use-text2image',
        action='store_true',
        help="use text2image script to generate training data instead of built-in function"
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help="show verbose output"
    )
    return parser.parse_args()

def main():
    ground_truth_dir = get_ground_truth_dir(writing_system_name)

    system_fonts = get_available_fonts()
    verify_fonts(variables)

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
        line_length = 50
        char_line = generate_text_line_weighted_chars(variables, length=line_length)
        if args.verbose:
            print(f"INFO: {char_line}")
            print(f"INFO: {b''.join(c.encode('unicode-escape') for c in char_line)}")

        # Choose font family.
        fonts = variables.get('fonts')
        n = get_random_index(len(fonts))
        font_fam = fonts[n]
        if args.verbose:
            print(f"INFO: {font_fam}")

        # Choose font style.
        styles = variables.get('styles')
        n = get_random_index(len(styles))
        font_sty = styles[n]
        if args.verbose:
            print(f"INFO: {font_sty}")
        fontfile = system_fonts.get(font_fam).get(font_sty)
        if not fontfile: # not all fonts include all styles
            if args.verbose:
                print("INFO: No font file found. Skipping font style.")
            continue

        # Generate files.
        filename = set_data_filename(font_fam, font_sty)
        txtdata = char_line
        if args.verbose:
            print(f"INFO: base name: {filename}")
        if not args.use_text2image:
            # name, txtdata, pngdata = generate_training_data_pair(char_line, font_fam, font_sty, fontfile)
            # txtdata, pngdata = generate_training_data_pair(char_line, fontfile)
            pngdata = generate_text_line_png(txtdata, fontfile)
            if not args.simulate:
                # if args.verbose:
                #     print(f"INFO: base name: {name}")
                # save_training_data_pair(ground_truth_dir, name, txtdata, pngdata)
                save_training_data_pair(ground_truth_dir, filename, txtdata, pngdata)
        else:
            generate_text2image_data_pair(ground_truth_dir, filename, txtdata, font_fam, font_sty)

    if args.simulate:
        # TODO: Is there some way to verify TXT and PNG file contents without saving them to disk?
        print("INFO: Simulation; no files generated.")


if __name__ == '__main__':
    main()
