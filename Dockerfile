# syntax=docker/dockerfile:1.7
FROM python:3.12-slim

# ---- no pyc ----
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_NO_CACHE=1 \
    UV_SYSTEM_PYTHON=1

# ---- non root user ----
RUN addgroup --system app && adduser --system --ingroup app --home /app app

WORKDIR /app

# ---- we will use uv ----
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# ---- copy dependency list to app ----
COPY pyproject.toml uv.lock /app/

# ---- install dependencies
RUN uv sync --frozen --no-dev

# ---- copy app ----  
COPY . /app
RUN chown -R app:app /app

USER app

# ---- default is scanner. 
# ---- in the future can use .consumer  as well ----
CMD ["python", "-m", "fs2mq.scanner"]


# ---- END ----