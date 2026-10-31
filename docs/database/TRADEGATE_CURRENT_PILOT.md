# Tradegate-Kursmodul — 31.10.2026

## Ziel und fachliche Bedeutung

Eine bestehende Aktie einmal über den bewährten MOSA-Tradegate-Weg abrufen,
als Observation-v2 speichern und über den vorhandenen Current-Webpfad anzeigen.
Der Preis ist der exakt dezimal berechnete Mittelwert aus Geld und Brief (Mid),
kein behaupteter letzter Handel. Marktzeit und tatsächliche Erfassungszeit bleiben
getrennt. Außerhalb der Handelszeiten darf der zuletzt verfügbare Kurs älter sein;
sein Alter wird nicht durch einen erneuten Abruf verschleiert.

## Wiederverwendung

Referenz ist `masterxfix/fixlab` am Commit
`8b2d8c523aa4f63bef3aa904956b756ad87ab49f`, insbesondere
`php/mosa_market_source_lab.php` und `php/mosa_market_live_quote_runner.php`.
Der neue generische Adapter `scripts/market_collector/tradegate.py` benötigt
genau einen GET auf `https://www.tradegatebsx.com/orderbuch.php?isin=<ISIN>`.
Der vorhandene Transport übernimmt TLS, Zeitlimit und den einmaligen Abruf.

Der gemeinsame Source-Key `provider:tradegate_bsx_mid` bezeichnet diesen
Mid-Datenstrom für alle ISINs. Sein Name `Tradegate · XGAT · Mid` wird von der
bestehenden Testsite direkt aus der Datenbank angezeigt. Eine eventuell vorhandene
Legacy-Source `provider:tradegate_bsx` bleibt unverändert. Es gibt keine neue
Datenbankmigration, keine aktienspezifische Logik und keine visuelle Umgestaltung.

Der Schema-4-Einmalstarter wählt eine vorhandene veröffentlichte EUR-Aktie,
registriert höchstens eine Source und eine inaktive Route und nutzt anschließend
den vorhandenen Collector, Observation-Writer und Current-Refresh. Der ausdrücklich
genehmigte Quellenwechsel validiert den bisherigen Current gegen seine bisherige
Route; ein älterer Marktwert verdrängt keinen neueren.

## Nachweise

- 3 fokussierte Adaptertests: MOSA-HTMLfixture, exakter Mid, Writer, Current,
  PHP-Webleseweg, Replay und ungültige Eingaben.
- 5 fokussierte Current-Übergangstests einschließlich tatsächlichem PHP-Leseweg.
- 1 fokussierter Manifesttest einschließlich vorhandener Legacy-Source und BIGINT-ID.
- 56 relevante Regressionen: `test_market_collector_v1`, `test_market_current`
  und `test_collector_release.Schema4OnceTests`, alle bestanden.
- Das isolierte Git-Kandidatenpaket mit 59 Dateien besteht Build/Verify; auch der
  Tradegate-Adapter wird aus den Paketbytes bis zum PHP-Webleseweg geprüft.

Lokale Prüfung: Python 3.12 und PHP 8.3.6. Die Zielkonfiguration bleibt ausdrücklich
Python 3.11.18 und PHP 8.4.12 auf Dogado; ein Fachlauf dort ist noch nicht belegt.

## Konkreter nächster Schritt

Nach ausdrücklichem Startauftrag genau ein zusätzlicher manueller Lauf von
`.github/workflows/collector-schema4-once.yml`, gebunden an den vollständigen
Commit dieses geprüften Stands. Bereits verbrauchte Actions: 3; mit diesem
zusätzlichen Lauf höchstens 4 insgesamt. Höchstens eine Provideranfrage,
keine Wiederholungsabrufe. Der vorhandene Marker `schema4-live-20261030`
wird weder gelöscht noch umbenannt.

Vorhandene GitHub-Secrets verwenden. Der Lauf installiert das private Paket,
führt den Einzelabruf aus und prüft gespeicherte Observation, Current und
installierten Web-Leseweg. Danach ist die tatsächliche Darstellung im bestehenden
Chrome separat zu prüfen. Erfolg erfordert einen konkreten Kurs mit ISIN, Quelle,
Marktzeit und Erfassungszeit; ein Paket-PASS allein reicht nicht.

Die automatische Ausführung bleibt deaktiviert. Die historischen Frankfurt-
Nachweise und `rights_confirmed=false` werden nicht in eine behauptete
Anbieterbestätigung umgeschrieben. Der Nutzer hat einen begrenzten praktischen
Versuch beauftragt; daraus wird keine pauschale Dauerfreigabe abgeleitet.

Aktueller Ausführungsstand: keine neue Action, kein Kursabruf und keine Installation.
Der Browserzugriff aus dieser Chat-Sitzung meldet fehlenden Ursprungskontext;
der GitHub-Connector besitzt keinen Workflow-Dispatch. Der vorbereitete Start
kann über den vorhandenen nativen Codex-/GitHub-CLI-Zugang erfolgen.
