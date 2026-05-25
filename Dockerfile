# syntax=docker/dockerfile:1.7

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates git \
    && rm -rf /var/lib/apt/lists/* \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && ln -s /root/.local/bin/uv /usr/local/bin/uv

WORKDIR /app

# deps cache layer
COPY pyproject.toml uv.lock* ./
RUN uv venv && uv sync --frozen --no-install-project 2>/dev/null || uv sync --no-install-project

# kreports
RUN uv pip install --no-cache "git+https://github.com/capitalparser/kreports-dart-mcp.git" || \
    echo "kreports install skipped"

# source
COPY data ./data
COPY utils ./utils
COPY signals ./signals
COPY bot.py alert_server.py ./
RUN uv pip install --no-cache .

# ticker cache — populated at runtime by scheduler (07:00 KST)
RUN mkdir -p /app/cache

ENV PORT=8080

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
  CMD python -c "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3).status==200 else 1)"

CMD ["uv", "run", "python", "bot.py"]
