#!/bin/sh
set -eu

# for dry-run we do not wait for rabbitmq
# if [ "${DRY_RUN:-0}" != "1" ]; then

host="${AMQP_HOST:-rabbitmq}"
port="${AMQP_PORT:-5672}"

echo "[INFO] waiting for ${host}:${port}..."

# small python code
python - <<'PY'
import socket, time, os
host = os.environ.get("AMQP_HOST", "rabbitmq")
port = int(os.environ.get("AMQP_PORT", "5672"))
while True:
    try:
        with socket.create_connection((host, port), timeout=1):
            break
    except OSError:
        time.sleep(1)
print("[INFO] rabbitmq is up.")
PY

# exec the main command
exec "$@"
