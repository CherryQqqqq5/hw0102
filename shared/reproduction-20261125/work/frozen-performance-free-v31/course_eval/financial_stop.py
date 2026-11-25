import fcntl
import functools
import hashlib
import json
import os
from pathlib import Path


def free_query_blocked(stop_path, model_id):
    admission_path = Path(os.environ["COURSE_PARALLEL_FREE_ADMISSION"])
    if hashlib.sha256(admission_path.read_bytes()).hexdigest() != os.environ["COURSE_PARALLEL_FREE_ADMISSION_SHA256"]:
        raise RuntimeError("The exact separately approved free-channel admission changed")
    admission = json.loads(admission_path.read_text())
    if model_id not in admission["allowed_models"]:
        raise RuntimeError("This parallel route is not an explicitly fixed verified-free model")
    raw = Path(stop_path).read_bytes()
    stop = json.loads(raw)
    if stop["active"] is False:
        return False
    return not (hashlib.sha256(raw).hexdigest() == admission["accepted_quota_stop_sha256"]
        and stop.get("quota_pause") and stop["pending_unverified_calls"] == 0
        and stop["unresolved_fee_stops"] == []
        and stop["accepted_total_unknown_calls"] == admission["historical_unknown_calls"])


def canonical_claim(details):
    if not details.get("run_dir"):
        return {"run_dir": None, "unverified_requests": list(details.get("unverified_requests", [])),
            "reason": details.get("reason", "Free-service eligibility could not be verified before dispatch")}
    directory = Path(details["run_dir"])
    request_ids = list(details.get("unverified_requests", []))
    traces = list(directory.rglob("model.jsonl")) if directory.exists() else []
    matching = []
    for trace in traces:
        events = [json.loads(line) for line in trace.read_text().splitlines()]
        actual = {row["request_id"] for row in events if row["event"] == "request"}
        if set(request_ids) <= actual:
            matching.append(trace)
    # 外层任务与内层 agent 对同一次实际请求只登记一次；多条轨迹不猜测归属。
    run_dir = str(matching[0].parent.resolve()) if len(matching) == 1 else str(directory.resolve())
    return {"run_dir": run_dir, "unverified_requests": request_ids,
        "reason": details.get("reason", "An actual request has unverified financial evidence")}


def preserve_free_stop(stop_path, **details):
    stop_path = Path(stop_path)
    with stop_path.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        stop = json.loads(stop_path.read_text())
        accepted = stop.get("accepted_total_unknown_calls", stop["historical_unknown_calls"])
        if type(accepted) is not int or accepted < 0:
            raise ValueError("The accepted historical unknown count must remain explicit")
        pending = list(stop.get("unresolved_fee_stops", [])) if stop["active"] else []
        if stop["active"] and not pending and not (stop.get("quota_pause") and stop.get("pending_unverified_calls") == 0):
            pending.append({key: stop[key] for key in ("run_dir", "unverified_requests", "reason") if key in stop})
        claim = canonical_claim(details)
        identity = lambda row: (row.get("run_dir"), tuple(row.get("unverified_requests", [])))
        if not any(identity(row) == identity(claim) for row in pending):
            pending.append(claim)
        stop.update(active=True, historical_unknown_calls=accepted, accepted_total_unknown_calls=accepted,
            unresolved_fee_stops=pending, pending_unverified_calls=sum(len(row["unverified_requests"]) for row in pending),
            **pending[0])
        temporary = stop_path.with_suffix(".writing")
        temporary.write_text(json.dumps(stop, ensure_ascii=False, indent=2) + "\n")
        temporary.replace(stop_path)


def stop_path_for(model):
    if hasattr(model, "stop_path"):
        return Path(model.stop_path)
    return Path(os.environ["COURSE_FREE_STOP_PATH"])


def guard_actual_receipt(method):
    @functools.wraps(method)
    def guarded(model, *args, **kwargs):
        try:
            return method(model, *args, **kwargs)
        except Exception:
            trace = Path(model.trace)
            events = [json.loads(line) for line in trace.read_text().splitlines()] if trace.exists() else []
            current = [row for row in events if row.get("request_id") == model.request_id]
            if (any(row["event"] == "request" for row in current)
                    and not any(row["event"] == "billing_verified" for row in current)):
                preserve_free_stop(stop_path_for(model), run_dir=str(trace.parent),
                    unverified_requests=[model.request_id],
                    reason="The current actual model request lacks its own valid financial evidence")
            raise
    return guarded


def guard_free_query(method):
    checked = guard_actual_receipt(method)
    @functools.wraps(method)
    def guarded(model, *args, **kwargs):
        if free_query_blocked(stop_path_for(model), model.model_id):
            raise RuntimeError("No new actual model request: the shared financial stop is active")
        return checked(model, *args, **kwargs)
    return guarded
