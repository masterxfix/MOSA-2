# Phase 3J – Unit-Schema 0003, ausschließlich offline

Issue #25; Ausgangspunkt `21bc7e359f0eba57e090514528859bcef63087e9`.
[Migration 0003](migrations/0003_market_units.sql) implementiert den physischen
[Phase-3I-Vertrag](PHASE3I_UNIT_CONTRACT.md), ohne ihn auszuführen. Ziel ist
MySQL **8.0.26-16**, InnoDB, strict SQL mode und UTC beim späteren Aufrufer.
Keine DB-Verbindung, Seeds, Ledgerwrites, Datenmigration oder Deployment in
Phase 3J. Die SQL-Datei enthält ausschließlich ein CREATE und vier ALTER.

## Physischer Katalog

`m2_units` ist die einzige neue Tabelle. Schlüssel und Vertragsbezeichner
verwenden explizit `utf8mb4_0900_bin`; Tabellenstandard bleibt wie bisher
`utf8mb4_0900_ai_ci`. Alle Spalten sind NOT NULL außer der Geldwährung.

| Spalte | SQL-Typ | Vertrag |
|---|---|---|
| unit_key | VARCHAR(64) | kanonische providerneutrale Identität |
| unit_version | INT UNSIGNED | positive Definitionsversion |
| unit_contract_version | VARCHAR(64) | mosa2-market-unit-v1 |
| dimension_key | VARCHAR(64) | z. B. monetary, index_point, quantity-Dimension |
| base_unit_key | VARCHAR(64) | direkte Basisdefinition |
| base_unit_version | INT UNSIGNED | positive Basisversion |
| monetary_currency_code | CHAR(3) NULL | genau für monetary belegt |
| scale_numerator | DECIMAL(38,0) | positive ganze Zahl |
| scale_denominator | DECIMAL(38,0) | positive ganze Zahl; niemals 0 |
| definition_sha256 | BINARY(32) | normative Definition/Evidenz |
| status | VARCHAR(16) | ausschließlich frozen |
| created_at | DATETIME(6) | UTC durch Aufrufer sicherzustellen |

PK `(unit_key, unit_version)` identifiziert die Definition. Zusätzlicher UNIQUE
`uq_units_contract(unit_key, unit_version, unit_contract_version)` ist bewusst
vorhanden, damit jede Referenz Definition **und** Vertrag im selben FK bindet.
Self-FK `(base_unit_key, base_unit_version, unit_contract_version)` referenziert
diesen UNIQUE mit ON DELETE RESTRICT und explizitem `ix_units_base`.
Eine Basisdefinition kann sich selbst referenzieren. Andere Definitionen müssen
ihre bereits vorhandene Basis referenzieren; Seeds werden hier nicht erzeugt.

Fünf CHECKs erzwingen positive Versionen und Skalierungszahlen, den monetären
Währungszustand, Vertragsname/frozen und nichtleere Schlüssel/Dimension. Kein
Provider, Asset, Ticker, Handelsplatz, Preis, FX-Kurs oder Routenrang im Katalog.
DECIMAL(38,0) bietet exakte ganzzahlige Faktoren ohne Float; strict mode und
zukünftiger Preflight müssen zusätzlich nichtganzzahlige Eingaben vor einer
möglichen MySQL-Rundung ablehnen.

## Route und Marktdaten

Alle vier Tabellen erhalten diese nullable Spalten ohne fachlichen Default:

| Spalte | SQL-Typ |
|---|---|
| unit_contract_version | VARCHAR(64), binäre Kollation |
| quote_unit_key | VARCHAR(64), binäre Kollation |
| quote_unit_version | INT UNSIGNED |
| quantity_basis_unit_key | VARCHAR(64), binäre Kollation |
| quantity_basis_unit_version | INT UNSIGNED |
| quantity_basis_amount | DECIMAL(32,8) |
| volume_unit_key | VARCHAR(64), binäre Kollation |
| volume_unit_version | INT UNSIGNED |

Bei **Current** heißen die beiden letzten Felder ausdrücklich
`day_volume_unit_key/version`; sie gehören zu `day_volume`, nicht zur Preiseinheit.
DECIMAL(32,8) legt Skala 8 verbindlich fest, mit 24 ganzzahligen Stellen. Die
Mengenbasis ist entweder vollständig NULL oder key/version/amount vollständig
belegt und amount > 0. Werte mit mehr als acht Nachkommastellen muss ein späterer
Writer vor SQL ablehnen. Ein Schema allein garantiert keine verlustfreie Eingabe.

Je Tabelle existieren drei explizite Dreispalten-Stützindizes und echte FKs für
Quote, Quantity und Volume auf `m2_units(unit_key, unit_version,
unit_contract_version)`, alle ON DELETE RESTRICT. Version 0 oder eine unbekannte
Definition bzw. ein abweichender Vertrag scheitert bei vollständiger Referenz am
FK. Teilweise NULL-FKs könnten MySQL umgehen; lokale CHECKs verhindern dies.

### Routenrevision

`m2_asset_source_routes.route_revision INT UNSIGNED NOT NULL DEFAULT 1` mit
CHECK > 0 führt bestehende Routen später deterministisch als Revision 1 ein.
IDs, external_key und route_type bleiben unverändert. Keine Route wird erzeugt.
Die nullable Unitspalten bleiben bei Legacyrouten vollständig NULL.
Unit-aware Routen verlangen Vertrag und vollständiges Quote-Paar; Quantity und
Volume bleiben optional, jeweils vollständig oder NULL.

Im **selben** ALTER werden zuerst die neuen UNIQUEs deklariert und die alten
ersetzt; es gibt keinen separaten ungeschützten DROP-Schritt:

| alter UNIQUE | neuer UNIQUE | Spalten danach |
|---|---|---|
| uq_routes_external | uq_routes_external_revision | source_id, route_type, external_key, route_revision |
| uq_routes_asset_source | uq_routes_asset_source_revision | asset_id, source_id, route_type, route_revision |

Beide behalten die bisherigen FK-Stützpräfixe. Eine zukünftige Unitänderung
erfordert neue physische Route-ID und neue positive Revision, niemals eine
Änderung der benutzten Bindung. Lückenlose Revisionen, konkurrierende Vergabe,
Unveränderlichkeit und gleiche Semantik je Revision sind zukünftige Writerregeln.

### Observations, Current und Bars

Observations erhalten zusätzlich `observation_format_version SMALLINT UNSIGNED
NULL`. Legacy: alle neun neuen Felder NULL und currency weiterhin vorhanden.
Unit-aware: format exakt 2, Vertrag und vollständiges Quote-Paar erforderlich.
Das implementiert **keine** v2-Kanonisierung oder Schreibfunktion.

Current und Bars benötigen keine redundante Formatspalte:
`unit_contract_version IS NULL` kennzeichnet Legacy, zusammen mit sämtlichen
neuen Feldern NULL. Ein belegter Vertrag verlangt vollständige Quote-Bindung.
Current-PK `asset_id` und Bar-UNIQUE
`(asset_id, route_id, interval_key, starts_at)` bleiben identisch. Bars besitzen
genau eine gemeinsame Quote-/Mengenbasis für OHLC, keine Unit je Einzelpreis.
Keine Routenauswahl, Sessions, Endzeiten, Adjustments oder Barrevisionen ergänzt.

`currency CHAR(3)` wird in allen drei Faktentabellen physisch nullable, jeweils
im selben ALTER wie der Legacy-CHECK. Legacy verlangt weiterhin currency NOT
NULL. Damit bleiben auch bereits vorhandene Current-/Barzeilen zulässig; ein
leerer Bestand ist keine Voraussetzung. Unit-aware POINT darf currency NULL
haben. Die fachliche Regel monetary ⇒ currency exakt Katalogwährung und
nonmonetary ⇒ currency NULL bleibt zwingender zukünftiger Cross-Table-Guard.

Für unit-aware Fakten gilt: Volumen NULL ⇒ beide Volume-Unitfelder NULL;
Volumen vorhanden (auch 0) ⇒ beide vollständig. Für Legacy darf vorhandenes
Volumen ohne neue Unitreferenz bleiben. Der Legacy-Zustandscheck erzwingt dort
dennoch sämtliche neuen Felder NULL. Keine historische Einheit wird behauptet.

Alle 18 neuen CHECKs schließen mit `IS TRUE`: MySQL akzeptiert gewöhnlich auch
UNKNOWN. Die explizite Wahrheitsprüfung verhindert NULL-Schlupflöcher.
[MySQL CHECK-Regeln](https://dev.mysql.com/doc/refman/8.0/en/create-table-check-constraints.html).
Für das genaue Zielrelease wurde zusätzlich der
[MySQL-8.0.26-DDL-Code](https://github.com/mysql/mysql-server/blob/mysql-8.0.26/sql/sql_table.cc#L6060)
geprüft: CHECK-Spalten sind mit den gewählten RESTRICT-FKs vereinbar; die dort
verbotenen SET-NULL-/SET-DEFAULT-/UPDATE-CASCADE-Aktionen werden nicht verwendet.

## Bewusst verbleibende Anwendungsguards

SQL-CHECKs können keine Katalogabfragen oder Unveränderlichkeit beweisen.
Ein späterer Seed-/Preflight-/Writervertrag muss deshalb vor jedem Write prüfen:

- kanonische Schlüssel/Dimensionen, freigegebene Vertragsversion und Währung;
- rationale Faktoren ganzzahlig, positiv und vollständig gekürzt (ggT = 1);
- direkte Basiswurzel, gleiche Dimension/Geldwährung, Basisfaktor 1/1,
  keine Zyklen oder Ketten als versteckte Umrechnung;
- authentische Definition mit geprüftem SHA-256, UTC-Zeit und immutable/frozen
  nach Nutzung; kein Update/Delete einer benutzten Definition oder Routenbindung;
- Route und Datensatz haben exakt gleiche Unit-/Mengenbasis-/Volumenbindung,
  currency stimmt mit der Definition überein; Current übernimmt die Observation;
- v1/v2-Dispatcher, Skala und zukünftige v2-Kanonisierung separat implementiert.

Die Self-FK beweist Existenz und Vertragsgleichheit, nicht Dimensionskompatibilität.
`frozen` ist ein erlaubter gespeicherter Zustand, kein UPDATE-Verbot.
GBX@1 ⇒ GBP@1, exakt 1/100, und POINT ohne Währung sind hier ausschließlich
synthetische Testvektoren; keine normativen Seeds und keine echte B8-Zeile.

## Späterer Apply: eigenes Issue und ausdrückliche Freigabe

Vor einem späteren Versuch sind isoliertes Ziel, MySQL-Version, strict/UTC,
Backup/Restorefähigkeit, Schreibpause und **exakte** 0001/0002-Struktur samt Ledger
zu prüfen. Kein vorhandenes m2_units, keine partiellen 0003-Spalten/Constraints.
Legacyidentitäten, Dedupe-Keys, Währungen und vorhandene Volumen vorab sichern.
Routen müssen vor dem ALTER die bisherigen beiden UNIQUEs erfüllen; die
projektierten Revision-1-Schlüssel müssen konfliktfrei sein. Vorhandene
route_revision oder andere Abweichungen führen zum Abbruch, nicht zu Reparatur.
Nach dem Routen-ALTER jede bestehende ID/external_key/route_type unverändert und
Revision exakt 1 nachweisen, alle Unitspalten NULL. Faktentabellen analog mit
unveränderten nativen Werten und Keys nachprüfen.

Die fünf InnoDB-DDL-Statements sind **einzeln atomar**, nicht gemeinsam
rollbackbar; DDL verursacht implizite Commits.
[MySQL Atomic DDL](https://dev.mysql.com/doc/refman/8.0/en/atomic-ddl.html).
Keine ALGORITHM-/LOCK-Zusage und kein Null-Downtime-Versprechen. Bei einem Fehler
sofort stoppen, Teilzustand sichern und gesondert bewerten; kein blindes Retry,
kein IF-EXISTS-Maskieren und kein automatischer destruktiver Rückbau.
0003 schreibt selbst keinen Ledger. Eine spätere Freigabe darf Version 3 erst
nach vollständigem Apply/Postcheck separat protokollieren.

Die vorhandenen v1-Postchecks und deren PHP-CHECK-Auswerter bleiben unverändert;
sie sind noch **kein** 0003-Runner. Composite-FKs, ALTER und IS-NULL/IS-TRUE müssen
für einen späteren Live-Preflight/Postcheck separat unterstützt und geprüft werden.

## Offline-Nachweis und Status

`tests/market_units_schema_fixture.py` konsumiert jede DDL-Klausel, prüft
Typen/Kollationen, zusammengesetzte Ziel-UNIQUEs und explizite FK-Stützindizes.
Ein unabhängiges SQL-Dreifachlogikmodell wertet die tatsächlichen neuen
CHECK-Ausdrücke aus. `tests/test_market_units_schema_phase3.py` prüft vollständige
NULL-Kombinationen, Legacy mit Volumen, currency-Schutz, Format/Quote, Quantity,
Revision, synthetische Katalogfälle sowie defekte DDL-/CHECK-Mutationen.
Byte-Schutz umfasst 0001/0002, v1-PHP, bestehende Phase-3C-Tests und Homepage.
Dies ist statische Syntaxplausibilität und Vertragsregression, **kein MySQL-Apply**.

Lokale Gesamtsuite: **232/233 bestanden**, ausschließlich der bekannte
Windows-Fall `budget_not_private` weicht ab; alle 16 neuen Schema-Tests bestehen.
`python scripts/deploy_sftp.py validate` und `git diff --check` erfolgreich.
Linux-Nachweis des Abschlusscommits mit vollständiger Suite, Validator und
Diff-Prüfung sowie Run-ID wird im Abschlusskommentar zu Issue #25 festgehalten;
der bestehende Workflow läuft dafür ausschließlich auf einem temporären Prüfbranch.

Rechnerischer Stand nach später vollständig erfolgreichem Apply:
**17 Tabellen, 186 Spalten, 17 PK, 10 weitere UNIQUEs, 39 nicht-eindeutige Indizes,
36 FKs, 37 CHECKs**; Ledger erst nach gesondertem Abschluss v3.
Historisch dokumentierter Teststand bleibt 16 Tabellen / Ledger v1+v2 / acht
Observations, Current/Bars 0; in diesem Auftrag nicht live gelesen.
Observation-v1, seine zehn kanonischen Felder und Dedupe-Keys bleiben byteidentisch;
kein Rehash, Backfill oder Import. Writer-v2 fehlt weiterhin.
B8 bleibt bis Apply, qualifizierten Seeds, Writer-v2 und spezifischem
Identitäts-/Evidenznachweis gesperrt; B5/B6/B7 behalten ihre weiteren Sperren.
Alle acht gesperrten Fälle bleiben gesperrt. Homepage und Ladezeitanzeige
unverändert, keine Produktion.
