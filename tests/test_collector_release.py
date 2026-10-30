"""Offline release, dependency, integrity and locked-deployment regression tests."""
import base64
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from scripts import collector_release as release
from scripts import deploy_private_collector as private
from scripts.market_collector import live_bridge
import test_market_collector_v1 as fixtures

ROOT = Path(__file__).resolve().parents[1]


class ReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
        cls.archive, cls.manifest = release.build(ROOT, cls.commit)
        cls.metadata = release.verify(ROOT, cls.commit, cls.archive, cls.manifest)

    def materialize(self, root):
        root.mkdir(mode=0o700)
        with tarfile.open(fileobj=io.BytesIO(self.archive), mode="r:") as bundle:
            for member in bundle:
                dest = root / member.name
                for directory in reversed(dest.parents):
                    if directory == root or root in directory.parents:
                        directory.mkdir(mode=0o700, exist_ok=True)
                with dest.open("xb") as f:
                    f.write(bundle.extractfile(member).read())
                dest.chmod(0o600)
        return root

    def mutated_tar(self, change):
        output = io.BytesIO()
        with tarfile.open(fileobj=io.BytesIO(self.archive), mode="r:") as source, \
             tarfile.open(fileobj=output, mode="w", format=tarfile.USTAR_FORMAT) as target:
            for index, member in enumerate(source):
                raw = source.extractfile(member).read()
                edited = change(index, member, raw)
                if edited is not None:
                    member, raw = edited
                    target.addfile(member, io.BytesIO(raw) if member.isfile() else None)
        return output.getvalue()

    def test_reproducible_commit_hashes_sizes_modes_and_exact_closure(self):
        self.assertEqual((self.archive, self.manifest), release.build(ROOT, self.commit))
        self.assertEqual(self.metadata["commit"], self.commit)
        self.assertEqual(len(self.metadata["files"]), 33)
        self.assertLess(self.metadata["payload_bytes"], 4 * 1024 * 1024)
        self.assertTrue(all(r["mode"] == "0600" for r in self.metadata["files"]))
        self.assertEqual(sum(r["size"] for r in self.metadata["files"]), self.metadata["payload_bytes"])
        with tempfile.TemporaryDirectory() as tmp:
            root = self.materialize(Path(tmp)/"release")
            release.validate_directory(root, self.metadata)

    def test_archive_rejects_paths_links_duplicate_unknown_metadata_and_corruption(self):
        def altered(field, value):
            def change(index, item, raw):
                if index == 0:
                    setattr(item, field, value)
                return item, raw
            return change
        cases = [altered("name", p) for p in ("../escape", "/absolute", "a/../../b", "a\\b", "a//b",
                                            "./a", ".env", "scripts/unknown.py")]
        cases += [altered("type", tarfile.SYMTYPE), altered("type", tarfile.LNKTYPE),
                  altered("mode", 0o644), altered("mtime", 1), altered("uid", 1),
                  altered("name", self.metadata["files"][1]["path"]),
                  lambda i, m, b: None if i == 0 else (m, b),
                  lambda i, m, b: (m, bytes([b[0] ^ 1]) + b[1:]) if i == 0 else (m, b)]
        for change in cases:
            with self.subTest(change=change), self.assertRaises(ValueError):
                release.verify(ROOT, self.commit, self.mutated_tar(change), self.manifest)

    def test_manifest_forgery_other_commit_and_unknown_json_fail_closed(self):
        for field, value in (("commit", "0"*40), ("payload_bytes", 0), ("unknown", True)):
            m = copy.deepcopy(self.metadata);m[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                release.verify(ROOT, self.commit, self.archive, release.canonical(m))
        with self.assertRaises(ValueError):
            release.verify(ROOT, "main", self.archive, self.manifest)
        with self.assertRaises(ValueError):
            release.decode(b'{"commit":1,"commit":2}')

    def test_materialized_missing_extra_symlinks_modes_and_hashes_rejected(self):
        for change in ("missing", "unknown", "symlink", "parent-link", "mode", "hash", "extra-dir"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as tmp:
                root = self.materialize(Path(tmp)/"release")
                path = root/self.metadata["files"][0]["path"]
                if change == "missing":path.unlink()
                elif change == "unknown":(root/"password.txt").write_text("SYNTHETIC-NOT-A-SECRET")
                elif change == "symlink":
                    path.unlink();path.symlink_to(ROOT/"AGENTS.md")
                elif change == "parent-link":
                    other = Path(tmp)/"aliased";root.rename(other);root.symlink_to(other, target_is_directory=True)
                elif change == "mode":path.chmod(0o644)
                elif change == "hash":path.write_bytes(b"changed")
                else:(root/"unknown").mkdir(mode=0o700)
                with self.assertRaises(ValueError):release.validate_directory(root, self.metadata)

    def test_git_source_and_static_missing_dependencies_fail_closed(self):
        known = {"scripts/x/a.py"}
        with self.assertRaises(ValueError):
            release.python_dependencies("scripts/x/a.py", "from scripts.missing import thing", known)
        # Working-tree tampering is tested in an isolated local clone; no network.
        with tempfile.TemporaryDirectory() as tmp:
            clone = Path(tmp)/"repo"
            subprocess.run(["git", "clone", "--quiet", "--no-hardlinks", str(ROOT), str(clone)], check=True)
            path = clone/"scripts/market_collector/contracts.py"
            path.write_bytes(path.read_bytes()+b"\n# changed\n")
            with self.assertRaisesRegex(ValueError, "differs"):release.build(clone, self.commit)
            subprocess.run(["git", "restore", "--", str(path.relative_to(clone))], cwd=clone, check=True)
            path.unlink();path.symlink_to(ROOT/"scripts/market_collector/contracts.py")
            with self.assertRaisesRegex(ValueError, "symlink"):release.build(clone, self.commit)

    def test_package_has_no_secret_environment_or_unlisted_private_files(self):
        sentinel = "SYNTHETIC-CREDENTIAL-CANARY-DO-NOT-PACKAGE"
        with patch.dict(os.environ, {"MOSA_TEST_DB_PASSWORD": sentinel,
                                     "MOSA_TEST_SFTP_PASSWORD": sentinel}), \
             patch.object(socket, "socket", side_effect=AssertionError("offline only")):
            archive, manifest = release.build(ROOT, self.commit)
        self.assertNotIn(sentinel.encode(), archive+manifest)
        names = {r["path"] for r in self.metadata["files"]}
        self.assertFalse(any("tests/" in n or "diagnostic" in n or "actions_acceptance" in n for n in names))
        self.assertNotIn("scripts/deploy_sftp.py", names)
        template = json.loads((ROOT/"config/collector-private.example.json").read_text())
        self.assertIsNone(template["approved_root"])
        self.assertFalse(template["execution_enabled"])
        self.assertFalse(template["upload_enabled"])

    def test_packaged_php_include_closure_is_loadable_with_no_legacy_main(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.materialize(Path(tmp)/"release")
            code = 'require $argv[1]; echo json_encode(get_included_files());'
            result = subprocess.run(["php", "-r", code, str(root/"scripts/market_collector/live_batch.php")],
                                    capture_output=True, text=True, check=True, timeout=10)
            included = {Path(p).relative_to(root).as_posix() for p in json.loads(result.stdout)}
            contract = json.loads((ROOT/release.CONTRACT).read_text())
            graph = {r["path"]: r["requires"] for r in contract["files"]}
            expected, pending = set(), ["scripts/market_collector/live_batch.php"]
            while pending:
                path = pending.pop()
                if path in expected:continue
                expected.add(path)
                pending.extend(p for p in graph[path] if p.endswith(".php"))
            self.assertEqual(included, expected)
            self.assertFalse(result.stderr)
            release.validate_directory(root, self.metadata)

    def test_same_package_for_one_two_five_assets_and_real_normalizer_replay(self):
        fixture = fixtures.FrankfurtCollectorTests();fixture.setUp()
        acquired = dict(adapter_module="scripts.market_collector.boerse_frankfurt",
                        adapter_class="FrankfurtSnapshotV1", provider_key=fixture.adapter.provider_key,
                        instrument=fixture.request.instrument, request_key=fixture.request.request_key,
                        requested_at=fixture.request.requested_at,
                        response=None)
        # Explicit response serialization uses the unchanged bridge transport.
        from dataclasses import asdict, replace
        from test_market_live_batch import isin
        acquired["response"] = live_bridge.transport(asdict(fixture.response))
        with tempfile.TemporaryDirectory() as tmp:
            root = self.materialize(Path(tmp)/"release")
            for size in (1, 2, 5):
                for index in range(size):
                    route = dict(fixture.route.route, id=str(302+index), asset_id=str(102+index))
                    instrument = isin(index+1)
                    document = json.loads(fixture.response.payload_bytes)
                    document["isin"] = instrument
                    response = replace(fixture.response, payload_bytes=json.dumps(document).encode())
                    item = dict(acquired, instrument=instrument,
                                response=live_bridge.transport(asdict(response)))
                    request = dict(action="plan", acquired=item, route=route,
                                   created_at=fixture.created, existing=[])
                    expected = live_bridge.run(request)
                    self.assertEqual(expected["plan"]["decision"], "INSERT")
                    result = subprocess.run([sys.executable, "-I", "-B",
                                str(root/"scripts/market_collector/live_bridge.py")],
                                input=json.dumps(request), capture_output=True, text=True, check=True, timeout=20)
                    self.assertEqual(json.loads(result.stdout), expected)
                    self.assertFalse(result.stderr)
                    plan = expected["plan"]
                    request = dict(action="replay", route=route, stored=plan["normalized"],
                        created_at=fixture.created, existing=[dict(format_version=2,
                            payload=plan["normalized"], dedupe_key=plan["dedupe_key"])])
                    result = subprocess.run([sys.executable, "-I", "-B",
                                str(root/"scripts/market_collector/live_bridge.py")],
                                input=json.dumps(request), capture_output=True, text=True, check=True, timeout=20)
                    self.assertEqual(json.loads(result.stdout), live_bridge.run(request))
                    self.assertEqual(json.loads(result.stdout)["plan"]["decision"], "DUPLICATE_UNCHANGED")
            release.validate_directory(root, self.metadata)

    def test_runtime_pins_and_child_php_path_are_fixed_without_core_changes(self):
        runtime = (ROOT/"scripts/collector_release/runtime.php").read_text()
        contract = json.loads((ROOT/release.CONTRACT).read_text())
        for text in ("/opt/alt/python311/bin/python3.11", "3.11.17",
                     "/opt/plesk/php/8.4/bin/php", "8.4.12",
                     "/opt/plesk/php/8.4/bin:/usr/bin:/bin"):
            self.assertIn(text, runtime)
        self.assertNotIn("MarketBatch\\run(", runtime)
        for row in contract["files"]:
            if row["path"].startswith("scripts/market_collector/") or "/phase" in row["path"]:
                self.assertIsNotNone(row["source_blob"])


class PrivateDeploymentTests(unittest.TestCase):
    def test_missing_or_forged_approval_always_blocks_before_remote_or_environment_access(self):
        class NoRemote:
            def __getattr__(self, key):raise AssertionError("remote access")
        with patch.dict(os.environ, {}, clear=True):
            for approved in (None, False, True, {"authorized": True, "root": private.PROPOSED_ROOT}):
                with self.assertRaises(PermissionError):
                    private.upload(NoRemote(), approval=approved)

    def test_proposal_is_not_authorization_and_rejects_webroots_and_path_manipulation(self):
        result = private.proposal(private.PROPOSED_ROOT, ())
        self.assertFalse(result["authorized"])
        self.assertFalse(result["remote_verified"])
        self.assertFalse(result["upload_enabled"])
        self.assertEqual(result["plan_reserve_bytes"], 64*1024*1024)
        for path in (private.shared.TEST_ROOT, private.shared.ABSOLUTE_ROOT, "/", "../x",
                     private.PROPOSED_ROOT+"/../x", private.PROPOSED_ROOT+"/", private.PROPOSED_ROOT+"//x",
                     private.shared.TEST_ROOT+"/private", "/var/www/vhosts"):
            with self.subTest(path=path), self.assertRaises(ValueError):private.proposal(path, ())
        with self.assertRaises(ValueError):
            private.proposal(private.PROPOSED_ROOT, (private.PROPOSED_ROOT,))

    def test_shared_host_key_algorithm_and_existing_deployment_are_unchanged(self):
        key = b"SYNTHETIC-HOST-KEY"
        pin = "SHA256:"+base64.b64encode(hashlib.sha256(key).digest()).decode().rstrip("=")
        private.verify_host_key_material(key, pin)
        with self.assertRaises(ValueError):private.verify_host_key_material(b"wrong", pin)
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
        paths = ("scripts/deploy_sftp.py", "scripts/deploy_test_sftp.py",
                 ".github/workflows/deploy-testsite.yml")
        expected_blobs = {"scripts/deploy_sftp.py":"7678f600876b72899da9f35b4ca21b23ba22868c","scripts/deploy_test_sftp.py":"cf4f5cce8225168d3783139bd740ca420ac79233",".github/workflows/deploy-testsite.yml":"1d06c152acd88a74e775c8c96caa0a82d525d8d1"}
        for path in paths:
            self.assertEqual(release.git(ROOT, "rev-parse", commit+":"+path).decode().strip(),
                             expected_blobs[path])


class RuntimeCorrectionTests(unittest.TestCase):
    def setUp(self):
        from scripts import collector_schema4_once as once
        self.once = once
        self.php = dict(version="8.4.12",binary=once.PHP,sapi="cli",pdo_mysql=True)
        self.python = dict(version="3.11.17",executable=once.PYTHON,resolved_executable=once.PYTHON,
            berlin=True,loaded_ca=0,loaded_x509=0,verify_mode="CERT_REQUIRED",check_hostname=True,
            ca_source_verified=True,ca_source_kind="DEFAULT_CAPATH_HASH_ENTRY_PARSED",
            ca_file=None,ca_path="/configured/ca",ca_path_entry="0123abcd.0",ca_entries_examined=1,
            ca_candidates_checked=1,ca_failure_code=None,ssl_environment_overrides_absent=True,
            php_child=dict(version="8.4.12",binary=once.PHP))

    def measure(self, python=None, php=None, result=None):
        result = {} if result is None else result
        replies = [(0,json.dumps(self.php if php is None else php).encode(),False,1),
                   (0,json.dumps(self.python if python is None else python).encode(),False,1)]
        with patch.object(self.once.remote,"remote_call",side_effect=replies):
            return self.once.runtime(object(),result)

    def test_lazy_ca_with_zero_loaded_count_passes_without_weakening_tls(self):
        result = self.measure()
        self.assertEqual(result["python"]["loaded_ca"],0)
        self.assertEqual(set(result["checks"].values()),{"PASS"})
        self.assertEqual(result["python"]["provider_tls"],"NOT_CHECKED")
        self.assertEqual(result["python"]["ca_source_scope"],"LOCAL_SOURCE_ONLY_NOT_PROVIDER_TLS")
        for field,value,code in (("ca_source_verified",False,"DEFAULT_CA_SOURCE_UNAVAILABLE"),
                                 ("verify_mode","OTHER","TLS_CERT_REQUIRED"),
                                 ("check_hostname",False,"TLS_HOSTNAME_REQUIRED")):
            measured = {};data = copy.deepcopy(self.python);data[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(self.once.RuntimeRejected,code):
                self.measure(data,result=measured)
            self.assertEqual(measured["failure_code"],code)
            self.assertEqual(measured["checks"][code],"FAIL")

    def test_execute_retains_version_mismatch_and_blocks_before_installation(self):
        from contextlib import contextmanager
        from unittest.mock import Mock
        once = self.once;commit = "a"*40
        env = dict(MOSA_SCHEMA4_EXPECTED_COMMIT=commit,MOSA_SCHEMA4_AUTHORIZATION=once.TOKEN+commit,
            GITHUB_SHA=commit,GITHUB_RUN_ID="123",GITHUB_ACTIONS="true",GITHUB_RUN_ATTEMPT="1",
            GITHUB_EVENT_NAME="workflow_dispatch",GITHUB_REF="refs/heads/main",GITHUB_REPOSITORY="masterxfix/MOSA-2")
        data = copy.deepcopy(self.python);data.update(version="3.11.18",secret="SYNTHETIC-DO-NOT-PRINT")
        @contextmanager
        def ssh(*args):
            yield object()
        replies = [(0,json.dumps(self.php).encode(),False,1),(0,json.dumps(data).encode(),False,1)]
        with patch.object(once.shared,"configuration",return_value={}), \
             patch.object(once.release,"git",return_value=(commit+"\n").encode()), \
             patch.object(once.upload,"artifact",return_value=({},b"{}",{})), \
             patch.object(once.shared,"ssh_client",side_effect=ssh), \
             patch.object(once.remote,"remote_call",side_effect=replies), \
             patch.object(once.upload,"upload") as install:
            report = once.execute(env,paramiko=Mock())
        install.assert_not_called()
        self.assertEqual(report["stage"],"runtime")
        self.assertEqual(report["provider_requests"],0)
        self.assertEqual(report["failure"],"RUNTIME_PYTHON_VERSION_MISMATCH")
        self.assertEqual(report["runtime"]["python"]["version"],"3.11.18")
        self.assertEqual(report["runtime"]["python"]["expected_version"],"3.11.17")
        self.assertEqual(report["runtime"]["php"]["version"],"8.4.12")
        self.assertNotIn("SYNTHETIC-DO-NOT-PRINT",json.dumps(report))

    def test_failed_probe_marks_missing_measurements_and_suppresses_stderr(self):
        measured = {}
        with patch.object(self.once.remote,"remote_call",return_value=(127,b"",True,1)), \
             self.assertRaisesRegex(self.once.RuntimeRejected,"PHP_PROBE_FAILED"):
            self.once.runtime(object(),measured)
        self.assertIsNone(measured["python"]["version"])
        self.assertIsNone(measured["php"]["version"])
        self.assertEqual(measured["null_means"],"NOT_MEASURED")
        self.assertEqual(measured["checks"]["PYTHON_VERSION_MISMATCH"],"NOT_MEASURED")

    def test_real_probe_and_supervisor_request_the_same_clean_environment(self):
        import ast,shlex
        replies = [(0,json.dumps(self.php).encode(),False,1),(0,json.dumps(self.python).encode(),False,1)]
        with patch.object(self.once.remote,"remote_call",side_effect=replies) as remote:
            self.once.runtime(object())
        for call in remote.call_args_list:
            args = shlex.split(call.args[1])
            self.assertEqual(args[:4],["/usr/bin/env","-i","PATH="+self.once.CLEAN_ENV["PATH"],"PYTHONDONTWRITEBYTECODE=1"])
        args = shlex.split(remote.call_args_list[1].args[1])
        self.assertEqual(args[4:8],[self.once.PYTHON,"-I","-B","-c"])
        self.assertEqual(args[8],self.once.RUNTIME_PROBE)
        tree = ast.parse((ROOT/"scripts/collector_dogado_pne_remote.py").read_text())
        child = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="child")
        popen = next(n for n in ast.walk(child) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=="Popen")
        env = next(k.value for k in popen.keywords if k.arg=="env")
        self.assertEqual({k.arg:ast.literal_eval(k.value) for k in env.keywords},self.once.CLEAN_ENV)

    def test_capath_requires_a_parsed_ca_and_matching_openssl_lookup_hash(self):
        from contextlib import contextmanager
        from types import SimpleNamespace
        from unittest.mock import Mock
        import ssl
        scope = {"__name__":"fixture"}
        exec(compile(self.once.RUNTIME_PROBE,"<local-ca-probe>","exec"),scope)
        entry = SimpleNamespace(name="0123abcd.0",path="/configured/ca/0123abcd.0")
        @contextmanager
        def entries(path):
            self.assertEqual(path,"/configured/ca")
            yield iter([entry])
        context = Mock();context.cert_store_stats.return_value = {"x509_ca":0}
        paths = SimpleNamespace(cafile=None,capath="/configured/ca")
        scope["os"] = SimpleNamespace(stat=Mock(return_value=SimpleNamespace(st_mode=stat.S_IFREG|0o644,st_size=1024)),scandir=entries)
        for ca_count, subject_hash, expected in ((1,b"0123abcd\n",True),(1,b"ffffffff\n",False),(0,b"0123abcd\n",False)):
            with self.subTest(ca_count=ca_count,subject_hash=subject_hash):
                diagnostic = Mock();diagnostic.cert_store_stats.return_value = {"x509_ca":ca_count}
                scope["ssl"] = SimpleNamespace(SSLContext=Mock(return_value=diagnostic),PROTOCOL_TLS_CLIENT=ssl.PROTOCOL_TLS_CLIENT,SSLError=ssl.SSLError)
                run = Mock(return_value=SimpleNamespace(returncode=0,stdout=subject_hash,stderr=b""))
                scope["subprocess"] = SimpleNamespace(run=run,DEVNULL=subprocess.DEVNULL,TimeoutExpired=subprocess.TimeoutExpired)
                result = scope["ca_source"](context,paths)
                self.assertIs(result["ca_source_verified"],expected)
                diagnostic.load_verify_locations.assert_called_once_with(cafile=entry.path)
                if expected:
                    self.assertEqual(result["ca_source_kind"],"DEFAULT_CAPATH_HASH_ENTRY_PARSED")
                    run.assert_called_once()
                    self.assertEqual(run.call_args.kwargs["env"],self.once.CLEAN_ENV)
                    self.assertEqual(result["ca_candidates_checked"],1)
        result = scope["ca_source"](context,SimpleNamespace(cafile=None,capath=None))
        self.assertFalse(result["ca_source_verified"])
        self.assertEqual(result["ca_failure_code"],"NO_USABLE_DEFAULT_CA_SOURCE")


class Schema4OnceTests(unittest.TestCase):
    """Bounded new-profile proof; existing Current/batch fixtures supply business contracts."""
    @classmethod
    def setUpClass(cls):
        from scripts import collector_schema4_once as once
        cls.once = once
        from historical_release_fixture import candidate_checkout
        paths = [".github/workflows/collector-schema4-once.yml", release.SCHEMA4_ONCE_CONTRACT,
                 "scripts/collector_private_upload_remote.py", "scripts/collector_release.py",
                 "scripts/deploy_private_collector.py", "scripts/collector_schema4_once.php",
                 "scripts/collector_schema4_once.py", "scripts/collector_schema4_once_remote.py",
                 "tests/test_collector_release.py", "tests/historical_release_fixture.py"]
        base = release.git(ROOT, "rev-parse", "HEAD").decode().strip()
        context = candidate_checkout(ROOT, base, paths)
        cls.candidate, cls.commit = context.__enter__()
        cls.addClassCleanup(context.__exit__, None, None, None)
        cls.archive, cls.manifest = release.build(cls.candidate, cls.commit, "schema4-once")
        cls.meta = release.verify(cls.candidate, cls.commit, cls.archive, cls.manifest, "schema4-once")

    def env(self, run="123"):
        return dict(MOSA_SCHEMA4_EXPECTED_COMMIT=self.commit,
                    MOSA_SCHEMA4_AUTHORIZATION=self.once.TOKEN+self.commit,
                    GITHUB_SHA=self.commit, GITHUB_RUN_ID=run, GITHUB_ACTIONS="true",
                    GITHUB_RUN_ATTEMPT="1", GITHUB_EVENT_NAME="workflow_dispatch",
                    GITHUB_REF="refs/heads/main", GITHUB_REPOSITORY="masterxfix/MOSA-2")

    def test_exact_package_dependency_closure_and_forgery_rejection(self):
        names = {r["path"] for r in self.meta["files"]}
        self.assertTrue({"scripts/collector_schema4_once.php", "scripts/market_current/refresh.php",
                         "scripts/market_current/planner.py", "scripts/market_current/selection.php",
                         "scripts/market_collector/schema_contract.php", "api/current_read.php"} <= names)
        self.assertFalse(any("remote" in p or "deploy" in p or p.startswith("tests/") for p in names))
        self.assertEqual((self.archive, self.manifest), release.build(self.candidate, self.commit, "schema4-once"))
        for key, value in (("commit", "b"*40), ("payload_bytes", 1), ("unknown", True)):
            m = copy.deepcopy(self.meta);m[key] = value
            with self.assertRaises(ValueError):
                release.verify(self.candidate, self.commit, self.archive, release.canonical(m), "schema4-once")
        with self.assertRaises(ValueError):
            release.verify(self.candidate, self.commit, self.archive[:-1], self.manifest, "schema4-once")
        # Existing fault-injection method: keep wrong source pins and missing includes fatal.
        objects, read = release.repository(self.candidate, self.commit)
        for defect in ("source", "edge"):
            contract = json.loads(read(release.SCHEMA4_ONCE_CONTRACT))
            if defect == "source":
                contract["files"][0]["source_blob"] = "0"*40
            else:
                row = next(r for r in contract["files"] if r["path"] == "api/observations_read.php")
                row["requires"].remove("api/current_read.php")
            def altered(path):
                return release.canonical(contract) if path == release.SCHEMA4_ONCE_CONTRACT else read(path)
            with patch.object(release, "repository", return_value=(objects, altered)), self.assertRaises(ValueError):
                release.build(self.candidate, self.commit, "schema4-once")
        historical = json.loads((ROOT/release.CONTRACT).read_text())
        self.assertEqual(len(historical["files"]), 33)
        self.assertEqual(private.ARCHIVE_SHA256, "73e34c8d8e13ce37265ef5dded1ceae162140eee5b17341b23ee7dae3e3a68f7")

    def test_commit_attempt_ref_and_manifest_are_bound_before_remote_effects(self):
        self.assertEqual(self.once.authorize(self.env()), (self.commit, "schema4-"+self.commit+"-123"))
        for key, value in (("GITHUB_RUN_ATTEMPT", "2"), ("GITHUB_REF", "refs/heads/other"),
                           ("GITHUB_EVENT_NAME", "schedule"), ("GITHUB_SHA", "b"*40),
                           ("MOSA_SCHEMA4_AUTHORIZATION", private.TOKEN+self.commit)):
            env = self.env();env[key] = value
            with self.subTest(key=key), self.assertRaises(PermissionError):
                self.once.authorize(env)
        scope = {"__name__": "fixture"}
        exec(compile(private.remote_source("schema4-once", self.meta), "<schema4-upload>", "exec"), scope)
        d = dict(commit=self.commit, authorization=self.once.TOKEN+self.commit, run_id="123",
                 manifest=self.meta, manifest_sha256=hashlib.sha256(self.manifest).hexdigest())
        self.assertEqual(scope["plan"](d)[0], self.commit)
        m = copy.deepcopy(self.meta);m["files"][0]["sha256"] = "0"*64
        d.update(manifest=m, manifest_sha256=hashlib.sha256(release.canonical(m)).hexdigest())
        with self.assertRaisesRegex(Exception, "EXACT_SCHEMA4_MANIFEST"):
            scope["plan"](d)

    def supervisor(self, ambiguous=False):
        from types import SimpleNamespace
        from unittest.mock import Mock
        scope = {"__name__": "fixture"}
        # The existing child supervisor is Linux-only. This test injects the OS
        # and child results below; importing its two POSIX modules is doubled on Windows.
        platform_modules = {name: Mock() for name in ("fcntl", "resource")} if os.name == "nt" else {}
        with patch.dict(sys.modules, platform_modules):
            exec(compile(self.once.remote_source(self.meta), "<schema4-once>", "exec"), scope)
        created = set();saved = {}
        def mkdir(name, mode, dir_fd):
            key = (dir_fd, name)
            if key in created:
                raise FileExistsError()
            created.add(key)
        scope["os"] = SimpleNamespace(mkdir=mkdir, fsync=lambda fd: None, close=lambda fd: None,
                                       umask=lambda mode: None, lstat=lambda path: object())
        scope["guard"] = lambda: None
        scope["audit"] = lambda *args: None
        scope["folder"] = lambda path: 1 if path.endswith("/locks") else 2 if path.endswith("/runs") else 3
        scope["new_metadata"] = lambda *args: None
        scope["file_once"] = lambda fd, name, raw: saved.setdefault(name, raw)
        answer = dict(ok=True, status="COMPLETE", provider_requests=1,
                      display=dict(name="Synthetic", price="123.4500000000", unit="EUR", unit_version="1",
                                   source="Synthetic Frankfurt", venue="XFRA", market_at="2026-10-30T10:00:00Z",
                                   observed_at="2026-10-30T10:01:00Z"))
        scope["child"] = Mock(side_effect=RuntimeError("synthetic lost result")) if ambiguous else Mock(
            side_effect=[answer, dict(status="ok", items=[answer["display"]])])
        return scope, saved

    def test_order_reservation_blocks_another_workflow_id_and_unknown_outcome_has_no_retry(self):
        for ambiguous in (False, True):
            with self.subTest(ambiguous=ambiguous):
                scope, saved = self.supervisor(ambiguous)
                d = dict(commit=self.commit, authorization=self.once.TOKEN+self.commit, run_id="123",
                         run="schema4-"+self.commit+"-123", manifest=self.meta,
                         manifest_sha256=hashlib.sha256(self.manifest).hexdigest(), password="SYNTHETIC-SECRET")
                result = scope["schema4_once"](d)
                self.assertEqual(result["status"], "OUTCOME_UNKNOWN" if ambiguous else "COMPLETE")
                self.assertEqual(result["provider_requests"], None if ambiguous else 1)
                self.assertIn("started.json", saved);self.assertIn("result.json", saved)
                self.assertNotIn(d["password"], saved["result.json"].decode())
                calls = scope["child"].call_count
                d.update(run_id="124", run="schema4-"+self.commit+"-124")
                result = scope["schema4_once"](d)
                self.assertEqual(result["failure"], "ORDER_OR_RUN_ALREADY_RESERVED")
                self.assertEqual(scope["child"].call_count, calls)

    def test_packaged_starter_selection_approval_and_shared_current_planner(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/"release";root.mkdir()
            with tarfile.open(fileobj=io.BytesIO(self.archive), mode="r:") as bundle:
                for member in bundle:
                    dest = root/member.name;dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(bundle.extractfile(member).read())
            # -I discards inherited project imports/PYTHONPATH. Set both sources
            # before importing the reused fixture; production always comes first.
            program = r'''
import hashlib, json, subprocess, sys
from pathlib import Path
root, candidate = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
sys.path[0:0] = [str(root), str(candidate/"tests")]
import test_market_current as fixtures
from test_market_live_batch import manifest
current = fixtures.current
catalog = current.writer.observation.catalog_module
sources = dict(current=Path(current.__file__).resolve(), writer=Path(current.writer.__file__).resolve(),
               catalog=Path(catalog.__file__).resolve(), manifest=catalog.units.DEFAULT.resolve())
assert all(path.is_relative_to(root) for path in sources.values()), sources
relative = "docs/database/seeds/0001_market_units_v1.json"
assert sources["manifest"] == root/relative, sources
raw = sources["manifest"].read_bytes()
digest = hashlib.sha256(raw).hexdigest()
assert raw == (candidate/relative).read_bytes(), sources
assert digest == sys.argv[3] == catalog.MANIFEST_BYTES == "0d9f196e4ccbd5e687292fa3d7a1a087b343ec81fb609b8b64b6454713246bbf", (sources, digest)
catalog.normative_catalog()
f = fixtures.CurrentTests(); f.setUp(); f.previous()
source = ('require $argv[1]; $d=json_decode(stream_get_contents(STDIN),true);'
          '$r=\\Mosa2\\Schema4Once\\choose($d["entries"]);'
          'echo json_encode(["selected"=>$r["route"]["isin"],'
          '"approval"=>\\Mosa2\\Schema4Once\\approval($d["route"],$d["now"])]);')
selected = [manifest(i)["identity"]["normalized_value"] for i in (2, 1)]
entries = [dict(route=dict(isin=v, asset_class="equity", source_key="provider:boerse_frankfurt_api",
                          quote_unit_key="EUR", quote_unit_version="1")) for v in selected]
p = subprocess.run(["php", "-r", source, str(root/"scripts/collector_schema4_once.php")],
                   input=json.dumps(dict(entries=entries, route=f.route, now=f.data["now"])),
                   text=True, capture_output=True, check=True)
assert p.stderr == "", p.stderr
answer = json.loads(p.stdout)
assert answer["selected"] == min(selected), answer
assert answer["approval"]["route_sha256"] == current.route_hash(f.route), answer
f.data["approval"] = answer["approval"]
p = subprocess.run([sys.executable, "-I", "-B", str(root/"scripts/market_current/planner.py")],
                   input=json.dumps(dict(items=[f.data])), text=True, capture_output=True, check=True)
assert p.stderr == "", p.stderr
assert json.loads(p.stdout)["plans"][0]["decision"] == "UNCHANGED", p.stdout
print(json.dumps(dict(sources={k:str(v) for k,v in sources.items()}, manifest_sha256=digest, decision="UNCHANGED")))
'''
            digest = next(r["sha256"] for r in self.meta["files"]
                          if r["path"] == "docs/database/seeds/0001_market_units_v1.json")
            p = subprocess.run([sys.executable, "-I", "-B", "-c", program,
                                str(root), str(self.candidate), digest], cwd=root,
                               text=True, capture_output=True, timeout=30)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(p.stderr, "")
            evidence = json.loads(p.stdout)
            self.assertEqual(evidence["decision"], "UNCHANGED")
            self.assertEqual(evidence["manifest_sha256"], digest)
            print("Packaged Current provenance: " + json.dumps(evidence, sort_keys=True))
        starter = (ROOT/"scripts/collector_schema4_once.php").read_text()
        self.assertIn("\\Mosa2\\MarketCurrent\\run(", starter)
        self.assertNotIn("INSERT INTO", starter)
        self.assertNotIn("UPDATE m2_", starter)
        for path in ("config/collector-operation.json", "config/collector-provider-budget.json"):
            self.assertFalse(json.loads((ROOT/path).read_text())["execution_enabled"])


if __name__ == "__main__":
    unittest.main()
