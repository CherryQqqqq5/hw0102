import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--preflights", type=Path, nargs="+", required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    controls = {}
    for root in args.preflights:
        for path in sorted(root.glob("*/preflight.json")):
            result = json.loads(path.read_text())
            controls[result["task"]] = path, result

    counts: dict[str, dict[str, int]] = {}
    outstanding = []
    references = {}
    for task in manifest["selected"]:
        key = task["benchmark"] + "/" + task["split"]
        group = counts.setdefault(key, {"expected": 0, "qualified": 0})
        group["expected"] += 1
        if task["id"] not in controls:
            outstanding.append({"task": task["id"], "status": "missing_controls"})
            continue
        path, result = controls[task["id"]]
        starter = result.get("original_starter", {})
        reference = result.get("upstream_reference", {})
        if (starter.get("scoreable") and starter.get("passed") is False
                and reference.get("scoreable") and reference.get("passed") is True):
            group["qualified"] += 1
            references[task["id"]] = str(path)
        else:
            outstanding.append({"task": task["id"], "status": "control_failed"})
    print(json.dumps({"counts": counts, "outstanding": outstanding}, ensure_ascii=False, indent=2))
    if args.out is not None:
        if outstanding:
            parser.error("Some selected tasks lack valid no-op and reference control outcomes")
        with args.out.open("x", encoding="utf-8") as output:
            json.dump(manifest | {"stage": "frozen", "preflight_paths": references}, output,
                      ensure_ascii=False, indent=2)
            output.write("\n")


if __name__ == "__main__":
    main()
