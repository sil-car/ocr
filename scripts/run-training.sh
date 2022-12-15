#!/bin/bash

### Start tesseract training on cloud server with relevant options.

# Set initial variables.
reset=
debug=
replace_layer=
start_model="Latin"
model_name="Latin_afr"
tess_tr_dir="${HOME}/tesstrain"
data_dir="${tess_tr_dir}/data"
tessdata="/usr/local/share/tessdata"
max_iter=100000
debug_interval=0
t2i=
submodel=$(date +%Y%m%d%H)
log="${data_dir}/${model_name}_${submodel}.log"
ocr_script_dir="$(readlink -f "$(dirname "$0")")"

help_text="usage: $0 [-dhrtv] [-i NUM]"
while getopts ":dhi:rtv" opt; do
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
        l) # replace layer
            replace_layer=YES
            ;;
        r) # reset
            reset=YES
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

# Handle debug option.
if [[ -n "$debug" ]]; then
    set -x
fi

# Handle reset option.
if [[ -n "$reset" ]]; then
    # Clean/reset generated files & exit (for now).
    echo "Resetting generated files (not GT data). No other option will be handled."
    make clean "MODEL_NAME=${model_name}"
    rm -v "${tess_tr_dir}/data/"*.traineddata
    cp -rv "$HOME/ocr/data/${model_name}" "${tess_tr_dir}/data/"
    exit 0
fi

# Start training.
time_start=$(date +%s)

# If using text2image use explicit training steps.
if [[ -n "$t2i" ]]; then
    # Explicit training with BOX files.
    output_dir="${data_dir}/${model_name}"
    ground_truth_dir="${output_dir}-ground-truth"
    # Use "manual" training steps.
    # Ref: https://groups.google.com/g/tesseract-ocr/c/7q5pmgJDu_o/m/q9Pb7UMoAgAJ

    # Create unicharset from training_text.
    # unicharset_extractor \
    #     --norm_mode 1 \
    #     --output_unicharset "${output_dir}/${model_name}.unicharset" \
    #     "../langdata/${model_name}/${model_name}.training_text"
    # Copy prepared unicharset & other files.
    langdata_dir="${data_dir}/langdata"
    mkdir -p "${langdata_dir}/${model_name}"
    cp "$HOME/ocr/data/${model_name}/${model_name}."* "${langdata_dir}/${model_name}/"

    # Create starter traineddatda (aka recoder).
    combine_lang_model \
        --input_unicharset "${output_dir}/${model_name}.unicharset" \
        --script_dir "${data_dir}/langdata" \
        --output_dir "$output_dir" \
        --lang "$model_name"

    # Create training files (for each image).
    lstmf_dir="${output_dir}/${model_name}"
    # tiff_files=$(find "${ground_truth_dir}/" -name '*.tif')
    # for tif in $tiff_files; do
    #     name="$(basename "$tif")"
    #     base="${name%.*}"
    #     tesseract "$tif" "${lstmf_dir}/${base}" --psm 6 lstm.train
    # done
    # Ref: https://stackoverflow.com/a/9612232
    find "${ground_truth_dir}/" -name '*.tif' -print0 |\
        while IFS= read -r -d '' tif; do
            name="$(basename "$tif")"
            base="${name%.*}"
            tesseract "$tif" "${lstmf_dir}/${base}" --psm 6 lstm.train
        done
    # Create list of lstmf files
    ls -1 "${lstmf_dir}/"*.lstmf > "${output_dir}/${model_name}.training_files.txt"

    # Train.
    lstmtraining \
        --traineddata "${output_dir}/${model_name}.traineddata" \
        --model_output "${output_dir}/${model_name}"  \
        --train_listfile  "${output_dir}/${model_name}/${model_name}.training_files.txt" \
        --max_iterations "$max_iter"

    # Create Final traineddata.
    lstmtraining \
        --stop_training \
        --continue_from "${output_dir}/${model_name}_checkpoint" \
        --traineddata "${output_dir}/${model_name}.traineddata" \
        --model_output "${tess_tr_dir}/${model_name}.traineddata"
elif [[ -n "$replace_layer" ]]; then
    echo "Training by replacing top layer of start model \"$start_model\"."
    # Need to follow same steps as "training" from Makefile, but also replace layers.
    # Use modified Makefile
    # TODO: Edit Makefile-layer to replace & retrain layers.
    echo "Using Makefile \"${ocr_script_dir}/Makefile-layer\""
    make -f "${ocr_script_dir}/Makefile-layer" training \
        MODEL_NAME="$model_name" \
        CORES=2 \
        START_MODEL="$start_model" \
        TESSDATA="$tessdata" \
        MAX_ITERATIONS="$max_iter" \
        DEBUG_INTERVAL="$debug_interval" \
        2>&1 | tee "$log"
else
    # Standard training with GT.TXT files.
    make training \
        MODEL_NAME="$model_name" \
        CORES=2 \
        START_MODEL="$start_model" \
        TESSDATA="$tessdata" \
        MAX_ITERATIONS="$max_iter" \
        DEBUG_INTERVAL="$debug_interval" \
        2>&1 | tee "$log"
fi
time_end=$(date +%s)
duration=$(($time_end - $time_start))

echo "Training lasted ${duration}s."
echo "Log file: $log"
# per_iter=$(($max_iter / $duration))
