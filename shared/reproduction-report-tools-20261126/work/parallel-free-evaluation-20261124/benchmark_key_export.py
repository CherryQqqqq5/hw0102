import base64
import hashlib
import json
from pathlib import Path
import re
import shutil

from course_eval.export_revision import HOME_PATH, LOG_NAMES, PRIVATE, PRIVATE_PEM, SECRET


ARTIFACTS = ["/app/ssl/server.key", "/app/ssl/server.crt", "/app/ssl/server.pem",
    "/app/ssl/verification.txt", "/app/check_cert.py"]
KEY_PATHS = {"/app/ssl/server.key", "/app/ssl/server.pem"}
PUBLIC_CERT = re.compile(r"-----BEGIN CERTIFICATE-----\s+[A-Za-z0-9+/=\s]+-----END CERTIFICATE-----\s*")
MARKER = "[REDACTED BENCHMARK PRIVATE KEY]"
APPROVED_RUNS = {
    "work/vmshare/performance75-hy4-sql-layout-v18-main-20261125/openssl-selfsigned-cert-C0-r1": {
        "trial": "73a2cd0eb231814873b1e74121db93199a20b6f358bc96ad485679a1458344ab",
        "protocol": "45853ec9c5e8173c25aaf503539ac18880346d443ba104d6cd2a604d356b9327",
        "candidates": {"openssl-selfsigned-cert__Aqci8FH/agent/candidates/candidate-001.json":
            "784335ea1e567d0f9c06dc9996ceb1b86020712aff5609fd0b62e56f934600e3"}},
    "work/vmshare/performance75-hy4-sql-layout-v18-repeat-20261125/openssl-selfsigned-cert-C0-r2": {
        "trial": "73a2cd0eb231814873b1e74121db93199a20b6f358bc96ad485679a1458344ab",
        "protocol": "45853ec9c5e8173c25aaf503539ac18880346d443ba104d6cd2a604d356b9327",
        "candidates": {
            "openssl-selfsigned-cert__pT76fts/agent/candidates/candidate-001.json":
                "f20f2e965def73c147d15264afb8a1016f98e3a6ad9ae5aaced7032ee74aba33",
            "openssl-selfsigned-cert__pT76fts/agent/candidates/candidate-002.json":
                "6351281f54138bcf5bf0dfe1aaa94cf48d0918b8d9402b03e13e8861ac1861c7"}},
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def candidate_projection(raw):
    record = json.loads(raw)
    if "export_redactions" in record:
        raise ValueError("An original candidate must not already be a filtered export")
    redactions = []
    for name, item in record["files"].items():
        original = base64.b64decode(item.get("data", ""), validate=True)
        text = original.decode("utf-8", errors="strict")
        matches = list(PRIVATE_PEM.finditer(text))
        if matches:
            remainder = PRIVATE_PEM.sub("", text).strip()
            if (name not in KEY_PATHS or len(matches) != 1
                    or (name.endswith(".key") and remainder)
                    or (name.endswith(".pem") and PUBLIC_CERT.fullmatch(remainder) is None)):
                raise ValueError("Private material is outside the exact benchmark key/certificate shape: " + name)
            filtered = PRIVATE_PEM.sub(MARKER, text)
            encoded = filtered.encode("utf-8")
            item["data"] = base64.b64encode(encoded).decode("ascii")
            redactions.append({"artifact": name, "source_sha256": sha(original),
                "source_bytes": len(original), "export_sha256": sha(encoded),
                "export_bytes": len(encoded), "byte_identical": False,
                "replayable": False, "removed_private_pem_blocks": 1})
        else:
            filtered = text
        if any(pattern.search(filtered) for pattern in (SECRET, PRIVATE, HOME_PATH)):
            raise ValueError("Unrelated sensitive candidate material remains: " + name)
    if redactions:
        record["export_redactions"] = {"format": "benchmark_private_pem_redaction_v1",
            "original_snapshot_sha256": sha(raw), "original_snapshot_replayable_from_export": False,
            "original_artifact_digest": record["artifact_digest"],
            "retained_artifact_digest_describes": "unfiltered_source_only",
            "files": redactions,
            "scope": "Original scores, digests, modes, eligibility and verification claims are retained. Only the generated private PEM is omitted; this filtered snapshot cannot restore the original key bytes."}
        return (json.dumps(record, ensure_ascii=False, indent=2) + "\n").encode(), record["export_redactions"]
    return raw, None


def prepare_filtered_source(source, stage):
    approved = APPROVED_RUNS.get(str(source.resolve().relative_to(Path.cwd())))
    candidate_hashes = {str(path.relative_to(source)): sha(path.read_bytes())
        for path in source.rglob("*") if path.is_file() and "candidates" in path.relative_to(source).parts}
    if (approved is None or sha((source / "trial.json").read_bytes()) != approved["trial"]
            or sha(source.with_suffix(".protocol.json").read_bytes()) != approved["protocol"]
            or candidate_hashes != approved["candidates"]):
        raise ValueError("This source is outside the reviewed closed benchmark run/candidate hashes")
    task = json.loads((source / "trial.json").read_text())["task"]
    scope = task.get("candidate_scope") or {}
    if (task["id"] != "openssl-selfsigned-cert" or task["benchmark"] != "terminal"
            or task["image"] != "alexgshaw/openssl-selfsigned-cert:20251031"
            or scope.get("kind") != "files" or scope.get("artifacts") != ARTIFACTS
            or scope.get("protected") != []):
        raise ValueError("Benchmark private-key filtering requires the exact frozen certificate task")
    expected, redactions = set(), []
    for original in sorted(source.rglob("*")):
        relative = original.relative_to(source)
        if not original.is_file() or original.is_symlink():
            continue
        if {"starter", "grader-input", "_python", "_deps", "solution", "tests"}.intersection(relative.parts):
            continue
        if original.name not in LOG_NAMES and not {"candidate", "candidates"}.intersection(relative.parts):
            continue
        destination = stage / relative
        if any(parent.is_symlink() for parent in destination.parents) or destination.is_symlink():
            raise ValueError("The filtered staging path contains a symbolic link")
        raw, metadata = original.read_bytes(), None
        if "candidates" in relative.parts:
            raw, metadata = candidate_projection(raw)
        if metadata:
            redactions.append({"path": str(relative), **metadata})
        if destination.exists():
            if destination.read_bytes() != raw:
                raise ValueError("An earlier filtered staging member differs from its original projection")
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            if metadata:
                destination.write_bytes(raw)
            else:
                shutil.copyfile(original, destination)
        expected.add(relative)
    if {path.relative_to(stage) for path in stage.rglob("*") if path.is_file()} != expected:
        raise ValueError("The filtered staging directory contains an unexpected member")
    return redactions
