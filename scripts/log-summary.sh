#!/usr/bin/env bash

log_files=$(find "$HOME"/tesstrain/data -name 'Latin_afr_*.log')
grep -h "New best" "$log_files" | tail -n1
grep -h "New worst" "$log_files" | tail -n1
grep -hEv -e "^Iteration" -e "^File" "$log_files" | tail -n12
