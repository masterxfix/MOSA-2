# Codex-Statuspunkt – MOSA 2

## Zweck
In `index.html`, `marktdaten.html` und `fundamentaldaten.html` erscheint rechts im Kopfbereich ein 11-Pixel-Punkt: **Grau** = kein aktueller Auftrag, **Grün** = mindestens ein laufender Codex-Auftrag. Hover-/Screenreader-Text erläutert den Zustand. Bei fehlender, fehlerhafter oder veralteter Evidenz bleibt der Punkt unsichtbar (nicht irreführend grau).

## Herkunft und Vertragsgrenze
Bewährte MOSA-Telemetrie statt eines frei erfundenen Statussignals: `mosa_ai_control_telemetry_v1`, `surface=codex_cli|codex_vscode`, `UserPromptSubmit` (Start), `Stop` oder `SessionEnd` (Ende), dazwischen Tool-Ereignisse als Aktivitätsnachweis. `SessionStart` ist ausdrücklich **kein** Auftragsstart. Andere Oberflächen wie `work_desktop` und WinSCP zählen nicht. Parallele Codex-Aufträge werden getrennt berücksichtigt. Laufende Aufträge ohne neue native Evidenz für mehr als 180 Sekunden werden **unbekannt**, nicht inaktiv.

## Verbindung der bestehenden MOSA-Quelle
- MOSA bleibt unverändert und Quelle der nativen Codex-Hooks.
- Die vorhandene vertrauenswürdige MOSA-Senderoutine muss die **ohnehin vorhandenen** Telemetrie-Batches zusätzlich an `POST /api/codex_status_ingest.php` von MOSA 2 spiegeln, ohne neue oder künstliche Hook-Ereignisse zu erzeugen. Noch **nicht verbunden**; diese Verkabelung muss in der nativen Umgebung nachgewiesen werden.
- MOSA-2-Host benötigt die Umgebungsvariable `MOSA2_CODEX_STATUS_TOKEN` (zufälliger geheimer Wert ab 32 Zeichen), außerhalb von Git, Logs und HTML. Der Sender überträgt ihn im Header `X-Mosa2-Codex-Token`. Für die bestehende vollständig passwortgeschützte Testsite benötigt der Sender zusätzlich den bereits autorisierten HTTP-Zugang; den äußeren Schutz **nicht** aufweichen.
- Das Hosting muss außerhalb des Webroots das Verzeichnis `mosa2-codex-status-private/` mit restriktiven Berechtigungen bereitstellen; dort wird ausschließlich `status.json` geschrieben. Keine Zugangsdaten, Auftragsinhalte, Prompts oder Originalereignisse werden im Snapshot gespeichert.
- Erst nach erfolgreichem Test der autorisierten Mirror-Zustellung zeigt der Punkt einen echten Zustand. Fehlt die Quelle, antwortet das lesende `GET /api/codex_status.php` mit `state: unavailable`. Keinesfalls statisch `idle` fälschen.
- Einziger Browserabruf: same-origin GET im Abstand von fünf Sekunden, nur bei sichtbarer Seite; Fetches laufen nicht parallel. Kein Datenbankzugriff, kein externer Fetch im Page-Load.

## Prüfung / Freigabe
Offline: `php tests/test_codex_status.php`; Frontend-Dateien und HTML-Struktur gezielt prüfen. Live nach bewusst freigegebenem Testsite-Deployment: echten Codex-Start, Stop, zwei parallele Aufträge, Quellenausfall, Anmeldung und drei Seiten mit Chrome prüfen; vollständige Ladezeit jeweils unter zwei Sekunden nachweisen. Kein automatisches Deployment oder Änderungen an MOSA, GitHub-Secrets, Hooks oder Produktivsystemen durch diesen Branch.
