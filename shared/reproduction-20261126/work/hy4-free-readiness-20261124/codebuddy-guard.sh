#!/bin/sh
entry_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec "$entry_dir/../.venv/bin/python" "$entry_dir/request_guard.py" "$@"
