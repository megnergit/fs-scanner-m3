# syntax=docker/dockerfile:1.7
FROM --platform=linux/amd64 python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_NO_CACHE=1 


RUN addgroup --system app && adduser --system --ingroup app --home /app app
WORKDIR /app

# uv (version pinned)
COPY --from=ghcr.io/astral-sh/uv:0.10.0 /uv /usr/local/bin/uv

# dependencies first
COPY pyproject.toml uv.lock README.md /app/

# we need this to let uv sync work
COPY src/ /app/src/

# install actual dependency
RUN uv sync --frozen --no-dev

# copy rest of app code
COPY . /app
RUN chown -R app:app /app
RUN chmod +x /app/docker/entrypoint.sh

# somehow scanner does not wait for rabbitmq
# let shell script wait for rabbitmq

USER app
ENTRYPOINT ["/app/docker/entrypoint.sh"]

CMD ["/app/.venv/bin/python", "-m", "fs2mq.scanner"]
# ---- END ----