# Phase 3C-B – History-Plan und Offline-Korrektur

## Gesicherter Live-Befund

Grundlage: Ausgangscommit `1fdcbcd29424a924d0fe262f8c17096fc61b02f3`,
[Issue #14, erster Live-Report](https://github.com/masterxfix/MOSA-2/issues/14#issuecomment-6263763383)
und [anschließende Einordnung](https://github.com/masterxfix/MOSA-2/issues/14#issuecomment-6263808301).
Der erste fachliche Lauf am 19.10.2026, 09:09:12 UTC, bestand 21/23 Prüfungen.
Die Schreibfälle (einschließlich Unique-Verletzung 1062 und Savepoint-Rollback)
bestanden. Die Leseprüfung brach am History-Key ab:

```sql
SELECT id,market_at
FROM m2_market_observations
WHERE asset_id=? AND market_at>=? AND market_at<?
ORDER BY market_at,id LIMIT 5
```

Parameter: `101`, `2026-01-02`, `2026-01-03`.
Erwartet: `ix_market_observations_asset_time`.
Tatsächlich: `ix_market_observations_asset_source`, `ref`, geschätzte sechs Zeilen,
`Using where; Using index; Using filesort`.

Die ursprüngliche funktionale Fixture hatte nur drei Assets, zwei Sources,
vier Routes und acht Observations insgesamt. Für das abgefragte Asset gab es
nur eine Source. Die geringe Größe ist konsistent damit, dass der Optimizer den
alternativen Asset-/Source-Index mit anschließendem Sortieren wählte. Ohne
Optimizer-Cost-Trace ist die genaue interne Kostenentscheidung nicht bewiesen.
Daraus folgt kein nachgewiesener Schemafehler. Migrationen und Indizes bleiben
byte-identisch, der erwartete Key bleibt zwingend.

## Geänderter Testpfad

Die bisherigen fachlichen Assertions bleiben klein und unverändert. Erst danach
ergänzt der reine Testadapter zwei gültige Routes und eine getrennte direkte
History-Fixture. Es gibt keine neue Current-Arbitration oder Collectorlogik.

| Eigenschaft | Anfang | Einmaliger Ausbau |
| --- | ---: | ---: |
| Assets | 3 | 3 |
| Sources/Routes je Asset | 2/2 | 2/2 |
| Tage ab 01.01.2026 UTC | 8 | 32 |
| Zeitpunkte je Tag/Source | 16 | 16 |
| zusätzliche Observations je Asset | 256 | 1.024 |
| zusätzliche Observations gesamt | 768 | 3.072 |
| gesamter Bestand einschließlich funktionaler Zeilen | 776 | 3.080 |
| Performance-Zeilen im History-Tagesfenster je Asset | 32 | 32 |

Alle Assets/Sources verwenden dieselbe Generierungslogik mit 90-Minuten-Abstand
und zehn Minuten Offset. Das Fenster trifft anfangs 1/8, nach Ausbau 1/32 der
Performance-Zeilen eines Assets. Funktionale Zeilen bleiben erhalten und werden
in der tatsächlichen Report-Verteilung mitgezählt. Der Ausbau fügt nur neue Tage
hinzu; keine Duplikate, Löschungen oder Current-Änderungen. Jede Observation
verwendet die vorhandene Normalisierung und denselben rohen SHA-256-Dedupe-Key.

Jeder Leseweg erhält zunächst einen natürlichen EXPLAIN. Bei falschem Key oder
`ALL` darf die Observation-Fixture global genau einmal erweitert werden. Ein
zweiter EXPLAIN folgt nur für diesen betroffenen Leseweg. Andere Wege teilen
denselben Ausbauzähler; es gibt keinen weiteren Ausbau. Jeder Versuch wird vor
jedem Guard dauerhaft gespeichert, einschließlich vollständiger EXPLAIN-Zeile,
SQL, Parametern, Versuch, erwarteten/tatsächlichen Plandaten und Fixturegröße
sowie Observations, Sources, Routes und Fensterzeilen je Asset.

Nach dem letzten erlaubten Versuch gelten erwarteter Key, begrenzter Zugriff
und kein Filesort strikt. Ein weiterer Fehler stoppt den Lauf. Kein FORCE/USE/
IGNORE INDEX, keine Query-Änderung zur Planerzwingung. Warmup, 20 monotone
Messungen und Budgets bleiben: Current <20 ms, History und Bars jeweils <100 ms.
Der anschließende Bars-Pfad bleibt erhalten; die Phase-3B-Suite wird nicht wiederholt.

## Rollback und Aussagegrenze

Der erste Live-Lauf endete mit äußerem Rollback. Eine unabhängige Verbindung
bestätigte 16 Tabellen, unverändertes Ledger v1+v2 und 15 leere Fachtabellen.
SHOW CREATE unterschied sich ausschließlich bei AUTO_INCREMENT-Zählern von
Sources, Observations und Bars. InnoDB setzt diese Metadaten bei einem
Datensatz-Rollback nicht zwingend zurück. Es gibt keinen fachlichen Datenrest,
keine DDL-Reparatur und keinen Zähler-Reset.

Der vorbereitete Endcheck trennt Leerstand/Ledger/Grants, vollständigen
Schema-/Constraint-Vertrag und den Zählerstand. Nur die Tabellenoption
AUTO_INCREMENT wird beim Strukturvergleich normalisiert; Spalteneigenschaften,
Indizes und Constraints bleiben vollständig im Vergleich.

Dieser Auftrag führt ausschließlich Offline-Tests aus: keine DB-Verbindung,
kein Passwort, kein Dogado/Plesk, kein Gateway-Deployment und kein neuer
Live-Test. Fake-EXPLAINs beweisen Retry-Grenzen und erhaltene Fehlerpläne auf
Disk, nicht die spätere natürliche MySQL-Indexwahl. Issue #14 bleibt offen.
Ein zweiter Phase-3C-B-Live-Nachweis benötigt einen separaten Auftrag und Freigabe.

## Offline-Prüfung

11 neue History-Regressionstests sowie alle 44 Phase-3C-Tests bestanden lokal.
Die Windows-Gesamtsuite bestand 142/143 Tests; ausschließlich der bekannte
POSIX-Dateirechtefall `budget_not_private` weicht ab. PHP-Lints aller drei
neuen/geänderten PHP-Dateien, Dateivalidierung und `git diff --check` bestanden.
Der verbindliche Linux-Nachweis erfolgt auf dem exakten Abschlusscommit über
einen temporären Prüfbranch; Ergebnis und Run-ID werden in Issue #14 ergänzt.
Der Deploy-Job muss dabei skipped bleiben.

## Separater finaler Live-Nachweis

Der anschließend separat freigegebene zweite Lauf am 19.10.2026,
09:42:32–09:42:33 UTC, verwendete die Korrektur auf `b61f189` unverändert und
bestand 23/23 Prüfungen. Bereits mit 768 Performance-Observations wählte History
im ersten Versuch `ix_market_observations_asset_time` / range / rows 35,
`Using where; Using index`, ohne Filesort. Kein Fixture-Ausbau war erforderlich.
Auch Bars und sämtliche Latenzbudgets bestanden. Der äußere Rollback und beide
Endchecks bestätigten vollständigen Leerstand bei unverändertem Ledger und
Strukturvertrag. Details: [PHASE3C_FINAL_LIVE.md](PHASE3C_FINAL_LIVE.md).
Die vorstehenden Offline-Aussagegrenzen bleiben für den damaligen Auftrag gültig.
