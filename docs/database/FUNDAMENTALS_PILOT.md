# Erster Fundamentals-Pilot: PNE, Geschäftsjahr 2025

Freigabe: Nutzerauftrag vom 01.11.2026; Ausgangscommit `5bbb29f`, echtes Dogado
Schema 6 bestätigt durch Actions 41288523408. Keine Migration oder Aktivierung.
Ausführungskennung `fundamentals-pne2025-20261101-01`; genau ein manueller Lauf,
Laufnummer/Versuch 1, exakter main-Commit und exklusiver dauerhafter Privatmarker.

## Ausführungsplan

1. Vorhandener gepinnter SSH-/DB-Zugang, feste Datenbank `h29077_mosa2_test`.
   Vollständige Schema-6-Prüfung, Ledger, gesperrter Collector, eindeutige bestehende
   Asset-Identität per ISIN und Name, Fingerprints aller 21 ursprünglichen Tabellen,
   fünf Currents und 28 Observations. Die fünf Fundamentals-Tabellen müssen leer sein.
2. Bestehende Privatpfade mit dem gemeinsamen No-Follow-/Owner-/Mode-Prüfer prüfen;
   aktuelle Inodes innerhalb dieses Laufs binden. Genau ein exklusiver Marker unter
   `private/mosa2-collector/locks`, genau ein privates Unterverzeichnis unter `runs`.
3. Vorhandener `ReadOnlyHttpTransport`: genau ein anonymer HTTPS-GET auf die
   beauftragte offizielle Meldung, kein Redirect, Retry, Cookie oder Login. Die
   vorbereitende Quellenprüfung verwendet Suchindex-Inhalte, keinen zweiten GET
   auf die Meldung. Nur die tatsächlichen Antwortbytes fließen in den Writer.
4. Originalbytes unverändert als `response.body`, URL/HTTP-Status/Content-Type,
   Abrufbeginn und tatsächliches Antwortende als `response.json` archivieren.
   Verzeichnis 0700, Dateien exklusiv 0600, fsync, SHA-256 und erneutes Lesen in
   einem frischen SSH-Prozess. Kein Webroot, Repository, Actions-Artefakt oder Dump.
5. Adapter validiert tatsächliche Antwort; allgemeiner Core prüft Definitionen,
   exakte Dezimalwerte, Dimensionen, Perioden, Dedupe und Current-Projektion.
   Bestand unmittelbar vor Transaktion erneut vergleichen. Source, File, Fetch,
   Katalog, Observations und Current zusammen committen. Bei Fehler vor Commit
   Transaktion zurücknehmen; unklare Commit-Bestätigung niemals erneut schreiben.
6. Unabhängige DB-Verbindung: alle geschriebenen Felder gegen den Plan lesen,
   Originalbestand vergleichen, Dubletten-/Zeilenzähler und gesperrten Collector
   bestätigen. Rohdatei erneut öffnen und vollständig hashen. Keine Provideranfrage.

## Fachliche Qualifikation

Gesamtleistung ist ausdrücklich **kein Umsatz**. Unbereinigtes und normalisiertes
EBITDA sind verschiedene offene Katalogeinträge; EBIT ist ein vierter Eintrag.
Werte werden ausschließlich aus eindeutigen tatsächlichen Ergebnissätzen gewonnen.
Explizite Vorjahreswerte bleiben eigene FY-Observations. Current wählt das jüngste
belegte Periodenende pro Asset/Kennzahl/Periodenart; gleiche Perioden mit
widersprüchlichen Fakten stoppen. Aktuelle Pilotqualifikation: kalenderjährliches
PNE-Geschäftsjahr 01.01.–31.12.; kein allgemeiner Schluss von FY auf Kalenderjahr.
Andere Geschäftskalender benötigen ihre eigene belegte Adapterzuordnung.

Native Einheit `EUR_MILLION`, Währung EUR, exakte Skalierung 1000000/1. Keine
Float-Konvertierung, Prozent-/Euro-Verwechslung oder erfundenen fehlenden Werte.
Publikation ist nur auf Tagesebene belegt: `reported_at` bleibt NULL statt einer
erfundenen Uhrzeit. Das Datum steht im reproduzierbaren `field_path` zusammen mit
dem Offset in der versioniert normalisierten HTML-Textdarstellung. `as_of_at`
bleibt ebenfalls NULL. Tatsächliche Abrufzeit wird separat in `observed_at` erfasst.

Prognosen, Dividendenvorschläge, MW-/GW-Projektangaben und weitere noch nicht
qualifizierte Aussagen bleiben vollständig im Raw; Fetch-Parserstatus deshalb
`partial`. Dies beschränkt nicht den langfristigen Kennzahlenumfang. Das ist ein
erster qualifizierter FY-Adapter, keine allgemeine Freigabe für andere Perioden,
Restatements oder einen automatischen Mehrquellenbetrieb. Core und Katalog haben
keine PNE-spezifischen Tabellen oder SQL-Abzweige; unveränderte Katalogdefinitionen
können wiederverwendet werden. Historienfakten sind insert-only, Current atomar.

## Messung und Nachweise

Current liest ausschließlich `m2_fundamental_current` per vollständigem PK;
History liest begrenzt per Asset/Kennzahl/FY und vorhandenem Periodenindex.
Je ein gezieltes SELECT plus EXPLAIN ANALYZE auf Dogado, keine Lastsuite.
PHP-Laufzeit inklusive SSH-Tunnel wird getrennt von serverseitiger
EXPLAIN-ANALYZE-Ausführungszeit ausgewiesen; keine pauschale Subtraktion als
behauptete Netzwerkzeit. Öffentliche Logs enthalten nur Status, Hashes, Zähler,
Kennzahlschlüssel und Messzeiten; keine Originalantwort oder privaten Werte.

Synthetische Offline-Tests decken Parser/Evidenz, Vorjahre, Prognosenausschluss,
Dezimal-/Einheitenvalidierung, Konflikte, atomare Schreibfehler, unbekannten Commit,
Einmalzugriff, Archivschutz und Manipulation ab. Echte Speicherung gilt erst mit
dem unabhängigen Dogado-Readback als belegt. Die Chrome-Sichtprüfung prüft die
bestehende Testseite; dieser Auftrag enthält keine neue Fundamentals-Oberfläche.
