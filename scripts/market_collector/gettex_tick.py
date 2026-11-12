"""Process one fresh private gettex file through the existing Dogado market batch."""
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


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
    if not 0 < archive.stat().st_size <= MAX_FILE or hashlib.sha256(archive.read_bytes()).hexdigest() != receipt["sha256"]:
        raise ValueError("archive identity")
    with gzip.open(archive, "rb") as source:
        data = source.read(MAX_EXPANDED + 1)
    if len(data) > MAX_EXPANDED:
        raise ValueError("archive size")
    # Presence only. The existing adapter still validates the complete trade and UTC slot.
    present = {line.split(b",", 1)[0] for line in data.splitlines()}
    selected = [code for code in codes if code.encode("ascii") in present]
    result = dict(slot=slot, selected=len(selected), observations=0, duplicates=0, failures=0)
    if not selected:
        return result
    work = Path(tempfile.mkdtemp(prefix="slot-", dir=root / "work"))
    try:
        original = work / archive.name
        os.link(archive, original)
        for index, code in enumerate(selected):
            batch = work / str(index) / "batch"
            batch.mkdir(parents=True, mode=0o700)
            scope = dict(mode="manual", request_budget=1, source_priority=["provider:gettex_mund_delayed"],
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
                    code_value = output.get("failure")
                    if isinstance(code_value, str) and re.fullmatch(r"[a-z_]{1,80}", code_value):
                        result["last_failure"] = code_value
                    continue
                result["observations"] += output["batch"]["insert_count"]
                result["duplicates"] += output["batch"]["duplicate_unchanged_count"]
            except (ValueError, KeyError, OSError, subprocess.TimeoutExpired):
                result["failures"] += 1
        return result
    finally:
        shutil.rmtree(work)


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
    write_status(status_path, status)


if __name__ == "__main__":
    main()
