import importlib.util
from pathlib import Path
import sys


folder = Path(__file__).resolve().parent
sys.path.insert(0, str(folder.parent / "nvidia75-aider-dispatch-v34-20261125"))
spec = importlib.util.spec_from_file_location("minimax_onecase_existing_lane", folder / "run_lane_owner.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.__file__ = str(folder / "run_lane.py")
module.main()
