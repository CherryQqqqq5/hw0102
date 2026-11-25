import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    root, folder = Path.cwd(), Path(__file__).resolve().parent
    parent = root / "work/free-recovery34-20261125/hy4-plans"
    output = folder / "plans"
    if output.exists():
        raise FileExistsError("Keep each prospective plan preparation immutable")
    driver = folder / "image_copy_driver.py"
    driver_name = str(driver.relative_to(root))
    output.mkdir()
    for name in ("tasks.json", "checks.json", "scopes.json"):
        shutil.copyfile(parent / name, output / name)
    prepared, preserved = {}, {}
    for arm in ("main", "repeat"):
        original_path = parent / (arm + "-plan.json")
        original = read(original_path)
        plan = copy.deepcopy(original)
        plan["image_copy_driver"] = driver_name
        plan["image_preparation_sha256"][driver_name] = digest(driver)
        changed = sorted(key for key in plan.keys() | original.keys() if plan.get(key) != original.get(key))
        if changed != ["image_copy_driver", "image_preparation_sha256"]:
            raise ValueError("Only the original image preparation child route may change")
        path = output / (arm + "-plan.json")
        path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
        actual = subprocess.run([sys.executable, str(root / plan["coordinator_path"]), "--plan", str(path),
            "--queue-dir", str(root / plan["queue"]), "--validate-only"],
            env=os.environ | {"PYTHONPATH": str(root)}, capture_output=True, text=True, check=True)
        prepared[arm] = {"path": str(path.relative_to(root)), "sha256": digest(path),
            "parent": str(original_path.relative_to(root)), "parent_sha256": digest(original_path),
            "changed_fields": changed, "actual_validation": json.loads(actual.stdout)}
        state = read(root / plan["queue"] / "state.json")
        for row in state["policy_results"] + state["baseline_results"]:
            result = (root / row["run_dir"]) / "result.json"
            preserved[str(result.relative_to(root))] = digest(result)
    proof = {"stage": "prospective_admin_preparation_plans_only_not_started", "phase": "DEBUG",
        "plans": prepared, "driver": driver_name, "driver_sha256": digest(driver),
        "preparer_sha256": digest(Path(__file__)), "preserved_closed_original_results": preserved,
        "new_model_calls": 0, "new_original_grader_calls": 0, "STOP_modified": False,
        "scope": "Original75/tasks/checks/scopes/runtime/model/budget/graders/billing guards and semantic failures unchanged;only public registry child CDN route changes. Do not dispatch until each preceding same-queue actor has naturally ended or a separately verified zero-model handoff is recorded."}
    (folder / "prepared.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"stage": proof["stage"], "plans": prepared,
        "closed_results_retained": len(preserved), "new_model_calls": 0}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
