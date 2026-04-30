# =============================================================================
# ProjectDiscovery scanner image
# Contient: httpx, nuclei, naabu, katana, cvemap, subfinder, dnsx
# Base debian (et non alpine) car certaines deps PD ont des soucis avec musl.
# =============================================================================
FROM golang:1.25-bookworm AS builder

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        git \
        build-essential \
        libpcap-dev \
        ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# GOTOOLCHAIN=auto : si un module exige Go > 1.25, Go telecharge la toolchain
# requise automatiquement (evite de devoir bumper l'image a chaque release PD).
ENV GOFLAGS="-buildvcs=false" \
    CGO_ENABLED=1 \
    GOTOOLCHAIN=auto

# Chaque install en couche separee : meilleur cache et diagnostic clair en cas
# d'echec d'un seul outil.
RUN go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest
RUN go install -v github.com/projectdiscovery/dnsx/cmd/dnsx@latest
RUN go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest
RUN go install -v github.com/projectdiscovery/naabu/v2/cmd/naabu@latest
RUN go install -v github.com/projectdiscovery/katana/cmd/katana@latest
RUN go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest
RUN go install -v github.com/projectdiscovery/cvemap/cmd/cvemap@latest

# -----------------------------------------------------------------------------
FROM debian:bookworm-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        ca-certificates \
        libpcap0.8 \
        chromium \
        bash \
        curl \
        jq \
        tzdata \
 && rm -rf /var/lib/apt/lists/*

COPY --from=builder /go/bin/httpx     /usr/local/bin/httpx
COPY --from=builder /go/bin/nuclei    /usr/local/bin/nuclei
COPY --from=builder /go/bin/naabu     /usr/local/bin/naabu
COPY --from=builder /go/bin/katana    /usr/local/bin/katana
COPY --from=builder /go/bin/cvemap    /usr/local/bin/cvemap
COPY --from=builder /go/bin/subfinder /usr/local/bin/subfinder
COPY --from=builder /go/bin/dnsx      /usr/local/bin/dnsx

# Pre-fetch nuclei templates (cache invalide par build arg)
ARG TEMPLATES_REFRESH=2026-04-30
RUN nuclei -update-templates -ut -silent || true

WORKDIR /scan

ENTRYPOINT ["/bin/bash", "-c"]
CMD ["echo 'projectdiscovery scanner image ready - httpx, nuclei, naabu, katana, cvemap, subfinder, dnsx'"]
