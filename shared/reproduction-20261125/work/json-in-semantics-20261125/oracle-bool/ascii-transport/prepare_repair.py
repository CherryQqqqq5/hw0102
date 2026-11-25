import base64
import copy
import hashlib
import json
from pathlib import Path
import shlex


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    root, folder = Path.cwd(), Path(__file__).parent.resolve()
    parent_path = folder.parent / "frozen/plan.json"
    previous = read(parent_path)
    for name, expected in previous["all_files_sha256"].items():
        if sha(root / name) != expected:
            raise ValueError("The retained previous configuration changed: " + name)
    proof_path = folder / "qualification/result.json"
    proof = read(proof_path)
    inputs = folder / "inputs"
    if (proof["phase"] != "actual_original_c0_ascii_transport_qualified" or proof["new_model_calls"] != 0
            or proof["original_grader_calls"] != 0 or proof["pin"] != previous["pin"]
            or proof["source_plan_sha256"] != sha(parent_path)
            or proof["driver_sha256"] != sha(folder / "qualify_transport.py")
            or proof["new_checks_sha256"] != sha(inputs / "checks.json")
            or proof["new_tasks_sha256"] != sha(inputs / "tasks.json")
            or proof["original_broken_command_reproduced"] is not True):
        raise ValueError("The exact registered C0 command qualification is incomplete or changed")
    for name, expected in proof["actual_loaded_runtime_modules"].items():
        if previous["all_files_sha256"][name] != expected or sha(root / name) != expected:
            raise ValueError("The actual C0 qualification loaded another frozen runtime")
    for name, expected in proof["source_original_scores_sha256"].items():
        if sha(root / name) != expected:
            raise ValueError("The naturally completed r5 original score changed")
    variants = {row["variant"]: row for row in proof["variants"]}
    if (set(variants) != {"reference", "known_wrong_r3", "actual_r5"}
            or variants["reference"]["state"] != "passed"
            or variants["reference"]["final"]["valid_verification"] is not True
            or variants["known_wrong_r3"]["state"] != "failed"
            or any(row["final"]["protected_unchanged"] is not True for row in variants.values())):
        raise ValueError("The actual positive and negative controller controls did not pass")
    for row in variants.values():
        if sha(root / row["patch_path"]) != row["patch_sha256"]:
            raise ValueError("A qualified actual candidate patch changed")
    old_checks, checks = read(root / previous["checks"]), read(inputs / "checks.json")
    expected = copy.deepcopy(old_checks)
    check, = expected[previous["task"]]
    old_command = check["command"]
    program = shlex.split(old_command)[-1]
    suffix = " && /opt/miniconda3/envs/testbed/bin/python -c " + shlex.quote(program)
    if not old_command.endswith(suffix) or hashlib.sha256(program.encode()).hexdigest() != proof["decoded_public_program_sha256"]:
        raise ValueError("The actual decoded public source differs from the previous registered program")
    encoded = base64.b64encode(program.encode()).decode("ascii")
    stub = "import base64;exec(compile(base64.b64decode(" + repr(encoded) + ").decode('utf-8'),'<course-public-json-contract>','exec'))"
    check["command"] = old_command[:-len(suffix)] + " && /opt/miniconda3/envs/testbed/bin/python -c " + shlex.quote(stub)
    if checks != expected or not check["command"].isascii():
        raise ValueError("Only the byte-exact ASCII transport may change")
    if (inputs / "tasks.json").read_bytes() != (root / previous["manifest"]).read_bytes():
        raise ValueError("The actual task input changed during transport repair")
    retirement = read(folder / "retirement.json")
    waiter = root / retirement["unstarted_second_run"]
    if (waiter.exists() or read(waiter.with_suffix(".resources.json")).get("admitted_at") is not None
            or retirement["second_new_model_calls"] != 0):
        raise ValueError("The retired second slot is no longer an unstarted zero-model position")
    destination = folder / "frozen"
    destination.mkdir()
    plan = copy.deepcopy(previous)
    plan.update({"stage": "frozen_after_exact_original_c0_ascii_transport_qualification",
        "manifest": str((inputs / "tasks.json").relative_to(root)),
        "checks": str((inputs / "checks.json").relative_to(root)),
        "queue": "work/vmshare/performance-json-oracle-ascii-v4-20261125",
        "prospective_trials": ["json-oracle-ascii-main-r7", "json-oracle-ascii-repeat-r8"],
        "main_variable": "Repair only the registered public program's transport to ASCII base64; decoded UTF-8 program and mature API guidance unchanged. The previous r5 original pass and failed public transport remain development evidence, never retroactively qualified.",
        "previous_retired_plan": str(parent_path.relative_to(root)),
        "exact_controller_qualification": str(proof_path.relative_to(root)),
        "decoded_public_program_sha256": proof["decoded_public_program_sha256"],
        "zero_model_retired_second_slot": str((folder / "retirement.json").relative_to(root)),
        "reporting": "Preserve original225, all five previous model-scored JSON sessions, the unstarted zero-model r6 slot, both final JSON and both final FEAL sessions and all three ablations. Joint acceptance inherits only unchanged73x2 plus4 fixed fresh final sessions. Expected237 model-scored positions including ablations; earlier SQL pilots and engineering grader calls remain separate."})
    paths = [parent_path, Path(__file__).resolve(), folder / "qualify_transport.py", folder / "retirement.json",
        folder / "qualification.resources.json", *inputs.glob("*.json"), *[path for path in (folder / "qualification").rglob("*")
            if path.is_file() and path.suffix in {".json", ".jsonl"}]]
    paths += [root / name for name in proof["source_original_scores_sha256"]]
    paths += [root / row["patch_path"] for row in variants.values()]
    plan["all_files_sha256"].update({str(path.relative_to(root)): sha(path) for path in paths})
    with (destination / "plan.json").open("x") as stream:
        stream.write(json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": "frozen", "new_model_calls": 0, "prospective_sessions": 2,
        "bound_files": len(plan["all_files_sha256"]), "exact_original_c0_controller_qualified": True}), flush=True)


if __name__ == "__main__":
    main()
