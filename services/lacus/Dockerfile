# =============================================================================
# LACUS - Capture engine (Playwright + Redis + Tor)
# Build from source : pas d'image officielle publiee.
# https://github.com/ail-project/lacus
# =============================================================================
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    LACUS_HOME=/lacus \
    PATH=/lacus/.venv/bin:$PATH

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        git \
        curl \
        ca-certificates \
        build-essential \
        libnss3 libxss1 libasound2 libxrandr2 libxkbcommon0 libxcomposite1 \
        libxdamage1 libgbm1 libcairo2 libpango-1.0-0 libatk1.0-0 \
        libatk-bridge2.0-0 libgtk-3-0 \
        fonts-noto-color-emoji fonts-noto-cjk \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /lacus
RUN git clone --depth 1 https://github.com/ail-project/lacus.git /tmp/lacus \
 && cp -a /tmp/lacus/. /lacus/ \
 && rm -rf /tmp/lacus

RUN pip install --no-cache-dir poetry==1.8.5 \
 && poetry config virtualenvs.in-project true \
 && poetry install --no-root --without dev \
 && poetry run playwright install --with-deps chromium

EXPOSE 7100

CMD ["bash", "-lc", "poetry run update --init && poetry run start"]
