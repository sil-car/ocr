#!/bin/bash

### Generate training data (optional) and train the Latin_afr model in one step.
#
# Wraps generate-training-data.py and tesstrain's Makefiles. The other scripts
# still work on their own; run-training.sh is still used for converting a
# checkpoint (-c) and the resets (-r/-R).
#
# Examples:
#   train.sh -n 100000                  # new images, replace top layer of Latin (Lfx1152), 1 epoch
#   train.sh -n 100000 -L Lfx1536 -d    # same with a bigger top layer, detached in screen
#   train.sh -f ~/Latin_afr_old.traineddata   # fine-tune an earlier model on the current images
#   train.sh -c -i 150000               # continue the last run up to 150000 iterations in total
#   train.sh -n 200000 -- -R 0.5        # pass extra options to generate-training-data.py

set -o pipefail

orig_args=("$@")

ocr_script_dir="$(readlink -f "$(dirname "$0")")"
repo_dir="$(dirname "$ocr_script_dir")"

# Fixed settings.
model_name="Latin_afr"
base_model="Latin"
tess_tr_dir="${HOME}/tesstrain"
data_dir="${tess_tr_dir}/data"
tessdata="${HOME}/tessdata_best"
output_dir="${data_dir}/${model_name}"
gt_dir="${repo_dir}/data/training/${model_name}-ground-truth"
our_makefile="${ocr_script_dir}/Makefile"
replace_makefile="${ocr_script_dir}/Makefile-replace-top-layer"
last_checkpoint="${output_dir}/checkpoints/${model_name}_checkpoint"
proto_model="${output_dir}/${model_name}.traineddata"
final_model="${data_dir}/${model_name}.traineddata"
screen_name="ocr-train"

# Defaults (change with options).
num_images=
lines_files=()
default_lines_file="${HOME}/ocr-example-docs/extracted/all.txt"
min_char_count=300
top_layer="Lfx1152"
finetune_from=
continue_run=
iterations=
epochs=1
ratio_train=0.99
debug_interval=-1
detach=
dry_run=

usage="usage: $0 [-n NUM] [-l FILE]... [-m N] [-L SPEC | -f MODEL | -c] [-i NUM | -e NUM] [-t RATIO] [-dpqh] [-- GENERATOR_ARGS]"
help_text="$usage

Training data:
  -n NUM     delete the old images and generate NUM new ones first;
             without -n the images already in the ground-truth folder are used
  -l FILE    real text lines for generate-training-data.py; can be repeated
             [${default_lines_file}]
  -m N       min. count for every character (generate-training-data.py -m) [${min_char_count}]
  -- ARGS    anything after -- is passed on to generate-training-data.py

Kind of training (choose one):
  -L SPEC    replace the top layer of ${base_model} with SPEC [${top_layer}] (default)
  -f MODEL   fine-tune MODEL instead: a .traineddata path, or a name in ${tessdata}
  -c         continue the last run from its latest checkpoint (no new images,
             same settings); give the new total with -i or -e

Length of training:
  -i NUM     stop after NUM training iterations (in total, also with -c)
  -e NUM     stop after NUM epochs, i.e. passes over the training images [${epochs}];
             ignored if -i is given
  -t RATIO   share of the images used for training; the rest form the eval
             list, which lstmtraining only reports on [${ratio_train}]

Other:
  -d         run detached in a screen session named \"${screen_name}\"
             (attach with: screen -r ${screen_name})
  -p         print the plan and commands without running anything
  -q         quiet: don't log every iteration (DEBUG_INTERVAL=0)
  -h         show this help
"

while getopts ":n:l:m:L:f:ci:e:t:dpqh" opt; do
    case $opt in
        n) num_images="$OPTARG" ;;
        l) lines_files+=("$OPTARG") ;;
        m) min_char_count="$OPTARG" ;;
        L) top_layer="$OPTARG"; layer_given=YES ;;
        f) finetune_from="$OPTARG" ;;
        c) continue_run=YES ;;
        i) iterations="$OPTARG" ;;
        e) epochs="$OPTARG"; epochs_given=YES ;;
        t) ratio_train="$OPTARG" ;;
        d) detach=YES ;;
        p) dry_run=YES ;;
        q) debug_interval=0 ;;
        h) echo -e "$help_text"; exit 0 ;;
        :) echo "Error: -$OPTARG needs a value."; echo "$usage"; exit 1 ;;
        *) echo "Error: unknown option -$OPTARG"; echo "$usage"; exit 1 ;;
    esac
done
shift $((OPTIND - 1))
generator_extra_args=("$@")

die() { echo "Error: $*" >&2; exit 1; }

# Check option combinations.
modes=0
[[ -n $layer_given ]] && modes=$((modes + 1))
[[ -n $finetune_from ]] && modes=$((modes + 1))
[[ -n $continue_run ]] && modes=$((modes + 1))
[[ $modes -gt 1 ]] && die "use only one of -L, -f and -c."
[[ -n $continue_run && -n $num_images ]] && die "-c continues on the same images; it can't be used with -n."
[[ -n $continue_run && -z $iterations && -z $epochs_given ]] && die "with -c, give the new total length with -i or -e."
[[ -n $num_images && ! $num_images =~ ^[0-9]+$ ]] && die "-n needs a number."
[[ -n $iterations && ! $iterations =~ ^[0-9]+$ ]] && die "-i needs a number."
[[ ! $epochs =~ ^[0-9]+$ || $epochs -lt 1 ]] && die "-e needs a whole number of 1 or more."
if [[ ${#lines_files[@]} -eq 0 && -r $default_lines_file ]]; then
    lines_files=("$default_lines_file")
fi

# Re-run inside a detached screen session if asked; keep a shell open
# afterwards so the output can still be read after attaching.
if [[ -n $detach && -z $OCR_TRAIN_DETACHED && -z $dry_run ]]; then
    sessions="$(screen -ls 2>/dev/null)"
    if grep -q "\.${screen_name}[[:space:]]" <<<"$sessions"; then
        die "a screen session named \"${screen_name}\" already exists (screen -r ${screen_name})."
    fi
    OCR_TRAIN_DETACHED=1 screen -dmS "$screen_name" bash -c 'bash "$0" "$@"; exec bash' "${ocr_script_dir}/$(basename "$0")" "${orig_args[@]}"
    echo "Training started in screen session \"${screen_name}\". Attach with: screen -r ${screen_name}"
    exit 0
fi

# Logging. A new log file per start, named like run-training.sh's logs so that
# log-training-summary.sh still finds them.
stamp=$(date +%Y%m%d%H%M)
if [[ -n $dry_run ]]; then
    log=/dev/null
else
    log="${data_dir}/${model_name}_${stamp}.log"
    mkdir -p "$data_dir"
    touch "$log"
fi
say() { echo "$*" | tee -a "$log"; }
# Show a command, then run it (unless -p), with its output copied to the log.
run() {
    say "+ $*"
    [[ -n $dry_run ]] && return 0
    "$@" 2>&1 | tee -a "$log"
    local status=${PIPESTATUS[0]}
    [[ $status -eq 0 ]] || die "command failed (exit $status): $*"
}
# Same, for commands that write to the log themselves (tesstrain's training).
run_nolog() {
    say "+ $*"
    [[ -n $dry_run ]] && return 0
    "$@" || die "command failed (exit $?): $*"
}

# Environment.
export TESSDATA_PREFIX=/usr/local/share/tessdata  # f/ git install
if which deactivate >/dev/null 2>&1; then deactivate; fi
source "${repo_dir}/env/bin/activate" || die "failed to activate ${repo_dir}/env."
cd "$tess_tr_dir" || die "failed to enter \"$tess_tr_dir\"."

# Length of training: -i wins; otherwise epochs (lstmtraining treats a negative
# MAX_ITERATIONS as a number of epochs over list.train).
if [[ -n $iterations ]]; then
    max_iter="$iterations"
    length_desc="${iterations} iterations"
else
    max_iter="-${epochs}"
    length_desc="${epochs} epoch(s) over the training list"
fi

if [[ -n $continue_run ]]; then
    kind="continue last run from ${last_checkpoint}"
elif [[ -n $finetune_from ]]; then
    kind="fine-tune ${finetune_from}"
else
    kind="replace top layer of ${base_model} with ${top_layer}"
fi

time_start=$(date +%s)
say "Started: $(date)"
say "commandline: $0 ${orig_args[*]}"
say "  training:    $kind"
say "  length:      $length_desc"
if [[ -n $num_images ]]; then
    say "  new images:  $num_images (lines: ${lines_files[*]:-none}; min. char count: $min_char_count${generator_extra_args[*]:+; extra: ${generator_extra_args[*]}})"
else
    say "  images:      existing ones in $gt_dir"
fi
[[ -z $continue_run ]] && say "  train ratio: $ratio_train"
say "  log:         $log"
say "  ocr commit:  $(git -C "$repo_dir" rev-parse --short HEAD 2>/dev/null)"
say

### Continue the last run.
if [[ -n $continue_run ]]; then
    for f in "$last_checkpoint" "$proto_model" "${output_dir}/list.train"; do
        [[ -r $f || -n $dry_run ]] || die "nothing to continue: $f not found."
    done
    eval_opts=()
    if [[ -s ${output_dir}/list.eval ]]; then
        eval_opts=(--eval_listfile "${output_dir}/list.eval")
    fi
    # lstmtraining restores from ${model_output}_checkpoint when it exists, so
    # this picks up where the run stopped. Iteration counts are totals.
    run lstmtraining \
        --debug_interval "$debug_interval" \
        --traineddata "$proto_model" \
        --continue_from "$last_checkpoint" \
        --model_output "${output_dir}/checkpoints/${model_name}" \
        --train_listfile "${output_dir}/list.train" \
        "${eval_opts[@]}" \
        --max_iterations "$max_iter" \
        --target_error_rate 0.01 \
        --max_image_MB 100 \
        --sequential_training
    run lstmtraining \
        --stop_training \
        --continue_from "$last_checkpoint" \
        --traineddata "$proto_model" \
        --model_output "$final_model"
else
    ### New run.

    # Put a fine-tuning start model where the Makefile expects one. It gets
    # its own name so it can't collide with $model_name's output folder.
    if [[ -n $finetune_from ]]; then
        if [[ -f $finetune_from ]]; then
            src="$(readlink -f "$finetune_from")"
        elif [[ -f ${tessdata}/${finetune_from%.traineddata}.traineddata ]]; then
            src="${tessdata}/${finetune_from%.traineddata}.traineddata"
        elif [[ -z $dry_run ]]; then
            die "start model not found: $finetune_from"
        fi
        start_name="start-$(basename "${finetune_from%.traineddata}")"
        start_tessdata="${data_dir}/start-models"
        run mkdir -p "$start_tessdata"
        run cp -f "$src" "${start_tessdata}/${start_name}.traineddata"
        # Drop components extracted from an older copy with the same name.
        run rm -rf "${data_dir:?}/${start_name}"
    fi

    # Keep the previous run's output instead of deleting it.
    if [[ -d $output_dir ]]; then
        archive="${data_dir}/archive/${model_name}_$(date -r "$output_dir" +%Y%m%d%H%M)"
        run mkdir -p "${data_dir}/archive"
        run mv "$output_dir" "$archive"
        [[ -f $final_model ]] && run mv "$final_model" "${archive}/${model_name}_final.traineddata"
    fi
    run cp -r "${repo_dir}/data/${model_name}" "${data_dir}/"

    # Generate new images.
    if [[ -n $num_images ]]; then
        gen_args=(-i "$num_images")
        for f in "${lines_files[@]}"; do gen_args+=(-l "$f"); done
        [[ $min_char_count -gt 0 ]] && gen_args+=(-m "$min_char_count")
        run "${ocr_script_dir}/generate-training-data.py" -r
        run "${ocr_script_dir}/generate-training-data.py" "${gen_args[@]}" "${generator_extra_args[@]}"
    fi
    if [[ -z $dry_run ]]; then
        num_gt=$(find "$gt_dir" -name '*.gt.txt' | wc -l)
        [[ $num_gt -gt 0 ]] || die "no images in $gt_dir; generate some with -n."
        say "Images available: $num_gt"
    fi

    # Character stats, as run-training.sh logs them.
    run "${ocr_script_dir}/generate-training-data.py" -c

    # Warn if tesstrain's Makefile has changed since ours were copied from it.
    if ! diff -q "${tess_tr_dir}/Makefile" "$our_makefile" >/dev/null 2>&1; then
        say "WARNING: ${tess_tr_dir}/Makefile differs from $our_makefile (check for upstream changes)."
    fi

    make_opts=(
        DATA_DIR="$data_dir"
        MODEL_NAME="$model_name"
        GROUND_TRUTH_DIR="$gt_dir"
        RATIO_TRAIN="$ratio_train"
        MAX_ITERATIONS="$max_iter"
        DEBUG_INTERVAL="$debug_interval"
        LOG_FILE="$log"
    )
    run make -j "$(nproc)" -f "$our_makefile" tesseract-langdata "${make_opts[@]}"

    if [[ -n $finetune_from ]]; then
        run_nolog make -j "$(nproc)" -f "$our_makefile" training \
            "${make_opts[@]}" \
            TESSDATA="$start_tessdata" \
            START_MODEL="$start_name"
    else
        # NOTE: NET_SPEC only gives the layers that replace the top of the
        # start model; see run-training.sh for notes on the Latin net spec.
        run_nolog make -j "$(nproc)" -f "$replace_makefile" training \
            "${make_opts[@]}" \
            TESSDATA="$tessdata" \
            START_MODEL="$base_model" \
            NET_SPEC="[${top_layer} O1c###]"
    fi
fi

time_end=$(date +%s)
say "Finished: $(date)"
say "Training lasted $((time_end - time_start))s."
say "Model: $final_model"
say "Checkpoints: ${output_dir}/checkpoints/"
