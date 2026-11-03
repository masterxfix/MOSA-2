# MOSA 2 – Agent Instructions

**Letzte Änderung:** 03.11.2026, 18:53:32 Uhr — Europe/Berlin (MEZ, UTC+01:00).

## Geltungsbereich

Diese Regeln gelten für alle Arbeiten in diesem Repository.

## Pflege dieser Datei

- Jede Änderung an `AGENTS.md` muss im selben Commit mit Datum, Uhrzeit und kurzer Änderungsbeschreibung im Änderungsprotokoll am Dateiende dokumentiert werden. Die Kopfzeile **Letzte Änderung** ist ebenfalls zu aktualisieren.
- Den tatsächlichen Bearbeitungszeitpunkt verwenden und in der Zeitzone **Europe/Berlin** mit der zum Datum passenden UTC-Abweichung angeben. Datum oder Uhrzeit nicht schätzen.
- Bei nachträglich dokumentierten Änderungen den belegten ursprünglichen Commit-Zeitpunkt verwenden und den Nachtrag samt Commit kenntlich machen. Vorhandene Protokolleinträge bleiben erhalten.

## Grundprinzipien

- Keine Sonderlocken. Gemeinsame, wiederverwendbare Logik und Module bevorzugen.
- Bestehende Architektur zuerst verstehen, dann ändern.
- Änderungen klein, nachvollziehbar und testbar halten.
- Keine produktiven Deployments ohne ausdrückliche Freigabe des Nutzers.
- MOSA-2-Webänderungen mit bestandenem fokussiertem Test und verbindlicher Chrome-Sichtprüfung sollen ohne weitere Nutzerfreigabe über den vorgesehenen Workflow auf die MOSA-2-Testsite deployed werden. Diese Dauerfreigabe gilt ausschließlich für die MOSA-2-Testsite; Produktionsdeployments, zusätzliche Provider-/DB-Schreibvorgänge und sonstige neue externe Aktionen bleiben ausdrücklich freigabepflichtig.
- Keine produktiven Zugangsdaten, Secrets oder Datenbankzugänge hinzufügen oder verändern, sofern dies nicht ausdrücklich beauftragt wurde.
- Keine Änderungen außerhalb dieses Repositories vornehmen.
- Keine Änderungen an `masterxfix/fixlab`.

## Verbindliche MOSA-2-Oberziele

- **Relevante Daten mit nachvollziehbarer Herkunft:** MOSA 2 speichert fachlich qualifizierte Zahlen, ihre erforderlichen Herkunftsnachweise und nachvollziehbare KI-Bewertungen. Vollständige PDFs oder Webseiten werden für neue Importe nicht auf Vorrat archiviert; unnötige Rohdatenbestände vermeiden.
- **Schlanke Evidenz statt Vollantwort:** HTML nur zur Laufzeit auswerten. Pro qualifiziertem Fakt Quell-URL, tatsächliche Erfassung, Unternehmen, Berichtsperiode, Kennzahlenname, Originaleinheit/-wert, genaue Position und Prüfstatus in kompaktem strukturiertem Evidence-JSON erhalten; nur bei Bedarf einen kurzen relevanten Belegauszug ergänzen. Nicht benötigte Inhalte nach Verarbeitung verwerfen. HTTP-Quellantwort und abgeleiteten Nachweis ausdrücklich unterscheiden; der Evidence-Hash bezeichnet ausschließlich die tatsächlich gespeicherten Evidence-Bytes. Fehlt eine korrekte Provenienzabbildung, vor DB-Schreibzugriff stoppen und die kleinste notwendige Änderung benennen.
- **Bestandsschutz und KI:** Vorhandene alte Archive und historische Nachweise bleiben unverändert und werden nicht gelöscht. Bestehende allgemeine Verarbeitung und fachlich bestätigte Adapter bleiben erhalten; ein bisheriger Archivweg ist keine Freigabe für neue Vollarchive. KI-Einordnungen erst nach unabhängig bestätigten Fakten erstellen, als Interpretation kennzeichnen und von den Zahlen trennen. Automatische KI-Speicherung oder kostenpflichtige Integration braucht einen eigenen Auftrag.
- **Performance ist gleichrangig und verbindlich:** normale DB-Abfrage ideal < 20 ms, gesamte DB-Zeit einer normalen Seite < 200 ms, normaler Seitenaufruf < 1,0 s, p95 < 1,5 s, harte Obergrenze 2,0 s. Current, History und Rohdaten/Evidenz getrennt halten; Indizes mit den kritischen Queries planen.
- **Teilscope ändert nicht das Gesamtziel:** Ein kleiner beauftragter Funktionsschritt darf das langfristige Daten- oder Produktziel nicht stillschweigend enger definieren. Bewusste vorläufige Einschränkungen als offen/temporär dokumentieren und nicht als endgültigen Datenumfang behandeln.
- **MOSA-Wissen wiederverwenden:** Bereits in MOSA erprobte Datenfelder, Anbieterinformationen und funktionierende allgemeine Logik vor einer Neuentwicklung prüfen und, sofern fachlich bestätigt, in die MOSA-2-Zielarchitektur übernehmen.
- **Keine Sonderlocken:** Anbieter- und Assetfunktionen allgemein und wiederverwendbar bauen.
- **KI auf verlässlichen Daten:** KI darf interpretieren, verbinden und erklären; Fakten, Berechnungen, Herkunft und Zeitbezüge bleiben deterministisch und nachvollziehbar.
- **Produktdesign:** MOSA 2 soll klar, smart und stilvoll wirken, mit wenigen Kacheln und langfristig einem einheitlichen Stylesheet. Die bestehende Designfreigaberegel bleibt davon unberührt.

## Nutzererfahrung und praktische Teilerfolge

- Der Nutzer berichtet am 31.10.2026, dass Secure Dashboard und MOSA gleichzeitig minütlich Kurse erfolgreich abrufen. Diese Betriebserfahrung bei der Planung berücksichtigen; eine hypothetische Überlastung nicht als beobachteten Fehler darstellen.
- Kleine beauftragte Versuche durchführen, aus dem tatsächlichen Ergebnis lernen und vorhandene erfolgreiche Funktionen wiederverwenden. Der historische Fünferlauf vom 31.10.2026 (Actions-Lauf 41198494118) hat fünf damals ausgewählte Wertpapiere über Tradegate gespeichert, Current aktualisiert und sichtbar nachgewiesen; dieser Erfolg ist Grundlage, aber nicht der endgültige Marktdatenumfang.
- Neue Bedenken, die den Auftrag stoppen, seinen Umfang verändern oder einen Anbieterwechsel auslösen würden, zuerst konkret mit dem Nutzer besprechen. Keine zusätzlichen Freigabehürden allein aus ungeprüften Vermutungen einführen.
- Paket-, Syntax- und Offline-Erfolge als Vorbereitung bezeichnen. Die erfolgreiche Anzeige und ein automatischer Dauerbetrieb sind jeweils eigene, tatsächlich nachzuweisende Ergebnisse.

## Auftragsfreigabe ohne Freigabeschleifen (dauerhafte Regel)

- **Ein Auftrag, ein zusammenhängender Ablauf:** Eine eindeutig beauftragte und zulässige Arbeit soll nach Möglichkeit vollständig erledigt werden. Analyse, Implementierung, lokale Tests, ein Abschluss-Commit, der im Auftrag vorgesehene Push und beauftragte Read-only-Prüfungen werden nicht künstlich in neue Nutzerfreigaben zerlegt. Das gilt auch für zukünftige MOSA-2-Aufträge und neue Chats.
- **Freigabebedarf vorab klären und bündeln:** Bereits bei der Formulierung des Auftrags alle absehbaren Schritte und nötigen Berechtigungen benennen und den Auftrag so gestalten, dass eine erforderliche Zustimmung möglichst den gesamten konkret beschriebenen Ablauf abdeckt. Nicht routinemäßig nach Commit, dann nach Push und dann nochmals nach demselben bereits beauftragten Actions-Dispatch fragen.
- **Bereits erteilte Freigabe nicht erneut verlangen:** Ist eine konkrete Aktion mit ihrem Umfang bereits ausdrücklich autorisiert, keine zweite inhaltlich gleiche Bestätigung allein wegen eines Etappenwechsels, Toolwechsels oder technischen Fehlversuchs erfinden. Das gilt nur, solange Ziel, Umfang, Commit-/Workflowbindung und etwaige Einmalbudgets unverändert sind.
- **Technischen Weg wechseln, nicht erneut um Erlaubnis bitten:** Scheitert eine GitHub-Browsersteuerung, zuerst einen bereits verfügbaren und authentifizierten direkten GitHub-Weg (API, Connector oder CLI) nutzen, soweit er für die Aktion zugelassen ist. Bei unklarer Ausführung ausschließlich lesend feststellen, ob sie bereits erfolgte; nie blind erneut dispatchen oder einen Einmalabruf wiederholen.
- **Keine künstlichen Sicherheitsstopps:** ChatGPT und Codex führen keine zusätzlichen eigenen Einzelgenehmigungen oder manuellen Zwischenstopps für zuvor beauftragte Routinearbeiten ein. Bestehende technische Schutzprüfungen, genaue Einmalautorisationen und Berechtigungsgrenzen bleiben erhalten; eine Tool- oder Plattformbestätigung, die tatsächlich am Aktionszeitpunkt vorgeschrieben ist, darf nicht umgangen werden.
- **Keine pauschale Erlaubnis für neue risikoreiche Aktionen:** Eine Freigabe deckt keine später erfundenen Providerabrufe, zusätzlichen DB-Schreibvorgänge, unbekannten GitHub-Actions-Läufe, Ausweitung auf andere Assets oder produktiven Deployments. Solche zusätzlichen oder rechtlich/technisch gesondert bestätigungspflichtigen Aktionen erfordern ihre eigene ausdrückliche Zustimmung. Bereits erteilte konkrete Freigaben dagegen nicht grundlos wiederholen.
- **Ergebnis statt Daueraufsicht:** Codex arbeitet innerhalb des genehmigten Umfangs eigenständig bis zum Abschluss und berichtet dann kompakt. Fehlt ein zwingender Zugang oder eine wirklich neue Sicherheitsfreigabe, genau den einen konkreten Blocker nennen statt eine mehrstufige Freigabeschleife zu erzeugen.

## Verhältnismäßigkeit und kleiner Auftragsscope

- **Kleine Änderung ohne historische Nebenbaustellen:** Vor Implementierung den tatsächlich aktuellen Nutzpfad, erforderliche Dateien und Tabellen sowie den kleinsten prüfbaren Umfang bestimmen. Für die Entfernung eines Wertpapiers aus L1 oder der Testdatenbank nicht automatisch bereits abgeschlossene Einmal-Collector, Remote-/SSH-/DB-Transporte, Autorisierungs-, Secret-, Audit- oder Release-Dateien umbauen. Eine solche Änderung braucht eine nachgewiesene aktuelle fachliche Abhängigkeit; historische Nachweise bleiben unverfälscht.
- **Commit präzise abgrenzen:** Vor Commit/Push den Diff gegen `origin/main` und den Commit-Dateisatz prüfen. Fremde oder auftragsfremde lokale Änderungen nicht mit übertragen und dabei nicht verwerfen. Verbindliche Secret- und Uploadprüfungen bleiben aktiv; eine von ihnen beanstandete Datei darf nicht über einen anderen Übertragungsweg eingeschleust werden.
- **Unabhängige Ergebnisse entkoppeln:** Ist ein DB-Schreibschritt wegen einer tatsächlich fehlenden Voraussetzung nicht zulässig, beauftragte und erfolgreich geprüfte unabhängige Web-/Dokumentationsänderungen dennoch über ihren vorgesehenen Weg abschließen. Den Gesamtauftrag als teilweise offen melden, ohne durch den Web-Deploy eine DB-Aktion auszulösen.
- **Risikogerechte Test-DB-Bereinigung:** Für ausdrücklich beauftragte, eng über ISIN/Asset-ID abgegrenzte Löschungen in `h29077_mosa2_test` zunächst read-only Identität, referenzierende Zeilen, Fremdschlüssel, Löschumfang und Sicherungsbedarf prüfen. Eine auf den betroffenen Datenverbund begrenzte, überprüfbar rückspielbare Sicherung kann ausreichend sein; der unabhängig geprüfte **Vollrestore der gesamten Testdatenbank** ist nicht pauschal für jede kleine transaktionale Löschung vorgeschrieben. Vor dem endgültigen Commit sind ein belegter Rückweg, eine begrenzte Transaktion und ein unabhängiger Postcheck notwendig. Fehlt der verlässliche Rückweg, nur den DB-Schreibschritt stoppen. Historische Archivschutzregeln und Sicherheitsgrenzen bleiben gültig.
- **Keine zweite gleiche Freigabe:** Eine eindeutige Nutzeranweisung zur Entfernung eines konkret benannten Wertpapiers aus der Testdatenbank ist die fachliche Zustimmung zur genau abgegrenzten Entfernung. Nach erfolgreichem Preflight nicht erneut für denselben Umfang fragen. Neue Assets, zusätzliche Provider-/DB-Aktionen, ein neuer Secret-Zugang oder ein unbekannter Workflow sind dadurch nicht autorisiert.

## Designbestandsschutz und ausdrückliche Nutzerfreigabe

- **Verbindlich für ChatGPT und Codex:** Die bestehende visuelle Identität von MOSA 2 bleibt unangetastet, solange der Nutzer nicht die **konkret betroffene Designänderung ausdrücklich genehmigt**. Das betrifft insbesondere Farben und Farbvariablen, Schriftfamilien und Schriftschnitte, Typografie, Logo/Branding, Symbole, Dark-/Light-Theme, Akzente und die vorhandene Gestaltungsgrundlage. Eine Genehmigung für ein Layout, eine Funktion oder einen Deploy gilt **nicht** automatisch als Genehmigung dieser weiteren Bereiche.
- Offene Formulierungen wie „modernisieren“, „hochwertiger“, „einheitlich“, „Dark-Design“ oder „weiter“ erteilen **keine Freigabe zum Austausch der bestehenden Farben, Schriften oder Markenmerkmale**. Bereits bestehende Gestaltungsentscheidungen müssen vor der Umsetzung aus dem aktuellen Repository beziehungsweise aus ausdrücklich bestätigten Vorgaben ermittelt und erhalten werden.
- Vor einer beabsichtigten Abweichung die **konkreten Alt-/Neuwerten, betroffenen Dateien und sichtbaren Auswirkungen** benennen und die ausdrückliche Zustimmung des Nutzers **vor Implementierung, Commit oder Deployment** einholen. Fehlt die Zustimmung: unverändert lassen; keinen stillen visuellen Ersatz oder kreative Standardannahmen vornehmen.
- Jeder ausdrücklich auf andere Bereiche begrenzte Webauftrag muss die **nicht freigegebenen** Farb-/Schrift-/Branding-Werte nachher unverändert nachweisen. Bei einer ausdrücklich verlangten Wiederherstellung nur den letzten belegten, zuvor akzeptierten Gestaltungsstand zurücksetzen; keine weiteren Designänderungen ergänzen.
- Diese Regel ist keine allgemeine Sperre für ausdrücklich beauftragte Korrekturen, sondern eine **strikte Scope-Grenze**: Nur die konkret vom Nutzer freigegebenen Eigenschaften dürfen verändert werden. Ein technisch erfolgreicher Test oder Deployment ersetzt keine Designfreigabe.

## Vorabinformation bei notwendigen Nutzeraktionen

- Wenn ein Codex-/MOSA-Auftrag voraussichtlich eine manuelle Nutzeraktion erfordert (z. B. Passwort eingeben, Formular absenden, Freigabe bestätigen oder sichtbare Browseraktion), muss ChatGPT den Nutzer **vor Ausgabe des Auftrags** kurz und verständlich darüber informieren.
- Die Vorabinformation muss konkret sagen: **was** der Nutzer voraussichtlich tun muss, **wo** dies geschieht und **warum** es erforderlich ist. Keine überraschenden Nutzeraktionen erst während des Codex-Laufs.
- Codex soll soweit technisch möglich bis unmittelbar vor den unvermeidbaren Nutzerschritt selbst navigieren/vorbereiten und den Nutzer erst dann mit einer klaren Ein-Schritt-Anweisung auffordern.
- Der Nutzer soll nicht selbst nach Tabs, Formularen oder Einstellungen suchen müssen, wenn Codex diese Vorbereitung übernehmen kann.

## Verbindliche Passwort- und Secret-Regel

- MOSA-2-/Codex-Aufträge dürfen **keine erneute Passwortabfrage als normalen Fallback** enthalten oder während der Ausführung überraschend auslösen.
- Bevor ein Auftrag ausgegeben wird, muss ChatGPT prüfen, ob für alle voraussichtlich benötigten Zugriffe ein bereits freigegebener nicht-interaktiver Weg existiert (z. B. GitHub-Actions-Secret, bestehender sicherer Zugang oder ausdrücklich dokumentierter Secret-Pfad).
- Ist ein benötigter nicht-interaktiver Zugang noch nicht eingerichtet, wird **zuerst dieser Zugang eingerichtet**. Der eigentliche Fachauftrag wird erst danach gestartet.
- Eine einmalige Secret-Einrichtung ist nur zulässig, wenn sie technisch wirklich erforderlich ist und der Nutzer **vorher** klar erfährt, welches Secret er wo und wofür einmalig hinterlegt. Danach darf derselbe Arbeitsweg keine wiederholten Passwortfenster mehr erzeugen.
- Bereits vorhandene geeignete Secrets und Zugänge sind wiederzuverwenden. Keine zusätzlichen Benutzer, Passwortwechsel, neuen Formulare oder lokalen Eingabedialoge nur für weitere Teilprüfungen anlegen.
- Für Testsite-SFTP/SSH ist der dokumentierte GitHub-Actions-Weg mit den vorhandenen MOSA_TEST_SFTP_* Secrets/Variablen zu verwenden; lokale erneute Eingabe des web213-Passworts ist dafür nicht zulässig.
- Für schreibende Test-DB-Läufe ist ebenfalls ein nicht-interaktiver Secret-Weg Voraussetzung. Solange dieser nicht eingerichtet ist, darf kein Auftrag gestartet werden, der absehbar eine erneute Test-DB-Passworteingabe verlangen würde.
- Wenn trotz dieser Regel ein Tool während eines laufenden Auftrags unerwartet ein Passwort verlangt, den Vorgang an dieser Stelle stoppen und **nicht** den Nutzer zur Eingabe auffordern. Erst den fehlenden nicht-interaktiven Zugang sauber herstellen.

## Verbindliche Codex-Modellwahl und Kosten-Nutzen-Abwägung

- **Vor jedem neu formulierten MOSA-2-Codex-Auftrag** empfiehlt ChatGPT ausdrücklich ein konkretes **Codex-Modell und eine Denkstufe (Reasoning Effort)**. Die Empfehlung steht **außerhalb** des einzigen kopierbaren Auftragsblocks, zusammen mit der kurzen Beschreibung und dem Schwierigkeitsgrad; die gesamte Vorabinformation bleibt bei **höchstens zwei kurzen Sätzen**.
- **Optimierungsziel ist der gesamte Kosten-Nutzen-Faktor**: voraussichtliche Ergebnisqualität, Bearbeitungsdauer, Nutzungskontingent und die Kosten zusätzlicher Fehlerdiagnosen, Korrekturen und Actions-Läufe berücksichtigen. Das billigste Modell pro Einzelaufruf ist nicht automatisch die günstigste Lösung; besonders bei einmaligen Live-Schreiboperationen und schwer reproduzierbaren Fehlern zählt die Zuverlässigkeit stärker.
- **Aktuelle Evidenz nutzen:** [DeepSWE](https://deepswe.datacurve.ai/) als unabhängigen, zeitabhängigen Langzeit-Coding-Benchmark und [OpenAI-Modellauswahl](https://developers.openai.com/api/docs/guides/model-selection) sowie [Work-/Codex-Nutzungshinweise](https://help.openai.com/en/articles/20001516-managing-usage-with-gpt-6-astra-in-work-and-codex) für Modellstärken, Denkstufen und Nutzung. Eigene belegte MOSA-2-Codex-Ergebnisse und wiederkehrende Fehler fließen ebenfalls ein.
- **Benchmarkwerte richtig einordnen:** DeepSWE wird mit eigener Agentenumgebung (mini-swe-agent), Aufgabenmischung und Kostenmethodik erhoben; weder Erfolgsquoten noch Dollarwerte sind eine Garantie oder direkte Abrechnung eines Codex-Auftrags. API-Tokenpreise sind nicht mit den Nutzungskontingenten in Codex gleichzusetzen. Keine unbelegten absoluten Kostenschätzungen.
- **Leitlinie, nicht starre Modellbindung:** Für klar begrenzte einfache Änderungen ein kostengünstiges Modell mit Low/Medium; für normale Programmierung und Tests ein ausgewogenes Modell mit Medium; für komplexe Architektur, wiederholte Integrationsfehler oder risikoreiche Einmalaktionen ein leistungsstarkes Modell mit Medium/High. Extra High/Max nur empfehlen, wenn der erwartete Qualitätsgewinn den Mehraufwand plausibel rechtfertigt.
- **Verfügbarkeit beachten:** Modelle, Modellnamen, Denkstufen, Preise und Benchmarks ändern sich. Nur tatsächlich belegte und für Codex verfügbare Optionen als sicher darstellen; sonst „sofern in Codex auswählbar“ und eine vernünftige Alternative nennen. ChatGPT kann die Codex-Modellwahl nicht stillschweigend umstellen; der Nutzer wählt das empfohlene Modell in Codex.
- **Keine Abstriche an Qualität und Regeln:** AGENTS.md, Datensicherheit, fachliche Akzeptanzkriterien, Testbudgets und Freigaben bleiben unverändert verbindlich. Modellwahl allein rechtfertigt weder weitere Actions-Läufe noch ungefragte Zusatzarbeiten.

## MOSA-Auftragsstandard

- Vor jedem neuen Codex-Auftrag erhält der Nutzer eine kurze, allgemein verständliche Vorabinformation außerhalb des kopierbaren Auftragsblocks: **Was Codex jetzt baut oder prüft.**
- Dazu gehört immer eine Einschätzung **Schwierigkeitsgrad: einfach / mittel / anspruchsvoll**, mit einer knappen Begründung. Erklärung und Einschätzung zusammen auf höchstens zwei kurze Sätze begrenzen; unnötigen Fachjargon vermeiden.
- Die Vorabinformation ist nur eine Zusammenfassung; alle fachlich notwendigen Inhalte bleiben vollständig im einzigen kopierbaren Auftragsblock.
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
- **GEÄNDERT – Browserstandard:** Der Standardbrowser für Codex ist **Google Chrome**. Diese Vorgabe gilt ausschließlich für Browseraktionen; sie legt keinen Dateiübertragungs- oder Deploymentweg fest.
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

## Dogado-Testsite-Dateizugang

- Für Dateiübertragungen zur MOSA-2-Testsite ist der verbindliche Standardweg der manuelle GitHub-Actions-Workflow `.github/workflows/deploy-testsite.yml` (**Deploy MOSA 2 testsite**).
- Ziel ist ausschließlich `https://mosa2-test.scharwerk.de/`; der fest freigegebene SFTP-Webroot ist `/var/www/vhosts/web213.server10.configcenter.info/mosa2-test.scharwerk.de`.
- Technischer Zugang: SFTP zu `server10.configcenter.info:22` mit dem primären Systembenutzer `web213`; SSH-Typ `/bin/bash (chrooted)`.
- Passwort und Host-Key-Fingerprint liegen ausschließlich als GitHub-Actions-Secrets `MOSA_TEST_SFTP_PASSWORD` und `MOSA_TEST_SFTP_HOST_KEY_SHA256`; Secretwerte niemals auslesen, protokollieren, in Prompts übernehmen oder im Repository speichern.
- Host, Port, Benutzer und Zielpfad werden über die zugehörigen Repository-Variablen `MOSA_TEST_SFTP_HOST`, `MOSA_TEST_SFTP_PORT`, `MOSA_TEST_SFTP_USER` und `MOSA_TEST_SFTP_PATH` bereitgestellt und vom Testsite-Client gegen feste Sollwerte geprüft.
- `web213` kann technisch weitere Verzeichnisse sehen; diese Sichtbarkeit ist **keine Freigabe**. MOSA-2-Dateioperationen bleiben hart auf den genannten Test-Webroot begrenzt.
- Für normale Testsite-Deployments keine Plesk-Aufgabe und keine erneute Passwortabfrage verwenden, solange der GitHub-Actions-Weg verfügbar ist.
- Der Testsite-Workflow startet nur manuell per `workflow_dispatch`; kein automatischer Produktionsdeploy. Der ältere Workflow für `mosa.scharwerk.de` ist davon getrennt und darf nicht als Testsite-Ersatz verwendet werden.
- Nach bestandenem beauftragtem lokalem Testlauf und verbindlicher Chrome-Sichtprüfung ist ein MOSA-2-Testsite-Deploy Teil desselben Arbeitsablaufs und benötigt keine zusätzliche Nutzerfreigabe. Codex verwendet dabei den exakten geprüften Commit und die ausdrücklich betroffenen Webdateien; der Testsite-Deploy darf keine echten Providerabrufe oder Datenbankänderungen auslösen.
- Detailvertrag, Nachweise und aktuelle Betriebsinformationen stehen in `docs/DEPLOYMENT.md` und `docs/dogado/README.md`.

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

## Verbindliche Testökonomie, Auftragsfokus und Kostenkontrolle

Die Kosten für Codex-Aufrufe, Tokenverbrauch und Testwiederholungen trägt der Nutzer. **Ein belegbares fachliches Ergebnis bei minimal notwendigen Prüfungen hat Vorrang vor zusätzlicher Analyse, immer neuen Testkatalogen oder Ausweitung der Architektur.** Diese Regeln gelten für ChatGPT bereits bei der Auftragsformulierung und für Codex während der Ausführung.

- **Vor dem Auftrag klären:** Den vorhandenen erfolgreichen Stand, das konkrete offene Akzeptanzkriterium, bekannte Fehler aus bestehenden Logs und bereits vorhandene passende Tests identifizieren. ChatGPT definiert im Codex-Auftrag einen **minimalen Prüfplan mit festem Testbudget und Abbruchbedingungen**. Keine pauschalen Großaufträge, neuen Nebenbaustellen oder eigenen Frameworks, wenn ein geprüfter vorhandener Weg ausreicht.
- **Fehler zuerst eingrenzen:** Zuerst vorhandene Logs, Testberichte und betroffene Codepfade lesen. Ein einzelner nachweisbarer Erstfehler ist vor der Erweiterung des Testumfangs zu verstehen. Folgefehler wie mehrfach belegte Testdatenbank-Ziele nicht als unabhängige Probleme zählen; Testfälle müssen isoliert sein, ohne reale Schutzsperren zu umgehen.
- **Verbindliche Testreihenfolge:** (1) vorhandene Belege ohne erneuten Lauf auswerten, (2) nur falls wirklich nötig **ein gezielter Diagnosetest**, (3) **ein fokussierter Nachweis** der korrigierten Funktion, (4) **einmalig die tatsächlich relevanten Regressionen**, erst nachdem der fokussierte Nachweis bestanden wurde. Bereits bestandene unveränderte Prüfungen nicht ohne konkreten Anlass wiederholen. Eine Dokumentations- oder Regeländerung benötigt keine GitHub-Testpipeline, solange keine ausführbare Logik verändert wird.
- **GitHub-Actions-Limit:** Pro Codex-Auftrag grundsätzlich **höchstens drei Actions-Läufe insgesamt**: optional ein Diagnoselauf, ein gezielter Korrekturlauf und ein finaler Regressionslauf. Bereits in demselben Auftrag gestartete Läufe werden mitgezählt. **Drei sind die Obergrenze, kein Sollwert.** Kein erneutes Dispatch, keine versteckte Schleife und keine erneute Komplettsuite nach ausreichendem Beleg. Mehr Läufe nur nach **vorheriger ausdrücklicher Zustimmung des Nutzers** mit konkretem Grund und zusätzlichem Kosten-/Prüfumfang.
- **Harter Stopp statt Schleife:** Scheitert der fokussierte Korrektur-Nachweis weiter oder kann die Ursache im vorgesehenen Budget nicht belastbar bestimmt werden, **sofort stoppen**, den ersten verbleibenden Fehler und die bisherigen Laufzahlen melden und **keinen weiteren Test starten**, bis ein neuer Auftrag vorliegt. Keine automatische „noch ein Versuch“-Strategie. Ein nicht bestandenes Akzeptanzkriterium bleibt offen; keinen Teilerfolg als Gesamterfolg darstellen und keine unfertige Änderung nach `main` übernehmen.
- **Scope und Wirtschaftlichkeit:** Zusätzliche Features, neue Testfamilien, breite Sicherheitsinventare oder Architekturumbauten nur, wenn für das konkrete Ziel zwingend notwendig; sonst gesondert planen und vorher freigeben lassen. Bei gleich sicheren Wegen die vorhandene einfachere Lösung bevorzugen. Erfolg wird am funktionierenden Ergebnis samt angemessenem Nachweis gemessen, nicht an der Zahl der Dateien, Tests oder Commits.
- **Kompakter Abschluss:** Fachliches Ergebnis, exakt belegte Tests, Zahl der tatsächlich gestarteten Actions-Läufe, Commit/Status und noch offene Risiken kurz nennen. Keine langen Rohlogs und keine Wiederholung früherer Diagnosen.

## Verständliche Einordnung nach Tests

- Nach jedem Testblock gibt ChatGPT von sich aus eine kurze, verständliche Einordnung: **fachlich erfolgreich / teilweise / fehlgeschlagen**, mit dem konkret nachgewiesenen Ergebnis und seiner Bedeutung für MOSA 2.
- Die wichtigsten Messwerte den vereinbarten Zielwerten gegenüberstellen und in Alltagssprache bewerten. Eine reine Datei-, Test- oder Commitliste ersetzt diese Einordnung nicht.
- Aussagegrenzen und offene Risiken nennen: Ein begrenzter Test ist keine Freigabe für größere Datenmengen, Parallelbetrieb oder Produktivbetrieb. Fehlende Prüfungen nicht als bestanden darstellen.
- Fachliche Testergebnisse und Probleme bei Werkzeugen, Statusübertragung oder KI-Kontrollzentrum getrennt bewerten; Regelverstöße und fehlende Nachweise trotzdem ausdrücklich nennen.
- Den nächsten sinnvollen Schritt kurz benennen, ohne ihn automatisch auszuführen. Insgesamt wenige kurze Absätze, keine langen Rohprotokolle oder unnötigen Fachbegriffe.

## Abschlussmeldung

Am Ende kompakt melden:

- Status: erfolgreich / teilweise / fehlgeschlagen
- geänderte Dateien
- Tests und Ergebnis
- Commit oder PR, falls erstellt
- verbleibende Blocker

Keine langen Rohprotokolle, wenn sie für die Bewertung nicht nötig sind.

## Änderungsprotokoll

Alle Zeitangaben gelten für **Europe/Berlin**. Der Nachtrag dokumentiert die zuletzt ergänzte Regel anhand ihres ursprünglichen GitHub-Commit-Zeitpunkts.

| Datum | Uhrzeit und UTC-Abweichung | Änderung |
| --- | --- | --- |
| 03.11.2026 | 18:53:32 Uhr (MEZ, UTC+01:00) | Geringer Auftragsumfang verbindlich: historische Collector-/Sicherheitsmodule nicht unnötig verändern, unabhängige Web-/DB-Teilschritte entkoppeln, risikogerechte Testdaten-Sicherung statt pauschaler Vollrestore-Pflicht und keine erneuten Freigaben für denselben Scope. |
| 03.11.2026 | 18:06:43 Uhr (MEZ, UTC+01:00) | Nutzerentscheidung dokumentiert: PNE AG / ISIN DE000A0JBPG2 wird aus dem aktiven MOSA-2-Projekt und der MOSA-2-Testdatenbank entfernt. Historische Archive und Nachweise bleiben unverändert; `masterxfix/fixlab` bleibt unberührt. |
| 03.11.2026 | 08:33:18 Uhr (MEZ, UTC+01:00) | Nutzerentscheidung ergänzt: Erfolgreich geprüfte MOSA-2-Webänderungen werden ohne weitere Freigabe über den vorgesehenen Workflow auf die MOSA-2-Testsite deployed; Produktionsdeployments und neue externe Aktionen bleiben freigabepflichtig. |
| 02.11.2026 | 16:26:05 Uhr (MEZ, UTC+01:00) | Dauerregel gegen wiederholte Freigabeschleifen: zusammenhängende Aufträge, gebündelte Zustimmung, keine erneute Nachfrage bei schon konkret autorisierten Aktionen; GitHub-Direktwege statt Browser-Blockade, unveränderte technische Sicherheitsgrenzen. |
| 01.11.2026 | 14:09:22 Uhr (MEZ, UTC+01:00) | Neue Nutzerentscheidung zur Aufbewahrung: qualifizierte Zahlen, kompakte Herkunftsevidenz und nachvollziehbare KI-Einordnung; keine neuen Vollarchive auf Vorrat, HTTP-Antwort und Evidence getrennt, alte Archive unverändert. |
| 01.11.2026 | 12:50:41 Uhr (MEZ, UTC+01:00) | Verbindliche Codex-Modell-/Denkstufenempfehlung vor jedem MOSA-2-Auftrag eingeführt: aktuelles DeepSWE und OpenAI-Hinweise mit eigenen Ergebnissen abgleichen, Gesamtaufwand statt Einzelpreis bewerten, Verfügbarkeit und Benchmarkgrenzen offenlegen. |
| 31.10.2026 | 13:27:11 Uhr (MEZ, UTC+01:00) | Verbindliche MOSA-2-Oberziele ergänzt: Datenvollständigkeit und Performance gleichrangig, relevante kostenlose Anbieterinformationen erhalten, unbekannte Felder nicht still verwerfen, Teilscope nicht zum Endumfang machen sowie MOSA-Wissen und Produktdesign als Leitplanken festgehalten. |
| 31.10.2026 | 09:16:24 Uhr (MEZ, UTC+01:00) | Nutzeranweisung festgehalten: vorhandene Betriebserfahrung berücksichtigen, begrenzt ausprobieren und lernen, neue stoppende Bedenken zuerst besprechen und sichtbare Teilerfolge nachweisen. |
| 22.10.2026 | 14:44:52 Uhr (MESZ, UTC+02:00) | Verbindlichen Designbestandsschutz ergänzt: keine stillschweigenden Farb-, Schrift-, Branding- und Theme-Änderungen bei Layout-/Funktionsaufträgen; genaue Designänderungen erfordern vorherige ausdrückliche Nutzerfreigabe. |
| 22.10.2026 | 12:40:56 Uhr (MESZ, UTC+02:00) | Verbindliche Auftrags- und Testökonomie ergänzt: vorhandene Belege zuerst, minimaler Testplan, stufenweise Nachweise, höchstens drei GitHub-Actions-Läufe ohne erneute Freigabe sowie sofortiger Stopp statt Testschleifen. |
| 20.10.2026 | 22:45:06 Uhr (MESZ, UTC+02:00) | Globale Passwort-/Secret-Regel ergänzt: keine erneuten Passwortabfragen als Fallback; Fachaufträge erst starten, wenn der benötigte nicht-interaktive Zugang eingerichtet ist. |
| 20.10.2026 | 21:05:00 Uhr (MESZ, UTC+02:00) | Verbindlichen Dogado-/SFTP-Testsite-Zugang für Codex festgehalten: GitHub-Actions-Workflow, web213, harter Test-Webroot, Secret-/Variablennamen und klare Trennung vom älteren Produktionsziel. |
| 20.10.2026 | 19:06:31 Uhr (MESZ, UTC+02:00) | Beim Diff-Check erkannte unbeabsichtigte Wortänderung im Abschnitt „Verständliche Einordnung nach Tests“ zurückgenommen; Browserkorrektur unverändert. |
| 20.10.2026 | 19:05:09 Uhr (MESZ, UTC+02:00) | Pauschale Browserpflicht für Web-/Dogado-Aufträge ersetzt: Google Chrome ist der Standardbrowser für Codex; Browserwahl und Dateiübertragung/Deployment ausdrücklich getrennt. Stelle mit **GEÄNDERT** markiert. |
| 17.10.2026 | 20:03:45 Uhr (MESZ, UTC+02:00) | Vorabinformation für notwendige Nutzeraktionen ergänzt: ChatGPT muss vor jedem Auftrag klar ankündigen, was der Nutzer wo und warum selbst tun muss; Codex soll bis unmittelbar vor diesen Schritt selbst vorbereiten. |
| 17.10.2026 | 17:23:47 Uhr (MESZ, UTC+02:00) | Verständliche Einordnung nach jedem Testblock ergänzt: fachliches Ergebnis, Bedeutung, Messwerte gegenüber Zielwerten, Aussagegrenzen und getrennter Status von Werkzeug-/Kontrollzentrumproblemen. |
| 17.10.2026 | 15:43:26 Uhr (MESZ, UTC+02:00) | Zeitstempelpflicht, Kopfzeile und Änderungsprotokoll eingeführt; Zeitpunkt der vorherigen Regel nachgetragen. |
| 17.10.2026 | 15:40:15 Uhr (MESZ, UTC+02:00) | Nachtrag zu Commit `86b0423`: Vor jedem Codex-Auftrag kurze verständliche Erklärung und Schwierigkeitsgrad mit knapper Begründung, zusammen höchstens zwei kurze Sätze. |
