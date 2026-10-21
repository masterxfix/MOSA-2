"""Offline private deployment profile. Remote I/O is deliberately not implemented."""
import argparse
import json
from pathlib import PurePosixPath
import re

from scripts import deploy_sftp as shared

PROPOSED_ROOT = "/var/www/vhosts/web213.server10.configcenter.info/private/mosa2-collector"
DIRECTORIES = ("releases", "staging", "runs", "locks")
RESERVE_BYTES = 64 * 1024 * 1024


def inside(child, parent):
    return child == parent or child.startswith(parent + "/")


def proposal(root, webroots):
    """Pure lexical review only: never proves remote existence, ownership or approval."""
    if (type(root) is not str or not re.fullmatch(r"/[A-Za-z0-9_./-]+", root)
            or str(PurePosixPath(root)) != root
            or any(p in (".", "..") for p in root.split("/")[1:])
            or root.endswith("/")):
        raise ValueError("invalid private proposal")
    for public in (*webroots, shared.ABSOLUTE_ROOT, shared.TEST_ROOT):
        if inside(root, public) or inside(public, root):
            raise ValueError("webroot/ancestor target forbidden")
    if root != PROPOSED_ROOT:
        raise ValueError("unreviewed private proposal")
    return dict(proposed_root=root, authorized=False, remote_verified=False,
                upload_enabled=False, directories={p: "0700" for p in DIRECTORIES},
                file_mode="0600", plan_reserve_bytes=RESERVE_BYTES)


def verify_host_key_material(key_bytes, expected):
    """Reuse the existing pinned-key algorithm; no client/network capability."""
    return shared.verify_fingerprint(key_bytes, expected)


def upload(*args, **kwargs):
    # This hard gate precedes configuration, secret access, client import or remote calls.
    # A later separate reviewed implementation is required; JSON cannot enable it.
    raise PermissionError("PRIVATE_COLLECTOR_UPLOAD_NOT_IMPLEMENTED_OR_AUTHORIZED")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("plan", "upload"))
    args = parser.parse_args()
    if args.operation == "upload":
        upload()
    print(json.dumps(proposal(PROPOSED_ROOT, ())))


if __name__ == "__main__":
    main()
