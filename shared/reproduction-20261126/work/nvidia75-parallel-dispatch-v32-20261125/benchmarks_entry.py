import hashlib
import importlib.util
import json
import os
from pathlib import Path
import runpy
import sys


runtime = Path(__file__).resolve().parents[1] / "frozen-performance-free-v31"
sys.path.insert(0, str(runtime))
os.environ["PYTHONPATH"] = str(runtime)
sources = {}
for name in ("benchmarks", "agent", "controller", "financial_stop", "openrouter_free", "nvidia_free"):
    source = Path(importlib.util.find_spec("course_eval." + name).origin).resolve()
    if source != runtime / "course_eval" / (name + ".py"):
        raise RuntimeError("The actual task would load an unintended runtime module")
    sources[name] = {"path": str(source), "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
if sys.argv[1:] == ["--import-proof"]:
    print(json.dumps({"actual_module_resolution": sources, "new_model_calls": 0}))
    raise SystemExit(0)
runpy.run_module("course_eval.benchmarks", run_name="__main__")
