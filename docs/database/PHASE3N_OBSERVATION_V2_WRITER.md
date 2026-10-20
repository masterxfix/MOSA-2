# Phase 3N – Observation-v2 / unit-aware Writer offline

Issue #30, Ausgangspunkt `296eb2ffb6cb6ecaf81db36d37c70028db29136e`.
Vollständig offline implementiert: Normalisierung, kanonische Bytes, rohe
SHA-256-Keys, qualifizierter Unitkatalog, strikte Routebindung, expliziter
Dispatcher und deterministische Write-Pläne. Keine SQL-Ausführung.

## Machbarkeit und bestehende Verträge

Schema-Version 3 enthält bereits sämtliche benötigten Spalten, FKs und CHECKs
auf Routes und Observations; keine Migration 0004 erforderlich oder erstellt.
Die vier normativen Units sind gemäß abgeschlossenem Phase-3M-Nachweis vorhanden;
dieser Auftrag hat dafür keine neue Live-Abfrage ausgeführt.

Grundlagen: [Phase 3I](PHASE3I_UNIT_CONTRACT.md),
[Phase 3L](PHASE3L_UNIT_SEEDS.md), [Phase 3M](PHASE3M_UNIT_SEEDS_LIVE.md).
Die bestehenden Migrationen und die Homepage sind byteidentisch geblieben.

## Komponenten und Verwendung

- `scripts/phase3n/unit_catalog_adapter.py`: validierter, nach außen nur lesbarer
  Katalog aus dem Phase-3L-Vertrag; verwendet dessen Validator und Projektion.
- `scripts/phase3n/observation_v2.py`: gemeinsame PHP-Wertnormalisierung, Unitbindung,
  feste v2-Feldreihenfolge, kanonische Bytes und 32 rohe Dedupe-Bytes.
- `scripts/phase3n/value_adapter.php`: ausschließlich lokaler Stdio-Adapter auf
  unveränderte Phase-3C-Primitiven. Keine DB, SQL, URL, Credentials oder Uhr.
- `scripts/phase3n/writer_plan.py`: unveränderliche Routensnapshots, Format-/Intent-
  Dispatch, Snapshot-/Replayprüfung und vier Planentscheidungen.

Python-Standardbibliothek und vorhandenes PHP sind die einzigen Laufzeitvoraussetzungen.
Der Adapter startet ausschließlich das lokale PHP-Wertskript; er führt keinen
Shelltext aus. Beispiele vollständig synthetisch in
`tests/test_observation_v2_writer_phase3.py`.

API vom Repository aus:

```python
from scripts.phase3n.writer_plan import WriterPlanner, observation
catalog = observation.catalog_module.normative_catalog()
planner = WriterPlanner(catalog, qualified_route_envelopes, existing_snapshot)
plan = planner.plan(native_observation, format_version=2,
                    intent='NEW_NATIVE_V2', representation='native',
                    created_at=frozen_insert_timestamp)
```

Diese Aufrufe lesen nur lokale Quellen und erzeugen Datenstrukturen. Die API
besitzt keine Apply-/Execute-Funktion. Der Aufrufer darf `db_values` nicht als
Freigabe für einen Live-Insert verstehen. Zeitstempel und Snapshots sind explizite
Inputs, niemals aktuelle Laufzeit oder erfundene Datenbank-IDs.

## v1 bleibt unverändert

`scripts/phase3c/market_flow.php` einschließlich `normalizeObservation`,
`canonicalObservation` und `dedupeKey` ist byteidentisch:
SHA-256 `ab2b9510da0a76b549b587e10db5d768f079b57cd1d4e0d6542b46f805cd33af`.
Alle bisherigen Tests laufen unverändert. Der neue äußere Dispatcher reicht
v1-Replays direkt an diese Funktionen durch; keine Unitauflösung für v1.
Der gespeicherte SQL-Formatmarker bleibt dabei NULL, nicht nachträglich 1.

Acht synthetische Golden-Vektoren wurden aus genau diesem unveränderten
Ausgangscode eingefroren. Tests vergleichen jedes Byte, jeden vorhandenen Key
und das Ergebnis `DUPLICATE_UNCHANGED` bei allen acht Zeilen. Die vorhandene
synthetische Batch-Regression prüft zusätzlich den achtzeiligen Importstand.
Die acht tatsächlichen Live-Zeilen/Keys wurden gemäß Offline-Grenze nicht
ausgelesen oder in Fixtures kopiert. Ihr unveränderter Replay ergibt sich für
identische Inputs aus dem byteidentischen v1-Code; dies ist ausdrücklich keine
neue Live-Messung ihrer privaten Werte. Kein Rehash, Backfill, Upgrade oder Reimport.

## v2-Domain und Normalisierung

Exakt `mosa2-observation-v2` + ein LF + kompaktes UTF-8-JSON, ohne abschließendes LF.
SHA-256 über diese Bytes liefert **32 rohe Bytes**, nicht den 64-Zeichen-Hextext.
Die kanonische Reihenfolge umfasst genau 18 Felder:

1. asset_id
2. source_id
3. route_id
4. currency
5. market_at
6. observed_at
7. price
8. bid
9. ask
10. volume
11. unit_contract_version
12. quote_unit_key
13. quote_unit_version
14. quantity_basis_unit_key
15. quantity_basis_unit_version
16. quantity_basis_amount
17. volume_unit_key
18. volume_unit_version

IDs, UTC-DATETIME(6), DECIMAL(28,10)-Preise und DECIMAL(32,8)-Volumen verwenden
dieselben v1-Primitiven. Preis positiv; bestehende Bid-/Ask-Regel unverändert.
Floats, bools und Exponenten in numerischen Inputs sind verboten. Keine Rundung.
Currency darf für v2 NULL sein; es wird keine Ersatzwährung eingesetzt.

Unitkeys sind kanonische ASCII-Schlüssel, Versionen positive kanonische
Dezimalstrings bis 4294967295, initialer Vertrag exakt `mosa2-market-unit-v1`.
Die Mengenbasis ist vollständig NULL oder ein vollständiges Triple. Ihr Betrag
ist ein positiver Dezimalstring mit höchstens 24 Vor- und 8 Nachkommastellen,
normalisiert auf acht Stellen; auch Menge 1 wird explizit als `1.00000000` gespeichert.
Nichtkanonische Mengenstrings mit Vorzeichen/führenden Nullen werden abgewiesen.
NULL volume verlangt NULL-Unitpaar, non-NULL volume ein vollständiges Unitpaar.

Nur diese 18 Fachfelder sind im v2-Hash. Nicht darin: Formatmarker, created_at,
redundante Dimension/Faktoren, Definitionsevidenz oder Basisprojektionen.
Unbekannte Inputfelder werden abgewiesen, nicht still in eine zweite History
überführt. Der SQL-Formatmarker 2 steht separat im validierten Plan.

## Unitkatalog und Currency

Der Standardkatalog prüft die exakten Manifestdateibytes und den freigegebenen
Paketfingerprint `b66df6f972ad13c05c3f34c604088c0281dcd9f0ff4bafad45b9600aa2b747ee`.
Alle Definitionhashes, Status frozen, Vertrag, Keys/Versionen, Dimension,
Währung, direkte Basis, 1/1-Selbstbasis, gekürzte positive Faktoren und Grenzen
werden durch die unveränderte Phase-3L-Validierung geprüft. Rehash einer geänderten
Definition unter derselben Identität genügt nicht: der getrennte Freigabeanker
passt dann nicht mehr. Katalogauflösung liefert Kopien statt mutierbarer Definitionen.

Der generische Katalog akzeptiert einen anderen Fingerprint nur als ausdrücklich
vom vertrauenswürdigen Aufrufer qualifizierten Offline-Vertrag. Die zusätzlichen
synthetischen Quantity-/Volume-/Versionsdefinitionen der Tests sind keine neuen
normativen oder live freigegebenen Seeds. Der Fingerprint des eingereichten
Manifests darf niemals selbst als seine Freigabe verwendet werden.

Currency muss exakt dem `monetary_currency_code` der Quote-Unit entsprechen.
Damit entstehen EUR/EUR, GBP/GBP, GBX/GBP und POINT/NULL rein aus den Definitionen;
der Writer enthält keinerlei Unit-/Provider-/Asset-Sonderfälle. Kein XXX.
Mengenbasis und Volumeneinheit werden unabhängig aus demselben Katalog aufgelöst.

## Routebindung und expliziter Dispatcher

Ein Routen-Envelope hat `format_version` (1 oder 2) und `route`. Der Wert ist ein
äußerer Writervertrag, keine erfundene SQL-Spalte auf Routes. Die Route enthält
`id, asset_id, source_id, route_revision` und die acht Unitfelder aus Migration 0003.
Route-IDs normalisieren wie v1; die Revision ist positiv. Routensnapshots werden
kopiert und eingefroren. Dieselbe physische ID zweimal zu deklarieren wird
abgelehnt; es gibt keine Routeanlage, Mutation oder neue Revision im Planer.

V2 verlangt vollständige Übereinstimmung der IDs und aller acht Unitfelder.
Route-Currency ist keine SQL-Spalte: die zulässige Currency folgt aus der an
der Route gebundenen Quote-Unit und wird gegen die Observation geprüft.
Keine Interpretation von external_key, route_type oder Providerstrings als Unit.
Vorhandene v2-Facts derselben Route dürfen nicht auf geänderte Asset-/Source-/
Unitsemantik umgedeutet werden. Historische v1-Routen dürfen nicht als v2
deklariert weiterverwendet werden, auch nicht für einen neuen Zeitpunkt.

Zentrale Dispatchentscheidung:

| Explizites Format | Route | Intent | Zulässige Folge |
| --- | --- | --- | --- |
| 1 | Legacy, alle Unitfelder NULL | V1_REPLAY | nur bestehende v1-Dublette; kein neuer Insert |
| 2 | vollständig unit-aware | NEW_NATIVE_V2 | validierter nativer v2-Plan |
| sonst oder Widerspruch | beliebig | beliebig | REJECT |

Keine Currency-Heuristik. Repräsentation muss `native` sein; eine als Derived/
Basisprojektion deklarierte Eingabe wird abgewiesen. Zusätzlich blockiert der
Planer einen neuen Key für ein bereits vorhandenes Factkoordinatentupel
`asset_id, source_id, market_at, observed_at`, auch über eine andere physische
Route oder Domain. Das ist ein konservativer Reimportschutz, keine Auswahl
zwischen Sources/Routes und keine Current-Arbitration. Fehlende/evidenzlos
umdeklarierte Herkunft lässt sich rein offline nicht unabhängig beweisen;
Snapshot und native Herkunft bleiben vom späteren freigegebenen Adapter zu qualifizieren.

## Plan, Duplicate und Conflict

Ein gültiger Plan enthält normalisierte Fachwerte, Formatmarker,
`canonical_bytes`, rohe `dedupe_key`, vollständige erwartete DB-Spalten,
Katalogfingerprint und Routenbindungsnachweis. Bei INSERT zusätzlich `db_values`
einschließlich explizit eingefrorenem created_at; keine automatisch vergebene PK.
Bytes bleiben Bytes in der Python-API, JSON-Ausgabe ist kein zweiter Serialisierer.

- INSERT: neuer valider nativer v2-Fact, lediglich Plan.
- DUPLICATE_UNCHANGED: gleicher Key, gleiches explizites Format und vollständige
  normalisierte fachliche Payloadgleichheit; keine Schreibwerte angewendet.
- CONFLICT: gleicher Key, anderes Format, veränderter/erweiterter Payload.
- REJECT: ungültiger Vertrag, Bindung, Input, Snapshot oder Reimportversuch.

Vorhandene Snapshot-Keys müssen 32 rohe Bytes sein. Für einen neuen Insert
werden vorhandene Payloads normalisiert, ihre Hashes geprüft und Factkoordinaten
verglichen. Gleicher Key mit anderem Payload führt niemals zu UPDATE,
INSERT IGNORE, Reparatur oder Routeanlage. Planen verändert keinen Snapshot.
created_at ist Insertmetadatum und kein Fachwert für die Dublettengleichheit.

## Native Zahlen und exakte Projektion

Gespeichert/geplant wird ausschließlich die native Zahl. Die vorhandene rationale
Phase-3L-Projektion ist ein separater Helper: beispielsweise synthetisch
`123.45` GBX → `1.2345` GBP. Keine Floatrechnung. Keine zweite Observation,
Route, Source oder FX-Observation; keine automatische Projektion im Writer.
Die Präzisions-/Skalengrenzen dieses vorhandenen Helpers bleiben unverändert.

## Tests und Aussagegrenzen

Gezielt: `python -m unittest discover -s tests -p test_observation_v2_writer_phase3.py -v`.
27/27 gezielte Tests bestanden: feste Feldreihenfolge und Golden-
v2-Hash, alle vier normativen Units, explizite Mengenbasis/Volumeneinheit,
Currency, Nullpaare/Triple, numerische Grenzen, Routebindung und Revision,
Katalog-/Definitionmanipulation, Duplicate/Conflict, Domain-/Reimportschutz,
acht v1-Byte-/Hashvektoren, unveränderte v1-/Schema-/Homepagebytes und lokaler
PHP-Adapter ohne Netz-/Persistenzfähigkeit. PHP-Lint ist Teil dieses Blocks.
Gesamte lokale Regression: **347/348**, ausschließlich bekannte Windows-
Abweichung `budget_not_private`; alle bisherigen v1-Tests unverändert grün.
Validator (drei deploybare Webdateien), zusätzlicher PHP-Lint und Diff-Prüfung
bestanden. Eine Deployment-Zeile im Unittest-Log stammt ausschließlich aus
dem Deployment-Mocktest. Es gab kein Deployment.
Der exakte Linux-Nachweis wird nach Durchführung in Issue #30 mit Commit/Run-ID
dokumentiert; Produktionsdeploy bleibt skipped.

Keine DB-Verbindung, Browser-, Dogado-/Plesk-, Gateway-, Passwort-, Provider-,
Live-Insert-, Current-/Bars-, B8- oder Produktionsaktion. Kein echter
Writer-Live-Test und keine Aussage zu Parallelbetrieb oder DB-Transaktionsverhalten.
Phase 3O benötigt eine neue ausdrückliche Freigabe für die isolierte Test-DB.
Erst danach gesonderte B8-Identitäts-/Routequalifikation und eigener Import.

KI-Kontrollzentrum: Start regulär versucht, PROMPT_RECEIPT_MISSING. Describe und
Plan jeweils einmal versucht, ohne verfügbare native Turnzuordnung abgewiesen.
Keine IDs erfunden oder Ereignisse rekonstruiert; Erfassungslücke getrennt vom
fachlichen Ergebnis behandelt.
