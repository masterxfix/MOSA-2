"""Bound to the reviewed manifest and prepended shared private auditor/supervisor."""
TOKEN = "MOSA2-SCHEMA4-ONE-SHOT-20261030:"
FIVE_TOKEN = "MOSA2-SCHEMA4-FIVE-20261031:"
FIVE_ORDER = "schema4-five-20261031"
ORDER_ONCE = "schema4-live-20261030"

# The historical supervisor prepended above defines its October-21 guard.
# This active profile must use the identity already bound by its installation.
def guard():
    schema4_guard()


def complete(report):
    return (isinstance(report, dict) and report.get("ok") is True
            and report.get("status") == "COMPLETE"
            and (report.get("request_scope") != "five" or report.get("observations_web_readback") == "PASS")
            and all(report.get(key) == "PASS" for key in
                    ("readback", "web_readback", "release_readback")))


def schema4_once(data):
    global RELEASE, RUN
    mode = data.get("scope", "one")
    need(mode in ("one", "five"), "EXACT_SCOPE")
    if mode == "five":
        need(data.get("execution_authorization") == FIVE_TOKEN + data.get("commit", ""), "EXACT_FIVE_AUTHORIZATION")
    budget = 5 if mode == "five" else 1
    commit, stage, rows, dirs = plan(data)
    need(data["run"] == "schema4-" + commit + "-" + data["run_id"], "RUN_PATH")
    need(isinstance(data.get("password"), str) and bool(data["password"]), "DB_SECRET_REQUIRED")
    RELEASE = ROOT + "/releases/" + commit
    RUN = ROOT + "/runs/" + data["run"]
    report = dict(ok=False, status="NOT_STARTED", commit=commit, run=data["run"], provider_requests=0)
    report["private_path_identity"] = bind_private_paths(data)
    guard()
    audit(RELEASE, rows, dirs)
    os.umask(0o077)
    locks = folder(ROOT + "/locks")
    runs = folder(ROOT + "/runs")
    fd = None
    begun = False
    try:
        # This order-wide reservation survives different workflow IDs and source commits.
        # Consumed once means no retry, even after a crash before the provider marker.
        os.mkdir(FIVE_ORDER if mode == "five" else ORDER_ONCE, 0o700, dir_fd=locks)
        os.fsync(locks)
        os.mkdir(data["run"], 0o700, dir_fd=runs)
        os.fsync(runs)
        fd = folder(RUN)
        file_once(fd, "started.json", json.dumps(dict(commit=commit, run=data["run"],
                  provider_request_budget=budget, automatic_retry=False)).encode())
        source = "require " + repr(RELEASE + "/scripts/collector_schema4_once.php") + "; \\Mosa2\\Schema4Once\\main();"
        begun = True
        result = child(source, data["password"], dict(commit=commit, run=data["run"], scope=mode,
                       authorization=(FIVE_TOKEN if mode == "five" else TOKEN) + commit), deadline=300 if mode == "five" else 120)
        report.update(result)
        if report.get("ok") is True:
            # Execute the installed web API with its unchanged SELECT-only account.
            # This is a read-path proof; Chrome must independently prove the visible render.
            web = BASE + "/mosa2-test.scharwerk.de/api/market.php"
            source = "$_SERVER['REQUEST_METHOD']='GET'; require " + repr(web) + ";"
            try:
                actual = child(source, data["password"], {})
                expected_items = [i["display"] for i in report["items"]] if mode == "five" else [report["display"]]
                keys = ("name", "price", "unit", "unit_version", "source", "venue", "market_at", "observed_at")
                equal = actual.get("status") == "ok"
                for expected in expected_items:
                    matches = [r for r in actual.get("items", []) if r.get("name") == expected["name"]]
                    equal = equal and len(matches) == 1 and all(matches[0].get(k) == expected.get(k) for k in keys)
                report["web_readback"] = "PASS" if equal else "FAILED"
                if mode == "five":
                    source = "$_SERVER['REQUEST_METHOD']='GET'; $_GET['view']='observations'; require " + repr(web) + ";"
                    observations = child(source, data["password"], {})
                    matched = observations.get("status") == "ok"
                    for expected in expected_items:
                        matches = [r for r in observations.get("items", []) if r.get("name") == expected["name"]]
                        matched = matched and len(matches) == 1 and all(matches[0].get(k) == expected.get(k) for k in keys)
                    report["observations_web_readback"] = "PASS" if matched else "FAILED"
                    equal = equal and matched
                    report["web_readback"] = "PASS" if equal else "FAILED"
            except Exception:
                report["web_readback"] = "FAILED"
            if report["web_readback"] != "PASS":
                report.update(ok=False, status="DATA_CONFIRMED_WEB_OPEN")
        audit(RELEASE, rows, dirs)
        report["release_readback"] = "PASS"
    except FileExistsError:
        report.update(ok=False, status="BLOCKED", failure="ORDER_OR_RUN_ALREADY_RESERVED")
    except Exception as error:
        report.update(ok=False, status="OUTCOME_UNKNOWN" if begun else "NOT_STARTED", failure_type=type(error).__name__)
    finally:
        if fd is not None:
            consumed = 0
            try:
                for index in range(1, budget+1):
                    marker = RUN + "/asset-" + format(index, "02d") + "/provider-consumed.lock"
                    try:
                        s = os.lstat(marker)
                    except FileNotFoundError:
                        continue
                    new_metadata(s, 0o600)
                    consumed += 1
                report["provider_budget_consumed"] = consumed > 0
                report["provider_reserved_count"] = consumed
                if report.get("status") in ("COMPLETE", "DATA_CONFIRMED_WEB_OPEN"):
                    if consumed != budget or report.get("provider_requests") != budget:
                        report.update(ok=False, status="OUTCOME_UNKNOWN", provider_requests=None)
                else:
                    report["provider_requests"] = None if consumed else 0
            except Exception:
                report.update(ok=False, status="OUTCOME_UNKNOWN", provider_requests=None)
            if report.get("status") == "COMPLETE" and not complete(report):
                report.update(ok=False, status="OUTCOME_UNKNOWN")
            report["ok"] = complete(report)
            text = json.dumps(report, sort_keys=True)
            password = data["password"]
            if password in text or json.dumps(password)[1:-1] in text:
                report = dict(ok=False, status="OUTCOME_UNKNOWN", failure="SECRET_OUTPUT_BLOCKED")
                text = json.dumps(report)
            try:
                file_once(fd, "result.json", text.encode())
            except Exception:
                report.update(ok=False, status="OUTCOME_UNKNOWN", receipt_persistence="FAIL")
            os.close(fd)
        os.close(locks)
        os.close(runs)
    return report


if __name__ == "__main__":
    try:
        data = json.loads(sys.stdin.read(1048577), object_pairs_hook=unique)
        result = schema4_once(data)
    except Exception as error:
        result = dict(ok=False, status="NOT_STARTED", provider_requests=0, failure_type=type(error).__name__)
    print(json.dumps(result, sort_keys=True))
