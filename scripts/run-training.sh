#!/bin/bash

### Start tesseract training on cloud server with relevant options.

# Set initial variables.
tess_tr_dir="${HOME}/tesstrain/"
tess_data="/usr/local/share/tessdata"
max_iter=100000
debug_interval=0

help_text="usage: $0 [-v] [-i NUM]"
while getopts ":hi:v" opt; do
    case $opt in
        h) # help text
            echo "$help_text"
            exit 0
            ;;
        i) # max. iterations
            max_iter="$OPTARG"
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
make training \
    MODEL_NAME=Latin_afr \
    CORES=2 \
    START_MODEL=Latin \
    TESSDATA="$tess_data" \
    MAX_ITERATIONS="$max_iter" \
    DEBUG_INTERVAL="$debug_interval"
time_end=$(date +%s)
duration=$(($time_end - $time_start))

echo "Training lasted ${duration}s."
# per_iter=$(($max_iter / $duration))
