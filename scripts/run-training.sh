#!/bin/bash

### Start tesseract training on cloud server with relevant options.

# Set initial variables.
reset=
debug=
model_name="Latin_afr"
tess_tr_dir="${HOME}/tesstrain"
data_dir="${tess_tr_dir}/data"
tess_data="/usr/local/share/tessdata"
max_iter=100000
debug_interval=0
t2i=

help_text="usage: $0 [-dtv] [-i NUM]"
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

# Handle clean option.
if [[ -n "$reset" ]]; then
    # Clean generated files & exit (for now).
    make clean "MODEL_NAME=${model_name}"
    rm "${tess_tr_dir}/data/"*.traineddata
    cp -r "$HOME/ocr/data/Latin_afr" "${tess_tr_dir}/data/"
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
