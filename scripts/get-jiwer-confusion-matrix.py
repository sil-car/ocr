"""Output misidentified characters in order of frequency."""

from pathlib import Path

import jiwer

# references and hypotheses must be line-aligned: same order, same count
references = []  # ground-truth text, one string per line
hypotheses = []  # Tesseract output, one string per line
for d in Path("./data/example-documents").iterdir():
    ref = []
    hyp = []
    if not d.is_dir():
        continue
    for f in d.iterdir():
        if f.name == "orig-text.txt":
            ref = f.read_text().splitlines()
        elif f.name == "ocr-text.txt":
            hyp = f.read_text().splitlines()
        if ref and hyp:
            break

    if len(ref) == len(hyp):
        references.extend(ref)
        hypotheses.extend(hyp)

out = jiwer.process_characters(references, hypotheses)

# substitutions: {(ref_char, hyp_char): count}
# insertions:    {hyp_char: count}   -- char OCR produced that isn't in the ground truth
# deletions:     {ref_char: count}   -- ground-truth char OCR failed to produce
substitutions, insertions, deletions = jiwer.collect_error_counts(out)

# quick human-readable view, sorted by frequency
print(jiwer.visualize_error_counts(out, top_k=30))
