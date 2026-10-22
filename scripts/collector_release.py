"""Offline, commit-bound collector packaging. No network or deployment capability."""
import argparse
import ast
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tarfile

CONTRACT = "docs/database/collector_release_contract.json"
LIMIT = 4 * 1024 * 1024
FORMAT = "mosa2-collector-release-v1"
SCHEMA5_CONTRACT = "docs/database/collector_release_contract_schema5_v1.json"


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def relative(value):
    require(type(value) is str and bool(re.fullmatch(r"[A-Za-z0-9_/-]+(?:\.[A-Za-z0-9_-]+)*", value)),
            "invalid relative path")
    p = PurePosixPath(value)
    require(not p.is_absolute() and str(p) == value and all(x not in ("", ".", "..") for x in p.parts),
            "invalid relative path")
    require(not any(x.startswith(".") for x in p.parts), "hidden path")
    require(not re.search(r"(^|/)(secret|access|password|credentials)([./_-]|$)", value, re.I),
            "credential path")
    return value


def no_links(path):
    path = Path(os.path.abspath(path))
    for item in (path, *path.parents):
        require(not item.is_symlink(), "symlink")
    return path


def git(root, *args):
    return subprocess.check_output(["git", *args], cwd=root)


def canonical(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":")) + "\n").encode()


def unique(pairs):
    out = {}
    for key, value in pairs:
        require(key not in out, "duplicate JSON key")
        out[key] = value
    return out


def decode(raw):
    return json.loads(raw, object_pairs_hook=unique)


def repository(root, commit):
    root = no_links(root)
    require(bool(re.fullmatch(r"[0-9a-f]{40}", commit)), "full commit required")
    require(git(root, "rev-parse", commit + "^{commit}").decode().strip() == commit, "commit identity")
    objects = {}
    for record in git(root, "ls-tree", "-r", "-z", commit).split(b"\0"):
        if record:
            meta, path = record.split(b"\t")
            mode, kind, sha = meta.decode().split()
            objects[path.decode()] = (mode, kind, sha)

    def read(path):
        relative(path)
        require(path in objects and objects[path][0] in ("100644", "100755")
                and objects[path][1] == "blob", "missing/nonregular tracked dependency")
        local = no_links(root / path)
        require(local.is_file(), "missing dependency")
        raw = git(root, "show", commit + ":" + path)
        require(local.read_bytes() == raw, "working file differs from release commit")
        return raw

    return objects, read


def python_dependencies(path, source, known):
    """Static local imports; audited edges cover dynamic imports and file resources."""
    found = set()
    for node in ast.walk(ast.parse(source, filename=path)):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = path[:-3].split("/")[:-1]
                require(node.level <= len(parts), "relative import escapes package")
                prefix = parts[:len(parts) - node.level + 1]
                module = ".".join(prefix + ([node.module] if node.module else []))
            else:
                module = node.module or ""
            names = [module] + [module + "." + a.name for a in node.names]
        for name in names:
            if not name.startswith("scripts."):
                require(name.split(".")[0] in sys.stdlib_module_names, "non-stdlib import")
                continue
            candidate = name.replace(".", "/") + ".py"
            if candidate in known:
                found.add(candidate)
            elif not any(p.startswith(name.replace(".", "/") + "/") for p in known):
                # Imported symbols are allowed only when their parent module exists.
                parent = name.rsplit(".", 1)[0].replace(".", "/") + ".py"
                require(parent in known, "unlisted Python dependency: " + name)
    return found


def payload(root, commit, profile="historical"):
    require(profile in ("historical", "schema5"), "release profile")
    objects, read = repository(root, commit)
    contract_raw = read(CONTRACT if profile == "historical" else SCHEMA5_CONTRACT)
    contract = decode(contract_raw)
    require(contract["format"] == "mosa2-collector-release-contract-v1", "contract version")
    if profile == "schema5":
        require(contract["candidate"] == {"schema_versions": [4, 5], "default_schema": 4,
                "execution_enabled": False, "upload_enabled": False}, "candidate activation forbidden")
        require(contract["entrypoints"] == decode(read(CONTRACT))["entrypoints"], "new entrypoint")
    rows = contract["files"]
    paths = [relative(r["path"]) for r in rows]
    require(paths == sorted(set(paths)), "duplicate/unsorted paths")
    known = set(paths)
    require(set(contract["entrypoints"]) <= known and set(contract["roots"]) <= known, "entrypoint/root")
    require(all(r["mode"] == "0600" for r in rows), "payload modes")
    require(all(set(r["requires"]) <= known for r in rows), "missing dependency edge")
    graph = {r["path"]: r["requires"] for r in rows}
    reachable, pending = set(), list(contract["roots"])
    while pending:
        path = pending.pop()
        if path not in reachable:
            reachable.add(path)
            pending.extend(graph[path])
    require(reachable == known, "unreachable/unknown package file")
    files = {}
    for row in rows:
        path = row["path"]
        raw = read(path)
        require(row["source_blob"] is None or objects[path][2] == row["source_blob"],
                "qualified source changed; re-audit dependency contract")
        require(len(raw) <= LIMIT, "file size cap")
        if path.endswith(".py"):
            require(python_dependencies(path, raw.decode("utf-8"), known) <= set(row["requires"]),
                    "unrecorded static import")
        if path.endswith(".php"):
            # Includes reachable at file load: both __DIR__ forms used by this release.
            includes = re.findall(r"require(?:_once)?\s+(__DIR__|dirname\(__DIR__(?:,\s*(\d+))?\))\s*\.\s*'([^']+)'\s*;", raw.decode())
            for base, levels, tail in includes:
                directory = PurePosixPath(path).parent
                if base != "__DIR__":
                    for _ in range(int(levels or 1)):
                        directory = directory.parent
                candidate = os.path.normpath(os.path.join(str(directory), tail.lstrip("/"))).replace("\\", "/")
                require(candidate in row["requires"], "unrecorded PHP include")
        files[path] = raw
    require(sum(map(len, files.values())) <= LIMIT, "release size cap")
    template = decode(files["config/collector-private.example.json"])
    require(template["execution_enabled"] is False and template["upload_enabled"] is False
            and template["approved_root"] is None, "enabled/secret-bearing template")
    require(template["runtime"] == contract["runtime"], "runtime contract drift")
    return contract, contract_raw, files


def build(root, commit, profile="historical"):
    contract, contract_raw, files = payload(root, commit, profile)
    entries = [dict(path=p, sha256=hashlib.sha256(raw).hexdigest(), size=len(raw), mode="0600")
               for p, raw in sorted(files.items())]
    manifest = dict(format=FORMAT, commit=commit, contract_sha256=hashlib.sha256(contract_raw).hexdigest(),
                    runtime=contract["runtime"], entrypoints=contract["entrypoints"],
                    files=entries, payload_bytes=sum(e["size"] for e in entries))
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for row in entries:
            info = tarfile.TarInfo(row["path"])
            info.size, info.mode, info.mtime = row["size"], 0o600, 0
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            archive.addfile(info, io.BytesIO(files[row["path"]]))
    return output.getvalue(), canonical(manifest)


def verify(root, commit, archive, manifest, profile="historical"):
    require(len(archive) <= 2 * LIMIT and len(manifest) <= LIMIT, "artifact size cap")
    expected_archive, expected_manifest = build(root, commit, profile)
    supplied = decode(manifest)
    require(manifest == canonical(supplied) and manifest == expected_manifest, "manifest/commit mismatch")
    rows = {r["path"]: r for r in supplied["files"]}
    seen = set()
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as bundle:
        for item in bundle:
            path = relative(item.name)
            require(path in rows and path not in seen, "unknown/duplicate file")
            require(item.isfile() and item.type == tarfile.REGTYPE and not item.linkname
                    and not item.pax_headers, "link/nonregular archive member")
            row = rows[path]
            require(item.size == row["size"] and item.mode == 0o600 and item.mtime == 0
                    and item.uid == item.gid == 0 and item.uname == item.gname == "", "archive metadata")
            require(hashlib.sha256(bundle.extractfile(item).read()).hexdigest() == row["sha256"], "hash mismatch")
            seen.add(path)
    require(seen == set(rows), "missing archive dependency")
    require(archive == expected_archive, "noncanonical archive")
    return supplied


def validate_directory(directory, manifest):
    """Validate an already materialized LOCAL fixture, never a remote target."""
    root = no_links(directory)
    require(root.is_dir() and root.stat().st_uid == os.getuid()
            and stat.S_IMODE(root.stat().st_mode) == 0o700, "private directory owner/mode")
    rows = {r["path"]: r for r in manifest["files"]}
    directories = {str(p) for name in rows for p in PurePosixPath(name).parents if str(p) != "."}
    found = set()
    for current, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            path = no_links(Path(current) / name)
            rel = path.relative_to(root).as_posix()
            require(path.lstat().st_uid == os.getuid(), "unexpected owner")
            mode = path.lstat().st_mode
            if stat.S_ISDIR(mode):
                require(rel in directories and stat.S_IMODE(mode) == 0o700, "unexpected/public directory")
            else:
                require(stat.S_ISREG(mode) and rel in rows and stat.S_IMODE(mode) == 0o600,
                        "unknown/nonregular/public file")
                row = rows[rel]
                require(path.stat().st_size == row["size"] and
                        hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"], "file integrity")
                found.add(rel)
    require(found == set(rows), "missing materialized dependency")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("build", "verify"))
    parser.add_argument("--commit", required=True)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", choices=("historical", "schema5"), default="historical")
    args = parser.parse_args()
    args.output = no_links(args.output)
    stem = args.output / args.commit
    if args.operation == "build":
        archive, manifest = build(args.root, args.commit, args.profile)
        require(not args.output.exists(), "output must be new local directory")
        args.output.mkdir(mode=0o700, parents=False)
        for suffix, raw in ((".tar", archive), (".manifest.json", manifest)):
            with open(str(stem) + suffix, "xb") as f:
                os.chmod(f.name, 0o600)
                f.write(raw)
    archive_path = no_links(str(stem) + ".tar")
    manifest_path = no_links(str(stem) + ".manifest.json")
    result = verify(args.root, args.commit, archive_path.read_bytes(), manifest_path.read_bytes(), args.profile)
    print(json.dumps(dict(status="PASS", commit=args.commit, file_count=len(result["files"]),
                         payload_bytes=result["payload_bytes"],
                         archive_sha256=hashlib.sha256(Path(str(stem) + ".tar").read_bytes()).hexdigest(),
                         manifest_sha256=hashlib.sha256(Path(str(stem) + ".manifest.json").read_bytes()).hexdigest())))


if __name__ == "__main__":
    main()
