# MOSA 2

MOSA 2 ist der eigenständige Entwicklungsstand für die nächste Generation des MOSA-Dashboards.

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
