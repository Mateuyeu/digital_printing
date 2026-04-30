# =============================================================================
# LACUS - Capture engine (Playwright + Redis + Tor)
# Build from source : pas d'image officielle publiee.
# https://github.com/ail-project/lacus
#
# Base : image officielle Microsoft Playwright Python (Chromium + deps systeme
# deja installes), ce qui evite de gerer manuellement libnss3/libgbm/etc.
# =============================================================================
FROM mcr.microsoft.com/playwright/python:v1.49.0-noble

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    LACUS_HOME=/lacus

WORKDIR /lacus

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        git \
        curl \
        ca-certificates \
        build-essential \
 && git clone --depth 1 https://github.com/ail-project/lacus.git /tmp/lacus \
 && cp -a /tmp/lacus/. /lacus/ \
 && rm -rf /tmp/lacus \
 && pip install --no-cache-dir 'poetry>=1.8' \
 && poetry install --no-root --without dev \
 && apt-get remove -y build-essential \
 && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*

EXPOSE 7100

CMD ["bash", "-lc", "poetry run update --init && poetry run start"]
