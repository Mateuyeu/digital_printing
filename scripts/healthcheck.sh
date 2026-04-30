#!/usr/bin/env bash
# =============================================================================
# Verifie l'etat des services
# =============================================================================
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
. "$ROOT/scripts/_lib.sh"

ORCH_PORT="$(env_get ORCHESTRATOR_PORT 8080)"
ORCH_USER="$(env_get ORCHESTRATOR_ADMIN_USER admin)"
ORCH_PWD="$(env_get  ORCHESTRATOR_ADMIN_PASSWORD admin)"

ok()   { printf '  \033[1;32m[OK]\033[0m %-22s %s\n' "$1" "$2"; }
down() { printf '  \033[1;31m[KO]\033[0m %-22s %s\n' "$1" "$2"; }

check_http() {
  local name="$1" url="$2"
  local code
  code="$(curl -ksS -o /dev/null -w '%{http_code}' --max-time 5 "$url" 2>/dev/null || echo 000)"
  if [ "${code:0:1}" = "2" ] || [ "${code:0:1}" = "3" ]; then
    ok "$name" "$url ($code)"
  else
    down "$name" "$url ($code)"
  fi
}

printf '\n\033[1m== Service health checks ==\033[0m\n\n'

check_http "Orchestrator"     "http://localhost:${ORCH_PORT}/healthz"
check_http "Orchestrator docs"  "http://localhost:${ORCH_PORT}/docs"
check_http "SpiderFoot"        "http://localhost:5001/"
check_http "TheHive"           "http://localhost:9000/api/v1/status"
check_http "Cortex"            "http://localhost:9001/api/status"
check_http "MISP"              "https://localhost:8443/users/login"
check_http "AIL Framework"     "https://localhost:7000/"
check_http "LACUS"             "http://localhost:7100/"

printf '\n\033[1m== Integrations (via orchestrator) ==\033[0m\n\n'
curl -ksS -u "${ORCH_USER}:${ORCH_PWD}" \
     "http://localhost:${ORCH_PORT}/api/v1/integrations/health" 2>/dev/null \
  | python3 -m json.tool 2>/dev/null \
  || echo "  (orchestrator non joignable)"
echo
