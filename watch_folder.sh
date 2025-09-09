#!/usr/bin/env sh
# Wrapper to run the folder watcher using the system's python interpreter
python "$(dirname "$0")/watch_folder.py" "$@"
