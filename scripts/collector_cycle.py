"""Pure composition of existing operation, budget and monitoring contracts.

No scheduler, transport, database, process, reservation or persistent state.
RUN_ELIGIBLE is always a simulation; all execution capabilities remain absent.
"""
from datetime import datetime, timezone
from scripts import collector_operation_plan as operation
from scripts import provider_budget_plan as budget

PROVIDER = "boerse_frankfurt_api_v1"


def cycle(operation_config, budget_config, evidence, now):
    result = dict(simulation_only=True, execution_authorized=False, atomic_reservation=False,
                  decision="BLOCKED", reason="INVALID_EVIDENCE", evaluated_at=None, scheduled_at=None,
                  interval_seconds=None, assets=[], expected_provider_requests=0, actual_provider_requests=0,
                  max_parallel=1, requests_per_asset=1, automatic_retries=0, automatic_resume=False,
                  budget_decision="BLOCKED", budget_reason="INVALID_EVIDENCE", next_theoretical_at=None,
                  stop_latched=True, monitor_reason="INVALID_EVIDENCE", retry_not_before=None)
    try:
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            return result
        utc = now.astimezone(timezone.utc)
        result["evaluated_at"] = utc.isoformat()
        if (operation_config.get("execution_enabled") is not False or
                budget_config.get("execution_enabled") is not False):
            result["reason"] = "EXECUTION_MUST_REMAIN_DISABLED"
            return result
        if operation_config.get("format") != operation.FORMAT_V2:
            result["reason"] = "EXPLICIT_V2_POLICY_REQUIRED"
            return result
        assets = operation.selection(operation_config["selection"])
        if len(assets) != 5:
            result["reason"] = "FIVE_ASSET_SCOPE_REQUIRED"
            return result
        result.update(assets=list(assets), expected_provider_requests=len(assets))
        holiday = operation.calendar_holiday(operation_config, utc)
        interval = budget.cadence_seconds(utc, holiday=holiday)
        result["interval_seconds"] = interval
        upcoming = operation.next_slot(operation_config, utc)
        result["next_theoretical_at"] = upcoming.isoformat() if upcoming else None
        if interval is None:
            result["reason"] = "CONFIGURATION_OR_CALENDAR_UNKNOWN"
            return result
        due = operation.is_slot(utc, holiday=holiday)
        result["scheduled_at"] = utc.isoformat() if due else None
        candidate = "cycle-" + utc.strftime("%Y%m%dt%H%M%Sz")
        result["cycle_id"] = candidate
        state, baseline = evidence["budget_state"], evidence["mosa_baseline"]
        provider = budget_config["providers"][PROVIDER]
        admission = budget.admission(budget_config, PROVIDER, state, baseline,
                                     planned_requests=len(assets), now=utc, simulation=True)
        result.update(budget_decision=admission["decision"], budget_reason=admission["reason"])
        # The v1 budget API historically models internal limits. The common gate
        # additionally requires actual documented provider-limit evidence.
        limit = provider["documented_provider_limit"]
        documented = (isinstance(limit, dict) and isinstance(limit.get("evidence_ref"), str) and
                      1 <= len(limit["evidence_ref"]) <= 200 and
                      all(operation.positive(limit.get(k)) for k in ("per_60s", "per_day", "parallel")))
        if documented:
            limits = provider["limits"]
            documented = all(operation.positive(limits.get(key)) and limits[key] <= limit[field]
                             for key, field in (("combined_per_60s", "per_60s"),
                                                ("combined_per_day", "per_day"),
                                                ("combined_parallel", "parallel")))
        proposal = budget_config["proposal"]
        if proposal["calendar_approved"] is not True:
            result["reason"] = "CALENDAR_PROPOSAL_UNCONFIRMED"
            return result
        if (proposal["timezone"] != "Europe/Berlin" or proposal["assets"] != 5 or
                proposal["weekday_fast_window"] != ["06:00", "24:00"] or
                proposal["weekday_fast_seconds"] != 60 or proposal["night_weekend_holiday_seconds"] != 900):
            result["reason"] = "CONFLICTING_SCHEDULE_PROPOSAL"
            return result
        previous, event = evidence["monitoring_previous"], evidence["monitoring_event"]
        for item in (previous, event):
            age = (utc-operation.instant(item["checked_at"])).total_seconds()
            if not 0 <= age <= operation_config["evidence_max_age_seconds"]:
                result["reason"] = "MONITORING_UNKNOWN"
                return result
        if type(event["provenance_conflict"]) is not bool:
            return result
        observed = dict(event)
        if event["provenance_conflict"]:
            observed["dedupe_decision"] = "CONFLICT"
        monitor = budget.observe(provider["monitoring"], previous, observed, now=utc, strict=True)
        receipts = operation.monitoring(evidence["receipts"], utc, operation_config["freshness_seconds"])
        op_state = evidence["operation_state"]
        if op_state["provider_requests_used"] != state["used_day"]:
            result["reason"] = "COUNTER_CONFLICT"
            return result
        if receipts["status"] in operation.FAILED or op_state["last_status"] in operation.FAILED:
            monitor = dict(monitor, stop_latched=True, reason="PREDECESSOR_FAILED_OR_UNKNOWN")
        if (op_state["unresolved"] is not False or type(op_state["active"]) is not bool or
                op_state["last_status"] not in {"IDLE", "COMPLETE"}):
            monitor = dict(monitor, stop_latched=True, reason="PREDECESSOR_FAILED_OR_UNKNOWN")
        if op_state["last_status"] == "COMPLETE":
            prior = receipts["last_started_run"]
            if (prior is None or prior["status"] != "COMPLETE" or
                    operation.instant(prior["started_at"]) != operation.instant(op_state["last_started_at"]) or
                    prior["completed_at"] is None or
                    operation.instant(prior["completed_at"]) != operation.instant(op_state["last_completed_at"])):
                monitor = dict(monitor, stop_latched=True, reason="PREDECESSOR_EVIDENCE_CONFLICT")
        elif op_state["last_status"] == "IDLE" and receipts["status"] != "NOT_STARTED":
            monitor = dict(monitor, stop_latched=True, reason="PREDECESSOR_EVIDENCE_CONFLICT")
        if state["stop_latched"] is not False or state["unresolved"] is not False:
            monitor = dict(monitor, stop_latched=True, reason="MOSA2_STOPPED")
        if state["mosa_impact"] is not False or baseline["healthy"] is False:
            monitor = dict(monitor, stop_latched=True, reason="MOSA_IMPACT")
        result.update(stop_latched=monitor["stop_latched"], monitor_reason=monitor["reason"],
                      retry_not_before=monitor.get("retry_not_before"))
        # This state is exclusively simulated. Passing it back preserves the latch;
        # there is no reset/resume function and no persistence claim.
        result["monitoring_state"] = {k: monitor[k] for k in
                                      ("errors", "consecutive_errors", "stop_latched", "retry_not_before") if k in monitor}
        result["monitoring_state"]["checked_at"] = operation.instant(event["checked_at"]).isoformat()
        operation_decision = operation.decide(operation_config, op_state, evidence["qualification"],
                                              utc, candidate, simulation=True)
        result["operation_decision"] = operation_decision
        if monitor["stop_latched"]:
            result["reason"] = "MONITORING_STOP"
        elif admission["decision"] == "BLOCKED":
            result["reason"] = admission["reason"]
        elif not documented:
            result["reason"] = "PROVIDER_LIMIT_UNKNOWN_OR_CONFLICTING"
        elif operation_decision == "BLOCKED":
            result["reason"] = "OPERATION_OR_PREDECESSOR_BLOCKED"
        elif operation_decision == "SKIP" or admission["decision"] == "SKIP":
            result.update(decision="SKIP", reason="SLOT_SKIPPED" if operation_decision == "SKIP" else admission["reason"])
        else:
            result.update(decision="RUN_ELIGIBLE", reason="SIMULATION_ONLY")
        result["admission_decision"] = result["decision"]
        if "simulated_attempts" in evidence:
            if result["decision"] != "RUN_ELIGIBLE":
                result.update(decision="BLOCKED", reason="ATTEMPTS_WITHOUT_ELIGIBILITY", stop_latched=True)
                result["monitoring_state"]["stop_latched"] = True
            else:
                usage = budget.simulate_attempts(state, assets, evidence["simulated_attempts"], cycle_id=candidate)
                if usage["decision"] == "BLOCKED":
                    result.update(decision="BLOCKED", reason=usage["reason"], stop_latched=True)
                    result["monitoring_state"]["stop_latched"] = True
                else:
                    # Keep the private ledger out of diagnostics, expose model counts only.
                    result["simulated_attempts"] = usage["attempts"]
                    result["simulated_used_60s"] = usage["used_60s"]
                    result["simulated_used_day"] = usage["used_day"]
                    failed = any(a["outcome"] != "SUCCESS" for a in evidence["simulated_attempts"])
                    incomplete = usage["attempts"] != len(assets)
                    result["simulated_cycle_status"] = "FAILED" if failed else "INCOMPLETE" if incomplete else "COMPLETE"
                    if failed or incomplete:
                        result.update(decision="BLOCKED", reason="SIMULATED_CYCLE_STOPPED", stop_latched=True,
                                      monitor_reason="SIMULATED_ATTEMPT_FAILED_OR_INCOMPLETE")
                        result["monitoring_state"]["stop_latched"] = True
        return result
    except (KeyError, ValueError, TypeError, AttributeError, OverflowError):
        result.update(decision="BLOCKED", reason="INVALID_EVIDENCE", stop_latched=True)
        if "monitoring_state" in result:
            result["monitoring_state"]["stop_latched"] = True
        return result
