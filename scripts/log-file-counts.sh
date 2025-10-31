#!/usr/bin/env bash

ps -ef | grep -Eo 'python3.*/generate.*$' | head -n1
echo -n 'PNG:'
find ~/ocr/data/training/Latin_afr-ground-truth/ -name '*.png' | wc -l
echo -n 'BOX:'
find ~/ocr/data/training/Latin_afr-ground-truth/ -name '*.box' | wc -l
echo -n 'LSTMF:'
find ~/ocr/data/training/Latin_afr-ground-truth/ -name '*.lstmf' | wc -l
