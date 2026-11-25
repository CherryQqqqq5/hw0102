import importlib.util
from pathlib import Path
import sys


folder = Path(__file__).resolve().parent
parent = folder.parent / "nvidia75-transport-v28-20261125"
sys.path.insert(0, str(parent))
spec = importlib.util.spec_from_file_location("unchanged_nvidia_v28_lane", parent / "run_lane.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.__file__ = str(folder / "run_lane.py")
module.main()
