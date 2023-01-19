#!/bin/bash

# Scan data/evaluation folder and ensure that OCR evalulation data is added to data.csv.

list_png_files() {
    # NOTE: Filenames must not have spaces for this work.
    base_dir="$(readlink -f "$1")"
    if [[ -n "$base_dir" ]]; then
        find "$base_dir" -iname '*.png'
    fi
}

script="$(readlink -f "$0")"
scripts_dir="$(dirname "$script")"
eval_dir="$(dirname "$scripts_dir")/data/evaluation"

models=$(cat "${eval_dir}/models.txt")
iso_langs=$(find "${eval_dir}" -type d | sed -r 's|.*/([a-z]{3}_[a-z]+)|\1|')

# Loop through language folders.
for l in $(echo $iso_langs); do
    # Find all PNG files in each language folder.
    png_files=$(list_png_files "${eval_dir}/$l")
    # Loop through PNG files.
    for p in $(echo $png_files); do
        # Loop through language models.
        for m in $(echo $models); do
            # Ensure that model evaluation is added to data.csv.
            "${scripts_dir}"/evaluate-ocr.py -l "$m" "$p"
        done
    done
done
