# =============================================================================
# ProjectDiscovery scanner image
# Contient: httpx, nuclei, naabu, katana, cvemap, subfinder, dnsx
# =============================================================================
FROM golang:1.22-alpine AS builder

RUN apk add --no-cache git build-base libpcap-dev

ENV GOFLAGS="-buildvcs=false" \
    CGO_ENABLED=1

# Project Discovery tools
RUN go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest \
 && go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest \
 && go install -v github.com/projectdiscovery/naabu/v2/cmd/naabu@latest \
 && go install -v github.com/projectdiscovery/katana/cmd/katana@latest \
 && go install -v github.com/projectdiscovery/cvemap/cmd/cvemap@latest \
 && go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest \
 && go install -v github.com/projectdiscovery/dnsx/cmd/dnsx@latest

# -----------------------------------------------------------------------------
FROM alpine:3.20

RUN apk add --no-cache \
        ca-certificates \
        libpcap \
        chromium \
        bash \
        curl \
        jq \
        tzdata

COPY --from=builder /go/bin/httpx     /usr/local/bin/httpx
COPY --from=builder /go/bin/nuclei    /usr/local/bin/nuclei
COPY --from=builder /go/bin/naabu     /usr/local/bin/naabu
COPY --from=builder /go/bin/katana    /usr/local/bin/katana
COPY --from=builder /go/bin/cvemap    /usr/local/bin/cvemap
COPY --from=builder /go/bin/subfinder /usr/local/bin/subfinder
COPY --from=builder /go/bin/dnsx      /usr/local/bin/dnsx

# Pre-fetch nuclei templates (cache invalided by build arg)
ARG TEMPLATES_REFRESH=2026-04-30
RUN nuclei -update-templates -ut -silent || true

WORKDIR /scan

ENTRYPOINT ["/bin/bash", "-c"]
CMD ["echo 'projectdiscovery scanner image ready - httpx, nuclei, naabu, katana, cvemap, subfinder, dnsx'"]
