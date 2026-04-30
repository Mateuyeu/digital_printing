#!/usr/bin/env bash
# =============================================================================
# Liste les findings d'un client (filtrable)
# Usage:
#   ./scripts/list-findings.sh <slug> [severity] [kind]
#   ./scripts/list-findings.sh acme critical
#   ./scripts/list-findings.sh acme high vulnerability
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
[ -f .env ] && set -a && . ./.env && set +a

API="http://localhost:${ORCHESTRATOR_PORT:-8080}/api/v1"
AUTH="-u ${ORCHESTRATOR_ADMIN_USER:-admin}:${ORCHESTRATOR_ADMIN_PASSWORD:-admin}"

SLUG="${1:?slug requis}"
QUERY=""
[ -n "${2:-}" ] && QUERY="severity=$2"
[ -n "${3:-}" ] && QUERY="${QUERY:+$QUERY&}kind=$3"

curl -fsS $AUTH "$API/clients/$SLUG/findings${QUERY:+?$QUERY}" \
  | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(f'== {len(data)} findings ==')
for f in data:
    print(f\"[{f['severity']:<8}] {f['kind']:<22} {f['title'][:70]:<70} ({f['source']})\")
"
