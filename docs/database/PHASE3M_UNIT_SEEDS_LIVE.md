# Phase 3M – normative Unit-Definitionen live validiert

**Aktueller Status: Live-Insert und Bereinigung erfolgreich.** Die unten
beschriebenen Stopps sind historische Zwischenstände; maßgeblich ist der
abschließende Erfolgsnachweis am Dokumentende.
Ausgangspunkt exakt `1207493e4acbb035dd9a1c067b754b0bfd966e95`,
vorher mit `origin/main` abgeglichen. Nutzerfreigabe für ausschließlich die
isolierte Testdatenbank ist in [Issue #29](https://github.com/masterxfix/MOSA-2/issues/29#issuecomment-6283656151)
dokumentiert. Das Issue bleibt offen. Kein Abschlusscommit/Push, da diese nur
bei vollständig erfolgreichem Live-Insert freigegeben sind.

## Eingefrorenes Paket und Offlineprüfung

Das [Phase-3L-Manifest](seeds/0001_market_units_v1.json) und sein Validator
bleiben unverändert. SHA-256 der exakten Manifestdateibytes:
`0d9f196e4ccbd5e687292fa3d7a1a087b343ec81fb609b8b64b6454713246bbf`.
Freigegebener Paketfingerprint:
`b66df6f972ad13c05c3f34c604088c0281dcd9f0ff4bafad45b9600aa2b747ee`.

| Unit, geplante Reihenfolge | Basis | Faktor | definition_sha256 |
|---|---|---|---|
| EUR@1 | EUR@1 | 1/1 | `4d2e721264795c68d1d5434cdab7c53199ba4270c1cd43114200f9e86de1c4c4` |
| GBP@1 | GBP@1 | 1/1 | `dcf7b65464052cd34b4e98a0fc7abcf32b53543117af2a612965f0ed3f4fb10a` |
| POINT@1 | POINT@1 | 1/1 | `29c50d2fad8e5176e9c4204579c1b33b9e7883f3afe8fe3cbfc097efd72b7092` |
| GBX@1 | GBP@1 | 1/100 | `c80d04b9e0b1ee996242364ffbfea7b37fbda9c23f746356072b43cce551ddd6` |

GBP ist die Geldwährung von GBX, POINT hat NULL. Alle Definitionen sind frozen,
Version 1, Vertrag mosa2-market-unit-v1. Keine Floats, Provider-/Asset-/Routenlogik.
Die neue Python-Logik unter `scripts/phase3m/unit_seed.py` importiert den
unveränderten Phase-3L-Validator. Sie erzeugt Insertpläne, vergleicht vollständige
Readbacks und klassifiziert Replay ohne Schreibzugriff. Nichtpersistierte Evidenz
wird beim Paketvergleich anhand der Identität aus dem freigegebenen Manifest
ergänzt; DB-created_at bleibt dabei außerhalb des öffentlichen Paketfingerprints.

Vor Browser-/DB-Zugriff: vollständige lokale Suite **300/301**, nur bekannte
Windows-Abweichung `budget_not_private`. Nach Ergänzung von Gateway/Transaktionslogik:
**307/308**, wieder ausschließlich diese Abweichung; Phase-3M-Tests **21/21**.
Validator, Diff-Prüfung und beide PHP-Lints bestanden. Tests decken unter anderem
Binärhash-Transport, Konflikte, unverändertes created_at, vollständigen Readback,
exakte Insertreihenfolge, Rollback vor Commit, keinen Retry und CSRF/HTTP-Guards ab.
Mock-Transaktionen sind ausdrücklich kein praktischer MySQL-Self-FK-Nachweis.

## Geschützter Testweg

Ausschließlich vorhandene verbundene Chrome-Sitzung und vorhandener Plesk-Textweg.
Dogado/Plesk waren angemeldet; der zusätzliche Verzeichnisschutz der Testseite
wurde durch den Nutzer angemeldet. Keine Erweiterungsberechtigungen geändert.
Secretfreie Quellen wurden serverseitig gegen ihre Hashes geprüft; historische
Quellen wurden vom exakten Ausgangscommit geladen. Eine CRLF-Arbeitskopie wurde
beim Transport gegen den tatsächlichen Git-Objekthash abgeglichen. Escaping und
Rechte des neu erzeugten öffentlichen Gateway-Verzeichnisses wurden vor jedem
DB-Zugriff korrigiert; bestehender Verzeichnisschutz und Homepage unverändert.

Serverseitiger Python-Validator (Python 3.6.8), Paket-/Quellhashvergleich und
PHP-8.4-Lints bestanden vor Passwortübergabe. Der tatsächliche passwortlose
Browser-GET/POST belegte HTTPS, exakte Origin, CSRF, Secure, HttpOnly,
SameSite Strict, no-store und noindex sowie **0 DB-Verbindungen / 0 DB-Writes**.
Danach gab der Nutzer das Passwort ausschließlich im vorbereiteten Formular ein.
Es wurde nur im laufenden PHP-Prozess verwendet, nie in Datei, URL oder Bericht.

## Tatsächlicher Live-Stopp und Aussagegrenzen

Der einzige Live-Lauf endete in `stage=live_preflight` mit:

`{"kind":"guard","reason":"auto_increments_changed"}`.

Der Vergleich der AUTO_INCREMENT-Metadaten gegen den hashgeprüften privaten
Phase-3K-Abschlussbeleg schlug fehl. Die genaue betroffene Tabelle und die beiden
Zählerwerte sind im Fehlerbericht nicht separat persistiert. Aus diesem Fehler
wird weder ein Schemafehler noch eine Änderung fachlicher Datensätze abgeleitet.
Es wurde keine weitere DB-Verbindung zur Diagnose hergestellt, kein Guard
abgeschwächt und kein Live-Preflight erneut versucht.

Der Code stoppt an dieser Stelle vor Self-FK-Probe, Paket-created_at-Erzeugung
und normativer Transaktion. Bericht: `ok=false`, `commit_requested=false`,
`commit_confirmed=false`; kein Self-FK-Ergebnis. **0 DB-Writes / 0 normative
Inserts / 0 Updates / 0 Ledgerwrites.** Die beim Verbindungsaufbau erforderlichen
Sessioneinstellungen wurden auf die bereits qualifizierten UTC-/Strict-Werte gesetzt.

| Geforderter Nachweis | Tatsächliches Ergebnis |
|---|---|
| Vollständiger Live-Preflight | an AUTO_INCREMENT-Vergleich gestoppt |
| Praktischer Self-FK-Precheck + unabhängiger Empty-Readback | nicht ausgeführt |
| Eingefrorenes Paket-created_at | nicht erzeugt |
| Normativer Insert 4/4 | nicht ausgeführt |
| m2_units vorher/nachher | im gestoppten Lauf nicht vollständig bestätigt; keine Units geschrieben |
| EUR/GBP/POINT/GBX live | durch Phase 3M nicht eingespielt |
| Post-Commit-Readback 1 und 2 | nicht ausgeführt |
| DB-Paketvergleich und Replay 4/0/0/0 | nur offline getestet, nicht live nachgewiesen |
| Vollständiger abschließender Legacy-/Ledger-Nachweis | wegen Preflight-Stopp nicht abgeschlossen |
| Linux vom Abschlusscommit | entfällt: kein freigegebener Erfolgscommit |

Der dokumentierte vorherige Phase-3K-Stand bleibt historische Grundlage:
17 Tabellen, Ledger v1/v2/v3, Units 0, acht Observations, Current/Bars 0.
Er wird nicht als vollständig neu bestätigter Phase-3M-Endzustand ausgegeben.

## Sicherheitsbereinigung

Nach Stopp keine DB-Aktion wiederholt. Passwortreferenzen wurden verworfen,
CSRF-Cookie gelöscht, öffentlicher Gateway entfernt. Alle 14 hashgeprüften
temporären Quelldateien einschließlich Transportplan und Migrationskopien sowie
Zugangskonfiguration, Lock und Python-Bytecode entfernt. Keine geplante Aufgabe
gespeichert. Private Diagnosebelege bleiben mit 0700/0600 erhalten.

Originaler Fehlerbericht unverändert erhalten, SHA-256:
`74823d75ff6f467db23cd2ea81d707280233ac7ff5a7df3ceb5fca5aac6ee80c`.
Bereinigungsnachweis bestätigt Quellen-/Config-/Lock-Entfernung und unveränderten
Homepagehash. Authentifizierter Browser-Readback des entfernten Gateway: **404**.
Separater HTTP-Abruf der Homepage ohne Auth: **401**.

Keine Homepageänderung, kein Writer-v2, B8-Import, Current-/Bar-Write,
produktives Deployment oder Produktion. Kein Ledger v4. Kein Erfolgscommit,
kein Push, kein Linux-Prüfbranch und kein Actions-/Deploylauf für Phase 3M.
Eine spätere Untersuchung/Fortsetzung erfordert einen eigenen konkreten Auftrag;
dieser Lauf endet nach dem vorgeschriebenen Stopp und der Bereinigung.

KI-Kontrollzentrum separat: nativer Start einmal regulär versucht,
`PROMPT_RECEIPT_MISSING`; Describe/Plan jeweils einmal mit tatsächlicher Turn-ID
versucht, beide ohne offenen nativen Auftrag. Keine IDs/Ereignisse rekonstruiert,
keine Abschlussbewertung für den unvollständigen Auftrag vorgemerkt.

## Autorisierte Fortsetzung: Read-only-Diagnose, erneut gestoppt

Der Folgeauftrag erlaubt eine Fortsetzung ausschließlich nach eindeutigem
Nachweis von METADATA_ONLY_DRIFT oder CHECKER_BASELINE_BUG. Die vorhandenen
privaten Artefakte enthielten keine aktuellen Zählerwerte; deshalb erfolgte
nach secretfreiem HTTP-/Formular-Dry-Run genau eine neue Read-only-Diagnose.
Die Transaktion wurde zurückgerollt. Keine DB-Reparatur oder Wiederholung.

Ergebnis: **EVIDENCE_INSUFFICIENT**, Guard `counter_not_above_max`.
Die geforderte technische Bedingung `AUTO_INCREMENT > MAX(PK)` ist mit den
erfassten Metadaten nicht durchgehend belegt. Daraus wird weder eine tatsächlich
defekte InnoDB-Zählerverwaltung noch eine fachliche Datenänderung abgeleitet.
Ein nachfolgender rein dateibasierter Auswertungsversuch meldete außerdem
`counter_integer`; auch dies rechtfertigt keine Lockerung oder neue DB-Abfrage.
Rohwerte und betroffene Tabellennamen bleiben ausschließlich privat.

Der vor dem Vergleich gesicherte Snapshot bestätigt gegenüber Phase 3K:

- vollständige fachliche Rows einschließlich PKs und Dedupe-Keys identisch;
- Row-Hashes, Ledger v1/v2/v3, Environment/Grants und Struktur identisch;
- Strukturvergleich normalisiert ausschließlich die AUTO_INCREMENT-Metadaten;
- 12 AUTO_INCREMENT-Tabellen, davon 10 mit abweichenden historischen Werten;
- Entities 7, Assets 7, Identifier 7, Sources 4, Routes 8, Observations 8,
  Checkpoints 5, Current 0, Bars 0; `m2_units = 0`.

Der bisherige Phase-3M-Liveguard bleibt unverändert. Die neue generische
Vergleichs-/Diagnoselogik und ihre Regressionstests sind lokal vorbereitet:
33/33 gezielte Tests bestanden. Kein erneuter Gesamtsuitenlauf ohne tatsächlichen
Guardfix; vorheriger Windows-Nachweis 307/308 mit ausschließlich
`budget_not_private`. Kein neuer Linux-Nachweis.

Self-FK-Test, normative Inserts, Paket-Replay und Post-Commit-Readbacks wurden
nicht gestartet. 0 DB-Writes, 0 Inserts, 0 Updates, 0 Ledgerwrites,
kein Counter-Reset und kein `ALTER TABLE AUTO_INCREMENT`. Units bleiben 0;
die vier normativen Definitionen sind weiterhin nicht live eingespielt.

Private Belege unter `mosa2_phase3m_resume_a157c2/scripts/phase3m`:

- `diagnostic-state.json`, SHA-256
  `5760ce1e996a5ebe00f488098281fbdea3e8808ce091b43aedee1f6eaec25aef`;
- `diagnosis.json`, SHA-256
  `2bd0408eadb66f0fa4c58a0bbd89f07524320b27fd529a6d94dd8ffc9d900f16`;
- ergänzende Zusammenfassung, HTTP-Proofs und Bereinigungsbericht.

Passwort nur im laufenden Formularprozess; Referenzen und CSRF-Cookie beim
Stopp verworfen. Alle 17 temporären Quellen, Zugangskonfiguration, Locks und
Bytecode entfernt. Öffentlicher Gateway einschließlich Verzeichnis entfernt:
authentifizierter Chrome-Readback **404**, Homepage ohne Auth **401**.
Keine geplante Aufgabe gespeichert; unverändert neun bestehende Aufgaben.
Private Belege mit 0700/0600 erhalten.

Der erste Bereinigungsvergleich zielte irrtümlich auf eine nicht vorhandene
`index.php`; der daraus entstehende Vergleich zweier fehlgeschlagener Hashwerte
wurde ausdrücklich verworfen und im privaten Bericht auf unbekannt korrigiert.
Die tatsächlich vorhandene `index.html` hat aktuell SHA-256
`7e86160f5ac33386743c11fd86beb0deb4fea0c27c82d5cea520927f0ad9ecb6`.
Dieser Lauf beansprucht daraus keinen eigenständigen Vorher-/Nachher-Nachweis.
Keine Homepage-Schreibaktion erfolgte.

Kein Abschlusscommit, Push, Linux-Prüfbranch, Actions-Lauf oder Deploy.
Issue #29 bleibt offen. Phase 3N wurde wegen unvollständiger Phase 3M nicht
begonnen. Kein Writer-v2, B8-Import oder Produktionszugriff.
Die fachliche Arbeit endet am ausdrücklich vorgeschriebenen Evidenz-Stopp.

## Korrigierter Phase-3C-Vertrag und erneute Fortsetzung

Der nächste menschliche Auftrag und Issue-Kommentar 6284234582 heben die
zusätzliche Freigabebedingung `AUTO_INCREMENT > MAX(PK)` ausdrücklich auf.
Die alten Stoppberichte bleiben historische Belege, ihre Klassifikation wird
für die Fortsetzungsentscheidung jedoch durch **CHECKER_BASELINE_BUG mit
METADATA_ONLY_DRIFT** ersetzt. Keine Datenreparatur erforderlich.

Die korrigierte gemeinsame Vergleichslogik wurde ohne neue DB-Verbindung auf
den hashgeprüften privaten Diagnose-Snapshot angewandt: akzeptiert, 10 von 12
Zählerwerten historisch abweichend, vollständige fachliche Rows/PKs/Hashes,
Struktur, Environment/Grants und Ledger identisch, Units 0. AUTO_INCREMENT
wird ausschließlich erfasst und diagnostisch verglichen; weder historische
Gleichheit noch eine Beziehung zum höchsten PK sind Freigabebedingungen.
Kein Reset, kein ALTER und keine tabellenspezifische Ausnahme.

Der Liveguard verwendet denselben generischen Vergleich bei Preflight,
Probe-Rollback, vor jedem Insert sowie vor/nach Commit. Readbacks vergleichen
den normalisierten Fachzustand und Units; rohe Snapshot-Hashes bleiben separat
als Transfer-/Artefaktevidenz erhalten. Die endgültige Durchführung ist noch
nicht belegt und darf erst nach Passworteingabe behauptet werden.

Offline nach tatsächlichem Guardfix: 34/34 gezielte Tests, Gesamtsuite 320/321
mit ausschließlich bekanntem Windows-Fehler `budget_not_private`, Validator,
Diff-Prüfung und alle fünf PHP-Lints bestanden. Ein fehlender PHP-PATH und
unzugänglicher prozessübergreifender Temp-Pfad wurden im Testruntime korrigiert;
die durch die gemeinsame Moduleinbindung verursachte doppelte Test-Inklusion
wurde zu `require_once` korrigiert. Tests wurden nicht abgeschwächt: veränderte
Rows, PK-Sätze, Rowcounts, Row-Hashes, Ledger, Struktur, Grants und unerwartete
Units bleiben Fehler. Historisch stark abweichende Zähler werden akzeptiert.

## Abschließender Live-Nachweis

Nach der einmaligen Passworteingabe ausschließlich im geschützten Formular
endete der korrigierte Lauf mit `ok=true`, `stage=complete`,
`commit_requested=true`, `commit_confirmed=true`. Kein Retry, kein Repair und
kein Counter-Reset. Klassifikation CHECKER_BASELINE_BUG mit METADATA_ONLY_DRIFT
bei 10/12 historischen Zählern.

Der rollbackbare praktische Self-FK-Test akzeptierte Self-Base und abhängige
Unit einschließlich CHECKs und verwarf die ungültige Basisreferenz über den
erwarteten FK. Vollständiger Rollback; neue Verbindung bestätigte Units 0.

Danach exakt EUR@1, GBP@1, POINT@1, GBX@1 in dieser Reihenfolge in einer
Transaktion eingefügt. Vollständiger 4/4-Readback samt Definitionhashes und
Paketfingerprint vor Commit erfolgreich. Einmalig eingefrorenes UTC-created_at:
`2026-10-20 05:48:42.298886`. Keine Updates, Upserts, INSERT IGNORE oder
Ledgerwrites. GBX referenziert GBP@1 mit currency GBP und Faktor 1/100;
POINT referenziert sich selbst mit currency NULL und Faktor 1/1.

Zwei unabhängige Post-Commit-Verbindungen bestätigten jeweils exakt vier
Definitionen mit unveränderten Hashes und created_at. Replay ist ausschließlich
Planung: **4 duplicate / 0 insert / 0 update / 0 conflict**, keine zweite
Insert-Transaktion. Alle vier verwendeten Verbindungs-IDs waren verschieden.

Legacy-Rows, vollständige PK-Sätze und Dedupe-Keys, Row-Hashes, Grants und
Struktur unverändert. Keine Unit-FKs in Legacyzeilen nachgetragen. Entities 7,
Assets 7, Identifier 7, Sources 4, Routes 8, Observations 8, Checkpoints 5,
Current 0, Bars 0; Ledger v1/v2/v3 unverändert. Units **0 → 4**.

Private Belege verbleiben außerhalb des Repositories. Abschlussbericht SHA-256:
`9914756fec7d78ec7e1ddd2d71f8ad221bc516bfded8844701f37029f1416b50`.
Beide fachlich normalisierten Readbacks haben SHA-256:
`837baa06c81caa85e547bc4d53489956bdd5170febcb994f6e9d02326f0b8e2a`.
Rohsnapshot-Hashes werden ausdrücklich nicht auf historische Zählergleichheit
gezwungen; Units werden separat vollständig verglichen.

Bereinigung tatsächlich bestätigt: 15/15 temporäre Quellen, Config, Locks und
Bytecode entfernt; Passwortreferenzen und CSRF-Cookie verworfen. Gatewaydatei
und Verzeichnis entfernt, authentifizierter Browser **404**, Homepage ohne
Auth **401**. `index.html` vor/nach Bereinigung byteidentisch zum geschützten
Repositoryhash `7e86160f5ac33386743c11fd86beb0deb4fea0c27c82d5cea520927f0ad9ecb6`.
Keine Aufgabe gespeichert (weiterhin neun bestehende Aufgaben).

Der Abschluss erfolgt mit genau einem Commit
`Validate MOSA market unit seeds live [skip ci]`. Der Linux-Nachweis vom exakten
Commit wird über einen temporären Prüfbranch ohne Produktionsdeploy ausgeführt;
Commit, Run-ID und Ergebnis werden in Issue #29 nachgetragen. Kein Writer-v2,
B8-Import oder Produktion. Dieser begrenzte Vier-Unit-Test ist kein Nachweis
für Parallelbetrieb, größere Importmengen oder produktiven Writerbetrieb.

## Nächster vorbereiteter Schritt: Phase 3N (offline)

Observation-v2/unit-aware Writer erst als getrennten Offline-Schritt umsetzen:
bestehenden Observation-Vertrag und Unit-Semantik zusammenführen; versionierte
Unitreferenz und exakte rationale Skalierung validieren; kanonische Identität,
Dedupe und konfliktfreies Replay erhalten. Mit synthetischen Fixtures gültige
Referenzen, fehlende/unbekannte Units, inkompatible Dimensionen, exakte Brüche,
Hashkonflikte und unveränderte Legacy-v1-Verarbeitung prüfen. Der vorbereitete
Schritt umfasst keinerlei DB-Verbindung, Live-Writer-Test oder B8-Import.
