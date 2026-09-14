# Training Regime Recommendations

Notes compiled for future work on `Latin_afr.traineddata`, based on a review of
`README.md`, `Training.md`, and `Evaluation.md` as of the current baseline
(stock `Latin` model CER ≈ 10.2%, score 839). Goal: reduce real-world CER
below the current best `Latin_afr` result.

## 0. Diagnose before changing the training regime

The overtraining heuristic already in use (eval CER / train BCER > 1 and
rising) is itself evidence of a synthetic-to-real domain gap — the model
fits generated data better than it fits reality. Before changing training
parameters, get a **character-level confusion matrix** from the real-eval
runs (`jiwer` can produce this, or a short script diffing predictions
against ground truth per character).

Two different underlying problems can produce the same aggregate CER, and
they call for different fixes:

- A handful of high-frequency confusion pairs (e.g. the documented
  i+grave / dotless-i+grave / i+macron-grave confusion) dominate the
  error → targeted fix.
- Errors are diffuse and spread across many characters → the model
  genuinely lacks coverage → needs more/better training data.

Recommendation: spend an hour confirming which regime we're in per test
document before prioritizing the items below.

## 1. Close the synthetic-to-real gap (highest expected impact)

- **Mix real data into training, not just evaluation.** A purely
  synthetic training set evaluated against real documents is the classic
  setup for exactly the BCER/CER divergence already being observed. Even
  a modest number of real, transcribed line images blended into training
  tends to close more of the gap than further synthetic tuning.
- **Bootstrap real training data cheaply.** Run the current best model
  on unlabeled real pages, manually correct the output, and feed the
  corrected line/ground-truth pairs back in as additional training data.
  Even a few hundred corrected real lines can help meaningfully.
- **Match degradations to the real capture conditions, not generic
  noise.** If real-world documents are typically phone photos of printed
  pages (fieldwork context) rather than flatbed scans, the dominant
  error sources are more likely perspective distortion, uneven
  lighting/shadow, moiré, and compression artifacts (e.g. from
  WhatsApp-forwarded images) than generic blur/fade/noise. Inspect actual
  failing real images and synthesize degradations that match what's
  actually happening, rather than a generic degradation suite.

## 2. Cheap, model-independent experiments to try first

- **Image preprocessing before OCR.** `Evaluation.md` explicitly notes
  evaluation has been done without any preprocessing (contrast
  normalization, deskew, adaptive binarization). This is close to a
  zero-cost experiment: re-run the existing best model on the same eval
  set after a basic preprocessing pass (deskew + adaptive threshold +
  denoise) and measure the CER shift before retraining anything.
- **Character whitelisting / per-language scoping.** Also flagged as
  untested in `Evaluation.md`. Since the target language for a given
  document/run is often known in advance, restricting the recognizer to
  that language's actual character inventory eliminates whole classes of
  cross-language confusion for free. This is a natural fit with the
  project's stated Goal #2 (narrowing OCR scope by a language's specific
  character set) and can be done as a config/post-processing step
  without retraining.

## 3. Training data and unicharset hygiene

- **Unicode normalization consistency.** `Training.md` lists "explicitly
  define the unicharset to remove composed characters" as an untested
  factor — prioritize this. If training data, ground truth, and font
  rendering aren't all enforced to one normalization form (NFC vs. NFD),
  the same visual glyph can end up mapped to different label sequences,
  which no amount of training can resolve. The documented i+grave
  confusion looks like a strong candidate for this: it may be a font
  rendering inconsistency (e.g. inconsistent dotless-i handling under a
  composed diacritic across fonts) rather than a data-volume problem.
  Audit that specific sequence across the font list before assuming more
  training data will fix it; consider dropping or fixing offending
  fonts.
- **Derive character/digraph frequency from real corpus text where
  possible**, rather than the current pseudo-word CVCV heuristic. If any
  digitized real-language text exists (e.g. scripture translations,
  often the largest available text source for these languages), use it
  to derive realistic character and digraph n-gram frequencies —
  especially for multi-letter digraphs that function as single phonemes
  (kp, gb, mb, mv, nd, ng, ngb, nz) and for realistic diacritic
  placement patterns, which are likely more systematic in real
  orthographies than "rarely on consonants, occasionally on vowels."

## 4. Model architecture / scoping

- **Per-language or per-character-subset models instead of one omnibus
  model.** Layer replacement already outperforms fine-tuning, and larger
  top layers already help (at a compute cost). An alternative to scaling
  the top layer further: train several smaller models scoped to a
  narrower character subset (grouped by which languages/orthographies
  co-occur), and route by known target language. A smaller hypothesis
  space per model may yield a bigger CER improvement than one model
  disambiguating the full extended character set at once.

## 5. Post-processing / correction layer

- **Add a lightweight correction pass.** Since the LSTM here is a pure
  visual recognizer, systematic single-character substitution errors
  (like i+grave) are often cheaper to fix with a small character-level
  or word-level n-gram language model / dictionary pass over known
  target-language text than to solve purely visually. Tesseract's own
  dictionary/wordlist features are untried per `Evaluation.md` and are a
  reasonable next experiment given the likely effort/payoff ratio.

## Suggested next-session checklist

- [ ] Generate a character-level confusion matrix per test document
- [ ] Determine whether errors are concentrated (few pairs) or diffuse
- [ ] Re-run best existing model on eval set with basic image
      preprocessing (deskew, adaptive threshold, denoise) — no retraining
- [ ] Audit i+grave (and similar) rendering across the font list for
      normalization/composition inconsistencies
- [ ] Identify any real transcribed text available for training (not
      just eval), or bootstrap a small corrected real dataset
- [ ] Try Tesseract character whitelisting for a known target language
- [ ] If real corpus text exists, recompute character/digraph
      frequencies from it and compare to current pseudo-word generation
