# fs-scanner-m3

## Architektur

Dieses Projekt besteht aus zwei Komponenten:

-   **Scanner (Python)** -- durchsucht ein lokales Dateisystem rekursiv
    und erzeugt Metadaten-Events.
-   **RabbitMQ** -- dient als Message Broker zur Aufnahme der Events.

Die Architektur ist bewusst minimal gehalten: Scanner → Direct Exchange
→ Queue → (Consumer optional)

Es gibt keine zusätzliche API-Schicht.

------------------------------------------------------------------------

## Schnellstart

``` bash
fs2mq ./data
```

Voraussetzungen:

-   Docker ist installiert und läuft.
-   `.env.example` wurde nach `.env` kopiert.

------------------------------------------------------------------------

## Funktionsweise

1.  Testverzeichnis erstellen\
2.  Docker-Image bauen\
3.  `docker compose up` ausführen

Der Scanner liest Dateien und sendet deren Metadaten als
JSON-Nachrichten an RabbitMQ.

------------------------------------------------------------------------

## Wichtige Parameter

### Scanner (CLI)

-   `--root PATH` -- Verzeichnis zum Scannen
-   `--dry-run` -- Nur Ausgabe als JSON, keine Veröffentlichung an
    RabbitMQ
-   `--limit N` -- Maximale Anzahl Events
-   `--log-every N` -- Fortschrittsausgabe

### RabbitMQ (.env)

-   `EXCHANGE`
-   `ROUTING_KEY`
-   `QUEUE_NAME`
-   `AMQP_URL`

------------------------------------------------------------------------

## Engineering Notes

### Architektur-Scope

-   Scanner + RabbitMQ
-   Keine zusätzliche API-Schicht

### Infrastruktur

-   Docker Compose (angemessene Komplexität)
-   Kein Kubernetes (Overkill für lokalen Anwendungsfall)
-   Keine Cloud (Authentifizierung/Kosten nicht erforderlich)

### Sprache

-   Python (schnelle Entwicklung)
-   Performance ist kein Hauptkriterium

### Messaging & Zuverlässigkeit

Zuverlässigkeit entsteht nicht durch eine einzelne Option:

-   durable Exchange
-   durable Queue
-   delivery_mode=2
-   publisher confirms
-   mandatory=True

### Fehlerbehandlung

-   Getrennte Behandlung von `UnroutableError` und `AMQPError`
-   Explizite Exit-Codes

------------------------------------------------------------------------

## Lessons Learned

### Scanner wartet nicht automatisch auf RabbitMQ

Docker Healthchecks reichen nicht aus.\
Der Scanner kann starten, bevor RabbitMQ vollständig bereit ist.

Lösung: `entrypoint.sh`, das aktiv auf die Verfügbarkeit wartet.

### Passwortänderung in RabbitMQ

RabbitMQ speichert Benutzerinformationen im Docker-Volume
(`rabbitmq_data`).\
Eine Änderung in `.env` überschreibt diese Daten nicht automatisch.

Das Volume muss explizit gelöscht werden.

### bool(None) ist False

`bool(None)` ergibt `False`.\
Das führte zu Fehlinterpretationen bei Rückgabewerten.

### Zuverlässigkeit ist mehrschichtig

Nachrichtenpersistenz erfordert mehrere Mechanismen gleichzeitig. Es
gibt keinen einzelnen „Reliability-Schalter".
