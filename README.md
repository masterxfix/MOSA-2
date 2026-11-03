# MOSA 2

MOSA 2 ist der eigenständige Entwicklungsstand für die nächste Generation des MOSA-Dashboards.

## Aktueller Stand und nächster Abschlussabschnitt

**31.10.2026:** [Tradegate-Kursmodul](docs/database/TRADEGATE_CURRENT_PILOT.md) erfolgreich bis zur sichtbaren Fünferabnahme geführt. Der Lauf [41198494118](https://github.com/masterxfix/MOSA-2/actions/runs/41198494118) auf Commit `87ed391d67f315a9a884556ab1363e7cd3809dcb` endete mit **COMPLETE**: fünf damals ausgewählte Wertpapiere wurden über `Tradegate · XGAT · Mid` gespeichert, Current aktualisiert und im Browser sichtbar geprüft. Observation-, Current-, Web- und Release-Readbacks bestanden; 5/5 Provideranfragen wurden genau einmal verbraucht. Der automatische Dauerbetrieb bleibt deaktiviert. Nächste fachliche Priorität ist die vollständige Übernahme der kostenlos verfügbaren relevanten Marktdaten ohne Verlust bekannter oder später nutzbarer Anbieterinformationen, bei unverändertem Performance-Budget.

**Historische Übergabe 22.10.2026:** [Damals bestätigter Projektstand und Abschlussfahrplan](docs/MOSA2_UEBERGABE_ABSCHLUSSFAHRPLAN_2026-10-22.md).

## Zielbild

MOSA 2 soll langfristig eine **persönliche, finanzorientierte KI-Plattform** werden.

Der wichtigste fachliche Schwerpunkt bleibt:
- Depot und Vermögensentwicklung,
- laufende Finanzen, Cashflows, Ausgaben und Risiken,
- verständliche persönliche Einordnung durch KI.

Weitere Lebensbereiche wie Netzwerk, Smart Home, Mediathek, Dokumente oder später z.B. Immobilien werden modular ergänzt. Sie sollen MOSA 2 ein vollständigeres persönliches Bild geben, ohne den Finanzfokus zu verdrängen.

Die bevorzugte Bedienung soll langfristig über die KI erfolgen: Der Nutzer stellt MOSA 2 Fragen und erhält persönliche, quellenbasierte Antworten aus den eigenen strukturierten Daten.

Die KI darf interpretieren, Zusammenhänge erkennen, erklären und Empfehlungen geben. **Fakten, Berechnungen und finanzielle Werte müssen jedoch deterministisch und nachvollziehbar aus der Datenbasis stammen.**

Autonomie wird später schrittweise und kontrolliert erweitert. Mehr Freiheiten werden nur innerhalb klarer Berechtigungen und mit vollständigem Aktionsprotokoll vergeben.

## Verbindliche Leitziele

- **Datenvollständigkeit:** MOSA 2 soll möglichst alle kostenlos verfügbaren, relevanten Informationen aus den tatsächlich genutzten Quellen erfassen und dauerhaft erhalten. Eine Information darf nicht allein deshalb verworfen werden, weil sie heute noch nicht angezeigt oder ausgewertet wird.
- **Rohdaten und Fachwerte:** Bekannte fachliche Werte werden strukturiert gespeichert. Noch nicht modellierte, aber relevante Anbieterinformationen bleiben mit Quelle und Zeitbezug in einer Rohdaten-/Evidenzschicht erhalten, damit sie später ohne erneuten historischen Abruf erschlossen werden können.
- **Geschwindigkeit:** Vollständigkeit darf nicht zu langsamen Seiten führen. Die verbindlichen Performance-Budgets stehen in `docs/database/README.md`; Current, History und Rohdaten bleiben deshalb getrennte Lese- und Speicherschichten.
- **Nachvollziehbarkeit und Historie:** Werte bleiben mit Asset, Quelle, Marktzeit, Erfassungszeit und Herkunft rückverfolgbar. MOSA 2 baut eine langfristig nutzbare eigene Datenhistorie auf.
- **Gemeinsame Module statt Sonderlocken:** Anbieter-, Asset-, Termin-, Logo-, Transaktions- und Analysefunktionen werden allgemein und wiederverwendbar gebaut.
- **KI auf verlässlichen Daten:** Die KI interpretiert, verbindet und erklärt gespeicherte Daten; Fakten und Berechnungen bleiben deterministisch und prüfbar.
- **Produktdesign:** MOSA 2 soll klar, smart und stilvoll wirken, mit wenigen Kacheln und langfristig einem einheitlichen Stylesheet. Konkrete Designänderungen bleiben an die Freigaberegeln in `AGENTS.md` gebunden.

## Arbeitsmodell

- Dieses Repository ist die verbindliche Arbeitsbasis für MOSA 2.
- Der Default-Branch `main` ist der MOSA-2-Arbeitsstand.
- Anforderungen werden zuerst im normalen Chat geklärt.
- Codex wird erst nach fachlicher und technischer Klärung für die Umsetzung eingesetzt.
- Ergebnisse von Codex werden anschließend über GitHub geprüft.
- Keine produktiven Deployments ohne ausdrückliche Freigabe.
- Keine Sonderlösungen, wenn eine gemeinsame wiederverwendbare Logik möglich ist.
- **MOSA bleibt bestehen und nutzbar.** Es dient weiterhin als Spielwiese/Labor für neue Ideen und Funktionen.
- **Nur ausgereifte und bestätigte Funktionen werden nach MOSA 2 übernommen.**
- **Prio 1 für die Datenbank ist eine saubere, nachvollziehbare Migration wertvoller MOSA-Daten nach MOSA 2.**
- **Sicherheit ist ein Architekturgrundsatz.** Der normale Zugang zu MOSA 2 wird auf FIDO2/WebAuthn aufgebaut; Recovery und Fernzugriff werden bewusst separat und ohne schwachen Passwort-Fallback geplant.

## Ziel

Ein stabiler, nachvollziehbarer und testbarer Entwicklungsworkflow zwischen Nutzer, ChatGPT, GitHub und Codex. MOSA 2 entsteht parallel zu MOSA als saubere Zielarchitektur und nicht als kurzfristiger Ersatz.

## Datenbank

Die geplante MOSA-2-Datenbankarchitektur, Ziele und Grundregeln werden unter [`docs/database/README.md`](docs/database/README.md) geführt.

## Sicherheit

Die Leitlinien für Zugang, FIDO2/WebAuthn, Fernzugriff, Recovery und spätere Sicherheitsfreigaben werden unter [`docs/security/README.md`](docs/security/README.md) geführt.
