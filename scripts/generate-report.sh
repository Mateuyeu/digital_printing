#!/usr/bin/env bash
# =============================================================================
# Genere un rapport HTML/PDF pour un client
# Usage:
#   ./scripts/generate-report.sh <slug> [days] [title]
#   ./scripts/generate-report.sh acme 30 "Rapport mensuel ACME"
#   ./scripts/generate-report.sh acme --list           -- lister les rapports
#   ./scripts/generate-report.sh acme --download <id>  -- telecharger un PDF
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
[ -f .env ] && set -a && . ./.env && set +a

API="http://localhost:${ORCHESTRATOR_PORT:-8080}/api/v1"
AUTH="-u ${ORCHESTRATOR_ADMIN_USER:-admin}:${ORCHESTRATOR_ADMIN_PASSWORD:-admin}"

[ "$#" -lt 1 ] && { echo "Usage: $0 <slug> [days|--list|--download <id>] [title]"; exit 1; }
SLUG="$1"; shift

case "${1:-}" in
  --list)
    curl -fsS $AUTH "$API/clients/$SLUG/reports" | python3 -m json.tool
    ;;
  --download)
    [ "$#" -lt 2 ] && { echo "Usage: $0 $SLUG --download <id>"; exit 1; }
    OUT="reports/output/${SLUG}-report-$2.pdf"
    mkdir -p reports/output
    curl -fsS $AUTH "$API/clients/$SLUG/reports/$2/pdf" -o "$OUT"
    echo "downloaded: $OUT"
    ;;
  *)
    DAYS="${1:-30}"
    TITLE="${2:-}"
    PAYLOAD=$(python3 -c "
import json
out = {'period_days': int('$DAYS'), 'include_easm': True, 'include_drps': True, 'push_pdf': True}
if '$TITLE': out['title'] = '$TITLE'
print(json.dumps(out))
")
    echo ">> POST $API/clients/$SLUG/reports"
    curl -fsS $AUTH -X POST -H "Content-Type: application/json" \
      "$API/clients/$SLUG/reports" -d "$PAYLOAD" | python3 -m json.tool
    echo
    echo "Rapport en cours de generation. Suivre avec :"
    echo "  $0 $SLUG --list"
    ;;
esac
