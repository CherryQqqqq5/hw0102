import hashlib
import json
import os
from pathlib import Path

from course_eval.docker_target import DockerTarget


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


PROBE = '''import ctypes,json,random,subprocess,time
from pathlib import Path
root=Path("/course-generated")
data=json.loads((root/"cases.json").read_text())
public=ctypes.CDLL(str(root/"original.so"))
public.set_keys.argtypes=[ctypes.c_uint32]*4
public.set_keys.restype=None
public.encrypt.argtypes=[ctypes.c_uint64]
public.encrypt.restype=ctypes.c_uint64
public.f_function.argtypes=[ctypes.c_uint32]
public.f_function.restype=ctypes.c_uint32
helper=ctypes.CDLL(str(root/"helper.so"))
for func in (helper.feal_round,helper.feal_round_inverse):
    func.argtypes=[ctypes.c_uint32]
    func.restype=ctypes.c_uint32
rng=random.Random(2026112502)
for _ in range(2048):
    value=rng.getrandbits(32)
    if helper.feal_round(value)!=public.f_function(value) or helper.feal_round_inverse(public.f_function(value))!=value:
        raise ValueError("Linux round mismatch")
rows=[]
for case in data:
    path=root/case["name"]
    started=time.monotonic()
    process=subprocess.run([str(root/"feal-known-pairs"),str(path)],check=True,capture_output=True,text=True,timeout=30)
    elapsed=time.monotonic()-started
    actual=json.loads(process.stdout)
    if actual["seeds"]!=case["generated_seeds"]:
        raise ValueError("Linux recovered different seeds from the host-generated evidence")
    public.set_keys(*actual["seeds"])
    pairs=[tuple(map(int,line.split())) for line in path.read_text().splitlines()]
    if not all(public.encrypt(plain)==cipher for plain,cipher in pairs):
        raise ValueError("The real Linux public cipher rejects recovered seeds")
    rows.append({"case":case["name"],"known_pairs":len(pairs),"original_public_cipher_verified":True,
        "solver_seconds":elapsed,"actual_stdout":process.stdout,"actual_stderr":process.stderr})
bad=subprocess.run([str(root/"feal-known-pairs"),str(root/"corrupted-generated-pairs.txt")],capture_output=True,text=True,timeout=30)
if bad.returncode==0 or bad.stdout.strip():raise ValueError("Linux accepted inconsistent evidence")
print(json.dumps({"passed":True,"round_cases":2048,"generated_cases":rows,
    "corrupted_pair_rejected":True,"corrupted_returncode":bad.returncode,
    "new_model_calls":0,"original_grader_calls":0}))
'''


def main():
    root, folder = Path.cwd(), Path(__file__).parent.resolve()
    host = folder / "generated-qualification"
    proof = read(host / "result.json")
    if proof["source_sha256"] != sha(folder / "feal_known_pairs.c") or proof["phase"] != "generated_public_cipher_qualification_passed":
        raise ValueError("The generated public qualification does not bind the current helper")
    baseline = root / "work/vmshare/performance75-dsh-hy4-v10"
    task, = [task for task in read(baseline / "tasks.json")["selected"] if task["id"] == "feal-linear-cryptanalysis"]
    expected = read(baseline / "environment-pins.json")["pins"][task["id"]]
    destination = folder / "linux-qualification"
    destination.mkdir()
    cases = []
    for row in proof["generated_cases"]:
        path = host / ("generated-known-pairs-" + str(row["case"]) + ".txt")
        if sha(path) != row["generated_input_sha256"] or row["original_seed_recovered"] is not True:
            raise ValueError("A generated qualification input or actual seed assertion changed")
        cases.append({"name": path.name, "generated_seeds": json.loads(row["actual_stdout"])["seeds"]})
    manifest, probe = destination / "cases.json", destination / "probe.py"
    manifest.write_text(json.dumps(cases, indent=2) + "\n")
    probe.write_text(PROBE)
    with DockerTarget(task["image"], "/app", platform="linux/amd64", memory_mb=512, cpus=1,
            read_only_empty_dirs=("/tests",)) as target:
        if target.image != expected:
            raise ValueError("The actual Linux qualification uses another task image")
        fingerprint = target.exec("sha256sum /app/feal.c && mkdir /course-generated", timeout=10)
        if fingerprint["returncode"] or fingerprint["stdout"].split()[0] != proof["public_cipher_sha256"]:
            raise ValueError("The actual public Linux cipher differs from the source used for generated qualification")
        target.upload_file(folder / "feal_known_pairs.c", "/course-generated/feal_known_pairs.c")
        target.upload_file(manifest, "/course-generated/cases.json")
        target.upload_file(probe, "/course-generated/probe.py")
        for case in cases:
            target.upload_file(host / case["name"], "/course-generated/" + case["name"])
        target.upload_file(host / "corrupted-generated-pairs.txt", "/course-generated/corrupted-generated-pairs.txt")
        compiled = target.exec("gcc -O3 -Wall -Wextra -Werror /course-generated/feal_known_pairs.c -o /course-generated/feal-known-pairs && gcc -O3 -shared -fPIC /course-generated/feal_known_pairs.c -o /course-generated/helper.so && gcc -O3 -shared -fPIC -Dmain=course_original_feal_main /app/feal.c -o /course-generated/original.so", timeout=30)
        (destination / "compile-process.json").write_text(json.dumps(compiled, indent=2) + "\n")
        if compiled["returncode"]:
            raise RuntimeError("The helper failed to compile in the actual original Linux environment")
        actual = target.exec("python3 /course-generated/probe.py", timeout=120)
        (destination / "actual-probe-process.json").write_text(json.dumps(actual, indent=2) + "\n")
        details = json.loads(actual["stdout"])
        if actual["returncode"] or details["passed"] is not True:
            raise ValueError("The actual original-image Linux qualification failed")
    result = {"phase": "actual_original_linux_generated_qualification_passed", "new_model_calls": 0,
        "original_grader_calls": 0, "pin": expected, "source_sha256": sha(folder / "feal_known_pairs.c"),
        "host_qualification_sha256": sha(host / "result.json"), "driver_sha256": sha(Path(__file__)),
        "generated_manifest_sha256": sha(manifest), "probe_sha256": sha(probe), "actual": details,
        "scope": "Actual original Linux image, generated known-pair data only. No actual task pairs, target keys, ciphertexts or plaintext answers read; no new model or original-grader pass claimed."}
    (destination / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"phase": result["phase"], "new_model_calls": 0,
        "solver_seconds": [row["solver_seconds"] for row in details["generated_cases"]]}), flush=True)


if __name__ == "__main__":
    main()
