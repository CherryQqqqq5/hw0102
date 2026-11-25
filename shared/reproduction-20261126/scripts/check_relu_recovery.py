import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np

from course_eval.relu_recovery import recover_relu_directions, validate_saved_directions


def direction_match(actual, expected):
    a = actual / np.linalg.norm(actual, axis=1, keepdims=True)
    b = expected / np.linalg.norm(expected, axis=1, keepdims=True)
    cosine = a @ b.T
    match = np.argmax(np.abs(cosine), axis=0)
    errors = []
    for column, index in enumerate(match):
        scale = actual[index] @ expected[column] / (actual[index] @ actual[index])
        errors.append(float(np.linalg.norm(scale * actual[index] - expected[column])
                            / np.linalg.norm(expected[column])))
    one_to_one = len(set(int(value) for value in match)) == len(expected)
    return {"shape": list(actual.shape), "expected_shape": list(expected.shape),
            "one_to_one": one_to_one, "max_relative_direction_error": max(errors),
            "passed": actual.shape == expected.shape and one_to_one and max(errors) <= 1e-5}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    results = []
    truncated_control = None
    for width, seed in ((4, 1729), (16, 1730), (64, 1731), (8, 1732)):
        rng = np.random.default_rng(seed)
        weights = rng.normal(size=(width, 10)) * 0.3
        biases = rng.normal(size=width) * 0.1
        output = rng.normal(size=width) * 0.3
        intercept = float(rng.normal())
        unidentifiable = seed == 1732
        if unidentifiable:
            output[-1] = 0

        def oracle(point):
            return float(output @ np.maximum(weights @ point + biases, 0) + intercept)

        started = time.monotonic()
        actual, trace = recover_relu_directions(oracle, 10)
        record = {"width": width, "seed": seed, "source": "Locally generated Gaussian network, not benchmark data",
                  "zero_output_neuron": unidentifiable, "wall_seconds": time.monotonic() - started,
                  **trace, **direction_match(actual, weights)}
        record["fresh_query_consistency"] = validate_saved_directions(oracle, 10, actual)
        results.append(record)
        if width == 64:
            truncated_control = {"source": "Constructed counterfactual: truncate actual recovered rows to 28",
                                 **direction_match(actual[:28], weights),
                                 "fresh_query_consistency": validate_saved_directions(oracle, 10, actual[:28])}
    result = {"new_model_calls": 0, "original_grader_calls": 0, "numpy_version": np.__version__,
              "library_sha256": hashlib.sha256(Path("course_eval/relu_recovery.py").read_bytes()).hexdigest(),
              "normal_cases": results[:-1], "known_wrong_control": truncated_control,
              "unidentifiable_control": results[-1],
              "ready_for_later_integration": (all(row["passed"] and row["fresh_query_consistency"]["passed"]
                                                   for row in results[:-1])
                  and not truncated_control["passed"]
                  and not truncated_control["fresh_query_consistency"]["passed"]
                  and not results[-1]["passed"]),
              "interpretation": "Synthetic numerical validation only; no agent invocation, original task grade or completeness guarantee"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    if not result["ready_for_later_integration"]:
        raise AssertionError("The frozen synthetic checks do not support integration; preserve and inspect this result")


if __name__ == "__main__":
    main()
