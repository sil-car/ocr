# Testing

## Character Error Rates (CER)

Each model is tested on 15 images taken from documents produced in the central Africa region.
The documents are a mixture of generated PDFs (selectable text) and raster PDFs (image-based).

*Source images are found in [data/example-documents/](data/example-documents)\<iso\>_\<language\>/block.png*

Language     | ISO | # src chars | Latin  | 2022121409 (fine-tune)  | 202212178613 (replace layer)
:---         |:---:|---:         |---:    |---:                     |---:
Bhogoto      | bdt | 461         | 14.75% | 4.34%                   | 0.43%
French       | fra | 151         | 0.00%  | 3.31%                   | 0.00%
Kaansa       | gna | 369         | 12.47% | 6.78%                   | 6.78%
Zulgo-Gemzek | gnd | 391         | 3.84%  | 10.74%                  | 3.32%
Banda-Linda  | liy | 373         | 5.09%  | 1.61%                   | 2.68%
Ngbugu       | lnl | 568         | 9.33%  | 9.33%                   | 5.63%
Lobala       | loq | 202         | 6.44%  | 23.27%                  | 12.87%
Makaa        | mcp | 418         | 5.74%  | 1.91%                   | 2.15%
Mpyemo       | mcx | 323         | 12.69% | 0.00%                   | 0.00%
Merey        | meq | 328         | 4.57%  | 0.00%                   | 0.31%
Mbuko        | mqb | 374         | 1.60%  | 1.60%                   | 0.27%
Mandja       | mza | 339         | 11.80% | 0.88%                   | 1.77%
Luto         | ndy | 324         | 3.09%  | 0.31%                   | 0.62%
Ngbaka       | nga | 295         | 13.56% | 40.34%                  | 16.61%
Nzakara      | nzk | 465         | 7.96%  | 6.02%                   | 3.23%
count < 5%   |     |             | 5      | 9                       | 11
count < 2%   |     |             | 2      | 7                       | 7
