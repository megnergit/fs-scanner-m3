# fs-scanner-m3

## Inhaltsverzeichnis

- [fs-scanner-m3](#fs-scanner-m3)
  - [Inhaltsverzeichnis](#inhaltsverzeichnis)
  - [So führst du es aus](#so-führst-du-es-aus)
    - [Testdaten-Verzeichnis erstellen](#testdaten-verzeichnis-erstellen)
    - [Docker-Image für den Scanner bauen](#docker-image-für-den-scanner-bauen)
    - [RabbitMQ und Scanner starten](#rabbitmq-und-scanner-starten)
  - [Nachrichten in der RabbitMQ-Web-UI prüfen](#nachrichten-in-der-rabbitmq-web-ui-prüfen)
    - [Management-UI öffnen](#management-ui-öffnen)
    - [Exchange](#exchange)
    - [Queue und Nachrichten](#queue-und-nachrichten)
  - [Nachrichten per RabbitMQ-CLI prüfen](#nachrichten-per-rabbitmq-cli-prüfen)
  - [Parameter](#parameter)
    - [Scanner](#scanner)
      - [`--root PATH` *(erforderlich)*](#--root-path-erforderlich)
      - [`--dry-run (optional)`](#--dry-run-optional)
      - [`--limit N (optional)`](#--limit-n-optional)
      - [`--log-every N (optional)`](#--log-every-n-optional)
    - [RabbitMQ](#rabbitmq)
  - [End-to-End-Test](#end-to-end-test)
    - [Aufräumen und Repo klonen](#aufräumen-und-repo-klonen)
    - [Test 1 – Großes Dateisystem](#test-1--großes-dateisystem)
    - [Test 2 – Spezialdateien](#test-2--spezialdateien)
    - [Test 3 – Unregelmäßige Dateien und Verzeichnisse](#test-3--unregelmäßige-dateien-und-verzeichnisse)

---

## So führst du es aus

Wir müssen drei Dinge tun:

1. Eine **Test-Verzeichnisstruktur** erstellen, die gelesen werden soll
2. Das **Docker-Image** für den Scanner bauen (der Python-Code, der das Dateisystem liest)
3. **docker compose** ausführen

Bitte stelle sicher, dass du eine funktionierende **Docker**-Umgebung auf deinem Rechner hast.

---

### Testdaten-Verzeichnis erstellen

Wir erstellen eine Test-Verzeichnisstruktur **lokal** und mounten sie
in den Scanner-Container.

```sh
uv run python src/fs2mq/utils/create_testdata.py  ./data --profile light
```

Falls [**`uv`**](https://docs.astral.sh/uv/getting-started/installation/) auf deinem Rechner
nicht verfügbar ist:

```sh
$ brew install uv
```

für macOS.

Es gibt **drei** verfügbare Testdaten-**Profile**.

| Profil  | Zweck                 | Eigenschaften                               |
|---------|-----------------------|--------------------------------------------|
| `light` | Schneller Sanity-Check | Flacher Baum, wenige kleine Dateien        |
| `deep`  | Stress-/Traversal-Tests | Tiefes Directory-„Spine“, exakte Dateianzahl |
| `edge`  | Robustheitstests       | Symlinks, Berechtigungen, FIFO, komische Namen |

Nach Ausführung des obigen Befehls sollte unter `./data` ein Testdaten-Verzeichnis erstellt sein.

```sh
$ tree ./data
./data
└── level-0-dir-1
    ├── file-1-0.txt
    ├── file-1-1.txt
    └── file-1-2.txt
```

---

### Docker-Image für den Scanner bauen

**Kopiere** `.env.example` nach `.env` und passe Werte bei Bedarf an.

```sh
cp .env.example .env
```

Dann:

```sh
$ docker build --platform=linux/amd64 -t fs2mq:0.1.0 .
```

Prüfe, ob das Image erfolgreich gebaut wurde:

```sh
$ docker images
IMAGE                       ID             DISK USAGE   CONTENT SIZE   EXTRA
fs2mq:0.1.0                 7229c8747137        254MB         65.4MB
```

---

### RabbitMQ und Scanner starten

Starte:

```sh
$ docker compose up -d
```

Prüfe, ob der RabbitMQ-Container läuft:

```sh
$ docker ps -a
CONTAINER ID   IMAGE                       COMMAND                  CREATED          STATUS                      PORTS                                                                                          NAMES
7318e63872b2   fs2mq:0.1.0                 ".venv/bin/python -m…"   45 seconds ago   Exited (3) ...
1df1944d39a2   rabbitmq:4.2.3-management   "docker-entrypoint.s…"   45 seconds ago   Up 45 seconds ....
```

Beachte: Der Scanner-Container (fs2mq) **beendet sich automatisch**, nachdem er
Datei-Metadaten in die RabbitMQ-Queue gesendet hat.

---

## Nachrichten in der RabbitMQ-Web-UI prüfen

### Management-UI öffnen

**Öffne** `http://localhost:15672` und melde dich mit dem Benutzernamen/Passwort an
(die Werte der Umgebungsvariablen `RABBITMQ_USER` und `RABBITMQ_PASS` in der `.env`
im Projekt-Root).

Wenn du nichts in `.env.example` geändert hast:

- User: admin
- Passwort: admin

### Exchange

Wir prüfen, ob Exchange und Queue erstellt wurden.

![Login](./images/login-1.png)

Gehe zu **Exchange** und stelle sicher, dass unten `fs2mq.ingress` vorhanden ist.

![Exchange](./images/exchange-1.png)

### Queue und Nachrichten

Klicke dann auf **Queues and Streams** und finde die neue Queue `files`.

Klicke auf die Queue `files` und finde den Button **Get Message(s)**.

![Get Messages](./images/get-message-1.png)

Dort sollte die erste Nachricht sichtbar sein, die RabbitMQ empfangen hat.

![Messages](./images/message-1.png)

---

## Nachrichten per RabbitMQ-CLI prüfen

Du kannst die Nachrichten auch über die CLI prüfen:

```bash
$ docker exec -it rabbitmq /bin/bash
root@e88f7ddc9610:/# rabbitmqadmin -u admin -p admin get messages -q files -c 10 | sed -n 's/.*│ \(.*path.*\) │.*/\1/p'
{"run_id": "dcb7e0c9-9bfa-4025-b129-b15bacd913ea", "host": "097553a78290", "root": "/data", "path": "/data/edge-cases/weird-names/unicode-äöü.txt", "size": 32, "mtime_epoch": 1770318606}  │ string
{"run_id": "dcb7e0c9-9bfa-4025-b129-b15bacd913ea", "host": "097553a78290", "root": "/data", "path": "/data/edge-cases/weird-names/space name.txt", "size": 32, "mtime_epoch": 1770318606}   │ string
{"run_id": "dcb7e0c9-9bfa-4025-b129-b15bacd913ea", "host": "097553a78290", "root": "/data", "path": "/data/edge-cases/weird-names/brackets-[x].txt", "size": 32, "mtime_epoch": 1770318606} │ string
{"run_id": "dcb7e0c9-9bfa-4025-b129-b15bacd913ea", "host": "097553a78290", "root": "/data", "path": "/data/edge-cases/weird-names/semi;colon.txt", "size": 32, "mtime_epoch": 1770318606}   │ string
{"run_id": "dcb7e0c9-9bfa-4025-b129-b15bacd913ea", "host": "097553a78290", "root": "/data", "path": "/data/level-0-dir-1/file-1-1.txt", "size": 64, "mtime_epoch": 1770341295}              │ string
{"run_id": "dcb7e0c9-9bfa-4025-b129-b15bacd913ea", "host": "097553a78290", "root": "/data", "path": "/data/level-0-dir-1/file-1-0.txt", "size": 64, "mtime_epoch": 1770341295}              │ string
{"run_id": "dcb7e0c9-9bfa-4025-b129-b15bacd913ea", "host": "097553a78290", "root": "/data", "path": "/data/level-0-dir-1/file-1-2.txt", "size": 64, "mtime_epoch": 1770341295}              │ string
{"run_id": "dcb7e0c9-9bfa-4025-b129-b15bacd913ea", "host": "097553a78290", "root": "/data", "path": "/data/level-0-dir-0/file-0-2.txt", "size": 64, "mtime_epoch": 1770341295}              │ string
{"run_id": "dcb7e0c9-9bfa-4025-b129-b15bacd913ea", "host": "097553a78290", "root": "/data", "path": "/data/level-0-dir-0/file-0-1.txt", "size": 64, "mtime_epoch": 1770341295}              │ string
{"run_id": "dcb7e0c9-9bfa-4025-b129-b15bacd913ea", "host": "097553a78290", "root": "/data", "path": "/data/level-0-dir-0/file-0-0.txt", "size": 64, "mtime_epoch": 1770341295}              │ string
root@e88f7ddc9610:/#
```

---

## Parameter

Die Runtime-Parameter für den Scanner (Python-Code `scanner.py`) und RabbitMQ
werden über CLI-Optionen bzw. Umgebungsparameter in der Datei `.env` konfiguriert.

| Komponente | Konfiguration          |
|-----------|-------------------------|
| Scanner   | Kommandozeilenoptionen |
| RabbitMQ  | `.env`                 |

### Scanner

Ein vollständig konfiguriertes Beispiel für die Ausführung auf der Kommandozeile:

```sh
uv run python -m src/fs2mq/scanner.py --root ./data \
                                      --dry-run \
                                      --limit 1024 \
                                      --log-every 100
```

#### `--root PATH` *(erforderlich)*
Root-Verzeichnis, das gescannt werden soll.  
Beispiel: `--root ./data`

- Relative Pfade sind erlaubt.
- Intern wird zu einem absoluten Pfad aufgelöst.

#### `--dry-run (optional)`

- Keine Events an RabbitMQ publishen.
- Events werden als JSON auf stdout ausgegeben.
- Nützlich für Tests und Inspektion.  
Beispiel: `--dry-run`

#### `--limit N (optional)`

- Stoppt nach der Verarbeitung von N Events.
- Zählt erfolgreich verarbeitete Events (Publish oder Dry-Run-Ausgabe).  
Beispiel: `--limit 1000`

#### `--log-every N (optional)`

- Gibt Fortschrittslogs alle N verarbeiteten Events aus.
- Logs werden auf stderr geschrieben.  
Beispiel: `--log-every 100`

### RabbitMQ

```sh
$ cat .env.example

# RabbitMQ (lokal)
RABBITMQ_VHOST=/
RABBITMQ_USER=admin
RABBITMQ_PASS=admin

# Messaging
EXCHANGE=fs2mq.ingress
ROUTING_KEY=file.found
QUEUE_NAME=files

# AMQP URL (URL-encode vhost)
AMQP_URL=amqp://admin:admin@rabbitmq:5672/%2F
```

- Der vhost `/` muss URL-kodiert als `%2F` angegeben werden.
- Bei Docker Compose wird `.env` automatisch gelesen und als Umgebungsvariablen in die Container injiziert.

- Bei lokaler Ausführung ohne Docker wird `.env` **nicht** automatisch geladen (z. B. `source .env` nutzen).
- **Außerdem** solltest du die Variablen in deiner Shell entfernen, wenn du auf RabbitMQ im Docker-Container wechselst.

```sh
# in deiner Shell
$ unset RABBITMQ_VHOST
$ unset RABBITMQ_USER
$ unset RABBITMQ_PASS
$ unset AMQP_URL
```

---

## End-to-End-Test

### Aufräumen und Repo klonen

Zuerst die Entwicklungsumgebung aufräumen:

```sh
$ docker compose down -v
$ docker stop rabbitmq
$ docker rm rabbitmq fs2mq
$ docker network rm fs2mq_default
$ docker volume rm fs-scanner-m3_rabbitmq_data
$ docker volume rm rabbitmq_data
$ docker volume rm fs2mq_rabbitmq_data
$ docker image rm fs2mq:0.1.0 rabbitmq:4.2.3-management
```

Prüfe, ob nichts mehr übrig ist:

```sh
$ docker ps -a
$ docker network ls
$ docker volume ls
$ docker images
```

Lösche Umgebungsvariablen, die in deiner Shell gesetzt sein könnten:

```sh
$ unset RABBITMQ_VHOST
$ unset RABBITMQ_USER
$ unset RABBITMQ_PASS
$ unset AMQP_URL
```

Prüfen:

```sh
$ env  | grep RABBITMQ
$ env  | grep AMQP
```

Zum Copy & Paste:

```sh
docker compose down -v
docker compose stop rabbitmq
docker rm rabbitmq fs2mq
docker network rm fs-scanner-m3_default
docker network rm fs2mq_default
docker volume rm fs-scanner-m3_rabbitmq_data
docker volume rm fs2mq_rabbitmq_data
docker volume rm rabbitmq_data
docker image rm fs2mq:0.1.0 rabbitmq:4.2.3-management

docker ps -a
docker network ls
docker volume ls
docker images

unset RABBITMQ_VHOST
unset RABBITMQ_USER
unset RABBITMQ_PASS
unset AMQP_URL

env  | grep RABBITMQ
env  | grep AMQP
```

**Docker Desktop beenden und neu starten.**

Danach ggf.:

```sh
$ docker login
```

Ein leeres Verzeichnis erstellen:

```sh
$ mkdir ./test
$ cd ./test
$ sudo rm -r ./fs-scanner-m3
```

Repo klonen:

```sh
$ git clone https://github.com/megnergit/fs-scanner-m3.git
```

Prüfen und hinein wechseln:

```sh
$ ls
total 0
drwxr-xr-x  16 meg  staff  512 Feb  6 09:02 fs-scanner-m3
$ cd fs-scanner-m3
```

### Test 1 – Großes Dateisystem

Falls `uv` auf deinem Rechner nicht verfügbar ist:

```sh
$ uv run python src/fs2mq/utils/create_testdata.py \
   ./data --profile deep \
   --depth 64 \
   --target-files 10000
```

Prüfen:

```sh
$ tree ./data | wc
   10067   20133 1568207
```

Für den Rest bitte zurück zu [Docker-Image für den Scanner bauen](#docker-image-für-den-scanner-bauen).

### Test 2 – Spezialdateien

Der einzige Unterschied ist:

```sh
$ uv run python src/fs2mq/utils/create_testdata.py \
   ./data --profile edge
```

Der Rest ist identisch mit [Test 1 – Großes Dateisystem](#test-1--großes-dateisystem).

### Test 3 – Unregelmäßige Dateien und Verzeichnisse

Hier haben wir einen Mix aus Verzeichnissen **ohne Leserechte** und mit Berechtigung.

```sh
sudo rm -rf ./data

mkdir -p ./data/no-permission-dir
touch ./data/no-permission-dir/file-1.txt
chmod 000 ./data/no-permission-dir

mkdir -p ./data/permission-dir
touch ./data/permission-dir/file-2.txt
```

Wird `file-2.txt` in die Queue gesendet?

```sh
$ docker exec -it rabbitmq /bin/bash
# rabbitmqadmin -u admin -p admin get messages -q files -c 1 | sed -n 's/.*│ \(.*path.*\) │.*/\1/p'
{"run_id": "374e8810-402c-4730-8575-fe8b4419a31d", "host": "158cc9d306cb", "root": "/data", "path": "/data/permission-dir/file-2.txt", "size": 0, "mtime_epoch": 1770369894} │ string
```

Alles klar.

Im Fall eines **leeren** Verzeichnisses:

```sh
$ sudo rm -rf ./data
$ mkdir -p ./data/empty-dir

$ mkdir -p ./data/permission-dir
$ touch ./data/permission-dir/file-2.txt
```

Im Fall eines **tricky** Dateinamens:

```sh
sudo rm -rf ./data
touch './data/weird name [;].txt'

mkdir -p ./data/permission-dir
touch ./data/permission-dir/file-2.txt
```

Das haben wir ebenfalls:

```sh
$ docker exec -it rabbitmq /bin/bash
root@dddf5ed3af13:/# rabbitmqadmin -u admin -p admin get messages -q files -c 1 | sed -n 's/.*│ \(.*path.*\) │.*/\1/p'
{"run_id": "9d7a4b90-7d7b-42f0-a6b3-2530b4d54fde", "host": "32b82409ac48", "root": "/data", "path": "/data/weird name [;].txt", "size": 0, "mtime_epoch": 1770370645} │ string
```

---
