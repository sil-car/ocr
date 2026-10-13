# Training

## Overview

There are several factors considered when preparing and running the training:
- precise list of unicode characters used
- whether to normalize to NFC or NFD
- character generation type (random, weighted by frequency, pseudo-word, etc.)
- share of real text lines vs. generated pseudo-word lines
- adjusting character frequency to match "real world" data
- text line length (in characters)
- number of fonts and font styles used
- image height (in pixels)
- image degradations (e.g. fade, blur, noise)
- number of images generated
- number of training iterations run
- type of training (fine tuning or layer replacement)
- size of top layer when using layer replacement

Each factor has been seen to influence the performance of the finished model, so dozens of models have been produced in order to compare the relative importance of each factor.
*However*, not all factors have been tested in complete isolation, so there is no quantification of the importance of each factor. If changing a factor improved the resulting model, then that change was kept without first testing if a different change would have improved the model even more.

Other factors to consider:
- Explicitly define the unicharset to remove composed characters?
  - Not possible: **tesseract** normalizes GT to NFC, so the unicharset is also always normalized to NFC.
- Explicitly define the unicharset to include all possible NFC characters plus additional NFD characters?

### Unicode character list

Since this OCR model is intended to improve character recognition for Latin script-based languages in the central Africa region, the vast majority of the unicode characters chosen for training come from SIL's [Cameroon Multilingual keyboard](https://langtechcameroon.info/keyboard/), which is widely used in the region. A few additional characters were added after getting feedback from linguists working in the region.

### Run setup.sh script to install dependencies and prepare tesstrain (ubuntu)
```
(env) $ ./scripts/setup.sh
```

### Generate training data and run the training.
See help for primary scripts:
```
(env) $ ./scripts/generate-training-data.py -h
(env) $ ./scripts/run-training.sh -h
```

### Fonts and font styles

All the fonts used for image generation for training can be found at `properties.fonts` in [data/Latin_afr/config.toml](data/Latin_afr/config.toml) or by passing the '-c' option to the command:
```
(env) $ ./scripts/generate-training-data.py -c
```

### Character selection during image generation

At first it was assumed that simply generating random combinations of valid characters would be sufficient when generating the training images. However, that proved to give very poor and unusable results.

Then character selection was made based on a weighting system that attempted to mimic real-world rates of the various types of characters.

Then a "pseudo-word" generation method was introduced. This assumes a CVCV word structure with varied word lengths, diacritics occasionally added over or below vowels, and diacritics rarely added over consonants.

Currently, real text lines can be mixed in with the pseudo-word lines. The real lines can be extracted from text files and sampled by `scripts/extract-text-lines.py`, which balances the sample so that rare non-ASCII characters are well represented. The source texts stay outside the repo; only the selected lines are needed.

The character inventory is bounded by the characters of the [Cameroon Multilingual keyboard](https://langtechcameroon.info/keyboard/): letters (and their capitals), diacritics, numbers and punctuation in [data/Latin_afr/config.toml](data/Latin_afr/config.toml), plus all printable ASCII. It is checked per code point, so any listed diacritic may go on any listed letter. `extract-text-lines.py` drops lines with any other code point before selecting lines (counts are printed and saved in the `.json` manifests; `--keep-unhandled` turns this off), and `generate-training-data.py` skips such lines from `--lines-file` with a warning. To see what would be dropped without selecting anything, run `extract-text-lines.py` with `--report-unhandled`, which writes `unhandled.tsv` and `unhandled-by-language.tsv`.

Look-alike code points are replaced with one standard form everywhere text comes in (training lines, ground truth and evaluation), using `[properties.codepoint_map]` in config.toml: e.g. the keyboard's Greek alpha (U+03B1) becomes Latin alpha (U+0251), and zero width spaces are deleted.

Pass the extracted lines with `-l/--lines-file` (it can be given more than once). By default 75% of the images use real lines (`-R/--real-ratio`) and the rest use pseudo-words, because many characters in the character list don't occur in the real texts. Real lines are used in file order, and each line is used once before any line repeats; each repeat gets a new random font, style and degradation. Without `--lines-file`, every line is pseudo-words, as before.

With `--lines-file`, the base letters, numbers and punctuation in pseudo-words follow their frequencies in the real lines that will be used (each keeps at least a fifth of an even share, so nothing disappears), instead of the built-in weights.

`-m/--min-char-count N` makes every character the inventory can produce appear at least N times in the run. Characters are counted per NFC code point, the way tesseract's unicharset splits text: precomposed letters (é, ẹ) are characters of their own, while combinations without a precomposed form (ɛ̂) are a base letter plus a combining mark. Before the run, the script counts the code points in the real lines that will be used, and plans the shortfall into the pseudo-word lines (at most `--max-forced` per line, default 8). Upper-case letters are placed at the start of a word. At the end it reports how many code points reached N and lists any that didn't, e.g. because no font could draw their line. A starting value of 300 adds only about 2 planned characters per pseudo-word line in a 200,000-image run:
```
(env) $ ./scripts/generate-training-data.py -i 200000 -l ~/ocr-data/lines/all.txt -m 300
```

Each line is drawn only in a font that has every character in it, so an image always matches its ground truth text. If no allowed font can draw a line, that iteration is skipped with a warning naming the missing characters.

### Generating the training data
Corresponding text line images and ground truth text files will be created.
```
(env) $ ./scripts/generate-training-data.py -i 500 # more likely over 100_000
```
To mix in real text lines (see above):
```
(env) $ ./scripts/generate-training-data.py -i 200000 -l ~/ocr-data/lines/all.txt
```
Files are named `<7-digit number>-<font>-<style>`, e.g. `0000123-Charis_SIL_Compact-Bold_Italic.png` and `.gt.txt`, so they sort in the order they were created. A second run into the same folder continues the numbering.

### Image line length

The length of each generated pseudo-word line is set to 75 characters (`-L/--line-length`). It's not clear if changing this value would have any effect on the model's training. It was chosen to roughly match real-world line lengths.

Real text lines keep the lengths they were given by `scripts/extract-text-lines.py`, which wraps each paragraph at a random width between 35 and 75 graphemes (`--min-width`/`--max-width`), to give the mix of line lengths found in real columns and pages.

### Image height

The height of the generated image has been set to 48px, which matches the base Latin model's input image height. This presumably reduces any inefficiencies introduced if the input image were to be scaled.

### Numbers of images generated and training iterations

It seems to be more of an art than a science to decide how many images to generate and how many training iterations to run on them. Testing seemed to show that training BCER were minimized if training iterations were maximized, but there's a point at which overtaining occurs and the real-world CER increases if BCER is minimized.

Overtraining has been defined as two or more consecutive checkpoints where the ratio between the evaluation CER to the training BCER is greater than 1.0 and increasing. This implies divergence between the training error ratio (on synthetic data) and the evaluation error ratio (on real-world data), which implies overtraining.

The number of images generated has been chosen based both on the expected number of iterations and the available storage on the test system. Often about 200,000 images are generated.

Then training is allowed to run until overtraining is suspected; i.e. the CER/BCER > 1 and growing for two consecutive model checkpoints. This can lead to anywhere from 50,000 iterations to over 100,000 iterations. The iteration limit is 99% of the number of image/ground-truth pairs, so 99% of generated images.

### Type of training (fine tuning vs layer replacement)

Fine tuning works okay and is fairly straightforward to run, but test results show that replacing the top layer works significantly better. See [Evaluation.md](Evaluation.md) for more details.

### Size of replaced top layer

It seems other models with large numbers of output characters use a top layer size of 512 nodes, while some use 256 or something in between. Sizes varying from 256 to 512 to 1024 to 1536 were tested, and the bigger the layer the better the recognition seems to be. However, there is a performance cost with larger top layers, both when training and when evaluating.
> [Ref: detailed info about Latin.traineddata model](https://tesseract-ocr.github.io/tessdoc/Data-Files-in-tessdata_best.html)

## Notes on specific models

See [data/training/training model notes.ods](data/training/training model notes.ods)

## Other Notes

The tesstrain repo's included `Makefile` has been modified to use `--sequential_training`.
The main benefit is reduced memory use. Otherwise `ltsmtraining` collects many
files in memory and chooses one line at a time from each file for better randomization.
However, our generated training data is already randomized, as well as being single-line
files anyway. So there seems to be nothing lost by choosing sequential training.
More info at: https://github.com/tesseract-ocr/tessdoc/blob/f5d77b62/tess5/TrainingTesseract-5.md#randomized-training-data-and-sequential_training
