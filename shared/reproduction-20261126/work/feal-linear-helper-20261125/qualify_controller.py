import hashlib
import json
import os
from pathlib import Path
import shlex
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "work/frozen-performance-hy4-feal-linear-v19"))
os.environ.setdefault("MSWEA_GLOBAL_CONFIG_DIR", str(Path(__file__).resolve().parents[2] / "work/miniswe-config"))
os.environ.setdefault("MSWEA_SILENT_STARTUP", "1")

from course_eval.agent import RunLimits
from course_eval.controller import Budget, ControlledEnvironment
from course_eval.docker_target import DockerTarget
from course_eval.terminal_runtime import prepare_public_runtime
from course_eval.verification import PublicCheck


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    root, folder = Path.cwd(), Path(__file__).parent.resolve()
    inputs = folder / "readmission-inputs"
    plan = read(folder / "frozen/plan.json")
    runtime = root / plan["runtime_root"]
    actual_modules = {name: Path(sys.modules[obj.__module__].__file__).resolve() for name, obj in
        (("agent", RunLimits), ("controller", ControlledEnvironment), ("verification", PublicCheck),
         ("terminal_runtime", prepare_public_runtime))}
    actual_modules["candidate_io_source"] = actual_modules["controller"].with_name("candidate_io.py")
    loaded = {}
    for name, path in actual_modules.items():
        if not path.is_relative_to(runtime.resolve()) or sha(path) != plan["all_files_sha256"][str(path.relative_to(root))]:
            raise ValueError("The real controller qualification loaded another runtime module: " + name)
        loaded[name] = {"path": str(path.relative_to(root)), "sha256": sha(path)}
    task, = read(inputs / "tasks.json")["selected"]
    failed = root / plan["queue"] / "feal-linear-cryptanalysis-C0-feal-linear-main-r1"
    instruction = (failed / "feal-linear-cryptanalysis/instruction.md").read_text()
    checks = tuple(PublicCheck(**entry) for entry in read(inputs / "checks.json")[task["id"]])
    for check in checks:
        check.validate(instruction)
    original_failed = root / plan["original_failed_score"]
    sys.path.insert(0, str(root / "work/parallel-free-evaluation-20261124"))
    from prepare_report_data import native_output
    wrong = native_output(original_failed.parent, "/app/plaintexts.txt")
    destination = folder / "controller-qualification"
    destination.mkdir()
    logs = destination / "actual-controller"
    logs.mkdir()
    limits = RunLimits(**plan["limits"])
    with DockerTarget(task["image"], "/app", platform="linux/amd64", memory_mb=512, cpus=1,
            read_only_empty_dirs=("/tests",)) as target:
        if target.image != plan["pin"]:
            raise ValueError("The real controller qualification uses another original image")
        deployed = prepare_public_runtime(target, task["candidate_scope"])
        environment = ControlledEnvironment(target, logs, limits, checks, task["candidate_scope"], Budget(3600), False)
        target.upload_file(wrong, "/app/plaintexts.txt")
        negative = environment.verify("public-task", "qualification_actual_wrong_artifact")
        if negative["state"] != "failed":
            raise ValueError("The real ControlledEnvironment accepted the actual wrong plaintext output")
        command = ("import json,subprocess;from pathlib import Path;"
            "subprocess.run(['gcc','-O3','/opt/course-tools/feal_known_pairs.c','-o','/app/feal-known-pairs'],check=True);"
            "r=subprocess.run(['/app/feal-known-pairs','/app/pairs.txt'],capture_output=True,text=True,check=True);"
            "keys=json.loads(r.stdout)['seeds'];out=Path('/app/plaintexts.txt').open('w');"
            "subprocess.run(['/app/decrypt','/app/ciphertexts.txt',*[format(value,'x') for value in keys]],stdout=out,check=True);out.close()")
        produced = target.exec("python3 -c " + shlex.quote(command), timeout=90)
        if produced["returncode"]:
            raise ValueError("The original public data pipeline did not produce its real output")
        positive = environment.verify("public-task", "qualification_public_derived_output")
        if positive["state"] != "passed":
            raise ValueError("The actual controller did not accept the correct public-cipher output")
        changed = target.exec("chmod u+w /opt/course-tools/feal_known_pairs.c && echo '/* qualification-only source change */' >> /opt/course-tools/feal_known_pairs.c", timeout=10)
        if changed["returncode"]:
            raise ValueError("The controlled helper mutation did not execute")
        _, tampered = environment.status()
        if tampered["public-task"]["state"] != "protected_dependency_changed":
            raise ValueError("Removing redundant check metadata weakened the actual helper protection")
        target.upload_file(root / plan["runtime_root"] / "course_eval/feal_known_pairs.c", "/opt/course-tools/feal_known_pairs.c")
        restored = target.exec("chmod 444 /opt/course-tools/feal_known_pairs.c", timeout=10)
        if restored["returncode"]:
            raise ValueError("The exact public helper could not be restored")
        verified = environment.verify("public-task", "qualification_after_exact_helper_restore")
        final = environment.finish("zero_model_controller_qualification")
        if verified["state"] != "passed" or final["valid_verification"] is not True or final["protected_unchanged"] is not True:
            raise ValueError("The actual controller cannot recover exact helper bytes and final evidence")
    result = {"phase": "real_publiccheck_controller_and_helper_protection_passed", "new_model_calls": 0,
        "original_grader_calls": 0, "pin": plan["pin"], "checks_sha256": sha(inputs / "checks.json"),
        "tasks_sha256": sha(inputs / "tasks.json"), "driver_sha256": sha(Path(__file__)),
        "runtime_root": plan["runtime_root"], "public_helper_manifest": deployed,
        "actual_loaded_modules": loaded,
        "old_wrong_state": negative["state"], "correct_state": positive["state"],
        "helper_tamper_state": tampered["public-task"]["state"], "restored_state": verified["state"],
        "final": final, "source_zero_model_failure_retained": str((failed / "result.json").relative_to(root)),
        "scope": "Real PublicCheck.validate, ControlledEnvironment, CandidateStore and protected helper state on the original image. No model class instantiated, no original grader invoked. Actual wrong and public-derived correct files consumed; not a new model score."}
    (destination / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"phase": result["phase"], "new_model_calls": 0,
        "helper_tamper_rejected": True, "final_protected_unchanged": True}), flush=True)


if __name__ == "__main__":
    main()
