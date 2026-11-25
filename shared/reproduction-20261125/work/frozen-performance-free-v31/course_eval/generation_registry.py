import fcntl
import hashlib
import json
import os
from pathlib import Path


def claim_generation(generation_id, model, trace, request_id):
    seed_path = Path(os.environ["COURSE_FREE_GENERATION_SEED"])
    seed_sha = hashlib.sha256(seed_path.read_bytes()).hexdigest()
    if seed_sha != os.environ["COURSE_FREE_GENERATION_SEED_SHA256"]:
        raise ValueError("The historical native generation identity seed changed")
    seeds = json.loads(seed_path.read_text())
    registry = Path(os.environ["COURSE_FREE_GENERATION_REGISTRY"])
    with registry.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        current = json.loads(registry.read_text()) if registry.exists() else {"seed_sha256": seed_sha, "generations": {}}
        if current["seed_sha256"] != seed_sha:
            raise ValueError("The shared actual-generation registry belongs to another history")
        if generation_id in seeds["generation_ids"] or generation_id in current["generations"]:
            raise ValueError("The native generation identity was already consumed in a prior or concurrent trial")
        current["generations"][generation_id] = {"model": model, "trace": str(Path(trace).resolve()), "request_id": request_id}
        temporary = registry.with_suffix(".writing")
        temporary.write_text(json.dumps(current, indent=2) + "\n")
        temporary.replace(registry)
