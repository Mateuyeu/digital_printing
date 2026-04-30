#!/usr/bin/env bash
# =============================================================================
# Genere un rapport HTML/PDF pour un client
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
. "$ROOT/scripts/_lib.sh"

ORCH_PORT="$(env_get ORCHESTRATOR_PORT 8080)"
ORCH_USER="$(env_get ORCHESTRATOR_ADMIN_USER admin)"
ORCH_PWD="$(env_get  ORCHESTRATOR_ADMIN_PASSWORD admin)"
API="http://localhost:${ORCH_PORT}/api/v1"

[ "$#" -lt 1 ] && { echo "Usage: $0 <slug> [days|--list|--download <id>] [title]"; exit 1; }
SLUG="$1"; shift

case "${1:-}" in
  --list)
    curl -fsS -u "${ORCH_USER}:${ORCH_PWD}" "$API/clients/$SLUG/reports" | python3 -m json.tool
    ;;
  --download)
    [ "$#" -lt 2 ] && { echo "Usage: $0 $SLUG --download <id>"; exit 1; }
    OUT="reports/output/${SLUG}-report-$2.pdf"
    mkdir -p reports/output
    curl -fsS -u "${ORCH_USER}:${ORCH_PWD}" "$API/clients/$SLUG/reports/$2/pdf" -o "$OUT"
    echo "downloaded: $OUT"
    ;;
  *)
    DAYS="${1:-30}"
    TITLE="${2:-}"
    PAYLOAD=$(DAYS="$DAYS" TITLE="$TITLE" python3 - <<'PY'
import json, os
out = {"period_days": int(os.environ["DAYS"]), "include_easm": True,
       "include_drps": True, "push_pdf": True}
if os.environ["TITLE"]:
    out["title"] = os.environ["TITLE"]
print(json.dumps(out))
PY
)
    echo ">> POST $API/clients/$SLUG/reports"
    curl -fsS -u "${ORCH_USER}:${ORCH_PWD}" -X POST -H "Content-Type: application/json" \
      "$API/clients/$SLUG/reports" -d "$PAYLOAD" | python3 -m json.tool
    echo
    echo "Rapport en cours de generation. Suivre avec :"
    echo "  $0 $SLUG --list"
    ;;
esac
