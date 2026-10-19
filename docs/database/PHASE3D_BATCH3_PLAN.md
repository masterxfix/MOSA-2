# Phase 3D-F – letztes kleines Paket der geeigneten Stichprobe

**Status:** Am 19.10.2026 ausschließlich offline vorbereitet. Paket 3 enthält die
zwei in Phase 3D-D bereits geeigneten, allein wegen der Paketgrenze zurückgestellten
Kandidaten. Noch nicht importiert. Ein späterer Import benötigt ein eigenes Issue
und eine neue ausdrückliche Nutzerfreigabe.

## Feste Auswahl und Ergebnis

| Eingefrorener Umfang / Planung | Anzahl |
| --- | ---: |
| Ursprüngliche Phase-3D-B-Kandidaten | 16 |
| Ursprünglich fachlich transformierbare Observations | 8 |
| Paket 1 erfolgreich importiert | 3 |
| Paket 2 erfolgreich importiert | 3 |
| Exakt zurückgestellte Restkandidaten reproduziert | 2 |
| Weiterhin vollständig geeignet | 2 |
| Paket-3-Größe (P3-A1/P3-A2) | 2 |
| Assets bestehend / neu | 0 / 2 |
| Sources bestehend / neu (unterschiedliche Katalogobjekte) | 0 / 1 |
| Routes bestehend / neu | 0 / 2 |
| Bedingt geplante Inserts nach Katalogauflösung | 2 |
| Finale Dedupe-Keys bereits bestimmbar | 0 |
| Finale Dedupe-Keys erst nach echter Katalogauflösung | 2 |
| Bestehende migration-v1-Checkpoints fortzuschreiben | 0 |
| Neuer migration-v1-Checkpoint nach Sourceauflösung | 1 |

Keine neue Auswahl aus allen 16 Fällen: Die feste Differenz aus fünf bereits
geeigneten Phase-3D-D-Kandidaten und dem tatsächlich importierten Dreierpaket
reproduziert exakt diese zwei. Gegenprobe gegen die ursprünglichen acht
transformierbaren Fälle und die sechs importierten Referenzen bestätigt die
Zuordnung. Keine Ersatzkandidaten, keine neue Quell- oder Stammdatensuche.
Die ursprünglich acht fachlich gesperrten Fälle bleiben vollständig ausgeschlossen.

## Private Evidence und Zielbasis

Snapshot und Dry Run aus Phase 3D-B, Phase-3D-D-Eligibility und Paket-2-Manifest,
Phase-3D-E-Importmanifest, resolved Manifest und vollständiger Abschlussreport
wurden einschließlich Parent-Verweisen und Fingerprints geprüft. Der separat
übernommene gespeicherte Originalreport stimmt mit dem geprüften Erfolgsreport
überein. Paket 2 ist committed und identisch replayt; beide unabhängigen Readbacks
sind fachlich und zeitlich gleich, Paket 1 unverändert.

Die beiden eingefrorenen Quellobjekte, normalisierten Werte, privaten
Quellreferenzen und Identitätsfingerprints sind unverändert. Erneute Offline-
Evidence-Prüfung bestätigt jeweils den eindeutigen gespeicherten Portfolio-Namen,
expliziten STOCK-Vertrag und `stock` → `equity`, keinen ETF-/Identitäts-/Namenskonflikt.
Kein Typdefault und keine Ableitung des Namens aus Symbol oder Kennung.

Ausschließliche Zielbasis ist der verifizierte private Phase-3D-E-Abschlussreport:
fünf Assets/Identifier, drei Sources, sechs Routes, sechs Observations, vier
Checkpoints; Current/Bars leer, Ledger v1+v2. Dies ist ein eingefrorener bestätigter
Zustand, keine neu abgefragte aktuelle Datenbankaufnahme.

## Katalog und Dedupe

Beide ISINs fehlen im bestätigten Zielkatalog. Geplant sind zwei neue aktive
Equity-Assets mit belegtem canonical_name/display_name, `base_currency = NULL`
und je einem globalen primären ISIN-Identifier ohne erfundene Sourcebindung.
Die native Quote-Währung wird nicht zur Basiswährung umgedeutet.

Beide Kandidaten verwenden dieselbe noch nicht vorhandene Source. Ihr vollständiger
geplanter Sourcevertrag enthält den eingefrorenen stabilen Source-Key, Typ
`market_data`, belegte deterministische Bezeichnung, `base_url = NULL` und
`enabled = 1`. Kein bestehendes Sourceobjekt wird wiederverwendet. Der private
Abgleich prüft bei jedem vorhandenen Treffer sämtliche semantischen Vertragsfelder;
Key-Gleichheit allein würde nicht genügen. Konflikte bleiben fail-closed.

Zwei neue Quote-Routes. Der generische Planer berücksichtigt beide UNIQUE-Verträge:
Source/Typ/externer Schlüssel sowie Asset/Source/Typ. Routepriorität begründet
keine Current-Auswahl. Konflikte werden nicht durch eine zweite Route umgangen.

Alle noch nicht angelegten Asset-, Source- und Route-IDs bleiben null. Die finale
Aktion ist jeweils `planned_insert_after_catalog_resolution`, kein abschließend
behauptetes `expected_insert`. Beide endgültigen Dedupe-Keys bleiben null.
Ein späterer freigegebener Import darf nur echte erzeugte/aufgelöste IDs mit
`normalizeObservation`, `canonicalObservation` und `dedupeKey` aus dem bestehenden
Phase-3C-Vertrag verwenden. Keine Ersatz-IDs, keine zweite Dedupe-Logik.

## Checkpointplanung ohne Schreibzugriff

Der allgemeine Stream bleibt `phase3d_market_migration_v1`; kein paketbezogener
neuer Stream. Für die eine neue Source wäre nach erfolgreichem Import genau ein
neuer Checkpoint nötig. Der private Plan enthält die belegte maximale observed_at
beider Kandidaten. Checkpoint-ID und endgültiger Cursor bleiben bis zur späteren
Sourceauflösung beziehungsweise zum verbindlichen Importmanifest offen.

Die vier bestätigten Checkpoints werden durch diesen Plan nicht verändert:
zwei gehören zum Paket-1-Stream, zwei zum bisherigen allgemeinen Migrationsstream.
Keine bestehende migration-v1-Zeile ist dieser neuen Source zugeordnet.
Bei späteren Paketen mit bestehendem Stream-Checkpoint wäre echter Fortschritt
kontrolliert fortzuschreiben, mit nicht rückläufiger Watermark. Ein identischer
Replay desselben Pakets dürfte dagegen kein unnötiges UPDATE erzeugen.
Dieser Auftrag implementiert und startet keine Checkpoint-Schreibaktion.

## Manifest, Reproduzierbarkeit und Freigabegrenze

Das private Manifest außerhalb Git enthält Parent-Fingerprints, eindeutige
P3-Zuordnung, unveränderte Quellreferenzen, belegte Namen/Klassen, Zeilen-/Evidence-
Fingerprints, vollständige Katalogplanung, normalisierte Observations,
Checkpointplanung und einen Selbstfingerprint. SHA-256 wird über kanonisches JSON
ohne das eigene Fingerprintfeld gebildet; der Dateifingerprint ist separat.
Keine Credentials und keine echten Daten in öffentlichen Artefakten.

`scripts/phase3d/next_batch.php` wurde unverändert wiederverwendet. Zwei generische
Planläufe sind bytegleich; auch die beiden daraus mit gleicher Evidence und
P3-Kennungen erstellten privaten Paketmanifeste sind bytegleich. Keine neue
Paket-Sonderlogik und keine Änderung an einem Import-/Schreibadapter erforderlich.

Vollständige Regressionen, Webdatei-Validierung und Diff-Prüfung werden trotz
reiner Dokumentationsänderung ausgeführt. Windows darf ausschließlich den bekannten
POSIX-Fall `budget_not_private` abweichend melden. Abschlusscommit, exakter
Linux-Nachweis mit übersprungenem Deploy und gelöschtem Prüfbranch stehen in Issue #21.

Kein Browser-/Dogado-/Plesk-Aufruf, keine Live-Quelle, keine DB-Verbindung,
kein Passwort oder Gateway, kein Import, Checkpoint-Write oder DDL. Keine Current-,
Bars-, Derived-/FX-, GBX-/XXX-, Indikator- oder Future-Fälle. Homepage und
Ladezeitanzeige unverändert. Kein Deployment und keine Produktion.

Die ursprüngliche geeignete Stichprobe ist **noch nicht vollständig migriert**:
sechs von acht Observations sind importiert, zwei nur vorbereitet. Ein späterer
Paket-3-Import benötigt ein eigenes Issue mit separater ausdrücklicher Freigabe.
