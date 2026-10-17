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

## MOSA-Auftragsstandard

- Jeder für Codex formulierte MOSA-2-Auftrag beginnt sichtbar mit **`Auftrag MOSA`**. Dieser Zusatz ist verbindlich, damit der Auftrag im KI-Kontrollzentrum eindeutig erkannt und beobachtet werden kann.
- Ein vollständig geklärter Auftrag wird in **einem zusammenhängenden Codex-Lauf** bearbeitet.
- Während der Bearbeitung keine Zwischenmeldungen an den Nutzer senden, sofern nicht zwingend eine Freigabe oder fehlende Information benötigt wird.
- Keine Rückfragen stellen, wenn der Auftrag und seine Akzeptanzkriterien ausreichend eindeutig sind.
- Keine freiwilligen Zusatzarbeiten, Verbesserungen oder Analysen außerhalb des ausdrücklich beauftragten Scopes durchführen.
- Eigene, durch den Auftrag verursachte Fehler im selben Lauf korrigieren.
- Relevante Tests nach der Umsetzung gesammelt ausführen. Falls eine eigene Korrektur nötig war, die betroffenen Tests im selben Lauf erneut ausführen.
- Wenn Repository-Änderungen erforderlich sind, am Ende **genau einen Abschluss-Commit** für den Auftrag erstellen.
- Diesen Abschluss-Commit nach `origin/main` pushen, sofern der Auftrag nicht ausdrücklich einen anderen Zielbranch oder keinen Push vorgibt.
- Nach erfolgreichem Abschluss, Tests, Commit und Push stoppen. Keine weitere ungefragte Arbeit anschließen.

## Verbindliche Werkzeug- und E:-Fehlerregel

Diese Regeln haben für alle MOSA-Aufträge Vorrang:

- Laufwerk `E:` gehört **nicht** zum MOSA-Arbeitsbereich. Es darf weder geprüft, aufgelistet, eingehängt, entsperrt noch verändert werden, sofern ein Auftrag nicht ausdrücklich `E:` betrifft.
- Ein Shell-, MXC-, Launcher-, Browser- oder Toolfehler, der durch eine interne `E:`-Initialisierung entsteht oder `E:` erwähnt, ist **kein fachlicher MOSA-Blocker**.
- Niemals den Nutzer auffordern, `E:` zu entsperren, zu ändern oder für Codex verfügbar zu machen.
- Wegen eines `E:`-bezogenen Toolfehlers einen MOSA-Auftrag nicht abbrechen, solange ein anderer geeigneter Werkzeugweg verfügbar ist.
- Für Repository-Inhalte bevorzugt den GitHub-Zugriff verwenden, wenn die lokale Shell nicht benötigt wird.
- Für Web-/Dogado-Aufträge den aktuell bereitgestellten Browser-/Chrome-Zugang verwenden. Ein lokaler Shell-Start ist für eine reine Browser-Bestandsaufnahme **nicht erforderlich**.
- Für Anhänge oder Projektdateien alternative verfügbare Datei-/GitHub-Zugriffe verwenden, bevor ein Auftrag als blockiert gilt.
- Wenn Auftragstext, GitHub-Issue oder Auftragsdokument bereits vorhanden sind, **niemals verlangen, dass der Nutzer den Auftrag erneut in den Chat einfügt**.
- Ein ausgefallener Recorder oder ein nicht lesbarer Anhang blockiert den Auftrag nicht, wenn die notwendigen Informationen bereits im Auftrag, Repository oder GitHub-Issue vorliegen.
- Ein echter Blocker darf erst gemeldet werden, wenn die für das Akzeptanzkriterium **tatsächlich erforderliche** Fähigkeit aktuell neu getestet wurde und alle sinnvollen, fachlich gleichwertigen Alternativen ohne `E:` ausgeschöpft sind.
- Falls danach wirklich eine Werkzeugfähigkeit fehlt, nur die konkret fehlende Fähigkeit benennen, zum Beispiel „aktueller Chrome-Zugriff nicht verfügbar“ oder „GitHub-Schreibzugriff fehlt“. `E:` darf nicht als Ursache oder notwendige Nutzeraktion ausgegeben werden.
- Historische Fehlerdiagnosen sind niemals ein aktueller Status. Jeder erforderliche Browser-/Toolzugang ist im aktuellen Lauf neu zu prüfen.

## Arbeitsweise für Codex

1. Auftrag vollständig lesen und Akzeptanzkriterien identifizieren.
2. Nur die für den Auftrag notwendigen Dateien ändern.
3. Vorhandene gemeinsame Komponenten wiederverwenden.
4. Relevante Tests ausführen.
5. Bei bestehenden, auftragsfremden Fehlern klar unterscheiden zwischen:
   - durch den Auftrag verursacht,
   - bereits vorher vorhanden.
6. Vergangene Tool-, Browser-, Chrome-, MXC-/Launcher-, Laufwerks- oder Berechtigungsfehler niemals ungeprüft als aktuellen Blocker übernehmen. Gespeicherte Diagnosen sind nur historische Hinweise, kein aktueller Status.
7. Wenn ein Auftrag Browser-/Chrome-Zugriff benötigt oder ein früherer Browserfehler relevant erscheint, den aktuellen Chrome-Zugang zuerst neu testen. Nur ein aktuell reproduzierbarer Fehler der tatsächlich erforderlichen Fähigkeit darf als Blocker gemeldet werden.
8. Das frühere Problem mit Laufwerk `E:` ist durch die verbindliche Werkzeug- und E:-Fehlerregel oben geregelt und darf nicht als MOSA-Blocker verwendet werden.
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
