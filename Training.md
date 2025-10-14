# Training

## Overview

There are several factors considered when preparing and running the training:
- precise list of unicode characters used
- number of fonts and font styles used
- character generation type (random or weighted)
- extra generation for characters getting poor results
- image line length (in characters)
- image height (in pixels)
- number of images generated
- number of training iterations run
- type of training (fine tuning or layer replacement)
- format of top layer when using layer replacement

Each factor has been seen to influence the performance of the finished model, so more than two dozen models have been produced in order to compare the relative importance of each factor.
*However*, not all factors have been tested in complete isolation, so there is no quantification of the importance of each factor. If changing a factor improved the resulting model, then that change was kept without first testing if a different change would have improved the model even more.

Other factors to consider:
- add noise to synthetic training data?
- explicitly define the unicharset to remove composed characters?
- increase the size of the top layer from 512?

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

At first it was assumed that simply generating random combinations of valid characters would be sufficient when generating the training images. However, that proved to give very poor and unusable results. So the character selection is now based on a weighting system that attempts to mimic real-world rates of the various types of characters. The weights can be found in [scripts/generate-training-data.py](scripts/generate-training-data.py) or by passing the '-w' option to the command:
```
(env) $ ./scripts/generate-training-data.py -w
```

In addition to the basic weighted system, some characters were especially poorly recognized. These characters are given an added weighting to increase their generation rates. They are noted at the end of the output from the above command.

### Generating the training data
Corresponding text line images and ground truth text files will be created.
```
(env) $ ./scripts/generate-training-data.py -i 500 # more likely over 100_000
```

### Image line length

The length of each text line in the generated images is set to 50. It's not clear if changing this value would have any effect on the model's training. It was chosen to roughly match real-world line lengths.

### Image height

The height of the generated image has been set to 48px, which matches the base Latin model's input image height. This presumably reduces any inefficiencies introduced if the input image were to be scaled.

### Numbers of images generated and training iterations

It seems to be more of an art than a science to decide how many images to generate and how many training iterations to run on them. Testing seemed to show that training BCER were minimized if training iterations were maximized, but there's a point at which overtaining occurs and the real-world CER increases if BCER is minimized.

So the number of images generated has been chosen based on the idea that the least likely characters (uppercase consonants with top diacritics) have a good chance of being generated twice in each font style; i.e.:
```
min # of images = 72 base letters / consonant weight / consonant top diacritic weight / uppercase rate X # of fonts X # of font styles X 2 / # of characters per image / 90% rate of images used for training vs testing
```

Then it seems that it's best if each generated image is only seen once during training, so:
```
# of training iterations = min # of images X 90%
```

### Type of training (fine tuning vs layer replacement)

Fine tuning works reasonably well and is fairly straightforward to run. But test results show that replacing the top layer works even better. See [Testing.md](Testing.md) for more details.

### Format of replaced top layer

It seems other models with large numbers of output characters use a top layer size of 512 nodes, while some use 256 or something in between. Both 512 and 256 were tested, and 512 seems to perform better.

## Notes on specific models

Model | Fonts ct. | GT Images ct. | Generated Chars. ct. | Char. Tweaks | Char. Ht. | Top Layer | Iterations | BCER
:-- | :-- | :-- | :-- | :-- | :-- | :-- | :-- | :--
Latin_afr_2022121409 | 8 | 25,600 | 1,280,000 | p_a, p_schwa = 0.01 | 40px | Lfx512 | 23,000 | 8.70%
Latin_afr_2022121416 | 8 | 50,000 | 2,500,000 | p_a, p_schwa = 0.01 | 40px | Lfx512 | 45,000 | 5.33%
Latin_afr_2022121520 | 8 | 50,000 | 2,500,000 | p_a, p_schwa = 0.01 | 40px | Lfx256 | 45,000 | 11.31%
Latin_afr_2022121606 | 8 | 100,000 | 5,000,000 | p_a, p_schwa = 0.01 | 40px | Lfx256 | 90,000 | 8.84%
Latin_afr_2022121705 | 8 | 110,000 | 5,500,000 | p_a, p_schwa = 0.01 | 40px | Lfx512 | 41,300 | 9.34%
Latin_afr_2022121714 | 8 | 110,000 | 5,500,000 | p_a, p_schwa = 0.01 | 40px | Lfx512 | 100,000 | 6.88%
Latin_afr_202212179339 | 8 | 110,000 | 5,500,000 | p_a, p_schwa = 0.01 | 40px | Lfx512 | 41,300 | 9.34%
Latin_afr_202212178613 | 8 | 110,000 | 5,500,000 | p_a, p_schwa = 0.01 | 40px | Lfx512 | 49,800 | 8.61%
Latin_afr_202212178057 | 8 | 110,000 | 5,500,000 | p_a, p_schwa = 0.01 | 40px | Lfx512 | 59,300 | 8.06%
Latin_afr_20221218 | 10 | 64,000 | 3,200,000 | None | 48px | Lfx512 | 58,000 | 8.97%
Latin_afr_20221219 | 10 | 64,000 | 3,200,000 | extra 'y' | 48px | Lfx512 | 58,000 | 8.94%
Latin_afr_20221221 | 10 | 64,000 | 3,200,000 | extra 'y' | 48px | Lfx256 | 58,000 | 11.04%
Latin_afr_20230129 | 31 | 115,000 | 5,750,000 | extra 'y' | 48px | Lfx512 | 102,000 | 11.77%
Latin_afr_20230131 | 31 | 345,000 | 17,250,000 | extra 'y' | 48px | Lfx512 | 306,000 | 8.71%
