# Codex-Statuspunkt – MOSA 2

## Zweck
In `index.html`, `marktdaten.html` und `fundamentaldaten.html` sitzt ein 11-Pixel-Punkt mittig in der Kopfzeile. **Grün** steht für mindestens einen laufenden MOSA-2-Auftrag, **Grau** für keinen aktiven Auftrag und ein **heller Ring mit zwei Pixeln Strichstärke** für unbekannten Status. Tooltip und Screenreader-Text benennen alle drei Zustände. Starte einen Auftrag mit `Auftrag-M2: <Anweisung>` oder mit `Auftrag-M2` auf einer eigenen ersten Zeile. Eine normale Nachricht eröffnet keinen Auftrag.

## MOSA als maßgebliche Drei-Zustände-Quelle

Die bestehende MOSA-Aktivitätsauswertung entscheidet für native Codex-Aufträge (CLI und VS Code) über genau drei Zustände: `running`, `idle`, `unavailable`. Der native MOSA-Sender überträgt den berechneten Wert als `mosa_source_presence` über die bestehende authentifizierte MOSA-2-Spiegelung. MOSA 2 speichert den Zustand und die Zeitmarken im bestehenden privaten Speicher. Ein älterer, erneut zugestellter Wert überschreibt keinen neueren. Fehlende oder länger als 180 Sekunden alte MOSA-Evidenz ergibt `unavailable`. Dasselbe gilt, wenn eine neuere Ereigniszeit der letzten MOSA-Meldung widerspricht. Gespeicherte Altdateien bleiben lesbar. Aus einzelnen Ereignissen berechnet M2 keinen Zustand.

Der vorhandene MOSA-Empfänger liefert auf Anforderung des Publishers (`m2-orders`) nur die Präsenz ausdrücklich markierter M2-Aufträge zurück. M2 übernimmt diese Präsenz über den Vertrag `mosa2_mosa_order_presence_v1`. Vorher gespeicherte oder erneut zugestellte unbeschränkte Zustände können den Punkt nicht aktivieren.

## Herkunft und Vertragsgrenze
Bewährte MOSA-Telemetrie statt eines frei erfundenen Statussignals: `mosa_ai_control_telemetry_v1`, `surface=codex_cli|codex_vscode`, `UserPromptSubmit` (Start), `Stop` oder `SessionEnd` (Ende), dazwischen Tool-Ereignisse als Aktivitätsnachweis. `SessionStart` ist ausdrücklich **kein** Auftragsstart. Andere Oberflächen wie `work_desktop` und WinSCP zählen nicht. Parallele Codex-Aufträge werden getrennt berücksichtigt. Laufende Aufträge ohne neue native Evidenz für mehr als 180 Sekunden werden **unbekannt**, nicht inaktiv.

## Verbindung der bestehenden MOSA-Quelle

Die Hook-Konfiguration des MOSA-Checkouts gilt nur in dessen Projekt. Für einen Start aus der Codex-App im separaten lokalen MOSA-2-Projekt muss dort `.codex/hooks.json` dieselben Ereignisse auf den vorhandenen `scripts/mosa_ai_activity_hook.ps1` im MOSA-Checkout verweisen. Verwende den absoluten lokalen Skriptpfad und die bestehende Senderkonfiguration. Codex verlangt die Vertrauensprüfung der Hook-Einträge am neuen Projektpfad. Sie erfolgt in der App über „Hooks prüfen“ oder „Einstellungen → Hooks“. Ohne diese Registrierung und Freigabe erhält MOSA aus dem Projekt keine Ereignisse. Ein CLI-Test im MOSA-Checkout prüft den Empfänger, aber ersetzt die App-Abnahme im MOSA-2-Projekt nicht.

- MOSA bleibt Quelle der nativen Codex-Hooks; der bestehende MOSA-Publisher spiegelt denselben bereits erzeugten Batch optional an die fest erlaubte MOSA-2-Testsite-URL. Es werden keine neuen Hook-Ereignisse und keine parallele Auftragserfassung erzeugt.
- Die Verbindung verwendet im MOSA-Quellhost die externen Variablen `FIXLAB_MOSA2_CODEX_STATUS_URL`, `FIXLAB_MOSA2_CODEX_STATUS_TOKEN` sowie bei aktivem äußerem Testsite-Schutz `FIXLAB_MOSA2_CODEX_STATUS_BASIC_USER` und `FIXLAB_MOSA2_CODEX_STATUS_BASIC_PASSWORD`. Der URL-Wert wird gegen `https://mosa2-test.scharwerk.de/api/codex_status_ingest.php` geprüft; Token und Zugangsdaten bleiben außerhalb von Git, Logs und HTML. Der Sender überträgt den Token im Header `X-Mosa2-Codex-Token`.
- MOSA-2 benötigt **entweder** die bisherige Umgebungsvariable `MOSA2_CODEX_STATUS_TOKEN` **oder** (wenn PHP-FPM/Plesk keine Umgebungsvariablen bereitstellt) die Datei `mosa2-codex-status-private/token.txt` im bereits vorgesehenen privaten Verzeichnis **außerhalb des Webroots**. Diese Datei enthält ausschließlich 64 hexadezimale Zeichen aus einem kryptografisch zufällig erzeugten 32-Byte-Token und darf nur für den Eigentümer lesbar sein (`0600`); der PHP-Reader lehnt Symlinks, zu offene Berechtigungen und ungültige Werte ab. Ein vorhandener gültiger Umgebungstoken hat Vorrang. Derselbe Token wird ausschließlich im nativen MOSA-Sender als `FIXLAB_MOSA2_CODEX_STATUS_TOKEN` hinterlegt. Token niemals in Git, Browser, Logs, Chat, URLs oder Webroots ablegen; der äußere HTTP-Schutz bleibt aktiv.
- Das Hosting muss außerhalb des Webroots das Verzeichnis `mosa2-codex-status-private/` mit restriktiven Berechtigungen bereitstellen; die beschreibbare `status.json` wird beim ersten autorisierten Statusereignis automatisch erstellt, nicht manuell vorbefüllt. Der private Token liegt getrennt davon in `token.txt`. Keine Zugangsdaten, Auftragsinhalte, Prompts oder Originalereignisse werden in `status.json` gespeichert.
- Erst nach erfolgreichem Test der autorisierten Mirror-Zustellung zeigt der Punkt einen echten Zustand. Fehlt die Quelle, antwortet das lesende `GET /api/codex_status.php` mit `state: unavailable`. Keinesfalls statisch `idle` fälschen.
- Einziger Browserabruf: same-origin GET im Abstand von fünf Sekunden, nur bei sichtbarer Seite; Fetches laufen nicht parallel. Kein Datenbankzugriff, kein externer Fetch im Page-Load.

## Prüfung / Freigabe
Offline: `php tests/test_codex_status.php`; Frontend-Dateien und HTML-Struktur gezielt prüfen. Der native Mirror ist separat mit `tests/mosa2_codex_status_mirror_test.ps1` im MOSA-Quellrepository abgesichert. Live nach bewusst freigegebenem Testsite-Deployment: echten Codex-Start, Stop, zwei parallele Aufträge, Quellenausfall, Anmeldung und drei Seiten mit Chrome prüfen; vollständige Ladezeit jeweils unter zwei Sekunden nachweisen. Kein automatisches Deployment und keine Änderung an GitHub-Secrets oder Produktivsystemen durch diesen MOSA-2-Branch.

## Robustheit des optionalen MOSA-2-Mirrors (Review 08.11.2026)
Der separate MOSA-Quellbranch `codex/mosa2-status-mirror-20261108` wurde um zwei Schutzregeln erweitert:

- **Best effort auch bei lokalen Speicherfehlern:** Sowohl das Schreiben der Pending-/Overflow-Dateien als auch die spätere Mirror-Zustellung sind gegen die reguläre MOSA-Übertragung abgegrenzt. Ein lokaler Fehler wird als `local_store_error` vermerkt, darf aber den bestehenden MOSA-POST/ACK/FIFO-Compact nicht verhindern. Eine fehlgeschlagene lokale Mirror-Ablage kann nicht garantiert nachgeliefert werden und wird ausdrücklich nicht als erfolgreich bestätigt.
- **Begrenzte Lebensdauer der Mirror-Queue:** Der MOSA-2-Receiver akzeptiert Ereignisse höchstens 24 Stunden nach ihrer nativen UTC-Zeit. Der Sender entfernt nach 23 Stunden 55 Minuten abgelaufene Einträge aus Pending und Overflow, um eine dauerhaft blockierte FIFO-Nachlieferung zu vermeiden. Abgelaufene Ereignisse werden **nicht** als neue Aufträge, künstliche Stopps oder erfundene Statusmeldungen rekonstruiert. Nach 180 Sekunden ohne frische MOSA-Evidenz erscheint der neutrale Ring.

Gezielte zusätzliche Regressionen: `tests/mosa2_codex_status_resilience_test.ps1` im fixlab-Branch für simulierten Queue-I/O-Fehler, >24h abgelaufene Einträge, Recovery und Unabhängigkeit der primären MOSA-FIFO. Ausführung im nativen PowerShell-Umfeld und Chrome-Live-Abnahme bleiben nachzuweisen; allein die Commit-Ablage ist kein bestandener Test.

## Dogado/Plesk ohne PHP-FPM-Umgebungsvariablen

Für die Testseite ist **kein SSH-/PHP-FPM-Variablenzugang nötig**, wenn die bestehende Plesk-Dateiverwaltung den bereits angelegten privaten Ordner außerhalb des Document Root beschreiben und die Dateirechte auf `0600` setzen kann. Codex prüft im vorhandenen Plesk-/Dateizugang die exakte Zuordnung des Verzeichnisses zu `dirname(__DIR__, 2).'/mosa2-codex-status-private/'` (PHP-Quelldatei unter `api/`), nutzt nur diese Testdomain und ändert keine fremden Websites.

1. Im vorhandenen autorisierten lokalen MOSA-Kontext kryptografisch zufällige 32 Bytes erzeugen und als genau 64 Hex-Zeichen verwenden. Das Geheimnis **nicht** im Repository, Aktionenprotokoll oder Chat speichern.
2. Das Geheimnis in Plesk im privaten, nicht webbasiert erreichbaren `token.txt` ablegen; Berechtigungen `0600` kontrollieren. Kein neues `.htaccess` nötig: Vertraulichkeit beruht auf der Lage *außerhalb* des Webroots und den Dateirechten.
3. Dieselben Zeichen im bestehenden nativen MOSA-Adapter als `FIXLAB_MOSA2_CODEX_STATUS_TOKEN` sowie die feste URL und ggf. vorhandene Basic-Zugangsdaten im autorisierten lokalen Geheimnisspeicher konfigurieren. Bereits aktive MOSA-Telemetrie nicht verändern.
4. Nur die beiden aktualisierten API-Dateien `api/codex_status_model.php` und `api/codex_status_ingest.php` über den vorhandenen **Testsite**-Deployment-Workflow ausrollen; sonst nichts. Danach echte native Codex-Start-/Stop-, Parallel- und Fehlerfälle prüfen. `status.json` erstellt die Anwendung beim ersten akzeptierten Ereignis selbst.
5. Wenn das Plesk-Konto die private Datei oder restriktive Rechte tatsächlich nicht schreiben kann, ist **genau diese** Berechtigung die verbliebene externe Sperre; keine Ausweichlösung innerhalb des öffentlichen Webroots und kein Abschalten der Authentifizierung.

## HTTP-Fehler bei der Zustellung unterscheiden

- nginx-HTML mit HTTP 401 entsteht vor PHP. Prüfe den vorhandenen Basic-Zugang im tatsächlich ausgeführten Hook-Prozess.
- HTTP 401 mit dem JSON-Vertrag `mosa2_codex_status_v1` kommt vom PHP-Empfänger. Prüfe die Tokenbereitstellung im Sender und die private Serverkonfiguration, ohne Werte auszugeben.
- Am 10.11.2026 erreichte der vorhandene Basic-Zugang PHP. Dort lieferte die Testdomain-Sperre aus dem Reset (Issue #61) HTTP 403. Die gezielte Freigabe betrifft ausschließlich den tokengeprüften Status-POST. Der äußere Basic-Schutz bleibt aktiv.
