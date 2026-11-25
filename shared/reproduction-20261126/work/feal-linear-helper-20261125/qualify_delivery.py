import importlib.util
import json
import hashlib
from pathlib import Path
import shlex
import sys

from course_eval.docker_target import DockerTarget

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "parallel-free-evaluation-20261124"))
from prepare_report_data import native_output


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    root, folder = Path.cwd(), Path(__file__).parent.resolve()
    runtime = root / "work/frozen-performance-hy4-feal-linear-v19"
    spec = importlib.util.spec_from_file_location("qualified_feal_terminal_runtime", runtime / "course_eval/terminal_runtime.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    host = read(folder / "generated-qualification/result.json")
    if host["source_sha256"] != sha(runtime / "course_eval/feal_known_pairs.c"):
        raise ValueError("The proposed deployed algorithm differs from its generated qualification")
    source = root / "work/vmshare/performance75-hy4-sql-layout-v18-main-20261125/feal-linear-cryptanalysis-C0-r1"
    score = source / "result.json"
    original_score_sha = sha(score)
    if read(score)["scoreable"] is not True or read(score)["passed"] is not False:
        raise ValueError("Preserve the actual scored wrong-plaintext case as the negative control")
    wrong = native_output(source, "/app/plaintexts.txt")
    baseline = root / "work/vmshare/performance75-dsh-hy4-v10"
    task, = [task for task in read(baseline / "tasks.json")["selected"] if task["id"] == "feal-linear-cryptanalysis"]
    pin = read(baseline / "environment-pins.json")["pins"][task["id"]]
    scope = {"reusable_helper": "feal_known_pairs", "python": "python3"}
    instructions = module.reusable_helper_instructions(scope)
    if "gcc -O3 -Wall -Wextra -Werror" not in instructions or "hexadecimal" not in instructions:
        raise ValueError("The exact deployment and hexadecimal CLI instructions are missing")
    destination = folder / "delivery-qualification"
    destination.mkdir()
    protected = "sha256sum /app/feal.c /app/decrypt.c /app/feal /app/decrypt /app/pairs.txt /app/ciphertexts.txt"
    with DockerTarget(task["image"], "/app", platform="linux/amd64", memory_mb=512, cpus=1,
            read_only_empty_dirs=("/tests",)) as target:
        if target.image != pin:
            raise ValueError("The advertised helper is not running in the actual original task image")
        before = target.exec(protected, timeout=10)
        deployed = module.prepare_public_runtime(target, scope)
        actual = target.exec("gcc -O3 -Wall -Wextra -Werror /opt/course-tools/feal_known_pairs.c -o /app/feal-known-pairs && /app/feal-known-pairs /app/pairs.txt > /app/recovered-public-seeds.json", timeout=90)
        (destination / "advertised-cli-process.json").write_text(json.dumps(actual, indent=2) + "\n")
        if actual["returncode"]:
            raise ValueError("The actual advertised CLI did not recover a key from the original visible pairs")
        target.upload_file(wrong, "/app/failed-model-plaintexts.txt")
        checker = "python3 /opt/course-tools/feal_public_check.py --plaintexts "
        failed = target.exec(checker + "/app/failed-model-plaintexts.txt", timeout=120)
        (destination / "actual-failed-model-content-check.json").write_text(json.dumps(failed, indent=2) + "\n")
        if failed["returncode"] != 1 or read_payload(failed)["passed"] is not False:
            raise ValueError("The public semantic checker did not reject the real shape-valid wrong model output")
        command = ("import json,subprocess;from pathlib import Path;"
            "keys=json.loads(Path('/app/recovered-public-seeds.json').read_text())['seeds'];"
            "out=Path('/app/qualified-public-plaintexts.txt').open('w');"
            "subprocess.run(['/app/decrypt','/app/ciphertexts.txt',*[format(value,'x') for value in keys]],stdout=out,check=True);out.close()")
        produced = target.exec("python3 -c " + shlex.quote(command), timeout=20)
        if produced["returncode"]:
            raise ValueError("The original public decryptor could not consume dynamically recovered hexadecimal seeds")
        correct = target.exec(checker + "/app/qualified-public-plaintexts.txt", timeout=120)
        (destination / "actual-derived-content-check.json").write_text(json.dumps(correct, indent=2) + "\n")
        if correct["returncode"] or read_payload(correct)["passed"] is not True:
            raise ValueError("The actual deployed public checker rejects correct public-cipher output")
        drop = ("from pathlib import Path;p=Path('/app/qualified-public-plaintexts.txt');"
            "Path('/app/dropped-public-plaintexts.txt').write_text('\\n'.join(p.read_text().splitlines()[1:])+'\\n')")
        removed = target.exec("python3 -c " + shlex.quote(drop), timeout=10)
        if removed["returncode"]:
            raise ValueError("The controlled missing-record input was not created")
        missing = target.exec(checker + "/app/dropped-public-plaintexts.txt", timeout=120)
        (destination / "actual-missing-record-check.json").write_text(json.dumps(missing, indent=2) + "\n")
        if missing["returncode"] != 1 or read_payload(missing)["passed"] is not False:
            raise ValueError("The real content checker accepted a deliberately omitted plaintext record")
        after = target.exec(protected, timeout=10)
        if before["returncode"] or after["returncode"] or before["stdout"] != after["stdout"]:
            raise ValueError("Public cipher programs or original inputs changed during qualification")
    if sha(score) != original_score_sha:
        raise ValueError("The original failed model score changed during engineering qualification")
    result = {"phase": "actual_original_linux_helper_and_public_content_check_passed",
        "new_model_calls": 0, "original_grader_calls": 0, "pin": pin,
        "runtime_files_sha256": {name: sha(runtime / "course_eval" / name) for name in
            ("terminal_runtime.py", "feal_known_pairs.c", "feal_public_check.py")},
        "driver_sha256": sha(Path(__file__)), "public_helper_manifest": deployed,
        "actual_failed_model_rejected": read_payload(failed), "actual_public_cipher_derived_output_accepted": read_payload(correct),
        "actual_omitted_record_rejected": read_payload(missing), "original_public_inputs_unchanged": True,
        "original_failed_score": str(score.relative_to(root)), "original_failed_score_sha256": original_score_sha,
        "actual_failed_artifact_sha256": sha(wrong),
        "scope": "An engineering task replay from public known pairs and original cipher tools. No hidden reference key or answer supplied. This is not a new model success or an original benchmark grade."}
    (destination / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"phase": result["phase"], "new_model_calls": 0,
        "original_grader_calls": 0, "real_failed_model_output_rejected": True}), flush=True)


def read_payload(process):
    return json.loads(process["stdout"])


if __name__ == "__main__":
    main()
