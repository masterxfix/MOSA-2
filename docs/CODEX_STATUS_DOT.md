# Codex-Statuspunkt – MOSA 2

## Zweck
In `index.html`, `marktdaten.html` und `fundamentaldaten.html` erscheint rechts im Kopfbereich ein 11-Pixel-Punkt: **Grau** = kein aktueller Auftrag, **Grün** = mindestens ein laufender Codex-Auftrag. Hover-/Screenreader-Text erläutert den Zustand. Bei fehlender, fehlerhafter oder veralteter Evidenz bleibt der Punkt unsichtbar (nicht irreführend grau).

## Herkunft und Vertragsgrenze
Bewährte MOSA-Telemetrie statt eines frei erfundenen Statussignals: `mosa_ai_control_telemetry_v1`, `surface=codex_cli|codex_vscode`, `UserPromptSubmit` (Start), `Stop` oder `SessionEnd` (Ende), dazwischen Tool-Ereignisse als Aktivitätsnachweis. `SessionStart` ist ausdrücklich **kein** Auftragsstart. Andere Oberflächen wie `work_desktop` und WinSCP zählen nicht. Parallele Codex-Aufträge werden getrennt berücksichtigt. Laufende Aufträge ohne neue native Evidenz für mehr als 180 Sekunden werden **unbekannt**, nicht inaktiv.

## Verbindung der bestehenden MOSA-Quelle
- MOSA bleibt Quelle der nativen Codex-Hooks; der bestehende MOSA-Publisher spiegelt denselben bereits erzeugten Batch optional an die fest erlaubte MOSA-2-Testsite-URL. Es werden keine neuen Hook-Ereignisse und keine parallele Auftragserfassung erzeugt.
- Die Verbindung verwendet im MOSA-Quellhost die externen Variablen `FIXLAB_MOSA2_CODEX_STATUS_URL`, `FIXLAB_MOSA2_CODEX_STATUS_TOKEN` sowie bei aktivem äußerem Testsite-Schutz `FIXLAB_MOSA2_CODEX_STATUS_BASIC_USER` und `FIXLAB_MOSA2_CODEX_STATUS_BASIC_PASSWORD`. Der URL-Wert wird gegen `https://mosa2-test.scharwerk.de/api/codex_status_ingest.php` geprüft; Token und Zugangsdaten bleiben außerhalb von Git, Logs und HTML. Der Sender überträgt den Token im Header `X-Mosa2-Codex-Token`.
- MOSA-2-Host benötigt die Umgebungsvariable `MOSA2_CODEX_STATUS_TOKEN` (zufälliger geheimer Wert ab 32 Zeichen), außerhalb von Git, Logs und HTML. Der äußere HTTP-Schutz wird nicht aufgeweicht.
- Das Hosting muss außerhalb des Webroots das Verzeichnis `mosa2-codex-status-private/` mit restriktiven Berechtigungen bereitstellen; dort wird ausschließlich `status.json` geschrieben. Keine Zugangsdaten, Auftragsinhalte, Prompts oder Originalereignisse werden im Snapshot gespeichert.
- Erst nach erfolgreichem Test der autorisierten Mirror-Zustellung zeigt der Punkt einen echten Zustand. Fehlt die Quelle, antwortet das lesende `GET /api/codex_status.php` mit `state: unavailable`. Keinesfalls statisch `idle` fälschen.
- Einziger Browserabruf: same-origin GET im Abstand von fünf Sekunden, nur bei sichtbarer Seite; Fetches laufen nicht parallel. Kein Datenbankzugriff, kein externer Fetch im Page-Load.

## Prüfung / Freigabe
Offline: `php tests/test_codex_status.php`; Frontend-Dateien und HTML-Struktur gezielt prüfen. Der native Mirror ist separat mit `tests/mosa2_codex_status_mirror_test.ps1` im MOSA-Quellrepository abgesichert. Live nach bewusst freigegebenem Testsite-Deployment: echten Codex-Start, Stop, zwei parallele Aufträge, Quellenausfall, Anmeldung und drei Seiten mit Chrome prüfen; vollständige Ladezeit jeweils unter zwei Sekunden nachweisen. Kein automatisches Deployment und keine Änderung an GitHub-Secrets oder Produktivsystemen durch diesen MOSA-2-Branch.
