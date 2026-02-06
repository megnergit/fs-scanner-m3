# fs-scanner-m3

## Inhaltsverzeichnis

- [fs-scanner-m3](#fs-scanner-m3)
  - [Inhaltsverzeichnis](#inhaltsverzeichnis)
  - [Ausführung](#ausführung)
    - [Testdaten erzeugen](#testdaten-erzeugen)
    - [Docker-Image für den Scanner bauen](#docker-image-für-den-scanner-bauen)
    - [RabbitMQ und Scanner starten](#rabbitmq-und-scanner-starten)
  - [Nachrichten im RabbitMQ Web-UI prüfen](#nachrichten-im-rabbitmq-web-ui-prüfen)
  - [Nachrichten per RabbitMQ CLI prüfen](#nachrichten-per-rabbitmq-cli-prüfen)

---

## Ausführung

Es sind **drei Schritte** erforderlich:

1. Testdaten-Verzeichnis erzeugen  
2. Docker-Image für den Scanner bauen  
3. Docker Compose starten  

Bitte stellen Sie sicher, dass eine **funktionsfähige Docker-Umgebung**
auf Ihrem System vorhanden ist.

---

### Testdaten erzeugen

Zunächst wird lokal eine Test-Verzeichnisstruktur erstellt,
die anschließend in den Scanner-Container gemountet wird.

```bash
uv run python src/fs2mq/utils/create_testdata.py ./data --profile light
```

Verfügbare Profile:

| Profil | Zweck | Eigenschaften |
|------|------|---------------|
| `light` | Schneller Funktionstest | Flache Struktur, wenige Dateien |
| `deep`  | Belastungstest | Tiefe Verzeichnisstruktur |
| `edge`  | Robustheitstest | Sonderzeichen, Berechtigungen, FIFO |

Nach erfolgreicher Ausführung sollte das Verzeichnis `./data` existieren:

```bash
tree ./data
```

---

### Docker-Image für den Scanner bauen

Kopieren Sie zunächst die Beispiel-Konfigurationsdatei:

```bash
cp .env.example .env
```

Passen Sie die Werte bei Bedarf an und bauen Sie anschließend das Image:

```bash
docker build --platform=linux/amd64 -t fs2mq:0.1.0 .
```

Prüfen Sie, ob das Image erfolgreich erstellt wurde:

```bash
docker images
```

---

### RabbitMQ und Scanner starten

Starten Sie die Container mit Docker Compose:

```bash
docker compose up -d
```

Prüfen Sie den Status der Container:

```bash
docker ps -a
```

Der Scanner-Container beendet sich **automatisch**, nachdem alle
Dateimetadaten erfolgreich an die RabbitMQ-Queue gesendet wurden.

---

## Nachrichten im RabbitMQ Web-UI prüfen

Öffnen Sie im Browser:

http://localhost:15672

Login-Daten (Standard):

- Benutzername: `admin`
- Passwort: `admin`

Navigieren Sie zu **Exchanges** und **Queues and Streams**.
Dort sollte die Queue `files` sichtbar sein.
Über **Get Message(s)** können empfangene Nachrichten angezeigt werden.

---

## Nachrichten per RabbitMQ CLI prüfen

Alternativ können die Nachrichten über die Kommandozeile geprüft werden:

```bash
docker exec -it rabbitmq /bin/bash
rabbitmqadmin -u admin -p admin -q files -c 10 | sed -n 's/.*│ \(.*path.*\) │.*/\1/p'
```

Die Ausgabe enthält die Metadaten der gescannten Dateien.
