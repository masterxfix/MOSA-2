# MOSA 2 – Phase 1: isolierte Datenbank-Testplattform

**Status:** geplant · noch keine Datenbank angelegt  
**Grundlage:** abgeschlossene Dogado-Plattformqualifikation  
**Ziel:** MySQL 8.0 und PHP 8.4 unter realen Dogado-Bedingungen prüfen, bevor das endgültige MOSA-2-Schema freigegeben wird.

## Festgelegter Ausgangspunkt

- eigene, von MOSA getrennte Testdatenbank;
- MySQL 8.0;
- PHP 8.4 FPM und PHP 8.4 CLI;
- lokaler Datenbankzugriff;
- eigener Datenbankbenutzer;
- keine echten MOSA-Daten in dieser Phase;
- keine produktive MOSA- oder MOSA-2-Änderung.

PHP 8.5 wird später als zusätzlicher Kompatibilitätskandidat verglichen. Es wird nicht automatisch zum Standard.

## Sicherheits- und Freigabegrenze

Die Anlage einer Datenbank, eines Benutzers oder einer Testdomain ist eine Dogado-Änderung und erfolgt erst nach ausdrücklicher Freigabe.

Zugangsdaten bleiben außerhalb von GitHub. Externer Datenbankzugriff bleibt zunächst deaktiviert. Alle Testtabellen erhalten einen eindeutig als temporär erkennbaren Präfix.

## Testblöcke

### 1. Plattform-Fingerprint

Zu erfassen sind unter anderem:

- genaue MySQL-8-Version;
- SQL-Modus, Zeichensatz, Kollation und Zeitzone;
- InnoDB- und Transaktionsverhalten;
- wichtige DB-Limits, soweit lesbar;
- PDO-MySQL-Verbindung über PHP 8.4 FPM und CLI;
- verfügbare PHP-Module für MOSA 2.

### 2. Minimales Testschema

Es werden noch keine endgültigen MOSA-2-Fachtabellen angelegt. Das Testschema bildet nur die geplanten Muster ab:

- kleine Current-Tabelle;
- große append-only History-Tabelle;
- Entity-/Identity-Zuordnung;
- Schema-Migrationsprotokoll;
- passende zusammengesetzte Indizes.

### 3. Datenmengen

Stufenweise testen:

1. 10.000 synthetische History-Zeilen;
2. 100.000 Zeilen;
3. 1.000.000 Zeilen erst nach positiver Zwischenbewertung und ausreichender Größen-/Lastfreigabe.

Jede Stufe muss wiederholbar und vollständig löschbar sein.

### 4. Kernabfragen

Mindestens messen:

- Current-Zustand eines Objekts;
- Current-Zustände mehrerer Objekte in einem Batch;
- neuesten History-Eintrag eines Objekts;
- begrenzten Zeitraum eines Objekts;
- Chart-/Zeitreihenbereich mit LIMIT;
- Insert-Batches;
- Update/Upsert eines Current-Zustands;
- Verhalten paralleler Lese- und Schreibzugriffe.

Für kritische Abfragen werden `EXPLAIN`, verwendeter Index, Sortierung und geschätzte gelesene Zeilen dokumentiert.

## Zielwerte

| Messpunkt | Ziel |
| --- | ---: |
| einfacher Current-Read | ideal < 20 ms |
| begrenzte History-Abfrage | < 100 ms |
| gesamte DB-Zeit einer normalen Seite | < 200 ms |
| normaler Seitenaufruf | < 1,0 s |
| p95 Seitenaufruf | < 1,5 s |
| harte Obergrenze | 2,0 s |

Ein Test gilt nicht als bestanden, wenn ein schneller Messwert nur durch Cache-Effekte entsteht, aber der Query-Plan ungeeignet ist.

## Backup- und Restore-Nachweis

Vor einer Schemafreigabe muss praktisch bewiesen werden:

- Export der Testdatenbank;
- Restore in eine zweite, getrennte Testdatenbank oder einen dafür vorgesehenen Restore-Zielbereich;
- Vergleich von Tabellen, Zeilenzahlen und Prüfsummen;
- dokumentierte Dauer und benötigter Speicher;
- kein Überschreiben einer bestehenden MOSA-Datenbank.

## Ergebnisse

Die Resultate werden nachvollziehbar in GitHub dokumentiert:

- getestete Versionen und Einstellungen;
- Testdatenmengen;
- Query-Pläne und Laufzeiten;
- Speicherentwicklung;
- Backup-/Restore-Ergebnis;
- Abweichungen von den Zielwerten;
- Entscheidung zu MySQL-Version, PHP-Version und Betriebsgrenzen.

## Freigabekriterium für das endgültige Schema

Das echte MOSA-2-Core-Schema wird erst freigegeben, wenn:

1. Current- und History-Muster die Zielwerte erreichen;
2. kritische Queries passende Indizes nutzen;
3. die Tests reproduzierbar sind;
4. Backup und Restore erfolgreich nachgewiesen wurden;
5. keine produktiven MOSA-Daten verändert wurden;
6. die technischen Dogado-Grenzen ausreichend verstanden sind.

Erst danach beginnen Core-Schema und kontrollierte MOSA→MOSA-2-Datenmigration.