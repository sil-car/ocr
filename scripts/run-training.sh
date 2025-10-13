#!/bin/bash

### Start tesseract training on cloud server with relevant options.

# Set initial variables.
cores=$(nproc)
convert_checkpoint=
debug=
reset=
replace_layer=
net_spec_top='Lfx512'
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

d=
v=

help_text="usage: $0 [-dhrtv] [-c CHECKPOINT] | [-l NET_SPEC] [-i NUM]"
while getopts ":c:dhi:l:rtv" opt; do
    case $opt in
        c) # convert checkpoint
            convert_checkpoint=YES
            checkpoint_file="$OPTARG"
            ;;
        d) # debug
            debug=YES
            v='-v'
            d='-d'
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
            net_spec_top="$OPTARG"
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
    rm -fv "${data_dir}/"*.traineddata
    cp -rv "$HOME/ocr/data/${model_name}" "${data_dir}/"
    exit 0
fi

# Handle convert checkpoint option.
if [[ -n "$convert_checkpoint" ]]; then
    # Verify that files exist.
    traineddata_file="${data_dir}/${model_name}/${model_name}.traineddata"
    checkpoints_dir="${data_dir}/${model_name}/checkpoints"
    if [[ ! -f "$checkpoint_file" ]]; then
        if [[ -f "${checkpoints_dir}/${checkpoint_file}" ]]; then
            checkpoint_file="${checkpoints_dir}/${checkpoint_file}"
        else
            echo "Error: File not found: $checkpoint_file"
            exit 1
        fi
    elif [[ ! -f "$traineddata_file" ]]; then
        echo "Error: File not found: $traineddata_file"
        exit 1
    fi
    # Convert checkpoint file to traineddata file.
    checkpoint_filename="$(basename "$checkpoint_file")"
    checkpoint_name="${checkpoint_filename%.checkpoint}"
    echo "Converting checkpoint to traineddata:"
    echo "  Checkpoint: $checkpoint_file"
    echo "  Outfile: ${data_dir}/${checkpoint_name}.traineddata"
    lstmtraining \
        --stop_training \
        --continue_from "$checkpoint_file" \
        --traineddata "${traineddata_file}" \
        --model_output "${data_dir}/${checkpoint_name}.traineddata"
    exit $?
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
        --train_listfile  "${output_dir}/${model_name}/${model_name}.training_files.txt" \
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
    # NOTE: The 1st term/layer in NET_SPEC includes the resized pixel height of the GT images.
    #   36px: [1,36,0,1...
    #   Ref:
    #   - https://github.com/tesseract-ocr/tesstrain/issues/241#issuecomment-880984403
    #   - https://github.com/tesseract-ocr/tessdoc/blob/f3201f2d32e69144047028869e0eda80b2b1cee2/tess4/VGSLSpecs.md
    net_spec="[$net_spec_top O1c###]"
    echo "NET_SPEC = $net_spec"
    make $d -f "${ocr_script_dir}/Makefile-layer" training \
        MODEL_NAME="$model_name" \
        CORES="$cores" \
        START_MODEL="$start_model" \
        TESSDATA="$tessdata" \
        MAX_ITERATIONS="$max_iter" \
        DEBUG_INTERVAL="$debug_interval" \
        NET_SPEC="$net_spec" \
        2>&1 | tee "$log"
else
    # Standard training with GT.TXT files.
    make $d -f "${ocr_script_dir}/Makefile-seq" training \
        MODEL_NAME="$model_name" \
        CORES="$cores" \
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
