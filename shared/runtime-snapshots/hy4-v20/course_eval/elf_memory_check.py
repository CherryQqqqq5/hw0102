import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from elftools.elf.elffile import ELFFile


def loaded_words(filename):
    words = {}
    segments = []
    with filename.open("rb") as stream:
        elf = ELFFile(stream)
        byteorder = "little" if elf.little_endian else "big"
        for segment in elf.iter_segments():
            if segment["p_type"] != "PT_LOAD":
                continue
            size = segment["p_memsz"]
            if size > 64 * 1024 * 1024:
                raise ValueError("This bounded public diagnostic supports load segments up to 64 MiB")
            data = segment.data()
            base = segment["p_vaddr"]
            segments.append({"virtual_address": base, "file_bytes": len(data), "memory_bytes": size})
            for offset in range(0, size - 3, 4):
                address = str(base + offset)
                value = int.from_bytes(data[offset:offset + 4].ljust(4, b"\0"), byteorder)
                if address in words and words[address] != value:
                    raise ValueError("Overlapping load segments give inconsistent memory words")
                words[address] = value
    if not words:
        raise ValueError("No complete loadable memory words are available")
    return words, segments


def check(binary, program):
    before = hashlib.sha256(binary.read_bytes()).hexdigest()
    expected, segments = loaded_words(binary)
    process = subprocess.run(["node", str(program), str(binary)], text=True, capture_output=True,
                             timeout=30, check=False)
    after = hashlib.sha256(binary.read_bytes()).hexdigest()
    if process.returncode:
        raise RuntimeError("The delivered extractor failed: " + process.stderr[-2000:])
    actual = json.loads(process.stdout)
    if not isinstance(actual, dict) or any(not isinstance(key, str) or not key.isdecimal()
            or type(value) is not int for key, value in actual.items()):
        raise ValueError("The extractor must return a JSON object of decimal addresses and integer values")
    inconsistent = {key: {"actual": actual[key], "memory_word": value}
                    for key, value in expected.items() if key in actual and actual[key] != value}
    matched = sum(actual.get(key) == value for key, value in expected.items())
    coverage = matched / len(expected)
    return {"passed": before == after and not inconsistent and coverage >= .75,
        "scope": "Public diagnostic of unsigned 32-bit words at ELF PT_LOAD virtual addresses; not the original reference scorer",
        "matched_loadable_words": matched, "total_loadable_words": len(expected),
        "public_memory_coverage": coverage, "inconsistent_addresses": inconsistent,
        "additional_addresses_outside_this_diagnostic": len(set(actual) - set(expected)),
        "binary_unchanged": before == after, "binary_sha256": before, "load_segments": segments,
        "new_model_calls": 0, "original_grader_calls": 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", type=Path)
    parser.add_argument("program", type=Path)
    args = parser.parse_args()
    result = check(args.binary.resolve(strict=True), args.program.resolve(strict=True))
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
