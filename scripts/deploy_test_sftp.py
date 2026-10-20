"""Manual MOSA-2 testsite profile; no production target or remote shell."""
import argparse
import hashlib
import json
import os
import re
import sys
import uuid

import deploy_sftp as shared

PREFIX = "MOSA_TEST_SFTP_"
EXPECTED = {"HOST": "server10.configcenter.info", "PORT": "22", "USER": "web213",
            "PATH": shared.TEST_ROOT}
NAMES = tuple(PREFIX + key for key in (*EXPECTED, "PASSWORD", "HOST_KEY_SHA256"))


def configuration(env=None):
    env = os.environ if env is None else env
    for name in NAMES:
        if not env.get(name):
            raise ValueError("Missing testsite configuration: " + name)
    for name, expected in EXPECTED.items():
        if env[PREFIX + name] != expected:
            raise ValueError("Testsite configuration differs from fixed profile: " + PREFIX + name)
    pin = env[PREFIX + "HOST_KEY_SHA256"]
    if not re.fullmatch(r"SHA256:[A-Za-z0-9+/]{43}", pin):
        raise ValueError("Invalid testsite host-key fingerprint format")
    return {key.lower(): env[PREFIX + key] for key in (*EXPECTED, "PASSWORD", "HOST_KEY_SHA256")}


def selected_files(encoded):
    try:
        names = json.loads(encoded)
    except (TypeError, json.JSONDecodeError):
        raise ValueError("files_json must be a JSON array of tracked web filenames") from None
    if (not isinstance(names, list) or not names or len(names) > 100
            or any(not isinstance(n, str) for n in names) or len(set(names)) != len(names)):
        raise ValueError("An explicit nonempty unique web file set is required")
    # Reuse the existing tracked-web package validation; never deploy that entire set implicitly.
    available = dict(shared.web_files())
    if any(name not in available for name in names):
        raise ValueError("Requested filename is outside the validated tracked web file set")
    return [(name, available[name]) for name in names]


def probe(sftp, run_id):
    name = ".mosa2-actions-probe-" + uuid.uuid4().hex + ".txt"
    path = shared.TEST_ROOT + "/" + name
    data = ("MOSA2 ACTIONS SFTP PROBE\nRun: " + run_id + "\n").encode("ascii")
    digest = hashlib.sha256(data).hexdigest()
    if shared.remote_kind(sftp, path) is not None:
        raise ValueError("Unexpected existing probe destination")
    # Exercise the same temporary upload, SHA-256 readback and atomic rename as real deployments.
    shared.upload(sftp, shared.TEST_ROOT, [(name, data)], profile="test")
    print("Upload and atomic rename: PASS")
    with sftp.open(path, "rb") as remote:
        returned = remote.read(len(data) + 1)
    if hashlib.sha256(returned).hexdigest() != digest:
        raise ValueError("Final probe readback mismatch")
    print("Final readback/SHA-256: PASS; digest=" + digest)
    # Delete only this unique probe and only after both readback checks passed.
    sftp.remove(path)
    if shared.remote_kind(sftp, path) is not None:
        raise ValueError("Probe still exists after removal")
    print("Probe removal and absence check: PASS")


def execute(config, operation, files=None):
    import paramiko

    class PinnedHostKey(paramiko.MissingHostKeyPolicy):
        def missing_host_key(self, client, hostname, key):
            shared.verify_fingerprint(key.asbytes(), config["host_key_sha256"])
            print("Host-key verification: PASS")

    with paramiko.SSHClient() as client:
        client.set_missing_host_key_policy(PinnedHostKey())
        # The existing verified key is Ed25519. Do not negotiate a different unpinned host key.
        client.connect(config["host"], port=22, username=config["user"],
            password=config["password"], allow_agent=False, look_for_keys=False,
            timeout=20, banner_timeout=20, auth_timeout=20, channel_timeout=30,
            disabled_algorithms={"keys": ["ssh-rsa", "rsa-sha2-256", "rsa-sha2-512",
                "ecdsa-sha2-nistp256", "ecdsa-sha2-nistp384", "ecdsa-sha2-nistp521"]})
        with client.open_sftp() as sftp:
            sftp.get_channel().settimeout(30)
            print("SFTP connection and authentication: PASS")
            if sftp.normalize(config["path"]) != shared.TEST_ROOT:
                raise ValueError("Canonical testsite root differs from fixed profile")
            shared.check_remote(sftp, shared.TEST_ROOT, scoped=True)
            print("Exact test-webroot verification: PASS")
            if operation == "probe":
                probe(sftp, os.environ.get("GITHUB_RUN_ID", "local"))
            else:
                shared.upload(sftp, shared.TEST_ROOT, files, profile="test")
                print("Explicit file-set upload/readback/SHA-256: PASS")
            print("All remote file operations confined to MOSA-2 test-webroot: PASS")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("check-config", "probe", "deploy"))
    args = parser.parse_args()
    config = configuration()  # Before reading files, loading client, or connecting.
    if args.operation == "check-config":
        print("Testsite secrets and fixed target profile: PASS")
        return
    files = selected_files(os.environ.get("MOSA_TEST_SFTP_FILES", "[]")) if args.operation == "deploy" else None
    execute(config, args.operation, files)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Never print remote exception messages or user-controlled configuration values.
        print("Testsite SFTP aborted: " + type(error).__name__, file=sys.stderr)
        sys.exit(1)
