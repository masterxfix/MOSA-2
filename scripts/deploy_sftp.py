"""Validate and deploy the tracked MOSA-2 web project through SFTP only."""

import argparse
import base64
import errno
import hashlib
from html.parser import HTMLParser
import hmac
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
SITE = "mosa.scharwerk.de"
ABSOLUTE_ROOT = f"/var/www/vhosts/web213.server10.configcenter.info/{SITE}"
TARGET_PATHS = {SITE, f"/{SITE}", ABSOLUTE_ROOT}
SECRET_NAMES = tuple("MOSA_DEPLOY_" + name for name in (
    "HOST", "PORT", "USER", "PASSWORD", "PATH", "HOST_KEY_SHA256"
))
EXCLUDED_DIRS = {".git", ".github", "docs", "scripts", "tests", "node_modules"}
EXCLUDED_FILES = {"AGENTS.md", "README.md", ".gitignore", ".gitattributes"}


class VisibleHTML(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
            "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        style = re.sub(r"\s", "", attrs.get("style", "")).lower()
        hidden = (any(item[1] for item in self.stack)
                  or tag in {"head", "script", "style", "template"}
                  or "hidden" in attrs or attrs.get("aria-hidden") == "true"
                  or "display:none" in style or "visibility:hidden" in style)
        if tag not in self.VOID:
            self.stack.append((tag, hidden))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        if not any(item[1] for item in self.stack):
            self.text.append(data)


def validate_html(content):
    parser = VisibleHTML()
    parser.feed(content.decode("utf-8"))
    parser.close()
    if not re.search(r"\bMOSA\b", " ".join(parser.text)):
        raise ValueError("index.html must contain visible MOSA text")


def web_files(root=ROOT):
    entries = subprocess.check_output(
        ["git", "ls-files", "--stage", "-z"], cwd=root
    ).decode("utf-8").split("\0")
    files = []
    for entry in filter(None, entries):
        metadata, name = entry.split("\t", 1)
        path = PurePosixPath(name)
        if path.parts[0] in EXCLUDED_DIRS or name in EXCLUDED_FILES:
            continue
        if (path.is_absolute() or ".." in path.parts or "\\" in name
                or any(ord(char) < 32 for char in name)
                or any(part.startswith(".env") for part in path.parts)
                or path.suffix.lower() in {".pem", ".key", ".p12", ".pfx"}
                or any(part.startswith(".") and part not in
                       {".htaccess", ".user.ini", ".well-known"} for part in path.parts)):
            raise ValueError("Unsafe or sensitive file in deployment package")
        local = root.joinpath(*path.parts)
        if metadata.split()[0] not in {"100644", "100755"} or local.is_symlink():
            raise ValueError("Symlinks and submodules cannot be deployed")
        if any(parent.is_symlink() for parent in local.parents if parent != root.parent):
            raise ValueError("Symlink in local source path")
        files.append((name, local.read_bytes()))
    contents = dict(files)
    if "index.html" not in contents:
        raise ValueError("Tracked, readable index.html is required")
    validate_html(contents["index.html"])
    return files


def configuration(env=None):
    env = os.environ if env is None else env
    missing = [name for name in SECRET_NAMES if not env.get(name)]
    if missing:
        raise ValueError("Missing GitHub Actions secrets: " + ", ".join(missing))
    config = {name.removeprefix("MOSA_DEPLOY_").lower(): env[name]
              for name in SECRET_NAMES}
    if config["host"] not in {"server10.configcenter.info", SITE}:
        raise ValueError("MOSA_DEPLOY_HOST must identify the MOSA-2 hosting server")
    if not config["port"].isdigit() or not 1 <= int(config["port"]) <= 65535:
        raise ValueError("MOSA_DEPLOY_PORT must be a valid SFTP port")
    config["port"] = int(config["port"])
    if config["path"] not in TARGET_PATHS:
        raise ValueError("MOSA_DEPLOY_PATH must be the exact MOSA-2 document root")
    if not re.fullmatch(r"SHA256:[A-Za-z0-9+/]{43}", config["host_key_sha256"]):
        raise ValueError("MOSA_DEPLOY_HOST_KEY_SHA256 must be a verified SHA256 fingerprint")
    return config


def verify_fingerprint(key_bytes, expected):
    actual = "SHA256:" + base64.b64encode(hashlib.sha256(key_bytes).digest()).decode().rstrip("=")
    if not hmac.compare_digest(actual, expected):
        raise ValueError("SFTP server host key does not match the verified fingerprint")


def remote_kind(sftp, path):
    try:
        return sftp.lstat(path).st_mode
    except OSError as error:
        if error.errno == errno.ENOENT:
            return None
        raise


def check_remote(sftp, root, name="", *, scoped=False):
    """Check every existing ancestor and destination without following symlinks."""
    target = PurePosixPath(root) / name
    parts = target.relative_to(root).parts if scoped else target.parts[1:]
    current = root if scoped else ""
    if scoped:
        mode = remote_kind(sftp, root)
        if mode is None or not stat.S_ISDIR(mode):
            raise ValueError("Scoped document root must be an existing directory")
    for index, part in enumerate(parts):
        current += "/" + part
        mode = remote_kind(sftp, current)
        if mode is None:
            continue
        directory = index < len(parts) - 1 or not name
        if not (stat.S_ISDIR(mode) if directory else stat.S_ISREG(mode)):
            raise ValueError("Remote path contains a symlink or unexpected file type")


TEST_ROOT = "/var/www/vhosts/web213.server10.configcenter.info/mosa2-test.scharwerk.de"


def upload(sftp, root, files, *, profile="legacy"):
    roots = {"legacy": {f"/{SITE}", ABSOLUTE_ROOT}, "test": {TEST_ROOT}}
    if profile not in roots or root not in roots[profile]:
        raise ValueError("Canonical SFTP root is outside the MOSA-2 document root")
    # Validate the entire explicit file set before any remote access.
    names = set()
    for name, _ in files:
        path = PurePosixPath(name)
        if (not name or path.is_absolute() or path.as_posix() != name
                or ".." in path.parts or "\\" in name
                or any(ord(c) < 32 for c in name) or name in names):
            raise ValueError("Unsafe or duplicate deployment filename")
        names.add(name)
    scoped = profile == "test"
    check_remote(sftp, root, scoped=scoped)
    mode = remote_kind(sftp, root)
    if mode is None or not stat.S_ISDIR(mode):
        raise ValueError("MOSA-2 document root must already exist")
    # Preflight the whole package before creating a directory or writing a file.
    for name, _ in files:
        check_remote(sftp, root, name, scoped=scoped)
    for name, data in files:
        check_remote(sftp, root, name, scoped=scoped)
        parent = PurePosixPath(name).parent
        current = root
        for part in parent.parts:
            current += "/" + part
            if remote_kind(sftp, current) is None:
                sftp.mkdir(current)
        target = root + "/" + name
        temporary = str(PurePosixPath(target).with_name(".mosa-upload-" + uuid.uuid4().hex))
        with sftp.open(temporary, "wx") as output:
            output.write(data)
        with sftp.open(temporary, "rb") as uploaded:
            digest = hashlib.file_digest(uploaded, "sha256").digest()
        if digest != hashlib.sha256(data).digest():
            raise ValueError("SFTP upload readback mismatch")
        check_remote(sftp, root, name, scoped=scoped)
        sftp.posix_rename(temporary, target)
    site = "mosa2-test.scharwerk.de" if scoped else SITE
    print(f"Deployed {len(files)} verified files to https://{site}")


def deploy(config, files):
    import paramiko

    class PinnedHostKey(paramiko.MissingHostKeyPolicy):
        def missing_host_key(self, client, hostname, key):
            verify_fingerprint(key.asbytes(), config["host_key_sha256"])

    with paramiko.SSHClient() as client:
        client.set_missing_host_key_policy(PinnedHostKey())
        client.connect(config["host"], port=config["port"], username=config["user"],
                       password=config["password"], allow_agent=False, look_for_keys=False,
                       timeout=20, banner_timeout=20, auth_timeout=20, channel_timeout=20)
        with client.open_sftp() as sftp:
            sftp.get_channel().settimeout(30)
            upload(sftp, sftp.normalize(config["path"]), files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "check-config", "deploy"))
    command = parser.parse_args().command
    if command == "check-config":
        configuration()
        print("All deployment secrets and target restrictions are valid")
    elif command == "validate":
        print(f"Validated {len(web_files())} deployable web files")
    else:
        config = configuration()  # Must run before loading client or opening network.
        deploy(config, web_files())


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Never print remote errors: they may contain usernames or connection data.
        message = str(error) if isinstance(error, ValueError) else type(error).__name__
        print(f"Deployment aborted: {message}", file=sys.stderr)
        sys.exit(1)
