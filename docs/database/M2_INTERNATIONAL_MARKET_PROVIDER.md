# MOSA 2 – Internationale ISIN-Kursversorgung ohne Sonder-Collector

> **HISTORISCHE TECHNISCHE DOKUMENTATION – NICHT AKTIVIERBAR (Nutzerentscheidung 12.11.2026).**
> **Twelve Data und EODHD sind in MOSA 2 AUSGESCHLOSSEN**, nicht bloß
> mangels Credentials vorübergehend deaktiviert. Die folgenden Adapter- und
> Zugangskonfigurationsbeispiele bleiben ausschließlich zur Dokumentation und
> für offline durchgeführte Regressionsprüfungen. Sie sind **keine**
> Betriebsfreigabe. Das zentrale `api/market_sources.php` blockiert beide
> Anbieter unabhängig von alten Freigabeflags. Nur neue ausdrückliche
> Nutzerentscheidung darf daran etwas ändern.
>
> Aktuelle Anbieterliste und geprüfte Alternativen:
> [M2 Marktdatenanbieter](../M2_MARKTDATEN_ANBIETER.md).


Stand 12.11.2026. Gilt ausschließlich für das eigenständige M2-System und die
bestehende Dogado-Testdatenbank. MOSA-Produktion darf nicht angesprochen werden.

## Betriebsstand und Geltungsgrenze

Der M2-Minutenjob bleibt der **einzige** automatische Kurscollector. Das zentrale
Quellenregister ist `api/market_sources.php`; die PHP-Quellenvorschau und das
Browser-JavaScript haben keine zweite Liste von aktiven Quellen.
Lang & Schwarz, Tradegate BSX und Frankfurt werden unabhängig per ISIN abgefragt.

M2 besitzt 19 eingefrorene versionierte Einheiten (vier historische sowie 15
internationale Basiswährungen). Die allgemeine native Quote-Verarbeitung nimmt
nur Daten an, deren Quote-Einheit im **tatsächlichen** `m2_units`-Bestand vorhanden
und `frozen` ist. Das Original wird nicht in EUR umgedeutet: Für `JPY` gilt
currency `JPY`, quote_unit_key `JPY`; für `GBX` gilt currency `GBP`,
quote_unit_key `GBX`. Marktzeit, Einheit, ISIN und Quelle bleiben prüfbar.
Der Current-Pfad darf keinen erfundenen Kurs und keine implizite FX-Umrechnung
veröffentlichen.

## Optionale internationale Anbieterquelle

`api/market_core/twelve_data.php` ist ein ISIN-generischer **Adapter im
bestehenden M2-Collector**, kein zweiter Scheduler und kein Spezialfall für
einzelne Aktien. Der offizielle Twelve-Data-REST-Endpunkt `/quote?isin=...`
kann für berechtigte Konten globale Kursdaten liefern. API-Zugriff per
`Authorization: apikey <secret>`-Header; der Schlüssel erscheint nicht in
URLs, Web-JavaScript, Workflow-Ausgaben oder der Datenbank. Der Anbieter muss
für die tatsächlich gewünschten Märkte, die automatisierte Nutzung und die
optionale **ISIN-Datenfreigabe** lizenziert sein. Ein HTTP-200-Test ohne gültige
Lizenz ist keine Betriebsfreigabe.

Das M2-Release aktiviert die Quelle **nicht automatisch**. Bei fehlender
Freigabe-Konfiguration gibt es **0 zusätzliche Anbieterrequests**, keine
Twelve-Data-Registrierung und keine neuen DB-Kursrouten. Bestehende Anbieter
arbeiten unverändert weiter.

Freigabekonfiguration ausschließlich als owner-only PHP-Datei außerhalb des
Webroots:

`/var/www/vhosts/web213.server10.configcenter.info/mosa2-market-twelvedata-private/access.php`

Verzeichnisberechtigung `0700`, Datei `0600`. Die Konfiguration muss erst
**nach** dem Erwerb und Nachweis des passenden Datenzugangs mit den tatsächlichen
vom Anbieter genehmigten Limits befüllt werden. Folgende Struktur wird erwartet:

```php
<?php
return [
    'enabled' => true,
    'market_data_rights_confirmed' => true,
    'isin_addon_confirmed' => true,
    'api_key' => '<AUSSCHLIESSLICH PRIVATE ECHTE ANBIETERZUGANGSDATEN>',
    'max_daily_requests' => 50,
    'max_minute_requests' => 2,
];
```

Die Limitwerte sind **keine Empfehlung und keine Annahme über das Twelve-Data-
Abonnement**; sie sind durch die tatsächlich zulässigen Limits zu ersetzen.
Schlüssel dürfen niemals ins Repository, in Chats oder in öffentlich erreichbare
M2-Dateien geschrieben werden. Die Berechtigungs-Flags sind nicht automatisch
Freigaben durch ChatGPT, sondern müssen den tatsächlichen Accountrechten
entsprechen. Bei unsicherer Datei oder fehlendem Recht verweigert der Adapter
den Start bzw. bleibt deaktiviert.

## Zweiter ISIN-generischer Provider: EODHD (verzögert)

Die M2-eigene Integration `api/market_core/eodhd.php` ist in den **einen**
bestehenden Minuten-Collector integriert. Das ist weder ein zweiter Collector
noch eine Länder-, ISIN- oder ETF-Sonderlösung. Sie verwendet dieselbe
`api/market_sources.php`-Quelle, denselben Schema-6-Observation-/Current-Writer
und die bestehende Scheduler-Sperre.

Die EODHD-Suchantwort wird **auf die exakte ISIN** geprüft; der Markt-Ticker
und die Originalwährung stammen aus deren verifizierbaren Datenfeldern.
Die Exchange-Metadaten müssen einen eindeutigen realen MIC liefern.
Mehrdeutige Primärnotierungen, Exchange-Codes mit mehreren MICs, abweichende
ISIN, andere Ticker im Kurs-Response, ungültiger Preis oder über 30 Minuten
alter Marktzeitstempel werden abgelehnt. Der Anbieter nennt für seine
Live-REST-Preise in der Regel 15–20 Minuten Verzögerung; die **unveränderte
Marktzeit** und das tatsächliche Alter bleiben sichtbar. Ein verzögerter
Kurs wird nicht als Echtzeitangebot etikettiert. Die Marktkennzeichnung des
Instruments ist kein universeller Beweis dafür, dass alle Preisbestandteile
direkt von dieser Börse stammen; der Anbieter beschreibt zum Teil indikative
aggregierte Quellen.

Die Routenauflösung wird im **bestehenden** M2-`m2_sync_checkpoints`-Speicher
ohne Zugangsdaten auf 14 Tage begrenzt wiederverwendet. Negative/mehrdeutige
ISIN-Abfragen werden für maximal sechs Stunden zurückgestellt. Sowohl
Routenrecherche als auch Kursabruf reservieren tatsächliche UTC-Minuten-
und Tagesbudgets vor jeder externen Anfrage. Kein schleichendes Überziehen
des Kontingents; der kostenlose EODHD-Tarif umfasst laut Anbieter nur
20 Calls pro Tag. Für viele Werte ist damit keine Minutentakt-Versorgung
möglich. Bestehende EUR-Quellen bleiben unabhängig aktiv.

**Sichere Aktivierung:** Nur mit echtem privaten API-Konto und tatsächlichen
Rechten auf vertrauliche, persönliche Anzeige. EODHD verlangt technisch den
Token als `api_token` in der HTTPS-Provideranfrage; er bleibt daher
ausschließlich auf dem privaten Dogado-Laufzeitpfad und darf niemals
in GitHub, Browser, Logdateien oder M2-Datenbank gelangen. Die Owner-Datei
liegt außerhalb des Webroots unter
`/var/www/vhosts/web213.server10.configcenter.info/mosa2-market-eodhd-private/access.php`;
Verzeichnis `0700`, Datei `0600`. Beispielstruktur **ohne echten Schlüssel**:

```php
<?php
return [
    'enabled' => true,
    'personal_or_internal_rights_confirmed' => true,
    'private_display_only' => true,
    'api_token' => '<ECHTER PRIVATER EODHD-ACCOUNT-TOKEN>',
    'max_daily_requests' => 20,
    'max_minute_requests' => 2,
];
```

Limits sind **nur Beispiele**: Maßgeblich sind die im persönlichen Konto
wirklich freigeschalteten Rechte und Kontingente. Der Code prüft die Flags,
nicht eigenständig die vom Anbieter erteilte Lizenz. Ohne die Datei wird
**kein zusätzlicher GET und keine neue Provider-DB-Route** erzeugt.

**Bekannte Grenze:** EODHD deckt zahlreiche Heimatmärkte (darunter ASX),
aber laut aktueller veröffentlichter Exchange-Liste nicht alle Börsen,
insbesondere ist Tokio dort nicht aufgeführt. Diese Integration allein
erfüllt deshalb **nicht** die Gesamtforderung nach internationaler
Live-Versorgung jeder ISIN. Die optionale Twelve-Data-Quelle deckt
zusätzliche Märkte ab, setzt aber ihre eigenen Markt- und ISIN-Rechte voraus.
Solange die tatsächliche Lizenz, echte Antworten in Originalwährung,
DB-Readback, Marktzeitzonen und sichtbare M2-Anzeige fehlen, bleibt die
Gesamtabnahme ausdrücklich **offen**.

Offizielle Quellen:
- https://eodhd.com/financial-apis/search-api-for-stocks-etfs-mutual-funds
- https://eodhd.com/financial-apis/live-ohlcv-stocks-api
- https://eodhd.com/financial-apis/exchanges-api-list-of-tickers-and-trading-hours
- https://eodhd.com/financial-apis/our-data-sources-and-data-partners
- https://eodhd.com/financial-apis/api-limits
- https://eodhd.com/help/personal-use
- https://eodhd.com/list-of-stock-markets

## Gemeinsame Sicherheits- und Datenverträge

- Nur eine exakte HTTPS-ISIN-Adresse: `api.twelvedata.com/quote?isin=<ISIN>`.
  Kein freier Host/URL/Redirect und keine Tickerraterei.
- ISIN ist an den Request gebunden. Ein abweichendes, im Antwortkörper
  mitgeliefertes ISIN-Echo führt zur Ablehnung.
- Erst ein positiver, expliziter `close`-Wert und ein echter UTC-`timestamp`
  bzw. `last_quote_at` liefern einen Kandidaten. Das echte `mic_code` wird
  als Routen-Evidenz übernommen. Fehlt eine gesicherte MIC, wird keine Heimatbörse
  erfunden.
- Die vorhandene MOSA-Quellenwahl, Wertprüfung und der Schema-6
  Observation-/Current-Writer bleiben der einzige Persistenzpfad.
- Reservierungen sind transaktional in bereits vorhandenen
  `m2_sync_checkpoints` gespeichert und kosten **auch bei Fehlern** Budget.
  Im UTC-Minuten- und UTC-Tagesfenster werden die privat erlaubten Grenzen
  durchgesetzt; HTTP 401/403/429 führen zu einer bestehenden Provider-Cooldown.
- Ist der letzte Anbieterpreis älter als die gültige Frischegrenze oder die
  Börse geschlossen, wird **kein fiktiver neuer Current** erzeugt. Letzte echte
  gespeicherte Daten dürfen nur mit ihrem tatsächlichen Datum/Alter angezeigt
  werden. Datenalter ist nicht gleich Zeit bis zum nächsten Börsenhandel.
- Die aktuelle manuelle Browser-Vorschau benutzt weiterhin die etablierten
  MOSA-Quellen, greift **nicht** ungeprüft auf private Twelve-Data-Credentials zu
  und umgeht dadurch kein API-Budget.

## Nachweislage und offene externe Voraussetzungen

Die vorhandenen europäischen Quellen haben ISINs aus Australien, Japan, China
und einen ETF mit **EUR-Notierungen** gefunden. Das ist **kein Nachweis für
Heimatbörsenkurse in AUD/JPY/HKD**.

Der neue Adapter hat Offline- und isolierte MySQL-Tests für echte native
Währung, MIC-Routenbindung, Frische, Quoten, Geheimhaltung und Fehlerfälle.
Ohne eingerichtete und gültige Anbieterberechtigung sind **echte** Twelve-Data-
Abfragen und eine internationale Live-Kurs-Speicherung ausdrücklich offen.
Nicht jede syntaktisch gültige ISIN ist börsennotiert oder im Umfang eines
Providers verfügbar; `unavailable` ist deshalb ein zulässiger ehrlicher
Datenstatus, keine Anlass zur Kursfabrikation.

Für die Gesamtfreigabe fehlen weiterhin ein berechtigtes internationales
Providerkonto und ein nachgewiesener echter M2-Test über mehrere Zeitzonen
einschließlich separater Observation-/Current- und Browser-Sichtabnahme.

Offizielle Grundlagen:
- https://twelvedata.com/docs
- https://twelvedata.com/terms
- https://twelvedata.com/docs/websocket/websocket-getting-started
