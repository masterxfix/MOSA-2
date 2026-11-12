"""Install the private M2 collector or relay one published delayed archive."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import urllib.request
import uuid
from zoneinfo import ZoneInfo

import collector_actions
import deploy_test_sftp as profile
import deploy_sftp as shared

ROOT = Path(__file__).resolve().parents[1]
# Keep the subscription path POSIX even when the command is inspected on Windows.
PERIODIC = shared.TEST_ROOT.rsplit("/", 1)[0] + "/private/mosa2-collector/periodic"
EXTRAS = (
    "api/market_core/native_currency_units.json",
    "scripts/market_collector/gettex_delayed.py",
    "scripts/market_collector/gettex_tick.php",
    "scripts/market_collector/gettex_tick.py",
)


def directory(sftp, path):
    if shared.remote_kind(sftp, path) is None:
        sftp.mkdir(path, mode=0o700)
    mode = sftp.lstat(path).st_mode
    if sftp.normalize(path) != path or not stat.S_ISDIR(mode) or stat.S_IMODE(mode) != 0o700:
        raise ValueError("Invalid private collector directory")


def write(sftp, path, raw):
    if shared.remote_kind(sftp, path) is None:
        temporary = path + ".new-" + uuid.uuid4().hex
        try:
            with sftp.open(temporary, "wx") as stream:
                sftp.chmod(temporary, 0o600)
                stream.write(raw)
            sftp.rename(temporary, path)
        finally:
            if shared.remote_kind(sftp, temporary) is not None:
                sftp.remove(temporary)
    mode = sftp.lstat(path).st_mode
    if not stat.S_ISREG(mode) or stat.S_IMODE(mode) != 0o600:
        raise ValueError("Invalid private collector file")
    with sftp.open(path, "rb") as stream:
        if stream.read(len(raw) + 1) != raw:
            raise ValueError("Private file differs")


def install(sftp, sha):
    contract = json.loads((ROOT / "docs/database/collector_release_contract_schema6_v1.json").read_text())
    paths = {item["path"] for item in contract["files"]} | set(EXTRAS)
    release = PERIODIC + "/releases/" + sha
    directory(sftp, release)
    for name in sorted(paths):
        if not re.fullmatch(r"(?:api|scripts|docs|config)/(?:[a-zA-Z0-9_][a-zA-Z0-9_.-]*/)*[a-zA-Z0-9_][a-zA-Z0-9_.-]*", name):
            raise ValueError("Private collector package path")
        raw = subprocess.check_output(["git", "show", sha + ":" + name], cwd=ROOT)
        if not 0 < len(raw) < 512 * 1024:
            raise ValueError("Private collector package size")
        target = release
        parts = name.split("/")
        for part in parts[:-1]:
            target += "/" + part
            directory(sftp, target)
        write(sftp, target + "/" + parts[-1], raw)
    print("Private collector release and exact file readback: PASS " + sha)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def relay(sftp):
    sys.path.insert(0, str(ROOT))
    from scripts.market_collector.gettex_delayed import FILE_BASE, FILE_STAMP, MAX_FILE_BYTES, STAMP, file_slot

    now = datetime.now(timezone.utc)
    local = now.astimezone(ZoneInfo("Europe/Berlin"))
    if local.weekday() >= 5 or not (7 <= local.hour <= 23):
        print("No relay outside the source publication window")
        return
    slot = file_slot(now.strftime(STAMP)).strftime(FILE_STAMP)
    inbox = PERIODIC + "/inbox/"
    receipt = inbox + slot + ".json"
    # Never download the same publication twice, including after a failed request.
    if shared.remote_kind(sftp, receipt) is not None:
        print("Published slot already relayed")
        return
    attempt = PERIODIC + "/state/" + slot + ".relay"
    try:
        with sftp.open(attempt, "wx") as stream:
            sftp.chmod(attempt, 0o600)
            stream.write(b"claimed\n")
    except OSError:
        if shared.remote_kind(sftp, attempt) is not None:
            print("Published slot already attempted")
            return
        raise
    name = "posttrade." + slot + ".mund.csv.gz"
    request = urllib.request.Request(FILE_BASE + name, headers={"Accept":"application/gzip,application/octet-stream"})
    opener = urllib.request.build_opener(NoRedirect())
    with opener.open(request, timeout=12) as response:
        if response.status != 200 or response.url != request.full_url:
            raise ValueError("Unexpected archive response")
        raw = response.read(MAX_FILE_BYTES + 1)
    if not 0 < len(raw) <= MAX_FILE_BYTES or not raw.startswith(b"\x1f\x8b"):
        raise ValueError("Unexpected archive payload")
    captured = datetime.now(timezone.utc).strftime(STAMP)
    write(sftp, inbox + "mosa2-gettex-" + name, raw)
    write(sftp, receipt, json.dumps(dict(sha256=hashlib.sha256(raw).hexdigest(), captured_at=captured)).encode())
    print("Official private archive relayed: " + slot)


def main():
    import paramiko

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("install", "relay"))
    args = parser.parse_args()
    sha = os.environ.get("GITHUB_SHA", "")
    if os.environ.get("GITHUB_REPOSITORY") != "masterxfix/MOSA-2" or os.environ.get("GITHUB_REF") != "refs/heads/main" \
            or re.fullmatch(r"[0-9a-f]{40}", sha) is None:
        raise ValueError("Exact M2 main required")
    if args.mode == "relay" and os.environ.get("MOSA_MARKET_GETTEX_PRIVATE_USE") != "1":
        raise ValueError("Private gettex use not enabled")
    if args.mode == "install" and sha != os.environ.get("M2_EXPECTED_COMMIT"):
        raise ValueError("Installation revision differs")
    with collector_actions.ssh_client(profile.configuration(), {}, paramiko) as transport:
        with paramiko.SFTPClient.from_transport(transport) as sftp:
            if sftp.normalize(shared.TEST_ROOT) != shared.TEST_ROOT:
                raise ValueError("Unexpected M2 webroot")
            directory(sftp, PERIODIC.rsplit("/", 1)[0])
            directory(sftp, PERIODIC)
            for name in ("inbox", "state", "work", "releases"):
                directory(sftp, PERIODIC + "/" + name)
            if args.mode == "install":
                install(sftp, sha)
            else:
                relay(sftp)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        raise SystemExit("M2 private collector operation failed: " + type(error).__name__) from None
