# =============================================================================
# theHarvester scanner image
# =============================================================================
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        git \
        curl \
        ca-certificates \
        chromium \
        chromium-driver \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt
RUN git clone --depth 1 https://github.com/laramies/theHarvester.git \
 && cd theHarvester \
 && pip install --no-cache-dir -r requirements/base.txt \
 && pip install --no-cache-dir .

WORKDIR /scan

ENTRYPOINT ["theHarvester"]
CMD ["-h"]
