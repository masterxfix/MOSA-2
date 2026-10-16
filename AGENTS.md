# MOSA 2 – Agent Instructions

## Geltungsbereich

Diese Regeln gelten für alle Arbeiten in diesem Repository.

## Grundprinzipien

- Keine Sonderlocken. Gemeinsame, wiederverwendbare Logik und Module bevorzugen.
- Bestehende Architektur zuerst verstehen, dann ändern.
- Änderungen klein, nachvollziehbar und testbar halten.
- Keine produktiven Deployments ohne ausdrückliche Freigabe des Nutzers.
- Keine produktiven Zugangsdaten, Secrets oder Datenbankzugänge hinzufügen oder verändern, sofern dies nicht ausdrücklich beauftragt wurde.
- Keine Änderungen außerhalb dieses Repositories vornehmen.
- Keine Änderungen an `masterxfix/fixlab`.

## Arbeitsweise für Codex

1. Auftrag vollständig lesen und Akzeptanzkriterien identifizieren.
2. Nur die für den Auftrag notwendigen Dateien ändern.
3. Vorhandene gemeinsame Komponenten wiederverwenden.
4. Relevante Tests ausführen.
5. Bei bestehenden, auftragsfremden Fehlern klar unterscheiden zwischen:
   - durch den Auftrag verursacht,
   - bereits vorher vorhanden.
6. Vergangene Tool-, Browser-, Chrome-, MXC-/Launcher-, Laufwerks- oder Berechtigungsfehler niemals ungeprüft als aktuellen Blocker übernehmen. Gespeicherte Diagnosen sind nur historische Hinweise, kein aktueller Status.
7. Wenn ein Auftrag Browser-/Chrome-Zugriff benötigt oder ein früherer Browserfehler relevant erscheint, den aktuellen Chrome-Zugang zuerst neu testen. Nur ein aktuell reproduzierbarer Fehler darf als Blocker gemeldet werden.
8. Das frühere Problem mit Laufwerk `E:` darf nicht automatisch als bestehender Blocker verwendet werden. `E:` ist für MOSA-Aufträge fachlich ausgeschlossen, sofern der Auftrag keinen ausdrücklichen Bezug dazu hat.
9. Eine Sicherheits-, Freigabe- oder Zugriffssperre auf eine konkrete MOSA-Seite ist getrennt von der grundsätzlichen Chrome-Verfügbarkeit zu bewerten. Aus einer gesperrten MOSA-Seite darf nicht auf fehlenden Chrome-Zugang geschlossen werden.
10. Keine Browser-, Deployment- oder Produktionsaktionen ausführen, sofern der Auftrag dies nicht ausdrücklich verlangt.

## Token- und Kontingentverbrauch

- Token-/Kontingentverbrauch aktiv beachten und so niedrig wie sinnvoll halten.
- Nur den für Auftrag und Akzeptanzkriterien notwendigen Kontext laden und verarbeiten.
- Keine unnötigen Vollscans des Repositories, wenn gezielte Datei-/Symbolsuche ausreicht.
- Keine Wiederholungsanalysen, redundanten Zusammenfassungen oder langen Rohprotokolle erzeugen.
- Bereits bekannte und verifizierte Informationen wiederverwenden, statt sie ohne Anlass erneut vollständig zu prüfen.
- Browser-, Test- und Toolläufe nur starten, wenn sie für Umsetzung oder Nachweis erforderlich sind.
- Einen ausreichenden Prüfnachweis nicht durch zusätzliche Prüfungen nur „zur Sicherheit“ verdoppeln.
- Relevante Tests weiterhin vollständig ausführen; Tokensparen darf nicht zu schlechter Qualität, fehlender Sicherheit oder ausgelassenen Akzeptanzkriterien führen.
- Bei mehreren gleichwertigen Wegen den mit geringerem Kontext-, Tool- und Tokenaufwand bevorzugen.

## Abschlussmeldung

Am Ende kompakt melden:

- Status: erfolgreich / teilweise / fehlgeschlagen
- geänderte Dateien
- Tests und Ergebnis
- Commit oder PR, falls erstellt
- verbleibende Blocker

Keine langen Rohprotokolle, wenn sie für die Bewertung nicht nötig sind.
