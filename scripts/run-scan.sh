#!/usr/bin/env bash
# =============================================================================
# Lance un scan pour un client
# Usage:
#   ./scripts/run-scan.sh <slug> <kind> [--push-thehive] [--push-misp] [params-json]
#
#   kind = full_recon | easm_discovery | easm_http | easm_vuln | easm_crawl
#        | easm_cve | easm_osint | drps_leaks | drps_ail | drps_darkweb | drps_social
#
# Exemples :
#   ./scripts/run-scan.sh acme full_recon --push-thehive --push-misp
#   ./scripts/run-scan.sh acme easm_cve '{"products":["wordpress","apache"]}'
#   ./scripts/run-scan.sh acme drps_darkweb '{"urls":["http://exampleonion.onion"], "proxy":"tor"}'
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
[ -f .env ] && set -a && . ./.env && set +a

API="http://localhost:${ORCHESTRATOR_PORT:-8080}/api/v1"
AUTH="-u ${ORCHESTRATOR_ADMIN_USER:-admin}:${ORCHESTRATOR_ADMIN_PASSWORD:-admin}"

[ "$#" -lt 2 ] && {
  echo "Usage: $0 <slug> <kind> [--push-thehive] [--push-misp] [params-json]"; exit 1; }

SLUG="$1"; KIND="$2"; shift 2
PARAMS="{}"
PUSH_TH=false
PUSH_MISP=false

while [ "$#" -gt 0 ]; do
  case "$1" in
    --push-thehive) PUSH_TH=true ;;
    --push-misp)    PUSH_MISP=true ;;
    *) PARAMS="$1" ;;
  esac
  shift
done

# Merge auto-push flags
PARAMS=$(python3 -c "
import json, sys
p = json.loads('''$PARAMS''')
if '$PUSH_TH'   == 'true': p['auto_push_thehive'] = True
if '$PUSH_MISP' == 'true': p['auto_push_misp']    = True
print(json.dumps(p))
")

PAYLOAD="{\"kind\":\"$KIND\",\"parameters\":$PARAMS}"
echo ">> POST $API/clients/$SLUG/scans"
echo ">> $PAYLOAD"
curl -fsS $AUTH -X POST -H "Content-Type: application/json" \
  "$API/clients/$SLUG/scans" -d "$PAYLOAD" | python3 -m json.tool
