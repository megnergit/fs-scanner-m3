# fs-scanner-m3

## Table of Contents

- [fs-scanner-m3](#fs-scanner-m3)
  - [Table of Contents](#table-of-contents)
  - [How to run](#how-to-run)
    - [Create Test data directory](#create-test-data-directory)
    - [Build Docker image for scanner](#build-docker-image-for-scanner)
    - [Run RabbitMQ and scanner](#run-rabbitmq-and-scanner)
  - [Check messages on RabbitMQ web UI](#check-messages-on-rabbitmq-web-ui)
    - [Open management UI](#open-management-ui)
    - [Exchange](#exchange)
    - [Queue and messages](#queue-and-messages)
  - [Check messages on RabbitMQ CLI](#check-messages-on-rabbitmq-cli)
  - [Parameters](#parameters)
    - [Scanner](#scanner)
      - [`--root PATH` *(required)*](#--root-path-required)
      - [`--dry-run (optional)`](#--dry-run-optional)
      - [`--limit N (optional)`](#--limit-n-optional)
      - [`--log-every N (optional)`](#--log-every-n-optional)
    - [RabbitMQ](#rabbitmq)
  - [End-to-End test](#end-to-end-test)
    - [Clean up and clone repo](#clean-up-and-clone-repo)
    - [Test 1 - Large file system](#test-1---large-file-system)
    - [Test 2 - Special files](#test-2---special-files)
    - [Test 3 - Irregular files and directories](#test-3---irregular-files-and-directories)

---
## How to run 

We need to do 3 things. 

1. Create **test directory** structure to read
2. Build the **Docker image** for the scanner (the Python code that reads the file system)
3. Run **docker compose**

Please make sure you have a working **Docker** environment on your machine.

---
### Create Test data directory  

We will create a test directory structure **locally** and mount it 
into the scanner container.

```sh
uv run python src/fs2mq/utils/create_testdata.py  ./data --profile light
```

If [**`uv`**](https://docs.astral.sh/uv/getting-started/installation/) is 
not available on your machine, 

```sh
$ brew install uv
```

for macOS.

There are **three** available test data **profiles.**




| Profile | Purpose | Characteristics |
|---------|---------|-----------------|
| `light` | Quick sanity check | Shallow tree, few small files |
| `deep`  | Stress / traversal tests | Deep directory spine, exact file count |
| `edge`  | Robustness testing | Symlinks, permissions, FIFO, weird names |


After executing the command above, a test data directory should be created at `./data`.

```sh
$ tree ./data
./data
└── level-0-dir-1
    ├── file-1-0.txt
    ├── file-1-1.txt
    └── file-1-2.txt
```

---
### Build Docker image for scanner

**Copy** `.env.example` to `.env` and adjust values if needed.

```sh
cp .env.example .env
```

Then run,

```sh
$ docker build --platform=linux/amd64 -t fs2mq:0.1.0 .
```

Check if the image is successfully built. 

```sh
$ docker images
IMAGE                       ID             DISK USAGE   CONTENT SIZE   EXTRA
fs2mq:0.1.0                 7229c8747137        254MB         65.4MB
```

---
### Run RabbitMQ and scanner 

Run 

```sh
$ docker compose up -d
```

Check if the RabbitMQ container is running.

```sh 
$ docker ps -a
CONTAINER ID   IMAGE                       COMMAND                  CREATED          STATUS                      PORTS                                                                                          NAMES
7318e63872b2   fs2mq:0.1.0                 ".venv/bin/python -m…"   45 seconds ago   Exited (3) ...
1df1944d39a2   rabbitmq:4.2.3-management   "docker-entrypoint.s…"   45 seconds ago   Up 45 seconds ....
```

Note that the scanner (fs2mq) container **exits** automatically after sending
file metadata to the RabbitMQ queue.

---
## Check messages on RabbitMQ web UI

### Open management UI

**Open** `http://localhost:15672` and log in with the username
(the values of the environment variables
```RABBITMQ_USER``` and ```RABBITMQ_PASS```  in ```.env``` at the project root).

If you did not change anything in `.env.example`, 

- User: admin
- Password: admin

### Exchange

We will check if the exchange and queue have been created. 

![Login](./images/login-1.png)

Go to **Exchange** and make sure that there is ```fs2mq.ingress``` at the bottom. 

![Exchange](./images/exchange-1.png)

### Queue and messages

Then click on **Queues and Streams**, and find a new queue `files`.

Click on the queue `files`, and find **Get Message(s)** button.  

![Get Messages](./images/get-message-1.png)

There should be the first message that RabbitMQ received. 

![Messages](./images/message-1.png)

---
## Check messages on RabbitMQ CLI

You can also check messages using the CLI.


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
## Parameters

The runtime parameters for the scanner ('scanner.py' python code) and RabbitMQ 
are configured by CLI options and the environment parameters in ```.env``` file, 
respectively. 

| Component  | Configuration             | 
|------------|---------------------------|
| Scanner    | command line options.     |
| RabbitMQ   | ```.env```                | 

### Scanner

A fully configured example to run code at the command line.

```sh
uv run python -m src/fs2mq/scanner.py --root ./data \
                                      --dry-run \
                                      --limit 1024 \
                                      --log-every 100

```

#### `--root PATH` *(required)*
Root directory to scan.
example:  ```--root ./data```

* Relative paths are allowed.
* Internally resolved to an absolute path.

#### `--dry-run (optional)`

* Do not publish events to RabbitMQ.
* Events are printed as JSON to stdout.
* Useful for testing and inspection.
example: ```--dry-run```


#### `--limit N (optional)`
* Stop after processing N events.
* Counts successfully processed events (publish or dry-run output).
example: ```--limit 1000```


#### `--log-every N (optional)`
* Print progress logs every N processed events.
* Logs are written to stderr.
example: ```--log-every 100```

### RabbitMQ

```sh
$ cat .env.example

# RabbitMQ (local)
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
* The vhost / must be URL-encoded as %2F.
* When using Docker Compose, ```.env``` is read automatically and injected into the container environment.

* When running locally without Docker, ```.env``` is **not** loaded automatically (use source .env, etc.).
* **AND** unset them on your shell when you switch to RabbitMQ running in a Docker container.

```sh: on your shell 
$ unset RABBITMQ_VHOST
$ unset RABBITMQ_USER
$ unset RABBITMQ_PASS
$ unset AMQP_URL
```

---
## End-to-End test

### Clean up and clone repo

First clean up the development environment.

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

Check nothing left.
```sh
$ docker ps -a
$ docker network ls
$ docker volume ls
$ docker images
```


Delete environment variables that might be set on your shell.

```sh
$ unset RABBITMQ_VHOST
$ unset RABBITMQ_USER
$ unset RABBITMQ_PASS
$ unset AMQP_URL
```

Check. 

```sh
$ env  | grep RABBITMQ
$ env  | grep AMQP
```

For cut and paste. 

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

**Quit Docker Desktop and start again.**


After that 
```sh
$ docker login
```
if needed. 

Create an empty directory.
```sh
$ mkdir ./test
$ cd ./test
$ sudo rm -r ./fs-scanner-m3
```

Pull the git repo.
```sh
$ git clone https://github.com/megnergit/fs-scanner-m3.git
```

Check and get into it.
```sh
$ ls
total 0
drwxr-xr-x  16 meg  staff  512 Feb  6 09:02 fs-scanner-m3
$ cd fs-scanner-m3
```

### Test 1 - Large file system

If `uv` is not available on your machine, 


```sh
$ uv run python src/fs2mq/utils/create_testdata.py \
   ./data --profile deep \
   --depth 64 \
   --target-files 10000
```

Check. 
```sh
$ tree ./data | wc
   10067   20133 1568207
```

For the rest please go back to [Build Docker image for scanner](#build-docker-image-for-scanner).

### Test 2 - Special files

Only difference is 

```sh
$ uv run python src/fs2mq/utils/create_testdata.py \
   ./data --profile edge 
```

The rest is same with [Test 1 - Large file system](#test-1---large-file-system).

### Test 3 - Irregular files and directories

In the case we have a mix of directories of  **no read permission**
and with a permission. 

```sh
sudo rm -rf ./data

mkdir -p ./data/no-permission-dir
touch ./data/no-permission-dir/file-1.txt
chmod 000 ./data/no-permission-dir

mkdir -p ./data/permission-dir
touch ./data/permission-dir/file-2.txt
```

Do we have `file-2.txt` sent to queue?

```sh
$ docker exec -it rabbitmq /bin/bash
# rabbitmqadmin -u admin -p admin get messages -q files -c 1 | sed -n 's/.*│ \(.*path.*\) │.*/\1/p'
{"run_id": "374e8810-402c-4730-8575-fe8b4419a31d", "host": "158cc9d306cb", "root": "/data", "path": "/data/permission-dir/file-2.txt", "size": 0, "mtime_epoch": 1770369894} │ string
```
All right.


In the case of **empty** directory.

```sh
$ sudo rm -rf ./data
$ mkdir -p ./data/empty-dir

$ mkdir -p ./data/permission-dir
$ touch ./data/permission-dir/file-2.txt
```

In the case of **tricky** filename. 

```sh
sudo rm -rf ./data
touch './data/weird name [;].txt'

mkdir -p ./data/permission-dir
touch ./data/permission-dir/file-2.txt
```

We have this one as well. 

```sh
$ docker exec -it rabbitmq /bin/bash
root@dddf5ed3af13:/# rabbitmqadmin -u admin -p admin get messages -q files -c 1 | sed -n 's/.*│ \(.*path.*\) │.*/\1/p'
{"run_id": "9d7a4b90-7d7b-42f0-a6b3-2530b4d54fde", "host": "32b82409ac48", "root": "/data", "path": "/data/weird name [;].txt", "size": 0, "mtime_epoch": 1770370645} │ string
```

---
