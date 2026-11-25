import json
import os
import sys
from pathlib import Path


root = Path(__file__).resolve().parents[2]
stop = json.loads((root / "work/performance-stop-20261122.json").read_text())
if stop["active"]:
    raise SystemExit("No new model request: the shared actual financial stop is active")
cli = root / "work/codebuddy/node_modules/.bin/codebuddy"
os.execv(str(cli), [str(cli), *sys.argv[1:]])
