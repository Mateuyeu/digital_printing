# =============================================================================
# SpiderFoot - OSINT & EASM
# Build from source : pas d'image officielle publiee sur GHCR/Docker Hub.
# https://github.com/smicallef/spiderfoot
# =============================================================================
FROM python:3.11-slim

ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /home/spiderfoot

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        git \
        gcc \
        swig \
        libxml2-dev \
        libxslt1-dev \
        libssl-dev \
        cargo \
        curl \
        ca-certificates \
        bash \
 && git clone --depth 1 https://github.com/smicallef/spiderfoot.git /tmp/sf \
 && cp -a /tmp/sf/. /home/spiderfoot/ \
 && pip install --no-cache-dir -r requirements.txt \
 && apt-get remove -y gcc swig libxml2-dev libxslt1-dev libssl-dev cargo git \
 && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/* /tmp/sf

EXPOSE 5001

CMD ["python", "./sf.py", "-l", "0.0.0.0:5001"]
