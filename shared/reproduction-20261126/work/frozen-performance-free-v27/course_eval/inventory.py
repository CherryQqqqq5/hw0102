import argparse
import hashlib
import json
import tomllib
from collections import Counter, defaultdict
from pathlib import Path

REVISIONS = {
    "swe": "78f471bf655a3137b2e8a75af1501690ec009ec3",
    "terminal": "7131e4375048a0e408a8fb404b5f499d726b695b",
    "aider": "7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f",
}
SEED = "nju-agent-course-20261104-v1"
AIDER_D = {"cpp": 2, "go": 2, "java": 1, "javascript": 2, "python": 2, "rust": 1}
TERMINAL_FAMILIES = {
    "break-filter-js-from-html": "filter-js-from-html",
    "feal-differential-cryptanalysis": "feal-cryptanalysis",
    "feal-linear-cryptanalysis": "feal-cryptanalysis",
    "path-tracing-reverse": "path-tracing",
    "polyglot-c-py": "polyglot-executable",
    "polyglot-rust-c": "polyglot-executable",
    "qemu-alpine-ssh": "qemu",
    "qemu-startup": "qemu",
}


def order(value: str) -> str:
    return hashlib.sha256(f"{SEED}\n{value}".encode()).hexdigest()


def load_swe(root: Path) -> list[dict]:
    path = root / "swe-inventory.json"
    records = []
    for row in json.loads(path.read_text()):
        reason = None
        if row["difficulty"] not in {"<15 min fix", "15 min - 1 hour"}:
            reason = "outside the preselected issue-size bands"
        elif not row["image"] or row["eval_type"] != "pass_and_fail":
            reason = "missing official prebuilt image or unsupported scoring mode"
        records.append({
            "benchmark": "swe", "id": row["instance_id"], "stratum": row["repo"],
            "group": row["instance_id"], "difficulty": row["difficulty"],
            "image": row["image"], "base_commit": row["base_commit"], "exclude": reason,
        })
    return records


def load_terminal(root: Path) -> list[dict]:
    base = root / f"terminal-bench-2-1-{REVISIONS['terminal']}" / "tasks"
    records = []
    for path in sorted(base.glob("*/task.toml")):
        config = tomllib.loads(path.read_text())
        env = config["environment"]
        meta = config["metadata"]
        task_id = path.parent.name
        reason = None
        if env.get("gpus", 0) or env["cpus"] > 2 or env["memory_mb"] > 3072:
            reason = "exceeds CPU-only per-task resource limit"
        elif not env.get("docker_image") or not (path.parent / "environment/Dockerfile").is_file():
            reason = "outside prebuilt single-container task scope"
        elif any((path.parent / "environment" / name).exists() for name in (
            "docker-compose.yaml", "docker-compose.yml", "compose.yaml", "compose.yml",
        )):
            reason = "outside single-container task scope"
        records.append({
            "benchmark": "terminal", "id": task_id, "stratum": meta["category"],
            "group": TERMINAL_FAMILIES.get(task_id, task_id), "difficulty": meta["difficulty"],
            "image": env.get("docker_image"), "cpus": env["cpus"], "memory_mb": env["memory_mb"],
            "agent_timeout_seconds": config["agent"]["timeout_sec"], "exclude": reason,
        })
    return records


def load_aider(root: Path) -> list[dict]:
    base = root / f"polyglot-benchmark-{REVISIONS['aider']}"
    records = []
    for path in sorted(base.glob("*/exercises/practice/*/.meta/config.json")):
        task_dir = path.parents[1]
        language = task_dir.parents[2].name
        exercise = task_dir.name
        config = json.loads(path.read_text())["files"]
        reason = None
        if language not in AIDER_D or not (task_dir / ".docs/instructions.md").is_file():
            reason = "missing supported language or original instructions"
        elif not config["solution"] or not config["test"] or not all(
            (task_dir / name).is_file() for name in config["solution"] + config["test"]
        ):
            reason = "missing original starter or test"
        records.append({
            "benchmark": "aider", "id": f"{language}/{exercise}", "stratum": language,
            "group": exercise, "solution_files": config["solution"], "test_files": config["test"],
            "exclude": reason,
        })
    return records


def strata(records: list[dict]) -> dict[str, list[dict]]:
    groups = defaultdict(list)
    for record in sorted(records, key=lambda item: order(item["id"])):
        if not record["exclude"]:
            groups[record["stratum"]].append(record)
    return dict(groups)


def assign(records: list[dict], slots: list[tuple[str, str]]) -> list[dict]:
    groups = strata(records)
    used = set()
    selected = []
    for split, stratum in slots:
        pick = next((record for record in groups[stratum] if record["group"] not in used), None)
        if pick is None:
            raise ValueError(f"Insufficient eligible tasks: {split} {stratum}")
        selected.append({**pick, "split": split})
        used.add(pick["group"])
    return selected


def draft_selection(inventory: list[dict], swe_strata_count: int = 5) -> list[dict]:
    by_benchmark = defaultdict(list)
    for record in inventory:
        by_benchmark[record["benchmark"]].append(record)

    swe_repos = sorted(
        (repo for repo, items in strata(by_benchmark["swe"]).items() if len(items) >= 3), key=order,
    )[:swe_strata_count]
    if len(swe_repos) != swe_strata_count:
        raise ValueError(f"The protocol requires {swe_strata_count} SWE-bench repositories")
    swe_slots = [(split, swe_repos[index % len(swe_repos)])
                 for split, count in (("D", 10), ("H", 5)) for index in range(count)]
    swe = assign(by_benchmark["swe"], swe_slots)

    terminal_strata = strata(by_benchmark["terminal"])
    categories = sorted(terminal_strata, key=order)
    counts = Counter()
    terminal_slots = []
    for split, count in (("D", 10), ("H", 5)):
        for _ in range(count):
            eligible = [cat for cat in categories if counts[cat] < len({
                row["group"] for row in terminal_strata[cat]
            })]
            category = min(eligible, key=lambda cat: (counts[cat], order(cat)))
            terminal_slots.append((split, category))
            counts[category] += 1
    terminal = assign(by_benchmark["terminal"], terminal_slots)

    languages = sorted(AIDER_D, key=order)
    aider = assign(by_benchmark["aider"], [
        ("D", language) for language in languages for _ in range(AIDER_D[language])
    ] + [("H", language) for language in languages[:5]])
    return swe + terminal + aider


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--preflight-exclusions", type=Path)
    parser.add_argument("--exclude-strata", type=Path)
    parser.add_argument("--swe-strata-count", type=int, choices=(4, 5), default=5)
    args = parser.parse_args()
    inventory = load_swe(args.sources) + load_terminal(args.sources) + load_aider(args.sources)
    if args.preflight_exclusions:
        exclusions = json.loads(args.preflight_exclusions.read_text())
        for record in inventory:
            key = f"{record['benchmark']}/{record['id']}"
            if key in exclusions:
                record["exclude"] = exclusions.pop(key)
        if exclusions:
            raise ValueError(f"Unknown preflight exclusions: {sorted(exclusions)}")
    if args.exclude_strata:
        excluded_strata = json.loads(args.exclude_strata.read_text())
        found = set()
        for record in inventory:
            key = f"{record['benchmark']}/{record['stratum']}"
            if key in excluded_strata:
                record["exclude"] = record["exclude"] or excluded_strata[key]
                found.add(key)
        if found != set(excluded_strata):
            raise ValueError(f"Unknown strata: {sorted(set(excluded_strata) - found)}")
    result = {
        "stage": "candidate_selection_pending_environment_preflight",
        "revisions": REVISIONS, "seed": SEED, "inventory": inventory, "swe_strata_count": args.swe_strata_count,
        "selected": draft_selection(inventory, args.swe_strata_count),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x") as handle:
        json.dump(result, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    print(Counter((item["benchmark"], item["split"]) for item in result["selected"]))


if __name__ == "__main__":
    main()
