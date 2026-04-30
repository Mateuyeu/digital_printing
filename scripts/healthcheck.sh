#!/usr/bin/env bash
# =============================================================================
# Verifie l'etat des services
# =============================================================================
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

[ -f .env ] && set -a && . ./.env && set +a

ok()   { printf '  \033[1;32m[OK]\033[0m %-22s %s\n' "$1" "$2"; }
down() { printf '  \033[1;31m[KO]\033[0m %-22s %s\n' "$1" "$2"; }
skip() { printf '  \033[1;90m[--]\033[0m %-22s %s\n' "$1" "$2"; }

check_http() {
  local name="$1" url="$2" code_expected="${3:-200}"
  local code
  code="$(curl -ksS -o /dev/null -w '%{http_code}' --max-time 5 "$url" 2>/dev/null || echo 000)"
  if [ "$code" = "$code_expected" ] || [ "${code:0:1}" = "2" ] || [ "${code:0:1}" = "3" ]; then
    ok "$name" "$url ($code)"
  else
    down "$name" "$url ($code)"
  fi
}

printf '\n\033[1m== Service health checks ==\033[0m\n\n'

check_http "Orchestrator"     "http://localhost:${ORCHESTRATOR_PORT:-8080}/healthz"
check_http "Orchestrator docs"  "http://localhost:${ORCHESTRATOR_PORT:-8080}/docs"
check_http "Postgres (proxy)"   "http://localhost:${ORCHESTRATOR_PORT:-8080}/healthz"

check_http "SpiderFoot"        "http://localhost:5001/" 200 \
  || skip "SpiderFoot" "non demarre"
check_http "TheHive"           "http://localhost:9000/api/v1/status" 200 \
  || skip "TheHive" "non demarre"
check_http "Cortex"            "http://localhost:9001/api/status" 200 \
  || skip "Cortex" "non demarre"
check_http "MISP"              "https://localhost:8443/users/login" 200 \
  || skip "MISP" "non demarre (premier boot ~3 min)"
check_http "AIL Framework"     "https://localhost:7000/" 200 \
  || skip "AIL" "non demarre"
check_http "LACUS"             "http://localhost:7100/" 200 \
  || skip "LACUS" "non demarre"

printf '\n\033[1m== Integrations (via orchestrator) ==\033[0m\n\n'
curl -ksS -u "${ORCHESTRATOR_ADMIN_USER:-admin}:${ORCHESTRATOR_ADMIN_PASSWORD:-admin}" \
     "http://localhost:${ORCHESTRATOR_PORT:-8080}/api/v1/integrations/health" 2>/dev/null \
  | python3 -m json.tool 2>/dev/null \
  || echo "  (orchestrator non joignable)"
echo
