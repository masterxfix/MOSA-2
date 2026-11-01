# Einmaliger echter DroneShield-Modellpilot

Nutzerfreigabe: genau ein Responses-POST, gpt-6.1-sol / medium, höchstens 0,10 USD.
Workflow fundamentals-assessment-once.yml ausschließlich manuell auf main,
Run-Nummer und Versuch 1, exakter Commit plus
MOSA2-DRONESHIELD-AI-ONCE-20261101:<commit>. Kein Rerun oder zweiter Dispatch.

Der vorhandene Read-only-Dogado-Leser prüft Gesamtbestand 45/23 und Markt 28/5,
Ledger und unveränderte Zeilen; Auswahl ausschließlich ISIN AU000000DRO2.
Vor dem POST: genau 14 Fakten, 7 Current, 7 Kennzahlen, FY2025/FY2024 jeweils
01.01.–31.12., AUD_MILLION, manuell kuratierte Herkunft und Rundungskennzeichen.
Echter Snapshot ausschließlich im Runner-RAM. Testmanifest dient nur Offline-
Prüfungen, niemals dem Live-Input. Derselbe Reader prüft nach Erfolg erneut;
der Input-Digest muss identisch bleiben.

Vor jedem POST werden beide Ausgabe-/Eingabeverträge, der vollständige reale
Echo-Entwurf, Referenzen und der tatsächliche Requestumfang geprüft. Der Echo-
Entwurf ist eine lokale Preflight-Prüfung, keine simulierte erfolgreiche KI.
Pilot-Ausgabelimit 4000 Tokens einschließlich Reasoning statt des Adapterdefaults
3000; vollständiges Echo maximal 12000 Bytes als Plausibilitätsgrenze. Ob das
Modell damit tatsächlich fertig wird, entscheidet erst die echte Antwort;
unvollständige Ausgaben stoppen endgültig. Keine Validierungslockerung.

Offizielle Preisprüfung vom 01.11.2026, 15:08:14 UTC:
https://developers.openai.com/api/docs/models/gpt-6.1-sol
Basis Input 2 USD/Million und Output 10 USD/Million. Standardverarbeitung wird
explizit als service_tier=default angefordert, keine Tools und kein Long-Context
über 272k. Veröffentlicht sind außerdem 1,25x Cache-Schreibpreis und regional
10 Prozent Aufschlag. Vorsorglich rechnet der Guard deshalb mit 2,75 USD Input
und 11 USD Output pro Million. Das behauptet keine tatsächlich angefallenen
Zuschläge, sondern eine konservative Obergrenze. Kein Cache-Rabatt angesetzt.
Preisfreigabe maximal 24 Stunden gültig, keine unbekannten Gebühren akzeptieren.
Der vorhandene Guard nutzt tatsächliche Request-Bytes plus Framingreserve und
stoppt vor Reservierung/POST bei >0,10 USD. Spätere Usage-Schätzung ebenfalls
mit den konservativen oberen Raten; keine Rechnungs-/Steuergarantie.

Vor dem HTTP-POST entsteht genau ein kleiner Marker im bestehenden privaten
locks-Bereich: fundamentals-ai-droneshield-20261101-01.consumed. Er enthält nur
Commit, ISIN, Input-Digest, Modell und Workflow. Vorhandene Schutzfunktionen
prüfen private Verzeichnisidentität, Owner/Mode, no-follow, exklusive Erstellung,
fsync und vollständigen Readback/Hash. Kein neuer Archivordner oder Modellarchiv.
Der Marker bleibt auch nach HTTP-Fehler, Timeout oder unbekanntem Ergebnis
verbraucht. Prozessinterner Adapter/Transport sperren ebenfalls den zweiten Versuch.

Einziger API-Key: MOSA2_OPENAI_API_KEY aus dem vorhandenen GitHub-Secret, nur im
Live-Schritt. Keine Secretwerte in Dateien/Logs/Artefakten. Der Wrapper liest
nur sichere Response-Metadaten; ein Versuch nach Reservierung zählt als verbraucht,
auch wenn das tatsächliche API-Ergebnis unbekannt ist. Bei fehlender Usage bleibt
der Kostenstatus UNKNOWN_UNTIL_VALIDATED. Kein Reparatur- oder Kostenrequest.

Nach erfolgreicher Modellantwort: unveränderte strikte Schema-/Wert-/Referenz-
und Interpretationsprüfung. Öffentlich nur Status, sichere Response-ID/Modell,
Digest, Mengen, Interpretationscodes, Usage und konservative Kostenschätzung.
Keine vollständigen Snapshots, Modellantworten oder Finanzwerte in Actions-Logs.
Keine Speicherung der KI-Bewertung. Abschlussbericht darf die bestätigten
Kategorien verständlich darstellen, ohne sie um unbelegte Ursachen zu ergänzen.

Fokussierter Nachweis: vollständiger Echo-/Kostenpfad offline, Marker vor POST,
Markerfehler verhindert POST, fehlender Secret stoppt vor Zugriff, exklusive
Reservierung und Bindung. Dazu bestehende neun Adapterregressionen. Anschließend
höchstens ein echter Actions-Lauf. Ergebnis nicht vor erfolgreichem Live-Nachweis
als KI-Auswertung bezeichnen. Collector und Scheduler bleiben gesperrt.
