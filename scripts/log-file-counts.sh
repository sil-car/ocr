#!/usr/bin/env bash

pgrep -af '.*scripts/generate.*' | cut -d' ' -f3-
pgrep -af '.*scripts/run-training.*' | cut -d' ' -f3-
tempfile=/tmp/generated-files.txt
find ~/ocr/data/training/Latin_afr-ground-truth/ -type f > "$tempfile"
echo -n 'PNG: '
grep \.png "$tempfile" | wc -l
echo -n 'BOX: '
grep \.box "$tempfile" | wc -l
echo -n 'LSTMF: '
grep \.lstmf "$tempfile" | wc -l
