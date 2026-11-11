# Codex-Textchat auf der M2-Testseite

Der gemeinsame Header öffnet einen eigenen Chat. Browser-Authentifizierung, Cookie, CSRF-Token und Chatablage sind von NOVA getrennt. Die Oberfläche zeigt die Erreichbarkeit des Transportdienstes. Das Codex-Statussymbol bezieht seine Anzeige weiterhin aus der bestehenden Telemetrie.

Der ausgehende Windows-Worker verwendet den vorhandenen, mit ChatGPT angemeldeten Codex-Client über `codex exec --ephemeral --json`. Jede Anfrage startet einen separaten Textlauf mit einem begrenzten Verlauf aus M2 und dem veröffentlichten Projektüberblick. Der Worker verwendet keine bestehende Codex-Unterhaltung und hat keine lokalen Werkzeuge. Der verifizierte Client ist per SHA-256 festgelegt. Bei einem Clientwechsel bleibt der Dienst aus, bis Werkzeugkatalog und echter Textlauf für die neue Version erneut geprüft wurden. Die Testseite und die veröffentlichte Übersicht liefern keine nicht veröffentlichten Projektinformationen.

Plesk beschränkt den Dienstbenutzer `mosa2-codex-worker` auf `/api/codex-transport`. Der PHP-Endpunkt prüft zusätzlich den SHA-256-Verifier des Diensttokens. Windows speichert die Dienstgeheimnisse verschlüsselt mit DPAPI im privaten Benutzerverzeichnis. Die geplante Aufgabe `MOSA2-Codex-Text-Transport` läuft mit Benutzerrechten und startet bei der Anmeldung. Es gibt keinen eingehenden Listener.

Der Worker verarbeitet jede Lease höchstens einmal. Bei einem Transportfehler kann er ausschließlich die Zustellung eines bereits erstellten Ergebnisses wiederholen. Hält ein Ausfall bis zum Ende der Lease an, zeigt der Browser einen Fehler. Das Gespräch läuft nach Wiederherstellung mit einer neuen Nachricht weiter.

Zum Abschalten die geplante Aufgabe stoppen oder deaktivieren. Zum Widerrufen das Dienstkonto am einzelnen Plesk-Pfad entfernen. NOVA und die persönliche Codex-Anmeldung benötigen dazu keine Änderungen.
