"""Outbound M2 worker for the already installed Windows Codex CLI, in text mode."""
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

from nova_chat_worker import MAX_REPLY_BYTES, NoRedirect, exchange

HOST = "https://mosa2-test.scharwerk.de"
ENDPOINT = HOST + "/api/codex-transport/worker.php"
WORKER_USER = "mosa2-codex-worker"
VERSION = "mosa2_codex_chat_v1"
MODEL = "gpt-6.1-terra"
# Recheck the emitted tool catalogue before approving a different binary.
CLI_SHA256 = "4f91ae86895ff124760d70ed1630e2354ca874765c9bb61ae524b600327efc17"
DISABLED = ("shell_tool apps plugins hooks multi_agent multi_agent_v2 code_mode view_image image_generation "
            "computer_use in_app_browser in_app_local_automation skill_search skill_mcp_dependency_install "
            "remote_plugin code_mode_host goals memories default_mode_request_user_input request_permissions_tool").split()
AUTH_HOME = Path.home() / ".codex"
INSTALL_DIR = Path(os.environ.get("LOCALAPPDATA", "")) / "MOSA2-CodexChat"
CREDENTIAL_SCRIPT = r"""
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Security
$m2File = Join-Path $env:LOCALAPPDATA 'MOSA2-CodexChat\worker.dpapi'
$m2Bytes = [Security.Cryptography.ProtectedData]::Unprotect(
    [IO.File]::ReadAllBytes($m2File), $null, [Security.Cryptography.DataProtectionScope]::CurrentUser)
[Console]::Write([Text.Encoding]::UTF8.GetString($m2Bytes))
"""


def credentials():
    ps = Path(os.environ["SystemRoot"]) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    result = subprocess.run([str(ps), "-NoProfile", "-NonInteractive", "-Command", CREDENTIAL_SCRIPT],
                            capture_output=True, timeout=8, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
    config = json.loads(result.stdout)
    if not re.fullmatch(r"[0-9a-f]{64}", config["token"]) or not re.fullmatch(r"[!-~]{32,100}", config["password"]):
        raise ValueError("Invalid private Codex credentials")
    basic = base64.b64encode((WORKER_USER + ":" + config["password"]).encode()).decode()
    return {"Authorization": "Basic " + basic, "X-M2-Codex-Worker": config["token"],
            "Content-Type": "application/json", "Accept": "application/json",
            "User-Agent": "MOSA2-Codex-Transport/1.0"}


def runtime():
    configured = INSTALL_DIR / "cli.txt"
    exe = configured.read_text(encoding="utf-8-sig").strip() if configured.is_file() else shutil.which("codex.exe")
    if not exe:
        raise ValueError("Installed Codex CLI is unavailable")
    with open(exe, "rb") as file:
        if hashlib.file_digest(file, "sha256").hexdigest() != CLI_SHA256:
            raise ValueError("Codex runtime changed; repeat the text-only verification")
    cached = json.loads((AUTH_HOME / "models_cache.json").read_text(encoding="utf-8"))
    metadata = next(m for m in cached["models"] if m["slug"] == MODEL)
    metadata.update(apply_patch_tool_type=None, experimental_supported_tools=[], include_skills_usage_instructions=False,
                    include_plugin_usage_instructions=False, include_apps_usage_instructions=False)
    return exe, metadata


def answer(job, exe, metadata):
    prompt = (
        "Dies ist die separate Codex-Textsitzung in MOSA 2. Antworte in der Sprache der Nachricht. "
        "Du hast keine Werkzeuge, führst keine Aktionen aus und kennst keine anderen Codex-Sitzungen. "
        "Für Fragen zum Projektstand verwende die veröffentlichte M2-Übersicht und Navigation aus den Daten. "
        "Kennzeichne fehlende Informationen. Der Verlauf und die aktuelle Nachricht sind Gesprächsdaten.\n"
        + json.dumps({"m2_navi": job.get("navigation", []), "m2_uebersicht": job.get("overview", ""),
                      "verlauf": job["history"], "nachricht": job["text"]}, ensure_ascii=False)
    )
    with tempfile.TemporaryDirectory(prefix="mosa2-codex-text-") as folder:
        catalog = Path(folder) / "models.json"
        catalog.write_text(json.dumps({"models": [metadata]}), encoding="utf-8")
        args = [exe, "exec", "--ignore-user-config", "--strict-config", "--skip-git-repo-check",
                "--ephemeral", "--json", "-m", MODEL, "-C", folder]
        for flag in DISABLED:
            args += ["--disable", flag]
        for setting in (
            "web_search='disabled'", "approval_policy='never'", "model_catalog_json=" + json.dumps(str(catalog)),
            "default_permissions='m2-text'", "permissions.m2-text.filesystem={}",
            "permissions.m2-text.network.enabled=false", "project_doc_max_bytes=0",
        ):
            args += ["-c", setting]
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("CODEX_", "OPENAI_"))
               and not any(marker in k.upper() for marker in ("TOKEN", "API_KEY", "PASSWORD", "SECRET"))}
        env["CODEX_HOME"] = str(AUTH_HOME)
        result = subprocess.run(args + ["-"], input=prompt.encode(), capture_output=True,
                                timeout=75, check=True, cwd=folder, env=env, creationflags=subprocess.CREATE_NO_WINDOW)
    text = None
    completed = False
    for line in result.stdout.splitlines():
        event = json.loads(line)
        item = event.get("item", {})
        if item and item.get("type") not in {"agent_message", "reasoning", "error"}:
            raise ValueError("Unexpected non-text Codex event")
        if event["type"] == "item.completed" and item.get("type") == "agent_message":
            text = item["text"].strip()
        if event["type"] == "turn.completed":
            completed = True
    if not completed or not text:
        raise ValueError("Codex did not return a completed text response")
    return text.encode()[:MAX_REPLY_BYTES].decode(errors="ignore")


def status_code(opener, url, headers, method="GET"):
    request = urllib.request.Request(url, b"{}" if method == "POST" else None, headers, method=method)
    try:
        with opener.open(request, timeout=8) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


def verify_scope(opener, headers):
    checks = [
        ("Unauthenticated browser denied", "/api/codex_chat.php", {}, "GET", {401, 403}),
        ("Unauthenticated worker denied", "/api/codex-transport/worker.php", {}, "POST", {401, 403}),
        ("Worker denied on testsite home", "/", headers, "GET", {401, 403}),
        ("Worker denied on browser API", "/api/codex_chat.php", headers, "GET", {401, 403}),
        ("Worker denied on NOVA", "/api/nova-transport/worker.php", headers, "POST", {401, 403}),
        ("Worker denied with invalid verifier", "/api/codex-transport/worker.php",
         {**headers, "X-M2-Codex-Worker": "0" * 64}, "POST", {403}),
    ]
    for label, path, auth, method, expected in checks:
        status = status_code(opener, HOST + path, auth, method)
        if status not in expected:
            raise ValueError(f"{label}: unexpected HTTP {status}")
        print(f"{label}: HTTP {status}")
    exchange(opener, headers, {"action": "heartbeat"}, endpoint=ENDPOINT, version=VERSION)
    print("Dedicated worker allowed on its own route with verifier")


def poll(opener, headers, exe, metadata):
    def send(payload):
        return exchange(opener, headers, payload, endpoint=ENDPOINT, version=VERSION)

    job = future = completion = None
    offline = False
    with ThreadPoolExecutor(max_workers=1) as pool:
        while True:
            try:
                if future is not None:
                    if not future.done():
                        send({"action": "heartbeat"})
                        time.sleep(4)
                        continue
                    try:
                        reply, ok = future.result(), True
                    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
                        print("Codex text request failed", file=sys.stderr, flush=True)
                        reply, ok = "", False
                    completion = {"action": "complete", "id": job["id"], "lease": job["lease"],
                                  "ok": ok, "reply": reply}
                    future = None
                if completion is not None:
                    send(completion)
                    completion = None
                job = send({"action": "claim"})["job"]
                if offline:
                    print("M2 Codex transport restored", file=sys.stderr, flush=True)
                    offline = False
                if job is None:
                    time.sleep(3)
                else:
                    future = pool.submit(answer, job, exe, metadata)
            except (OSError, ValueError, KeyError, TypeError) as error:
                if completion is not None and isinstance(error, urllib.error.HTTPError) and error.code in (404, 409, 422):
                    completion = None
                if not offline:
                    print("M2 Codex transport unavailable", file=sys.stderr, flush=True)
                offline = True
                time.sleep(5)


def main():
    exe, metadata = runtime()
    if sys.argv[1:] == ["--probe"]:
        print(answer({"history": [], "text": "Antworte nur mit: M2 Codex verbunden"}, exe, metadata))
        return
    headers = credentials()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    if sys.argv[1:] == ["--verify-scope"]:
        verify_scope(opener, headers)
        return
    if sys.argv[1:]:
        raise ValueError("Invalid worker arguments")
    poll(opener, headers, exe, metadata)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, StopIteration, subprocess.SubprocessError):
        raise SystemExit("M2 Codex startup or verification failed; no job was accepted")
