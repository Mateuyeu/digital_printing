#!/usr/bin/env bash
# =============================================================================
# Lance un scan pour un client
# Usage:
#   ./scripts/run-scan.sh <slug> <kind> [--push-thehive] [--push-misp] [params-json]
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
. "$ROOT/scripts/_lib.sh"

ORCH_PORT="$(env_get ORCHESTRATOR_PORT 8080)"
ORCH_USER="$(env_get ORCHESTRATOR_ADMIN_USER admin)"
ORCH_PWD="$(env_get  ORCHESTRATOR_ADMIN_PASSWORD admin)"
API="http://localhost:${ORCH_PORT}/api/v1"

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

PARAMS=$(PARAMS_JSON="$PARAMS" PUSH_TH="$PUSH_TH" PUSH_MISP="$PUSH_MISP" python3 - <<'PY'
import json, os
p = json.loads(os.environ["PARAMS_JSON"])
if os.environ["PUSH_TH"]   == "true": p["auto_push_thehive"] = True
if os.environ["PUSH_MISP"] == "true": p["auto_push_misp"]    = True
print(json.dumps(p))
PY
)

PAYLOAD="{\"kind\":\"$KIND\",\"parameters\":$PARAMS}"
echo ">> POST $API/clients/$SLUG/scans"
echo ">> $PAYLOAD"
curl -fsS -u "${ORCH_USER}:${ORCH_PWD}" -X POST -H "Content-Type: application/json" \
  "$API/clients/$SLUG/scans" -d "$PAYLOAD" | python3 -m json.tool
