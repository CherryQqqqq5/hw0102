import ctypes
import hashlib
import json
import random
import subprocess
import time
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    root, folder = Path.cwd(), Path(__file__).parent.resolve()
    destination = folder / "generated-qualification"
    destination.mkdir()
    original = root / "work/vmshare/performance75-hy4-sql-layout-v18-main-20261125/feal-linear-cryptanalysis-C0-r1/feal-linear-cryptanalysis/environment/task-deps/feal.c"
    source = folder / "feal_known_pairs.c"
    commands = [
        ["cc", "-O3", "-Wall", "-Wextra", "-Werror", str(source), "-o", str(destination / "feal-known-pairs")],
        ["cc", "-O3", "-dynamiclib", str(source), "-o", str(destination / "helper.dylib")],
        ["cc", "-O3", "-Wno-format", "-dynamiclib", "-Dmain=course_original_feal_main", str(original), "-o", str(destination / "original.dylib")],
    ]
    for command in commands:
        subprocess.run(command, check=True, capture_output=True, text=True)
    helper, public = ctypes.CDLL(str(destination / "helper.dylib")), ctypes.CDLL(str(destination / "original.dylib"))
    for function in (helper.feal_round, helper.feal_round_inverse, public.f_function):
        function.argtypes = [ctypes.c_uint32]
        function.restype = ctypes.c_uint32
    public.set_keys.argtypes = [ctypes.c_uint32] * 4
    public.set_keys.restype = None
    public.encrypt.argtypes = [ctypes.c_uint64]
    public.encrypt.restype = ctypes.c_uint64
    rng = random.Random(20261125)
    for _ in range(2048):
        value = rng.getrandbits(32)
        if helper.feal_round(value) != public.f_function(value) or helper.feal_round_inverse(public.f_function(value)) != value:
            raise ValueError("The helper does not match and invert the actual public round function")
    rows = []
    for index in range(3):
        keys = [rng.randrange(1 << 20) for _ in range(4)]
        public.set_keys(*keys)
        known = [(value, public.encrypt(value)) for value in [rng.getrandbits(64) for _ in range(32)]]
        unseen = [(value, public.encrypt(value)) for value in [rng.getrandbits(64) for _ in range(16)]]
        path = destination / ("generated-known-pairs-" + str(index) + ".txt")
        path.write_text("".join(str(left) + " " + str(right) + "\n" for left, right in known))
        started = time.monotonic()
        actual = subprocess.run([str(destination / "feal-known-pairs"), str(path)],
            check=True, capture_output=True, text=True, timeout=30)
        elapsed = time.monotonic() - started
        outcome = json.loads(actual.stdout)
        recovered = outcome["seeds"]
        if len(recovered) != 4 or not all(type(value) is int and 0 <= value < 1 << 20 for value in recovered):
            raise ValueError("The real helper returned an invalid seed vector")
        public.set_keys(*recovered)
        if not all(public.encrypt(value) == ciphertext for value, ciphertext in known + unseen):
            raise ValueError("Recovered seeds do not encrypt both known and withheld generated plaintexts")
        rows.append({"case": index, "known_pairs": len(known), "additional_generated_pairs": len(unseen),
            "all_verified_by_original_public_cipher": True, "original_seed_recovered": recovered == keys,
            "solver_seconds": elapsed, "actual_stdout": actual.stdout, "actual_stderr": actual.stderr,
            "generated_input_sha256": sha(path)})
    wrong = destination / "corrupted-generated-pairs.txt"
    bad = list(known)
    bad[-1] = bad[-1][0], bad[-1][1] ^ 1
    wrong.write_text("".join(str(left) + " " + str(right) + "\n" for left, right in bad))
    rejected = subprocess.run([str(destination / "feal-known-pairs"), str(wrong)],
        capture_output=True, text=True, timeout=30)
    if rejected.returncode == 0 or rejected.stdout.strip():
        raise ValueError("The real solver accepted inconsistent generated evidence")
    result = {"phase": "generated_public_cipher_qualification_passed", "new_model_calls": 0,
        "original_benchmark_grader_calls": 0, "actual_task_key_or_plaintexts_used": False,
        "source_sha256": sha(source), "public_cipher_sha256": sha(original),
        "driver_sha256": sha(Path(__file__)), "native_host_compilation": commands,
        "random_round_inverse_cases": 2048, "generated_cases": rows,
        "corrupted_pair_rejected": {"returncode": rejected.returncode, "stdout": rejected.stdout, "stderr": rejected.stderr},
        "scope": "Native host only, three generated20bit-seed instances. No task model output, actual task pairs, actual keys, target plaintext or hidden grading inputs enter the solver. No Linux-container qualification or new model score claimed."}
    (destination / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"phase": result["phase"], "new_model_calls": 0,
        "generated_solver_seconds": [row["solver_seconds"] for row in rows], "corrupted_pair_rejected": True}), flush=True)


if __name__ == "__main__":
    main()
