# fs-scanner-m3

## Table of Contents

- [fs-scanner-m3](#fs-scanner-m3)
  - [Table of Contents](#table-of-contents)
  - [How to run](#how-to-run)
    - [Create Test data directory](#create-test-data-directory)
    - [Build docker image for scanner](#build-docker-image-for-scanner)
    - [Run RabbitMQ and scanner](#run-rabbitmq-and-scanner)
  - [Check messages on rabbitmq web UI](#check-messages-on-rabbitmq-web-ui)
    - [Open management UI](#open-management-ui)
    - [Exchange](#exchange)
    - [Queue and messages](#queue-and-messages)
  - [Check messages on rabbitmq CLI](#check-messages-on-rabbitmq-cli)
  - [Parameters](#parameters)
  - [End-to-End test](#end-to-end-test)
    - [Clean up and clone repo](#clean-up-and-clone-repo)
    - [Test 1 - Large file system](#test-1---large-file-system)
    - [Test 2 - Tricky file system](#test-2---tricky-file-system)
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

```python 
uv run python src/fs2mq/utils/create_testdata.py  ./data --profile light
```

If [**`uv`**](https://docs.astral.sh/uv/getting-started/installation/) is 
not available on your machine, 

```sh
$ brew install uv
```

for macos.

There are **three** available test data **profiles.**


| Profile | Purpose | Characteristics |
|---------|---------|-----------------|
| `light` | Quick sanity check | Shallow tree, few small files |
| `deep`  | Stress / traversal tests | Deep directory spine, exact file count |
| `edge`  | Robustness testing | Symlinks, permissions, FIFO, weird names |

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

Check if the Rabbitmq container is running.

```sh 
$ docker ps -a
CONTAINER ID   IMAGE                       COMMAND                  CREATED          STATUS                      PORTS                                                                                          NAMES
7318e63872b2   fs2mq:0.1.0                 ".venv/bin/python -m…"   45 seconds ago   Exited (3) ...
1df1944d39a2   rabbitmq:4.2.3-management   "docker-entrypoint.s…"   45 seconds ago   Up 45 seconds ....
```

Note that the scanner (fs2mq) container **exits** automatically after sending
file metadata to the RabbitMQ queue.

---
## Check messages on rabbitmq web UI

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

There should be the first message that rabbitmq received. 

![Messages](./images/message-1.png)

---
## Check messages on rabbitmq CLI

You can also check messages using the CLI.


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
## Parameters




---
## End-to-End test

### Clean up and clone repo

First clean up the development environment.

```sh
$ docker compose down -v
$ docker stop rabbitmq
$ docker rm rabbitmq fs2mq
$ docker network rm fs2mq_default
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

Create an empty directory.
```sh
$ mkdir ./test
$ cd ./test
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

For the rest please go back to [Build docker image for scanner](#build-docker-image-for-scanner).


### Test 2 - Tricky file system










---
