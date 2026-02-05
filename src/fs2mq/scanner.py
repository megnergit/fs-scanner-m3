#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterator, Optional, Tuple

import pika


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


def _now_epoch() -> int:
    return int(time.time())


def _get_host() -> str:
    try:
        return socket.gethostname()
    except Exception:
        return "unknown-host"


# -----------------------------
# Filesystem scan
# -----------------------------

def iter_files(root: Path) -> Iterator[Tuple[Path, os.stat_result]]:
    """
    Recursively iterate regular files under root.

    - Skips symlinks.
    - Handles PermissionError/OSError robustly (continues scan).
    """
    # Use os.walk for robust error callbacks
    def onerror(err: OSError) -> None:
        # Print to stderr but do not crash
        print(f"[WARN] walk error: {err}", file=sys.stderr)

    for dirpath, dirnames, filenames in os.walk(root, onerror=onerror, followlinks=False):
        # Optional: prune unreadable dirs (os.walk already calls onerror)
        # We also protect stat calls below.
        for name in filenames:
            p = Path(dirpath) / name
            try:
                # Skip symlinks explicitly (even if os.walk gives them as files)
                if p.is_symlink():
                    continue
                st = p.stat()
                # Only regular files
                if not os.path.isfile(p):
                    continue
                yield p, st
            except (PermissionError, FileNotFoundError) as e:
                print(f"[WARN] cannot access file {p}: {e}", file=sys.stderr)
                continue
            except OSError as e:
                print(f"[WARN] os error on file {p}: {e}", file=sys.stderr)
                continue


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


def connect(cfg: RabbitConfig) -> Tuple[pika.BlockingConnection, pika.adapters.blocking_connection.BlockingChannel]:
    params = pika.URLParameters(cfg.amqp_url)
    params.heartbeat = 30
    params.blocked_connection_timeout = 60
    # Optional: shorter socket timeouts so failures are detected quickly
    params.socket_timeout = 10

    conn = pika.BlockingConnection(params)
    ch = conn.channel()

    # Enable publisher confirms (robustness)
    ch.confirm_delivery()

    # Declare exchange/queue/binding idempotently
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
        delivery_mode=2,  # persistent
        timestamp=_now_epoch(),
        app_id="fs2mq",
        type="file.found",
    )

    # mandatory=True makes unroutable messages returnable (if no binding)
    # with confirms, basic_publish returns True/False for acked/nacked
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
        # Should not happen if binding exists, but keep robust
        print(f"[ERROR] unroutable message: {e}", file=sys.stderr)
        return False
    except pika.exceptions.AMQPError as e:
        print(f"[ERROR] publish failed: {e}", file=sys.stderr)
        return False


# -----------------------------
# CLI / main
# -----------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="fs2mq: recursively scan a local filesystem and publish file metadata to RabbitMQ"
    )
    p.add_argument(
        "--root",
        type=Path,
        required=True,
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
    return p.parse_args()


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


def main() -> int:
    args = parse_args()
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
            print(f"[ERROR] RabbitMQ connection/declare failed: {e}", file=sys.stderr)
            return 3

    published = 0
    failed = 0
    scanned = 0
    t0 = time.time()

    try:
        for p, st in iter_files(root):
            scanned += 1
            evt = FileEvent(
                run_id=run_id,
                host=host,
                root=str(root),
                path=str(p),
                size=int(st.st_size),
                mtime_epoch=int(st.st_mtime),
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
                print(f"[INFO] published={published} failed={failed} scanned={scanned} rate={rate:.1f}/s", file=sys.stderr)

    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    elapsed = time.time() - t0
    rate = published / elapsed if elapsed > 0 else 0.0
    print(f"[INFO] done run_id={run_id} published={published} failed={failed} scanned={scanned} elapsed={elapsed:.2f}s rate={rate:.1f}/s", file=sys.stderr)

    # non-zero exit if publishing failed for any file (robust signal)
    return 0 if failed == 0 else 4


if __name__ == "__main__":
    raise SystemExit(main())

# -----------------------------
# END
# =============================
