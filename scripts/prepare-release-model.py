#!/usr/bin/env python3
"""Prepare a .traineddata model for release.
 - create outfile "MODEL_NAME.traineddata"
 - set version (including network details) with MODEL_NAME.version
Also consider:
 - update (restrict) MODEL_NAME.lstm-unicharset (would affect all dawg files)?
 - update/remove punc MODEL_NAME.lstm-punc-dawg?
"""

# import argparse
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

MODEL_NAME = "Latin_afr"
today = datetime.today()
DEFAULT_DATESTAMP = f"{today.year}{today.month}{today.day}"


def get_net_spec(model_file):
    stdout = subprocess.run(
        ("combine_tessdata", "-l", str(model_file)), capture_output=True
    ).stdout.decode()
    for line in stdout.splitlines():
        if line.startswith("LSTM"):
            line = line.lstrip("LSTM: ")
            properties = line.split(", ")
            lstm = {}
            for property in properties:
                k, v = property.split("=")
                lstm[k] = v
            network = lstm.get("network")
            break
    old, new = network.split("][")
    return f"{old.rstrip('Lfx512O1c1')}{new.replace(' ', '')}"


def get_version_string(model_file):
    stdout = subprocess.run(
        ("combine_tessdata", "-d", str(model_file)),
        capture_output=True,
    ).stdout.decode()
    for line in stdout.splitlines():
        if line.startswith("Version:"):
            return ":".join(line.split(":")[1:])


def set_version_string(model_file, new_version_string):
    with tempfile.TemporaryDirectory() as d:
        tempdir = Path(d)
        version_file = tempdir / f"{MODEL_NAME}.version"
        version_file.write_text(new_version_string)
        subprocess.check_output(
            (
                "combine_tessdata",
                "-o",
                str(model_file),
                str(version_file),
            ),
        )


def set_version_info(model_file):
    """Released model version string: \"tessver:model_name:datestamp:net_spec\" """
    # Assume current version string is just tessver.
    return f"{get_version_string(model_file)}:{MODEL_NAME}:{get_datestamp(model_file)}:{get_net_spec(model_file)}"


def get_datestamp(model_file):
    """Relies on the date and CER value being part of the filename; falls back to today"""
    datestamp = model_file.stem.split("_")[-1]
    # Ensure that datestamp is valid.
    if int(datestamp[0]) not in range(10):
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

    # Use a tempfile; move into place when ready.
    outfile_path = Path.cwd() / f"{MODEL_NAME}.traineddata"
    with tempfile.NamedTemporaryFile(delete=False) as t:
        temp_outfile = Path(t.name)
        # Copy model data to tempfile.
        temp_outfile.write_bytes(model_file.read_bytes())
        # Set tempfile version.
        set_version_string(temp_outfile, set_version_info(model_file))
        # Move tempfile to outfile location
        temp_outfile.rename(outfile_path)

    # Show file name at completion.
    print(outfile_path)


if __name__ == "__main__":
    main()
