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

ENDPOINT = "https://mosa2-test.scharwerk.de/api/nova_chat.php"
VERSION = "mosa2_nova_chat_v1"
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
    if not re.fullmatch(r"[0-9a-f]{64}", config["worker_token"]):
        raise ValueError("Invalid worker token")
    basic = base64.b64encode(
        (config["basic_user"] + ":" + config["basic_password"]).encode()
    ).decode()
    return {"Authorization": "Basic " + basic, "X-M2-Nova-Worker": config["worker_token"],
            "Content-Type": "application/json", "Accept": "application/json"}


def exchange(opener, headers, payload):
    request = urllib.request.Request(ENDPOINT, json.dumps(payload).encode(), headers, method="POST")
    with opener.open(request, timeout=8) as response:
        result = json.loads(response.read(24577))
    if result.get("contract_version") != VERSION:
        raise ValueError("Unexpected M2 response")
    return result


def answer(job, cli):
    prompt = (
        "Du bist NOVA im Textchat von MOSA 2. Antworte kurz in der Sprache der Frage. "
        "Du hast in diesem Chat keine Werkzeuge und kannst keine Aktionen durchführen. "
        "Die JSON-Daten enthalten Gesprächsverlauf und die aktuelle Test- oder Informationsfrage.\n"
        + json.dumps({"verlauf": job["history"], "frage": job["text"]}, ensure_ascii=False)
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", TEXT_INFERENCE, cli],
        input=prompt, text=True, encoding="utf-8", capture_output=True, timeout=75, check=True,
    )
    envelope = json.loads(result.stdout)
    if envelope.get("ok") is not True or envelope.get("transport") != "local":
        raise ValueError("Unexpected inference transport")
    text = envelope["outputs"][0]["text"].strip()
    if not text:
        raise ValueError("OpenClaw did not return text")
    return text.encode()[:2400].decode(errors="ignore")


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
