"""CLI decision bridge for the schema-4 scheduler; no provider or database I/O."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import collector_cycle as cycle, collector_operation_plan as operation


def decide(data):
    blocked = {"decision": "BLOCKED", "reason": "INVALID_EVIDENCE"}
    try:
        config, budget = data["operation_config"], data["budget_config"]
        if config.get("execution_enabled") is not True or budget.get("execution_enabled") is not True:
            return {"decision": "SKIP", "reason": "DISABLED"}
        now = operation.instant(data["now"])
        tick = now.replace(second=0, microsecond=0)
        records = data["records"]
        if not isinstance(records, list) or len(records) > 10000:
            return blocked
        selection = operation.selection(config["selection"])
        day = tick.astimezone(operation.ZONE).date()
        used_day = used_60s = 0
        last = None
        seen = []
        for row in records:
            # Any interrupted, failed or foreign run requires manual review, even on a later day.
            if row["status"] != "completed" or row["attempt_no"] != 1:
                return {"decision": "BLOCKED", "reason": "PREDECESSOR_UNRESOLVED"}
            summary = row["summary"]
            if summary["contract"] != "mosa2-scheduler-v1":
                return blocked
            envelope = summary["envelope"]
            receipt = operation.project_receipt(envelope, now, config["freshness_seconds"])
            if receipt["status"] != "COMPLETE":
                return blocked
            start, end = operation.instant(row["started_at"]), operation.instant(row["finished_at"])
            if start > end or end > now or operation.instant(envelope["started_at"]) != start or operation.instant(envelope["completed_at"]) != end:
                return blocked
            slot = operation.instant(summary["slot"])
            if slot.second or slot.microsecond or not slot <= start < slot+timedelta(minutes=1):
                return blocked
            run_id = "cycle-" + slot.strftime("%Y%m%dt%H%M%Sz")
            if envelope["run_id"] != run_id or run_id in seen:
                return blocked
            seen.append(run_id)
            count = summary["reserved_requests"]
            if not operation.positive(count) or count > 10:
                return blocked
            if start.astimezone(operation.ZONE).date() == day:
                used_day += count
            if tick-timedelta(seconds=60) < start <= now:
                used_60s += count
            if last is None or start > operation.instant(last["started_at"]):
                last = envelope
        evidence = deepcopy(data["evidence"])
        # Own usage and predecessor claims always come from durable DB runs, never the private sidecar.
        stamp = tick.isoformat()
        # External MOSA/monitoring evidence must be fresh at invocation, including cron jitter.
        # Rebase only validated check timestamps to the slot used by the pure model.
        for key in ("budget_state", "mosa_baseline", "monitoring_previous", "monitoring_event"):
            item = evidence[key]
            age = (now-operation.instant(item["checked_at"])).total_seconds()
            limit = min(config["evidence_max_age_seconds"],
                        budget["providers"][data["provider"]]["limits"]["evidence_max_age_seconds"])
            if not 0 <= age <= limit:
                return blocked
            item["checked_at"] = stamp
        own = evidence["budget_state"]
        if own["budget_date"] != day.isoformat() or any(not operation.natural(own[k]) for k in ("used_60s", "used_day", "in_flight")):
            return blocked
        # External evidence may be more conservative (other authorized MOSA-2 activity).
        # Never erase its reported usage or in-flight work.
        used_day = max(used_day, own["used_day"])
        used_60s = max(used_60s, own["used_60s"])
        evidence["operation_state"] = dict(
            checked_at=stamp, active=False, unresolved=False, seen_run_ids=seen,
            last_status="COMPLETE" if last else "IDLE",
            last_started_at=last["started_at"] if last else None,
            last_completed_at=last["completed_at"] if last else None,
            provider_budget_date=day.isoformat(), provider_requests_used=used_day)
        evidence["receipts"] = [last] if last else []
        state = evidence["budget_state"]
        state.update(checked_at=stamp, budget_date=day.isoformat(), used_60s=used_60s,
                     used_day=used_day)
        evidence["qualification"] = deepcopy(data["qualification"])
        evidence["qualification"]["checked_at"] = stamp
        # cycle() is deliberately a pure model. Its disabled simulation view cannot
        # authorize execution: the two original switches above are mandatory.
        model_config, model_budget = deepcopy(config), deepcopy(budget)
        model_config["execution_enabled"] = model_budget["execution_enabled"] = False
        result = cycle.cycle(model_config, model_budget, evidence, tick, provider_key=data["provider"])
        return {k: result.get(k) for k in ("decision", "reason", "cycle_id", "scheduled_at", "interval_seconds")}
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
        return blocked


if __name__ == "__main__":
    try:
        result = decide(json.loads(sys.stdin.read(1048577)))
    except Exception:
        result = {"decision": "BLOCKED", "reason": "INVALID_EVIDENCE"}
    print(json.dumps(result))
