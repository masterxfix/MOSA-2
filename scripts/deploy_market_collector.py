"""Install the standalone collector for the MOSA 2 test database."""
import argparse
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import uuid

import collector_actions
import deploy_test_sftp as profile
import deploy_sftp as shared

ROOT = Path(__file__).resolve().parents[1]
# Keep the subscription path POSIX even when the command is inspected on Windows.
PERIODIC = shared.TEST_ROOT.rsplit("/", 1)[0] + "/private/mosa2-collector/periodic"
EXTRAS = (
    "api/market_source_engine.php",
    "api/market_sources.php",
    "api/isin_quote.php",
    "api/market_core/native_currency_units.json",
    "api/market_core/twelve_data.php",
    "api/market_core/eodhd.php",
    "docs/database/migrations/0007_network_smart_home_core.sql",
    "scripts/market_collector/gettex_delayed.py",
    "scripts/market_collector/mosa_tick.php",
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


def main():
    import paramiko

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("install",))
    parser.parse_args()
    sha = os.environ.get("GITHUB_SHA", "")
    if os.environ.get("GITHUB_REPOSITORY") != "masterxfix/MOSA-2" or os.environ.get("GITHUB_REF") != "refs/heads/main" \
            or re.fullmatch(r"[0-9a-f]{40}", sha) is None:
        raise ValueError("Exact M2 main required")
    if sha != os.environ.get("M2_EXPECTED_COMMIT"):
        raise ValueError("Installation revision differs")
    with collector_actions.ssh_client(profile.configuration(), {}, paramiko) as transport:
        with paramiko.SFTPClient.from_transport(transport) as sftp:
            if sftp.normalize(shared.TEST_ROOT) != shared.TEST_ROOT:
                raise ValueError("Unexpected M2 webroot")
            directory(sftp, PERIODIC.rsplit("/", 1)[0])
            directory(sftp, PERIODIC)
            for name in ("inbox", "state", "work", "releases"):
                directory(sftp, PERIODIC + "/" + name)
            install(sftp, sha)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        raise SystemExit("M2 private collector operation failed: " + type(error).__name__) from None
