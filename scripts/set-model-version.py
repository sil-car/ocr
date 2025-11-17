#!/usr/bin/env python3
"""Append version and network details to Latin_afr*.traineddata file."""

import subprocess
import sys
from datetime import datetime
from pathlib import Path

MODEL_NAME = "Latin_afr"
today = datetime.today()
DATESTAMP = f"{today.year}{today.month}{today.day}"


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
    if not isinstance(model_file, Path):
        model_file = Path(model_file)
    return model_file.read_bytes().split(b"\x01\x00\x00")[-1].decode()


def set_version_string(model_file, new_version_string):
    if not isinstance(model_file, Path):
        model_file = Path(model_file)
    with model_file.open("r+b") as f:
        # Seek in file to just before current version info & remove it.
        f.seek(-len(get_version_string(model_file)), 2)
        f.truncate()
        # Write new version info bytes to file.
        f.write(new_version_string.encode())


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

    current_version_str = get_version_string(model_file)
    net_spec = get_net_spec(model_file)
    version = f"{MODEL_NAME}:{DATESTAMP}:{net_spec}"
    current_version = current_version_str.split(":")
    tess_version = current_version[0]
    if current_version[1:] != version.split(":"):
        new_version_string = f"{tess_version}:{version}"
        set_version_string(model_file, new_version_string)
        print(f"Updated version string to: {new_version_string}")


if __name__ == "__main__":
    main()
