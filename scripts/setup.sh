#!/usr/bin/env bash
# =============================================================================
# Setup initial : verifie prerequis, copie .env, build images, demarre core
# Usage : ./scripts/setup.sh [core|all|build-only]
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MODE="${1:-core}"
COMPOSE_BIN="${COMPOSE_BIN:-docker compose}"

bold()  { printf '\033[1m%s\033[0m\n' "$*"; }
ok()    { printf '\033[1;32m[OK]\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m[!]\033[0m %s\n' "$*"; }
fail()  { printf '\033[1;31m[X]\033[0m %s\n' "$*" >&2; exit 1; }

bold "== Digital Printing - EASM/DRPS bootstrap ($MODE) =="

# --- 1. prerequis -----------------------------------------------------------
command -v docker >/dev/null 2>&1 || fail "docker introuvable"
$COMPOSE_BIN version >/dev/null 2>&1 || fail "'$COMPOSE_BIN' introuvable - installer docker compose v2"
ok "docker + compose detectes"

# --- 2. .env ----------------------------------------------------------------
if [ ! -f .env ]; then
  cp .env.example .env
  warn ".env cree depuis .env.example - EDITER les secrets avant production !"
fi

# --- 3. parametres systeme requis pour Elasticsearch ------------------------
if [ "$MODE" = "all" ] || [ "$MODE" = "soar" ]; then
  current="$(sysctl -n vm.max_map_count 2>/dev/null || echo 0)"
  if [ "$current" -lt 262144 ]; then
    warn "vm.max_map_count=$current (requis >=262144 pour Elasticsearch)"
    echo "    Executer: sudo sysctl -w vm.max_map_count=262144"
    echo "    Persister: echo 'vm.max_map_count=262144' | sudo tee -a /etc/sysctl.d/99-elasticsearch.conf"
  fi
fi

# --- 4. build images --------------------------------------------------------
bold "== Build images Docker =="
$COMPOSE_BIN -f docker-compose.yml build orchestrator
$COMPOSE_BIN -f docker-compose.yml --profile build build scanner-projectdiscovery scanner-theharvester
ok "Images orchestrator + scanners construites"

if [ "$MODE" = "drps" ] || [ "$MODE" = "all" ]; then
  $COMPOSE_BIN -f docker-compose.yml -f docker-compose.drps.yml build lacus spiderfoot
  ok "Images LACUS + SpiderFoot construites"
fi

if [ "$MODE" = "build-only" ]; then
  ok "Mode build-only - termine"
  exit 0
fi

# --- 5. start --------------------------------------------------------------
bold "== Demarrage des services =="
case "$MODE" in
  core)
    $COMPOSE_BIN -f docker-compose.yml up -d
    ;;
  soar)
    $COMPOSE_BIN -f docker-compose.yml -f docker-compose.soar.yml up -d
    ;;
  drps)
    $COMPOSE_BIN -f docker-compose.yml -f docker-compose.drps.yml up -d
    ;;
  all)
    $COMPOSE_BIN -f docker-compose.yml -f docker-compose.soar.yml -f docker-compose.drps.yml up -d
    ;;
  *)
    fail "mode inconnu: $MODE (core|soar|drps|all|build-only)"
    ;;
esac

ok "Services demarres - waiting healthchecks..."
sleep 5
"$ROOT/scripts/healthcheck.sh" || true

bold "== Bootstrap termine =="
echo "  Orchestrator API : http://localhost:${ORCHESTRATOR_PORT:-8080}/docs"
[ "$MODE" = "all" ] || [ "$MODE" = "soar" ] && echo "  TheHive          : http://localhost:9000  (creation admin au premier demarrage)"
[ "$MODE" = "all" ] || [ "$MODE" = "soar" ] && echo "  Cortex           : http://localhost:9001"
[ "$MODE" = "all" ] || [ "$MODE" = "soar" ] && echo "  MISP             : https://localhost:8443"
[ "$MODE" = "all" ] || [ "$MODE" = "drps" ] && echo "  SpiderFoot       : http://localhost:5001"
[ "$MODE" = "all" ] || [ "$MODE" = "drps" ] && echo "  AIL              : https://localhost:7000"
[ "$MODE" = "all" ] || [ "$MODE" = "drps" ] && echo "  LACUS            : http://localhost:7100"
echo
echo "Prochaine etape : ./scripts/add-client.sh <slug> '<nom>' <contact>"
