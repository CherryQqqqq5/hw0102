import argparse
from pathlib import Path

from course_eval.benchmarks import write_json
from course_eval.docker_target import DockerTarget
from course_eval.inventory import REVISIONS


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--python-test-packages", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    task = "openssl-selfsigned-cert"
    original = args.sources / f"terminal-bench-2-1-{REVISIONS['terminal']}" / "tasks" / task
    image = "alexgshaw/openssl-selfsigned-cert:20251031"
    for kind in ("starter", "oracle"):
        with DockerTarget(image, "/app", platform="linux/amd64", memory_mb=2048, cpus=1) as target:
            target.docker("cp", str(args.python_test_packages), f"{target.container}:/preflight-deps")
            target.docker("cp", str(original / "tests/test_outputs.py"), f"{target.container}:/test_outputs.py")
            if kind == "oracle":
                target.docker("cp", str(original / "solution/solve.sh"), f"{target.container}:/solve.sh")
                oracle = target.exec("bash /solve.sh", timeout=90)
                write_json(args.out / "oracle.json", oracle)
                if oracle["returncode"]:
                    raise RuntimeError("The original reference script failed")
            output = target.exec("PYTHONPATH=/preflight-deps python -m pytest /test_outputs.py -rA", timeout=120)
            write_json(args.out / f"{kind}-pytest.json", output)
            expected = 0 if kind == "oracle" else 1
            if output["returncode"] != expected:
                raise RuntimeError(f"Unexpected pytest status for {kind}: {output['returncode']}")
    write_json(args.out / "result.json", {"task": task, "check": "original_test_assertions",
                                          "starter_exit_code": 1, "reference_exit_code": 0,
                                          "official_harbor_trial": False, "model_requests": 0})


if __name__ == "__main__":
    main()
