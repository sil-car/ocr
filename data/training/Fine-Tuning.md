# Fine-Tuning notes from 2026-09-21
Claude recommended fine-tuning based on real data rather than retraining.
1. I created ~1000 lines of training data in `data/training/real-gt`.
1. I combined all files into a single tempdir `data/phase2_realdata/gt`.
1. I generated `.box` and `.lstmf` files from the `GT` with Claude's help:
    ```bash
    # scripts/create-lstm-parallel.sh 
    
    TESSTRAIN_DIR="../tesstrain"   # wherever setup.sh put it
    GT_DIR="data/phase2_realdata/gt"        # your per-language subdirectories
    
    find "$GT_DIR" -name '*.png' | xargs -P "$(nproc)" -I{} bash -c '
        img="{}"
        base="${img%.png}"
        gt="${base}.gt.txt"
        if [[ ! -f "$gt" ]]; then
            echo "WARNING: missing ground truth for $img" >&2
            exit 0
        fi
        python3 "'"$TESSTRAIN_DIR"'/generate_line_box.py" -i "$img" -t "$gt" > "${base}.box"
        tesseract "$img" "$base" --psm 13 lstm.train
    '
    ```
1. I created `lstm.train` and `lstm.eval` files with Claude's help:
    ```bash
    # scripts/create-list-files.sh
    
    GT_DIR="data/phase2_realdata/gt"
    WORK_DIR="data/phase2_realdata"
    
    : > "${WORK_DIR}/list.train"
    : > "${WORK_DIR}/list.eval"
    
    for lang in $(for f in "$GT_DIR"/*.lstmf; do basename "$f" .lstmf; done | cut -d'_' -f1 | sort -u); do
        mapfile -t files < <(find "$GT_DIR" -maxdepth 1 -name "${lang}_*.lstmf" | shuf)
        n=${#files[@]}
    
        if (( n < 10 )); then
            n_eval=0
        else
            n_eval=$(( n / 5 ))
            (( n_eval < 2 )) && n_eval=2
        fi
    
        printf '  %-6s %3d files -> %3d train / %2d eval\n' "$lang" "$n" "$((n - n_eval))" "$n_eval"
        printf '%s\n' "${files[@]:0:$((n - n_eval))}" >> "${WORK_DIR}/list.train"
        (( n_eval > 0 )) && printf '%s\n' "${files[@]: -$n_eval}" >> "${WORK_DIR}/list.eval"
    done
    ```
1. I extracted the LSTM network from the previous best model, `Latin_afr_202612160504.traineddata`:
    ```bash
    BASE_MODEL_FILE=tessdata/Latin_afr_202512160504.traineddata
    WORK_DIR=data/phase2_realdata
    combine_tessdata -u $BASE_MODEL_FILE $WORK_DIR/Latin_afr_202512160504
    ```
1. I evaluated that model using `lstmeval`:
    ```bash
    BASE_MODEL_FILE=tessdata/Latin_afr_202512160504.traineddata
    WORK_DIR=data/phase2_realdata
    lstmeval \
      --model $WORK_DIR/Latin_afr_202512160504.lstm \
      --traineddata $BASE_MODEL_FILE \
      --eval_listfile $WORK_DIR/list.eval
    ```
    Result:
    ```
    BCER eval=22.544, BWER eval=42.443
    ```
1. I did initial fine-tuning on the previous best model using the new, real data:
    ```bash
    lstmtraining \
      --continue_from $WORK_DIR/Latin_afr_202512160504.lstm \
      --traineddata $BASE_MODEL_FILE \
      --train_listfile $WORK_DIR/list.train \
      --eval_listfile $WORK_DIR/list.eval \
      --model_output $WORK_DIR/checkpoints/rd1 \
      --learning_rate 0.0001 \
      --reset_learning_rate \
      --max_iterations 300
    ```
1. I discovered 3 characters in the new data that were not included in the original training:
    | Language | Missing character(s)
    | :-- | :-- |
    | gna | ʋ (U+028B), ɲ (U+0272)
    | hed	| ɦ (U+0266)
1. I evaluated the best fine-tuned checkpoint:
    ```bash
    BASE_MODEL_FILE="tessdata/Latin_afr_202512160504.traineddata"
    WORK_DIR="data/phase2_realdata"
    
    lstmeval \
      --model "${WORK_DIR}/checkpoints/rd1_4.084_130_200.checkpoint" \
      --traineddata "$BASE_MODEL_FILE" \
      --eval_listfile "${WORK_DIR}/list.eval"
    ```
    Result:
    ```
    BCER eval=12.701, BWER eval=26.070
    ```
1. I exported that checkpoint
    ```bash
    BASE_MODEL_FILE="tessdata/Latin_afr_202512160504.traineddata"
    WORK_DIR="data/phase2_realdata"
    
    lstmtraining --stop_training \
      --continue_from "${WORK_DIR}/checkpoints/rd1_4.084_130_200.checkpoint" \
      --traineddata "$BASE_MODEL_FILE" \
      --model_output "tessdata/Latin_afr_202609211700.traineddata"
    ```
1. I tested that model with the repo's typical test regime at `data/evaluation/README.md`.
1. I did additional fine-tuning for later evaluation:
    ```bash
    BASE_MODEL_FILE="tessdata/Latin_afr_202512160504.traineddata"
    WORK_DIR="data/phase2_realdata"

    lstmtraining \
      --continue_from "${WORK_DIR}/checkpoints/rd1_4.084_130_200.checkpoint" \
      --traineddata "$BASE_MODEL_FILE" \
      --train_listfile "${WORK_DIR}/list.train" \
      --eval_listfile "${WORK_DIR}/list.eval" \
      --model_output "${WORK_DIR}/checkpoints/rd1" \
      --max_iterations 800
    ```
