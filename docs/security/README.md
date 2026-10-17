# MOSA 2 – Sicherheit & Zugang

Sicherheit ist ein Grundbestandteil von MOSA 2 und wird von Anfang an mitgeplant.

## Dokumentierter Sicherheitsvorfall

Der mögliche Privacy-/Security-Boundary-Fehler vom 17.10.2026 ist hier vollständig dokumentiert:

- [`INCIDENT_2026-10-17_CODEX_DRIVE_E.md`](INCIDENT_2026-10-17_CODEX_DRIVE_E.md)

Dort stehen bestätigte Beobachtungen, ausdrücklich nicht bewiesene Punkte, Chronologie, offene Fragen an OpenAI sowie der vorbereitete englische Bericht.

## Grundsatz

Der normale Zugang zu MOSA 2 soll **nur über FIDO2 / WebAuthn** möglich sein. Die bereits getestete FIDO-Karte ist dabei der primäre Zugangsschlüssel.

Ein klassischer Passwort-Login ist **nicht als normaler Fallback** vorgesehen.

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
