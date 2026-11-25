import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import shlex
import sys


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    root, folder = Path.cwd(), Path(__file__).parent.resolve()
    parent = folder.parent / "frozen/plan.json"
    plan = read(parent)
    for name, expected in plan["all_files_sha256"].items():
        if sha(root / name) != expected:
            raise ValueError("The retired Unicode configuration source changed: " + name)
    runtime = (root / plan["runtime_root"]).resolve()
    sys.path.insert(0, str(runtime))
    os.environ.setdefault("MSWEA_GLOBAL_CONFIG_DIR", str(root / "work/miniswe-config"))
    os.environ.setdefault("MSWEA_SILENT_STARTUP", "1")
    from course_eval import agent, benchmarks, controller, docker_target, verification

    loaded = {}
    for module in (agent, benchmarks, controller, docker_target, verification):
        path = Path(module.__file__).resolve()
        name = str(path.relative_to(root))
        if not path.is_relative_to(runtime) or sha(path) != plan["all_files_sha256"][name]:
            raise ValueError("The actual C0 qualification loaded another runtime")
        loaded[name] = sha(path)
    checks = read(root / plan["checks"])
    before = copy.deepcopy(checks)
    item, = checks[plan["task"]]
    old_command = item["command"]
    tokens = shlex.split(old_command)
    if tokens[-2] != "-c":
        raise ValueError("The recorded broken check does not use the expected Python argument boundary")
    program = tokens[-1]
    suffix = " && /opt/miniconda3/envs/testbed/bin/python -c " + shlex.quote(program)
    if not old_command.endswith(suffix) or program.isascii():
        raise ValueError("The exact demonstrated non-ASCII argv could not be isolated")
    encoded = base64.b64encode(program.encode("utf-8")).decode("ascii")
    stub = "import base64;exec(compile(base64.b64decode(" + repr(encoded) + ").decode('utf-8'),'<course-public-json-contract>','exec'))"
    item["command"] = old_command[:-len(suffix)] + " && /opt/miniconda3/envs/testbed/bin/python -c " + shlex.quote(stub)
    if not item["command"].isascii() or base64.b64decode(encoded).decode("utf-8") != program:
        raise ValueError("ASCII transmission changed the registered public program bytes")
    for task_id in checks:
        if task_id != plan["task"] and checks[task_id] != before[task_id]:
            raise ValueError("Another task's public check changed")
    first = root / plan["queue"] / (plan["task"] + "-C0-json-oracle-guided-main-r5")
    result = read(first / "result.json")
    if result["scoreable"] is not True or result["passed"] is not True:
        raise ValueError("Retain the actual completed r5 original score")
    task, = read(root / plan["manifest"])["selected"]
    instruction = (first / "instruction.txt").read_text()
    check = verification.PublicCheck(**item)
    check.validate(instruction)
    destination = folder / "qualification"
    destination.mkdir()
    inputs = folder / "inputs"
    inputs.mkdir()
    (inputs / "checks.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2) + "\n")
    (inputs / "tasks.json").write_bytes((root / plan["manifest"]).read_bytes())
    limits = agent.RunLimits(**plan["limits"])
    variants = [("reference", folder.parents[1] / "expanded/separate-public-reference.patch"),
        ("known_wrong_r3", root / "work/vmshare/performance-json-contract-v2-20261125/django__django-13346-C0-json-contract-main-r3/candidate.patch"),
        ("actual_r5", first / "candidate.patch")]
    rows, old_failure = [], None
    source_scores = {str((first / "result.json").relative_to(root)): sha(first / "result.json")}
    for name, patch in variants:
        output = destination / name
        output.mkdir()
        options = benchmarks.swe_public_dependencies(task)
        options["read_only_mounts"] = options.get("read_only_mounts", ()) + benchmarks.runtime_mounts("linux/amd64")
        with docker_target.DockerTarget(task["image"], "/testbed", platform="linux/amd64", memory_mb=3072, cpus=2,
                read_only_empty_dirs=benchmarks.SWE_HIDDEN_CACHES, **options) as target:
            if target.image != plan["pin"]:
                raise ValueError("The exact C0 transmission qualification used another original pin")
            benchmarks.check_swe_checkout(task, target, output)
            environment = controller.ControlledEnvironment(target, output, limits, (check,),
                {"kind": "repository", "python": "/opt/miniconda3/envs/testbed/bin/python"}, controller.Budget(3600), False)
            target.upload_file(patch, "/qualification.patch")
            applied = target.exec("git apply --check /qualification.patch && git apply /qualification.patch", timeout=30)
            if applied["returncode"]:
                raise ValueError("An actual candidate could not be applied")
            if name == "reference":
                old_failure = target.exec(old_command, timeout=120)
                (output / "original-broken-command.json").write_text(json.dumps(old_failure, indent=2) + "\n")
                if old_failure["returncode"] == 0 or "surrogates not allowed" not in old_failure["stderr"]:
                    raise ValueError("The actual original container did not reproduce the recorded argv encoding defect")
            actual = environment.verify(check.check_id, "zero_model_exact_ascii_command_qualification")
            final = environment.finish("zero_model_exact_ascii_command_qualification")
            (output / "actual-verification.json").write_text(json.dumps(actual, indent=2) + "\n")
            if "surrogates not allowed" in actual["stderr"] or final["protected_unchanged"] is not True:
                raise ValueError("The corrected real controller command still fails its transport or protection")
            if name == "reference" and (actual["state"] != "passed" or final["valid_verification"] is not True):
                raise ValueError("The exact corrected registered check did not accept the mature reference")
            if name == "known_wrong_r3" and actual["state"] != "failed":
                raise ValueError("The corrected real check no longer rejects the demonstrated Boolean regression")
            rows.append({"variant": name, "patch_path": str(patch.relative_to(root)), "patch_sha256": sha(patch),
                "state": actual["state"], "returncode": actual["returncode"], "final": final,
                "actual_verification_sha256": sha(output / "actual-verification.json")})
    for name, expected in source_scores.items():
        if sha(root / name) != expected:
            raise ValueError("The actual r5 original score changed during zero-model diagnosis")
    proof = {"phase": "actual_original_c0_ascii_transport_qualified", "new_model_calls": 0, "original_grader_calls": 0,
        "driver_sha256": sha(Path(__file__)), "pin": plan["pin"], "actual_loaded_runtime_modules": loaded,
        "source_plan": str(parent.relative_to(root)), "source_plan_sha256": sha(parent),
        "original_broken_command_reproduced": old_failure["returncode"] != 0,
        "decoded_public_program_sha256": hashlib.sha256(program.encode()).hexdigest(),
        "corrected_command_is_ascii": True, "decoded_program_exactly_preserved": True,
        "new_checks_sha256": sha(inputs / "checks.json"), "new_tasks_sha256": sha(inputs / "tasks.json"),
        "source_original_scores_sha256": source_scores, "variants": rows,
        "scope": "Exact registered command, original locale and original C0 ControlledEnvironment, repository scope and 3072MiB/2CPU target. No model instantiated or original grader run. The existing r5 grade remains true; its public transport failure is retained separately."}
    (destination / "result.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"phase": proof["phase"], "new_model_calls": 0, "original_grader_calls": 0,
        "variants": [{"variant": row["variant"], "state": row["state"]} for row in rows]}), flush=True)


if __name__ == "__main__":
    main()
