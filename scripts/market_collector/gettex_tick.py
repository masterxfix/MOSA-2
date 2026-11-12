"""Process available post-trade publications through the common Dogado market batch."""
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import timedelta

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.market_collector import nasdaq_nordic as nordic


FILE = re.compile(r"(?P<slot>\d{8}\.\d{2}\.\d{2})\.json")
ISIN = re.compile(r"[A-Z]{2}[A-Z0-9]{9}[0-9]")
MAX_FILE = 2 * 1024 * 1024
MAX_EXPANDED = 16 * 1024 * 1024
STAMP = "%Y-%m-%d %H:%M:%S.%f"


def write_status(path, status):
    tmp = path.with_suffix(".pending")
    tmp.write_text(json.dumps(status, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)
    print(json.dumps(status, separators=(",", ":")))


def process_file(root, config, slot, receipt, archive, codes):
    if not archive.is_file() or archive.is_symlink() or archive.stat().st_mode & 0o077:
        raise ValueError("private archive")
    if not 0 < archive.stat().st_size <= MAX_FILE:
        raise ValueError("archive size")
    raw = archive.read_bytes()
    if len(raw) > MAX_FILE or hashlib.sha256(raw).hexdigest() != receipt["sha256"]:
        raise ValueError("archive identity")
    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as source:
        data = source.read(MAX_EXPANDED + 1)
    if len(data) > MAX_EXPANDED:
        raise ValueError("archive size")
    # Presence only. The existing adapter still validates the complete trade and UTC slot.
    present = {line.split(b",", 1)[0] for line in data.splitlines()}
    selected = [code for code in codes if code.encode("ascii") in present]
    return store_publication(root, config, slot, receipt, archive.name, raw,
                             [(code, "provider:gettex_mund_delayed") for code in selected])


def store_publication(root, config, slot, receipt, filename, raw, selected):
    result = dict(slot=slot, selected=len(selected), observations=0, duplicates=0, failures=0)
    if not selected:
        return result
    work = Path(tempfile.mkdtemp(prefix="slot-", dir=root / "work"))
    try:
        original = work / filename
        original.write_bytes(raw)
        for index, (code, source) in enumerate(selected):
            batch = work / str(index) / "batch"
            batch.mkdir(parents=True, mode=0o700)
            scope = dict(mode="manual", request_budget=1, source_priority=[source],
                         expected_isins=[code], archive={**receipt, "slot":slot, "private_path":str(original)})
            contract = dict(python=config["python"], php=config["php"], project=config["project"],
                            runtime_path="/opt/plesk/php/8.4/bin:/usr/bin:/bin", public_root=config["web"],
                            db_host="127.0.0.1", db_port=3307, private_dogado=True,
                            state_contract=dict(schema_version=6, allow_current=True))
            request = dict(config=contract, password=config["password"], scope=scope, private_root=str(batch))
            try:
                child = subprocess.run([config["php"], "-d", "display_errors=0", "-d", "log_errors=0",
                    str(Path(config["project"]) / "scripts/market_collector/live_batch.php")],
                    input=json.dumps(request).encode(), capture_output=True, timeout=45, check=False,
                    env={"PATH":contract["runtime_path"],"LANG":"C.UTF-8","PYTHONDONTWRITEBYTECODE":"1"})
                output = json.loads(child.stdout)
                if child.returncode or child.stderr or not output.get("ok") or output.get("current", {}).get("readback") != "PASS":
                    result["failures"] += 1
                    items = (output.get("batch") or {}).get("item_results", [])
                    code_value = (items[0].get("failure_stage") if items else None) or output.get("failure")
                    if isinstance(code_value, str) and re.fullmatch(r"[a-z_]{1,80}", code_value):
                        result["last_failure"] = code_value
                    continue
                items = output["batch"]["item_results"]
                if len(items) != 1 or items[0].get("readback") != "PASS":
                    raise ValueError("unverified observation")
                writer = items[0]["writer"]
                if writer == "INSERT":
                    result["observations"] += 1
                elif writer == "DUPLICATE_UNCHANGED":
                    result["duplicates"] += 1
                else:
                    raise ValueError("unexpected writer outcome")
            except (ValueError, KeyError, OSError, subprocess.TimeoutExpired) as error:
                result["failures"] += 1
                result["last_failure"] = type(error).__name__
        return result
    finally:
        shutil.rmtree(work)


def nordic_tick(root, config, codes, now, previous):
    local = now.astimezone(nordic.ZoneInfo("Europe/Stockholm"))
    if local.weekday() >= 5 or not (9 <= local.hour <= 18) or not codes:
        return previous
    state = root / "state"
    if (state / "nasdaq-nordic.stop").exists():
        return {"status": "stopped"}
    available = nordic.publications()
    candidates = [name for name in available if
                  timedelta(minutes=15) <= now.replace(tzinfo=None) - nordic.publication_start(name) <= timedelta(hours=1)]
    if not candidates:
        return previous
    name = candidates[0]
    try:
        with (state / (name + ".checked")).open("x", encoding="utf-8"):
            pass
    except FileExistsError:
        return previous
    response = nordic.fetch(nordic.download_url(name), nordic.MAX_BYTES)
    if response.http_status in (401, 403, 429):
        (state / "nasdaq-nordic.stop").write_text(str(response.http_status), encoding="utf-8")
    if response.http_status != 200:
        return {"slot": name, "failures": 1, "http_status": response.http_status}
    registered = set(codes)
    choices = {}
    for isin, mic, market, _, _ in nordic.trades(response.payload_bytes, name):
        if isin not in registered:
            continue
        rank = (isin[:2] == nordic.MARKETS[mic][0], market, mic)
        if isin not in choices or rank > choices[isin]:
            choices[isin] = rank
    selected = [(code, "provider:nasdaq_nordic_" + choices[code][2].lower() + "_delayed")
                for code in sorted(choices)]
    receipt = dict(sha256=hashlib.sha256(response.payload_bytes).hexdigest(), captured_at=response.collected_at)
    return store_publication(root, config, name, receipt, name + ".csv", response.payload_bytes, selected)


def main():
    os.umask(0o077)
    config = json.load(sys.stdin)
    root = Path(config["periodic"]).resolve(strict=True)
    inbox, state = root / "inbox", root / "state"
    now = datetime.now(timezone.utc)
    codes = [code for code in config["is_registry"] if ISIN.fullmatch(code)]
    status_path = state / "last.json"
    previous = json.loads(status_path.read_text()) if status_path.is_file() else {}
    status = {"checked_at": now.strftime(STAMP), "checks":previous.get("checks", 0) + 1,
              "registered":len(codes),"last_batch":previous.get("last_batch")}
    for path in sorted(inbox.glob("*.json")):
        match = FILE.fullmatch(path.name)
        if not match or path.is_symlink() or path.stat().st_size > 1024 or path.stat().st_mode & 0o077:
            continue
        slot = match["slot"]
        archive = inbox / ("mosa2-gettex-posttrade." + slot + ".mund.csv.gz")
        try:
            receipt = json.loads(path.read_text(encoding="utf-8"))
            if set(receipt) != {"sha256","captured_at"} or not re.fullmatch(r"[0-9a-f]{64}",receipt["sha256"]):
                raise ValueError("archive receipt")
            captured = datetime.strptime(receipt["captured_at"], STAMP).replace(tzinfo=timezone.utc)
            if not 0 <= (now - captured).total_seconds() <= 86400:
                raise ValueError("archive receipt time")
            done = state / (slot + ".checked")
            # Claim before work, including for an empty selection. Only a new file adds work.
            with done.open("x", encoding="utf-8") as mark:
                mark.write(receipt["sha256"] + "\n")
        except (FileExistsError, ValueError, KeyError):
            continue
        try:
            status["last_batch"] = process_file(root, config, slot, receipt, archive, codes)
            if status["last_batch"]["failures"] == 0:
                path.unlink()
                archive.unlink()
        except (ValueError, OSError):
            status["last_batch"] = {"slot":slot,"failures":1}
        break
    if config.get("nasdaq_nordic_private_use") is True:
        try:
            status["nasdaq_nordic"] = nordic_tick(root, config, codes, now, previous.get("nasdaq_nordic"))
        except (KeyError, TypeError, ValueError, OSError) as error:
            status["nasdaq_nordic"] = {"failures": 1, "reason": str(error) if type(error) is ValueError
                                      and str(error).startswith("read_only_http_") else type(error).__name__}
    write_status(status_path, status)


if __name__ == "__main__":
    main()
