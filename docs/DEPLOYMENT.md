# MOSA 2: Deployment nach mosa.scharwerk.de

## Methode und Voraussetzungen

GitHub Actions deployt den getesteten Commit von `main` per **SFTP**. Plesk zeigt
für den vorhandenen Webspace SSH-Shellzugriff als „Verboten“; rsync/scp ist damit
nicht zuverlässig nachgewiesen. SFTP benötigt keine Remote-Shell und kein
serverseitiges Git. Eine authentifizierte SFTP-Verbindung wurde noch nicht getestet.
Am 16.10.2026 waren keine GitHub Actions Secrets hinterlegt. Dieser Auftrag
bereitet ausschließlich den Deploymentweg vor und führt kein Produktivdeployment aus.

[Dogado: SFTP im Webhosting](https://help.dogado.de/hc/de/articles/28533569940113-SFTP-im-Webhosting-und-WordPress-Hosting)
beschreibt SFTP auf Port 22 mit dem **primären FTP-Benutzer**. Zusätzliche
FTP-Benutzer funktionieren laut Anbieter nicht für SFTP. Daher ist eine
serverseitige Beschränkung dieses Kontos auf MOSA 2 nicht vorausgesetzt: Der
Workflow erzwingt selbst den festen Zielpfad. Das primäre Konto hat möglicherweise
weitergehende Rechte; Workflowänderungen und Zugriff auf Repository-Secrets
müssen entsprechend geschützt werden. Vor dem ersten Einsatz SFTP-Verfügbarkeit,
Hostschlüssel und den tatsächlichen Pfad im SFTP-Namensraum verifizieren.
Hierfür keine Plesk-Einstellungen oder Passwörter beiläufig ändern.

## GitHub Actions Secrets

Unter **Settings → Secrets and variables → Actions → New repository secret**
im Repository `masterxfix/MOSA-2` hinterlegen. Keine Werte in Dateien schreiben.

| Secret | Bedeutung |
| --- | --- |
| `MOSA_DEPLOY_HOST` | Verifizierter SFTP-Server; zugelassen sind `server10.configcenter.info` und `mosa.scharwerk.de`. |
| `MOSA_DEPLOY_PORT` | SFTP-Port aus den Hosting-Verbindungsdaten, üblicherweise 22. |
| `MOSA_DEPLOY_USER` | Primärer FTP-Benutzer laut oneHome. |
| `MOSA_DEPLOY_PASSWORD` | Passwort dieses Benutzers. |
| `MOSA_DEPLOY_PATH` | Exakter Document Root im SFTP-Namensraum, siehe unten. |
| `MOSA_DEPLOY_HOST_KEY_SHA256` | Über einen vertrauenswürdigen Weg bestätigter Server-Hostschlüssel-Fingerprint im Format `SHA256:…` (43 Base64-Zeichen ohne `=`). |

Den Hostschlüssel mit Dogado beziehungsweise einem bereits unabhängig
verifizierten SSH-Hostschlüssel abgleichen. Ein ungeprüftes `ssh-keyscan` allein
beweist die Serveridentität nicht. Es gibt keine automatische Schlüsselannahme.
Die Verbindung prüft den Fingerprint vor der Passwortauthentifizierung.
Fehlt auch nur ein Secret oder ist der Pfad ungültig, scheitert der Job **vor
der ersten Netzwerkverbindung**. Es erfolgt dann kein Teildeployment.

## Zielpfad und Dateiumfang

Plesk-Document-Root: `mosa.scharwerk.de`, relativ zum Webspace.
Zulässige Secret-Werte sind ausschließlich:

- `mosa.scharwerk.de` (relativ zum SFTP-Startverzeichnis)
- `/mosa.scharwerk.de` (bei entsprechendem SFTP-Chroot)
- `/var/www/vhosts/web213.server10.configcenter.info/mosa.scharwerk.de`

Der serverseitig aufgelöste Pfad muss einer der beiden absoluten Varianten
entsprechen. `/`, `.`, `httpdocs`, fremde Domains und abweichende Pfade werden
abgelehnt. Der Document Root muss bereits existieren. Bei einem anderen
SFTP-Namensraum zuerst die Zuordnung prüfen und den Pfadschutz gezielt reviewen,
keinen allgemeineren Zielpfad erlauben.

Das Skript überträgt **alle versionierten Webdateien einschließlich Unterordnern**,
z.B. HTML, PHP, CSS und Bilder. Ausgenommen sind Entwicklungsverzeichnisse
`.github`, `docs`, `scripts`, `tests`, `node_modules` sowie Git-/Agent-Metadaten.
`.htaccess`, `.user.ini` und `.well-known` sind erlaubt; `.env*`, Schlüsseldateien,
andere versteckte Dateien, Symlinks und Submodule führen zum Abbruch.
Neue Buildschritte müssen ihre Laufzeitdateien später ausdrücklich bereitstellen;
`node_modules` und unversionierte Buildprodukte werden nicht automatisch hochgeladen.

## Ablauf und Sicherheitsgrenzen

Client und transitive Python-Abhängigkeiten sind in
`scripts/requirements-deploy.txt` versionsfest festgelegt; die Checkout-Action
ist auf einen vollständigen Commit-SHA gepinnt.

Workflow: `.github/workflows/deploy.yml`, auf Push nach `main` und zusätzlich
`workflow_dispatch`. Manuelle Läufe anderer Branches validieren nur; der
Deployjob ist auf `masterxfix/MOSA-2` und `main` beschränkt. Checkout und Tests
beziehen sich auf denselben Commit. Parallel laufende Deployments werden serialisiert.

`validate` führt Offline-Sicherheitstests, die Prüfung der lesbaren `index.html`
auf sichtbaren Text „MOSA“ und `git diff --check` aus. PHP-Lint, MOSA-Tests und
Playwright vor Deployment können hier ergänzt werden. Die aktuelle HTML-Prüfung
erkennt Metadaten, Kommentare und einfache Versteckattribute; sie ersetzt keinen Browsertest.
`deploy` startet nur nach erfolgreicher Validierung, prüft sämtliche Secrets und
den Zielpfad und lädt ausschließlich die Webdateien hoch. Bestehende Zielpfade
werden vor Schreibbeginn auf Symlinks und unpassende Dateitypen geprüft.

Kein Remote-Shellbefehl, kein `--delete`, keine Löschung alter Dateien, keine
Datenbank-, DNS-, Plesk- oder fixlab-Änderung. Uploads werden per SHA-256
zurückgelesen und dateiweise atomar ersetzt (OpenSSH `posix-rename` erforderlich).
Ein Transportfehler bricht sichtbar ab. Das gesamte Projekt wird nicht als eine
Transaktion ausgetauscht: Bei einem Fehler nach Schreibbeginn können bereits
übertragene Dateien aktualisiert sein; temporäre `.mosa-upload-*`-Dateien können
zurückbleiben. Nach Behebung einen vollständigen Lauf starten. Der Client setzt
ein unverändert vertrauenswürdiges Hostingkonto voraus; parallele manuelle
Änderungen am Ziel während eines Deployments vermeiden.

## Manuell starten und Fehler prüfen

Erst nach Hinterlegung und Verifikation der Secrets:
**Actions → Deploy MOSA 2 → Run workflow → Branch main → Run workflow**.
Ein Push auf `main` löst denselben Weg aus. Jeder erfolgreiche Lauf zeigt im
Job-Summary den tatsächlich übertragenen Commit; dies ist noch kein HTTP-/Browsernachweis.

Bei Fehlern unter **Actions → Lauf → fehlgeschlagener Job → roter Schritt** die
Meldung prüfen. Fehlende Secret-Namen werden genannt, Werte nicht ausgegeben.
Bei Verbindungsfehlern zunächst Host, Port, Hostschlüssel, primären Benutzer und
SFTP-Pfad prüfen. Niemals Hostschlüsselprüfung oder Pfadschutz deaktivieren.
Der erste Lauf ohne Secrets soll bei `Check all secrets before connecting, then deploy`
verständlich fehlschlagen und keine Verbindung aufbauen.

Für spätere Live-Abnahme einen separaten Job `verify-live` mit `needs: deploy`
ergänzen: HTTPS-Aufruf von `https://mosa.scharwerk.de`, HTTP 200, Playwright-
Sichtprüfung, Screenshot und Upload als GitHub-Artefakt. Dieser Job benötigt
keine Deployment-Secrets und ist hier bewusst noch nicht aktiviert.

Lokale Tests ohne Secrets oder Netzwerk:

```text
python -m unittest discover -s tests -v
python scripts/deploy_sftp.py validate
git diff --check
```
