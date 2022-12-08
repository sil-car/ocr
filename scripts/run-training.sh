#!/bin/bash

### Start tesseract training on cloud server with relevant options.

# Set initial variables.
debug=
model_name="Latin_afr"
tess_tr_dir="${HOME}/tesstrain"
data_dir="${tess_tr_dir}/data"
tess_data="/usr/local/share/tessdata"
max_iter=100000
debug_interval=0
t2i=

help_text="usage: $0 [-dtv] [-i NUM]"
while getopts ":dhi:tv" opt; do
    case $opt in
        d) # debug
            debug=YES
            ;;
        h) # help text
            echo "$help_text"
            exit 0
            ;;
        i) # max. iterations
            max_iter="$OPTARG"
            ;;
        t) # train based on text2image
            t2i=YES
            ;;
        v) # verbose output
            debug_interval=-1
            ;;
        *) # invalid option
            echo "$help_text"
            exit 1
            ;;
    esac
done
shift $(($OPTIND - 1))

# Ensure no other virtual environment is active.
if which deactivate >/dev/null 2>&1; then
    deactivate
fi

# Enter tesstrain folder.
cd "$tess_tr_dir"
if [[ $? -ne 0 ]]; then
    echo "Error: Failed to enter \"$tess_tr_dir\"."
    exit 1
fi

# Activate virtual environment.
source ./env/bin/activate
if [[ $? -ne 0 ]]; then
    echo "Error: Failed to activate virtual environment."
    exit 1
fi

# Start training.
time_start=$(date +%s)

# Handle debug option.
if [[ -n "$debug" ]]; then
    set -x
fi

# If using text2image use explicit training steps.
if [[ -n "$t2i" ]]; then
    # Explicit training with BOX files.
    out_dir="${data_dir}/${model_name}"
    # Use "manual" training steps.
    # Ref: https://groups.google.com/g/tesseract-ocr/c/7q5pmgJDu_o/m/q9Pb7UMoAgAJ

    # Create unicharset from training_text.
    # unicharset_extractor \
    #     --norm_mode 1 \
    #     --output_unicharset "${out_dir}/${model_name}.unicharset" \
    #     "../langdata/${model_name}/${model_name}.training_text"
    # Copy prepared unicharset & other files.
    langdata_dir="${data_dir}/langdata/${model_name}"
    mkdir -p "$langdata_dir"
    cp "$HOME/ocr/data/${model_name}/${model_name}."* "${langdata_dir}/"

    # Create starter traineddatda (aka recoder).
    combine_lang_model \
        --input_unicharset "${out_dir}/${model_name}.unicharset" \
        --script_dir "${data_dir}/langdata" \
        --output_dir "$out_dir" \
        --lang "$model_name"

    # Create training files (for each image).
    lstmf_dir="${out_dir}/${model_name}"
    # tiff_files=$(find "${data_dir}/${model_name}-ground-truth" -name '*.tif')
    # for tif in $tiff_files; do
    #     name="$(basename "$tif")"
    #     base="${name%.*}"
    #     tesseract "$tif" "${lstmf_dir}/${base}" --psm 6 lstm.train
    # done
    # Ref: https://stackoverflow.com/a/9612232
    find "${data_dir}/${model_name}-ground-truth" -name '*.tif' -print0 |\
        while IFS= read -r -d '' tif; do
            name="$(basename "$tif")"
            base="${name%.*}"
            tesseract "$tif" "${lstmf_dir}/${base}" --psm 6 lstm.train
        done
    # Create list of lstmf files
    ls -1 "${lstmf_dir}/"*.lstmf > "${out_dir}/${model_name}.training_files.txt"

    # Train.
    lstmtraining \
        --traineddata "${out_dir}/${model_name}.traineddata" \
        --model_output "${out_dir}/${model_name}"  \
        --train_listfile  "${out_dir}/${model_name}/${model_name}.training_files.txt" \
        --max_iterations "$max_iter"

    # Create Final traineddata.
    lstmtraining \
        --stop_training \
        --continue_from "${out_dir}/${model_name}_checkpoint" \
        --traineddata "${out_dir}/${model_name}.traineddata" \
        --model_output "${tess_tr_dir}/${model_name}.traineddata"
else
    # Standard training with GT.TXT files.
    make training \
        MODEL_NAME="$model_name" \
        CORES=2 \
        START_MODEL=Latin \
        TESSDATA="$tess_data" \
        MAX_ITERATIONS="$max_iter" \
        DEBUG_INTERVAL="$debug_interval"
fi
time_end=$(date +%s)
duration=$(($time_end - $time_start))

echo "Training lasted ${duration}s."
# per_iter=$(($max_iter / $duration))
