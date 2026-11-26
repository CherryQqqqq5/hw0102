import argparse
import hashlib
import json
from pathlib import Path


SOURCE_SHA256 = "f3dd9a3efc6ef2bdb3a28708225162f99cd39a45323481b46023ac9d7e2cfae4"


def export_script(output, dimension, oracle_module, oracle_function, array_name="stolen_A1.npy"):
    if type(dimension) is not int or dimension < 1:
        raise ValueError("Use the positive input dimension from the public task")
    if not all(part.isidentifier() and not part.startswith("_") for part in oracle_module.split(".")):
        raise ValueError("The public oracle module must be a dotted public identifier")
    if (not oracle_function.isidentifier() or oracle_function.startswith("_")
            or oracle_function in {"A1", "A2", "b1", "b2"}):
        raise ValueError("Select the public callable from the task,not private weights")
    if Path(array_name).name != array_name or not array_name.endswith(".npy") or output.suffix != ".py":
        raise ValueError("Use a Python output script and a local.npy artifact filename")
    source = Path(__file__).with_name("relu_recovery.py").read_bytes()
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        raise ValueError("The immutable public numerical helper changed")
    entry = f'''

import importlib
from pathlib import Path
import sys


def main():
    directory = Path(__file__).resolve().parent
    sys.path.insert(0, str(directory))
    oracle = getattr(importlib.import_module({oracle_module!r}), {oracle_function!r})
    if not callable(oracle):
        raise TypeError("The public query API is not callable")
    rows, diagnostics = recover_relu_directions(oracle, {dimension!r})
    rows = np.asarray(rows, dtype=np.float64)
    if rows.ndim != 2 or rows.shape[1] != {dimension!r} or not np.isfinite(rows).all():
        raise ValueError("Recovery did not produce a finite direction matrix")
    np.save(directory / {array_name!r}, rows)
    print({{"shape": list(rows.shape), "oracle_queries": diagnostics["oracle_queries"],
           "completeness_certified": diagnostics["completeness_certified"]}})


if __name__ == "__main__":
    main()
'''
    program = source + entry.encode("utf-8")
    compile(program, str(output), "exec")
    with output.open("xb") as stream:
        stream.write(program)
    return {"source_sha256": SOURCE_SHA256, "script_sha256": hashlib.sha256(program).hexdigest(),
        "script_bytes": len(program), "dimension": dimension, "oracle_module": oracle_module,
        "oracle_function": oracle_function, "scope": "Copies only the frozen public helper;exports no weights and performs no oracle queries"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dimension", type=int, required=True)
    parser.add_argument("--oracle-module", required=True)
    parser.add_argument("--oracle-function", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--array-name", default="stolen_A1.npy")
    args = parser.parse_args()
    print(json.dumps(export_script(args.output, args.dimension, args.oracle_module, args.oracle_function, args.array_name)))
