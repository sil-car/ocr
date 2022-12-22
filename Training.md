# Training

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

### Unicode character list

Since this OCR model is intended to improve character recognition for Latin script-based languages in the central Africa region, the vast majority of the unicode characters chosen for training come from SIL's [Cameroon Multilingual keyboard](https://langtechcameroon.info/keyboard/), which is widely used in the region. A few additional characters were added after getting feedback from linguists working in the region.

### Fonts and font styles

All the fonts used for image generation for training can be found in [scripts/generate-training-data.py](scripts/generate-training-data.py) or by passing the '-c' option to the command:
```bash
(env) $ ./scripts/generate-training-data.py -c
```

Several font families have been tested, including various SIL fonts, as well as common Microsoft, Android, and Open Source fonts. In the end, all of the following fonts were discarded after proving to be unable to render at least some of the combined glyphs:
- ~Andika New Basic~
- ~Arial~
- ~Carlito~
- ~Comic Sans MS~
- ~Liberation Sans~
- ~Noto Sans/Serif~
- ~Times New Roman~

### Character selection during image generation

At first it was assumed that simply generating random combinations of valid characters would be sufficient when generating the training images. However, that proved to give very poor and unusable results. So the character selection is now based on a weighting system that attempts to mimic real-world rates of the various types of characters. The weights can be found in [scripts/generate-training-data.py](scripts/generate-training-data.py) or by passing the '-w' option to the command:
```bash
(env) $ ./scripts/generate-training-data.py -w
```

In addition to the basic weighted system, some characters were especially poorly recognized. These characters are given an added weighting to increase their generation rates. They are noted at the end of the output from the above command.

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
