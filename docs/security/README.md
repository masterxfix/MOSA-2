# MOSA 2 – Sicherheit & Zugang

Sicherheit ist ein Grundbestandteil von MOSA 2 und wird von Anfang an mitgeplant.

## Grundsatz

Der normale Zugang zu MOSA 2 soll **nur über FIDO2 / WebAuthn** möglich sein. Die bereits getestete FIDO-Karte ist dabei der primäre Zugangsschlüssel.

Ein klassischer Passwort-Login ist **nicht als normaler Fallback** vorgesehen.

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
