#!/usr/bin/env python3
"""Prepare a .traineddata model for release.
 - create outfile "MODEL_NAME.traineddata"
 - set version (including network details) with MODEL_NAME.version
Also consider:
 - update (restrict) MODEL_NAME.lstm-unicharset (would affect all dawg files)?
 - update/remove punc MODEL_NAME.lstm-punc-dawg?
"""

# import argparse
import re
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

MODEL_NAME = "Latin_afr"
today = datetime.now(tz=UTC)
DEFAULT_DATESTAMP = today.strftime("%Y%m%d")


def get_unicharset_size(model_file):
    """Number of entries in the model's lstm-unicharset (what tesstrain puts in O1c###)."""
    with tempfile.TemporaryDirectory() as d:
        prefix = Path(d) / "model."
        subprocess.run(
            ("combine_tessdata", "-u", str(model_file), str(prefix)),
            capture_output=True,
            check=True,
        )
        unicharset = Path(f"{prefix}lstm-unicharset")
        return int(unicharset.read_text(encoding="utf-8").splitlines()[0])


def get_net_spec(model_file):
    """Effective network spec, e.g. "[1,48,0,1Ct3,3,16Mp3,3Lfys64Lfx96Lrx96Lfx512O1c426]".

    combine_tessdata -l shows the start model's spec, followed by "[...]" with the
    replacement layers if the top was replaced (--append_index). The start model's
    output size shows as O1c1, so the output size is taken from the unicharset.
    """
    stdout = subprocess.run(
        ("combine_tessdata", "-l", str(model_file)),
        capture_output=True,
        check=True,
    ).stdout.decode()
    m = re.search(r"network=(\[[^,]*(?:,[^,=]*)*\])(?:, |$)", stdout, re.MULTILINE)
    if not m:
        raise ValueError(f"no LSTM network found in {model_file}")
    groups = re.findall(r"\[([^\]]*)\]", m.group(1))
    base = groups[0].replace(" ", "")
    for added in groups[1:]:
        added = added.replace(" ", "")
        # Drop the output layer of the base; if the added part starts with a
        # new hidden layer, that layer replaced the base's top hidden layer.
        base = re.sub(r"O1c\d+$", "", base)
        if not added.startswith("O"):
            base = re.sub(r"L[a-z]+\d+$", "", base)
        base += added
    # Use the real output size (unicharset entries), as tesstrain does for O1c###.
    base = re.sub(r"O1c\d+$", f"O1c{get_unicharset_size(model_file)}", base)
    return f"[{base}]"


def get_version_string(model_file):
    stdout = subprocess.run(
        ("combine_tessdata", "-d", str(model_file)),
        capture_output=True,
        check=True,
    ).stdout.decode()
    for line in stdout.splitlines():
        if line.startswith("Version:"):
            # Keep only the Tesseract version, in case the model was released before.
            return line.split(":")[1]


def set_version_string(model_file, new_version_string):
    with tempfile.TemporaryDirectory() as d:
        tempdir = Path(d)
        version_file = tempdir / f"{MODEL_NAME}.version"
        version_file.write_text(new_version_string)
        subprocess.run(
            ("combine_tessdata", "-o", str(model_file), str(version_file)),
            capture_output=True,
            check=True,
        )


def set_version_info(model_file):
    """Released model version string: \"tessver:model_name:datestamp:net_spec\" """
    # Assume current version string is just tessver.
    return f"{get_version_string(model_file)}:{MODEL_NAME}:{get_datestamp(model_file)}:{get_net_spec(model_file)}"


def get_datestamp(model_file):
    """Last "_" part of the file name if it starts with a date (e.g. 20261015a2921); else today."""
    datestamp = model_file.stem.split("_")[-1]
    if not re.match(r"20\d{6}", datestamp):
        datestamp = DEFAULT_DATESTAMP
    return datestamp


def main():
    if len(sys.argv) < 2:
        print("ERROR: Need TRAINEDDATA file as argument")
        sys.exit(1)

    model_file = Path(sys.argv[1])
    if model_file.suffix != ".traineddata":
        # TODO: 1st 4 bytes should also be: \x18 \x00 \x00 \x00
        print(f"ERROR: Invalid file type: {model_file}")
        sys.exit(1)
    elif not model_file.is_file():
        print(f"ERROR: File does not exist: {model_file}")
        sys.exit(1)

    # Use a tempfile in the output folder (so the rename can't cross file
    # systems); move into place when ready.
    outfile_path = Path.cwd() / f"{MODEL_NAME}.traineddata"
    version_info = set_version_info(model_file)
    with tempfile.NamedTemporaryFile(
        dir=outfile_path.parent, suffix=".traineddata", delete=False
    ) as t:
        temp_outfile = Path(t.name)
    try:
        temp_outfile.write_bytes(model_file.read_bytes())
        set_version_string(temp_outfile, version_info)
        temp_outfile.replace(outfile_path)
    except BaseException:
        temp_outfile.unlink(missing_ok=True)
        raise
    print(f"Version: {version_info}")

    # Show file name at completion.
    print(outfile_path)


if __name__ == "__main__":
    main()
