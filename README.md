# OCR for African Latin-based writing systems

An attempt at creating a reliable character-based OCR solution for Latin-based writing scripts in Africa. The strategy is to start with **Tesseract's** Latin script training data and improve it using additional data relevant to languages in the central African region.

## Goals

1. Develop an accurate system for OCRing text at the character level from documents produced/discovered in the central Africa region. (Theoretically, this could apply to *any* language that uses a Latin-based script, but the generated training data will only explicitly consider characters important to the central Africa region.)
1. Ideally, allow for the OCR scope to be narrowed by a specific language's
   given character set.

## Current OCR options are unsatisfactory

**[Tesseract](https://github.com/tesseract-ocr)** seems to be a reasonable option for character-based OCR work because it provides script-based "language" options while other solutions are language-based. But when **Tesseract** was tried on a document in a central African language with a Latin-based script (Banda-Linda [liy]) it clearly struggled to properly identify less-common Latin script characters (e.g. ɓ, ɗ, ɛ, ə, ŋ, ɔ), as well as both those and more-common ones that were composed with various diacritics. Nevertheless, **Tesseract** is still able to properly identify *~95%* of the Banda-Linda characters using the "Latin" language option, i.e.:
```
tesseract -l Latin <image.png>
```

This was further tested on more than 10 other documents from the region that use some of the same "special" characters and diacritics. Details of those results can be found in [data/example-documents](data/example-documents). In all cases the same kinds of characters as with Banda-Linda were improperly recognized.

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

OCR accuracy can be measured in a few different ways. Here the focus will be on:
1. total number of recognized characters
1. number of mis-recognized characters (i.e. wrong character was recognized)
1. number of missing characters (i.e. character was left out of results)
1. number of extra characters (i.e. character was added to results)

Ideally, this solution will prove to be **98%-99%** accurate.
*Further reading: http://www.dlib.org/dlib/march09/holley/03holley.html*

### Character set

The new script model, "Latin_afr", will be based on "Latin", then be given training data using the following vowels, consonants, and diacritics:
- vowels: a, e, i, o, u, ɛ, ə, ı, ɨ, ɔ, ʉ
- consonants: ɓ, ɗ, ŋ
- diacritics:
  - \u0300, combining grave accent
  - \u0301, combining acute accent
  - \u0302, combining circumflex
  - \u0303, combining tilde
  - \u0308, combining diaeresis
  - \u0327, combining cedilla
