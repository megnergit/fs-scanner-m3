# fs-scanner-m3

Filesystem scanner that detects file system events and publishes them to a message queue (RabbitMQ).

This project focuses on **safe, reproducible, and observable** event publishing from a filesystem into a messaging pipeline.

---

## Table of Contents

- [fs-scanner-m3](#fs-scanner-m3)
  - [Table of Contents](#table-of-contents)
  - [How to run](#how-to-run)
    - [Create Test data directory](#create-test-data-directory)
    - [Build docker image for scanner](#build-docker-image-for-scanner)
    - [Run rabbitMQ and scanner](#run-rabbitmq-and-scanner)
  - [Check messages on rabbitmq web UI](#check-messages-on-rabbitmq-web-ui)
  - [Check messages on rabbitmq CLI](#check-messages-on-rabbitmq-cli)

---
## How to run 

We have to do 3 things. 

1. Create test directory structure to read
2. Build docker image for scanner (= python code that read the file system)
3. Run docker compose

Please make sure you have docker execution environment on your machine. 

---
### Create Test data directory  



```python 
uv run python src/fs2mq/utils/create_testdata.py  ./data --profile light
```

We have 3 profiles for testdata. 

| Profile | Purpose | Characteristics |
|---------|---------|-----------------|
| `light` | Quick sanity check | Shallow tree, few small files |
| `deep` | Stress / traversal tests | Deep directory spine, exact file count |
| `edge` | Robustness testing | Symlinks, permissions, FIFO, weird names |


After executing the command above, we should see test data directory at ```./data```
```sh
$ tree ./data
./data
└── level-0-dir-1
    ├── file-1-0.txt
    ├── file-1-1.txt
    └── file-1-2.txt
```

---
### Build docker image for scanner

Copy `.env.example` to `.env` and adjust the values as needed:

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
### Run rabbitMQ and scanner 

Run 

```sh
$ docker compose up -d
```

Check if the rabbitmq container is running.
```sh 
$ docker ps -a
CONTAINER ID   IMAGE                       COMMAND                  CREATED          STATUS                      PORTS                                                                                          NAMES
7318e63872b2   fs2mq:0.1.0                 ".venv/bin/python -m…"   45 seconds ago   Exited (3) ...
1df1944d39a2   rabbitmq:4.2.3-management   "docker-entrypoint.s…"   45 seconds ago   Up 45 seconds ....
```

Note that the scanner (fs2mq) has already exited after sending file metadata to a rabbitmq queue. 

---
## Check messages on rabbitmq web UI

First check if the exchange and queue have been created. 

Open ```localhost:15672``` and log in with user name (= the value of the environment 
variable ```RABBITMQ_USER``` and ```RABBITMQ_PASS```  in ```.env``` at the project root).

![Login](./images/login-1.png)

Go to "Exchange" and make sure that there is ```fs2mq.ingress``` at the bottom. 

![Exchange](./images/exchange-1.png)

Then click on "Queues and Streams", and find a new queue `files`.

Click on the queue `files`, and find "Get Message(s) button.  

![Get Messages](./images/get-message-1.png)

There should be the first message that rabbitmq received. 

![Messages](./images/message-1.png)

--

---
## Check messages on rabbitmq CLI

One can also check with CLI. 

```bash
$ docker exec -it rabbitmq /bin/bash
root@e88f7ddc9610:/# rabbitmqadmin -u admin -p admin -q files -c 10 | sed -n 's/.*│ \(.*path.*\) │.*/\1/p'
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
