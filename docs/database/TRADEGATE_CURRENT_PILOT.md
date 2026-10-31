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

## Ausführungsnachweis und Installationskorrektur

[Lauf 41184371735](https://github.com/masterxfix/MOSA-2/actions/runs/41184371735)
führte den Stand `3796c85a62c7f1df06476eee22081d53c9da61d6` am 31.10.2026 aus.
Das 59-Dateien-Paket bestand die Prüfung. Alle 13 Runtime-Prüfungen bestanden,
einschließlich Python 3.11.18 und PHP 8.4.12. Die private Vorbereitung stoppte
vor dem ersten Schreibvorgang mit `BASE_IDENTITY_CHANGED`: 0 Provideranfragen,
0 Datenbankverbindungen, keine neue Observation oder Current-Aktualisierung.

Der wiederverwendete Verzeichnisprüfer erwartet noch die am 21.10.2026 gemessene
Basisidentität `device=64768, inode=5248112` sowie sechs damalige private
Verzeichniskennungen. Die Abweichung ist belegt; heutige Einzelwerte und die
Ursache der Änderung wurden in diesem Lauf nicht ausgegeben.

Schema-4 erfasst deshalb jetzt einmalig vor Installationsschreibvorgängen die
Identitäten der sieben fest vorgegebenen Verzeichnisse. Die vorhandenen Prüfungen
von Host-Key, Account, Pfad, Eigentümer, Rechten, Symlinks und Stat/Open-Wechseln
bleiben wirksam. Ein vollständiger zweiter Durchgang bestätigt die Erfassung.
Dieser Stand wird durch Vorbereitung, unabhängige Readbacks, Veröffentlichung
und Collectorstart weitergereicht. Spätere Phasen dürfen ihn weder neu erfassen
noch ersetzen. Auch der zusammengesetzte Supervisor verwendet diese Bindung;
seine historische Prüffunktion darf sie nicht überschreiben.

- 6 fokussierte Tests der tatsächlich zusammengesetzten Programme bestanden:
  neue Ausgangskennungen, unveränderte Pfadprüfungen, Änderungen innerhalb und
  zwischen SSH-Phasen, fehlende/ungültige Bindung und Controller-Weitergabe.
- 31 unmittelbar betroffene bestehende Regressionen bestanden: 11 Verzeichnistests,
  16 Uploadtests und 4 Schema-4-Autorisierungs-/Abschlusstests.
- Die historischen Uploadtests wurden auf das tatsächliche Originalrelease
  `92274a79550b8acd719434459022da6de5261d2e` ausgerichtet. Zuvor verhinderten
  ihre HEAD-Bezüge und die unvollständige Übernahme eines historischen Objekts
  aus dem flachen Checkout den vollständigen Nachweis. Nach Korrektur wurden
  nur noch fehlende beziehungsweise betroffene Tests ausgeführt.
- Historische Profile behalten ihre bisherigen Identitätsvorgaben. Die
  Korrektur betrifft die Installationsprogramme, nicht die 59 Payload-Dateien.
- Bei dieser Korrektur: 0 Actions, 0 Provideranfragen, keine Serverinstallation
  und keine Datenbankänderung.

## Konkreter nächster Schritt

Bereits verbrauchte Actions: **4**; Provideranfragen dieses fortgesetzten
Einmalauftrags: **0**. Das zuletzt freigegebene Laufbudget ist ausgeschöpft.
Ein fünfter Lauf ist noch nicht freigegeben. Für den Live-Nachweis wird genau
ein weiterer manueller Lauf von `.github/workflows/collector-schema4-once.yml`
vorgeschlagen, gebunden an den vollständigen Commit des korrigierten Stands.
Er benötigt die ausdrückliche Erweiterung des Laufbudgets gemäß `AGENTS.md`.
Höchstens eine Provideranfrage, keine Wiederholungsabrufe. Der vorhandene
Marker `schema4-live-20261030` wird weder gelöscht noch umbenannt.

Vorhandene GitHub-Secrets verwenden. Der Lauf installiert das private Paket,
führt den Einzelabruf aus und prüft gespeicherte Observation, Current und
installierten Web-Leseweg. Danach ist die tatsächliche Darstellung im bestehenden
Chrome separat zu prüfen. Erfolg erfordert einen konkreten Kurs mit ISIN, Quelle,
Marktzeit und Erfassungszeit; ein Paket-PASS allein reicht nicht.

Die automatische Ausführung bleibt deaktiviert. Die historischen Frankfurt-
Nachweise und `rights_confirmed=false` werden nicht in eine behauptete
Anbieterbestätigung umgeschrieben. Der Nutzer hat einen begrenzten praktischen
Versuch beauftragt; daraus wird keine pauschale Dauerfreigabe abgeleitet.

Eine Installation und sichtbare Kursabnahme sind weiterhin offen. Der bereits
verwendete native Codex-/GitHub-CLI-Zugang kann den nächsten freigegebenen
Start ausführen; eine erneute Einrichtung des GitHub-Zugangs ist nicht nötig.

## Expliziter Fünferlauf (31.10.2026)

Der neue Workflow-Modus `scope=five` verwendet ausschließlich die zentrale
Namensliste BYD, DroneShield, Ubtech Robotics, PNE AG und Carl Zeiss Meditec.
ISINs und physische Beziehungen stammen aus vollständig validierten,
bereits veröffentlichten Current-Datensätzen. Keine numerischen IDs sind
fest codiert. Bestehende Tradegate-Quelle und -Routen werden wiederverwendet;
fehlende Routen erzeugt ausschließlich der gemeinsame Planer.

Eigene exakte Autorisierung: `MOSA2-SCHEMA4-FIVE-20261031:<Vollcommit>`.
Der dauerhafte Marker `schema4-five-20261031` reserviert diesen Auftrag
genau einmal. `schema4-live-20261030` bleibt unverändert und verbraucht.
Maximal fünf sequenzielle Provideranfragen, eine je qualifizierter ISIN;
keine Wiederholung. Das unveränderte Installationsprotokoll erhält seine
paketgebundene Installationsautorisierung separat; diese erteilt keine
weitere Abrufberechtigung.

Die bestehenden gemeinsamen Batch-, Observation-, Current- und
Quellenwechselprüfungen bleiben maßgeblich. Danach unabhängige
Observation-/Current-Prüfung, Replay, unveränderte übrige Bestände,
installierte Current- und Observation-Weblesewege sowie Release-Readback.
Die sichtbare Browserabnahme ist ein eigener Nachweis. Python 3.11.18,
PHP 8.4.12; automatische Betriebsfreigaben bleiben deaktiviert.

Fokussierter Offline-Nachweis: drei Tests bestanden, einschließlich der
Mischlage mit vorhandener DroneShield-Tradegate-Route und vier bisherigen
Frankfurt-Zuordnungen. Der gemeinsame In-Memory-Store vergibt auch über
mehrere Materialisierungen eindeutige synthetische Route-IDs.

102 unmittelbar betroffene lokale Regressionen bestanden; zwei lokale
Prüfpunkte (PHP-Schemafixture und historischer Git-Checkout für die Paketklasse)
benötigen den isolierten Linux-Nachweis. Der neue Offline-Scope
`tradegate-five` führt ausschließlich diese offenen Prüfpunkte einschließlich
der Fünfer-Supervisorprüfung sowie Build/Verify des 59-Dateien-Pakets aus.
Bereits bestandene lokale Regressionen werden dort nicht wiederholt.
