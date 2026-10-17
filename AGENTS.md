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

- Jeder für Codex formulierte MOSA-2-Auftrag beginnt als erste eigenständige, unzitierte Zeile exakt mit **`MOSA-Auftrag`**. Nur diese Markersyntax wird vom KI-Kontrollzentrum erkannt.
- Der Marker darf im tatsächlichen Codex-Prompt nicht in einem Zitat, Markdown-Codeblock oder Fließtext stehen.
- Formulierungen wie `Auftrag MOSA`, `Auftrag für MOSA` oder eine bloße Inline-Erwähnung starten keine Anzeige im KI-Kontrollzentrum.
- Jeder Codex-Auftrag wird dem Nutzer als **genau ein vollständiger, direkt kopierbarer `text`-Codeblock** ausgegeben. Der Nutzer muss nur einmal auf „Kopieren“ klicken und den Inhalt einmal als native Textnachricht in Codex einfügen.
- Die erste Inhaltszeile dieses kopierbaren Blocks lautet exakt `MOSA-Auftrag`; nach dem Kopieren stehen keine Markdown-Zäune im Codex-Prompt.
- Kein fachlich notwendiger Teil des Auftrags darf außerhalb dieses einen kopierbaren Blocks stehen.
- Einen Auftrag niemals auf mehrere Codeblöcke, Anhänge oder aufeinanderfolgende Nachrichten verteilen.
- Keine verschachtelten Markdown-Codeblöcke im Auftrag verwenden; Beispiele und Befehle innerhalb des Auftrags als normalen eingerückten Text darstellen.
- Codex-Aufträge standardmäßig **nicht als Datei oder Anhang** übergeben. Ein Anhang ist nur zulässig, wenn der Nutzer ihn ausdrücklich verlangt und der Auftragstext trotzdem im nativen Prompt eindeutig verfügbar bleibt.
- Der Auftrag muss vollständig in sich geschlossen sein und darf nicht auf „den Text oben“, einen nicht lesbaren Anhang oder eine frühere Chatnachricht als einzige Quelle verweisen.
- Ein vollständig geklärter Auftrag wird in **einem zusammenhängenden Codex-Lauf** bearbeitet.
- Während der Bearbeitung keine Zwischenmeldungen an den Nutzer senden, sofern nicht zwingend eine Freigabe oder fehlende Information benötigt wird.
- Keine Rückfragen stellen, wenn der Auftrag und seine Akzeptanzkriterien ausreichend eindeutig sind.
- Keine freiwilligen Zusatzarbeiten, Verbesserungen oder Analysen außerhalb des ausdrücklich beauftragten Scopes durchführen.
- Eigene, durch den Auftrag verursachte Fehler im selben Lauf korrigieren.
- Relevante Tests nach der Umsetzung gesammelt ausführen. Falls eine eigene Korrektur nötig war, die betroffenen Tests im selben Lauf erneut ausführen.
- Wenn Repository-Änderungen erforderlich sind, am Ende **genau einen Abschluss-Commit** für den Auftrag erstellen.
- Diesen Abschluss-Commit nach `origin/main` pushen, sofern der Auftrag nicht ausdrücklich einen anderen Zielbranch oder keinen Push vorgibt.
- Nach erfolgreichem Abschluss, Tests, Commit und Push stoppen. Keine weitere ungefragte Arbeit anschließen.

## Streng vertrauliche Daten- und Laufwerksgrenze

Diese Grenze ist verbindlich und hat Vorrang vor Komfort, Toolwahl oder Automatisierung:

- Laufwerk `E:` ist **streng vertraulich** und vollständig außerhalb des MOSA-/Codex-Arbeitsbereichs.
- Für MOSA-Aufträge ist jeder Zugriff auf `E:` verboten: kein Lesen, Öffnen, Auflisten, Scannen, Indexieren, Traversieren, Mounten, Entsperren, Schreiben oder Verändern.
- Auch ein **rein technisches Enumerieren oder Initialisieren** von `E:` durch einen Launcher, eine Shell, einen Browser-Wrapper, einen Recorder oder ein anderes Werkzeug ist für MOSA nicht zulässig.
- Ein Tool, das für seinen Start oder seine Berechtigungsinitialisierung `E:` berührt oder voraussetzt, darf für MOSA-Aufträge **nicht verwendet** werden.
- Niemals versuchen, den Zustand, Inhalt, freien Speicher, Verschlüsselungsstatus oder sonstige Eigenschaften von `E:` zu ermitteln.
- Niemals den Nutzer auffordern, `E:` zu entsperren, bereitzustellen, freizugeben oder zu verändern.
- Informationen von `E:` dürfen weder in Prompts, Logs, Diagnosen, Commits, Issues noch in Abschlussmeldungen übernommen werden.
- Ein interner Tool- oder Launcherfehler im Zusammenhang mit `E:` ist ausschließlich ein **Werkzeugproblem** und niemals ein fachlicher MOSA-Blocker.
- Falls die einzige verfügbare Werkzeugroute diese Vertraulichkeitsgrenze nicht sicher einhalten kann, diese Werkzeugroute nicht verwenden. Stattdessen eine fachlich gleichwertige, E:-freie Route nutzen oder exakt die fehlende sichere Werkzeugfähigkeit melden.
- Diese Regel gilt unabhängig davon, ob ein Tool `E:` absichtlich, automatisch oder als Teil einer generischen Laufwerksinventarisierung berühren würde.

## Verbindliche Browser- und Werkzeugregel

- Für Repository-Inhalte bevorzugt den GitHub-Zugriff verwenden, wenn keine lokale Shell erforderlich ist.
- Für Web-/Dogado-Aufträge den vom Nutzer bereitgestellten verbundenen Browser-/Chrome-Zugang verwenden.
- Bei bereitgestelltem Chrome-Zugang zuerst an die **bestehende verbundene Browser-Sitzung** anbinden und deren offene Tabs inventarisieren.
- Nicht zuerst versuchen, einen neuen lokalen Chrome-Prozess über Shell, CUA-, Node-, MXC- oder ähnliche Launcher zu starten.
- Lokale Browser-/Computer-Use-Launcher, die bei ihrer Initialisierung Laufwerke enumerieren oder `E:` berühren könnten, sind für MOSA unzulässig.
- Das Scheitern eines lokalen Browser-Launchers beweist **nicht**, dass der bereitgestellte Chrome-Zugang fehlt.
- Ein Browser-Auftrag darf erst mit „verbundene Browser-Sitzung nicht verfügbar“ blockiert werden, wenn genau diese vorhandene Sitzung aktuell geprüft und nicht erreichbar ist.
- Ist die Browser-Sitzung erreichbar, aber der benötigte Dogado-Tab bzw. die Anmeldung fehlt, ist exakt das zu melden: „Dogado-Tab/Anmeldung nicht vorhanden“.
- Für Anhänge oder Projektdateien alternative verfügbare Datei-/GitHub-Zugriffe verwenden, bevor ein Auftrag als blockiert gilt.
- Wenn Auftragstext, GitHub-Issue oder Auftragsdokument bereits vorhanden sind, niemals verlangen, dass der Nutzer den Auftrag erneut in den Chat einfügt.
- Ein ausgefallener Recorder oder ein nicht lesbarer Anhang blockiert den Auftrag nicht, wenn die notwendigen Informationen bereits im Auftrag, Repository oder GitHub-Issue vorliegen.
- Wenn die account-spezifische Browserprüfung das zentrale Akzeptanzkriterium eines Auftrags ist, darf ein reiner Dokumentations-/Webrecherche-Ersatz nicht als teilweise Erfüllung dieses Kernziels gewertet und nicht als Abschluss behandelt werden.
- Historische Fehlerdiagnosen sind niemals ein aktueller Status. Jeder tatsächlich benötigte Zugang ist im aktuellen Lauf neu und über einen zulässigen, E:-freien Werkzeugweg zu prüfen.

## Arbeitsweise für Codex

1. Auftrag vollständig lesen und Akzeptanzkriterien identifizieren.
2. Nur die für den Auftrag notwendigen Dateien ändern.
3. Vorhandene gemeinsame Komponenten wiederverwenden.
4. Relevante Tests ausführen.
5. Bei bestehenden, auftragsfremden Fehlern klar unterscheiden zwischen:
   - durch den Auftrag verursacht,
   - bereits vorher vorhanden.
6. Vergangene Tool-, Browser-, Chrome-, MXC-/Launcher-, Laufwerks- oder Berechtigungsfehler niemals ungeprüft als aktuellen Blocker übernehmen.
7. Für Browser-Aufträge ausschließlich einen zulässigen, E:-freien Zugriffspfad verwenden.
8. Laufwerk `E:` darf unter keinen Umständen als notwendige Voraussetzung, Ursache einer Nutzeraktion oder MOSA-Arbeitsbereich behandelt werden.
9. Eine Sicherheits-, Freigabe- oder Zugriffssperre auf eine konkrete MOSA-Seite ist getrennt von der grundsätzlichen Browser-Verfügbarkeit zu bewerten.
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
