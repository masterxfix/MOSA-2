"""Injected DB-API adapter, no connection configuration, transport or starter.

Only synthetic integration callers are wired in this revision. Every public
result denies execution. A reservation consumes quota even without a request.
DB factory MUST supply dedicated connections with bounded connect/read/write
timeouts, autocommit disabled, dictionary cursors and MySQL 8/InnoDB.
"""
from copy import deepcopy
from datetime import datetime, time, timedelta, timezone
import hashlib
import json
from uuid import UUID, uuid4

from scripts import collector_cycle as flow
from scripts import collector_operation_plan as operation
from scripts import provider_budget_plan as budget

PROVIDER = flow.PROVIDER
MAX_WINDOW_ROWS = 100000  # Implementation bound, never a provider allowance.
ERRORS = {"NONE", "INITIAL_LOCK", "TRANSACTION_ROLLED_BACK", "COMMIT_UNKNOWN",
          "PROVIDER_FAILED", "PROVIDER_TIMEOUT", "MISSING_FINAL", "STATE_INVALID"}


class Blocked(Exception):
    """Fixed diagnostic only; never includes DB/driver exception contents."""


def answer(code, **fields):
    return dict(code=code, execution_authorized=False, actual_provider_requests=0,
                automatic_retry=False, automatic_resume=False, **fields)


def policy_hash(data):
    raw = json.dumps([data["operation_config"], data["budget_config"]],
                     sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def day_bounds(now):
    day = now.astimezone(operation.ZONE).date()
    start = datetime.combine(day, time(), operation.ZONE).astimezone(timezone.utc)
    end = datetime.combine(day + timedelta(days=1), time(), operation.ZONE).astimezone(timezone.utc)
    return day, start, end


def sql_time(value):
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def utc(value):
    if not isinstance(value, datetime) or value.tzinfo is not None:
        raise Blocked("STATE_INVALID")
    return value.replace(tzinfo=timezone.utc)


def close(connection):
    if connection is not None:
        try:
            connection.close()
        except Exception:
            pass  # Cleanup must never replace a fixed outcome with raw errors.


def owner_token(value):
    try:
        valid = isinstance(value, str) and str(UUID(value)) == value
    except ValueError:
        valid = False
    if not valid:
        raise Blocked("INVALID_OWNER")
    return value


class Store:
    def __init__(self, connection_factory, *, test_clock=None):
        self.factory = connection_factory
        # Injection is solely for isolated synthetic time/DST tests. Live clock
        # is the database UTC clock, obtained AFTER acquiring the provider lock.
        self.test_clock = test_clock
        self.poisoned = False

    def _connection(self):
        c = self.factory()
        try:
            with c.cursor() as q:
                q.execute("SET SESSION time_zone = '+00:00'")
                q.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED")
                q.execute("SET SESSION innodb_lock_wait_timeout = 3")
                q.execute("SET SESSION max_execution_time = 2000")
            c.commit()
            return c
        except Exception:
            close(c)
            raise

    @staticmethod
    def _one(q, statement, values=()):
        q.execute(statement, values)
        return q.fetchone()

    def _lock(self, q, *, read_only=False):
        lock = "" if read_only else " FOR UPDATE"
        share = "" if read_only else " FOR SHARE"
        s = self._one(q, "SELECT * FROM m2_collector_state WHERE provider=%s"+lock, (PROVIDER,))
        module = self._one(q, "SELECT schema_version,status FROM m2_module_state WHERE module_key='collector_reservations'"+share)
        job = self._one(q, "SELECT job_key,module_key,handler_key,enabled FROM m2_jobs WHERE id=%s"+share, (s["job_id"],)) if s else None
        if (not s or module != {"schema_version": 5, "status": "LOCKED"} or
                job != dict(job_key="collector_reservations_v1", module_key="collector_reservations", handler_key="UNWIRED", enabled=0) or
                s["status"] not in {"IDLE", "RUNNING", "COMPLETE", "FAILED", "PARTIAL_FAILED", "OUTCOME_UNKNOWN"} or
                s["stop_latched"] not in (0, 1) or s["unresolved"] not in (0, 1) or s["error_code"] not in ERRORS):
            raise Blocked("STATE_INVALID")
        q.execute("SELECT cycle_id FROM m2_collector_cycles WHERE provider=%s AND status='RUNNING' LIMIT 2", (PROVIDER,))
        running = q.fetchall()
        if ([r["cycle_id"] for r in running] != ([s["active_cycle"]] if s["active_cycle"] else []) or
                (s["status"] == "RUNNING") != (s["active_cycle"] is not None) or
                (s["status"] == "COMPLETE" and s["last_confirmed_cycle"] is None) or
                (s["status"] == "OUTCOME_UNKNOWN" and not s["unresolved"]) or
                (s["status"] == "IDLE" and (s["last_confirmed_cycle"] or s["pending_asset"] or s["unresolved"])) or
                (s["status"] in {"FAILED", "PARTIAL_FAILED", "OUTCOME_UNKNOWN"} and not s["stop_latched"])):
            raise Blocked("STATE_INVALID")
        q.execute("SELECT cycle_id,asset_id FROM m2_collector_requests WHERE provider=%s AND status IN ('RESERVED','OUTCOME_UNKNOWN') LIMIT 2", (PROVIDER,))
        pending = q.fetchall()
        if (len(pending) > 1 or bool(pending) != bool(s["unresolved"]) or
                (pending and pending[0]["asset_id"] != s["pending_asset"]) or
                (not pending and s["pending_asset"] is not None)):
            raise Blocked("STATE_INVALID")
        return s

    def _now(self, q, s):
        value = self.test_clock() if self.test_clock else utc(self._one(q, "SELECT UTC_TIMESTAMP(6) AS stamp")["stamp"])
        if not isinstance(value, datetime) or value.tzinfo is None:
            raise Blocked("INVALID_TIME")
        value = value.astimezone(timezone.utc)
        if s["last_observed_utc"] is not None and value < utc(s["last_observed_utc"]):
            raise Blocked("CLOCK_REGRESSION")
        return value

    def _usage(self, q, now, *, read_only=False):
        day, start, end = day_bounds(now)
        # All queries bounded even if historical data exceeds the supported size.
        q.execute("SELECT asset_id FROM m2_collector_requests WHERE provider=%s AND reserved_utc>%s AND reserved_utc<=%s LIMIT 100001",
                  (PROVIDER, sql_time(now-timedelta(seconds=60)), sql_time(now)))
        minute = len(q.fetchall())
        q.execute("SELECT asset_id FROM m2_collector_requests WHERE provider=%s AND berlin_day=%s AND reserved_utc>=%s AND reserved_utc<%s LIMIT 100001",
                  (PROVIDER, day, sql_time(start), sql_time(end)))
        used = len(q.fetchall())
        counter = self._one(q, "SELECT reserved_count FROM m2_collector_days WHERE provider=%s AND berlin_day=%s"+("" if read_only else " FOR UPDATE"), (PROVIDER, day))
        if minute > MAX_WINDOW_ROWS or used > MAX_WINDOW_ROWS or (counter is None and used) or (counter and counter["reserved_count"] != used):
            raise Blocked("STATE_INVALID")
        return dict(provider=PROVIDER, checked_at=now.isoformat(), budget_date=day.isoformat(),
                    used_60s=minute, used_day=used, in_flight=0, stop_latched=False, unresolved=False, mosa_impact=False)

    def _cycle(self, q, cycle_id, *, read_only=False):
        row = self._one(q, "SELECT * FROM m2_collector_cycles WHERE cycle_id=%s AND provider=%s"+("" if read_only else " FOR UPDATE"), (cycle_id, PROVIDER))
        if not row:
            raise Blocked("CYCLE_UNKNOWN")
        selected = json.loads(row["selection_json"])
        if (cycle_id != "cycle-"+utc(row["started_utc"]).strftime("%Y%m%dt%H%M%Sz") or
                row["status"] not in {"RUNNING", "COMPLETE", "FAILED", "PARTIAL_FAILED", "OUTCOME_UNKNOWN"} or
                (row["status"] == "RUNNING") != (row["finished_utc"] is None) or
                not isinstance(selected, list) or len(selected) != 5 or
                any(set(a) != {"isin", "asset_id"} or not operation.ISIN.fullmatch(a["isin"]) or
                    type(a["asset_id"]) is not int or a["asset_id"] <= 0 for a in selected) or
                len({a["isin"] for a in selected}) != 5 or len({a["asset_id"] for a in selected}) != 5):
            raise Blocked("STATE_INVALID")
        q.execute("SELECT * FROM m2_collector_requests WHERE cycle_id=%s ORDER BY ordinal_no LIMIT 6", (cycle_id,))
        requests = q.fetchall()
        if (len(requests) > 5 or len(requests) != row["reserved_count"] or
                sum(r["attempt_confirmed"] for r in requests) != row["confirmed_attempts"] or
                (row["status"] == "COMPLETE" and (len(requests) != 5 or any(r["status"] != "CONFIRMED" for r in requests))) or
                any(r["ordinal_no"] != i+1 or r["asset_id"] != selected[i]["asset_id"] or r["provider"] != PROVIDER or
                    r["status"] not in {"RESERVED", "CONFIRMED", "FAILED", "OUTCOME_UNKNOWN"} or
                    (r["status"] == "CONFIRMED" and (r["attempt_confirmed"] != 1 or r["finished_utc"] is None))
                    for i, r in enumerate(requests))):
            raise Blocked("STATE_INVALID")
        return row, selected, requests

    def _identity(self, q, isin):
        if not isinstance(isin, str) or not operation.ISIN.fullmatch(isin):
            raise Blocked("ASSET_INVALID")
        q.execute("SELECT a.entity_id FROM m2_asset_identifiers i JOIN m2_assets a ON a.entity_id=i.asset_id JOIN m2_entities e ON e.id=a.entity_id WHERE i.identifier_type='isin' AND i.normalized_value=%s AND i.scope_key='' AND i.valid_to IS NULL AND a.asset_class='equity' AND a.status='active' AND e.status='active' LIMIT 2 FOR SHARE", (isin,))
        rows = q.fetchall()
        if len(rows) != 1:
            raise Blocked("ASSET_INVALID")
        return rows[0]["entity_id"]

    def _guard(self):
        """Commit an intent before any reservation transaction can be attempted.

        It survives rollback or uncertain commit of that later transaction. No
        TTL, takeover, clearing-on-restart or automatic recovery exists.
        """
        if self.poisoned:
            raise Blocked("CONNECTION_OUTCOME_UNKNOWN")
        c = self._connection()
        committing = False
        token = str(uuid4())
        try:
            c.begin()
            with c.cursor() as q:
                s = self._lock(q)
                if s["operation_token"] is not None:
                    raise Blocked("UNRESOLVED_OPERATION")
                if s["stop_latched"]:
                    raise Blocked("STOP_LATCHED")
                q.execute("UPDATE m2_collector_state SET operation_token=%s WHERE provider=%s", (token, PROVIDER))
            committing = True
            c.commit()
            return token
        except Exception:
            if committing:
                self.poisoned = True
                raise Blocked("COMMIT_UNKNOWN") from None
            c.rollback()
            raise
        finally:
            close(c)

    def _release(self, token):
        c = self._connection()
        try:
            c.begin()
            with c.cursor() as q:
                s = self._lock(q)
                if s["operation_token"] != token:
                    raise Blocked("STATE_INVALID")
                q.execute("UPDATE m2_collector_state SET operation_token=NULL WHERE provider=%s", (PROVIDER,))
            c.commit()
        finally:
            close(c)

    def _transaction(self, action):
        token = None
        c = None
        committing = False
        try:
            token = self._guard()
            c = self._connection()
            c.begin()
            with c.cursor() as q:
                s = self._lock(q)
                if s["operation_token"] != token or s["stop_latched"]:
                    raise Blocked("STATE_INVALID")
                now = self._now(q, s)
                result = action(q, s, now)
                q.execute("UPDATE m2_collector_state SET last_observed_utc=%s WHERE provider=%s", (sql_time(now), PROVIDER))
            committing = True
            c.commit()
            close(c); c = None
            # Only an acknowledged main commit permits intent release. A crash
            # between these commits leaves an enduring barrier, never a retry.
            self._release(token)
            return result
        except Blocked as e:
            code = str(e)
            if committing or code == "COMMIT_UNKNOWN":
                self.poisoned = True
                return answer("OUTCOME_UNKNOWN", error_code="COMMIT_UNKNOWN", requires_read_only_review=True)
            if c:
                try:
                    c.rollback()
                except Exception:
                    self.poisoned = True
                    return answer("OUTCOME_UNKNOWN", error_code="COMMIT_UNKNOWN", requires_read_only_review=True)
            if token:
                try:
                    self._release(token)
                except Exception:
                    self.poisoned = True
                    return answer("OUTCOME_UNKNOWN", error_code="COMMIT_UNKNOWN", requires_read_only_review=True)
            return answer("BLOCKED", error_code=code)
        except Exception:
            if committing:
                self.poisoned = True
                return answer("OUTCOME_UNKNOWN", error_code="COMMIT_UNKNOWN", requires_read_only_review=True)
            # Failed/unknown rollback keeps durable intent, no implicit retry.
            rolled_back = False
            if c:
                try:
                    c.rollback(); rolled_back = True
                except Exception:
                    pass
            self.poisoned = True
            return answer("BLOCKED" if rolled_back else "OUTCOME_UNKNOWN",
                          error_code="TRANSACTION_ROLLED_BACK" if rolled_back else "COMMIT_UNKNOWN",
                          requires_read_only_review=True)
        finally:
            if c:
                close(c)

    def begin(self, data, owner):
        """Start a synthetic cycle only after the existing full pure decision."""
        def action(q, s, now):
            owner_token(owner)
            if s["active_cycle"] is not None or s["unresolved"] or s["pending_asset"] is not None:
                raise Blocked("ACTIVE_OR_UNKNOWN_PREDECESSOR")
            usage = self._usage(q, now)
            payload = deepcopy(data)
            state = dict(checked_at=now.isoformat(), active=False, unresolved=False, seen_run_ids=[],
                         last_status="IDLE", last_started_at=None, last_completed_at=None,
                         provider_budget_date=usage["budget_date"], provider_requests_used=usage["used_day"])
            receipts = []
            if s["last_confirmed_cycle"]:
                prior, prior_selection, requests = self._cycle(q, s["last_confirmed_cycle"])
                if (s["status"] != "COMPLETE" or prior["status"] != "COMPLETE" or
                        len(requests) != 5 or any(r["status"] != "CONFIRMED" for r in requests) or prior["finished_utc"] is None):
                    raise Blocked("STATE_INVALID")
                start, end = utc(prior["started_utc"]).isoformat(), utc(prior["finished_utc"]).isoformat()
                state.update(last_status="COMPLETE", last_started_at=start, last_completed_at=end)
                receipts = [dict(run_id=prior["cycle_id"], started_at=start, completed_at=end,
                                 receipt=dict(overall_status="COMPLETE", item_results=[
                                     dict(asset_identity=a["isin"], status="COMPLETE") for a in prior_selection]))]
            elif s["status"] != "IDLE":
                raise Blocked("STATE_INVALID")
            payload["evidence"].update(operation_state=state, budget_state=usage, receipts=receipts)
            if "simulated_attempts" in payload["evidence"]:
                raise Blocked("ATTEMPTS_NOT_ALLOWED")
            plan = flow.cycle(payload["operation_config"], payload["budget_config"], payload["evidence"], now)
            if plan["decision"] != "RUN_ELIGIBLE":
                if plan["stop_latched"] and plan.get("monitor_reason") not in {"INVALID_EVIDENCE", "HEALTHY"}:
                    q.execute("UPDATE m2_collector_state SET stop_latched=1,error_code='PROVIDER_FAILED' WHERE provider=%s", (PROVIDER,))
                    return answer("BLOCKED", error_code="MONITORING_STOP")
                raise Blocked("PLAN_BLOCKED")
            cid = plan["cycle_id"]
            if self._one(q, "SELECT cycle_id FROM m2_collector_cycles WHERE cycle_id=%s", (cid,)):
                raise Blocked("DUPLICATE_CYCLE")
            selected = [dict(isin=isin, asset_id=self._identity(q, isin)) for isin in plan["assets"]]
            q.execute("INSERT INTO m2_collector_cycles (cycle_id,provider,owner_token,policy_hash,selection_json,status,started_utc) VALUES (%s,%s,%s,%s,%s,'RUNNING',%s)",
                      (cid, PROVIDER, owner, policy_hash(payload), json.dumps(selected), sql_time(now)))
            q.execute("UPDATE m2_collector_state SET active_cycle=%s,status='RUNNING',error_code='NONE' WHERE provider=%s", (cid, PROVIDER))
            return answer("CYCLE_COMMITTED", cycle_id=cid)
        return self._transaction(action)

    def _active(self, q, s, cid, owner):
        owner_token(owner)
        if s["active_cycle"] != cid or s["status"] != "RUNNING":
            raise Blocked("ACTIVE_OR_UNKNOWN_PREDECESSOR")
        row, selected, requests = self._cycle(q, cid)
        if row["owner_token"] != owner or row["status"] != "RUNNING":
            raise Blocked("OWNER_OR_CYCLE_MISMATCH")
        return row, selected, requests

    def reserve(self, cid, owner, isin, data):
        """Check durable usage and reserve ONE sequential asset under same lock."""
        def action(q, s, now):
            row, selected, requests = self._active(q, s, cid, owner)
            if s["unresolved"] or s["pending_asset"] is not None or any(r["status"] != "CONFIRMED" for r in requests):
                raise Blocked("OPEN_OR_UNKNOWN_REQUEST")
            if len(requests) >= 5 or isin != selected[len(requests)]["isin"]:
                raise Blocked("DUPLICATE_OR_OUT_OF_ORDER")
            asset = self._identity(q, isin)
            if asset != selected[len(requests)]["asset_id"]:
                raise Blocked("ASSET_INVALID")
            if policy_hash(data) != row["policy_hash"] or data["operation_config"]["execution_enabled"] is not False or data["budget_config"]["execution_enabled"] is not False:
                raise Blocked("POLICY_CHANGED")
            if (now-utc(row["started_utc"])).total_seconds() > data["operation_config"]["max_duration_seconds"]:
                raise Blocked("CYCLE_EXPIRED")
            evidence = data["evidence"]
            qualification = evidence["qualification"]
            if (qualification["selection"] != [a["isin"] for a in selected] or qualification["all_qualified"] is not True or
                    qualification["asset_class"] != "equity" or qualification["policy"] != "USE_EXISTING_ROUTE" or
                    qualification["venue"] != data["operation_config"]["venue"] or
                    qualification["contract"] != "mosa2-operation-qualification-v1"):
                raise Blocked("QUALIFICATION_UNKNOWN")
            for event in (qualification, evidence["monitoring_previous"], evidence["monitoring_event"]):
                if not 0 <= (now-operation.instant(event["checked_at"])).total_seconds() <= data["operation_config"]["evidence_max_age_seconds"]:
                    raise Blocked("EVIDENCE_STALE")
            provider = data["budget_config"]["providers"][PROVIDER]
            event = dict(evidence["monitoring_event"])
            if type(event["provenance_conflict"]) is not bool:
                raise Blocked("MONITORING_STOP")
            if event["provenance_conflict"]:
                event["dedupe_decision"] = "CONFLICT"
            monitor = budget.observe(provider["monitoring"], evidence["monitoring_previous"], event, now=now, strict=True)
            if monitor["stop_latched"]:
                # Persist a stop without acquiring any new quota. No reset API.
                q.execute("UPDATE m2_collector_state SET stop_latched=1,error_code='PROVIDER_FAILED' WHERE provider=%s", (PROVIDER,))
                return answer("BLOCKED", error_code="MONITORING_STOP")
            usage = self._usage(q, now)
            decision = budget.admission(data["budget_config"], PROVIDER, usage, evidence["mosa_baseline"], planned_requests=1, now=now, simulation=True)
            if decision["decision"] != "RUN_ELIGIBLE":
                raise Blocked("BUDGET_OR_BASELINE_BLOCKED")
            day = now.astimezone(operation.ZONE).date()
            q.execute("INSERT INTO m2_collector_days (provider,berlin_day,reserved_count) VALUES (%s,%s,1) ON DUPLICATE KEY UPDATE reserved_count=reserved_count+1", (PROVIDER, day))
            q.execute("INSERT INTO m2_collector_requests (cycle_id,asset_id,ordinal_no,provider,reserved_utc,berlin_day) VALUES (%s,%s,%s,%s,%s,%s)",
                      (cid, asset, len(requests)+1, PROVIDER, sql_time(now), day))
            q.execute("UPDATE m2_collector_cycles SET reserved_count=reserved_count+1 WHERE cycle_id=%s", (cid,))
            q.execute("UPDATE m2_collector_state SET unresolved=1,pending_asset=%s WHERE provider=%s", (asset, PROVIDER))
            return answer("RESERVATION_COMMITTED", reserved_requests=len(requests)+1,
                          used_60s=usage["used_60s"]+1, used_day=usage["used_day"]+1)
        return self._transaction(action)

    def record(self, cid, owner, isin, outcome, *, attempt_confirmed):
        """Injected synthetic final evidence. No provider call or retry is made."""
        def action(q, s, now):
            row, selected, requests = self._active(q, s, cid, owner)
            if (outcome not in {"SUCCESS", "FAILED", "TIMEOUT", "MISSING_FINAL"} or type(attempt_confirmed) is not bool or
                    (outcome == "SUCCESS" and not attempt_confirmed) or not requests or
                    requests[-1]["status"] != "RESERVED" or not s["unresolved"] or s["pending_asset"] != requests[-1]["asset_id"] or
                    isin != selected[len(requests)-1]["isin"]):
                raise Blocked("FINAL_EVIDENCE_INVALID")
            unknown = outcome in {"TIMEOUT", "MISSING_FINAL"}
            status = "CONFIRMED" if outcome == "SUCCESS" else "OUTCOME_UNKNOWN" if unknown else "FAILED"
            code = "PROVIDER_TIMEOUT" if outcome == "TIMEOUT" else "MISSING_FINAL" if unknown else "PROVIDER_FAILED" if outcome == "FAILED" else "NONE"
            q.execute("UPDATE m2_collector_requests SET status=%s,attempt_confirmed=%s,finished_utc=%s WHERE cycle_id=%s AND asset_id=%s", (status, int(attempt_confirmed), sql_time(now), cid, requests[-1]["asset_id"]))
            complete = outcome == "SUCCESS" and len(requests) == 5
            terminal = complete or outcome != "SUCCESS"
            cycle_status = "COMPLETE" if complete else "OUTCOME_UNKNOWN" if unknown else "PARTIAL_FAILED" if outcome == "FAILED" and len(requests) > 1 else "FAILED" if outcome == "FAILED" else "RUNNING"
            q.execute("UPDATE m2_collector_cycles SET confirmed_attempts=confirmed_attempts+%s,status=%s,finished_utc=%s,error_code=%s WHERE cycle_id=%s", (int(attempt_confirmed), cycle_status, sql_time(now) if terminal else None, code, cid))
            q.execute("UPDATE m2_collector_state SET status=%s,stop_latched=%s,unresolved=%s,pending_asset=%s,active_cycle=%s,last_confirmed_cycle=%s,error_code=%s WHERE provider=%s",
                      (cycle_status, int(outcome != "SUCCESS"), int(unknown), requests[-1]["asset_id"] if unknown else None,
                       None if terminal else cid, cid if complete else s["last_confirmed_cycle"], code, PROVIDER))
            return answer("FINAL_COMMITTED", status=cycle_status, stop_latched=outcome != "SUCCESS")
        return self._transaction(action)

    def inspect(self):
        """Separate read-only reconciliation; never clears intent/latch or quota.

        A committed intent remains OUTCOME_UNKNOWN even if ledger rows exist.
        Resolution/operational grants need a separately reviewed future tool.
        """
        c = None
        try:
            c = self._connection()
            with c.cursor() as q:
                q.execute("START TRANSACTION READ ONLY")
                s = self._lock(q, read_only=True)
                now = self._now(q, s)
                usage = self._usage(q, now, read_only=True)
                active = None
                for cid in {s["active_cycle"], s["last_confirmed_cycle"]}-{None}:
                    row, _, _ = self._cycle(q, cid, read_only=True)
                    if cid == s["active_cycle"]:
                        active = row
                ambiguous = bool(s["operation_token"] or s["unresolved"])
                result = answer("READ_ONLY_STATE", status="OUTCOME_UNKNOWN" if ambiguous else s["status"],
                                stop_latched=bool(s["stop_latched"] or ambiguous), unresolved=ambiguous,
                                active_cycle=s["active_cycle"], last_confirmed_cycle=s["last_confirmed_cycle"],
                                used_60s=usage["used_60s"], used_day=usage["used_day"],
                                reserved_requests=active["reserved_count"] if active else None,
                                confirmed_attempts=active["confirmed_attempts"] if active else None,
                                error_code="COMMIT_UNKNOWN" if s["operation_token"] else s["error_code"])
            c.rollback()
            return result
        except Exception:
            return answer("OUTCOME_UNKNOWN", error_code="STATE_INVALID", stop_latched=True, unresolved=True)
        finally:
            if c:
                close(c)
