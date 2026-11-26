import hashlib
import json
from pathlib import Path


ROOT = Path.cwd()
FOLDER = Path(__file__).parent.resolve()
SEED = "nju-input-efficiency-20261126-v1"


def main():
    old = ROOT / "work/unseen-efficiency-20261126"
    source = ROOT / "work/hw0102-publish/shared/candidate-tasks.json"
    manifest = json.loads(source.read_text())
    scout = json.loads((old / "scout-review.json").read_text())
    excluded = {tuple(row) for row in scout["unseen_exclusions"]["excluded_ids"]}
    excluded.update((row["benchmark"], row["id"]) for row in json.loads((old / "candidate-tasks.json").read_text())["selected"])
    families = {(row["benchmark"], row["group"]) for row in manifest["inventory"]
        if (row["benchmark"], row["id"]) in excluded}
    eligible = [row for row in manifest["inventory"] if not row["exclude"]
        and (row["benchmark"], row["group"]) not in families]
    ordered = sorted(eligible, key=lambda row: hashlib.sha256((SEED + "\n" + row["id"]).encode()).hexdigest())
    confirmation = [next(row for row in ordered if row["benchmark"] == "aider" and row["stratum"] == language)
        for language in ("javascript", "python", "cpp")]
    projects = set()
    for row in ordered:
        if (row["benchmark"] == "swe" and row["stratum"] in
                {"django/django", "pytest-dev/pytest", "scikit-learn/scikit-learn", "pydata/xarray"}
                and row["stratum"] not in projects):
            confirmation.append(row)
            projects.add(row["stratum"])
            if len(projects) == 3:
                break
    diagnostic_ids = ["javascript/book-store", "django__django-14855", "pytest-dev__pytest-7571"]
    diagnostic = [next(row for row in manifest["inventory"] if row["id"] == name) for name in diagnostic_ids]
    result = {"stage": "selection_before_model_calls", "seed": SEED, "revisions": manifest["revisions"],
        "selected": diagnostic + confirmation, "inventory": diagnostic + confirmation,
        "diagnostic_ids": diagnostic_ids, "confirmation_ids": [row["id"] for row in confirmation],
        "excluded_ids": sorted(excluded), "excluded_count": len(excluded),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "selection_uses_model_results": False, "confirmation_selected_before_diagnostic_calls": True,
        "primary_variable": "New successful long bash output: full versus deterministic digest with full-output recall",
        "limits": {"model_calls": 500, "wall_seconds": 1800, "command_seconds": 120,
            "max_output_tokens": 64000, "timeout_retries": 0},
        "maximum_model_task_trials": 33,
        "diagnostic_progression": "Complete all9; admit digest to fresh confirmation only if all3 original scores pass and no mechanical boundary remains",
        "routing_candidates": {"dsh-aider-env-swe": {"aider": "dsh", "swe": "environment"},
            "dsh-aider-digest-swe": {"aider": "dsh", "swe": "digest"}},
        "selection_rule": "All6 original grades and applicable controller checks pass; >=10% lower tokens per passed task than environment C0, median and maximum agent time <=110% of environment C0; choose lowest tokens; repeat exactly6 once",
        "repeat_adoption_rule": "All6 pass, >=10% lower tokens per passed task and median/maximum time <=110% of first-round environment C0",
        "execution_target": "ModelArts isolated Linux guest; original container scorer; local authenticated free-model relay",
        "fee_rule": "Hy4free actual own zero-credit record per generation; stop unknown or nonzero; historical35 retained"}
    with (FOLDER / "candidate-tasks.json").open("x") as handle:
        handle.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"diagnostic": diagnostic_ids, "confirmation": result["confirmation_ids"],
        "excluded": len(excluded), "model_calls": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
