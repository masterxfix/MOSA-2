# Phase 3H – acht gesperrte Marktdatenfälle

**Stand 19.10.2026:** Ausschließlich Offline-Analyse auf `f4ac6be`, Issue #23.
Exakt acht gesperrte Kandidaten reproduziert; keiner ist jetzt importierbar.
Keine neue Auswahl, kein Import und keine automatische Entsperrung.
Phase 3D-G hat die anderen **8/8 ursprünglich transformierbaren Observations**
über drei idempotente Pakete übernommen. Die Gesamtmigration bleibt offen.

## Nachweis und Zählweise

Der ursprüngliche private Phase-3D-B-Snapshot, beide identischen Dry-Run-Reports,
Report-Selbstfingerprint und sämtliche Snapshot-Dateifingerprints sind unverändert.
Zwei erneute Läufe des unveränderten Offline-Evaluators sind bytegleich mit dem
ursprünglichen Report. Die privaten Phase-3D-G-Abschlussartefakte wurden nur zur
Bestätigung des abgeschlossenen Imports und zum Ausschluss seiner acht
Quellreferenzen verwendet; keine erneute fachliche Analyse dieser Observations.
Die disjunkten Paketmengen enthalten 3 + 3 + 2 Referenzen und entsprechen exakt
den acht ursprünglich transformierbaren Fällen. Mengendifferenz: **16 − 8 = 8**.

B1–B8 folgen stabil der Reihenfolge der verbleibenden Kandidaten im eingefrorenen
Snapshot. Die private Matrix außerhalb Git bindet jede Kennung an Quellreferenz,
Originalobjekt, Zeilen-/Objektfingerprint, Evidence und vollständige Blockerliste.
Sie enthält auch Provider, Series, Quotevariante, native Währung/Einheit,
Identitäts-/Source-/Routestatus, Zeit-/Wertsemantik und minimal fehlende Evidenz.
`importable_now = false` gilt ausnahmslos. Keine realen Identitäten oder Einzelwerte
werden in dieser Dokumentation veröffentlicht.

| Disjunkte Hauptfamilie | Kandidaten | Anzahl |
| --- | --- | ---: |
| Derived-/FX-Ableitungen | B1, B2 | 2 |
| Rohstoff-/Future-Referenzen | B3, B4 | 2 |
| Index-/Punkteindikator | B5 | 1 |
| Native OHLCV-Bars | B6, B7 | 2 |
| Native Snapshotquote mit Preisuntereinheit | B8 | 1 |
| Gesamt | B1–B8 | 8 |

**GBX überlappt:** B6/B7/B8 sind drei GBX-Fälle; B6/B7 sind zugleich die beiden
Barfälle. Drei GBX + zwei Derived + zwei Bars + drei Indikatoren ergeben deshalb
keine Kandidatensumme. Auch die ursprünglichen Reason-Summen zählen mehrfach.

## Genau eine Hauptklassifikation pro Kandidat

| Klassifikation | Anzahl |
| --- | ---: |
| EXISTING_EVIDENCE_RESOLVABLE | 0 |
| READONLY_EVIDENCE_REQUIRED | 0 |
| TARGET_CONTRACT_REQUIRED | 6 |
| OUT_OF_SCOPE | 2 |
| CONFLICT | 0 |
| Gesamt | 8 |

Ein Fall ist nur A, wenn vorhandene Evidenz **und bestehender allgemeiner
Zielvertrag** genügen; nur B, wenn allein zusätzliche historische Evidenz fehlt.
Bei B1/B2/B5/B6/B7/B8 fehlt bereits ein ausreichend bestimmter Zielvertrag.
Zusätzlicher späterer read-only Evidenzbedarf bleibt dort ein sekundärer Bedarf,
keine zweite Hauptklassifikation. Es wurde kein Evidenzwiderspruch festgestellt;
das beweist keine vollständige Assetidentität, insbesondere bei den Indikatoren.
B3/B4 werden bewusst außerhalb der aktuellen Investment-Quote-Migration geparkt,
bleiben aber im privaten Nachweis erhalten; keine Daten werden gelöscht.

In der letzten Spalte bedeutet **ja***: Schemaerweiterung für die unten empfohlene
allgemeine Modellierung voraussichtlich nötig; noch keine beschlossene Migration.
**Nein** bei geparkten Fällen bedeutet keine Schemaarbeit in diesem Umfang.

| Fall | Fachlicher Typ / Zielkandidat | Primärer Reason-Code | Sekundäre ursprüngliche Reason-Codes | Hauptklasse | Schemaerweiterung? |
| --- | --- | --- | --- | --- | --- |
| B1 | Währungsabgeleitete Quote / native Quote + FX-Rate + Conversion-Beziehung | derived_provenance_unresolved | current_route_unselected | TARGET_CONTRACT_REQUIRED | ja* |
| B2 | Währungsabgeleitete Quote / native Quote + FX-Rate + Conversion-Beziehung | derived_provenance_unresolved | current_route_unselected | TARGET_CONTRACT_REQUIRED | ja* |
| B3 | Rohstoff-Future-Referenz / separates Referenzmodell bei späterer Freigabe | unit_contract_unresolved | asset_identity_missing, route_unresolved, current_route_unselected | OUT_OF_SCOPE | nein |
| B4 | Rohstoff-Future-Referenz / separates Referenzmodell bei späterer Freigabe | unit_contract_unresolved | asset_identity_missing, route_unresolved, current_route_unselected | OUT_OF_SCOPE | nein |
| B5 | Indexstand in Punkten / typisierter Marktindikator | unit_contract_unresolved | asset_identity_missing, route_unresolved, unit_or_currency_missing, current_route_unselected | TARGET_CONTRACT_REQUIRED | ja* |
| B6 | Native GBX-OHLCV-Bar / einheitenbewusste Bar | interval_unknown | adjustment_unknown, bar_end_unknown, unit_scale_required | TARGET_CONTRACT_REQUIRED | ja* |
| B7 | Native GBX-OHLCV-Bar / einheitenbewusste Bar | interval_unknown | adjustment_unknown, bar_end_unknown, unit_scale_required | TARGET_CONTRACT_REQUIRED | ja* |
| B8 | Native GBX-Snapshotquote / einheitenbewusste Observation | unit_scale_required | current_route_unselected | TARGET_CONTRACT_REQUIRED | ja* |

`current_route_unselected` wird als historischer zusätzlicher Reason erhalten,
bleibt aber vollständig außerhalb der History-/Bar-Auflösung. Keine Current-
Arbitration, Prioritätsauswahl oder Current-Freigabe wird hier definiert.

## Historische Quellverträge und Zielgrenze

Quellsemantik ausschließlich auf fixlab
`baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c`, niemals rückwirkend auf aktuellem main:

- [Requestprofile, FX-Route und Derived-Producer](https://github.com/masterxfix/fixlab/blob/baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c/php/mosa_market_collection_runner.php#L30):
  current fordert 1d/1d ohne Pre-/Post-Market, daily 1mo/1d und backfill max/1d
  jeweils mit Dividenden-/Split-Ereignissen; rich fordert 1m/1d. Diese möglichen
  Profile beweisen nicht das tatsächlich verwendete Profil einer historischen Zeile.
- [Yahoo-Normalisierung](https://github.com/masterxfix/fixlab/blob/baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c/php/market_collection_bundle.php#L8):
  GBp/GBX wird als GBX erhalten. timestamp[] wird UTC; O/H/L/C/V wird nach bar_*
  projiziert. Snapshot nutzt regularMarketPrice und regularMarketTime. Der Writer
  übernimmt keine vollständige Chartmeta-, Sitzungs-, AdjustedClose- oder
  Revisionssemantik in die flache Marktzeile. Nicht projiziert bedeutet nicht,
  dass ein ursprünglicher Payload diese Angaben zwingend nicht enthielt.
- [Indikator-Producer](https://github.com/masterxfix/fixlab/blob/baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c/php/mosa_market_indicator_collector.php#L69):
  unit_key, reference_type und currency_supplied bleiben im derivation_json.
  Fehlende Währung wird technisch XXX; ein gespeicherter Dreilettercode allein
  ist deshalb kein Geldwährungsbeleg.

Zielprüfung gegen [Migration 0001](migrations/0001_core_asset_identity.sql),
[Migration 0002](migrations/0002_market_current_history.sql),
[Feldmapping](PHASE3D_FIELD_MAPPING.md) und vorhandenen Phase-3C-Dedupe.
Die Migrationen wurden nur gelesen. Source-/Route-Tupel und zwei UNIQUE-Verträge
bleiben verbindlich; vorhandene numerische IDs oder neue Katalogobjekte werden
hier nicht aufgelöst oder behauptet.

## GBX / allgemeiner Price-Unit-Vertrag – B6, B7, B8

Vorhanden: native Preiseinheit GBX, gültiger Kennungskontext, vorgeschlagener
Source-/Routekontext und gespeicherte UTC-Zeiten; bei B6/B7 OHLCV, bei B8 Snapshot.
Assetname/-klasse und tatsächliche Zielzuordnung sind dadurch noch nicht freigegeben.
Der historische FX-Producer verwendet GBPEUR mit rate_scale 0.01: Das trennt einen
Pence-Skalierungsschritt vom anschließenden Wechselkurs. Es ist keine bestehende
allgemeine Freigabe einer GBX→GBP-Zielnormalisierung.

| Allgemeine Option | Erhaltung / Vergleichbarkeit | Reproduzierbarkeit und Dedupe / Route |
| --- | --- | --- |
| Native Zahl + explizite quote_unit | Native Präzision und Einheit bleiben erhalten; Vergleich braucht Einheitenabgleich | Einheit und Vertragsversion müssen an Payload/Route gebunden sein; bisheriger Zehn-Felder-Key darf nicht still neu interpretiert werden |
| GBP-normalisierte Zahl, exakter scale_factor 0.01 | Vergleich in GBP einfach; native Zahl/Einheit gehen ohne unveränderliche Originalprovenienz verloren | Exakte Dezimal-/Rationalarithmetik, Präzisions-/Rundungsgrenzen und Originalfingerprint nötig; separate normalisierte Route, kein FX-Fetch für reine Einheitenskalierung |
| Allgemeines Quantity-/Unit-Modell | Auch andere Untereinheiten, Punkte und Preise pro Mengeneinheit konsistent | Versionierter Einheitenkatalog mit Basisdimension, Bezugsgröße und rationalem Faktor; höhere Modellkosten, höchste Wiederverwendbarkeit |

**Empfehlung:** universeller Quantity-/Quote-Unit-Vertrag mit nativer Zahl,
expliziter Einheit, Geldwährung nur soweit fachlich vorhanden, Bezugsgröße und
exaktem rationalem Skalenfaktor. Eine GBP-Normalisierung wäre eine ausdrücklich
abgeleitete, versionierte Sicht, keine zweite native Beobachtung. Derselbe Vertrag
muss History, spätere Current-Projektion und Bars abdecken. Native und normalisierte
Semantik nicht unter identischer Source-/Routeidentität mischen; zwei UNIQUEs
beachten und bei Kollision vor jeder Anlage stoppen.

Observation/Current/Bar besitzen derzeit currency, aber keine eigenständige
quote_unit, Bezugsgröße oder versionierte Unit-Provenienz. GBX einfach als currency
zuzulassen oder einen Faktor in ein Provider-Sonderfeld zu schreiben löst das
nicht. Daher alle drei Fälle C, Schemaerweiterung für die empfohlene native
Erhaltung voraussichtlich nötig. Eine bewusst eingeschränkte GBP-only-Alternative
könnte bestehende Preisfelder nutzen, braucht aber zuerst einen genehmigten
allgemeinen Normalisierungs-/Auditvertrag; sie ist aktuell ebenfalls nicht A/B.
Keine automatische Skalierung und keine Änderung des bestehenden Dedupe-Formats.

## Derived / FX – B1 und B2

Bei beiden separat vorhanden: native Inputzahl/-währung, FX-Symbol und Rate,
beide Input-Marktzeiten, native Fingerprints und eingefrorener EUR-Ausgabewert.
Bei beiden fehlen vollständiger FX-Payloadfingerprint und eigenständiges
FX-observed_at. Die zwei Fälle sind über eigene private Zeilenfingerprints und
Inputreferenzen gebunden, keine aus der Reason-Summe erfundene Verdopplung.
Der historische Producer multipliziert über Float-/Decimal-Formatierung und setzt
die Ausgabe-Marktzeit auf das Minimum beider Input-Marktzeiten; die gespeicherte
Abrufzeit stammt vom nativen Input. Das ersetzt keinen zweiten Erfassungsbeleg.

**Ziel:** native Marktquote, eigenständige FX-Beobachtung mit eindeutig gerichtetem
Währungspaar und eine deterministische Conversion-Beziehung mit Input-/Output-
Referenzen, beiden Markt-/Erfassungszeiten, Payloadfingerprints, Formelversion,
Einheitenskalierung und definierter Dezimal-/Rundungspolitik. Historisch gerundete
Werte erhalten; keine zusätzliche Genauigkeit erfinden. Die spätere Reproduktion
muss die alte Formel exakt erklären oder einen Konflikt melden. Heutige FX-Kurse
können fehlende historische Inputs nicht ersetzen.

Die Observation-Tabelle hat nur einen Source-/Routebezug und ein Zeitpaar;
Sources/Routes beschreiben keinen vollständigen Inputgraph. m2_relationships
verknüpft Entities, keine Observation-/FX-Zeilen; m2_events.metadata_json könnte
JSON aufnehmen, besitzt aber keinen definierten typisierten Provenienz-, FK-,
Versions- und Dedupe-Vertrag für diesen Graphen. Beliebiges JSON ist kein Beweis
bestehender Zielunterstützung. Beide Fälle C; ein neuer allgemeiner Lineage-/
Conversion-Vertrag und voraussichtlich typisierte persistente Referenzen nötig.

Minimal später read-only: ausschließlich exakt zugehörige historische FX-Inputs
und Archive anhand der eingefrorenen Run-/Source-/Payloadbezüge suchen, einschließlich
Abrufzeit und Payloadhash. Fehlender historischer Beleg bleibt fehlend; keine
Ersetzung durch einen neuen Providerabruf und keine native EUR-Assetroute.

## OHLCV / universeller Barvertrag – B6 und B7

Beide flachen Zeilen enthalten O/H/L/C/V und native Einheit, aber keinen vollständig
belegten Intervall-/End-/Adjustierungsvertrag. B6 liegt auf einer Minutengrenze;
das beweist allein kein Intervall. B7 liegt nicht auf einer glatten Minutengrenze;
das ist eine zusätzliche Diagnose, kein Grund zum Runden oder Verschieben.
Bei beiden: series=chart beweist weder daily noch den konkreten Request.

Erforderlicher allgemeiner Vertrag:

- interval_key aus belegtem Request **und** konsistenter Chartmeta; nur aktuell
  zulässige Zielintervalle, sonst weiter gesperrt;
- starts_at aus belegter Timestamp-/Bar-Startsemantik, ends_at aus belegter
  Sitzung/Intervallgrenze einschließlich möglicher unvollständiger letzter Bar;
- session_basis, Zeitzone und versionierter Sitzungskalender; kein geratenes
  starts_at + ein Tag und kein aus Exchange-Symbolen erfundener Kalender;
- explizite adjusted/unadjusted-Basis, gegebenenfalls belegte Adjustierungsserie;
  vorhandene quote-Close-Felder nicht ungeprüft mit adjustedClose gleichsetzen;
- volume_basis/Einheit: Stück-/Kontraktvolumen für genau dieses Intervall,
  kein kumulierter Snapshotumsatz;
- Revision: zunächst identischer Payload duplicate, gleicher Bar-Schlüssel mit
  anderem Payload Konflikt; keine stillen Updates. Ein späteres Revisionsmodell
  braucht unveränderliche Versionen, Erfassungszeit und nachvollziehbare Auswahl.

m2_market_bars kann Intervall, Start/Ende und OHLCV speichern. Session-/Timezone-,
Unit-, Adjustment- und Revisionsprovenienz fehlen als ausreichend definierter
allgemeiner Zielvertrag; insbesondere die native GBX-Einheit ist nicht getrennt
abbildbar. Deshalb beide C mit zusätzlichem read-only Bedarf, nicht allein B.

Minimal später: je Kandidat nur exakt historischen Request-/Archivbezug und
notwendige Chartmeta (dataGranularity, Exchange/Timezone, trading periods,
Adjustment-/Sessionbeleg) prüfen; vollständigen Chart nicht neu abrufen. Ob diese
historischen Belege überhaupt noch verfügbar sind, ist offen. Anschließend
separat Assetname/-klasse belegen. Fehlende End-/Adjustierungsevidenz sperrt weiter.

## Index / XXX / Futures – B3, B4, B5

B5 ist durch gespeicherte unit_key=points, reference_type=index_reference und
currency_supplied=false als Punkteindikator belegt. XXX ist hier keine reale
Währung. Korrektes Ziel wäre ein typisierter Indexindikator mit stabiler,
providerunabhängiger Referenzidentität und expliziter Punkteeinheit; kein
Equity-/ETF-Default und keine tickerbasierte Identität. Indexklasse und gesicherter
Kennungsscope sowie Source-/Routevertrag sind zusätzlich erforderlich. C; der
allgemeine Unit-Vertrag nutzt auch Indizes und andere nichtmonetäre Messwerte.
Späterer read-only Bedarf: eng begrenzter Referenz-/Identitätsbeleg, kein neuer Kurs.

B3 und B4 sind jeweils als future_reference mit unterschiedlichen monetären
Mengeneinheiten belegt. Das beweist weder einen bestimmten lieferbaren Kontrakt
noch eine kontinuierliche Rollserie. Beiden fehlen bestätigte Identifier,
Verfall/Liefermonat, Kontrakt-/Notierungsbezugsgröße sowie Roll-/Adjustierungs-
semantik. USD allein löst dies nicht. **Bewusst OUT_OF_SCOPE** für die aktuelle
Investment-Quote-Migration: kein handelbarer Future wird daraus erfunden.
Falls später separat aufgenommen, zuerst allgemeiner Referenz-/Future-Vertrag
für endliche Kontrakte versus kontinuierliche Reihen; dann gezielter read-only
Identitäts-/Rollbeleg. Dafür heute weder Evidenzabruf noch Schemaänderung.

## Empfohlene Reihenfolge und Schemaentscheidung

1. **Priorität 1 – vorhandene Evidenz und bestehender Vertrag:** aktuell kein Fall.
2. **Priorität 2 – allein read-only Evidenz:** aktuell kein Fall. Der zusätzliche
   Evidenzbedarf der C-Fälle macht ihre fehlenden Zielverträge nicht überflüssig.
3. **Priorität 3 – neue allgemeine Verträge:** zuerst Unit-/Quantity-Konzept am
   einfachen Snapshotfall B8 entscheiden, ohne Datenfreigabe. Es ist Voraussetzung
   auch für B6/B7 und B5. Danach Bar-Semantik/Metadaten B6/B7 und FX-Lineage B1/B2
   als getrennte kleine Vertragsentscheidungen; den komplexeren Inputgraph erst
   mit definierten Einheiten/Dezimalregeln konkretisieren. B5 anschließend als
   gesonderten Indikatorvertrag entscheiden. Erst nach dem jeweils festgelegten
   Vertrag gezielte historische read-only Nachweise, dann neue Offline-Prüfung.
4. **Priorität 4 – bewusst außerhalb:** B3/B4 geparkt lassen; Aufnahme nur mit
   expliziter Umfangsentscheidung und allgemeinem Referenzkontraktvertrag.

Schemaentscheidung: **teilweise voraussichtlich nötig**, keine Migration 0003.
Die sechs C-Fälle benötigen allgemeine Attribute/Referenzen für Einheit,
Dimension/Bezugsgröße, Vertrag-/Provenienzversion, Inputgraph beziehungsweise
Bar-Session-/Adjustment-/Revisionsbezug. Die endgültige physische Modellierung
wird erst nach eigener Vertragsfreigabe festgelegt; keine Provider-Sonderfelder,
kein Missbrauch freier JSON-Felder und keine vorweggenommene SQL-Implementierung.
Reine GBP-Normalisierung könnte vorhandene Preisfelder nutzen, beseitigt aber
weder Audit- noch Vertragsbedarf und löst die übrigen Familien nicht universell.

## Prüfung und Ausführungsgrenze

Docs-only; kein neuer Klassifikationsadapter, keine Änderung am Evaluator oder
Importer. Privat geprüft: exakt acht Restfälle, acht importierte ausgeschlossen,
Originalfingerprints, zwei bytegleiche Dry Runs, vollständige Reasons, eine
Hauptklasse je B-Kennung und Erhaltungssummen. Öffentliche Inhalte gegen private
Identitäten/Quellreferenzen und Einzelmarktwerte abgegrenzt.

Vollständige Regressionen, deploy_sftp.py validate und git diff --check werden
auch für diese Dokumentationsänderung ausgeführt; unter Windows ist ausschließlich
der bekannte POSIX-Fall budget_not_private zulässig. Keine geänderte PHP-Datei.
Abschlusscommit, exakter Linux-Run und übersprungener Produktionsjob werden in
Issue #23 dokumentiert; temporärer Prüfbranch wird anschließend entfernt.

Keine DB-Verbindung, kein Passwort/Gateway, kein Browser/Dogado/Plesk, kein
Providerabruf, keine Datenänderung, kein Import/DDL und kein Deployment.
Homepage, dynamische Ladezeit und Migrationen 0001/0002 bleiben unverändert.
Der Teststand wird hier nicht neu live geprüft. KI-Kontrollzentrum separat:
Start PROMPT_RECEIPT_MISSING, Describe/Plan jeweils Invalid laboratory identity;
keine Zuordnungen oder Ereignisse erfunden, fachlich wie beauftragt fortgesetzt.
