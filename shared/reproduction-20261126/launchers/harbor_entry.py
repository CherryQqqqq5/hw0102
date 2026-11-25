import sys
from pathlib import Path
from runpy import run_path

from harbor.cli.main import app


if __name__ == "__main__":
    capture = next((parent / "scripts/harbor_artifact_capture.py" for parent in Path(__file__).resolve().parents
        if (parent / "scripts/harbor_artifact_capture.py").is_file()), None)
    if capture is None:
        raise RuntimeError("The explicit local artifact collector is missing")
    sys.argv = run_path(str(capture))["prepare_args"](sys.argv)
    if sys.argv[0].endswith("-script.pyw"):
        sys.argv[0] = sys.argv[0][:-11]
    elif sys.argv[0].endswith(".exe"):
        sys.argv[0] = sys.argv[0][:-4]
    sys.exit(app())
