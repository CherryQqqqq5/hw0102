import fcntl
import functools
import json
import os
from pathlib import Path


def preserve_free_stop(stop_path, **details):
    stop_path = Path(stop_path)
    with stop_path.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        stop = json.loads(stop_path.read_text())
        accepted = stop.get("accepted_total_unknown_calls", stop["historical_unknown_calls"])
        if type(accepted) is not int or accepted < 0:
            raise ValueError("The accepted historical unknown count must remain explicit")
        pending = list(stop.get("unresolved_fee_stops", [])) if stop["active"] else []
        if stop["active"] and not pending:
            pending.append({key: stop[key] for key in ("run_dir", "unverified_requests", "reason") if key in stop})
        claim = {"run_dir": details.get("run_dir"),
            "unverified_requests": details.get("unverified_requests", []),
            "reason": details.get("reason", "An actual request has unverified financial evidence")}
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
        if json.loads(stop_path_for(model).read_text())["active"]:
            raise RuntimeError("No new actual model request: the shared financial stop is active")
        return checked(model, *args, **kwargs)
    return guarded
