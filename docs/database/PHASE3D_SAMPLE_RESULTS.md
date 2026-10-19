# Phase 3D-B – echte Read-only-Stichprobe

**Stand:** 19.10.2026. Fachlicher Offline-Nachweis auf einer privat eingefrorenen
Stichprobe; kein Import. Ausgangspunkt `d5eb41c63fb60b8afc4256b12df0508c720a25f1`.
Quelllogik unverändert auf fixlab
`baa0f66d6b40105d6b030c6d1b81239ad6a6fc8c`.
Die produktiv installierten PHP-Dateien wurden hier nicht unabhängig gehasht.

## Auswahl und Beweisgrenze

Bestehende angemeldete MOSA-Ansicht zuerst gelesen, danach Plesk-SSO und
phpMyAdmin ausschließlich für geprüfte einzelne SELECT-Abfragen verwendet.
Keine Passworteingabe, kein Reset, kein Collector/Scheduler und kein Upload.
MOSA-2-Datenbank: **keine Verbindung**, kein Zielkatalog gelesen oder angelegt.
Der zuletzt belegte Zielzustand aus Phase 3C ist ausschließlich Kontext.

Die SQL-Auswahl verwendet eine zuvor ermittelte feste obere PK-Grenze, ein
festes Fenster von höchstens 100.000 IDs, stabile Sortierung und LIMIT je
Familie. Acht initiale Strata sind auf je zwei Objekte beschränkt; hinzu kommen
ein bereits in der Leseansicht beobachteter XXX-Datensatz mit fester ID und
eine native NOK-Snapshotquote aus demselben Fenster. Maximal 18 mögliche,
**16 tatsächlich ausgewählte Quellobjekte / 16 Zielkandidaten**, keine Expansion
nach weiteren Assets. Eine erneute identische Auswahl ergab bytegleiche
Quellobjekte. Alle von diesem Auftrag ausgeführten Quellabfragen waren SELECT;
keine Quelländerung. Laufende unabhängige Collector-Append-Vorgänge wurden
weder gestoppt noch als unveränderter Gesamtbestand behauptet.

Private Dateien außerhalb des Git-Repositories enthalten feste Grenzen,
Auswahl-SQL, echte Quellreferenzen, Snapshotzeit, Quellfingerprints, Versions-
und Zeitzonendaten sowie vollständige Reports. Keine Realzeilen, Kennungen,
Depotinhalte, Benutzer-IDs, Secrets oder privaten Serverpfade werden hier
veröffentlicht. Die beiläufig sichtbare Anzeigehistorie ist kein zusätzlicher
Dry-Run-Datenbestand. Keine vollständige Historie oder Payloadarchive extrahiert.

| Stratum | Quellobjekte | Fachlich transformierbar | Finale Aktion unresolved |
| --- | ---: | ---: | ---: |
| L&S Live-Mid | 2 | 2 | 2 |
| Tradegate Live-Mid | 2 | 2 | 2 |
| Yahoo Snapshot | 2 | 1 | 2 |
| Native Yahoo NOK-Snapshotquote | 1 | 1 | 1 |
| Frankfurt Snapshot | 2 | 2 | 2 |
| Yahoo Chart / GBX-OHLC | 2 | 0 | 2 |
| Abgeleitete EUR-Quotes / FX | 2 | 0 | 2 |
| Yahoo Future-Indikatoren | 2 | 0 | 2 |
| Tradegate Indikator / XXX-Punkte | 1 | 0 | 1 |
| **Gesamt** | **16** | **8** | **16** |

L&S-Chart lieferte im festgelegten Fenster keinen Treffer. Frankfurt-History
und NEL-JSON-Punkte sind **nicht in dieser Stichprobe beobachtet/extrahiert**;
ihre Verfügbarkeit oder Importfähigkeit ist damit nicht widerlegt oder gelöst.
Es wurde keine Suche durch größere Datenbestände zur Erzwingung dieser Fälle
unternommen. Der frühere Quellenvertrag bleibt dafür offen.

## Identität, Route und Zeit

- **13/16** Zeilen haben eine prüfziffergültige ISIN: acht unterschiedliche
  vorgeschlagene Asset-Schlüssel, keine erfundene MOSA-2-ID. Drei Indikatoren
  haben keinen für dieses Ziel bestätigten Asset-Identifier. Kein Konflikt
  beobachtet, WKN-Belege nicht in der Stichprobe vorhanden.
- 14 ursprüngliche Zeilen wurden zusätzlich über exakt Run + Asset + Source +
  Provider mit ihren Attempts verknüpft: jeweils genau ein Treffer; vorhandene
  ISINs stimmen überein. Zwei ergänzte Objekte verwenden den belegten
  Quellzeilen-/Producer-Kontext; dafür kein zusätzlicher Registry-Join.
- Vier vorgeschlagene Sources; 13 Zeilen mit zwölf unterschiedlichen
  vorgeschlagenen Routes. L&S enthält eindeutige Instrument-/Marktkennung,
  Yahoo Symbol + Exchange, Tradegate venuebezogene ISIN. Frankfurt hat eine
  vorgeschlagene venuebezogene ISIN-Route; ein separater MIC-/Registry-Nachweis
  ist hier nicht enthalten. Das sind **Vorschläge**, keine bestehenden Zielroutes.
  Provider, Venue, Währung, Variante, Series und Art bleiben getrennt; keine
  Asset-Sonderroute und keine Cross-Source-Arbitration.
- 16 gespeicherte Markt- und Erfassungszeiten gegen den dokumentierten
  Producer-Vertrag geprüft: bereits normalisierte UTC-SQL-Mikrosekunden.
  L&S-/Tradegate-Lokalzeit wird im Producer vor Persistenz konvertiert, Yahoo
  Epoch und Frankfurt ISO im gemeinsamen Bundle. Kein zweites Verschieben.
  Die Leseansicht bestätigt beim XXX-Objekt zusätzlich explizite UTC-Offsets.
  Keine originale Providerzeit oder historische DST-Konversion erneut
  abgespielt; dieser Nachweis betrifft die gespeicherte UTC-Vertragssemantik.

## Werte, Einheiten und gesperrte Fälle

| Quellwährung | Anzahl |
| --- | ---: |
| EUR | 8 |
| NOK | 1 |
| DKK | 1 |
| GBX | 3 |
| USD | 2 |
| XXX | 1 |

13 Kandidaten gehören zur Klasse Währung pro Instrument; dazu ein Punkte-
und zwei Rohstoff-/Future-Referenzwerte. GBX ist tatsächlich vorhanden, ein
eigenständiger Skalierungsbeleg fehlt in diesen Quellobjekten: alle drei bleiben
gesperrt. Keine automatische GBP-Umrechnung. XXX bezeichnet im beobachteten
Fall ausdrücklich Punkte und keine Geldwährung. Auch USD bei Future-Referenzen
beweist keinen vollständigen Kontrakt-/Roll- oder Assetvertrag.

Die beiden EUR-Ableitungen enthalten native Währung/Preis, FX-Symbol/-Rate,
zwei Marktzeiten und native Fingerprints; jeweils fehlt der FX-Payloadfingerprint
und eine getrennte FX-Erfassungszeit. Keine Archive nachgeladen und keine
vollständige Input-Reproduktion behauptet. Der generische Evaluator bleibt für
Derived-Quotes konservativ gesperrt, auch bei nur ausgefüllten Lineage-Feldern;
ein exakter Reproduktionsadapter ist hier nicht implementiert.

Zwei Yahoo-OHLC-Kandidaten haben **kein belegtes kanonisches Intervall, Ende,
Adjustierungs-/Revisionsmodell**. Einer enthält zudem einen nicht glatt
gerasterten Startzeitpunkt; daraus wird kein Intervall geraten. Keine Endzeit,
OHLC aus Punktreihen oder Bar-Importfähigkeit erfunden.

Kumuliertes Snapshotvolumen und Umsatz werden nicht als Punkt-Stückvolumen
übernommen. Bei den acht fachlich gültigen Observations bleiben Preis/Bid/Ask,
native Währung und beide UTC-Zeitpunkte erhalten; Dezimalstrings werden ohne
zusätzlichen Float-Roundtrip kanonisiert. Tages-/Provider-Zusatzstatistik bekommt
keine neue Zielspalte. Kein Legacy-is_selected wird als Current-Freigabe genutzt.

| Reason-Code (mehrere je Kandidat möglich) | Anzahl |
| --- | ---: |
| current_route_unselected | 14 |
| target_snapshot_missing | 8 |
| asset_identity_missing | 3 |
| route_unresolved | 3 |
| unit_contract_unresolved | 3 |
| unit_scale_required | 3 |
| adjustment_unknown | 2 |
| bar_end_unknown | 2 |
| interval_unknown | 2 |
| derived_provenance_unresolved | 2 |
| unit_or_currency_missing | 1 |

**Summen:** 14 Observation-/2 Bar-Kandidaten; Current ja 0, nein 2 (Bars),
unresolved 14. Transformierbar 8; insert 0, duplicate 0, reject 0, unresolved 16.
Die Erhaltungssumme ist 16 = 0 + 0 + 0 + 16. Reason-Summen sind Mehrfachzählungen.
Die übrigen acht sind fachlich gesperrt; bei den acht gültigen fehlt nur der
Zielvergleich für eine endgültige History-Aktion. Current bleibt separat offen.

## Offline-Vertrag und Reproduzierbarkeit

`scripts/phase3d/dry_run.php` liest genau einen bereits privat extrahierten
Snapshot (höchstens 30 Kandidaten, 1 MiB), stellt keine DB-/Netzverbindung her
und schreibt weder Quelle noch Ziel. CLI-Ausgabe geht auf stdout. Evidence-
Annotationen sind vorab geprüfte Belege, kein automatischer Wahrheitsnachweis;
ein beliebig selbst beschrifteter Snapshot ist keine Importfreigabe.

Die gemeinsame Phase-3C-Wertenormalisierung wurde ohne Änderung ihres Formats
extrahiert. Vollständige kanonische Observation und Dedupe verwenden weiterhin
exakt `normalizeObservation` / `canonicalObservation` / `dedupeKey`. Ohne reale
Ziel-IDs bleibt der private Dedupe-Key **null** statt eines Hashs erfundener IDs.
Mit eingefrorenem bestätigtem Offline-Katalog liefert er denselben Hex-Key;
dies ist synthetisch getestet. Dieser Dry-Run-Pfad behauptet generell keine
insert-/duplicate-Aktion und besitzt keinen schreibenden Adapter.

Zwei Läufe mit identischem privatem Snapshot und Manifest liefern nach
kanonischer Sortierung bytegleiche Ergebnisdaten, Reasons, Summen und
Report-Fingerprint. Der Fingerprint hasht den kanonischen Report ohne sein
eigenes Fingerprintfeld; die finale Datei besitzt zusätzlich einen privaten
Dateifingerprint. Keine Systemzeit fließt in die Ausgabe ein.

## Prüfungen und Abschluss

26 neue synthetische Tests bestanden im korrigierten Workspace-Tempverzeichnis.
Gesamtsuite lokal **168/169**, ausschließlich bekannter Windows/POSIX-Fall
`budget_not_private`. Ein erster neuer CLI-Testlauf scheiterte zusätzlich am
Sandbox-Tempverzeichnis; nach Korrektur der Laufumgebung bestanden alle neuen
Tests. Deploy-Dateivalidierung, Diff-Prüfung und beide PHP-Lints bestanden.
Migrationen 0001/0002 sind bytegleich. Keine Tests abgeschwächt.

Linux-Nachweis des exakten Abschlusscommits, Run-ID, Deploy skipped und gelöschter
Prüfbranch werden nach Ausführung in Issue #16 dokumentiert. Ein bestandenes
Read-only-Sample ist keine Freigabe für einen Import oder Produktion.
KI-Kontrollzentrum separat: nativer Start `PROMPT_RECEIPT_MISSING`, Describe/Plan
jeweils `Invalid laboratory identity`; keine Zuordnung rekonstruiert.
