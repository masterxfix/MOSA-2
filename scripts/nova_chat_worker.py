"""Outbound transport for MOSA 2. Runs on the existing mosa-pi host."""
import base64
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

ENDPOINT = "https://mosa2-test.scharwerk.de/api/nova-transport/worker.php"
WORKER_USER = "mosa2-nova-worker"
VERSION = "mosa2_nova_chat_v1"
MAX_REPLY_BYTES = 8000
MAX_RESPONSE_BYTES = 98304
CONFIG = Path.home() / ".config" / "mosa2-nova-chat.json"
TEXT_INFERENCE = """
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
const cli = process.argv[1];
const prompt = readFileSync(0, "utf8");
process.argv = [process.execPath, cli, "infer", "model", "run",
  "--local", "--json", "--prompt", prompt];
await import(pathToFileURL(cli).href);
"""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def credentials():
    if CONFIG.is_symlink() or CONFIG.stat().st_mode & 0o077:
        raise ValueError("Private M2 transport configuration required")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    if config["basic_user"] != WORKER_USER or not re.fullmatch(r"[0-9a-f]{64}", config["worker_token"]):
        raise ValueError("A dedicated NOVA service account and token are required")
    basic = base64.b64encode(
        (config["basic_user"] + ":" + config["basic_password"]).encode()
    ).decode()
    return {"Authorization": "Basic " + basic, "X-M2-Nova-Worker": config["worker_token"],
            "Content-Type": "application/json", "Accept": "application/json",
            "User-Agent": "MOSA2-NOVA-Transport/1.0"}


def exchange(opener, headers, payload, *, endpoint=ENDPOINT, version=VERSION):
    request = urllib.request.Request(endpoint, json.dumps(payload).encode(), headers, method="POST")
    with opener.open(request, timeout=8) as response:
        body = response.read(MAX_RESPONSE_BYTES + 1)
    if len(body) > MAX_RESPONSE_BYTES:
        raise ValueError("M2 response too large")
    result = json.loads(body)
    if result.get("contract_version") != version:
        raise ValueError("Unexpected M2 response")
    return result


def answer(job, cli):
    prompt = (
        "Du bist NOVA im Textchat von MOSA 2. Antworte in der Sprache der Nachricht und passe die Länge an die Aufgabe an. "
        "Du hast in diesem Chat keine Werkzeuge und kannst keine Aktionen durchführen. "
        "Wenn die Frage die Seiten von M2 betrifft, nutze die Hauptnavigation aus den JSON-Daten. "
        "Die übrigen JSON-Daten enthalten den Gesprächsverlauf und die aktuelle Nachricht.\n"
        + json.dumps({"m2_hauptnavigation": job.get("navigation", []),
                      "verlauf": job["history"], "nachricht": job["text"]}, ensure_ascii=False)
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", TEXT_INFERENCE, cli],
        input=prompt, text=True, encoding="utf-8", capture_output=True, timeout=75, check=True,
        # Keep the prompt in this process. A launcher restart would inherit consumed stdin.
        env={**os.environ, "NODE_DISABLE_COMPILE_CACHE": "1", "OPENCLAW_NO_RESPAWN": "1"},
    )
    envelope = json.loads(result.stdout)
    if envelope.get("ok") is not True or envelope.get("transport") != "local":
        raise ValueError("Unexpected inference transport")
    text = envelope["outputs"][0]["text"].strip()
    if not text:
        raise ValueError("OpenClaw did not return text")
    return text.encode()[:MAX_REPLY_BYTES].decode(errors="ignore")


def main():
    cli = shutil.which("openclaw")
    if not cli:
        raise SystemExit("The existing OpenClaw installation is unavailable.")
    cli = os.path.realpath(cli)
    headers = credentials()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    failed = False
    completion = None
    while True:
        try:
            if completion is not None:
                exchange(opener, headers, completion)
                completion = None
            job = exchange(opener, headers, {"action": "claim"})["job"]
            if failed:
                print("M2 transport restored", file=sys.stderr, flush=True)
                failed = False
            if job is None:
                time.sleep(3)
                continue
            try:
                reply = answer(job, cli)
                ok = True
            except (OSError, ValueError, KeyError, IndexError, TypeError, subprocess.SubprocessError):
                print("OpenClaw text request failed", file=sys.stderr, flush=True)
                reply, ok = "", False
            completion = {"action": "complete", "id": job["id"], "lease": job["lease"],
                          "ok": ok, "reply": reply}
            # Only delivery can be retried. A claimed inference is never sent again.
        except urllib.error.HTTPError as error:
            if completion is not None and error.code in (404, 409, 422):
                completion = None
            if not failed:
                print(f"M2 transport unavailable (HTTP {error.code})", file=sys.stderr, flush=True)
            failed = True
            time.sleep(5)
        except (OSError, ValueError, KeyError, TypeError):
            if not failed:
                print("M2 transport unavailable", file=sys.stderr, flush=True)
            failed = True
            time.sleep(5)


if __name__ == "__main__":
    main()
