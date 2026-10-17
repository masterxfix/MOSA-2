# MOSA 2 – Phase 0: Dogado-Plattformqualifikation

**Status:** geplant  
**Ziel:** Die tatsächlichen technischen Möglichkeiten des vorhandenen Dogado-Webhostings werden geprüft, bevor das MOSA-2-Datenbankschema verbindlich festgelegt wird.

## Auftrag an Codex

Nutze den vom Nutzer bereitgestellten, bereits angemeldeten Chrome-Zugang zu Dogado für eine **reine Bestandsaufnahme**. Öffentliche Dogado-Dokumentation darf ergänzend verwendet werden, aber account-spezifische Aussagen müssen nach Möglichkeit im tatsächlichen Kundenkonto geprüft werden.

### Sicherheitsgrenzen

- keine Datenbank anlegen oder löschen;
- keine bestehenden Datenbanken, Benutzer oder Berechtigungen verändern;
- keine Passwörter, Secrets oder Zugangsdaten anzeigen, kopieren oder dokumentieren;
- keine PHP-, Domain-, DNS-, Backup-, SFTP-/SSH- oder Hosting-Einstellungen verändern;
- keine produktiven MOSA-/MOSA-2-Dateien deployen;
- keine Lasttests oder großen Datenbanktests durchführen;
- bei einer Aktion, die eine Änderung auslösen würde, vor dem Ausführen stoppen.

## Zu prüfen

### Datenbank
- welche MySQL-/MariaDB-Versionen beim Erstellen einer neuen Datenbank tatsächlich auswählbar sind;
- Host/Port-Modell der verfügbaren Versionen;
- Anzahl möglicher Datenbanken und erkennbare Quoten/Limits;
- Datenbankbenutzer und Rechteverwaltung;
- lokaler, externer oder IP-beschränkter Zugriff;
- phpMyAdmin und erkennbare Verwaltungsfunktionen;
- erkennbare Limits zu Speicher, Connections, Import/Export oder Laufzeiten;
- Backup-/Restore-Möglichkeiten für Datenbanken.

### Webhosting / Laufzeit
- verfügbare PHP-Versionen und relevante Laufzeitoptionen;
- Cronjobs/Scheduler bzw. geplante Tasks;
- SFTP/SSH-Möglichkeiten und erkennbare Einschränkungen;
- Dateispeicher/Quota und sinnvolle Ablage für spätere große Dateien;
- vorhandene Backup-/Restore-Möglichkeiten des Webspaces;
- weitere Funktionen, die für MOSA 2 langfristig sinnvoll sein könnten.

### MOSA-2-Eignung
Bewerte anschließend kurz:
- welche DB-Version für MOSA 2 bevorzugt getestet werden sollte;
- welche Dogado-Funktionen wir sinnvoll nutzen können;
- welche wichtigen Limits noch unbekannt sind und durch eigene Tests bestimmt werden müssen;
- welche Risiken oder Abhängigkeiten für Performance, Backup, Migration oder Betrieb bestehen.

## Ergebnis

Die belastbaren Ergebnisse werden in **dieser Datei** dokumentiert. Dabei klar unterscheiden:

- **im Dogado-Konto bestätigt**;
- **nur durch offizielle Dokumentation bestätigt**;
- **noch offen / später zu testen**.

Keine Vermutungen als bestätigte Tatsachen darstellen.

Nach Abschluss soll dieses Dokument eine kurze Empfehlung für die nächste Phase enthalten: Welche technische Kombination aus DB-Version, PHP-Version und Dogado-Funktionen soll in einem isolierten MOSA-2-Testaufbau praktisch benchmarked werden?

## Danach

Erst nach dieser Bestandsaufnahme folgt eine ausdrücklich freizugebende Testphase mit eigener MOSA-2-Testdatenbank, synthetischen Daten, EXPLAIN-/Index-Tests, Backup/Restore und realistischen Performance-Benchmarks.
