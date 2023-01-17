# Testing

Each tesseract language model is used to OCR the same set of 15 sample images.
The 15 images are taken from documents produced in the central Africa region, which are a mixture of generated PDFs (selectable text) and raster PDFs (image-based).
The results are evaluated manually and the Character Error Rate is calculated.

A summary showing the results of three particular models is given below. The models are:
1. The original Latin model produced by Tesseract.
1. The best "fine tuning" model I could come up with using Tesseract training.
1. The best "replace layer" model I could produce.

***Fine tuning*** involves giving additional training data to an existing model.
***Replacing a layer*** involves also rebuilding part of an existing model to make it better fit the new data, at the cost of additional computational effort and time.

## Character Error Rates (CER), by inspection**

Language     | ISO | # src chars | Latin  | 2022121409 (fine-tune)  | 20221219 (replace layer)
:---         |:---:|---:         |---:    |---:                     |---:
Bhogoto      | bdt | 461         | 14.75% | 4.34%                   | 1.52%
French       | fra | 151         | 0.00%  | 3.31%                   | 0.00%
Kaansa       | gna | 369         | 12.47% | 6.78%                   | 7.05%
Zulgo-Gemzek | gnd | 391         | 3.84%  | 10.74%                  | 2.81%
Banda-Linda  | liy | 371         | 5.09%  | 1.61%                   | 1.62%
Ngbugu       | lnl | 528         | 9.33%  | 9.33%                   | 7.39%
Lobala       | loq | 202         | 6.44%  | 23.27%                  | 9.90%
Makaa        | mcp | 418         | 5.74%  | 1.91%                   | 2.15%
Mpyemo       | mcx | 323         | 12.69% | 0.00%                   | 0.00%
Merey        | meq | 328         | 4.57%  | 0.00%                   | 0.61%
Mbuko        | mqb | 374         | 1.60%  | 1.60%                   | 0.27%
Mandja       | mza | 339         | 11.80% | 0.88%                   | 2.36%
Luto         | ndy | 324         | 3.09%  | 0.31%                   | 0.62%
Ngbaka       | nga | 295         | 13.56% | 40.34%                  | 19.32%
Nzakara      | nzk | 465         | 7.96%  | 6.02%                   | 4.52%
             |     |             |        |                         |
average CER  |     |             | 7.58%  | 7.39%                   | 4.01%
standard dev.|     |             | 4.69%  | 10.97%                  | 5.20%
count < 5%   |     |             | 5      | 9                       | 11
count < 2%   |     |             | 2      | 7                       | 7

*Source images are found in [data/example-documents/](data/example-documents)\<iso\>_\<language\>/block.png*

> NOTE: This testing has been done without any image preprocessing (e.g. increasing contrast to remove specks that could be confused for characters). It has also not made use of tesseract's character blacklist or whitelist features, which in some cases would significantly reduce substitution and/or insertion errors.
> NOTE 2: The values uses to calculate the CER were determined by visual inspection. This will soon be reevaluated using a machine inspection. It has already been recognized that tesseract has preferred composed characters over decomposed characters. This needs to be fixed.
