#!/usr/bin/env bash

pgrep -af '.*scripts/generate.*' | cut -d' ' -f3-
pgrep -af '.*scripts/run-training.*' | cut -d' ' -f3-
echo -n 'PNG: '
find ~/ocr/data/training/Latin_afr-ground-truth/ -type f | grep \.png | wc -l
echo -n 'BOX: '
find ~/ocr/data/training/Latin_afr-ground-truth/ -type f | grep \.box | wc -l
echo -n 'LSTMF: '
find ~/ocr/data/training/Latin_afr-ground-truth/ -type f | grep \.lstmf | wc -l
