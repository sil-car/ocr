#!/usr/bin/env python3

# List in unicode order all the unique characters in the given text files.
# TODO: Modifications for Paratext project files.
#   - Create special Paratext option.
#   - Output language name + 3-letter abbrev.
#   - For each language show all non-ASCII chars (all > \u0127)

import argparse
import sys

from pathlib import Path


def get_chars_from_file(file_pathobj):
    chars = set()
    # with file_pathobj.open() as f:
    #     chars.update(c for c in f.read_text())
    try:
        chars.update(c for c in file_pathobj.read_text())
    except UnicodeDecodeError as e:
        # print(f"Warning: Skipping file \"{file_pathobj.name}\"; {e}")
        print(f"Warning: Skipping file \"{file_pathobj.name}\"")
        # print(e)
    return chars

def get_parsed_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
    '-l', '--list',
    action='store_true',
    help="list files that character list was built from"
    )
    parser.add_argument(
        '-p', '--paratext',
        action='store_true',
        help="pass source as a Paratext project name or folder"
    )
    parser.add_argument(
        '-u', '--unicode',
        action='store_true',
        help="show unicode value of output characters"
    )
    # parser.add_argument(
    #     '-k', '--trim',
    #     nargs=2,
    #     type=str,
    #     help="Trim the file to keep content between given timestamps (HH:MM:SS)."
    # )
    # parser.add_argument(
    #     '-s', '--speed',
    #     type=float,
    #     help="Change the playback speed of the video using the given factor (0.5 to 100).",
    # )
    # parser.add_argument(
    #     '-t', '--tutorial',
    #     dest='rates',
    #     action='store_const',
    #     const=(128000, 500000, 10),
    #     default=(128000, 2000000, 25),
    #     help="Use lower bitrate and fewer fps for short tutorial videos."
    # )
    parser.add_argument(
        "file",
        nargs='*',
        help="space-separated list of source files or folders"
    )

    return parser.parse_args()

def set_search_paths(script_args):
    search_paths = []
    for f in script_args.file:
        p = Path(f).resolve()
        if p.is_dir():
            search_paths.append(p)
        elif args.paratext:
            # Assume Paratext project name given.
            project_found = False
            for d in paratext_project_dirs:
                test_path = d / f
                if test_path.is_dir():
                    search_paths.append(test_path)
                    project_found = True
            if not project_found:
                print(f"Warning: \"{f}\" was not found in Paratext project folders and will be ignored.")
        else:
            # Not a valid folder.
            print(f"Warning: \"{f}\" is not a valid folder and will be ignored.")
    return search_paths

def remove_ascii_from_string(given_string):
    return ''.join([c for c in given_string if ord(c) >= 128])

def get_unicode_values_from_string(given_string):
    return [c.encode('unicode-escape') for c in given_string]


user_home = Path.home()
args = get_parsed_args()

file_types = [
    '.sfm',
    '.txt',
]
if args.paratext:
    # Only search SFM files.
    file_types = [
        '.sfm',
        ]

paratext_project_dirs = [
    # Linux
    user_home / "Paratext8Projects",
    user_home / "Paratext9Projects",
    user_home / "snap" / "paratextlite" / "current" / "Paratext8Projects",
    user_home / "snap" / "paratextlite" / "current" / "Paratext8Projects.bak",
    # Windows
    user_home / "My Paratext 8 Projects",
    user_home / "My Paratext 9 Projects",
]

car_paratext_projects = [
    'Ban',
    'BGT',
    'GBP',
    'GTSag',
    'Kab',
    'Mpyemo',
    'Mza',
    'NDY',
    'NGB',
    'Nzk',
    'SAB',
    'Tali',
]

search_paths = set_search_paths(args)

scraped_files = []
all_chars = set()
paratext_results = {}
for fpath in search_paths:
    if fpath.is_dir():
        if args.paratext:
            # Populate paratext_results.
            proj_name = fpath.name
            if not paratext_results.get(proj_name):
                paratext_results[proj_name] = {
                    'characters': set(),
                    'files': [fpath.as_uri()],
                }
            else:
                paratext_results[proj_name]['files'].append(fpath.as_uri())
        # Use globbing to find all file_types recursively within given directory.
        valid_files = []
        for t in file_types:
            valid_files.extend(fpath.glob(f'**/*{t}'))
            valid_files.extend(fpath.glob(f'**/*{t.upper()}'))
        scraped_files.extend(f.as_uri() for f in valid_files)
        for fp in valid_files:
            # Get characters from file.
            chars = get_chars_from_file(fp)
            if args.paratext:
                if not paratext_results.get(proj_name).get('characters'):
                    paratext_results[proj_name]['characters'] = set(chars)
                else:
                    paratext_results[proj_name]['characters'].update(chars)
            all_chars.update(chars)
    elif fpath.is_file():
        # Get characters from file.
        file_type = fpath.suffix.lower()
        if file_type in file_types:
            scraped_files.append(fpath.as_uri())
            chars = get_chars_from_file(fpath.as_uri())
            all_chars.update(chars)

all_chars_list = list(all_chars)
all_chars_list.sort()
scraped_files.sort()

c_ct = len(all_chars_list)
f_ct = len(scraped_files)
if args.list:
    print(f"Found {c_ct} characters in the following {f_ct} files:")
    for f in scraped_files:
        print(f)
    print()
else:
    print(f"Found {c_ct} characters in {f_ct} files. Use \"-l\" option to see file list.")

all_chars_str = ''.join(all_chars_list)
print("Characters:")
print(all_chars_str)
if args.unicode:
    print("\nUnicode values:")
    all_chars_u = get_unicode_values_from_string(all_chars_str)
    for i, c in enumerate(all_chars_u):
        if i % 4 == 3:
            print(f"{c} ")
        else:
            print(f"{c} ", end='')
print()

if args.paratext:
    print(f"Non-ASCII characters by Paratext project:")
    for p, v in paratext_results.items():
        p_chars = list(v.get('characters'))
        p_chars.sort()
        p_chars_str = ''.join(p_chars)
        x_chars_str = remove_ascii_from_string(p_chars_str)
        print(f"{p}\t{x_chars_str}")

        x_chars_o = [ord(c) for c in x_chars_str]
        if args.unicode:
            # x_chars_u = [c.encode('unicode-escape') for c in x_chars_str]
            x_chars_u = get_unicode_values_from_string(x_chars_str)
            for i, c in enumerate(x_chars_u):
                if i % 4 == 3:
                    print(f"{c} ")
                else:
                    print(f"{c} ", end='')
            print()
