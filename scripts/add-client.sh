#!/usr/bin/env bash
# =============================================================================
# Cree un client (tenant) et ajoute ses scopes
# Usage:
#   ./scripts/add-client.sh <slug> <nom> [contact_email]
#   ./scripts/add-client.sh <slug> --add-scope <kind> <value> [note]
#   ./scripts/add-client.sh <slug> --list-scopes
#   ./scripts/add-client.sh <slug> --del-scope <id>
#   ./scripts/add-client.sh --list
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
. "$ROOT/scripts/_lib.sh"

ORCH_PORT="$(env_get ORCHESTRATOR_PORT 8080)"
ORCH_USER="$(env_get ORCHESTRATOR_ADMIN_USER admin)"
ORCH_PWD="$(env_get  ORCHESTRATOR_ADMIN_PASSWORD admin)"
API="http://localhost:${ORCH_PORT}/api/v1"

usage() {
  cat <<EOF
Usage:
  $0 <slug> <nom> [contact_email]                  -- creer client
  $0 <slug> --add-scope <kind> <value> [note]      -- ajouter un scope
  $0 <slug> --list-scopes                          -- lister les scopes
  $0 <slug> --del-scope <id>                       -- supprimer un scope
  $0 --list                                        -- lister tous les clients

  kind = domain | ip | cidr | asn | keyword | email | brand | executive
       | social_handle | crypto_wallet
EOF
  exit 1
}

[ "$#" -lt 1 ] && usage

if [ "$1" = "--list" ]; then
  curl -fsS -u "${ORCH_USER}:${ORCH_PWD}" "$API/clients" | python3 -m json.tool
  exit 0
fi

SLUG="$1"; shift

case "${1:-}" in
  --add-scope)
    [ "$#" -lt 3 ] && usage
    KIND="$2"; VALUE="$3"; NOTE="${4:-}"
    curl -fsS -u "${ORCH_USER}:${ORCH_PWD}" -X POST -H "Content-Type: application/json" \
      "$API/clients/$SLUG/scopes" \
      -d "{\"kind\":\"$KIND\",\"value\":\"$VALUE\",\"note\":\"$NOTE\"}" \
      | python3 -m json.tool
    ;;
  --list-scopes)
    curl -fsS -u "${ORCH_USER}:${ORCH_PWD}" "$API/clients/$SLUG/scopes" | python3 -m json.tool
    ;;
  --del-scope)
    [ "$#" -lt 2 ] && usage
    curl -fsS -u "${ORCH_USER}:${ORCH_PWD}" -X DELETE "$API/clients/$SLUG/scopes/$2"
    echo "deleted scope $2"
    ;;
  *)
    NAME="${1:-}"; CONTACT="${2:-}"
    [ -z "$NAME" ] && usage
    curl -fsS -u "${ORCH_USER}:${ORCH_PWD}" -X POST -H "Content-Type: application/json" \
      "$API/clients" \
      -d "{\"slug\":\"$SLUG\",\"name\":\"$NAME\",\"contact_email\":\"$CONTACT\"}" \
      | python3 -m json.tool
    ;;
esac
