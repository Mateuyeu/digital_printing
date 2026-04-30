#!/usr/bin/env bash
# =============================================================================
# Liste les findings d'un client (filtrable)
# Usage:
#   ./scripts/list-findings.sh <slug> [severity] [kind]
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
. "$ROOT/scripts/_lib.sh"

ORCH_PORT="$(env_get ORCHESTRATOR_PORT 8080)"
ORCH_USER="$(env_get ORCHESTRATOR_ADMIN_USER admin)"
ORCH_PWD="$(env_get  ORCHESTRATOR_ADMIN_PASSWORD admin)"
API="http://localhost:${ORCH_PORT}/api/v1"

SLUG="${1:?slug requis}"
QUERY=""
[ -n "${2:-}" ] && QUERY="severity=$2"
[ -n "${3:-}" ] && QUERY="${QUERY:+$QUERY&}kind=$3"

curl -fsS -u "${ORCH_USER}:${ORCH_PWD}" "$API/clients/$SLUG/findings${QUERY:+?$QUERY}" \
  | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(f'== {len(data)} findings ==')
for f in data:
    print(f\"[{f['severity']:<8}] {f['kind']:<22} {f['title'][:70]:<70} ({f['source']})\")
"
