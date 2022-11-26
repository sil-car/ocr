#!/bin/bash

### Start tesseract training on cloud server with relevant options.

# Set initial variables.
if [[ -n "$1" ]]; then
    max_iter="$1"
else
    max_iter=100000
fi
tess_tr_dir="${HOME}/tesstrain/"
tess_data="/usr/local/share/tessdata"

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
make training MODEL_NAME=Latin_afr CORES=2 START_MODEL=Latin TESSDATA="$tess_data" MAX_ITERATIONS="$max_iter"
time_end=$(date +%s)
duration=$(($time_end - $time_start))

echo "Training lasted ${duration}s."
# per_iter=$(($max_iter / $duration))
