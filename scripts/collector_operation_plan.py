"""Pure operating-plan decisions and receipt projections. No execution or I/O.

RUN_ELIGIBLE is a simulation result, never an execution authorization.
Qualification and lock/budget evidence must come from existing guarded components.
"""
from datetime import date, datetime, time, timezone
import math
import re
from zoneinfo import ZoneInfo

FORMAT = "mosa2-collector-operation-plan-v1"
ZONE = ZoneInfo("Europe/Berlin")
TERMINAL = {"COMPLETE", "FAILED", "PARTIAL_FAILED", "OUTCOME_UNKNOWN"}
FAILED = {"FAILED", "PARTIAL_FAILED", "OUTCOME_UNKNOWN"}
RUN_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,99}")
ISIN = re.compile(r"[A-Z]{2}[A-Z0-9]{9}[0-9]")


def instant(value):
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError("timestamp")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("timezone")
    return result.astimezone(timezone.utc)


def positive(value):
    return type(value) is int and value > 0


def natural(value):
    return type(value) is int and value >= 0


def selection(values):
    if not isinstance(values, list) or not 1 <= len(values) <= 10:
        raise ValueError("selection")
    if any(not isinstance(v, str) or not ISIN.fullmatch(v) for v in values):
        raise ValueError("selection")
    if len(set(values)) != len(values):
        raise ValueError("duplicate")
    return values


def _configuration(c):
    if set(c) != {
        "format", "execution_enabled", "selection", "max_batch_size", "venue",
        "timezone", "weekdays", "windows", "calendar", "interval_seconds",
        "provider_budget", "max_duration_seconds", "evidence_max_age_seconds",
        "freshness_seconds", "error_policy",
    } or c["format"] != FORMAT or type(c["execution_enabled"]) is not bool:
        raise ValueError("config")
    if c["max_batch_size"] != 10 or type(c["max_batch_size"]) is not int:
        raise ValueError("batch")
    assets = selection(c["selection"])
    if c["timezone"] != "Europe/Berlin" or c["error_policy"] != "STOP_AND_REQUIRE_REVIEW":
        raise ValueError("policy")
    if not isinstance(c["venue"], str) or not re.fullmatch(r"[A-Z0-9]{4}", c["venue"]):
        raise ValueError("venue")
    for name in ("interval_seconds", "max_duration_seconds", "evidence_max_age_seconds", "freshness_seconds"):
        if not positive(c[name]):
            raise ValueError("limits")
    budget = c["provider_budget"]
    if set(budget) != {"per_run", "per_day"} or any(not positive(v) for v in budget.values()):
        raise ValueError("budget")
    if len(assets) > budget["per_run"] or len(assets) > budget["per_day"]:
        raise ValueError("budget")
    weekdays = c["weekdays"]
    if (not isinstance(weekdays, list) or not weekdays or
            any(type(v) is not int or v not in range(5) for v in weekdays) or len(set(weekdays)) != len(weekdays)):
        raise ValueError("weekdays")
    windows = c["windows"]
    if not isinstance(windows, list) or not windows or len(windows) > 10:
        raise ValueError("windows")
    parsed = []
    for w in windows:
        if set(w) != {"start", "end"} or any(not isinstance(v, str) or not re.fullmatch(r"\d{2}:\d{2}", v) for v in w.values()):
            raise ValueError("window")
        start, end = time.fromisoformat(w["start"]), time.fromisoformat(w["end"])
        if start >= end:
            raise ValueError("overnight_not_supported")
        parsed.append((start, end))
    if any(a[1] > b[0] for a, b in zip(sorted(parsed), sorted(parsed)[1:])):
        raise ValueError("overlap")
    cal = c["calendar"]
    if set(cal) != {"approved", "source", "version", "valid_from", "valid_until", "open_dates", "closed_dates"} or cal["approved"] is not True:
        raise ValueError("calendar")
    if any(not isinstance(cal[k], str) or not 1 <= len(cal[k]) <= 200 for k in ("source", "version")):
        raise ValueError("calendar_source")
    lo, hi = date.fromisoformat(cal["valid_from"]), date.fromisoformat(cal["valid_until"])
    if lo > hi:
        raise ValueError("coverage")
    dates = []
    for key in ("open_dates", "closed_dates"):
        raw = cal[key]
        if not isinstance(raw, list) or len(raw) > 3700:
            raise ValueError("calendar_dates")
        values = [date.fromisoformat(v) for v in raw]
        if len(set(values)) != len(values) or any(not lo <= v <= hi for v in values):
            raise ValueError("calendar_dates")
        dates.append(set(values))
    if dates[0] & dates[1]:
        raise ValueError("calendar_conflict")
    return assets, parsed, lo, hi, dates


def decide(config, state, qualification, now, candidate_id):
    """Return only RUN_ELIGIBLE, SKIP or BLOCKED; never create a job or retry."""
    try:
        if not isinstance(config, dict) or config.get("format") != FORMAT:
            return "BLOCKED"
        if config.get("execution_enabled") is False:
            return "SKIP"
        assets, windows, lo, hi, dates = _configuration(config)
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            return "BLOCKED"
        utc = now.astimezone(timezone.utc)
        local = utc.astimezone(ZONE)
        if not isinstance(candidate_id, str) or not RUN_ID.fullmatch(candidate_id):
            return "BLOCKED"
        # Stale/missing evidence never proves absence of a running/unknown job.
        for evidence in (state, qualification):
            age = (utc - instant(evidence["checked_at"])).total_seconds()
            if not 0 <= age <= config["evidence_max_age_seconds"]:
                return "BLOCKED"
        if state["active"] is not False or state["unresolved"] is not False:
            return "BLOCKED"
        seen = state["seen_run_ids"]
        if (not isinstance(seen, list) or len(seen) > 10000 or
                any(not isinstance(v, str) or not RUN_ID.fullmatch(v) for v in seen) or
                len(set(seen)) != len(seen) or candidate_id in seen):
            return "BLOCKED"
        status = state["last_status"]
        if status not in {"IDLE", "COMPLETE"}:
            return "BLOCKED"  # failures require explicit operator review, no automatic retry
        last = state["last_started_at"]
        if (status == "IDLE") != (last is None):
            return "BLOCKED"
        if last is not None:
            elapsed = (utc - instant(last)).total_seconds()
            if elapsed < 0:
                return "BLOCKED"
        if (qualification["contract"] != "mosa2-operation-qualification-v1" or
                qualification["selection"] != assets or qualification["venue"] != config["venue"] or
                qualification["policy"] != "USE_EXISTING_ROUTE" or
                qualification["asset_class"] != "equity" or qualification["all_qualified"] is not True):
            return "BLOCKED"
        # This is an injected complete-scope attestation of existing qualify()/runtime checks.
        if state["provider_budget_date"] != local.date().isoformat() or not natural(state["provider_requests_used"]):
            return "BLOCKED"
        if state["provider_requests_used"] + len(assets) > config["provider_budget"]["per_day"]:
            return "BLOCKED"
        day = local.date()
        if not lo <= day <= hi:
            return "BLOCKED"
        if day.weekday() not in config["weekdays"] or day in dates[1]:
            return "SKIP"
        if day not in dates[0]:
            return "BLOCKED"  # no implicit holiday/weekday permission
        wall = local.time().replace(tzinfo=None)
        if not any(start <= wall < end for start, end in windows):
            return "SKIP"
        if last is not None and elapsed < config["interval_seconds"]:
            return "SKIP"
        return "RUN_ELIGIBLE"
    except (KeyError, ValueError, TypeError, AttributeError, OverflowError):
        return "BLOCKED"


def number(value):
    return value if type(value) in (int, float) and math.isfinite(value) and value >= 0 else None


def project_receipt(envelope, now, freshness_seconds):
    """Allowlisted view of existing batch receipts, supplied in memory.

    Envelope timestamps are receipt metadata, not market timestamps. Missing
    market timestamps remain UNKNOWN. Never expose paths, raw errors or secrets.
    """
    invalid = {"status": "OUTCOME_UNKNOWN", "last_error_code": "INVALID_RECEIPT"}
    try:
        run_id = envelope["run_id"]
        if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
            return invalid.copy()
        start = instant(envelope["started_at"])
        if now.tzinfo is None or start > now:
            return invalid.copy()
        receipt = envelope["receipt"]
        batch = receipt.get("batch", receipt)
        status = batch["overall_status"]
        if status == "FAILED_BEFORE_FIRST_COMMIT":
            status = "FAILED"
        if status not in TERMINAL:
            return invalid.copy()
        end = envelope.get("completed_at")
        if end is not None and not start <= instant(end) <= now:
            return invalid.copy()
        if status == "COMPLETE" and end is None:
            return invalid.copy()
        items = batch.get("item_results", [])
        if not isinstance(items, list) or len(items) > 10:
            return invalid.copy()
        projected = []
        provider_errors = 0
        for item in items:
            identity = item["asset_identity"]
            if not isinstance(identity, str) or not ISIN.fullmatch(identity):
                return invalid.copy()
            metrics = item.get("metrics", {})
            writer = item.get("writer")
            if writer not in {None, "INSERT", "DUPLICATE_UNCHANGED"}:
                return invalid.copy()
            item_status = item.get("status")
            if item_status not in {"COMPLETE", "FAILED", "OUTCOME_UNKNOWN", "NOT_STARTED"}:
                return invalid.copy()
            provider_failed = item.get("failure_stage") in {"provider", "acquisition"}
            provider_errors += int(provider_failed)
            # Existing receipts do not necessarily include market timestamps.
            market = item.get("market_at")
            freshness = "UNKNOWN"
            if market is not None and positive(freshness_seconds):
                age = (now - instant(market)).total_seconds()
                freshness = "UNKNOWN" if age < 0 else ("STALE" if age > freshness_seconds else "FRESH")
            observation = item.get("observation_id")
            if observation is not None and not positive(observation):
                return invalid.copy()
            projected.append({
                "isin": identity, "status": item_status, "writer": writer,
                "observation_id": observation,
                "collector_ms": number(metrics.get("collector_ms")),
                "provider_ms": number(metrics.get("provider_ms")),
                "database_check_ms": number(metrics.get("database_check_ms")),
                "data_freshness": freshness,
            })
        if any(i["status"] == "OUTCOME_UNKNOWN" for i in projected):
            status = "OUTCOME_UNKNOWN"
        if status == "COMPLETE" and (not items or any(i["status"] != "COMPLETE" for i in projected)):
            return invalid.copy()
        provider_unknown = any(i.get("status") == "FAILED" and i.get("failure_stage") not in {"provider", "acquisition", "writer", "readback", "preflight", "batch_validation"} for i in items)
        counts = {}
        for key in ("requested_count", "started_count", "completed_count", "provider_requests", "insert_count", "duplicate_unchanged_count"):
            value = batch.get(key)
            counts[key] = value if natural(value) else None
        return {
            "run_id": run_id, "started_at": start.isoformat(),
            "completed_at": instant(end).isoformat() if end is not None else None,
            "status": status, **counts, "assets": projected,
            "provider_errors": None if provider_unknown else provider_errors, "batch_ms": number(batch.get("local_batch_ms")),
            "last_error_code": ("OUTCOME_UNKNOWN" if status == "OUTCOME_UNKNOWN" else
                                "PROVIDER_ERROR" if provider_errors else
                                "BATCH_FAILED" if status in FAILED else None),
        }
    except (KeyError, ValueError, TypeError, AttributeError, OverflowError):
        return invalid.copy()


def monitoring(envelopes, now, freshness_seconds):
    """Summarize bounded receipts; unresolved evidence is never hidden by success."""
    if not isinstance(envelopes, list) or len(envelopes) > 1000:
        return {"status": "OUTCOME_UNKNOWN", "last_error_code": "INVALID_RECEIPT"}
    rows = [project_receipt(e, now, freshness_seconds) for e in envelopes]
    valid = sorted((r for r in rows if "started_at" in r), key=lambda r: instant(r["started_at"]))
    successful = [r for r in valid if r["status"] == "COMPLETE"]
    uncertain = any(r["status"] == "OUTCOME_UNKNOWN" for r in rows)
    last = valid[-1] if valid else None
    return {
        "last_started_run": last,
        "last_successful_run": successful[-1] if successful else None,
        "status": "OUTCOME_UNKNOWN" if uncertain else (last["status"] if last else "NOT_STARTED"),
        "last_error_code": "OUTCOME_UNKNOWN" if uncertain else (last["last_error_code"] if last else None),
        "execution_authorized": False,
    }
