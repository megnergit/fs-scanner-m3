#!/usr/bin/env python3
from __future__ import annotations

import argparse
from importlib.resources import files
import json
import os
import socket
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterator, Optional, Tuple
import traceback

import pika
import hashlib
import pdb

# -----------------------------
# Data model
# -----------------------------

@dataclass(frozen=True)
class FileEvent:
    run_id: str
    host: str
    root: str
    path: str
    size: int
    mtime_epoch: int
    sha256: str    

def _now_epoch() -> int:
    return int(time.time())


def _get_host() -> str:
    try:
        return socket.gethostname()
    except Exception:
        return "unknown-host"

#==============================
# sandbox playground 
#==============================
# for ii, js, ks in os.walk("./data"):
#     print(f"ks = {ks}")
#     for k in ks:
#         print(f"k = {k}")
#         print("=" * 20)
    

# for i in iter_files("./data"):
#     print(i)
    
# -----------------------------
# Filesystem scan
# -----------------------------

def iter_files(root: Path) -> Iterator[Tuple[Path, os.stat_result]]:
    """
    Recursively iterate regular files under root.

    - Skips symlinks.
    - Handles PermissionError/OSError robustly (continues scan).
    """
    def onerror(err: OSError) -> None:
        print(f"[WARN] walk error: {err}", file=sys.stderr)

    for dirpath, dirnames, filenames in os.walk(root, onerror=onerror, 
                                                followlinks=False):
        for name in filenames:
            p = Path(dirpath) / name
            try:
                if p.is_symlink():
                    continue
                st = p.stat()
                if not p.is_file():
                    continue
                yield p, st
            except (PermissionError, FileNotFoundError) as e:
                print(f"[WARN] cannot access file {p}: {e}", file=sys.stderr)
                continue
            except OSError as e:
                print(f"[WARN] os error on file {p}: {e}", file=sys.stderr)
                continue

# -----------------------------
# Calculate file hash (optional, can be expensive)
# -----------------------------

def calc_sha256(p: Path, buf_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        while True:
            chunk = f.read(buf_size) # read 1M byte (stream hash)
                                     # to protect memory
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()

# -----------------------------
# RabbitMQ
# -----------------------------

@dataclass(frozen=True)
class RabbitConfig:
    amqp_url: str
    exchange: str
    routing_key: str
    queue_name: str
    durable: bool = True


# ==============================
# Sandbox playground for RabbitMQ connection and publish
# -----------------------------

cfg = RabbitConfig(
    amqp_url="amqp://admin:admin@localhost:5672/%2F",
    exchange="fs2mq.ingress",
    routing_key="file.found",
    queue_name="files",
    durable=True,
    )


x = connect(cfg)

# ==============================
def connect(cfg: RabbitConfig) -> Tuple[pika.BlockingConnection, 
                                        pika.adapters.blocking_connection.BlockingChannel]:
    params = pika.URLParameters(cfg.amqp_url)
    params.heartbeat = 30
    params.blocked_connection_timeout = 60
    params.socket_timeout = 10

    conn = pika.BlockingConnection(params)
    ch = conn.channel()

    ch.confirm_delivery()

    ch.exchange_declare(exchange=cfg.exchange, exchange_type="direct", durable=cfg.durable)
    ch.queue_declare(queue=cfg.queue_name, durable=cfg.durable)
    ch.queue_bind(queue=cfg.queue_name, exchange=cfg.exchange, routing_key=cfg.routing_key)

    return conn, ch


def publish_file_event(
    ch: pika.adapters.blocking_connection.BlockingChannel,
    cfg: RabbitConfig,
    event: FileEvent,
) -> bool:
    body = json.dumps(asdict(event), ensure_ascii=False).encode("utf-8")

    props = pika.BasicProperties(
        content_type="application/json",
        delivery_mode=2,
        timestamp=_now_epoch(),
        app_id="fs2mq",
        type="file.found",
    )

    try:
        ok = ch.basic_publish(
            exchange=cfg.exchange,
            routing_key=cfg.routing_key,
            body=body,
            properties=props,
            mandatory=True,
        )
        return bool(ok)
    except pika.exceptions.UnroutableError as e:
        print(f"[ERROR] unroutable message: {e}", file=sys.stderr)
        return False
    except pika.exceptions.AMQPError as e:
        print(f"[ERROR] publish failed: {e}", file=sys.stderr)
        return False


# -----------------------------
# CLI
# -----------------------------

def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        description="fs2mq scanner: recursively scan a local filesystem and publish file metadata to RabbitMQ",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show this help
  uv run python src/fs2mq/scanner.py

  # Dry-run (print events as JSON lines)
  uv run python src/fs2mq/scanner.py --root ./data --dry-run --limit 10

  # Publish to RabbitMQ (requires env vars)
  AMQP_URL=amqp://... EXCHANGE=... ROUTING_KEY=... QUEUE_NAME=... \\
    uv run python src/fs2mq/scanner.py --root ./data --log-every 100

Environment variables (required unless --dry-run):
  AMQP_URL     AMQP URL, e.g. amqp://user:pass@host:5672/vhost
  EXCHANGE     Exchange name (direct)
  ROUTING_KEY  Routing key for publishing
  QUEUE_NAME   Queue name to bind

Exit codes:
  0 = success
  2 = invalid usage / missing env / bad --root
  3 = RabbitMQ connect/declare failure
  4 = publishing had failures for some files
""",
    )


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    p = build_parser()
    p.add_argument(
        "--root",
        type=Path,
        required=False,  # allow empty invocation -> show help
        help="Root directory to scan (will be scanned recursively)",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional limit for number of files to publish (0 = no limit)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan and print events but do not publish to RabbitMQ",
    )
    p.add_argument(
        "--log-every",
        type=int,
        default=100,
        help="Print progress every N published files (default: 100)",
    )
    return p.parse_args(argv)


def load_rabbit_cfg_from_env() -> RabbitConfig:
    def must(name: str) -> str:
        v = os.environ.get(name)
        if not v:
            raise RuntimeError(f"Missing required env var: {name}")
        return v

    return RabbitConfig(
        amqp_url=must("AMQP_URL"),
        exchange=must("EXCHANGE"),
        routing_key=must("ROUTING_KEY"),
        queue_name=must("QUEUE_NAME"),
        durable=True,
    )


# -----------------------------
# main
# -----------------------------

def main() -> int:
    parser = build_parser()
    args = parse_args()

    # If called without args (especially without --root), show help and exit 0.
    if args.root is None:
        parser.print_help()
        return 0

    root = args.root.resolve()

    if not root.exists():
        print(f"[ERROR] root does not exist: {root}", file=sys.stderr)
        return 2
    if not root.is_dir():
        print(f"[ERROR] root is not a directory: {root}", file=sys.stderr)
        return 2

    run_id = str(uuid.uuid4())
    host = _get_host()

    cfg: Optional[RabbitConfig] = None
    conn: Optional[pika.BlockingConnection] = None
    ch: Optional[pika.adapters.blocking_connection.BlockingChannel] = None

    if not args.dry_run:
        try:
            cfg = load_rabbit_cfg_from_env()
        except RuntimeError as e:
            print(f"[ERROR] {e}", file=sys.stderr)
            return 2

        try:
            conn, ch = connect(cfg)

        except Exception as e:
            print(f"[ERROR] RabbitMQ connection/declare failed: {type(e).__name__}: {e!r}", file=sys.stderr)
            return 3



    published = 0
    failed = 0
    scanned = 0
    t0 = time.time()

    try:
        for p, st in iter_files(root):
            scanned += 1

            if args.dry_run:
                sha256 = "DRY_RUN"
            else:
                try:
                    sha256 = calc_sha256(p)
                except (PermissionError, FileNotFoundError) as e:
                    # cannot read, or somehow interrupted
                    print(f"[WARN] cannot read file for sha256 {p}: {e}", file=sys.stderr)
                    failed += 1
                    continue
                except OSError as e:
                    print(f"[WARN] os error while hashing {p}: {e}", file=sys.stderr)
                    failed += 1
                    continue

            evt = FileEvent(
                run_id=run_id,
                host=host,
                root=str(root),
                path=str(p),
                size=int(st.st_size),
                mtime_epoch=int(st.st_mtime),
                sha256=sha256,                    
            )

            if args.dry_run:
                print(json.dumps(asdict(evt), ensure_ascii=False))
                published += 1
            else:
                assert cfg is not None and ch is not None
                ok = publish_file_event(ch, cfg, evt)
                if ok:
                    published += 1
                else:
                    failed += 1

            if args.limit and published >= args.limit:
                break

            if args.log_every > 0 and published > 0 and (published % args.log_every == 0):
                elapsed = time.time() - t0
                rate = published / elapsed if elapsed > 0 else 0.0
                print(
                    f"[INFO] published={published} failed={failed} scanned={scanned} rate={rate:.1f}/s",
                    file=sys.stderr,
                )

    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    elapsed = time.time() - t0
    rate = published / elapsed if elapsed > 0 else 0.0
    print(
        f"[INFO] done run_id={run_id} published={published} failed={failed} scanned={scanned} "
        f"elapsed={elapsed:.2f}s rate={rate:.1f}/s",
        file=sys.stderr,
    )

    return 0 if failed == 0 else 4


if __name__ == "__main__":
    raise SystemExit(main())

# -----------------------------
# END
# -----------------------------
