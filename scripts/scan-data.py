#!/usr/bin/env python3

# Scan data/evaluation folder and ensure that OCR evalulation data is added to data.csv.

import subprocess

from pathlib import Path


def list_png_files(base_dir):
    files = []
    if base_dir.is_dir():
        files = list(base_dir.glob('**/*.png'))
    return files

def find_files_by_ext(ext, base_dir):
    ext = ensure_ext_dot(ext)
    return list(base_dir.glob(f"**/*{ext.lower()}"))

def ensure_ext_dot(ext):
    return f".{ext}" if ext[0] != '.' else ext

def get_ocr_ready_files(base_dir):
    files = []
    gt_files_all = find_files_by_ext('.gt.txt', base_dir)
    for f in gt_files_all:
        name_p = str(f).replace('.gt.txt', '')
        f_png = Path(f"{name_p}.png")
        if f_png.is_file():
            files.append(f)
    return files

def get_ocr_files_by_ext(ext, base_dir):
    ext = ensure_ext_dot(ext)
    files = []
    gt_files_all = find_files_by_ext('.gt.txt', base_dir)
    for f in gt_files_all:
        name_p = str(f).replace('.gt.txt', '')
        f_ext = Path(f"{name_p}{ext}")
        if f_ext.is_file():
            files.append(f)
    return files

def get_ocr_recognized_files_by_model(base_dir, model):
    files = []
    gt_files_all = find_files_by_ext('.gt.txt', base_dir)
    for f in gt_files_all:
        name_p = str(f).replace('.gt.txt', '')
        f_rec = Path(f"{name_p}.{model}.txt")
        if f_rec.is_file():
            files.append(f)
    return files

def main():

    script = Path(__file__).expanduser().resolve()
    scripts_dir = script.parent
    root_dir = scripts_dir.parent
    models_dir = root_dir / 'tessdata'
    eval_dir = root_dir / 'data' / 'evaluation'
    for d in [root_dir, models_dir, scripts_dir, eval_dir]:
        if not d.is_dir():
            print(f"Error: Folder does not exist: {d}")
            exit(1)

    # ocr_ready_files = get_ocr_files_by_ext('.png', eval_dir)
    ocr_gt_files = find_files_by_ext('.gt.txt', eval_dir)
    ocr_gt_files.sort()
    models = [f.stem for f in models_dir.iterdir() if not f.is_dir() and f.stem != 'Latin_afr']
    models.sort()

    print(f"Base dir: {eval_dir}")
    for m in models:
        # # Verify that model has been used to create OCR output.
        # ocr_recognized_files = get_ocr_files_by_ext(f".{m}.txt", eval_dir)
        # # Verify that a corresponding gt file exists.
        print(f"  Running OCR evaluations for {m}...")
        # for f in ocr_recognized_files:
        #     gt_file = Path(str(f).replace(f".{m}.", '.gt.'))
        #     if gt_file.is_file():
        #         # Ensure that model evaluation is added to data.csv.
        #         cmd = [scripts_dir / 'evaluate-ocr.py', '-l', m, gt_file]
        #         proc = subprocess.run(cmd, capture_output=True)
        #         print(proc.stdout.decode(), end='')
        ## Idea 2
        for gt_file in ocr_gt_files:
            # Ensure that model evaluation is added to data.csv.
            cmd = [scripts_dir / 'evaluate-ocr.py', '-l', m, gt_file]
            proc = subprocess.run(cmd, capture_output=True)
            print(proc.stdout.decode(), end='')

if __name__ == '__main__':
    main()
