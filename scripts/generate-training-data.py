#!/usr/bin/env python3

"""generate tesseract training data to fine tune the Latin script for use in African languages

Each iteration renders one line of text as an image and saves it with its
ground-truth text. A line is either:
  - a real line from the file(s) given with --lines-file, e.g. the "<lang>.txt"
    or "all.txt" output of extract-text-lines.py; or
  - a pseudo-word line generated from the characters in
    data/Latin_afr/config.toml (--line-length characters long).

With --lines-file, --real-ratio of the images (default 0.75) use real lines and
the rest use pseudo-words, which cover characters missing from the real texts.
Real lines are used in file order, and each line is used once before any line
repeats. Without --lines-file, every line is pseudo-words.

Each line is drawn in a randomly chosen font family and style that has every
character in it, so the image always matches its ground truth; a line that no
allowed font can draw is skipped with a warning.
"""

# https://tesseract-ocr.github.io/tessdoc/tess5/TrainingTesseract-5.html
# Generate training data for Tesseract:
#   - data folder: "data/training/Latin_afr-ground-truth"
#   - image files of individual lines of text: "<name>.png" (or ".tif" with -t)
#   - text files of individual lines of text: "<name>.gt.txt"
#   - <name> is "<7-digit number>-<font>-<style>", e.g.
#     "0000123-Charis_SIL_Compact-Bold_Italic"; numbering continues from the
#     highest number already in the folder.

import argparse
import multiprocessing
import random
import re
import subprocess
import sys
import tempfile
import tomllib
from functools import cache
from pathlib import Path
from unicodedata import normalize

from fontTools.ttLib import TTFont
from matplotlib import font_manager
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# Global variables.
WRITING_SYSTEM_NAME = "Latin_afr"
DEFAULT_CHARACTER_HEIGHT = 48
DEFAULT_DEGRADED_IMAGE_PROBABILITY = 1.0
DEFAULT_ITERATIONS = 1
DEFAULT_LINE_LENGTH = 75
# Keep some pseudo-word lines even when real text is given: many characters
# and diacritic combinations are known to be missing from the real texts.
DEFAULT_REAL_RATIO = 0.75
# Ground-truth files are named "<number>-<font>-<style>"; 7 digits sort
# correctly up to 9,999,999 files (names stay unique beyond that).
FILE_NUMBER_DIGITS = 7
FILE_NUMBER_RE = re.compile(rf"^(\d{{{FILE_NUMBER_DIGITS}}})-")
CORE_FONTS = [
    "Andika",
    "Andika Compact",
    "Charis SIL",
    "Charis SIL Compact",
    "DejaVu Sans",
    "DejaVu Serif",
    "Doulos SIL",
    "Doulos SIL Compact",
    "FreeSans",
    "FreeSerif",
    "Liberation Sans",
    "Liberation Serif",
    "Noto Sans",
    "Noto Serif",
]


def get_git_root(path):
    """find repository root from the path's parents"""
    # https://stackoverflow.com/a/67516092
    for p in Path(path).resolve().parents:
        # Check whether "path/.git" exists and is a directory
        git_dir = p / ".git"
        if git_dir.is_dir():
            return p


def get_model_dir(model_name):
    proj_dir = get_git_root(__file__)
    model_dir = proj_dir / "data" / model_name
    if not model_dir.is_dir():
        print(f"Error: Couldn't find {model_dir}.")
        sys.exit(1)
    return model_dir


def show_character_weights():
    print("Character weights:")
    for k, v in PROPERTIES.get("weights").items():
        print(f"{k}: {v}")
    if PROPERTIES.get("weights").get("p_y"):
        print(
            'NOTE: "p_y" is applied if a non-y consonant is chosen.\nThis is to increase the occurrences of "y" to correct for "y" being frequently\nrecognized as "v".'
        )


def show_character_combinations():
    # Calculate total number of unique vowel+diacritic characters.
    vowels = PROPERTIES.get("vowels")
    num_vowels = len(vowels)
    top_diac = PROPERTIES.get("diacritics").get("top")
    num_top_diac = len(top_diac)
    bot_diac = PROPERTIES.get("diacritics").get("bottom")
    num_bot_diac = len(bot_diac)
    # Vowels can receive both top and bottom diacritics.
    num_vowel_combos = (num_top_diac + 1) * (num_bot_diac + 1) * num_vowels

    # Get total number of consonants.
    consonants = PROPERTIES.get("consonants")
    num_consonants = len(consonants)
    # Consonants can receive top diacritics b/c of grammatical tone markings.
    num_consonant_combos = (num_top_diac + 1) * num_consonants

    # Get number of numbers & punctuation characters.
    numbers = PROPERTIES.get("numbers")
    num_numbers = len(numbers)
    punctuation_chars = PROPERTIES.get("punctuation")
    num_punctuation_chars = len(PROPERTIES.get("space")) + len(
        punctuation_chars
    )

    # Calculate total number of all characters.
    num_cased_chars = num_consonant_combos + num_vowel_combos
    num_uncased_chars = num_numbers + num_punctuation_chars
    num_chars = num_cased_chars + num_uncased_chars

    # Calculate total number of unique displayed characters.
    fonts = PROPERTIES.get("fonts")
    num_fonts = len(fonts)
    num_styles = len(PROPERTIES.get("styles"))
    num_cases = len(PROPERTIES.get("cases"))
    # combinations = num_chars * num_fonts * num_styles * num_cases
    combinations = (
        (num_cased_chars * num_cases + num_uncased_chars) * num_fonts * num_styles
    )

    wts = PROPERTIES.get("weights")
    img_min = int(
        (num_consonants + num_vowels)
        / wts.get("p_conso")
        / wts.get("p_ctpdi")
        / wts.get("p_upper")
        * num_fonts
        * num_styles
        * 2
        / LINE_LENGTH
        / 0.9
    )

    print("CHARACTER LIST:")
    print(f"  Consonants [{num_consonants}]: {''.join(consonants)}")
    print(f"  Vowels [{num_vowels}]: {''.join(vowels)}")
    print(f"  Top diacritics [{num_top_diac}]: {', '.join(top_diac)}")
    print(f"  Bottom diacritics [{num_bot_diac}]: {', '.join(bot_diac)}")
    print(f"  Numbers [{num_numbers}]: {''.join(numbers)}")
    print(f"  Punctuation [{len(punctuation_chars)}]: {''.join(punctuation_chars)}")
    print()
    print("Character weights:")
    for k, v in wts.items():
        print(f"{v}\t{k}")
    print()
    print("Training recommendations:")
    print(f"{img_min}\timages (min.)")
    print(f"{int(img_min * 0.9)}\titerations (min.)")
    print()
    print("Character counts:")
    print(f"{num_vowel_combos}\tvowels with or without top or bottom diacritics")
    print(f"{num_consonant_combos}\tconsonants with or without top diacritics")
    print(f"{num_numbers}\tnumbers")
    print(f"{num_punctuation_chars}\tpunctuation characters")
    print("-" * 40)
    print(f"{num_chars}\ttotal unique characters")
    print()
    print("FONT LIST:")
    fonts = PROPERTIES.get("fonts")
    fonts.sort()
    print(f"  Fonts: {', '.join(fonts)}")
    print(f"  Styles: {', '.join(PROPERTIES.get('styles'))}")
    print()
    print(f"{num_fonts}\tfonts")
    print(f"{num_styles}\tstyles (not all fonts support all styles)")
    print(f"{num_cases}\tcases (upper/lower)")
    print("-" * 40)
    print(f"{combinations}\t total possible combinations")


def show_installed_fonts(fonts_dict):
    for n, d1 in fonts_dict.items():
        print(f"\n{n}:")
        for s, p in d1.items():
            print(f"  {s}: {p}")


def reset_ground_truth(gt_dir_path):
    """delete all files in the ground-truth folder except .placeholder file, then exit"""
    for c in gt_dir_path.iterdir():
        if c.name == ".placeholder":
            continue
        c.unlink()


def get_random_index(num_opt):
    """return random index from integer range"""
    return random.randrange(num_opt)


def get_weighted_index(weights):
    """return weighted index from list of weights"""
    return random.choices([i for i, w in enumerate(weights)], weights=weights)[0]


def get_binary_choice(prob=0.5):
    # 1 == yes/true; 0 = no/false
    # prob of 1.0 = always yes/true; prob of 0.0 = never yes/true
    # https://stackoverflow.com/a/5887040
    return random.random() < prob


def get_available_fonts():
    # https://stackoverflow.com/a/68810954
    fonts = {}
    # search_paths = [
    #     "/usr/share/fonts",
    #     f"{environ['HOME']}/.local/share/fonts",
    # ]
    fpaths = font_manager.findSystemFonts()
    fpaths.sort()
    for p in fpaths:
        try:
            f = font_manager.get_font(p)
        except RuntimeError:
            continue
        if ONLY_CORE_FONTS and f.family_name not in CORE_FONTS:
            continue
        if not fonts.get(f.family_name):
            fonts[f.family_name] = {}
        if fonts.get(f.family_name).get(f.style_name):
            # Keep 1st version (in $HOME) of font found.
            continue
        fonts[f.family_name][f.style_name] = p
    return fonts


def get_random_char_type(options):
    # If only one option allowed, return it.
    if len(options) == 1:
        char_type = next(iter(options))
    else:
        char_type = None

    if not char_type:
        # Loop through dict of char types and probabilities;
        # select char type if "true" is "rolled" for the given char type.
        # NOTE: This "tries" lowest-probability char type first. Does this lead to
        # over-representation of lower-probability chars?
        highest_prob_item = ()
        for t, p in sorted(options.items(), key=lambda kv: (kv[1], kv[0])):
            if not highest_prob_item or p > highest_prob_item[1]:
                highest_prob_item = (t, p)
            if get_binary_choice(p):
                char_type = t
                break
        if not char_type:  # fall back to option with highest probability.
            char_type = highest_prob_item[0]
    return char_type


def get_next_file_number(gt_dir):
    """return the number after the highest numbered file in gt_dir, or 0

    Only names starting with FILE_NUMBER_DIGITS digits and a hyphen count, so
    older time-based names (e.g. "1791881323.028-...") are ignored.
    """
    if not gt_dir.is_dir():
        return 0
    numbers = [
        int(m.group(1))
        for p in gt_dir.iterdir()
        if (m := FILE_NUMBER_RE.match(p.name))
    ]
    return max(numbers) + 1 if numbers else 0


def set_data_filename(iter_num, fontname, fontstyle):
    """return a unique base name that sorts in the order files were planned

    The zero-padded number makes names unique across worker processes and
    across runs into the same folder (numbering continues from the highest
    existing file; see get_next_file_number).
    """
    number = f"{FIRST_FILE_NUMBER + iter_num:0{FILE_NUMBER_DIGITS}d}"
    return f"{number}-{fontname.replace(' ', '_')}-{fontstyle.replace(' ', '_')}"


def generate_text_line(length=50, method="random-chars"):
    """return a line of given length with a random mixture of valid charachers

    method: random-chars, weighted-chars, pseudo-words
    """
    match method:
        case "random-chars":
            return generate_text_line_random_chars(length)
        case "weighted-chars":
            return generate_text_line_weighted_chars(length)
        case "pseudo-words":
            return generate_text_line_pseudo_words(length)


def generate_text_line_random_chars(length=40):
    """return a line of given length with a random mixture of valid charachers

    choices:
      - lower or upper case
      - consonant or vowel
      - 0 or 1 top diacritic
      - 0 or 1 bottom diacritic
    """
    s = b""
    for i in range(length):
        # Choose between lower or upper case.
        upper = get_binary_choice(0.5)

        # Choose between consonant or vowel.
        c_bases = ["consonants", "vowels"]
        n = get_binary_choice(0.5)
        # print(f"c/v choice: {n}")
        c_base = c_bases[n]

        # Choose character index from base.
        n = get_random_index(len(PROPERTIES.get(c_base)))
        # print(f"{c_base} index: {n}")
        c = PROPERTIES.get(c_base)[n]
        if upper:
            c = c.upper()
        u = c.encode("unicode-escape")
        dt = None
        db = None
        if c_base == "vowels":
            accept_dt = get_binary_choice(0.5)
            n = get_random_index(len(PROPERTIES.get("diacritics").get("top")))
            dt = PROPERTIES.get("diacritics").get("top")[n] if accept_dt == 1 else None
            accept_db = get_binary_choice(0.5)
            n = get_random_index(len(PROPERTIES.get("diacritics").get("bottom")))
            db = PROPERTIES.get("diacritics").get("bottom")[n] if accept_db else None
        if dt:
            u += dt
        if db:
            u += db
        s += u
    return s.decode("unicode-escape")


def generate_text_line_weighted_chars(length=40):
    """return a line (str) of given length with a weighted mixture of valid characters"""

    default_options = {
        "consonants": PROPERTIES.get("weights").get("p_conso"),
        "numbers": PROPERTIES.get("weights").get("p_num"),
        "punctuation": PROPERTIES.get("weights").get("p_punct"),
        "space": PROPERTIES.get("weights").get("p_space"),
        "vowels": PROPERTIES.get("weights").get("p_vowel"),
    }

    text_line = ""
    last_c_type = None
    # last_u = None
    for i in range(length):
        options = default_options.copy()
        # Special treatment for 'space'.
        if i == 0 or i == length - 1 or last_c_type == "space":
            # Shouldn't be a space at beginning or end of string, or after another space.
            options.pop("space")
        # Get base character type.
        c_type = get_random_char_type(options)
        last_c_type = c_type
        c_opts = PROPERTIES.get(c_type)
        c = c_opts[get_random_index(len(c_opts))]

        # Special treatment to improve recognition of some base characters.
        # if (
        #     c_type == "consonants"
        #     and c != "y"
        #     and get_binary_choice(PROPERTIES.get("weights").get("p_y"))
        # ):
        #     c = "y"
        # if c_type == 'vowels':
        #     if c != 'a':
        #         if get_binary_choice(PROPERTIES.get('weights').get('p_a')):
        #             c = 'a'
        #     elif c != 'ə':
        #         if get_binary_choice(PROPERTIES.get('weights').get('p_schwa')):
        #             c = 'ə'

        # Set case.
        c = set_case(c, c_type)

        # Set diacritics.
        c = set_diacritics(c, c_type)
        text_line += c

    return text_line


def get_next_char_type(last_c_type, current_word_length):
    """choose a character type based on the last one; e.g. CVCV"""
    default_c_types = {
        "consonants": PROPERTIES.get("weights").get("p_conso"),
        "numbers": PROPERTIES.get("weights").get("p_num"),
        "punctuation": PROPERTIES.get("weights").get("p_punct"),
        "vowels": PROPERTIES.get("weights").get("p_vowel"),
    }

    match last_c_type:
        case None:
            options = default_c_types
        case "consonants":
            if current_word_length > 1:
                options = {k: default_c_types.get(k) for k in ("punctuation", "vowels")}
            else:
                options = {k: default_c_types.get(k) for k in ("vowels",)}
        case "numbers":
            options = {k: default_c_types.get(k) for k in ("numbers", "punctuation")}
        case "punctuation":
            if current_word_length > 1:
                return  # don't continue word after punctuation
            else:
                options = default_c_types
        case "vowels":
            options = {k: default_c_types.get(k) for k in ("consonants", "punctuation")}
        case _:
            raise ValueError(f"{last_c_type=}")

    return get_random_char_type(options)


def get_character(char_type):
    """select random character of given 'char_type', but adjust for given weights"""
    char_weights = {
        # FIXME: This should be moved to `config.toml`.
        # NOTE: Unlisted characters' weights default to 1.0.
        "consonants": {
            "ɓ": 0.16,
            "ɗ": 0.15,
            "ŋ": 0.15,
            "ẅ": 0.15,
            "ꞌ": 0.05,
            "ʼ": 0.05,
        },
        "vowels": {
            "ɛ": 0.11,
            "æ": 0.06,
            "ɑ": 0.02,
            "ə": 0.10,
            "ɨ": 0.10,
            "ɔ": 0.11,
            "ø": 0.08,
            "œ": 0.06,
            "ʉ": 0.08,
        },
    }
    char_opts = PROPERTIES.get(char_type)
    # One weight per entry in char_opts (default 1.0). Weights for characters
    # not in config.toml are ignored; adding them as extra entries made the
    # weight list longer than char_opts, which caused an IndexError whenever
    # one of those extra entries was picked.
    adjusted = char_weights.get(char_type, {})
    weights = [adjusted.get(c, 1) for c in char_opts]
    return random.choices(char_opts, weights=weights)[0]


def set_case(char, char_type):
    if char_type in ["consonants", "vowels"] and get_binary_choice(
        PROPERTIES.get("weights").get("p_upper")
    ):
        char = char.upper()
    return char


def set_diacritics(char, char_type):
    # TODO: Allow for relative weighting of diacritics.
    use_bot_diac = False
    use_top_diac = False
    if char_type == "consonants":
        use_top_diac = get_binary_choice(PROPERTIES.get("weights").get("p_ctpdi"))
    elif char_type == "vowels":
        use_top_diac = get_binary_choice(PROPERTIES.get("weights").get("p_vtpdi"))
        use_bot_diac = get_binary_choice(PROPERTIES.get("weights").get("p_vbtdi"))
    # Add lower diacritics first: https://www.unicode.org/reports/tr15/#Examples
    if use_bot_diac:
        diac_bot_list = PROPERTIES.get("diacritics").get("bottom")
        char += diac_bot_list[get_random_index(len(diac_bot_list))]
    if use_top_diac:
        diac_top_list = PROPERTIES.get("diacritics").get("top")
        td = diac_top_list[get_random_index(len(diac_top_list))]
        # Special treatment to improve recognition of some base top diacritics.
        # if td != b'\\u0303' and get_binary_choice(PROPERTIES.get('weights').get('p_tilda')): doesn't help
        #     td = b'\\u0303'
        char += td
    return char


def generate_pseudo_word():
    max_length = 9

    last_c_type = None
    min_length = 2
    length = max(min_length, get_random_index(max_length))
    word = ""
    while len(word) < length:
        c_type = get_next_char_type(last_c_type, len(word))
        last_c_type = c_type
        if c_type is None:  # last char is word-ending (punct)
            break

        # Get [weighted] character of given type.
        c = get_character(c_type)

        # Set character case for first letter.
        if len(word) == 0:
            c = set_case(c, c_type)

        # Set diacritics.
        c = set_diacritics(c, c_type)
        if len(c) > 1:
            # Account for added diacritics.
            length += len(c) - 1

        word += c

    return word


def generate_text_line_pseudo_words(length=50):
    """return text of given length that resembles legitimate words"""
    text_line = ""
    while len(text_line) < length:
        word = generate_pseudo_word()
        text_line += f"{word} "
    return text_line.rstrip()


@cache
def font_codepoints(fontfile):
    """return the set of Unicode code points the font file maps to glyphs

    Combines all Unicode cmap subtables. The result is cached, so each font
    file is read once per process; workers forked after a lookup in the main
    process inherit its cache. A font that can't be read gives an empty set,
    so it covers no text instead of appearing to cover everything.
    """
    try:
        font = TTFont(fontfile, fontNumber=0, lazy=True)
        codepoints = set()
        for cmap in font["cmap"].tables:
            if cmap.isUnicode():
                codepoints.update(cmap.cmap)
        font.close()
    except Exception as e:  # noqa
        print(f"ERROR: file: {fontfile}; {e}")
        return frozenset()
    return frozenset(codepoints)


def generate_text_line_png(chars, fontfile):
    image_blend_alpha = 0.4

    def add_fade(image):
        """set pixel color to white for certain random pixels"""
        fade_ratio = 0.15

        # Create list of pixel indexes to change to white.
        px_ct = image.size[0] * image.size[1]
        fade_idxs = list(
            set(random.randrange(px_ct) for _ in range(int(fade_ratio * px_ct)))  # noqa
        )
        fade_idxs.sort()  # re-sort

        # Loop through all pixels, changing specified pixels.
        faded_image = Image.new(image.mode, image.size)
        faded_img_data = list(image.get_flattened_data())
        for i in fade_idxs:
            faded_img_data[i] = (255, 255, 255)

        faded_image.putdata(faded_img_data)
        return faded_image

    def add_noise(image):
        noise_sigma = 25
        noise = Image.effect_noise(size=image.size, sigma=noise_sigma)
        image = Image.blend(image, noise.convert(image.mode), image_blend_alpha)
        return image

    def add_blur(image):
        px_radius = 1
        image = image.filter(ImageFilter.GaussianBlur(px_radius))
        return image

    # Characters are drawn exactly as given, so the image always matches the
    # ground truth; run_iteration only passes fonts that cover every character
    # (see choose_covering_font).
    # Create image using pillow.
    font = ImageFont.truetype(fontfile, size=CHARACTER_HEIGHT)
    # Define enough padding to avoid character overruns.
    pad = int(CHARACTER_HEIGHT * 0.5)  # px
    # Get size of generated text chars.
    (text_w, text_h) = font.getmask(chars).size
    # Add padding; create blank image.
    size = (text_w + 2 * pad, text_h + 2 * pad)
    img = Image.new("RGB", size, "white")
    # Add text chars to image.
    draw = ImageDraw.Draw(img)
    draw.text((pad, pad + text_h), chars, anchor="ld", font=font, fill="black")

    # Apply indicated degradations.
    if get_binary_choice(DEGRADED_IMAGE_PROBABILITY * 2):
        # Ensure at least one degradation is applied, with equal probability
        # for all possibilities.
        if get_binary_choice():  # could be introduced during printing
            img = add_fade(img)
        if get_binary_choice():  # could be introduced during printing or scanning
            img = add_blur(img)
        if get_binary_choice():  # could be introduced during scanning
            img = add_noise(img)

    # img.show()  # for debugging
    return img


def generate_training_data_pair(chars, fontfile):
    pngdata = generate_text_line_png(chars, fontfile)
    return chars, pngdata


def generate_text2image_data_pair(basedir, filename, chars, fontname, fontstyle):
    if fontstyle == "Regular":
        font = fontname
    else:
        font = f"{fontname} {fontstyle}"

    # Create tempfile for chars & use it to create TIFF image with text2image.
    # Ref: https://stackoverflow.com/a/15235559
    with tempfile.NamedTemporaryFile(mode="w+") as f:
        f.write(chars)
        f.flush()
        cmd = [
            "text2image",
            f"--text={f.name}",
            f"--outputbase={basedir}/{filename}",
            "--fonts_dir=/usr/share/fonts",
            f"--font={font}",
        ]
        subprocess.run(cmd, check=False)


def weighted_order(items, weights):
    """return items in a random order, drawing without replacement by weight"""
    items, weights = list(items), list(weights)
    order = []
    while items:
        i = get_weighted_index(weights)
        order.append(items.pop(i))
        weights.pop(i)
    return order


def choose_covering_font(text):
    """choose a font family and style that can draw every character of text

    Returns (family, style, fontfile, missing). The first family and style
    are drawn exactly as before: a uniformly random installed family (or the
    one given with --font), then a style by weight. Only if that font file
    lacks a character in text are the family's other styles tried, then the
    other families. If nothing fits, fontfile is None and missing is the set
    of characters that none of the tried fonts has (empty if each character
    is in some font but no single font has them all), or None if there were
    no installed fonts to try.
    """
    style_weights = {
        "Bold": 0.2,
        "Italic": 0.2,
        "Bold Italic": 0.1,
    }
    if FORCED_FONT:
        families = [FORCED_FONT] if FORCED_FONT in SYSTEM_FONTS else []
    else:
        families = [f for f in PROPERTIES.get("fonts") if f in SYSTEM_FONTS]
        random.shuffle(families)

    needed = {ord(c) for c in text}
    covered = set()
    tried_any = False
    for family in families:
        # Only styles that are both wanted and installed for this family.
        styles = [s for s in PROPERTIES.get("styles") if s in SYSTEM_FONTS[family]]
        # One weight per style (default 1.0); weights for styles not in
        # config.toml are ignored (same IndexError risk as in get_character).
        weights = [style_weights.get(s, 1) for s in styles]
        for style in weighted_order(styles, weights):
            fontfile = SYSTEM_FONTS[family][style]
            codepoints = font_codepoints(fontfile)
            tried_any = True
            if needed <= codepoints:
                return family, style, fontfile, set()
            if VERBOSE:
                print(f"INFO: {family} {style} lacks some characters; trying another")
            covered |= codepoints
    if not tried_any:
        return None, None, None, None
    return None, None, None, {chr(cp) for cp in needed - covered}


def verify_fonts(needed_fonts, installed_fonts):
    missing_fonts = []
    for f in needed_fonts:
        if f not in installed_fonts:
            missing_fonts.append(f)
    if len(missing_fonts) > 0:
        print("ERROR: Not all required fonts are installed:")
        for m in missing_fonts:
            print(f"  - {m}")
        sys.exit(1)


def save_training_data_pair(gt_dir, name, txtdata, pngdata):
    txtfile = gt_dir / f"{name}.gt.txt"
    pngfile = gt_dir / f"{name}.png"

    # Write out file contents.
    txtfile.write_text(txtdata)
    pngdata.save(pngfile)


def load_text_lines(paths):
    """return NFC-normalized, non-blank lines from the given text files

    Expects one text line per file line, e.g. the "<lang>.txt" or "all.txt"
    files written by extract-text-lines.py. Lines are kept in file order and
    are not de-duplicated, so giving a file twice doubles its weight.
    """
    lines = []
    for p in paths:
        if not p.is_file():
            print(f"ERROR: Lines file not found: {p}")
            sys.exit(1)
        n_before = len(lines)
        for line in p.read_text(encoding="utf-8-sig").splitlines():
            line = normalize("NFC", line.strip())
            if line:
                lines.append(line)
        if VERBOSE:
            print(f"INFO: {len(lines) - n_before} lines loaded from {p}")
    if not lines:
        print("ERROR: No text lines found in the given lines file(s).")
        sys.exit(1)
    return lines


def plan_real_lines(iterations, num_lines, ratio):
    """return a list giving, for each iteration, a real line index or None

    Exactly round(iterations * ratio) iterations get a real line; which
    iterations those are is random, so real and pseudo-word lines are mixed
    throughout the run. Real lines are handed out in file order, cycling
    back to the start only after every line has been used once, so the
    coverage balance from extract-text-lines.py is kept. Each repeat of a
    line gets its own randomly chosen font, style and degradations.
    """
    plan = [None] * iterations
    if not num_lines or ratio <= 0:
        return plan
    num_real = round(iterations * ratio)
    for k, i in enumerate(sorted(random.sample(range(iterations), num_real))):
        plan[i] = k % num_lines

    passes = num_real / num_lines
    print(
        f"INFO: {num_real} of {iterations} images will use real lines "
        f"({passes:.2f} passes through {num_lines} lines)."
    )
    if num_real < num_lines:
        print(
            f"WARNING: only {num_real} of {num_lines} real lines will be used; "
            "raise -i or --real-ratio to use them all."
        )
    return plan


def get_parsed_args():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-c",
        "--combinations",
        action="store_true",
        help="output character list and counts, then exit",
    )
    parser.add_argument(
        "-f",
        "--installed-fonts",
        action="store_true",
        help="list installed fonts, then exit",
    )
    parser.add_argument(
        "-r",
        "--reset",
        action="store_true",
        help=reset_ground_truth.__doc__,
    )
    parser.add_argument(
        "-w",
        "--weights",
        action="store_true",
        help="show weights used for each type of character",
    )
    parser.add_argument(
        "-C",
        "--only-core-fonts",
        action="store_true",
        help="only use core SIL and open fonts",
    )
    parser.add_argument(
        "-D",
        "--degraded-image-probability",
        type=float,
        default=DEFAULT_DEGRADED_IMAGE_PROBABILITY,
        help=f"probability of degradations getting applied to generated images [{DEFAULT_DEGRADED_IMAGE_PROBABILITY}]",
    )
    parser.add_argument(
        "-F",
        "--font",
        type=str,
        default="",
        help="generate images using only the given font family",
    )
    parser.add_argument(
        "-H",
        "--character-height",
        type=int,
        default=DEFAULT_CHARACTER_HEIGHT,
        help=f"set max height (px) of generated characters [{DEFAULT_CHARACTER_HEIGHT}]",
    )
    parser.add_argument(
        "-i",
        "--iterations",
        type=int,
        default=DEFAULT_ITERATIONS,
        help=f'create "i" iterations of ground truth data [{DEFAULT_ITERATIONS}]',
    )
    parser.add_argument(
        "-L",
        "--line-length",
        type=int,
        default=DEFAULT_LINE_LENGTH,
        help=f"number of characters per generated pseudo-word line; real lines from --lines-file keep their own length [{DEFAULT_LINE_LENGTH}]",
    )
    parser.add_argument(
        "-l",
        "--lines-file",
        type=Path,
        action="append",
        metavar="FILE",
        help="text file with one line of real text per line, e.g. from extract-text-lines.py; can be given more than once",
    )
    parser.add_argument(
        "-R",
        "--real-ratio",
        type=float,
        default=DEFAULT_REAL_RATIO,
        help=f"share of lines taken from --lines-file instead of generated as pseudo-words; ignored without --lines-file [{DEFAULT_REAL_RATIO}]",
    )
    parser.add_argument(
        "-n",
        "--simulate",
        action="store_true",
        help="generate training data without saving it to disk",
    )
    parser.add_argument(
        "-t",
        "--use-text2image",
        action="store_true",
        help="use text2image script to generate training data instead of built-in function",
    )
    parser.add_argument(
        "-T",
        "--text",
        type=str,
        help="generate training data with given line of text",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="show verbose output"
    )
    return parser.parse_args()


def run_iteration(iter_num):
    if VERBOSE:
        print(f"INFO: Iteration: {iter_num}")

    # Choose the text first, so that the font can be chosen to cover it.
    # Remove any 'bad_chars' items from 'dirty_char_str' to create clean 'char_line'.
    if FORCED_TEXT:
        text_line = FORCED_TEXT
    elif REAL_LINE_PLAN[iter_num] is not None:
        line_idx = REAL_LINE_PLAN[iter_num]
        text_line = REAL_LINES[line_idx]
        if VERBOSE:
            print(f"INFO: source: real line {line_idx}")
    else:
        if VERBOSE and REAL_LINES:
            print("INFO: source: pseudo-words")
        text_line = generate_text_line(
            length=LINE_LENGTH,
            # method="random-chars",
            # method="weighted-chars",
            method="pseudo-words",
        )

    # clean_unicode_chars = [c for c in dirty_char_str if c not in bad_chars]
    text_line = normalize("NFC", text_line)
    if VERBOSE:
        # print(f"INFO: start ({len(dirty_char_str)}): {dirty_char_str}")
        # print(f"INFO: bad:   {bad_chars}")
        print(f"INFO: text: ({len(text_line)}): {text_line}")
        print(f"INFO: {b''.join([c.encode('unicode-escape') for c in text_line])}")

    # Choose a font family and style whose font file covers every character.
    if FORCED_FONT and FORCED_FONT not in PROPERTIES.get("fonts"):
        print(
            f"ERROR: Font not installed: {FORCED_FONT}; skipping iteration: {iter_num}"
        )
        return
    font_fam, font_sty, fontfile, missing = choose_covering_font(text_line)
    if not fontfile:
        if missing is None:
            print(f"ERROR: No valid font found; skipping iteration: {iter_num}")
        elif missing:
            chars = " ".join(f"{c} (U+{ord(c):04X})" for c in sorted(missing))
            print(
                f"WARNING: no allowed font has {chars}; skipping iteration: {iter_num}"
            )
        else:
            print(
                "WARNING: no single allowed font covers all characters of the "
                f"line; skipping iteration: {iter_num}"
            )
        return
    if VERBOSE:
        print(f"INFO: {font_fam=}")
        print(f"INFO: {font_sty}")

    # Generate files.
    filename = set_data_filename(iter_num, font_fam, font_sty)
    if VERBOSE:
        print(f"INFO: base name: {filename}")
    if USE_TEXT2IMAGE:
        generate_text2image_data_pair(
            GROUND_TRUTH_DIR, filename, text_line, font_fam, font_sty
        )
    else:
        pngdata = generate_text_line_png(text_line, fontfile)
        if not SIMULATE:
            save_training_data_pair(GROUND_TRUTH_DIR, filename, text_line, pngdata)


def main():
    # Handle command args.
    args = get_parsed_args()

    # FIXME: Using globals is not ideal, but it makes setting up muliprocessing
    # a lot easier.
    global PROPERTIES
    with (get_model_dir(WRITING_SYSTEM_NAME) / "config.toml").open('rb') as f:
        PROPERTIES = tomllib.load(f).get("properties")

    global CHARACTER_HEIGHT
    CHARACTER_HEIGHT = args.character_height

    global LINE_LENGTH
    LINE_LENGTH = args.line_length

    global VERBOSE
    VERBOSE = args.verbose

    global SIMULATE
    SIMULATE = args.simulate

    global ONLY_CORE_FONTS
    ONLY_CORE_FONTS = args.only_core_fonts

    global USE_TEXT2IMAGE
    USE_TEXT2IMAGE = args.use_text2image

    global GROUND_TRUTH_DIR
    GROUND_TRUTH_DIR = (
        get_git_root(__file__)
        / "data"
        / "training"
        / f"{WRITING_SYSTEM_NAME}-ground-truth"
    )

    global SYSTEM_FONTS
    SYSTEM_FONTS = get_available_fonts()

    global FORCED_FONT
    FORCED_FONT = args.font

    global FORCED_TEXT
    FORCED_TEXT = args.text

    global DEGRADED_IMAGE_PROBABILITY
    DEGRADED_IMAGE_PROBABILITY = args.degraded_image_probability

    global REAL_RATIO
    REAL_RATIO = args.real_ratio
    if not 0.0 <= REAL_RATIO <= 1.0:
        print(f"ERROR: --real-ratio must be between 0 and 1; got {REAL_RATIO}")
        sys.exit(1)

    if args.combinations:
        show_character_combinations()
        sys.exit()

    if args.installed_fonts:
        show_installed_fonts(SYSTEM_FONTS)
        sys.exit()

    if args.weights:
        show_character_weights()
        sys.exit()

    if args.reset:
        reset_ground_truth(GROUND_TRUTH_DIR)
        sys.exit()

    # Ensure training fonts are installed.
    # verify_fonts(CHAR_VARS.get("fonts"), SYSTEM_FONTS)

    # Continue file numbering after any files already in the folder, so a
    # second run into the same folder doesn't overwrite the first.
    global FIRST_FILE_NUMBER
    FIRST_FILE_NUMBER = get_next_file_number(GROUND_TRUTH_DIR)
    if FIRST_FILE_NUMBER and not SIMULATE:
        print(f"INFO: Numbering new files from {FIRST_FILE_NUMBER:0{FILE_NUMBER_DIGITS}d}.")

    # Load real text lines once, before the worker pool starts, so that
    # forked workers inherit them instead of re-reading the files.
    global REAL_LINES
    REAL_LINES = load_text_lines(args.lines_file) if args.lines_file else []
    if REAL_LINES:
        print(f"INFO: {len(REAL_LINES)} real text lines loaded.")

    # Decide up front which iterations get which real line. Workers can't
    # share a counter, so the plan is built here and inherited by them.
    global REAL_LINE_PLAN
    REAL_LINE_PLAN = plan_real_lines(
        args.iterations, len(REAL_LINES) if not FORCED_TEXT else 0, REAL_RATIO
    )

    procs = multiprocessing.cpu_count()
    with multiprocessing.Pool(processes=procs) as pool:
        pool.map(run_iteration, range(args.iterations))

    if SIMULATE:
        # TODO: Is there some way to verify TXT and PNG file contents without saving them to disk?
        print("INFO: Simulation; no files generated.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
