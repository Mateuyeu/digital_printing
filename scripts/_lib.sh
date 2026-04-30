#!/usr/bin/env bash
# Helpers communs aux scripts. Source ce fichier en debut de chaque script :
#   . "$(dirname "$0")/_lib.sh"
#
# Lit une variable depuis .env de maniere robuste (strip quotes, ignore commentaires).
# Usage : VAL=$(env_get NOM_VARIABLE [default])
env_get() {
  local var="$1" default="${2:-}"
  local val
  if [ -f .env ]; then
    val="$(grep -E "^[[:space:]]*${var}=" .env 2>/dev/null \
           | tail -n1 \
           | sed -E "s/^[[:space:]]*${var}=//; s/^[\"']//; s/[\"']$//")"
  fi
  printf '%s' "${val:-$default}"
}
