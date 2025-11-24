# Training

## Overview

There are several factors considered when preparing and running the training:
- precise list of unicode characters used
- character generation type (random, weighted by frequency, pseudo-word, etc.)
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
- explicitly define the unicharset to remove composed characters?

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

All the fonts used for image generation for training can be found in [data/Latin_afr/fonts.txt](data/Latin_afr/fonts.txt) or by passing the '-c' option to the command:
```
(env) $ ./scripts/generate-training-data.py -c
```

### Character selection during image generation

At first it was assumed that simply generating random combinations of valid characters would be sufficient when generating the training images. However, that proved to give very poor and unusable results.

Then character selection was made based on a weighting system that attempted to mimic real-world rates of the various types of characters.

Currently, a "pseudo-word" generation method is used. This assumes a CVCV word structure with varied
word lengths, diacritics occasionally added over or below vowels, and diacritics rarely added over
consonants.

### Generating the training data
Corresponding text line images and ground truth text files will be created.
```
(env) $ ./scripts/generate-training-data.py -i 500 # more likely over 100_000
```

### Image line length

The length of each text line in the generated images is set to 75. It's not clear if changing this value would have any effect on the model's training. It was chosen to roughly match real-world line lengths.

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
