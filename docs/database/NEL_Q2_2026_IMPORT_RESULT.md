# NEL ASA – Q2 2026 Importergebnis

Stand: 2026-11-08  
Repository: `masterxfix/MOSA-2`  
Commit-Bindung: `7a272cb59d2c42db1909b535ca702539bf91fa78`
Datenbankziel: `h29077_mosa2_test`  
Asset: NEL ASA, ISIN `NO0010081235`

## Ergebnis

Die fünf NEL-Q2-2026-Fakten stehen nach dem einzigen autorisierten Execution-03-
Lauf nachweislich in der Datenbank. Der Import-Workflow selbst endete
fail-closed mit `UNKNOWN_NO_RETRY`, weil sein unabhängiger interner Readback
die vollständige Vorher-Fingerprintprüfung unverändert gegen die nun erwarteten
neuen Fakten verglich. Die Datenbanktransaktion war zu diesem Zeitpunkt bereits
committet; der unabhängige Read-only-Postcheck bestätigt den tatsächlichen
Bestand. Es wurde kein zweiter Importlauf gestartet.

Execution 01 und 02 blieben unverändert. Execution 03 lautet:
`fundamentals-nel-q2-2026-20261108-03`.

## Authentifizierte Datenbanknachweise

### Read-only-Vorcheck

Run `42524364781`, auf Commit `7a272cb59d2c42db1909b535ca702539bf91fa78`:

- Datenbankidentität `h29077_mosa2_test@localhost`, genau ein Zielasset;
- 6 bestehende FY-Observations und 3 FY-Current-Zuordnungen;
- 0 Q2-2026-Fakten und keine Duplikate;
- `read_only_confirmed=true`, `db_writes=0`, `db_unchanged=true`;
- `provider_requests=0`, `market_data_read=false`, Source- und
  Fact-Referenzen bestanden.

### Einziger autorisierter Importlauf

Run `42524618785`, Workflow
[fundamentals-reports.yml](https://github.com/masterxfix/MOSA-2/actions/runs/42524618785),
mit `reports=nel-q2-2026`, der exakten Commitbindung und der gebundenen
Authorization. Der Lauf machte genau 1 PDF-GET (HTTP 200, 510279 Bytes),
bestand Adapter, Evidence-Archiv und Plan mit 5 qualifizierten Metrics und
committete die atomare Transaktion. Danach schlug der interne
`INDEPENDENT_READBACK` fail-closed fehl; es gab keinen Retry.

### Unabhängiger Read-only-Postcheck

Run `42524976213`, [erfolgreich abgeschlossen](https://github.com/masterxfix/MOSA-2/actions/runs/42524976213),
Job `128866468569`:

- Ziel `NO0010081235`, NEL ASA, `target_asset_count=1`;
- **11 Observations insgesamt = 6 FY + 5 FQ**;
- **8 Current insgesamt = 3 FY + 5 FQ**;
- genau fünf gültige Q2-Current-Slots: `revenue:fq`, `ebitda:fq`,
  `ifrs_operating_profit:fq`, `profit_after_tax:fq` und
  `operating_cashflow:fq`;
- `target_fundamental_observations=11`,
  `target_fundamental_current=8`;
- `read_only_confirmed=true`, `db_writes=0`, `provider_requests=0`,
  `market_data_read=false`, `db_unchanged=true`;
- `source_references=PASS`, `fact_references=PASS`.

Die drei FY-Current-Zuordnungen blieben erhalten:
`ifrs_operating_profit:fy` → 64, `operating_cashflow:fy` → 66 und
`profit_before_tax:fy` → 65. Die sechs FY-Observations sind im Readback
weiterhin vorhanden. Der Importpfad beschreibt keine Marktdaten; der
unabhängige Postcheck las keine Marktdaten.

## Q2-2026-Fakten und Herkunft

Berichtsperiode: `2026-04-01` bis `2026-06-30` (`fq`, Geschäftsjahr 2026,
Quartal 2). Originaleinheit: `NOK_THOUSAND`, Währung NOK. Quelle:
[offizieller NEL-Q2-2026-Bericht (PDF)](https://mb.cision.com/Public/115/4374557/96afc9701633c3dd.pdf),
HTTP 200, 510279 Bytes, SHA-256
`60336ebdbcba904234ea9c40a759eb22baf9892fab571651b78e3c319f89a116`.

DB-Quelle: `source_id=217`, `fetch_id=13`,
`storage_backend=dogado_private_evidence_json_v1`, Evidence-SHA-256
`F0494A83B6C8B654A31747292D0B06B519F9E1BC4E79E814837B596BBBEFC943`.

| Metric-Key | Wert | Gespeicherter Field-Path |
|---|---:|---|
| `revenue` | 153407 | `evidence:facts/0;source=pdf:page=12;table=Consolidated statement of comprehensive income;row=Revenue and income Revenue from contracts with customers 3;column=Q2 2026;x0=76.32;y0=210.89` |
| `ebitda` | -155337 | `evidence:facts/1;source=pdf:page=18;table=Note 3 Segment information;row=Total;column=Q2 2026;x0=76.32;y0=300.89` |
| `ifrs_operating_profit` | -205220 | `evidence:facts/2;source=pdf:page=12;table=Consolidated statement of comprehensive income;row=Operating loss;column=Q2 2026;x0=76.32;y0=353.57` |
| `profit_after_tax` | -188571 | `evidence:facts/3;source=pdf:page=12;table=Consolidated statement of comprehensive income;row=Net income (loss) for the period;column=Q2 2026;x0=76.32;y0=460.49` |
| `operating_cashflow` | 1673 | `evidence:facts/4;source=pdf:page=14;table=Consolidated statement of cash flows;row=Net cash flow from operating activities;column=Q2 2026;x0=76.32;y0=254.15` |

Der Iwatani-Effekt bleibt Herkunftsevidenz; es wurde kein bereinigtes EBITDA
gebildet. Alle fünf Readbackzeilen tragen `parser_key=nel_q2_2026_pdf_v1`,
`parse_status=parsed`, `source_id=217`, `fetch_id=13`, `http_status=200`,
`unit_key=NOK_THOUSAND` und die gemeinsame Evidence-Datei. Damit sind Source-,
Fetch-, File-/Storage- und Field-Path-Provenienz gebunden.

## Actions-Nachweis

1. Read-only-Vorcheck `42524364781`: erfolgreich auf
   `7a272cb59d2c42db1909b535ca702539bf91fa78`, ohne Schreib-, Provider- oder
   Marktdatenzugriff.
2. Einziger Schreib-/Import-Dispatch `42524618785` mit
   `reports=nel-q2-2026`, `expected_commit=7a272cb59d2c42db1909b535ca702539bf91fa78`
   und `authorization=MOSA2-REPORTS-nel-q2-2026:7a272cb59d2c42db1909b535ca702539bf91fa78`.
   Genau 1 PDF-GET, Evidence-Archiv `PASS`, 5 qualifizierte Metrics; Ergebnis
   `failure` im nachgelagerten `INDEPENDENT_READBACK`, `UNKNOWN_NO_RETRY`.
3. Unabhängiger Read-only-Postcheck `42524976213`: erfolgreich; 11
   Observations, 8 Current und alle fünf Q2-FQ-Fakten sind tatsächlich
   vorhanden.

## Technische Ursache des Workflow-Failures

Der Adaptervertrag ist korrekt `parse(raw, metadata, identity)`; die
Execution-03-Tests und der Actions-Preflight bestanden. Die atomare
Transaktion schrieb die fünf Fakten und Current-Zuordnungen. Danach prüfte
`core.php` mit `original($read, $before)` die vollständigen
Fundamentaltabellen gegen den Vorher-Fingerprint, obwohl genau diese Tabellen
durch die neuen Fakten wachsen müssen. Der interne Workflow-Readback war damit
zu streng und endete fail-closed nach dem Commit. Der unabhängige Postcheck ist
der maßgebliche tatsächliche Datenbanknachweis.

Der fokussierte lokale NEL-Testblock besteht mit dem vorhandenen PHP-CLI mit
**11/11 Tests**, einschließlich Execution-03-Registrierung, unveränderter
Execution-02-Historie, Metadata-/Identity-Aufruf und fail-closed Hash-/Werte-
Bindung.

## Issue-Status

Issue [#47](https://github.com/masterxfix/MOSA-2/issues/47) ist technisch durch
den unabhängigen Datenbank-Readback nachgewiesen erledigt. Die One-shot-Historie
bleibt unverändert: Execution 01 und 02 wurden nicht gelöscht, entsperrt,
verändert oder wiederverwendet; Execution 03 wurde genau einmal gestartet.

Die verbindliche Chrome-Sichtprüfung wurde wegen des bekannten
E:-abhängigen Browser-Launchers nicht durchgeführt; es gab keine
Webseitenänderung und kein Deployment. Eine visuelle Chrome-Abnahme wird daher
nicht behauptet.

