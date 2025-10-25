#!/usr/bin/env bash

log_file="$(find "$HOME"/tesstrain/data -name 'Latin_afr_*.log' | sort | tail -n1)"
grep "New best" "$log_file" | tail -n1
grep "New worst" "$log_file" | tail -n1
grep -Ev -e "^Iteration" -e "^File" "$log_file" | tail -n12
