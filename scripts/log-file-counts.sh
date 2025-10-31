#!/usr/bin/env bash

pgrep -af '.*scripts/generate.*' | cut -d' ' -f3-
pgrep -af '.*scripts/run-training.*' | cut -d' ' -f3-
echo -n 'PNG: '
find ~/ocr/data/training/Latin_afr-ground-truth/ -name '*.png' | wc -l
echo -n 'BOX: '
find ~/ocr/data/training/Latin_afr-ground-truth/ -name '*.box' | wc -l
echo -n 'LSTMF: '
find ~/ocr/data/training/Latin_afr-ground-truth/ -name '*.lstmf' | wc -l
