import argparse
import hashlib
import json
import os
import runpy
import shlex
from pathlib import Path

import numpy as np

from course_eval.controller import Budget, BoundedTarget, CandidateStore
from course_eval.docker_target import DockerTarget
from course_eval.terminal_runtime import RELU_HELPER_PATH, prepare_public_runtime, reusable_helper_instructions
from check_relu_recovery import direction_match


PROBE = '''import json
import sys
import numpy as np
sys.path.insert(0, "/opt/course-tools")
from relu_recovery import recover_relu_directions
from forward import forward
rows, trace = recover_relu_directions(forward, 10)
np.save("/app/stolen_A1.npy", rows)
print(json.dumps({"rows": rows.tolist(), "trace": trace, "numpy_version": np.__version__}))
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--public-forward", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    root = Path.cwd()
    os.environ.update(DOCKER_HOST="unix://" + str(root / "work/v/c/sock/docker.sock"),
                      DOCKER_CONFIG=str(root / "work/docker-config"),
                      COURSE_DOCKER_BIN=str(root / "work/vendor/docker/docker"))
    public = args.public_forward.resolve(strict=True)
    expected = runpy.run_path(str(public))["A1"]
    scope = {"kind": "files", "python": "/opt/miniconda3/envs/testbed/bin/python",
             "artifacts": ["/app/stolen_A1.npy"],
             "protected": ["/app/forward.py", RELU_HELPER_PATH], "reusable_helper": "relu_directions"}
    with DockerTarget(args.image, "/app", platform="linux/amd64", memory_mb=1024, cpus=1,
                      read_only_empty_dirs=("/tests",)) as target:
        unchanged = prepare_public_runtime(target, {"python": scope["python"]}) is None
        target.upload_file(public, "/app/forward.py")
        runtime = prepare_public_runtime(target, scope)
        budget = Budget(120)
        store = CandidateStore(BoundedTarget(target, budget), args.out, scope, budget)
        output = target.exec(scope["python"] + " -c " + shlex.quote(PROBE), timeout=60)
        if output["returncode"]:
            raise RuntimeError(output)
        actual = json.loads(output["stdout"])
        rows = np.asarray(actual.pop("rows"))
        match = direction_match(rows, expected)
        protected_before = store.trusted(store.capture())
        modified = target.exec("printf '\\n' >> " + RELU_HELPER_PATH, timeout=10)
        if modified["returncode"]:
            raise RuntimeError(modified)
        protected_change_rejected = not store.trusted(store.capture())
        result = {"source": "Publicly supplied forward.py prototype only; public A1 is used solely by this numerical control",
                  "source_sha256": hashlib.sha256(public.read_bytes()).hexdigest(),
                  "image_id": target.image, "runtime": runtime, "computation": actual,
                  "direction_match": match, "normal_no_helper_scope_unchanged": unchanged,
                  "helper_description_present": RELU_HELPER_PATH in reusable_helper_instructions(scope),
                  "protected_inputs_unchanged_after_computation": protected_before,
                  "changed_helper_rejected": protected_change_rejected,
                  "new_model_calls": 0, "original_grader_calls": 0,
                  "interpretation": "Actual sandbox upload, query-only computation and candidate protection validation; no agent adoption or hidden-task success"}
        result["passed"] = (match["passed"] and unchanged and protected_before and protected_change_rejected
                            and result["helper_description_present"])
    (args.out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False))
    if not result["passed"]:
        raise AssertionError("Actual reusable-runtime integration did not satisfy its fixed controls")


if __name__ == "__main__":
    main()
