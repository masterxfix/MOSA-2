# MOSA 2 – Sicherheit & Zugang

Sicherheit ist ein Grundbestandteil von MOSA 2 und wird von Anfang an mitgeplant.

## Dokumentierter Sicherheitsvorfall

Der mögliche Privacy-/Security-Boundary-Fehler vom 17.10.2026 ist hier vollständig dokumentiert:

- [`INCIDENT_2026-10-17_CODEX_DRIVE_E.md`](INCIDENT_2026-10-17_CODEX_DRIVE_E.md)

Dort stehen bestätigte Beobachtungen, ausdrücklich nicht bewiesene Punkte, Chronologie, offene Fragen an OpenAI sowie der vorbereitete englische Bericht.

## Grundsatz

Der normale Zugang zu MOSA 2 soll **nur über FIDO2 / WebAuthn** möglich sein. Die bereits getestete FIDO-Karte ist dabei der primäre Zugangsschlüssel.

Ein klassischer Passwort-Login ist **nicht als normaler Fallback** vorgesehen.

## Verbindlicher Ausbauplan der MOSA-2-Authentifizierung

Die Sicherheitsarchitektur wird bewusst stufenweise aufgebaut. Die Zwischenstufen sind keine Änderung des Zielbilds, sondern ermöglichen eine kontrollierte Entwicklung und Abnahme, bevor echte MOSA-Daten verwendet werden.

### Stufe 1 – vorgeschalteter Passwortschutz der Testumgebung

- `mosa2-test.scharwerk.de` wird als erste äußere Schutzschicht vollständig serverseitig mit einer Passwortabfrage geschützt.
- Der Schutz gilt für den gesamten Document Root einschließlich direkter Asset- und Unterseitenzugriffe.
- Zugangsdaten werden nicht im Repository, in Issues, Logs oder im Seitenquelltext gespeichert.
- Diese Stufe ist ein Entwicklungs- und Übergangsschutz und **nicht** das endgültige MOSA-2-Login.
- Solange keine spätere Stufe ausdrücklich freigegeben und verifiziert wurde, bleibt der vorhandene Schutz aktiv.

### Stufe 2 – MOSA-Loginprinzip in MOSA 2 übernehmen

- Das in MOSA bereits erprobte Login-/Session-Prinzip wird für MOSA 2 übernommen und sauber in die neue Architektur integriert.
- Die bestehende Funktionsweise dient als Referenz; es wird keine parallele Sonderlösung erfunden.
- Secrets, Altlasten oder produktive Zugangsdaten werden nicht kopiert.
- Die konkrete technische Umsetzung wird vor der Übernahme gegen die MOSA-2-Architektur und Sicherheitsregeln geprüft.
- Der serverseitige Schutz aus Stufe 1 wird nicht stillschweigend entfernt; eine Änderung der äußeren Schutzschicht benötigt eine eigene Entscheidung und Prüfung.

### Stufe 3 – FIDO-Karte als starker physischer Faktor

- Die in MOSA bereits erfolgreich getestete FIDO-Funktion wird als primärer starker Authentifizierungsfaktor in MOSA 2 integriert.
- Ziel bleibt FIDO2 / WebAuthn als normaler Zugangsschlüssel; ein klassisches Passwort wird nicht zum normalen Fallback der endgültigen Anmeldung.
- Registrierung, Backup-Authenticator, Verlustfall und Step-up-Freigaben werden vor produktiver Nutzung verbindlich abgesichert.

### Stufe 4 – physischen Kartenstatus unterscheiden

MOSA 2 soll nicht nur erkennen, **dass** die FIDO-Karte vorhanden ist, sondern auch den physischen Präsentationszustand unterscheiden:

- **Karte aufgelegt** – kontaktlose Nutzung am Leser;
- **Karte steckt im Kartenleser** – gesteckte/kontaktbehaftete Nutzung.

Diese beiden Zustände müssen technisch eindeutig erfasst und in MOSA 2 getrennt dargestellt werden. Ob daraus später unterschiedliche Berechtigungs- oder Freigabestufen entstehen, wird ausdrücklich als eigene Sicherheitsregel festgelegt und nicht implizit angenommen.

### Endziel

Der Endausbau besteht damit aus mehreren klar getrennten Ebenen:

```text
äußerer Zugangsschutz
       ↓
MOSA-2 Login / Session
       ↓
FIDO2 / WebAuthn mit physischem Authenticator
       ↓
Erkennung: Karte aufgelegt oder gesteckt
       ↓
Berechtigungen / Step-up für kritische Aktionen
```

Die Stufen werden einzeln umgesetzt, geprüft und dokumentiert. Keine spätere Stufe darf eine bereits wirksame Schutzebene unbeabsichtigt schwächen.

## Vertraulichkeitsgrenze für lokale Daten

Lokale private Daten, die nicht ausdrücklich Bestandteil eines MOSA-Auftrags sind, gehören nicht in den Arbeitsbereich von MOSA oder Codex.

Für Laufwerk `E:` gilt ausdrücklich:

- `E:` ist **streng vertraulich** und fachlich nicht Teil von MOSA.
- MOSA/Codex darf `E:` weder lesen, auflisten, scannen, indexieren, initialisieren, entsperren noch verändern.
- Auch automatische Laufwerksinventarisierung durch Tools oder Launcher ist für MOSA nicht akzeptabel, wenn dabei `E:` berührt wird.
- Werkzeuge, die diese Grenze technisch nicht einhalten können, werden für MOSA nicht verwendet.
- Inhalte oder Metadaten von `E:` dürfen nicht in Logs, Diagnosen oder Projektdokumentation gelangen.
- Ein `E:`-bezogener interner Werkzeugfehler darf niemals zu einer Aufforderung führen, das Laufwerk zu entsperren oder zugänglich zu machen.

Diese Grenze ist unabhängig von der späteren MOSA-2-Zugangsarchitektur und gilt bereits für Entwicklung und Codex-Aufträge.

## Zielbild

```text
Netz / Fernzugriff
       ↓
äußerer Zugangsschutz
       ↓
FIDO2 / WebAuthn
       ↓
MOSA-2 Session
       ↓
Berechtigungen
       ↓
kritische Aktionen ggf. erneut bestätigen
```

Damit werden drei Dinge getrennt:

1. Wer darf MOSA 2 überhaupt erreichen?
2. Wer meldet sich tatsächlich an?
3. Welche Aktionen darf diese Identität ausführen?

## FIDO-Zugang

- Primäre FIDO-Karte für den normalen Zugang.
- Mindestens ein zweiter physischer FIDO-Authenticator als Backup.
- Backup-Authenticators werden getrennt von der Hauptkarte aufbewahrt.
- Neue FIDO-Authenticators dürfen nur nach starker erneuter Bestätigung registriert werden.
- Verlust oder Defekt einer Karte darf nicht zu einem schwächeren Passwort-Login führen.

## Unterwegs / Fernzugriff

Auch unterwegs soll der sichere FIDO-Zugang erhalten bleiben.

Der Fernzugriff wird deshalb später als eigener Sicherheitsbaustein geplant, z.B. über VPN, privaten Tunnel oder einen vorgeschalteten Access-Gateway. MOSA 2 soll möglichst nicht einfach ungeschützt direkt im Internet stehen.

Ziel bleibt:

> Auch unterwegs erfolgt die eigentliche Anmeldung weiterhin mit FIDO.

## Notfall / Recovery

Der endgültige Recovery-Weg ist noch offen und wird separat geplant.

Wichtige Leitlinien:

- Recovery darf nicht schwächer sein als der normale Sicherheitsstandard.
- Kein dauerhaft nutzbares Notfall-Passwort.
- Ein Recovery-Verfahren soll möglichst nur die Registrierung eines neuen FIDO-Authenticators ermöglichen.
- Ein verwendeter Recovery-Schlüssel muss anschließend ungültig werden bzw. ersetzt werden.
- Recovery-Vorgänge werden vollständig protokolliert.

## Step-up für kritische Aktionen

Eine bestehende Session reicht später nicht für jede Aktion aus.

Für besonders sensible Vorgänge kann eine erneute FIDO-Bestätigung erforderlich sein, z.B.:

- neue FIDO-Karte registrieren;
- Sicherheits- oder KI-Berechtigungen ändern;
- wichtige Daten löschen;
- kritische Systemkonfiguration ändern;
- später eventuell Finanzaktionen freigeben.

## KI und Sicherheit

Auch die spätere KI-Autonomie folgt demselben Modell.

Die KI darf nur innerhalb ausdrücklich definierter Rechte handeln. Je kritischer eine Aktion, desto höher die notwendige Freigabestufe.

Beispiel:

```text
lesen / analysieren
        ↓
empfehlen
        ↓
Aktion vorbereiten
        ↓
definierte Aktion ausführen
        ↓
kritische Aktion nur mit zusätzlicher Freigabe
```

Alle sicherheitsrelevanten und autonomen Aktionen müssen nachvollziehbar protokolliert werden.

## Noch zu entscheiden

- konkrete Backup-FIDO-Strategie;
- sicherer Fernzugang;
- Break-Glass-/Recovery-Verfahren;
- Session-Laufzeiten und automatische Sperren;
- welche Aktionen eine erneute FIDO-Bestätigung verlangen;
- spätere Rollen und KI-Berechtigungsstufen.

Diese Punkte werden vor Umsetzung der produktiven MOSA-2-Authentifizierung verbindlich festgelegt.
