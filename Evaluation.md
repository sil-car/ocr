# Evaluation

Models are rated based on a score computed from the average CER over the test documents and the standard deviation of the CERs:
```
score = 1000 / (0.5 * (1 + avg_cer) + 0.5 * (1 + std_dev)) ** 2
```

The standard deviation is included as a way to prefer models that produce more consistent CERs across all test documents, which would maybe indicate better performance on other, unknown documents. Only using the best average CER might bias the rating towards models that happen to be especially well-trained for the test set.

## Using *jiwer* Module

![Models scoring above 875](data/evaluation/models-above-score-875.png)

![Best & Latin Model Performance by ISO_Language](data/evaluation/comp-Latin-Latin_afr_202511200870.png)

> - Chart data gathered from [data/evaluation/data.csv](data/evaluation/data.csv)
> - data.csv populated from evalutation of files in [data/evaluation/\<iso_langname\>](data/evaluation).

### Shortcomings

- i + grave accent commonly recognized as either i + macron-grave or dotless i + grave

> 1. This testing has been done without any image preprocessing (e.g. increasing contrast to remove specks that could be confused for characters). It has also not made use of tesseract's character blacklist or whitelist features, which in some cases would significantly reduce substitution and/or insertion errors.

### Commands

```bash
(env) $ # Verify that all models have been used and evaluated with all image/GT pairs.
(env) $ ./scripts/evaluate-models.py
Using model: Latin
 - Evaluating file: ...
 - Creating file: ...
  [...]
(env) $ # Create charts to summarize data.
(env) $ ./scripts/show-chart.py         # all models summary chart
(env) $ ./scripts/show-chart.py comp    # Latin vs best comparison chart
```
