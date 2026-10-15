# Releasing a model

A release is a git tag plus a GitHub release with `Latin_afr.traineddata` attached. The README links to the latest release, so the attached file must keep that exact name.

## 1. Choose the model

- Evaluate the candidate checkpoints (see [Evaluation.md](Evaluation.md)) and pick the one with the lowest pmCER.
- Before deciding, check the per-language CERs against `Latin` and the previous release. Note any language that is worse; mention it in the release notes.
- The model must be a float model (`combine_tessdata -l MODEL` shows `int_mode=0`).

## 2. Prepare the release file

Run `prepare-release-model.py` from the folder where the release file should be written. It writes `Latin_afr.traineddata` to the current folder and sets its version string to `TESSVER:Latin_afr:DATESTAMP:NET_SPEC`, with the datestamp taken from the model's file name.

```bash
cd tessdata
../scripts/prepare-release-model.py Latin_afr_20261015a2921.traineddata
combine_tessdata -d Latin_afr.traineddata | head -1   # check the version string
tesseract ../data/representative-languages/ags_esimbi/evaluation/primer-pg10a.png - --tessdata-dir . -l Latin_afr --psm 4
```

`tessdata/Latin_afr.traineddata` is not committed; it only goes into the GitHub release.

## 3. Update the charts and docs

```bash
./scripts/show-chart.py -t best    # data/evaluation/best-model-perf-by-lang.png
./scripts/show-chart.py -t comp    # data/evaluation/comp-Latin-<best model>.png
cp data/evaluation/comp-Latin-Latin_afr_20261015a2921.png data/evaluation/comp-Latin-Latin_afr.png
```

The README shows `comp-Latin-Latin_afr.png`, so the comparison chart has to be renamed. Update Evaluation.md and the README if anything they say about the current model has changed. Commit and push.

## 4. Tag and publish

Tag the commit with the release date and push the tag:

```bash
git tag 20261015
git push origin 20261015
```

Then create the release on GitHub from that tag (Releases → Draft a new release) and attach `tessdata/Latin_afr.traineddata`. With the GitHub CLI:

```bash
gh release create 20261015 tessdata/Latin_afr.traineddata --title "Latin_afr 20261015" --notes-file notes.md
```

Release notes should include:

- the source model (e.g. `Latin_afr_20261015a2921`) and its version string;
- how it was trained (start model, real/synthetic share, `-m`, iterations at the chosen checkpoint);
- pmCER and per-language CER compared with `Latin` and the previous release, including any regressions.

## 5. Check

Open https://github.com/sil-car/ocr/releases/latest and confirm the new release is marked "Latest" and the download link in the README works.
