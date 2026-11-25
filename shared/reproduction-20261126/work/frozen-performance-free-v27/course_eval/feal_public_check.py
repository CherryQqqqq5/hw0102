import argparse
from collections import Counter
import json
from pathlib import Path
import re
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", type=Path, default=Path("/app/pairs.txt"))
    parser.add_argument("--ciphertexts", type=Path, default=Path("/app/ciphertexts.txt"))
    parser.add_argument("--plaintexts", type=Path, default=Path("/app/plaintexts.txt"))
    args = parser.parse_args()
    source = Path(__file__).with_name("feal_known_pairs.c")
    folder = Path("/app/.course-feal-check")
    folder.mkdir(exist_ok=True)
    binary = folder / "known-pairs-solver"
    compiled = subprocess.run(["gcc", "-O3", "-Wall", "-Wextra", "-Werror", str(source), "-o", str(binary)],
        capture_output=True, text=True, timeout=30)
    if compiled.returncode:
        raise RuntimeError("The public known-pair solver could not compile: " + compiled.stderr)
    recovered = subprocess.run([str(binary), str(args.pairs)], capture_output=True, text=True, timeout=60)
    if recovered.returncode:
        raise RuntimeError("The public known pairs do not determine an admissible verified key: " + recovered.stderr)
    record = json.loads(recovered.stdout)
    seeds = record["seeds"]
    if (record["seed_bits"] != 20 or len(seeds) != 4
            or not all(type(value) is int and 0 <= value < 1 << 20 for value in seeds)):
        raise ValueError("The public solver did not return four20bit seeds")
    keys = [format(value, "x") for value in seeds]
    pairs = [tuple(map(int, line.split())) for line in args.pairs.read_text().splitlines()]
    if not pairs or any(len(pair) != 2 or any(value < 0 or value >= 1 << 64 for value in pair) for pair in pairs):
        raise ValueError("The supplied known-pair file has invalid unsigned64bit values")
    for plaintext, ciphertext in pairs:
        actual = subprocess.run(["/app/feal", format(plaintext, "x"), *keys],
            capture_output=True, text=True, timeout=5)
        matches = re.findall(r"^Ciphertext:\s*0x([0-9a-fA-F]+)\s*$", actual.stdout, re.MULTILINE)
        if actual.returncode or len(matches) != 1 or int(matches[0], 16) != ciphertext:
            raise ValueError("The original public encryptor rejects the recovered key")
    expected = subprocess.run(["/app/decrypt", str(args.ciphertexts), *keys],
        capture_output=True, text=True, timeout=10)
    if expected.returncode:
        raise RuntimeError("The original public decryptor rejected the recovered seeds: " + expected.stderr)
    wanted = [int(token) for token in expected.stdout.split()]
    if not wanted or any(value < 0 or value >= 1 << 64 for value in wanted):
        raise ValueError("The original public decryptor did not produce unsigned64bit plaintexts")
    actual_values = [int(token) for token in re.findall(r"(?<![A-Za-z0-9_.+-])\d+(?![A-Za-z0-9_.])", args.plaintexts.read_text())]
    missing = Counter(wanted) - Counter(actual_values)
    passed = not missing
    print(json.dumps({"passed": passed, "conditions": [{"id": "public-known-pair-plaintexts", "passed": passed,
        "actual": {"verified_public_known_pairs": len(pairs), "expected_ciphertext_records": len(wanted),
            "missing_plaintext_records": sum(missing.values())},
        "required": "Each plaintext derived with a key verified against every public known pair appears as a decimal token"}],
        "scope": "Uses only public cipher programs and task-visible input files; no hidden key, plaintext file or original grading data. Diagnostic text and additional tokens are allowed; output ordering is not asserted."}))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
