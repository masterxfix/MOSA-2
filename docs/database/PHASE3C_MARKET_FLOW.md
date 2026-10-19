# MOSA 2 – Phase 3C: kontrollierter Marktdaten-Schreibfluss

**Status:** 3C-A als Offline-Referenz implementiert und getestet; 3C-B nicht gestartet
**Grundlage:** Phase 3B am 19.10.2026 erfolgreich abgeschlossen; 16 Tabellen, Ledger v1+v2, alle 15 Nicht-Ledger-Tabellen leer  
**Ziel:** Den fachlichen Schreibfluss History → Current mit kleinen synthetischen Beispieldaten reproduzierbar nachweisen, bevor echte MOSA-Marktdaten übernommen werden.

## Scope

Phase 3C prüft ausschließlich:

- normalisierte synthetische Marktbeobachtungen;
- deterministischen Dedupe-Schlüssel;
- append-only History;
- transaktionale Current-Aktualisierung;
- Schutz gegen Rückschreiben älterer Marktzeitpunkte;
- deterministische Behandlung desselben Marktzeitpunkts innerhalb derselben Route;
- Route-/Asset-/Source-Konsistenz vor dem Schreiben;
- begrenzte History-/Bar-Lesewege und deren Laufzeiten;
- vollständigen Rollback der synthetischen Daten.

Nicht Teil dieser Phase:

- echte MOSA-Daten;
- produktive Collector oder Scheduler;
- Provider-Sonderlogik;
- Cross-Source-Arbitration für Current;
- Depot, News, KI oder Prognosen;
- Produktivdeployment.

## Schreibvertrag

Für eine synthetische Observation gilt:

1. Eingabe fachlich validieren.
2. Asset, Source und Route müssen existieren.
3. Die Route muss zum selben Asset und zur selben Source gehören.
4. Dedupe-Schlüssel zentral und deterministisch aus dem kanonischen Observation-Payload bilden.
5. Observation append-only in `m2_market_observations` schreiben.
6. Bereits vorhandener identischer Dedupe-Schlüssel erzeugt keine zweite History-Zeile.
7. Current wird innerhalb derselben Transaktion geprüft und ggf. aktualisiert.
8. Ein älterer `market_at` darf Current niemals überschreiben.
9. Bei gleichem `market_at` innerhalb derselben Route gewinnt nur ein neueres `observed_at`; bei identischem `observed_at` bleibt Current unverändert.
10. Fehler führen zum vollständigen Rollback.

Cross-Source-/Cross-Route-Auswahl für einen Asset-Current wird in Phase 3C nicht erfunden. Die Tests verwenden pro Testfall eine eindeutig ausgewählte Route.

## Dedupe

Der Dedupe-Schlüssel ist SHA-256 über eine zentrale kanonische Darstellung mindestens dieser Felder:

- asset_id
- source_id
- route_id
- currency
- market_at
- price
- bid
- ask
- volume

NULL-Werte und DECIMAL-Werte müssen eindeutig und stabil serialisiert werden. Keine provider- oder asset-spezifische Sonderlogik.

### Referenzvertrag für Phase 3C-A

`scripts/phase3c/market_flow.php` enthält den gemeinsamen providerneutralen
Normalizer, die testbare kanonische Darstellung, den SHA-256-Key und das
gekapselte `MarketFlow`-Offline-Modell. Die illustrativen Phase-3A-Modelltests
bleiben unverändert; der hier beschriebene 3C-Vertrag ist die Referenz für den
späteren 3C-B-Nachweis. Es entsteht kein Collector oder zweiter produktiver Pfad.

Die Eingabe enthält genau die oben genannten Felder **plus `observed_at`**,
keinen selbst gelieferten Dedupe-Key und keine zusätzlichen unvalidierten Felder.
`observed_at` gehört ebenfalls zur Identität: eine später erfasste Observation
bei identischem `market_at` muss als neue History-Beobachtung unterscheidbar
sein und darf gemäß Zeitregel Current aktualisieren. Ein vollständig identisches
Replay bleibt ein No-op für beide Projektionen.

Die kanonischen Bytes bestehen aus `mosa2-observation-v1` plus LF und einem
kompakten UTF-8-JSON-Objekt in fester Reihenfolge:
`asset_id, source_id, route_id, currency, market_at, observed_at, price, bid, ask, volume`.
Keine Eingabereihenfolge oder Locale beeinflusst diese Bytes. IDs werden als
positive unsigned-BIGINT-Dezimalstrings ohne führende Nullen normalisiert.
Währung: genau drei ASCII-Großbuchstaben. Zeitangaben sind explizite UTC-
SQL-Zeitstrings, kalendergeprüft und auf sechs Nachkommastellen aufgefüllt;
Offsets, lokale Zeitformate und mehr als sechs Stellen werden abgelehnt.

Preise/Bid/Ask verwenden die Präzision `DECIMAL(28,10)`, Volume `DECIMAL(32,8)`.
Zulässig sind Dezimalstrings oder Integer, keine Floats, Exponenten oder
localeabhängigen Trennzeichen. Führende Nullen, Pluszeichen, nachlaufende
Nachkommanullen und negatives Null werden vereinheitlicht; Ausgabe mit fester
Skala. Nicht darstellbare Werte werden ohne Rundung abgelehnt. Optionale Felder
sind ausdrücklich vorhanden und können JSON-`null` sein; NULL bleibt von null
als Zahl verschieden. Preis- und Bid/Ask-Prüfung entsprechen Migration 0002.
`dedupeKey()` liefert 32 rohe Bytes für `BINARY(32)`; das Offline-Modell verwendet
deren Hexdarstellung als History-Lookup und im Schreibresultat.

Das Modell hält logische Projektionen der vorhandenen Tabellen: History enthält
die normalisierten Observation-Felder; Current nur die passenden Current-Felder,
ohne History-Volume oder Dedupe-Spalte. Technische DB-IDs sowie `created_at` und
`updated_at` werden offline nicht erfunden. Der Ergebnisstatus unterscheidet
`inserted`/`duplicate` und `updated`/`unchanged`.

Alle Existenz- und Provenienzprüfungen erfolgen vor jeder Zustandsänderung.
Ein Wechsel von Source/Route eines vorhandenen Asset-Current wird vollständig
abgelehnt; eine Auswahl zwischen Routen wird nicht implementiert. Beide
Projektionen werden zunächst per Copy-on-write lokal aufgebaut und erst bei
Erfolg veröffentlicht. Der gezielte Fehler direkt nach dem History-Schritt
lässt beide Originalzustände unverändert. History ist von außen nur als
abgetrennter Snapshot lesbar; kein Update-/Delete-Pfad wird angeboten.

## Testfälle

Mindestens nachweisen:

- erste Observation erzeugt genau eine History-Zeile und Current;
- identische Observation erneut: keine zweite History-Zeile, Current unverändert;
- neuere Observation: History wächst um eins, Current wird aktualisiert;
- ältere Observation: History wächst um eins, Current bleibt auf dem neueren Stand;
- gleicher Marktzeitpunkt, neueres observed_at auf derselben Route: Current wird deterministisch aktualisiert;
- gleicher Marktzeitpunkt und identisches observed_at: Current bleibt unverändert;
- falsche Route-/Asset-/Source-Kombination wird vor dem Schreiben abgewiesen;
- absichtlich erzeugter Fehler rollt Observation und Current gemeinsam zurück;
- mehrere Assets beeinflussen sich nicht gegenseitig.

## Live-Test in Phase 3C

Der spätere Live-Nachweis verwendet nur wenige synthetische Assets/Sources/Routes und bleibt vollständig rollbackfähig. Nach dem Test müssen alle 15 Nicht-Ledger-Tabellen wieder leer sein; Ledger v1+v2 bleiben unverändert.

## Performance-Ziele

Auf der isolierten Testplattform:

- Current-Lesen ideal < 20 ms;
- begrenzte Observation-/Bar-Abfragen < 100 ms;
- keine ungebundenen Full Scans.

Die Messung ist ein kleiner Funktions-/Latenznachweis, keine Last- oder Produktivfreigabe.

## Ablauf

### 3C-A – Repository-Prüfcode

**Umgesetzt.** `tests/test_phase3c.py` führt die echten PHP-Referenzfunktionen
automatisiert aus: 24 Tests für die oben genannten Vertragsfälle, drei getrennte
Assets, kanonische Bytes und SHA-256, jedes Identitätsfeld, NULL-/DECIMAL-/UTC-
Grenzen, unveränderte History, No-op-Replay, Provenienz und modellierten Rollback.
Die Migrationen bleiben byte-identisch. Ausführung vom Repository-Root:

```text
python -m unittest discover -s tests -p test_phase3c.py -v
python -m unittest discover -s tests -v
python scripts/deploy_sftp.py validate
php -l scripts/phase3c/market_flow.php
git diff --check
```

Der Linux-Nachweis prüft exakt den Abschluss-Commit im vorhandenen Workflow;
Commit, Testergebnis und Run-ID werden in Issue #13 dokumentiert. Deploy muss
skipped bleiben; der temporäre Prüfbranch wird anschließend entfernt.

Diese Offline-Tests beweisen **keine** echte MySQL-Transaktion, DB-Latenz,
Dedupe-Unique-Verletzung, Parallelität, Collector-Ausführung, Cross-Source-
Auswahl oder Produktivfähigkeit. 3C-B bleibt separat freizugeben und ungestartet.

- zentrale, providerneutrale Schreib-/Dedupe-Logik für den Testpfad;
- deterministische Offline-Regressionstests;
- keine DB-Verbindung.

### 3C-B – isolierter Live-Nachweis

Erst nach separater Freigabe:

- Preflight: 16 Tabellen, Ledger v1+v2, alle 15 Nicht-Ledger-Tabellen leer;
- synthetische Core-/Asset-/Route-Fixtures in einer Transaktion;
- Schreibvertrag vollständig prüfen;
- Lesezeiten messen;
- vollständiger Rollback;
- finaler unabhängiger Leerstandscheck.

## Erfolgskriterium

Phase 3C ist erfolgreich, wenn der History→Current-Schreibvertrag deterministisch nachgewiesen ist, Dedupe und zeitliche Regeln funktionieren, Fehler atomar zurückrollen, die vorgesehenen Lesewege im Budget bleiben und nach dem Live-Test keine synthetischen Fachdaten zurückbleiben.
