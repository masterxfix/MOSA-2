# Fundamentals, Finanzdaten und Payload-Provenienz

Status: **nur vorbereitet**, Migration 0006, MySQL 8. Keine Anwendung, kein
Fundamental-Collector, Writer, Scheduler, Providerabruf oder Webdeploy.
Basis dieses Entwurfs: `753ddf95e3b0fe00fbb1affdb37b87ba1ccad943`.
0001–0005 und ihre Ledger-Prüfsummen bleiben byte-identisch. Schema 4 bleibt
der bestätigte installierte Stand; 0005 bleibt separat vorbereitete Migration.

## Bestehenden Core erweitern

Kein Neuaufbau: Assets/Entities, Identifier, Sources, physische Routen,
Files und Job-Runs bleiben die gemeinsamen Identitäten. Market Current,
Observations, Bars, Market-Unit-Vertrag und Collector-Reservierungen werden
nicht verändert. 0006 enthält ausschließlich fünf neue CREATE TABLEs.

| Tabelle | Verantwortung |
| --- | --- |
| `m2_provider_fetches` | Ein nachgewiesener Abruf: Quelle, optional Asset/Route/Job-Run, vollständiger Routenhash und Revision, Datei, Rohbytehash/-größe, Content-Type, reale Erfassung, HTTP-/Parserstatus |
| `m2_fundamental_metrics` | Erweiterbarer Katalog: stabiler Schlüssel, Name, Kategorie, Werttyp, Fachsemantik, Dimension, Definitionshash, Status und Zeiten |
| `m2_fundamental_units` | Eigenständige eingefrorene Fundamental-Einheiten mit Version, Dimension, Währung und exakter rationaler Skalierung |
| `m2_fundamental_observations` | Append-only Fakten, Perioden, Originaleinheit, Fetch-/Feldherkunft, realer Erfassungszeit und Dedupe |
| `m2_fundamental_current` | Kleine vorbereitete Projektion mit Wertkopie und exakt gebundener Observation-Identität |

Keine neue Quelldatei-, Job- oder Asset-Verwaltung. `m2_files` speichert
bereits Backend, privaten Speicherort, Größe, SHA-256 und MIME-Typ; ein zweites
Payloadarchiv als BLOB-/JSON-Tabelle ist deshalb unnötig. `m2_sources`
bleibt die Quelle, `m2_job_runs` der optionale Betriebsnachweis.
Routen bleiben optional, wenn die Antwort keine einzelne physische Route besitzt.
Es entsteht keine automatische Registrierung, Aktivierung oder Lesefreigabe.

## Vollständige Rohantworten vor der Fachauswertung

`m2_files` verweist auf unveränderliche Rohbytes außerhalb öffentlicher
Webroots und normaler DB-Hot-Tables. Archivierung vor Parsing:
vollständiger tatsächlich empfangener Body, auch unbekannte Felder, ungültiges
JSON, mehrdeutige oder derzeit nicht verwendete Inhalte. Keine Rekonstruktion
aus bereits gefiltertem JSON. Trunkierung ist kein vollständiger Archivnachweis.
Archivierung von Authentifizierungsheadern, Secrets oder ungeprüften
privaten Antwortteilen ist nicht freigegeben; ein solcher Konflikt muss vor
Speicherung gelöst werden, ohne redigierte Bytes als Original auszugeben.
Quelle, Zugriffs-/Aufbewahrungsrechte und Speichergrenzen sind später zu prüfen;
kostenlos erreichbar bedeutet nicht automatisch uneingeschränkt nutzbar.

`payload_sha256` und `payload_bytes` beziehen sich auf die exakten,
unkomprimierten Originalbytes. Verlustfreie Kompression/Verschlüsselung gehört
zum bestehenden Files-Backend; dessen gespeicherte Repräsentation und Hash
müssen getrennt eindeutig beschrieben sein. Für den neuen Pfad beschreibt
der m2_files-Datensatz die Originaldatei (sha256/byte_size = Rohbody).
Ein späterer Backend-Wrapper muss weiterhin genau diese Originalbytes liefern.
Kein stilles Gleichsetzen von Roh- und Kompressionshash.

Identische Bodies können denselben m2_files-Datensatz und Speichergegenstand
wiederverwenden. Der vorhandene `ix_files_sha256` unterstützt die Suche;
Größe und Bytes werden unabhängig geprüft. Der Index ist bewusst nicht UNIQUE:
der spätere Archivschreiber benötigt eine transaktionale Hash-Reservierung/
bestehende exklusive Job-Sperre und Readback, um parallele Datei-Dubletten zu
verhindern. Hier wird keine konkurrierende Schreibfähigkeit behauptet.
Jeder tatsächliche Abruf behält trotzdem einen eigenen Fetch mit realer Zeit.
`fetch_key` bindet eine stabile Abrufreservierung (Job/Lauf + Request-Ordinal
oder explizite einmalige Importkennung), niemals nur den Bodyhash. Replays
derselben Reservierung dürfen keinen neuen Abruf auslösen.

`unparsed` verlangt NULL-Parserkennung/-version; `parsed`, `partial`,
`rejected` und `failed` verlangen eine benannte Parser-Version.
`parsed` bedeutet syntaktisch/fachlich bearbeitet, nicht „alle Felder
normalisiert“. Die vollständigen Originalbytes bleiben auch danach erhalten.
Ein späterer Parser muss ein versioniertes Feldinventar erzeugen: Pfad,
normalisiert/unmapped/mehrdeutig/ungültig und Grund. Ein großes Inventar kann
als weiterer privater m2_files-Nachweis abgelegt werden; es gehört nicht in
Current. Noch unbekannte Kennzahlen benötigen heute weder neue Spalten noch
unvollständige Platzhalterfakten. Nach Katalogqualifikation können dieselben
Bytes erneut ausgewertet werden, ohne einen Provider erneut abzufragen.

File-Hash/-größe, Quellenbindung und optionale File-Entity/Source-Zuordnung
sowie Route→Asset/Source/Revision/Hash müssen vor einem späteren Schreibvorgang
zentral validiert werden. Die vorhandenen Tabellen besitzen dafür nicht alle
Composite-UNIQUEs; 0006 behauptet keine nachträgliche SQL-Vollbindung und ändert
den Core nicht. `fetch_id + source_id` bindet jede Fundamental-Observation
bereits per Composite-FK an genau ihre Fetch-Quelle. Enthält ein Fetch ein Asset
oder eine Route, müssen sie zum Fakt passen. Mehrassetantworten behalten
NULL-Asset/Route am Fetch und werden erst nach eindeutiger Identitätsauflösung
in einzelne Fakten zerlegt. `field_path` ist ein versioniert interpretierter
JSON-Pfad, HTML-Selektor oder anderer genauer Parser-Locator, keine freie
Behauptung ohne auffindbare Originalstelle.

## Katalog, Werte und Einheiten

Neue Kennzahl = neue Katalogzeile, keine neue Datenspalte. Kategorien sind offene
Maschinenschlüssel, zum Beispiel valuation, profitability, income,
balance_sheet, cashflow, dividend, shares, growth, market_reference.
Keine Anbieter- oder Aktiennamen im DDL. Die Herkunft wird über Source-FKs
gebunden. Definitionshash und Fachsemantik einer verwendeten Kennzahl sind
unveränderlich; nur Anzeigename/Status dürfen kontrolliert geändert werden.
Eine semantisch andere Kennzahl erhält einen anderen stabilen Schlüssel.

Werte sind DECIMAL(38,12), Text bis 1024 Zeichen oder DATE; exakt eine Alternative
ist belegt. Keine FLOATs, impliziten Währungsumrechnungen oder
Null→0-Ersetzungen. Negative Gewinne/Quoten und echte Nullwerte sind zulässig.
Provider-null, nicht lieferbare Werte und fehlerhafte Zahlen erzeugen keinen
Wertfakt; ihr Original und Grund bleiben in der Evidenz. Werte außerhalb des
DECIMAL-/Textbereichs bleiben vollständig im Roharchiv, werden nicht gerundet
oder abgeschnitten und blockieren die betreffende Normalisierung.
Text/Datum nur für ausdrücklich qualifizierte nichtnumerische Fakten,
z.B. Ausschüttungsart oder belegtes Auflagedatum. Ein DATE wird nicht zu einem
erfundenen Mitternachts-Marktzeitpunkt.

Der Market-Unit-Vertrag `mosa2-market-unit-v1` bleibt eingefroren. Er ist an
Market-Writer, Kataloghashes und Format-v2-Prüfungen gebunden. Die separate kleine
Fundamental-Unit-Tabelle vermeidet, diese Bindungen für Finanzkennzahlen
umzudeuten. Exakt gleiche Definitionen können später kontrolliert aus
m2_units abgeleitet werden; keine automatischen Seeds oder stillen Aliase.
Unit-Versionen/Definitionshashes bleiben unveränderlich. Composite-FKs binden
Kennzahl-Werttyp/-Dimension und Unit-Version/-Dimension. Text- und
Datumskennzahlen verlangen genau ihre nichtnumerische Dimension; deren
Einheiten sind unskaliert (1/1). Ein DATE mit Währungseinheit ist unzulässig.

Beispiele für Dimensionen/Einheiten:
monetary/EUR; monetary_per_share/EUR_PER_SHARE; ratio/ONE oder PERCENT
(Skalierung 1/100); shares/SHARE; count/COUNT; dimensionless/ONE_DIMENSIONLESS;
text/TEXT; date/DATE. Das sind **Entwurfsbeispiele, keine freigegebenen Seeds**.
Monetäre Dimensionen verlangen eine Währung, andere verbieten sie.
Währungscodes, genaue rational definierte Einheiten und Prozent-Konvention
werden später gegen den qualifizierten Katalog validiert.
Native 5 Prozent mit PERCENT entspricht 0,05 mit ONE; beide sind ohne belegte
explizite Normalisierung nicht austauschbar. Fachdimension und reiner Zahltyp
dürfen nicht verwechselt werden (Aktienanzahl ≠ beliebiger Count).
Metadaten und Originalwerte bleiben über Fetch erreichbar.

## Perioden und Zeitbezug

| period_type | Semantik / Pflichtfelder |
| --- | --- |
| snapshot | Zeitpunktfakt; keine FY/FQ-/Bereichs-/Forward-Felder; as_of_at nur wenn belegt |
| fy | Geschäftsjahr; fiscal_year und expliziter period_start/end, keine Quartalsnummer |
| fq | Geschäftsquartal; fiscal_year, fiscal_quarter 1–4 und expliziter Bereich |
| ttm | Rollierende zwölf Monate; kein FY/FQ; belegter Bereich optional, niemals erfunden |
| forward | Schätzung; eindeutiger estimate_horizon erforderlich, FY/FQ/Zeitraum nur wenn belegt |

Das FY ist das vom Provider belegte Geschäftsjahr, nicht zwingend das Kalenderjahr.
Q4, FY und TTM bleiben verschiedene Identitäten. Nichtjährliche Rumpfjahre
werden nicht pauschal verworfen. Start < Ende und vollständige Bereichspaare
werden per CHECK erzwungen. Forward-Quartal benötigt ein Geschäftsjahr.
Unbekannte Perioden verbleiben roh bis zur generischen Vertragsqualifikation.

`period_key` = SHA-256 über kanonisch serialisierten, domänenversionierten
period_type/fiscal_year/fiscal_quarter/period_start/period_end/estimate_horizon
mit expliziten NULLs. Periodenkey und Dedupe müssen später im gemeinsamen
Fundamental-Schreiber berechnet und nachgerechnet werden; DDL allein prüft den
Digestinhalt nicht. Date-Felder sind Geschäftskalenderdaten, alle DATETIME(6)
sind explizite UTC-Eingaben.

`as_of_at`: fachlicher Stand, `reported_at`: belegte Veröffentlichung,
`observed_at`: tatsächliche Erfassung, `created_at`: persistierter Fakt.
Ein neuer Abruf ist niemals ein neuer fachlicher Berichtsstand. Fehlender
as_of_at bleibt unbekannt, statt auf observed_at gesetzt zu werden.
Berichtigungen werden als neue Fakten angehängt, nicht als UPDATE der Historie.

## Dedupe, Current und Widersprüche

Die logische Fact-Identität enthält Domainversion, Asset, Source, physische
Route samt Revision/Hash (oder explizites NULL), metric_key samt Definitionshash,
period_key, as_of_at/reported_at, exakten typisierten Wert und Unit-Version/
Definitionshash. Dezimalwerte werden exakt kanonisiert, ohne Float-Rundung.
Gleiche Werte mit anderen Perioden, Quellen, Einheiten oder Berichtsständen
bleiben verschieden. Fetch-ID, beobachtet/erstellt und Parser-Version gehören
nicht zum logischen Dedupe-Key. Neue identische Abrufe behalten neue Fetches,
erzeugen aber keinen identischen zweiten Fakt. Dedupe-Index UNIQUE BINARY(32);
bei Konflikt vollständigen Inhalt vergleichen, nicht blind Erfolg melden.
Ein anderer Locator mit gleicher Semantik erzeugt ebenfalls keinen neuen Fakt;
der neue Fetch bewahrt seine eigene Antwort unabhängig auf.

Current hat absichtlich PK **(asset_id, metric_key, period_type)**. „Pro Asset
und Kennzahl aktuell“ darf FY, FQ, TTM, snapshot und forward nicht gegenseitig
überschreiben. Eine Bildschirmseite kann eine freigegebene Periodenart auswählen
oder die getrennten aktuellen Zustände zeigen. Unterschiedliche Forward-Horizonte
bleiben in History; der ausgewählte Horizont wird pro Current-Slot ausdrücklich
durch spätere Projektionspolitik festgelegt, niemals durch bloße Abrufreihenfolge.

Current enthält Wert, Einheit, Perioden-/Zeitkontext, Source und Observation-ID.
Der Composite-FK bindet letztere exakt an Asset, Kennzahl, Periodenart und Source.
Die restlichen Wert-/Zeitkopien muss der spätere gemeinsame Projektionsschreiber
vollständig mit der History vergleichen, atomar schreiben und unabhängig
zurücklesen. FK allein beweist keine identischen Kopien. Keine generische
„neueste id“-/MAX(id)-Auswahl. Vorausgesetzte Auswahlregeln:
vergleichbare Einheiten, freigegebene Quelle/Route, belegter fachlicher Stand,
Perioden-/Berichtsfortschritt, danach Erfassung als nachvollziehbarer Gleichstand.
Bei gleichem fachlichen Stand widersprüchliche Werte blockieren; ältere Berichte
ersetzen keinen neueren Current. Unbekannte fachliche Zeit ist nicht „frisch“.
Restatements, Sourcewechsel, Konsolidierungs-/Estimatevarianten benötigen
eindeutige Semantik statt stiller Vermischung.

History-Append-only erfordert später INSERT/SELECT-Rechte ohne UPDATE/DELETE
und einen entsprechenden Writervertrag. Keine Trigger und keine erfundene
Rechtefreigabe: diese Migration allein erzwingt keine Append-only-Nutzung.
Raw→History→Current ist ein später separat freizugebender Ingestionsweg.

## Lesewege und statische EXPLAIN-Erwartung

Alle Beispiele sind parametrisierte SELECTs, keine ausgeführten DB-Abfragen.
LIMITs sind feste Obergrenzen; überzählige Ergebnisse werden per Folgeseite
gelesen oder fail-closed gemeldet, nie als vollständiger Bestand abgeschnitten.

| Weg | SQL-Muster / Prädikat und Ordnung | Geplanter Index / erwarteter Zugriff |
| --- | --- | --- |
| 1 alle Current-Werte eines Assets | asset_id=:a; keyset (metric_key,period_type) > (:m,:p); ORDER BY metric_key,period_type; LIMIT 129 | PRIMARY, ref/range, kein History-Zugriff |
| 2 ein Current-Slot | asset_id=:a AND metric_key=:m AND period_type=:p | PRIMARY, const, höchstens eine Zeile |
| 3 zeitliche Kennzahlenhistorie | asset_id=:a AND metric_key=:m AND period_type=:p AND as_of_at<:cursor; ORDER BY as_of_at DESC,id DESC; LIMIT 101 | ix_fund_obs_timeline, range, Reverse-Scan |
| 4 FY-Serie | asset_id=:a AND metric_key=:m AND period_type='fy' AND fiscal_year BETWEEN :lo AND :hi; ORDER BY fiscal_year DESC,fiscal_quarter DESC,period_end DESC,id DESC; LIMIT 101 | ix_fund_obs_period, range |
| 5 FQ-Serie | gleiche Bindungen, period_type='fq', begrenzte Geschäftsjahre; gleiche Ordnung | ix_fund_obs_period, range |
| 6 Source-Provenienz | Observation id=:id; Source id=observation.source_id | zwei PRIMARY-Punktzugriffe; keine Source-Historie |
| 7 Payload-Nachweis | Observation id=:id; Fetch (id,source_id); Files id=fetch.file_id | PRIMARY/uq_fetch_source/PRIMARY; keine Archivsuche |

Bei Zeitleisten-Keysets mit gleichem as_of_at muss der Cursor das id-Tiebreak
einschließen: as_of_at < :t OR (as_of_at=:t AND id<:i).
Die History-IDs dienen nur der Pagination, niemals der fachlichen Konfliktlösung.
Bereiche/Asset/Metric/Periodenart bleiben in jeder History-Abfrage gebunden.
Payloadbytes werden nur auf dem expliziten Evidenzweg nachgeladen.
Der Normalfall liest keine History, Fetches oder Dateien; auch eine
Web-/KI-Auswertung besitzt keinen Provideraufruf im Requestpfad.

**Statischer Plan, kein gemessenes EXPLAIN und keine Laufzeitgarantie.**
Vor einem Apply müssen diese Wege mit natürlichen Indizes auf dem späteren
isolierten MySQL-8-Ziel, repräsentativen Mengen, engen und breiten zulässigen
Bereichen geprüft werden. Kein FORCE INDEX als Ersatz.
Budgets: normale Query ideal <20 ms, zugelassene langsamere <100 ms,
gesamte DB-Zeit pro normaler Seite <200 ms; Seitenaufruf <1,0 s,
p95 <1,5 s, harte Obergrenze 2,0 s. Die große Historie bleibt außerhalb des
Hot-Reads; die Markt-Current-Abfragen werden durch 0006 nicht geändert.

## Aus MOSA übernommene Erfahrung (ausschließlich Quellcode gelesen)

Gelesen im Repository masterxfix/fixlab: php/market_history_contract.php,
php/market_history_persistence.php, php/market_collection_bundle.php,
php/mosa_market_source_lab.php, php/mosa_boerse_frankfurt.php,
php/mosa_etf_reference.php. Keine Ausführung und keine Änderungen dort.

Übernommen: exakte Dezimalstrings; Source-/Identitäts-/Einheitenbindung;
reale Providerzeit getrennt von Erfassung; zeitlose Referenzwerte nicht als
zeitgestützten Handel ausgeben; vollständige Payload-Kandidaten und
unmapped_field_inventory; SHA-basierte Originalbelege. justETF bleibt
ETF-Stammdatenquelle und wird nicht zum Kursprovider umgedeutet.
Nicht übernommen: Markt-Fixspalten pro Anbieterfeld, BLOB-Hot-Tabellen,
begrenzte bekannte Feldlisten als Erhaltungsgrenze oder alte DB-Namen.
Die im MOSA-Code sichtbaren Felder belegen frühere Implementierungen,
keine heutige kostenlose Vollverfügbarkeit oder allgemeine Betriebsrechte.
Dieser Entwurf begrenzt weder Anbieter noch Kennzahlen auf die bekannten Beispiele.

## Fachbeispiele (synthetisch, keine Kurse oder Providerbehauptungen)

| metric_key | Kategorie / Dimension | Periodenbeispiel / Bedeutung |
| --- | --- | --- |
| market_cap | market_reference / monetary | snapshot; EUR, as_of nur wenn geliefert |
| pe_ratio | valuation / ratio | snapshot; ONE, negativer Wert nicht pauschal verboten |
| eps | income / monetary_per_share | ttm; EUR_PER_SHARE; TTM-Zeitraum nur wenn belegt |
| revenue | income / monetary | fy, fiscal_year=2025, belegter 2025-01-01 bis 2025-12-31 |
| revenue_growth | growth / ratio | fy 2025; PERCENT oder ONE mit eindeutigem Vergleichsbasisvertrag |
| net_income | income / monetary | fy 2025; einschließlich realer negativer Ergebnisse |
| profit_margin | profitability / ratio | fy 2025; Gewinn-/Umsatzdefinition im Katalog exakt festgelegt |

Die Beispielbereiche sind inklusive Provider-Geschäftskalendertage;
end_date ist der letzte Berichtstag, keine erfundene Marktzeit.
Umsatzwachstum muss im Definitionstext z.B. Vorjahresvergleich mit gleicher
Berichts-/Währungsbasis benennen. Fehlende Vergleichsgrundlage bleibt roh.
Neue Kennzahlen/Units sind qualifizierte Katalogzeilen, kein Schemaumbau.

## Späterer separater Apply und verbleibende Nachweise

Kein Apply-/Rollbackskript in diesem Auftrag. 0006 setzt den exakt qualifizierten
Stand 0001–0005 voraus; nicht direkt auf dem noch bestehenden Schema 4 ausführen.
Backup/Restore, Zustimmung zu 0005 und 0006, Rechte und MySQL-Version,
DDL-Platz/Indexgrößen, vollständige Core-/Ledger-Prüfsummen und Bestandsvergleich
sind vor einem Apply separat nachzuweisen. MySQL-DDL committet implizit;
kein Versprechen eines atomaren Gesamt-Rollbacks. Bei Teilfehler stoppen und
Istzustand feststellen; kein IF NOT EXISTS oder automatischer Retry.
Units/Kennzahlen-Seeds, Privatarchivpfad/Quoten/Rechte, Writer-/Current-Validierung,
Parser-Feldinventar, echte Constraint-/EXPLAIN-/Lasttests und Append-only-Rechte
sind noch nicht implementiert oder aktiviert. Normale Marktseiten bleiben
unverändert. Offline-Tests belegen nur den vorbereiteten Vertrag.

## Offline-Nachweis und Grenzen dieses Abschlussstands

15 neue fokussierte Tests mit dem vorhandenen eingeschränkten DDL-Parser und
SQL-Dreiwert-CHECK-Modell: genaue Tabellen/Spalten/Typen/NULLs, PK/UNIQUE/FK,
Indexpräfixe/-größen, Perioden, typisierte Werte, Units, Fetch-/Current-Bindung,
Dedupe-Designmodell, Rohfeld-Erhalt und negative Constraint-Mutationen.
Die fünf alten Migrationen werden unabhängig per SHA-256 an den Ausgangsstand
gebunden. Kein Test verbindet sich mit einer DB oder einem Anbieter.

57 unmittelbar betroffene bestehende Core-/Market-/Unit-Schema-Regressionen
einmalig bestanden. Die historischen Webdatei-Hashanker des alten
Unit-Testmoduls gehören nicht zu diesem Schemaauftrag und wurden nicht
ausgeführt oder verändert. Die beiden bestehenden Migrationsinventare wurden
um die bereits vorhandene 0005 und die neue 0006 ergänzt; sonst bleiben
bestehende Testverträge erhalten. `git diff --check` bestanden, 0 Actions.
Das ist kein echter MySQL-Syntax-, FK-/CHECK-Ausführungs-, EXPLAIN- oder
Performance-Nachweis. Diese Prüfungen bleiben vor einem separat autorisierten
Apply verpflichtend. Kein unbewiesenes PASS für den Datenbankbetrieb.

## Isolierter MySQL-8-Versuch vom 31.10.2026: noch nicht qualifiziert

**Ergebnis: teilweise; kein erfolgreicher MySQL-Nachweis von 0006.**
[Einziger Actions-Lauf 41204442891](https://github.com/masterxfix/MOSA-2/actions/runs/41204442891)
auf Prüfcommit `7dbaa2405036af886159bb3ea4b7ca0a20e82743`.
Verwendet wurde ausschließlich der bereits vorhandene wegwerfbare
`mysql:8.0`-Dienst, tatsächlich **MySQL 8.0.46**, über Runner-Loopback
127.0.0.1:3307 und die synthetische Datenbank mosa2_collector_isolated.
Keine Dogado-/Testsite-/Produktivverbindung, keine echten Secrets,
keine Provideranfrage, kein Deployment. Container und Netzwerk wurden nach
dem Lauf laut Actions-Cleanup entfernt.

### Erster konkreter Fehler und minimale Korrektur

Der vorhandene PyMySQL-DictCursor lieferte für `SHOW TABLES` der leeren
Service-Datenbank ein leeres Tuple `()`. Die neue Testhilfe verglich
irrtümlich mit der leeren Liste `[]` und brach mit
`() != [] : Service database must be initially empty` ab.
Das ist ein **Fixturefehler vor dem ersten DDL**, kein nachgewiesener
Fehler der Migration. Es wurde keine Migration 0001–0006 angewendet,
keine Ledgerzeile erzeugt, keine Fachprobe ausgeführt und kein Lastdatensatz
geladen. Die einzige fehlgeschlagene Integration ist deshalb ausdrücklich
kein Syntax-/Schema-/Performance-PASS.

Die Testhilfe verwendet jetzt `assertFalse(SHOW-TABLES-Ergebnis)`.
Eine leere Liste und ein leeres Tuple sind damit gleichwertig akzeptiert;
jede nichtleere Tabelle wird weiterhin vor dem ersten DDL abgewiesen.
Die MySQL-Version wird vor diesem Guard in der Evidence festgehalten.
Der gezielte Offline-Test prüft beide leeren und beide nichtleeren Formen
und besteht. Kein Index, FK, CHECK oder Migrationstext wurde gelockert.
**Kein zweiter Actions-Lauf und kein Rerun.**

### Datenmengen und sieben noch offene Messwege

Tatsächlich geladen: **0** synthetische Assets/Kennzahlen/Current-/History-Zeilen.
Vorbereitet, aber noch nicht ausgeführt: 100 Assets, 3 Sources,
52 Kennzahlen (50 numerische plus Text/Datum), 9 Units, 1 kleiner Dummy-File-
Metadatensatz, 1.200 Fetches, **100.288 Observations** und **25.000 Current-Zeilen**.
288 zusätzliche historische Werte verdichten die drei gemessenen Serien
des Testassets auf jeweils 100 Treffer. Current liefert alle 250 Slots
eines Assets über zwei begrenzte Seiten (128 + Sentinel); keine verdeckte
Trunkierung als „alle Kennzahlen“.

| Weg | Geplanter natürlicher Index | Reales EXPLAIN / Median / p95 |
| --- | --- | --- |
| A alle Current-Slots eines Assets (zwei Seiten) | PRIMARY | nicht ausgeführt / nicht gemessen / nicht gemessen |
| B einzelner Current-Slot | PRIMARY | nicht ausgeführt / nicht gemessen / nicht gemessen |
| C zeitliche Historie, LIMIT 100 | ix_fund_obs_timeline | nicht ausgeführt / nicht gemessen / nicht gemessen |
| D FY-Serie, LIMIT 100 | ix_fund_obs_period | nicht ausgeführt / nicht gemessen / nicht gemessen |
| E FQ-Serie, LIMIT 100 | ix_fund_obs_period | nicht ausgeführt / nicht gemessen / nicht gemessen |
| F Source-Provenienz | PRIMARY-Punktzugriffe | nicht ausgeführt / nicht gemessen / nicht gemessen |
| G Payload-/Fetch-Metadaten | PRIMARY / uq_fetch_source | nicht ausgeführt / nicht gemessen / nicht gemessen |

Der vorbereitete Nachweis trennt drei Warm-ups von 40 Messungen pro Weg;
p95 ist der sortierte Messwert ceil(0,95*n). Gemessen wird Client↔DB einschließlich
Ergebnisübertragung, keine Webseite. A umfasst beide Queries der vollständigen
Asset-Lesung. EXPLAIN FORMAT=JSON soll Zugriffstyp, Key und
`rows_examined_per_scan` als **Schätzwerte** sichern; EXPLAIN ANALYZE ergänzt
tatsächliche Iteratorzeilen/-schleifen. Keine Vermischung von Schätzung und
tatsächlich untersuchten Zeilen, keine FORCE-INDEX-Anweisung.
Current darf weder History noch Fetch/File-Tabelle berühren. Großtabellen-
ALL-/vollständige Indexscans oder unerwartete Keys schlagen fehl.
P95 muss für A/B <20 ms und für alle sieben Wege <100 ms liegen.
Das ist nur ein vorbereiteter Prüfumfang, keine gemessene Performancefreigabe.

### Erhaltene Artefakte und Offline-Prüfungen

Migrationen 0001–0005 wurden vor und nach der lokalen Arbeit per SHA-256
an die eingefrorenen Ausgangswerte gebunden; alle sind unverändert.
Auch 0006 blieb fachlich und bytegenau unverändert:
`55457063c72d20498a097d273b5465d34cfd8aba5b2c7c229a9673bfc0c4a60c`.

Vor dem Lauf bestanden 15 bestehende fokussierte 0006-Schematests und
9 neue Offline-Harnessprüfungen (einschließlich korrigierter ursprünglicher
MySQL-Metadatenrendering-Fixture). 57 unmittelbar betroffene Schema-Regressionen
wurden genau einmal ausgeführt und bestanden. Nach dem Actions-Fehler
bestand ausschließlich der zusätzlich betroffene Leertabellen-Guardtest.
`git diff --check` besteht. Es wurden keine breiten Backendregressionen wiederholt.

Die strukturierte Fehler-Evidence liegt im
[Artefakt fundamentals6-isolated-evidence](https://github.com/masterxfix/MOSA-2/actions/runs/41204442891/artifacts/13043576734),
Aufbewahrung sieben Tage. Sie enthält keine vorgetäuschten Datenmengen,
Constraint- oder Performanceerfolge. Die vollständigen, nicht ausgeführten
Constraintproben und sieben Lesewege bleiben reproduzierbar im Testcode.

### Nächster Nachweis und Dogado-Grenze

Für den nun korrigierten Test ist eine **neue ausdrückliche Freigabe eines
weiteren isolierten Actions-Laufs** erforderlich. Bis dieser erfolgreich
abgeschlossen ist, bleiben Apply, SHOW-CREATE-/INFORMATION_SCHEMA-Abgleich,
reale PK/UNIQUE/FK/CHECK-Proben, alle sieben natürlichen EXPLAINs und
Median/p95 **offen**. Es liegt weder ein DB-Architekturfehler noch deren reale
Betriebsfähigkeit nachgewiesen vor.

Auch ein später erfolgreicher isolierter Lauf wäre keine Freigabe für
Dogado: Backup/Restore-Nachweis, Istschema/Ledger, qualifizierter
0005-Ausgangsstand, ausdrücklicher Applyplan, Postcheck und
Rollforward-/Teilfehlersicherheit bleiben separat erforderlich.
