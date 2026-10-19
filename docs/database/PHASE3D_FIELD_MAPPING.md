# Phase 3D-A – deterministisches Feldmapping und Dry-Run-Vertrag

**Entwurfsstand, kein Importer.** Quelle und Belege sind im
[Quelleninventar](PHASE3D_SOURCE_INVENTORY.md) mit fixlab-Commit
`baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c` festgelegt. Ziel sind ausschließlich
die bestehenden Migrationen 0001/0002 und der validierte Phase-3C-Vertrag.
Keine DB-Verbindung, keine Datenübernahme und keine neue Provider-Spalte.

## 1. Klassifikation aller relevanten Quellfelder

Die Kategorien beziehen sich auf den Zielvertrag: **ÜBERNEHMEN (U)** erhält
einen fachlichen Wert nach Validierung; **ABLEITEN (A)** bildet deterministisch
Identität/Format/Referenz daraus; **VERWERFEN (V)** bedeutet keine Übernahme in
die sieben Zieltabelle(n), nicht Verlust des zulässigen Auditnachweises;
**OFFEN (O)** sperrt die betroffene Zielabbildung bis zur Klärung.
Ein Feld kommt innerhalb seiner Quellstruktur in genau einer Kategorie vor.
Für benannte Zusatzstrukturen gelten die expliziten Ergänzungen unten.

### fixlab_market_observations (vollständiger Spaltenvertrag H)

| Kategorie | Quellfelder | Begründung / Ziel |
| --- | --- | --- |
| A | id, asset_key, source_key, provider_key, quote_variant, series, venue_key, quoted_at, collected_at | stabile Quellreferenz, Asset-/Source-/Route-Auflösung, Zeitnormalisierung; Details unten |
| U | symbol, isin, currency, last_price, bid_price, ask_price, bar_open, bar_high, bar_low, bar_close, bar_volume | Identifier/Route, Währung, echte Preiswerte bzw. OHLCV; Bars nur bei zusätzlich gesicherter Intervall-/Endsemantik |
| V | run_id, run_uuid, is_selected, source_status, payload_sha256, content_sha256, created_at | Lauf-/Auswahl-/Qualitäts-/Alt-Hash-Metadaten sind kein neuer Marktwert; alten Key nicht wiederverwenden, technische Schreibzeit nicht als Abrufzeit ausgeben |
| O | observation_kind, open_price, previous_close, day_high, day_low, weeks52_high, weeks52_low, volume_units, turnover_original, turnover_eur, price_fixings, trading_time_start, trading_time_end, minimum_tradable_unit, fx_rate, fx_symbol, derivation_json | Typ-/Einheiten-/FX-/Current-Erweiterung oder nicht vorhandenes Zielfeld; gezielte Gründe unten, keine stillschweigende Preis-/Volumen-/Zeitersetzung |

`observation_kind=market_quote` mit last_price kann Observation werden;
`series=chart/daily_1d` mit bar_* ist ein Bar-Kandidat. Ein reiner Bar-Close wird
nicht nebenbei zu einer zweiten Punktbeobachtung. `fx_quote`, `derived_quote`,
`venue_activity` und `market_indicator` benötigen eine explizite Asset-/Einheiten-
und Provenienzentscheidung (O), statt pauschal wie Wertpapierquotes zu gelten.
Die offenen Preis-/Statistikfelder sind nicht wertlos: die aktuelle
Observation-Tabelle hat dafür keine Zielspalten, und der validierte Writer
projiziert sie auch nicht in Current. Sie werden im Dry Run als O gezählt.
`volume_units` ist typischerweise ein kumulierter Snapshot, `bar_volume` ein
Intervallwert; keine Gleichsetzung. Umsatz ist kein Stückvolumen.

### Weitere Tabellen (jeweils vollständiger H-Spaltenvertrag)

| Quellstruktur | A | U | V | O |
| --- | --- | --- | --- | --- |
| fixlab_market_untimed_quotes | id, asset_key, source_key, provider_key, venue_key, collected_at | symbol, isin, currency, bid_price, ask_price | run_id, run_uuid, payload_sha256, content_sha256, created_at | time_status (Marktzeit fehlt; ganze Kursabbildung unresolved) |
| fixlab_market_reference_observations | id, asset_key, source_key, provider_key, venue_key, observed_at | symbol, isin, currency | run_id, run_uuid, payload_sha256, content_sha256, created_at | time_status, market_capitalization, shares_outstanding (keine Marktquote; kein Ziel in diesen Tabellen) |
| fixlab_market_collection_runs | id | — | run_uuid, asset_key, collector_key, started_at, finished_at, run_status, selected_source_key, selected_observation_id, attempt_count, success_count, error_count, created_at | — |
| fixlab_market_source_attempts | id, asset_key, source_key, venue_key, provider_key, payload_role, quote_variant, instrument_id, market_id, category_type_context | symbol, isin, currency | run_id, run_uuid, attempted_at, finished_at, attempt_status, http_status, latency_ms, response_bytes, parse_status, error_code, payload_sha256, observation_count, created_at | — |
| fixlab_market_payload_archive | id | — | payload_sha256, source_key, content_type, compression, original_bytes, stored_bytes, payload_gzip, first_seen_at, last_seen_at, seen_count, created_at | — |

Attempt-Instrumentkontext darf nur über einen eindeutigen Join von Run, Asset,
Source und Provider zur fachlichen Zeile ergänzt werden. Ein Mehrfachtreffer
mit unterschiedlichen instrument_id/market_id ist unresolved, kein First-Match.
Run-/Attempt-/Archivzeiten ersetzen **nie** eine fehlende Marktzeit.
Archive werden nicht vollständig in den Dry-Run-Report kopiert.

### Registrierungen und zusätzliche Strukturen

| Struktur | U | A | V | O |
| --- | --- | --- | --- | --- |
| S: Source-Registration | isin; technical.symbol, exchange, instrument_id, market_id, category_symbol, category_name, exchange_name, currency, timezone | asset_key, provider_key, source_key | user_id, status, discovered_at; technical.selection_method | Konflikte/Mehrfachregistrierungen sind Zeilenstatus, keine zusätzliche Feldkategorie |
| I: Invested-Instrument | isin, wkn, object_name | object_key | contract_version, user_id, origin, recorded_at, recorded_by | — |
| M: Market-Identity | primary_symbol, primary_exchange_code, primary_mic, primary_currency, primary_timezone, isin, wkn, asset_label | object_key, asset_key, early_provider, early_venue_label, early_currency, early_timezone | contract_version, user_id, country_code, country_label, primary_exchange_label, status, evidence, derived_at | nicht aufgelöste/konfliktbehaftete Kandidaten sperren das Objekt |
| E: ETF-Reference | object_name, asset_type, isin, wkn, ticker, fund_currency, trading_currency, trading_venue, xetra_ticker, xetra_reference_symbol | object_key | contract_version, user_id, reference_url, source_label, source_url, fetched_at, recorded_at, recorded_by | ter, distribution_policy, replication, fund_size, inception_date (kein Kurswert/Zielattribut dieser sieben Tabellen) |
| J: NEL-Intraday-Header | currency | asset_key, provider_key, source_key, quote_variant | contract_version, updated_at | — |
| J: points[] | price_eur | quoted_at, collected_at | — | — |
| N: nel_state v1/v2 | original_price, original_currency | asset_key, symbol, active_source, quoted_at, collected_at | contract_version, quote_age_seconds_at_collection, fresh_at_collection, source_status, fallback_status, technical | price_eur, fx_applied, fx_rate, fx_symbol, fx_source, sources (Verschachtelung/FX und verlorene Erfassungsdetails klären) |
| U: Kraftstofftabelle | — | id | station_name, station_status, fetch_success, error_code | station_id, recorded_at, interval_started_at, e5, e10, diesel, source (separates Einheiten-/Assetmodell; gesamte Familie bleibt unresolved) |

Die Quelle M ist ein abgeleiteter Identitätsvorschlag. U bedeutet dort nur
„als belegten Kandidaten erhalten“, nicht ungeprüft freigeben. Eine später
entdeckte zusätzliche Spalte oder JSON-Eigenschaft erhält **keinen** Default:
`unresolved/unknown_source_field` und explizite Mappingrevision.
Transportdiagnostik, Refresh-Status, Cache-/Lock-/Incremental-State sowie
Darstellung (Labels, Formatierungen, Spread-/Altersanzeigen) sind V für diese
Zieltabellen. Nicht gelesene sensible Store-Inhalte werden nicht vorausgesetzt.
E ist nur Stammdaten-/Kennungsevidenz; justETF ist ausdrücklich keine Preisquelle.
ETF-WKN/Ticker sind im Altvertrag optional und nur grob textvalidiert: sie
benötigen für das Ziel dieselbe Kennungs-/Scope-Prüfung wie andere Quellen.

## 2. Gemeinsame Identitäts-, Zeit- und Wertregeln

**ID:** Quell-ID/asset_key niemals als m2_assets.entity_id kopieren. Eine
versionierte, separat bereitgestellte Katalogaufnahme löst in dieser Reihenfolge
auf: gültige ISIN → bereits bestehender eindeutiger MOSA-2-Identifier → explizite
Asset-/Source-/Route-Zuordnung. WKN dient als zusätzlicher Konsistenzbeleg.
Alle vorhandenen Belege müssen zum selben Asset passen. Fehlender Treffer ist
unresolved, widersprechende Belege sind reject/identity_conflict. Ein vorhandener
aber widersprüchlicher ISIN darf nicht durch einen Ticker übersteuert werden.
Ticker nur mit nachgewiesenem Markt-/MIC-Scope; kein Name-/Prefix-/NEL-Sonderfall.
Aktuell existieren keine in diesem Auftrag gelesenen Zielkataloge oder realen IDs.
Geplante Neuanlagen erhalten nur stabile `proposed_*_key`, keine erfundenen IDs.

**ROUTE:** Vorgeschlagene Source-Identität ist ein geprüftes Tupel aus Provider,
Venue, Währung und Preiseinheit, z.B. Yahoo/Oslo/NOK oder L&S/TradeCenter/EUR.
Ein versionierter Katalog gibt den source_key vor; keine bestehenden Zielquellen
werden behauptet. Route-Tupel: Asset + Source + semantischer route_type
(`quote_mid`, `quote_trade`, `bar_1m`, `bar_1d` als Entwurf) + externe Kennung.
Die Kennung enthält je nach belegtem Pfad ISIN+MIC, registriertes Yahoo-Symbol
oder instrument_id+market_id+Quoteart; feste Feldreihenfolge und eindeutige
Escapes im Katalog, maximal 255 Zeichen. Keine Zugangsdaten/URLs mit Query-Secrets.
Konkrete Katalogeinträge bleiben bis 3D-B offen. Ein change von Instrument,
Venue, Währung oder Quoteart erfordert eine eigene geprüfte Route.

Bestehende Constraints gelten: UNIQUE(source_id, route_type, external_key) und
UNIQUE(asset_id, source_id, route_type). Zwei externe Kennungen für dasselbe
Tupel sind daher ein Konflikt, kein zusätzlicher Insert. Unterschiedliche Venues
desselben Providers benötigen unterscheidbare Source-Kontexte, keine neue Spalte.

**TIME:** Ziel ist DATETIME(6), UTC, explizit normalisiert; keine lokale Zeit
ohne nachgewiesene Zone. Zeitquelle und Konvertierung werden je Dry-Run-Zeile
angegeben. Bereits normalisierte SQL-Zeiten nicht erneut um Stunden verschieben.

| Quellzeit | belegte Semantik | Ziel / Sperre |
| --- | --- | --- |
| B/C: quoted_at aus Yahoo timestamp[]/regularMarketTime | Unix-Sekunden → UTC; Chartstart bzw. Snapshot-Marktzeit je Profil | starts_at oder market_at; Profilbeleg erforderlich |
| Q: quoted_at L&S-HTML | midTime + Abrufdatum in Europe/Berlin, ggf. Vortag nach bestehender Heuristik | gespeichertes UTC als market_at; nur Uhrzeit ohne Abrufkontext unresolved |
| Q/L: Tradegate-Aktualisierung | Datum+Uhrzeit Europe/Berlin → UTC | market_at; fehlendes Datum/Mehrdeutigkeit unresolved |
| B: L&S Chart numerisch | ausdrücklich lokale Berlin-Wanduhr in numerischer Codierung, nicht normaler Unix-Epoch | nur gesicherter Adapterpfad konvertieren; DST-Doppelstunde ohne Offset unresolved; normalisierte SQL-quoted_at nicht erneut konvertieren |
| F/B: Frankfurt timestampLastPrice / timeValuePairs.time | ISO mit Zone / Unix-Sekunden → UTC | market_at; keine künstliche Bar-Endzeit |
| B/C/Q: collected_at, JSON collected_at | Collection-/Erfassungszeit in den nachgewiesenen Writern UTC | observed_at; kein Ersatz für market_at |
| H: created_at, Run started/finished, Attempt attempted/finished | technische Schreib-/Laufzeiten | V; nicht zu Marktzeit umdeuten |
| Referenz observed_at | ausschließlich Abrufzeit, collection_time_only | kein market_at, Familie unresolved |
| J: updated_at | Cache-Schreibzeit | V; points[].collected_at verwenden |
| N: quoted_at/collected_at ohne Zone | Altvalidator akzeptiert freies DateTime-Parsing; nicht jeder Altstand beweist UTC | ohne belegte Producer-/Versionszuordnung unresolved |

**VALUE:** Persistierte DECIMAL-Werte als Strings lesen und mit der bestehenden
Phase-3C-Normalisierung prüfen; Preis DECIMAL(28,10), Volumen DECIMAL(32,8).
JSON-Zahlentext verlustfrei lesen und in Dezimalstring überführen, nicht erst
über IEEE-Float. Bereits im alten Writer gerundete acht Stellen sind die
vorhandene Evidenz; ursprüngliche Präzision nicht erfinden. Überlauf, NaN,
Exponenten ohne vereinbarte Expansion, Preis <=0 oder bid>ask → reject.
Fehlende optionale Werte bleiben NULL, nicht 0. Bid-only/Ask-only wird ohne
unabhängigen Preis weder gemittelt noch über mehrere Zeitpunkte zusammengefügt.

**CURRENCY:** Native Währung der jeweiligen Route erhalten; keine EUR-Annahme
aus Nutzerstandort/Assetname. Payload-/Registrierungs-/Route-Konflikt → reject.
L&S und Frankfurt haben einen belegten EUR-Adapterkontext; Yahoo trägt die
native Währung, Oslo im Profil NOK. GBX ist eine Preisuntereinheit, kein
ungeprüftes ISO-Währungsziel: bis zur expliziten, exakt dezimalen GBX→GBP-
Skalierungsfreigabe unresolved/unit_scale_required. XXX/fehlende Währung bei
Indikatoren bleibt unresolved/unit_or_currency_missing. FX-/Derived-Daten nicht
mit nativen Quotes unter derselben Route vermischen.

## 3. Zielmapping jedes Attributs

P = Pflicht; O = optional/NULL. Die Regeln ID/ROUTE/TIME/VALUE/CURRENCY gelten
für jede Zeile und konkretisieren Validierung und Reject. `unresolved` bedeutet
fachlich noch nicht entschieden, `reject` ein belegter ungültiger/konfliktärer
Wert. Technische Importzeiten kommen aus einem eingefrorenen Dry-Run-Manifest,
nicht aus einem bei jeder Auswertung neu gelesenen Systemzeitpunkt.

### m2_assets

| Zielattribut | Quellfeld / Transformation | P/O | Validierung / Reject / offene Frage |
| --- | --- | --- | --- |
| entity_id | ISIN/Identifier/Explizitkatalog → ID | P | FK auf vorhandene m2_entities und Asset; Neuanlage benötigt später separat angelegte Entity, keine alte id kopieren |
| asset_class | belegter Instrumenttyp: stock→equity, ETF→etf als Katalogentscheidung | P | nur bestätigter Typ; Index/Future/FX/Fuel offen, nicht pauschal equity |
| display_name | I.object_name bzw. bestätigter Assetname | P | nicht leer, <=255; Name ist kein Identitätsschlüssel |
| base_currency | bestätigter Assetkatalog, nicht einzelne Quote-Währung | O | fehlt → NULL; widersprüchliche Basiswährung unresolved |
| status | freigegebener Zielkatalogstatus | P | keine alten technischen freshness/status-Werte kopieren; Entscheidung offen |
| created_at | Manifest.import_at UTC | P | TIME; technische Neuanlage, kein Marktzeitpunkt |
| updated_at | Manifest.import_at UTC | P | TIME; gleiche Eingaben gleicher Entwurf |

### m2_asset_identifiers

| Zielattribut | Quellfeld / Transformation | P/O | Validierung / Reject / offene Frage |
| --- | --- | --- | --- |
| id | Zielzuweisung, nicht Quell-id | P bei späterem Insert | im Dry Run keine numerische ID erfinden |
| asset_id | ID | P | eindeutiges vorhandenes/proposed Asset |
| identifier_type | isin/wkn aus I, ticker aus bestätigter Registrierung | P | erlaubter Katalogtyp; fehlende Kennung unresolved |
| identifier_value | originaler bestätigter Kennungswert | P | Länge <=128, keine fremden Payloadreste |
| normalized_value | trim/uppercase bei ISIN/WKN; Ticker gemäß geprüftem Scope-Vertrag | P | ISIN-Format+Prüfziffer, WKN-Format; widersprüchliche Normalisate reject |
| scope_key | ISIN/WKN: leer; Ticker: belegter MIC-/Venue-Scope | P | Ticker-Scope nie leer; isin/wkn/figi Scope zwingend leer |
| is_primary | versionierte Identifier-Auswahl | P | 0/1; keine alte is_selected-Quote als Identifierpriorität verwenden |
| source_id | belegte Kennungsprovenienz aus Katalog | O | FK oder NULL; Preisprovider nicht ungeprüft zum Identitätsbeweis machen |
| valid_from | belegter Gültigkeitsbeginn | O | sonst NULL, nicht recorded_at/discovered_at erfinden |
| valid_to | belegtes Gültigkeitsende | O | sonst NULL |
| created_at | Manifest.import_at | P | TIME; Unique(type,normalized,scope) muss zum selben Asset gehören |

### m2_sources

| Zielattribut | Quellfeld / Transformation | P/O | Validierung / Reject / offene Frage |
| --- | --- | --- | --- |
| id | ROUTE-Katalogauflösung oder proposed_source_key | P später | keine alte Source-ID vorhanden voraussetzen |
| source_key | versionierte Provider-/Venue-/Währungs-/Einheitenidentität | P | <=128, eindeutig, Stabilität ohne user_id; Katalogfreigabe offen |
| source_type | belegter Datentyp aus Quelle, z.B. API/HTML; derived getrennt | P | kein Quote-observation_kind als Quellenidentität; Wert im Katalog festlegen |
| display_name | Provider+Venue, sachliche Bezeichnung | P | <=255, kein privater Nutzername |
| base_url | öffentlicher Provider-Origin aus Requestdefinition | O | <=512, keine Query-/Authdaten; NULL möglich |
| enabled | explizite Zielfreigabe | P | 0/1; Existenz des Altadapters aktiviert keine neue Quelle |
| created_at | Manifest.import_at | P | TIME |
| updated_at | Manifest.import_at | P | TIME |

### m2_asset_source_routes

| Zielattribut | Quellfeld / Transformation | P/O | Validierung / Reject / offene Frage |
| --- | --- | --- | --- |
| id | eindeutiger ROUTE-Katalogeintrag | P später | unresolved ohne Eintrag, keine Quell-attempt-id |
| asset_id | ID | P | eindeutiger Assetbezug |
| source_id | ROUTE | P | passender Provider/Venue/Währung/Einheit |
| route_type | belegte Quoteart oder Barintervall → katalogisierte Rolle | P | mid/trade/bar getrennt; unbekannte Variante unresolved |
| external_key | ISIN+MIC oder Yahoo-Symbol oder instrument_id+market_id+Quoteart | P | <=255, feste Serialisierung, keine mehrdeutigen Joins; beide bestehenden UNIQUEs beachten |
| priority | expliziter Zielkatalogwert | P | unsigned SMALLINT; keine alte Routerrangfolge übernehmen; Entscheidung offen |
| enabled | explizite Freigabe | P | 0/1; keine automatische Aktivierung |
| created_at | Manifest.import_at | P | TIME |
| updated_at | Manifest.import_at | P | TIME |

### m2_market_observations

| Zielattribut | Quellfeld / Transformation | P/O | Validierung / Reject / offene Frage |
| --- | --- | --- | --- |
| id | spätere Zielzuweisung | P später | Quell-id nur source_reference |
| asset_id | ID aus asset_key+ISIN+Registry | P | fehlend unresolved, Konflikt reject |
| source_id | ROUTE aus provider_key+Venue+Währung | P | keine automatische Provider-Vermischung |
| route_id | ROUTE einschließlich quote_variant/series | P | gehört exakt zu asset_id+source_id; Mid/Trade unterscheiden |
| currency | currency bzw. bestätigter nativer JSON-Kontext | P | CURRENCY; GBX/XXX offen, kein stummer FX-Transfer |
| price | last_price; J.price_eur oder N.original_price nur bei eindeutigem Source-Kontext | P | VALUE; bar_close nicht automatisch duplizieren; nur Bid/Ask ohne Preis unresolved |
| bid | bid_price desselben Quellobjekts | O | VALUE, NULL erlaubt; kein Join verschiedener Quotes |
| ask | ask_price desselben Quellobjekts | O | VALUE, bid<=ask wenn beide gesetzt |
| volume | nur explizit semantisch passendes Quellvolumen | O | volume_units/Snapshot-Zeitraum offen; ohne Nachweis NULL, kein bar_volume-Doppelmapping |
| market_at | belegtes quoted_at / J.points[].quoted_at | P | TIME; untimed Quotes bleiben unresolved |
| observed_at | collected_at / J.points[].collected_at | P | TIME; ursprüngliche Abrufzeit erhalten, kein jetzt() |
| dedupe_key | dedupeKey(normalisierte zehn Phase-3C-Felder) | P | roher SHA-256, 32 Bytes; alte content_sha256 niemals kopieren |
| created_at | Manifest.import_at | P | technische Zielzeit, außerhalb des zentralen Dedupe-Payloads |

Keine zweite Dedupe-Implementierung. Der spätere Dry Run ruft ausschließlich
`normalizeObservation()`, `canonicalObservation()` und `dedupeKey()` aus
`scripts/phase3c/market_flow.php` auf. Der Key enthält observed_at: gleiche
Marktwerte mit anderer Erfassungszeit sind daher keine identischen Replays.
Alt-History deduplizierte diese Erfassungszeit weg; verlorene Abrufe können
nicht rekonstruiert werden. JSON/SQL-Replays sind nur bei identischen vollständig
normalisierten Payloads duplicate, sonst separat bzw. bei Konflikt reject.

### m2_market_bars

| Zielattribut | Quellfeld / Transformation | P/O | Validierung / Reject / offene Frage |
| --- | --- | --- | --- |
| id | spätere Zielzuweisung | P später | keine alte Observation-id |
| asset_id | ID | P | eindeutig |
| source_id | ROUTE | P | native Source/Venue/Währung |
| route_id | ROUTE mit belegter Barserie | P | gleiche Asset-/Source-Provenienz |
| interval_key | belegtes Requestprofil/Archiv: 1m/5m/1h/1d | P | nur diese vier; series=chart/history allein reicht nicht; andere Intervalle unresolved |
| currency | bestätigte native Währung | P | CURRENCY |
| starts_at | Yahoo timestamp[] bzw. zugehöriges normalisiertes quoted_at | P | TIME plus belegte Bar-Startsemantik, nicht Tagesdatum erraten |
| ends_at | belegte Intervall-/Sitzungsgrenze | P | starts_at<ends_at; Tagesbar nicht blind +24h UTC bei DST/Handelssitzungen; ohne Beleg unresolved |
| open_price | bar_open | P | VALUE, >0; aus price-only History nicht erfinden |
| high_price | bar_high | P | >=open/close/low |
| low_price | bar_low | P | <=open/close/high |
| close_price | bar_close | P | VALUE, >0; adjclose nicht ungeprüft verwenden |
| volume | bar_volume | O | VALUE und passende Einheit/Zeitspanne, sonst NULL/offen |
| trade_count | keine belegte allgemeine Quellspalte | O | NULL; price_fixings oder Parser-trade-count ist nicht automatisch Bartradezahl |
| observed_at | collected_at der gespeicherten Barversion | P | TIME; Revisionszeit erhalten |
| created_at | Manifest.import_at | P | technische Zielzeit |

Identität: asset_id+route_id+interval_key+starts_at. Identischer vorhandener
Barpayload → duplicate. Gleiche Identität mit abweichendem OHLCV/Ende →
reject/bar_identity_conflict, bis eine Revisionsregel separat festgelegt ist.
SQL-History enthält kein allgemeines interval_key/ends_at. `daily_1d` liefert
einen Intervallhinweis, aber nicht automatisch die vollständige End-/Sitzungs-
und Adjustierungssemantik. L&S-Punkte und Frankfurt-timeValuePairs sind keine
belegten OHLC-Bars. 3D-A ist im Bar-Fall deshalb ein **fertiger Sperrvertrag**,
keine Behauptung, jede vorhandene Zeile bereits importieren zu können.

### m2_market_current

| Zielattribut | Quellfeld / Transformation | P/O | Validierung / Reject / offene Frage |
| --- | --- | --- | --- |
| asset_id | normalisierte gültige Observation | P | genau ein Current je Asset |
| source_id | dieselbe ausgewählte Observation/Route | P | keine Cross-Source-Auswahl aus Alt-is_selected |
| route_id | explizit gewählte Route | P | Wechsel ohne Arbitration weiterhin abgelehnt |
| currency | dieselbe Observation | P | kein Vermischen nativer/abgeleiteter Werte |
| price | dieselbe Observation.price | P | Phase-3C-Validierung |
| bid | dieselbe Observation.bid | O | NULL erhalten |
| ask | dieselbe Observation.ask | O | NULL erhalten |
| day_open | kein Feld im validierten Zehn-Felder-Writer | O | NULL; Alt-open_price erst nach separater Projektionsregel |
| day_high | dito | O | NULL; nicht aus fremder Source mischen |
| day_low | dito | O | NULL; Erweiterung offen |
| previous_close | dito | O | NULL; Frankfurt-Referenz nicht als Current-Preis einsetzen |
| day_volume | dito | O | NULL; Quelle/Einheit/Tag müssen erst freigegeben werden |
| market_at | Observation.market_at | P | neuerer Marktzeitpunkt gewinnt |
| observed_at | Observation.observed_at | P | Gleichstand market_at: neueres observed_at gewinnt; beide Zeiten gleich → unverändert |
| updated_at | technische Manifestzeit bei tatsächlicher Projektion | P | nicht als Marktzeit ausgeben |

Current-relevant ist eine zusätzliche Eigenschaft einer gültigen Observation,
kein zweiter Import derselben Quellzeile. Die Alt-Current-JSON wird nicht 1:1
kopiert. Reihenfolge für eine gewählte Route: market_at, observed_at, danach
stabile source_reference. Bei identischen Zeiten und unterschiedlichem Payload
bleibt die erste deterministisch verarbeitete Projektion erhalten, History
kann beide unterschiedliche Keys enthalten. Keine neue Source-Priorität.

## 4. Reproduzierbarer Dry-Run-Vertrag für den späteren 3D-B-Auftrag

Noch kein ausführbarer Reader/Importer. Ein späterer freigegebener Dry Run nutzt
ein unveränderliches Manifest: Quellcode-Commit, Mappingversion, begrenzte
Quellobjekt-/ID-/Zeitfensterauswahl, read-only Snapshot-ID und Fingerprint,
Katalogversionen/Fingerprints für Assets/Identifier/Sources/Routes, explizite
Current-Routenauswahl, Intervall-/Sitzungskalenderversion, Währungs-/Einheiten-
regeln, feste import_at sowie Software-/Timezone-Datenversion.
Fehlende Manifeste führen zu unresolved, nicht zu einem neuen Live-Fetch.
Keine Ziel-DB-Verbindung: vorhandene Ziel-Keys/Payloads nur aus einer separat
freigegebenen, minimierten Offline-Katalogaufnahme. Ohne diese ist eine Aussage
„insert statt duplicate“ nicht belegt und bleibt unresolved/target_snapshot_missing.

Pro Quellobjekt genau ein Ergebnisobjekt (bei benötigter Aufspaltung explizite
stabile child_reference und getrennter Elternzähler):

| Ausgabe | Vertrag |
| --- | --- |
| source_reference | Repository-/Snapshot-ID + logische Tabelle/Datei + Quell-PK bzw. stabiler Punktindex und Fingerprint; kein privater absoluter Pfad |
| asset_identity | Typ, normalisierte Kennung, Scope und Belegreferenzen; keine Benutzer-/Depotwerte |
| resolved_asset_id | bestätigte Ziel-ID als Dezimalstring oder null plus unresolved/proposed_key; keine erfundene Null-ID |
| source / route | aufgelöste ID oder stabile proposed_key + Typ/externes Instrument/Markt/Währung/Einheit; offene Zuordnung bleibt sichtbar |
| target_type | observation / bar / current-relevant; current-relevant referenziert dieselbe normalisierte Observation und erzeugt keine zweite History-Aktion |
| normalized_values | exakt die zulässigen Attribute des jeweiligen Zielvertrags, Dezimalstrings und UTC(6), optionale Werte explizit null |
| dedupe_key / bar_identity | zentraler Observation-Key als 64 Hexzeichen nur im Report (DB später 32 rohe Bytes), bzw. Bar-Tupel; bei ungelösten Pflichtwerten null |
| action | insert / duplicate / reject / unresolved, exklusiv |
| reason | stabiler maschinenlesbarer Grundcode, keine Exceptions/Secrets/Rohpayloads |
| evidence | minimierte Quellfeld-/Zeit-/Katalogbelege, keine vollständigen sensiblen Providerantworten |

Deterministische Entscheidung: strukturell ungültig oder widersprüchlich →
reject; erforderliche Semantik/Katalogbelege fehlen → unresolved; sonst
normalisieren, Identität erzeugen, mit Offline-Zielaufnahme und vorherigen
Zeilen vergleichen → duplicate oder insert. Sortierung: logische Quellfamilie,
Quell-PK bzw. kanonische Punktzeit, child_reference; kein Systemzeit-/Fetch-
Zufall. Observation-Hashgleichheit erfordert identischen kanonischen Payload,
sonst reject/dedupe_payload_conflict. Keine allgemeine Fehlerunterdrückung.

Mindestens folgende Summen sind aus der Ergebnisliste erneut berechenbar:

- Quellobjekte gesamt; erzeugte Zielkandidaten separat;
- erfolgreich gemappt = insert+duplicate; unresolved; rejects und rejects nach reason;
- erwartete neue Observations; erwartete Dubletten (zusätzlich nach Zieltyp);
- erwartete Bars, jeweils neu/duplicate/konfliktär getrennt;
- betroffene Assets, Sources, Routes (aufgelöste und vorgeschlagene getrennt);
- Währungen bzw. gesperrte Einheiten getrennt;
- frühester/spätester market_at bzw. Bar-starts_at je Zieltyp/Source/Währung;
  unresolved-Zeiten werden nicht in einen scheinbar vollständigen Bereich eingerechnet.

Für die Zielkandidaten gilt: gesamt = insert+duplicate+reject+unresolved.
Current-relevant zählt dieselbe Observation nicht erneut in Quellzeilen-/History-
Summen. Zwei Wiederholungen mit denselben Manifesten und Inputs müssen nach
kanonischer Sortierung bytegleiche Ergebnisdaten und Summen liefern.

## 5. Sperren / offene Entscheidungen für 3D-B

| Grundcode | Fachlich offen / spätere Voraussetzung |
| --- | --- |
| source_snapshot_missing | tatsächliche begrenzte Quellzeilen, Store-Versionen, Datenvollständigkeit und aktuelle Quellenregistrierungen |
| asset_unresolved / identity_conflict | ISIN/WKN/Scope-Konflikte, Benutzerüberlappung, Index/Future/FX/Fuel ohne passenden Assetkatalog |
| route_unresolved / route_identity_conflict | tatsächliche Provider-Instrument-IDs/Venues/Währungen und bestehende UNIQUE-Kollisionen; keine NEL-Ausnahme |
| market_time_unknown / timezone_ambiguous | zeitlose Quotes, lokale Altzeiten ohne Zone, DST-Mehrdeutigkeit, L&S-Altversionen |
| interval_unknown / bar_end_unknown / adjustment_unknown | Barprofil/Start-/Ende/Sitzungskalender und Yahoo-Adjustierungs-/Revisionspolitik fehlen in der flachen SQL-Zeile |
| unit_scale_required / unit_or_currency_missing | GBX, XXX, Indexpunkte, Gold/Brent-Kontrakte, Kraftstoffpreise pro Liter |
| derived_provenance_unresolved | FX-/derived_quote hat zwei Inputquellen; Route und Reproduzierbarkeit müssen vor Übernahme vollständig nachgewiesen sein |
| current_route_unselected | keine ausdrücklich gewählte Route; keine Übernahme alter dynamischer Router-/ETF-/Fallback-Regeln |
| current_enrichment_unmapped | Tagesfelder/Referenz-/Volumenmetrik sind nicht Teil des validierten Observation→Current-Projektionsvertrags |
| target_snapshot_missing | keine eingefrorenen Ziel-IDs/Keys/Payloads; keine erfundenen insert/duplicate-Aussagen |

Das Mapping ist als deterministischer, fail-closed Vertrag fertig. Tatsächliche
Asset-/Route-Auflösung, vollständig eindeutige Zeiten für alle Altstände und
Barimportfähigkeit bleiben teilweise offen. Gerade diese Fälle sind Ergebnisse
von 3D-A, keine Erlaubnis für eine DB-Verbindung oder Phase 3D-B.
