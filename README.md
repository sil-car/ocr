# OCR for African Latin-based writing systems

An attempt at creating a reliable character-based OCR solution for Latin-based writing scripts in Africa. The strategy is to start with **Tesseract's** Latin script training data and improve it using additional data relevant to languages in the central African region.

## Goals

1. Develop an accurate system for OCRing text at the character level from documents produced/discovered in the central Africa region. (Theoretically, this could apply to *any* language that uses a Latin-based script, but the generated training data will only explicitly consider characters important to the central Africa region.)
1. Ideally, allow for the OCR scope to be narrowed by a specific language's
   given character set.

### Current Testing
Current best model: [tessdata/Latin_afr_202212178613.traineddata](tessdata/Latin_afr_202212178613.traineddata)

Average CER: 3.82% over 5,381 characters from 15 samples

[Summary test results](Testing.md)

[Full test results](data/example-documents/)

### Usage
1. Install **Tesseract** on your system.
1. Copy the above model into **Tesseract's** *tessdata* folder; e.g.
   ```
   sudo wget https://github.com/sil-car/ocr/raw/main/tessdata/Latin_afr_2022121409.traineddata -P /usr/share/tesseract-ocr/4.0/tessdata/
   ```
1. Use the model with **Tesseract**; e.g.
   ```
   tesseract -l Latin_afr_2022121409 image.png
   ```
You can also make use of other front-end apps that use **Tesseract** as a back end. Just select "Latin_afr_2022121409" as the language to be recognized after having copied the model to the appropriate place.

## Existing OCR options are unsatisfactory

**[Tesseract](https://github.com/tesseract-ocr)** seems to be a reasonable option for character-based OCR work because it provides script-based "language" options while other solutions are language-based. But when **Tesseract** was tried on a document in a central African language with a Latin-based script (Banda-Linda [liy]) it clearly struggled to properly identify less-common Latin script characters (e.g. ɓ, ɗ, ɛ, ə, ŋ, ɔ), as well as both those and more-common ones that were composed with various diacritics. Nevertheless, **Tesseract** is still able to properly identify *~95%* of the Banda-Linda characters using the "Latin" language option, i.e.:
```
tesseract -l Latin image.png
```

This was further tested on more than 15 other documents from the region that use some of the same "special" characters and diacritics. Details of those results can be found in [data/example-documents](data/example-documents). In all cases the same kinds of characters as with Banda-Linda were improperly recognized.

## Considerations

### Scope

From an end-user perspective it would be great to have a graphical, cross-platform app than can reliably perform these steps:
1. Recognize text blocks in an image or PDF document, regardless of columns, text orientation, etc.
1. Recognize all Latin script characters within these text blocks, regardless of language.
1. Export the text to a unicode text file.
1. Optionally export the results, including images, to a searchable PDF.
1. Optionally export the results, including images, to an editable document format, such as ODT or ODG.

This repository will only focus on Step 2: OCR proper using **Tesseract**. Later, various GUI apps can be evaluated depending on specific end user needs.

### Defining accuracy

OCR accuracy can be measured in a few different ways. Since we are concerned with
an OCR solution at the writing script-level (i.e. character level) rather than one
at the word-level, we will focus on the Character Error Rate (CER).

The CER is composed of 5 quantities:
1. N: number of characters in source text (or ground truth text)
1. C: number of correctly recognized characters
1. S: number of substitution errors (i.e. wrong character was recognized)
1. D: number of deletion errors (i.e. character was left out of results)
1. I: number of insertion errors (i.e. character was added to results)

The simple CER is calculated as follows:
```CER = (S + D + I) / N
```

However, this can result in a CER > 100% if there are many insertion errors. So
an alternative *Normalized CER* can be calculated as follows:

```CERn = (S + D + I) / (S + D + I + C)
```

Ideally, this solution will prove to be **98%-99%** accurate; i.e. CER <= 2%.
*Further reading:*
- *http://www.dlib.org/dlib/march09/holley/03holley.html*
- *https://towardsdatascience.com/evaluating-ocr-output-quality-with-character-error-rate-cer-and-word-error-rate-wer-853175297510*

### Character set

The new script model, "Latin_afr", will be based on "Latin", then be given training data using the following vowels, consonants, and diacritics:
- vowels: a, e, i, o, u, ɛ, æ, ɑ, ə, ı, ɨ, ɔ, ø, œ, ʉ
- consonants: b, c, d, f, g, h, j, k, l, m, n, p, q, r, s, t, v, w, x, z, ɓ, ɗ, ŋ, ẅ, ꞌ, ʼ
- top diacritics:
  - \u0300 # combining grave accent
  - \u0301 # combining acute accent
  - \u0302 # combining circumflex
  - \u0303 # combining tilde above
  - \u0304 # combining macron
  - \u0308 # combining diaeresis
  - \u030c # combining caron
  - \u030d # combining vert. line above
  - \u1dc4 # combining macron-acute
  - \u1dc5 # combining grave-macron
  - \u1dc6 # combining macron-grave
  - \u1dc7 # combining acute-macron
- bottom diacritics:
  - \u0323 # combining dot below
  - \u0327 # combining cedilla
  - \u0330 # combining tilde below
- punctuation: !"'(),-.:;?[]¡«»“”‹›
