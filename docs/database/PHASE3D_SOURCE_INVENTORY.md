# Phase 3D-A – belegtes Quelleninventar

**Stand:** 19.10.2026; reine Repository-Analyse, keine DB-/Provider-Abfrage.
MOSA-2-Ausgangspunkt: `2d23913a0f86bfa61785f71bed1fda1170cfe17f`.
Untersuchte fixlab-Revision: `baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c`.
fixlab wurde ausschließlich über GitHub GET gelesen und nicht verändert.

**Beweisgrenze:** Die folgenden Quellen, Writer, Leser und Speicherverträge sind
im Code vorhanden. Tatsächlicher aktueller Tabellenbestand, Registrierungen,
Datenmengen, Vollständigkeit und Verfügbarkeit der Provider bleiben **OFFEN**.
Historische Deployment-Dokumentation ist kein neuer Laufzeitnachweis. Kein
privater Store, Rohpayload, Credential oder echter Marktdatensatz wurde gelesen.

## Nachprüfbare Codebelege

Alle Verweise sind auf die oben genannte fixlab-Revision festgelegt:

| Kürzel | Datei / wesentliche Funktionen |
| --- | --- |
| H | [market_history_contract.php](https://github.com/masterxfix/fixlab/blob/baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c/php/market_history_contract.php#L10): Tabellenvertrag L23–140; Observation-Validierung/Hash L197–225 |
| P | [market_history_persistence.php](https://github.com/masterxfix/fixlab/blob/baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c/php/market_history_persistence.php#L71): Insert-/Dedupe-Plan, Batch-Transaktion, Payload-Archiv |
| B | [market_collection_bundle.php](https://github.com/masterxfix/fixlab/blob/baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c/php/market_collection_bundle.php#L7): Decimal-/Zeitnormalisierung und Yahoo/L&S/Frankfurt-Payloadmapping |
| Q | [mosa_market_live_quote_runner.php](https://github.com/masterxfix/fixlab/blob/baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c/php/mosa_market_live_quote_runner.php#L111): L&S/Tradegate-Offerten, Quellentscheidung L146–163, Persistenzbundle L175–190 |
| L | [mosa_market_source_lab.php](https://github.com/masterxfix/fixlab/blob/baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c/php/mosa_market_source_lab.php#L189): Tradegate-Zeit/Währung L189–206, Berlin-Uhrzeit L221–223, Indikatoren L74–107 |
| C | [mosa_market_collection_runner.php](https://github.com/masterxfix/fixlab/blob/baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c/php/mosa_market_collection_runner.php#L30): Requestprofile, Source-/Venue-Kontext L56–69, FX L80–116 |
| S | [mosa_market_source_registry.php](https://github.com/masterxfix/fixlab/blob/baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c/php/mosa_market_source_registry.php#L8): `mosa_market_sources.json`, technische Registrierungen, Unique-/Replace-Regeln |
| I | [mosa_invested_instrument.php](https://github.com/masterxfix/fixlab/blob/baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c/php/mosa_invested_instrument.php#L11): explizite ISIN/WKN und Luhn-Prüfung L17–33 |
| E | [mosa_etf_reference.php](https://github.com/masterxfix/fixlab/blob/baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c/php/mosa_etf_reference.php#L10): mosa_etf_references.json, justETF-Stammdaten und ISIN-Prüfung; ausdrücklich keine Preisquelle |
| M | [mosa_market_identity.php](https://github.com/masterxfix/fixlab/blob/baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c/php/mosa_market_identity.php#L9): Identitätsstore, Exchange-/MIC-/Währungs-/Zonenprofile, Kandidatenbewertung |
| R | [mosa_current_market_selector.php](https://github.com/masterxfix/fixlab/blob/baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c/php/mosa_current_market_selector.php#L7): bisherige Current-Auswahl aus SQL-History |
| N | [collectors/nel_market.php](https://github.com/masterxfix/fixlab/blob/baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c/php/collectors/nel_market.php#L8): NEL-Altstand und Yahoo-/L&S-Fallback |
| J | [nel_intraday_mid_history.php](https://github.com/masterxfix/fixlab/blob/baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c/php/nel_intraday_mid_history.php#L6): NEL-Mid-JSON, Punktvalidierung und Zeit-Unique |
| D | [mosa_market_chart_read_model.php](https://github.com/masterxfix/fixlab/blob/baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c/php/mosa_market_chart_read_model.php#L42): SQL-Lesewege für Livekurse, Schlussreferenz, Volumen und Indikatoren |
| K | [mosa_market_indicator_collector.php](https://github.com/masterxfix/fixlab/blob/baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c/php/mosa_market_indicator_collector.php#L69): Indikator-Observation, Einheiten und XXX-Fallback |
| F | [mosa_boerse_frankfurt.php](https://github.com/masterxfix/fixlab/blob/baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c/php/mosa_boerse_frankfurt.php#L5): Frankfurt-Konstanten und Snapshot-/History-Requests |
| U | [mosa_fuel_price_history.php](https://github.com/masterxfix/fixlab/blob/baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c/php/mosa_fuel_price_history.php#L6): separater Kraftstoffpreis-Speichervertrag; hier nur abgegrenzt |

## Quellen und ihre Verwendung

| Quelle / Provider | Persistenz und Identität | Werte / Zeit / Währung / Intervall | Verwendung und Fallbacks |
| --- | --- | --- | --- |
| Live-Offerte L&S / `lang_schwarz` | `fixlab_market_observations`; `asset_key`, SourceKey des Providers/Assets; Attempt trägt ISIN, instrument_id/market_id; Venue `lang_schwarz_tradecenter` (Q) | HTML `bid`, `ask`, `midTime`; `last_price` wird als Mid aus demselben Bid/Ask gespeichert. EUR im Adapter festgelegt. quoted_at aus lokaler Berlin-Uhrzeit und Abrufdatum, collected_at UTC. Kein OHLC/Volumen/Barintervall | Livekurs und Intraday-Chart; vollständige Offerte erforderlich; Router gegen Tradegate, siehe unten |
| Live-Offerte Tradegate / `tradegate_bsx` | gleiche SQL-Tabelle; ISIN-Prüfung; Venue `tradegate_bsx`; SourceKey Provider/Asset (Q,L) | Bid/Ask aus BSX-HTML, Mid daraus abgeleitet; Handelswährung aus HTML, nur EUR akzeptiert. „Letzte Aktualisierung“ Datum/Uhrzeit Europe/Berlin → UTC. Kein OHLC/Volumen im Quote-Writer | alternative vollständige Live-Offerte; ETF- und Aktienregeln unterscheiden sich im alten Router |
| Yahoo Chart / `yahoo_finance_chart` | gleiche SQL-Tabelle; registriertes Symbol, Exchange und ISIN-Kontext aus S/C/M; `series=chart`, `daily_1d` oder `snapshot` | Unix-Sekunden in timestamp[] bzw. regularMarketTime. Chart O/H/L/C/Volume nach `bar_*`; Snapshot regularMarketPrice, chartPreviousClose, Tages-/52-Wochen-Werte, regularMarketVolume. Native Payload-Währung, GBp/GBX → GBX. C fordert 1m intraday bzw. 1d daily/backfill an | Heimatmarkt-/Chart-/Tageshistorie und Volumen, z.B. Oslo/NOK. Keine direkte Oslo-Börsenanbindung belegt: hier Yahoo mit OSL/.OL-Kontext. Bar-Ende/Intervall nicht vollständig in SQL-Zeile gespeichert |
| L&S Chart / `lang_schwarz_chart` | gleiche SQL-Tabelle; Registrierung mit instrument_id, market_id, Kategorie; exakter ISIN-Match. quote_variant mid/bid/ask/trade und series intraday/history (B,S) | numerische Zeitstempel werden ausdrücklich als codierte Europe/Berlin-Wanduhr interpretiert (B; NEL-v2-Adapter). Mid/Trade → last_price, Bid/Ask je separat. EUR-Kontext; kein belegtes vollständiges OHLCV | generischer historischer Punktweg und NEL-Altadapter. NEL-Adapter versucht Chartvarianten und fällt von intraday auf history zurück. Bid-/Ask-Einzelpunkt ist kein vollständiges Observation-Payload |
| Frankfurt / `boerse_frankfurt_api` | gleiche SQL-Tabelle; ISIN+MIC aus Registrierung, Venue boerse_frankfurt (F,C,B) | Snapshot lastPrice/timestampLastPrice, Vorclose, Tages-/52-Wochen-Werte, Stückvolumen, Umsätze. History timeValuePairs Unix-Sekunden + Preis. Währung originalValue mit Kontextprüfung EUR. Requests verwenden M/H/D; keine vollständigen OHLC-Bars in diesem Pfad | offizielle Schluss-/Referenzquelle im alten MOSA. Snapshot/History sind Marktwerte; market_capitalization/shares_outstanding gehören zur getrennten Referenzfamilie |
| Yahoo FX / `yahoo_finance_chart` | `fixlab_market_observations`; FX-Symbol im Collection-Kontext; genaue gespeicherte FX-Assetzuordnung erst in 3D-B bestätigen (C) | `<CCY>EUR=X`; GBX-Skalierung über GBPEUR=X ×0,01. Native und FX-Quote bilden derived_quote/EUR; quoted_at wird auf den älteren Zeitpunkt beider Inputs gesetzt | Währungsumrechnung für native Quotes; bei FX-Ausfall kann native Beobachtung erhalten bleiben. Kein automatisches Mapping einer abgeleiteten EUR-Quote auf die native Route |
| Marktindikatoren / Yahoo und Tradegate | gleiche SQL-Tabelle, `observation_kind=market_indicator`; source_key `market_indicator:<key>:<provider>` (K,L) | Konfiguriert: DAX, S&P 500, Nikkei 225, Gold, Brent. Symbol/Referenztyp/Einheit in Konfiguration und derivation_json. Unix-/Adapterzeit, collected_at UTC. Fehlende Währung wird im Writer zu XXX, daher keine sichere Währungsaussage aus drei Buchstaben allein | Chart-/Marktumfeld; Tradegate-DAX und Yahoo nach Status current/delayed. Indexpunkte, Futures und Währung sind fachlich zu trennen; Assetklasse/Einheit offen |
| NEL-Altstand / Yahoo Oslo + FX, L&S Mid | `data/nel_state.json` v1/v2, kein separater Current-SQL-Vertrag (N) | price_eur, original_price/currency, quoted_at, collected_at, fx_rate/symbol/source, sources{}, active_source, Alter/Qualität. Yahoo NEL.OL in NOK, NOKEUR=X; L&S EUR | Legacy-Auswahl: frisches Yahoo zuerst, dann frisches L&S, sonst jüngster verfügbarer Wert. Nur dokumentiert, keine neue MOSA-2-Regel |
| NEL-Intraday-Mid-Cache / L&S Chart | `data/nel_intraday_mid_history.json`, Quelle lang_schwarz_nel_mid (J) | Header asset_key/provider/source/quote_variant=mid/currency=EUR; points[].quoted_at, price_eur, collected_at; updated_at technisch. Maximal 2.000 Punkte, sortiert, Zeit-Unique | begrenzter Mid-Chartcache, keine Vollhistorie, keine OHLC-Bars. SQL-/JSON-Überlappung muss vor späterem Import separat ausgewertet werden |
| Kraftstoffpreise (angrenzender Chartpfad) | `fixlab_mosa_fuel_price_history` (U) | station_id, recorded_at UTC, gerastertes interval_started_at (5 Minuten), e5/e10/diesel; Preise EUR/Liter im zugehörigen Chart, keine OHLCV. UNIQUE station_id+interval_started_at | Verbraucherpreis-/Dieselanzeige. Kein Wertpapierkurs; bis zu eigenem Asset-/Einheitenvertrag ausdrücklich unresolved/out_of_scope; nicht als 5m-Bar umdeuten |

### Vorhandene technische Persistenz

H/P definieren sechs Tabellen, deren tatsächliche Live-Existenz hier nicht geprüft wurde:

| Tabelle | Bedeutung / Schlüssel / Dedupe |
| --- | --- |
| fixlab_market_observations | append-only Markt-/Chart-/FX-/Indikatorzeilen; PK id; UNIQUE asset_key+source_key+observation_kind+quoted_at+content_sha256 |
| fixlab_market_collection_runs | Sammlung mit UUID, Status, Zählern, Auswahlreferenz; UNIQUE run_uuid; keine Kurs-History |
| fixlab_market_source_attempts | Quellversuch mit Provider-/Instrument-/Marktkontext, technischen Zeiten/Status, optionalem Payloadhash; keine Kurs-History |
| fixlab_market_untimed_quotes | Bid/Ask ohne belegte Marktzeit; time_status=not_provided_by_payload; UNIQUE asset_key+source_key+content_sha256 |
| fixlab_market_reference_observations | Marktkapitalisierung/Aktienanzahl, observed_at nur Collectionzeit; time_status=collection_time_only; UNIQUE asset_key+source_key+content_sha256 |
| fixlab_market_payload_archive | gzip-Rohbytes mit SHA-256, Größen, first/last_seen_at, seen_count; UNIQUE payload_sha256; keine fachlichen Kurszeilen |

P dedupliziert fachliche Zeilen mit einem `ON DUPLICATE KEY UPDATE id=id` und
separaten Archiv-Upserts. Der alte Contenthash kanonisiert Dezimalstrings,
entfernt jedoch u.a. collected_at, run_id/run_uuid, created_at und is_selected.
Er ist **nicht** der MOSA-2-Dedupe-Key und darf nicht als solcher kopiert werden.

Die privaten JSON-Dateinamen `mosa_invested_instruments.json`,
`mosa_etf_references.json`, `mosa_market_identities.json` und `mosa_market_sources.json` sind im Code I/E/M/S
belegt. Der konkrete private Laufzeitpfad und die Dateiinhalte wurden nicht
ermittelt. Es werden keine privaten Serverpfade veröffentlicht.
Onboarding-/Incremental-State-Dateien sind Steuerzustände, keine zusätzliche
Marktpreisquelle. Refresh-/Health-JSON und Payloadarchive werden nicht als Kurse
eingestuft.

### Bisherige Current-/Prioritätsregeln, ausschließlich Bestandsbeschreibung

Der NEL-Yahoo-Altadapter
[yahoo_finance_test.php L186–245](https://github.com/masterxfix/fixlab/blob/baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c/php/collectors/yahoo_finance_test.php#L186)
bevorzugt regularMarketPrice, fällt sonst auf den letzten numerischen Chart-Close
zurück, verwendet für quoted_at aber weiterhin regularMarketTime. Ohne zugehörige
Preis-/Zeit-Evidenz ist dieser Fallback keine bewiesene zeitgleiche Snapshotquote;
ein betroffener Altstand bleibt für die spätere Übernahme offen.

Q und der reine Router `mosa_market_quote_router.php` prüfen vollständige
Offerten, Aktualität, relativen Spread, Alter und stabilen SourceKey.
Aktien-Quellenwechsel benötigen zwei Empfehlungen, bei Ausfall sofortiger
Failover. ETF-Regeln bevorzugen Tradegate, verwenden L&S als Fallback/Kontrolle
und berücksichtigen Marktstatus/Konflikt. R wählt über quoted_at, bei Gleichstand
Routenrang und lexikalische technische Felder. Diese unterschiedlichen Regeln
werden **nicht** in MOSA 2 übernommen. Eine explizit ausgewählte Route bleibt
Voraussetzung der Phase-3C-Current-Entscheidung.

## Identität und offene Punkte

I validiert explizite ISIN mit Prüfziffer und WKN mit Format; der Store ist nur
pro user_id+object_key eindeutig. M leitet alte asset_keys ab und hat dabei eine
NEL-Ausnahme; der MOSA-2-Entwurf verwendet keine solche Asset-Sonderregel.
Yahoo-Heimatmarkt-/Ticker-Kandidaten stammen aus einer Bewertung, nicht aus
einem universellen Ticker-Identitätsbeweis. Ein ISIN-Ländercode beweist weder
Börsenplatz noch Handelswährung. Provider-Instrument-ID, MIC und Symbol sind
separate Route-/Identifierdaten.
E liefert eine zusätzliche, ISIN-basierte ETF-Identität mit optionalen WKN-/Ticker-
und Fonds-/Handelswährungsdaten. Q bezieht ETF-Assets daraus und aus aktiven
Relationship-Einträgen. Das ist Auswahlkontext, kein Depot-/Positionsimport.

**Eindeutig:** Konzept einer validierten ISIN, danach bestehender eindeutiger
MOSA-2-Identifier oder explizite Route. **Tatsächliche Zuordnung: offen**,
weil Quell- und Zielkataloge nicht gelesen wurden. Gleiches Objekt bei mehreren
Benutzern, widersprüchliche ISIN/WKN, Mehrfachtreffer, fehlende ISIN und
symbolgleiche verschiedene Märkte müssen unresolved/reject werden.

Offene Fälle und das vollständige Feld-/Zielmapping stehen in
[PHASE3D_FIELD_MAPPING.md](PHASE3D_FIELD_MAPPING.md). Phase 3D-A schafft einen
prüfbaren Vertrag; erst ein separat freigegebenes 3D-B darf echte begrenzte
Quellzeilen und dazugehörige Metadaten read-only auswerten. Hier wurde weder
ein Collector gestartet noch ein SQL-Adapter ausgeführt.
