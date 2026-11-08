# NEL ASA – Q2 2026 Importergebnis

Stand: 2026-11-08  
Repository: `masterxfix/MOSA-2`  
Commit-Bindung: `dbcdb73823ace8db02e7cda8755252203c683645`
Datenbankziel: `h29077_mosa2_test`  
Asset: NEL ASA, ISIN `NO0010081235`

## Ergebnis

Die NEL-Q2-2026-Migration ist **noch nicht erfolgreich abgeschlossen**. Der
einmalige Importlauf mit der getrennt reservierten Execution
`fundamentals-nel-q2-2026-20261108-02` wurde exakt einmal gestartet. Er hat den
offiziellen PDF-Bericht einmal erfolgreich abgerufen, ist danach aber in
`stage=ADAPTER` mit `STOP_NO_RETRY` abgebrochen. Der Writer und die
Importtransaktion wurden nicht erreicht; alle fünf Q2-Fakten bleiben daher
nicht gespeichert.

## Authentifizierter Datenbankbestand

Der Read-only-Vorcheck `42523125573` auf dem Commit oben war erfolgreich:

- Datenbankidentität: `h29077_mosa2_test`, genau ein aktives NEL-Equity-Asset;
- 6 bestehende FY-Observations und 3 FY-Current-Zuordnungen;
- 0 Q2-2026-Fakten;
- `read_only_confirmed=true`, `db_writes=0`, `db_unchanged=true`;
- 0 Providerabfragen, `market_data_read=false`, Quellen- und Faktenreferenzen bestanden.

Der unabhängige Postcheck `42523805036` nach dem fehlgeschlagenen Import
bestätigte denselben Bestand: 6 Observations, 3 FY-Current-Zuordnungen, keine
Q2-Fakten, `db_writes=0`, `db_unchanged=true`, 0 Providerabfragen und keine
Marktdatenlektüre. Die vorhandenen FY-Zuordnungen bleiben damit unverändert:
`ifrs_operating_profit:fy` → 64, `operating_cashflow:fy` → 66 und
`profit_before_tax:fy` → 65.

## Fachlich qualifizierte Q2-Kandidaten

Berichtsperiode: `2026-04-01` bis `2026-06-30` (`fq`, Geschäftsjahr 2026,
Quartal 2). Originaleinheit: `NOK_THOUSAND`, Währung NOK. Quelle:
[offizieller NEL-Q2-2026-Bericht (PDF)](https://mb.cision.com/Public/115/4374557/96afc9701633c3dd.pdf),
HTTP 200, 510279 Bytes, SHA-256
`60336ebdbcba904234ea9c40a759eb22baf9892fab571651b78e3c319f89a116`.

| Metric-Key | Originalwert | Fundstelle |
|---|---:|---|
| `revenue` | 153407 | PDF S. 12, „Revenue from contracts with customers“, Q2 2026 |
| `ebitda` | -155337 | PDF S. 17, Note 3, EBITDA-Block, Q2 2026 |
| `ifrs_operating_profit` | -205220 | PDF S. 12, „Operating loss“, Q2 2026 |
| `profit_after_tax` | -188571 | PDF S. 12, „Net income (loss) for the period“, Q2 2026 |
| `operating_cashflow` | 1673 | PDF S. 13, „Net cash flow from operating activities“, Q2 2026 |

Der Iwatani-Effekt bleibt Herkunftsevidenz; es wurde kein bereinigtes EBITDA
gebildet.

## Actions-Nachweis

1. Read-only-Vorcheck `42523125573`: erfolgreich auf `dbcdb738…`, ohne
   Schreib-, Provider- oder Marktdatenzugriff.
2. Einziger Schreib-/Import-Dispatch `42523237492` mit
   `reports=nel-q2-2026`, `expected_commit=dbcdb73823ace8db02e7cda8755252203c683645`
   und der gebundenen Authorization. Ergebnis: `failure`, genau 1 PDF-GET,
   `source_http_status=200`, `source_bytes=510279`, `provider_requests=1`,
   `observations=0`, `current=0`, `full_responses_archived=0`,
   `outcome=STOP_NO_RETRY`.
3. Unabhängiger Read-only-Postcheck `42523805036`: erfolgreich; der Bestand
   blieb unverändert und enthält weiterhin keine Q2-Fakten.

## Nachgewiesene technische Ursache und Korrektur

Der aktuelle NEL-Adapter definiert den sicher gebundenen Vertrag
`parse(raw, metadata, identity)`. Die gemeinsame Pipeline rief ihn in
`scripts/fundamentals_pilot_once.py` noch mit dem alten Zweieraufruf
`parse(raw, response.collected_at)` auf. Dieser deterministische
Vertragsbruch erklärt den `ADAPTER`-Abbruch; der öffentliche Runner unterdrückt
den internen Python-Traceback.

Die lokale Korrektur führt kontextgebundene Adapter über `_parse_adapter` mit
Metadaten und Asset-Identität aus und ergänzt die fehlenden öffentlichen
NEL-Fehlerklassen. Der fokussierte lokale Testblock besteht mit dem vorhandenen
PHP-CLI aus **10/10 Tests**, einschließlich der neuen Shared-Pipeline-Prüfung.
Es wurde nach dem Importfehler kein Provider- oder Datenbankzugriff lokal
wiederholt.

## Offener Blocker und Issue-Status

Execution 02 wurde beim einzigen erlaubten Importlauf sicher reserviert und ist
damit verbraucht. Der Marker darf weder gelöscht noch umgangen oder blind
wiederverwendet werden. Ein erneuter Schreiblauf mit korrigiertem Code benötigt
deshalb eine neue, ausdrücklich gebundene Execution und einen neuen
Autorisierungs-/Commit-Nachweis; dieser Auftrag hat keinen sicheren Weg dafür
ohne die One-shot-Sicherheitsgrenze zu verletzen. Issue #47 bleibt offen.

Die verbindliche Chrome-Sichtprüfung konnte wegen des aktuellen
E:-abhängigen Browser-Launchers nicht durchgeführt werden; es gab keine
Webseitenänderung und kein Testsite-Deployment. Eine vollständige Abnahme wird
daher nicht behauptet.

