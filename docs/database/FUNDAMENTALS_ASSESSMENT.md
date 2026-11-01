# Offline-Modellbereitschaft: mosa2-ai-assessment-v1

Basis c076ed16e6e6a7d03d41dd0bd28417c7926485ba. Keine neue DB-Verifikation,
Modellabfrage, Archivierung oder Actions-Ausführung erforderlich/freigegeben.

## Gemeinsamer Adapter

`scripts/fundamentals/assessment.py` akzeptiert genau einen bestehenden
`mosa2-ai-analysis-input-v1`-Snapshot. Keine Unternehmensadapter und keine zweite
Finanzberechnung. Beobachtungswerte, Herkunft, Rundung, Einheiten und Quellen
bleiben erhalten. Nur Berechnungskennungen kommen hinzu: SHA-256 über die
kanonische vorhandene Berechnung mit Domain `mosa2-calculation-v1`.
Der Input-Digest bindet das gesamte angereicherte Eingabepaket. Der ursprüngliche
Snapshot wird nicht verändert. Fremde Top-Level-/Identitätsfelder werden abgewiesen.
Aktienfilter und DB-Leser bleiben unverändert; zugelassen sind nur die Snapshots
des bereits geprüften Equity-Lesers, keine beliebigen Depot-/ETF-Daten.

Responses-Request: konfigurierbares Modell (Vorgabe gpt-6.1-sol), Reasoning medium,
store=false, tools=[], tool_choice=none, striktes text.format.json_schema,
3000 maximale Ausgabetokens einschließlich Reasoning, Timeout 60 Sekunden,
Antwort maximal 64 KiB. Keine Tools, Websuche, fremden Datenquellen oder Retries.
Offizielle Vertragsgrundlage:
https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses
https://developers.openai.com/api/docs/models/gpt-6.1-sol

Standardmäßig ist kein Transport konfiguriert; keine Secret-Abfrage und keine
CLI/Action können hier einen Modellrequest starten. Der Adapter nimmt einen
explizit injizierten Responses-Transport an: `(request, timeout,
max_response_bytes) -> Response-JSON`. Tests injizieren ausschließlich Fakes.
`responses_transport.py` stellt den späteren HTTP-Transport bereit: festes
api.openai.com:443 /v1/responses, TLS-Standardprüfung, Timeout 60 Sekunden,
maximal 64 KiB Antwort, keine Redirects oder automatischen Retries. Konstruktion
verlangt explizit live_authorized=true und einen übergebenen Schlüssel; es gibt
keinen Zugriff auf Umgebungsvariablen oder Konfigurationsdateien. Diese
Aktivierung benötigt den gesonderten Pilotauftrag samt freigegebenem Secret.
Ein Transport ohne passende Input-Digest-Autorisierung wird im Adapter abgewiesen;
nach dem ersten Versuch sind Adapter und HTTP-Transport verbraucht, auch bei Fehler.
Ein späterer Pilot-Workflow muss zusätzlich eine dauerhafte Einmalreservierung
gegen erneute Prozessstarts besitzen. Keine solche Ausführung wird hier aktiviert.

## Ausgabe und unabhängige Prüfung

Schema: `scripts/fundamentals/assessment.schema.json`, identisch zu `SCHEMA` im
Adapter. Alle Felder sind Pflicht; zusätzliche Eigenschaften sind verboten.
Der lokale rekursive Validator prüft sämtliche im Schema verwendeten Typ-,
Enum-, Objekt- und Arrayregeln unabhängig von der Modell-Schemaerzwingung.
Danach folgen Digest-/Metadaten-/Referenz-/Werteprüfungen.

- factual_claims: Observation-ID, vorhandener Kennzahlenschlüssel, exakter
  Originalwert, Einheit, Source-ID, Herkunft und Rundungskennzeichen.
- calculation_claims: vorhandene Berechnungs-ID und exakt bereitgestellter Wert.
- interpretations: beleggebundene Kategorien NUMERICAL_INCREASE,
  NUMERICAL_DECREASE, ADJUSTMENT_GAP, CURATED_ROUNDING, LIMITED_COVERAGE.
- uncertainties: kontrollierte offene Fragen zu Ursachen, Bereinigungsüberleitung
  und Nachhaltigkeit; keine Behauptung einer konkreten unbelegten Ursache.
- missing_information: die tatsächlichen fehlenden Kernkennzahlen des Snapshots.

Diese erste Version verwendet absichtlich keine frei formulierten Modelltexte:
Unbekannte Kennzahlen, neue Zahlen oder Ursachen können daher nicht über Prosa
in eine formal gültige Bewertung gelangen. Richtung und Bereinigungsinterpretationen
werden gegen die referenzierten bestehenden Berechnungen geprüft, nicht neu
finanziell berechnet. Das begrenzt die sprachliche Breite; es ist kein Nachweis
allgemeiner semantischer Wahrheitsprüfung beliebiger Freitexte.
Jeder Fakt und jede Berechnung muss vollständig und genau einmal referenziert
sein. Input-Digest, gewünschtes Modell, gemessene Erzeugungszeit und Aufrufkennung
müssen den vorgegebenen Metadaten entsprechen. Die Provider-Response-ID wird
zusätzlich separat erhalten. Refusals, unvollständige Antworten, Tools,
unbekannte Referenzen, falsche Werte, zusätzliche Felder oder doppelte JSON-Keys
werden ohne Reparaturaufruf verworfen. Nach erfolgreicher Prüfung werden Usage
und konservative tatsächliche Kostenobergrenze zurückgegeben.

Ohne Fakten entsteht lokal INSUFFICIENT_DATA mit konkreten Datenlücken, leeren
Claims/Interpretationen, model_id=none und model_executed=false. Keine bezahlte
Abfrage nötig. Simulierte Antworten haben simulated=true und model_executed=false;
sie sind keine tatsächliche KI-Auswertung. Keine Speicherung der Bewertungen.

## Kosten und Zugang zum späteren Pilot

Höchstens eine Aktie pro Adapteraufruf und ein Transportversuch pro Instanz.
Konservative Obergrenze 0,10 USD. Eingabetoken-Obergrenze: gesamte serialisierte
Request-UTF-8-Bytezahl plus 2048 Framingreserve, maximal 30000. Ausgabetokenlimit
3000. Es wird kein zusätzlicher kostenpflichtiger Tokenzähl-Request gestartet.
Eine übergebene, vom Pilotverantwortlichen anhand offizieller Quellen geprüfte
Preisfreigabe muss Modell, positive Ein-/Ausgabepreise pro Million Tokens,
Quell-URL und höchstens 24 Stunden alten UTC-Prüfzeitpunkt enthalten. Der Adapter
kann die Echtheit dieser freigegebenen Preiskonfiguration nicht selbst attestieren;
die spätere Pilotfreigabe muss ihre Herkunft sichern.
Bei fehlenden, veralteten oder unpassenden Preisen und Kosten >0,10 USD: Stopp
vor Transport. Kein Cache-Rabatt in der Obergrenze.
Am 01.11.2026 laut offizieller Modellseite: 2 USD/Million Input und 10 USD/Million
Output; beim maximalen Budget rechnerisch höchstens 0,09 USD. Diese Dokumentation
ist keine dauerhafte Preisfreigabe. Vor dem echten Pilot neu prüfen. Usage wird
gegen die freigegebenen Grenzen geprüft; unklare Ergebnisse niemals wiederholen.
OpenAI-API-Abrechnung ist getrennt von ChatGPT-/Codex-Nutzung.

Einziger vorgesehener Secretname: MOSA2_OPENAI_API_KEY. Sein autorisiertes
Vorhandensein wurde nicht geprüft und wird nicht behauptet. Es wurden keine
produktiven Konfigurationen, alten MOSA-Schlüssel oder Secretwerte gelesen.
Die alte Anbindung wurde nicht benötigt; keine Änderungen an fixlab.

Nächster Auftrag: gesonderte Freigabe für genau einen echten DroneShield-Aufruf
mit frischem read-only Snapshot, überprüftem Preisbudget, festem Commit,
Einmalreservierung, gesichertem MOSA2_OPENAI_API_KEY, aktiviertem begrenztem
Responses-Transport, unabhängiger Ausgabeprüfung und Usage-/Kostenbericht.
Erste nötige Nutzerentscheidung: diesen Secret-Zugang und das einmalige
API-Kostenbudget ausdrücklich freigeben; falls der Secret noch fehlt, ihn über
den vorgesehenen geschützten GitHub-Secrets-Weg einmalig einrichten. Kein Key im Chat.
