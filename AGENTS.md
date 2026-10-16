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
6. Alte Tool-, Browser-, Launcher- oder Laufwerksfehler niemals automatisch als aktuellen Blocker übernehmen. Den aktuellen Zustand neu prüfen.
7. Keine Browser-, Deployment- oder Produktionsaktionen ausführen, sofern der Auftrag dies nicht ausdrücklich verlangt.

## Abschlussmeldung

Am Ende kompakt melden:

- Status: erfolgreich / teilweise / fehlgeschlagen
- geänderte Dateien
- Tests und Ergebnis
- Commit oder PR, falls erstellt
- verbleibende Blocker

Keine langen Rohprotokolle, wenn sie für die Bewertung nicht nötig sind.
