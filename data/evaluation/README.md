# Evaluation steps

1. Download `TRAINEDDATA` file to `tessdata` dir, giving it a unique `MODEL_NAME.traineddata`.
1. [optionally] Convert checkpoints to `traineddata` files:
  - `scripts/run-training -c /path/to/CHECKPOINT_MODEL_NAME.checkpoint`
  - `mv ~/tesstrain/data/CHECKPOINT_MODEL_NAME.traineddata tessdata/Latin_afr_MODEL_NAME.traineddata`
1. Run `scripts/evaluate-models.py` to evaluate test documents with all models
  (incl. the new one)
1. Run `scripts/show-chart.py -t model -l MODEL_NAME` to display model results.
1. Update `training/training model notes.ods` with CERs.

## Evaluation Strategy

- Select documents such that all characters covered by the model occur at least once.
- The CER rate will likely be higher in this case than in real-world use, assuming that rarer characters will be over-represented in the evaluation data.
