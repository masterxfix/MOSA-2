# Kuratierter Fundamentals-Import ohne Providerabruf

Ausgangscommit: `4fbafbdfcc1e0f88cfd4703598687d557f7145b2`.
Vorbereitung und Offline-Tests sind kein Nachweis einer Dogado-Speicherung.
Nur der einmalige Actions-Lauf mit unabhängigem Readback kann diese bestätigen.

## Eingabe und fachlicher Vertrag

`scripts/fundamentals/manifests/droneshield-fy2025-v1.json` ist die versionierte,
explizit vom Nutzer freigegebene Eingabe. Die 14 gerundeten Werte für sieben
Kennzahlen stammen laut Nutzerrecherche aus Financial Highlights des Annual
Report 2025. Sie liegen ausschließlich im Manifest, nicht im Adapter/Collector.
Dies ist kein neuer Abruf oder unabhängiger Quellenvergleich durch den Runner.
Financial Filings bleibt als unabhängiger Drittanbieter gekennzeichnet;
finanzen.net ist nur der vom Nutzer genannte Vergleich für Umsatz/Gewinn.

Der gemeinsame Vertrag `mosa2-curated-facts-v1` enthält Emittentenidentität,
Quellen, explizite Prüfbestätigung, Katalogdefinitionen, Originaleinheiten,
Geschäftsperioden und Fakten mit Abschnitts-/Spaltenreferenzen. Ein anderes
freigegebenes Manifest kann denselben Importer und SQL-Core verwenden.
Eine Auswahl neuer Manifeste erfordert eine geprüfte Profilfreigabe, keine
neue Unternehmens-SQL-Implementierung oder automatische Aktivierung.

Dezimalwerte sind Strings und werden mit Decimal verarbeitet. Eine Nachkommastelle
beschreibt die veröffentlichte Rundung, nicht zusätzliche Rechengenauigkeit.
FY2025 und FY2024: jeweils 01.01.–31.12., AUD_MILLION unverändert als Originaleinheit.
EBITDA und Underlying EBITDA sind getrennte Katalogeinträge; Underlying PBT ist
kein EBIT. Keine Cash-Bestände als Cashflow. Definitionen und Hashes werden über
den bestehenden Core strikt wiederverwendet; Konflikte stoppen atomar.

## Wahrheitsgemäße Schema-6-Abbildung

Schema 6 benötigt hierfür keine Migration. `http_status` ist explizit nullable;
Parserkennung, Source-Typ und Files-Backend sind versionierbare Zeichenfelder.
Die kuratierte Variante ist ein **Manifest-Eingangsnachweis**, kein HTTP-GET:

| Feld / Nachweis | Kuratierte Bedeutung |
| --- | --- |
| `m2_sources.source_type` | `manually_reviewed_public_facts`, separate kuratierte Quelle |
| `m2_provider_fetches.parser_key` | `curated_public_facts_v1` |
| `m2_provider_fetches.http_status` | SQL NULL, niemals 200 |
| `payload_sha256`, `payload_bytes`, `content_type` | SHA-256/Größe der tatsächlich übergebenen Manifest-Datei, `application/json`; kein HTTP-Response-Hash |
| `fetch_key` | eigene Domain `fundamental-curated-import-v1` |
| `observed_at` | tatsächlicher Zeitpunkt der Manifestverarbeitung im Runner, keine historische Web-Erfassungszeit |
| `m2_files.storage_backend` | `dogado_private_curated_evidence_v1` |
| `m2_files.sha256/byte_size/mime_type` | tatsächliche Evidence-JSON-Bytes und `application/json` |

Das Evidence-JSON (`mosa2-curated-evidence-v1`, `kind=curated_evidence`) erklärt
`http_request_performed=false`, `http_response=null` und die Eingabemethode.
Der genaue Recherchezeitpunkt ist nicht überliefert: `researched_at=null`,
`before_assignment_exact_time_unknown`. Die Nutzerbestätigung bleibt als solche
kenntlich. Der Importzeitpunkt wird tatsächlich in UTC gemessen und separat
gespeichert. Kein erfundenes Request-Datum oder Veröffentlichungszeitpunkt.

Das kleine JSON enthält die genauen Manifest-Bytes als UTF-8-String sowie die
geprüften Faktenbindungen. So lässt sich der Input-Hash auch später unabhängig
nachrechnen. Der Evidence-Hash liegt in der privaten Metadatendatei und in
`m2_files`, außerhalb der gehashten Evidence-Bytes; keine unmögliche rekursive
Selbsthash-Behauptung. Die PHP-Validierung prüft beide Hashes, Klassifikation,
Zeiten, Quellen, Identität, Kataloge, Perioden, Rundung und jeden Faktenbeleg.
Alte Original- und HTML-Evidence-Verträge bleiben aktiv und unverändert streng.

## Ausführung und Bestandsschutz

Manueller Workflow `.github/workflows/fundamentals-curated.yml`, Profil
`droneshield-fy2025-v1`, exakter Main-Commit und
`MOSA2-CURATED-droneshield-fy2025-v1:<commit>`. Höchstens ein neuer Lauf,
Versuch 1, kein Retry; eigener exklusiver Verbrauchsmarker. Der Runner besitzt
keinen Providerabrufpfad. Die bestehenden GitHub-/SSH-/DB-Zugänge werden genutzt.

Der vorhandene private Archivschutz schreibt nur `evidence.json` und dessen
Metadaten: feste freigegebene Kennung, Host-Pinning, Owner/Mode, no-follow,
exklusive Erstellung, fsync und unabhängige Hash-Readbacks vor und nach SQL.
Keine PDF-/Web-Vollarchive und keine Änderung alter Archive.

Generischer SQL-Core: normale Vorprüfung und Sperren, atomare Transaktion,
identische Fakten wiederverwenden, Current nach Geschäftsjahr, unveränderte
Stammdaten/Ledger und Hashbestandsschutz für PNE 11/6, Zeiss 20/10, Markt 28/5.
Anschließend neue Read-only-Verbindung mit anderer Connection-ID, exakte
Readbacks einschließlich Input-/Evidence-Provenienz und begrenzte Current-/History-
Messungen über vorhandene Indizes. EXPLAIN-Iteratorzeit und Clientzeit samt
Tunnel werden getrennt ausgewiesen. Kein erzwungener Index oder Schemaumbau.

## Prüfungen und Ergebnisgrenzen

Sechs fokussierte Tests: freigegebene Manifestwerte/Präzision/Herkunft,
Wiederverwendbarkeit mit zweiter Aktie und abweichendem Geschäftsjahr,
fehlerhafte/fehlende/widersprüchliche Eingaben, gemeinsame Transaktion mit
Katalogwiederverwendung/allen eingefügten Schreibfehlerpunkten/Replay/Readback,
Privatdateischutz und Einmalausführung ohne Provideraufruf. Danach einmalig
HTML-Evidence- und generische PNE-/Zeiss-Regressionen.

Eine erste KI-Einordnung darf ausschließlich bestätigte Readback-Zahlen und
offen ausgewiesene Berechnungen daraus verwenden. Bereinigungen erklären ohne
belegte Überleitung keine Ursachen. Keine Kauf-/Verkaufsempfehlung, externe
KI-API oder KI-Speichertabelle. Automatisierte KI-Auswertung bleibt Folgeauftrag.
