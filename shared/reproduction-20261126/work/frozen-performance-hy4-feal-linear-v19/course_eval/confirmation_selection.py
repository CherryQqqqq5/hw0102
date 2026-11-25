import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from course_eval.inventory import AIDER_D


SEED = "nju-course-independent-confirmation-20261105-v1"


def order(value: str) -> str:
    return hashlib.sha256((SEED + "\n" + value).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--previous", type=Path, default=Path("work/frozen.json"))
    parser.add_argument("--history", type=Path, default=Path("work/vmshare"))
    parser.add_argument("--exclusions", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    previous = json.loads(args.previous.read_text())
    exposed = {(row["benchmark"], row["id"]) for row in previous["selected"]}
    for path in args.history.glob("**/trial.json"):
        trial = json.loads(path.read_text())
        task = trial.get("task")
        if isinstance(task, dict) and "benchmark" in task:
            exposed.add((task["benchmark"], task["id"]))
    families = {(row["benchmark"], row["group"]) for row in previous["inventory"]
                if (row["benchmark"], row["id"]) in exposed}
    exclusions = json.loads(args.exclusions.read_text()) if args.exclusions else {}
    inventory = []
    for original in previous["inventory"]:
        row = original.copy()
        key = row["benchmark"] + "/" + row["id"]
        if (row["benchmark"], row["group"]) in families:
            row["exclude"] = "Previously exposed task or duplicate family"
        elif key in exclusions:
            row["exclude"] = exclusions[key]
        inventory.append(row)
    selected, used = [], set()

    def pick(benchmark, stratum):
        available = [row for row in inventory if row["benchmark"] == benchmark and row["stratum"] == stratum
                     and not row["exclude"] and (benchmark, row["group"]) not in used]
        if not available:
            raise ValueError(f"No remaining eligible task: {benchmark}/{stratum}")
        row = min(available, key=lambda item: order(item["id"]))
        selected.append(row | {"split": "C"})
        used.add((benchmark, row["group"]))

    # 使用已验收的四个仓库环境，避免新的工具链成为配置差异。
    for repo, count in (("django/django", 3), ("scikit-learn/scikit-learn", 3),
                        ("pydata/xarray", 2), ("pytest-dev/pytest", 2)):
        for _ in range(count):
            pick("swe", repo)
    for language, count in sorted(AIDER_D.items()):
        for _ in range(count):
            pick("aider", language)
    counts = Counter()
    for _ in range(10):
        categories = {row["stratum"] for row in inventory if row["benchmark"] == "terminal"
                      and not row["exclude"] and ("terminal", row["group"]) not in used}
        category = min(categories, key=lambda value: (counts[value], order(value)))
        pick("terminal", category)
        counts[category] += 1
    result = {"stage": "candidate_selection_pending_environment_preflight", "seed": SEED,
              "revisions": previous["revisions"], "previously_exposed": sorted(exposed),
              "inventory": inventory, "selected": selected}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x") as handle:
        json.dump(result, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    for row in selected:
        print(row["benchmark"], row["stratum"], row["id"])


if __name__ == "__main__":
    main()
