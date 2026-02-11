# fs-scanner-m3

## Inhaltsverzeichnis

- Architektur
- Schnellstart
- Funktionsweise
- Parameter
- End-to-End-Test
- Engineering Notes
- Lessons Learned

---
## Architektur

Dieses Projekt besteht aus zwei Komponenten:

- **Scanner (Python)** – durchsucht rekursiv ein lokales Dateisystem und erzeugt Metadaten-Events.
- **RabbitMQ** – dient als Message Broker zur Aufnahme dieser Events.

Die Architektur ist bewusst minimal gehalten:

Scanner → Direct Exchange → Queue → (optional Consumer)

Es gibt keine zusätzliche API-Schicht.

---
## Schnellstart

```bash
fs2mq ./data
```

- `./data` ist das Verzeichnis, das gescannt werden soll.
- Docker muss installiert und aktiv sein.
- `.env.example` muss zuvor nach `.env` kopiert werden.

---
## Funktionsweise

Es sind drei Schritte erforderlich:

1. Testverzeichnis erstellen
2. Docker-Image bauen
3. `docker compose up` ausführen

Der Scanner liest Dateien und sendet deren Metadaten als JSON-Nachrichten an RabbitMQ.

---
## Parameter

### Scanner (CLI)

- `--root PATH` – Verzeichnis zum Scannen
- `--dry-run` – Nur Ausgabe als JSON (keine Veröffentlichung an RabbitMQ)
- `--limit N` – Maximale Anzahl Events
- `--log-every N` – Fortschrittsausgabe

### RabbitMQ (.env)

Konfiguration erfolgt über `.env`:

- `EXCHANGE`
- `ROUTING_KEY`
- `QUEUE_NAME`
- `AMQP_URL`

Hinweis: Das VHost `/` muss als `%2F` URL-encodiert werden.

---
## End-to-End-Test

Vor dem Test empfiehlt sich ein vollständiges Aufräumen der Docker-Umgebung:

```bash
docker compose down -v
docker volume rm rabbitmq_data
docker image rm fs2mq:0.1.0 rabbitmq:4.2.3-management
```

Danach kann das Repository neu geklont und getestet werden.

---
## Engineering Notes

### Architektur-Scope
- Nur Scanner + RabbitMQ
- Keine zusätzliche API-Schicht

### Infrastruktur
- Docker Compose (angemessene Komplexität)
- Kein Kubernetes (Overkill für lokalen Einsatz)
- Keine Cloud (Authentifizierungs- und Kosten-Overhead)

### Sprache
- Python (schnelle Entwicklung)
- Performance ist kein Hauptkriterium

### Messaging & Zuverlässigkeit

Zuverlässigkeit entsteht nicht durch eine einzelne Option:

- durable Exchange
- durable Queue
- delivery_mode=2
- Publisher Confirms
- mandatory=True

Zuverlässigkeit ist ein Zusammenspiel mehrerer Mechanismen.

### Fehlerbehandlung
- Separate Behandlung von `UnroutableError` und `AMQPError`
- Explizite Exit-Codes

### Betriebsumfang
- Kein HA-Cluster
- Kein Backup (aktuell außerhalb des Scopes)
- Kein CI/CD

### Zukunft
- CIS Docker Hardening
- AMQPS (TLS)

---
## Lessons Learned

### Scanner wartet nicht automatisch auf RabbitMQ

Docker Healthchecks reichen nicht aus.
Der Scanner kann starten, bevor RabbitMQ vollständig bereit ist.

Lösung: Ein `entrypoint.sh`, das aktiv auf die Verfügbarkeit wartet.

### Passwortänderung in RabbitMQ

RabbitMQ speichert Benutzerinformationen im Docker-Volume (`rabbitmq_data`).
Eine Änderung in `.env` überschreibt diese Daten nicht automatisch.
Das Volume muss explizit gelöscht werden.

### bool(None) ist False

`bool(None)` ergibt `False`.
Das kann zu Fehlinterpretationen bei Rückgabewerten führen.

### Zuverlässigkeit ist mehrschichtig

Nachrichtenpersistenz erfordert mehrere Mechanismen gleichzeitig.
Es gibt keinen einzelnen „Reliability-Schalter“.
