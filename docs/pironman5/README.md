# Pironman 5 / MOSA-2 — NOVA-Version und Freigaben

Stand: 2026-10-18

## Projekt

- GitHub-Repository: `masterxfix/MOSA-2`
- Branch: `main`
- Relevante Bereiche:
  - `docs/pironman5/README.md`
  - `docs/database/`
- Der Repository-Bezug zu MOSA-2 und Pironman 5 ist bestätigt.
- Die physische Zuordnung des lokalen Hosts zum konkreten Pironman-5-Gehäuse muss vor Ort geprüft werden.

## NOVA-Laufzeit

- Hostname: `mosa-pi`
- Hardware: Raspberry Pi 5 Model B Rev 1.1
- Betriebssystem: Linux `6.18.50+rpt-rpi-2712` aarch64
- Benutzer: `frank`, UID 1000
- Node.js: `v24.22.0`
- OpenClaw: `2026.9.9 (bcfc888)`
- Aktuelles Modell: `openai/gpt-5.6-luna`
- Agent: `main`

## Bestätigte Freigaben

- Lokaler Zugriff als Benutzer `frank`
- Lesen und Schreiben in berechtigten Benutzerpfaden, einschließlich Workspace und User-Diensten
- Keine bestätigten Root-/System-Administratorrechte
- Kein separater MOSA-2-Laufzeit-Node verbunden

## MOSA

- Zugriff über den lokalen MOSA-Helper
- Ausschließlich lesend
- Keine Trades, Aktualisierungen, Trigger, Statusänderungen oder Remote-Konfigurationsänderungen
- Keine MOSA-Zugangsdaten in dieser Dokumentation speichern
- Der Zugriff war zum Prüfzeitpunkt verfügbar und technisch gesund; die Berechtigung ist bei Bedarf erneut zu prüfen.

## GitHub

- Der Benutzer kann das Repository im Browser sehen.
- NOVA selbst hatte zum Prüfzeitpunkt kein verbundenes GitHub-Konto/Credential.
- Daher aktuell kein bestätigter GitHub-Lese- oder Schreibzugriff für NOVA.
- Der sichtbare Browserzugriff des Benutzers ist nicht automatisch eine NOVA-Freigabe.

## openHAB

- Normale, eindeutig adressierte reversible Aktionen dürfen nach der zentralen Policy ohne zusätzliche Einzelbestätigung ausgeführt und verifiziert werden.
- Kritische Aktionen sowie Regel-, Konfigurations- und Strukturänderungen bleiben ausdrücklich freigabepflichtig.

## Prüfstatus

Direkt verifiziert wurden Repository, Branch, Pfadstruktur sowie der aktuelle OpenClaw-/NOVA-Stand aus der laufenden OpenClaw-Sitzung und der dortigen `MEMORY.md`. Die physische Zuordnung zum Pironman-5-Gehäuse ist weiterhin nicht separat verifiziert.
