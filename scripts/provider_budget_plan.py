"""Offline provider-load model and MOSA-2-only circuit contract. No starter/I/O.

Internal test budgets are not provider rate limits or rights. No request is sent,
no live reservation is acquired, and no MOSA state is mutated by this module.
"""
from datetime import datetime, time, timedelta, timezone
from email.utils import parsedate_to_datetime
from scripts.collector_operation_plan import ZONE, instant, natural, positive, number

FORMAT = "mosa2-provider-budget-plan-v1"


def cadence_seconds(now, *, holiday):
    """Proposed cadence, NOT an authorization; unknown calendar blocks modelling."""
    if not isinstance(now, datetime) or now.tzinfo is None or type(holiday) is not bool:
        return None
    local = now.astimezone(ZONE)
    return 60 if local.weekday() < 5 and not holiday and local.hour >= 6 else 900


def day_load(day, *, holiday, assets=5):
    """Exact scheduled slots in one Berlin civil day, including DST weekends.

    Count aligned minute/quarter-hour slots; no catch-up, retries or FX requests.
    """
    if not positive(assets) or assets > 10 or type(holiday) is not bool:
        raise ValueError("invalid simulation scope")
    start = datetime.combine(day, time(), ZONE).astimezone(timezone.utc)
    end = datetime.combine(day + timedelta(days=1), time(), ZONE).astimezone(timezone.utc)
    cursor = start
    runs = 0
    while cursor < end:
        local = cursor.astimezone(ZONE)
        interval = cadence_seconds(cursor, holiday=holiday)
        if interval == 60 or local.minute % 15 == 0:
            runs += 1
        cursor += timedelta(minutes=1)
    return {"runs": runs, "requests": runs * assets, "per_provider": {"boerse_frankfurt_api_v1": runs * assets}}


def admission(config, provider, state, baseline, *, planned_requests, now):
    """Pure simulation; future adapter must reserve atomically under existing lock."""
    def result(decision, reason):
        return {"decision": decision, "reason": reason, "scope": "MOSA2",
                "execution_authorized": False}
    try:
        if config["format"] != FORMAT:
            return result("BLOCKED", "INVALID_CONTRACT")
        if config["execution_enabled"] is False:
            return result("SKIP", "DISABLED")
        if config["execution_enabled"] is not True:
            return result("BLOCKED", "INVALID_CONTRACT")
        p = config["providers"][provider]
        if p["rights_confirmed"] is not True:
            return result("BLOCKED", "RIGHTS_UNCONFIRMED")
        if p["automatic_retries"] != 0 or p["automatic_resume"] is not False:
            return result("BLOCKED", "UNSAFE_POLICY")
        limits = p["limits"]
        if not all(positive(limits[k]) for k in limits):
            return result("BLOCKED", "BUDGET_UNAPPROVED")
        if limits["mosa2_parallel"] != 1 or not positive(planned_requests) or planned_requests > min(5, limits["mosa2_per_run"]):
            return result("BLOCKED", "SCOPE_OR_CONCURRENCY")
        if state["stop_latched"] is not False or state["unresolved"] is not False:
            return result("BLOCKED", "MOSA2_STOPPED")
        utc = now.astimezone(timezone.utc)
        if now.tzinfo is None:
            return result("BLOCKED", "INVALID_TIME")
        for evidence in (state, baseline):
            age = (utc - instant(evidence["checked_at"])).total_seconds()
            if not 0 <= age <= limits["evidence_max_age_seconds"]:
                return result("BLOCKED", "BASELINE_UNKNOWN")
            if evidence["provider"] != provider or evidence["budget_date"] != utc.astimezone(ZONE).date().isoformat():
                return result("BLOCKED", "BASELINE_UNKNOWN")
            if not all(natural(evidence[k]) for k in ("used_60s", "used_day", "in_flight")):
                return result("BLOCKED", "BASELINE_UNKNOWN")
        if baseline["healthy"] is not True or state["mosa_impact"] is not False:
            return result("BLOCKED", "MOSA_BASELINE_OR_IMPACT")
        if state["in_flight"] >= limits["mosa2_parallel"]:
            return result("SKIP", "MOSA2_BUSY")
        if baseline["in_flight"] + state["in_flight"] + 1 > limits["combined_parallel"]:
            return result("SKIP", "MOSA_PRIORITY")
        for usage, own, combined in (
            ("used_60s", "mosa2_per_60s", "combined_per_60s"),
            ("used_day", "mosa2_per_day", "combined_per_day"),
        ):
            if state[usage] + planned_requests > limits[own]:
                return result("BLOCKED", "MOSA2_BUDGET")
            if baseline[usage] + state[usage] + planned_requests > limits[combined]:
                return result("BLOCKED", "COMBINED_BUDGET")
        return result("RUN_ELIGIBLE", "SIMULATION_ONLY")
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
        return result("BLOCKED", "INVALID_EVIDENCE")


def retry_after(value, now):
    """Only advisory not-before; never resumes a stopped circuit."""
    try:
        if not isinstance(value, str) or len(value) > 128 or now.tzinfo is None:
            return None
        if value.isascii() and value.isdecimal():
            seconds = int(value)
            if seconds > 31536000:
                return None
            until = now + timedelta(seconds=seconds)
        else:
            until = parsedate_to_datetime(value)
            if until.tzinfo is None:
                return None
        return max(now, until).astimezone(timezone.utc).isoformat()
    except (ValueError, TypeError, OverflowError, AttributeError):
        return None


def observe(policy, previous, event, *, now):
    """Bounded synthetic monitoring projection, sticky stop, closed output fields.

    Caller must supply a fresh per-provider window; no response bodies, URLs,
    headers, exception text or secret values are copied into the projection.
    """
    safe = {"scope": "MOSA2", "stop_latched": True, "reason": "INVALID_EVIDENCE",
            "retry_not_before": None, "requires_manual_review": True,
            "automatic_retry": False, "execution_authorized": False}
    try:
        window = policy["window_size"]
        if not positive(window) or window > 100:
            return safe
        if any(not positive(policy[k]) for k in ("min_samples", "consecutive_error_stop", "latency_ms_stop", "stale_seconds")):
            return safe
        ratio = policy["error_ratio_stop"]
        if number(ratio) is None or not 0 < ratio <= 1 or policy["min_samples"] > window:
            return safe
        samples = previous["errors"]
        if (not isinstance(samples, list) or len(samples) > window or
                any(type(v) is not bool for v in samples) or
                type(previous["stop_latched"]) is not bool or not natural(previous["consecutive_errors"])):
            return safe
        status = event["http_status"]
        if status is not None and (type(status) is not int or not 100 <= status <= 599):
            return safe
        if any(type(event[k]) is not bool for k in ("timeout", "network_error", "blocked_signal", "valid_payload", "mosa_impact")):
            return safe
        error = (event["timeout"] or event["network_error"] or
                 status is None or not 200 <= status < 300 or not event["valid_payload"])
        samples = (samples + [error])[-window:]
        consecutive = previous["consecutive_errors"] + 1 if error else 0
        age = number(event.get("data_age_seconds"))
        latency = number(event.get("latency_ms"))
        duplicate = event.get("dedupe_decision")
        if duplicate not in (None, "INSERT", "DUPLICATE_UNCHANGED", "CONFLICT", "REJECT"):
            return safe
        reason = "HEALTHY"
        until = None
        if previous["stop_latched"]:
            reason = "STOP_LATCHED"
            prior = previous.get("retry_not_before")
            # Only preserve a valid canonical timestamp, never arbitrary strings.
            if prior is not None:
                until = instant(prior).isoformat()
        elif status == 429:
            reason = "HTTP_429"
            until = retry_after(event.get("retry_after"), now)
        elif status in (401, 403) or event["blocked_signal"]:
            reason = "ACCESS_BLOCKED"
        elif event["mosa_impact"]:
            reason = "MOSA_IMPACT"
        elif duplicate in ("CONFLICT", "REJECT"):
            reason = "DATA_INTEGRITY"
        elif latency is not None and latency > policy["latency_ms_stop"]:
            reason = "LATENCY"
        elif consecutive >= policy["consecutive_error_stop"]:
            reason = "ERROR_TREND"
        elif len(samples) >= policy["min_samples"] and sum(samples) / len(samples) >= ratio:
            reason = "ERROR_TREND"
        stopped = reason != "HEALTHY"
        return {
            "scope": "MOSA2", "stop_latched": stopped, "reason": reason,
            "retry_not_before": until, "requires_manual_review": stopped,
            "automatic_retry": False, "execution_authorized": False,
            "http_status": status, "errors": samples, "consecutive_errors": consecutive,
            "latency_ms": latency, "data_age_seconds": age,
            "freshness": "UNKNOWN" if age is None else ("STALE" if age > policy["stale_seconds"] else "FRESH"),
            "dedupe_decision": duplicate,
        }
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
        return safe
