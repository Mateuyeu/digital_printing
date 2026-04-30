# =============================================================================
# Digital Printing - EASM/DRPS Multi-Tenant Platform
# =============================================================================

COMPOSE := docker compose
COMPOSE_CORE := -f docker-compose.yml
COMPOSE_SOAR := $(COMPOSE_CORE) -f docker-compose.soar.yml
COMPOSE_DRPS := $(COMPOSE_CORE) -f docker-compose.drps.yml
COMPOSE_ALL  := $(COMPOSE_CORE) -f docker-compose.soar.yml -f docker-compose.drps.yml

.PHONY: help setup build up down restart logs ps health \
        up-core up-soar up-drps up-all clean nuke

help:
	@echo "make setup         - bootstrap initial (env, build, services core)"
	@echo "make build         - build images orchestrator + scanners"
	@echo "make up-core       - core seul (orchestrator, scanners, db)"
	@echo "make up-soar       - core + TheHive/Cortex/MISP"
	@echo "make up-drps       - core + SpiderFoot/AIL/LACUS/Tor"
	@echo "make up-all        - tout"
	@echo "make down          - arrete tout"
	@echo "make restart       - restart core"
	@echo "make logs S=<svc>  - tail logs (defaut: orchestrator)"
	@echo "make ps            - liste containers"
	@echo "make health        - healthcheck endpoints"
	@echo "make clean         - down + suppression volumes (DESTRUCTIF)"
	@echo "make nuke          - clean + rm images"

setup:
	./scripts/setup.sh core

build:
	$(COMPOSE) $(COMPOSE_CORE) build orchestrator
	$(COMPOSE) $(COMPOSE_CORE) --profile build build scanner-projectdiscovery scanner-theharvester
	$(COMPOSE) $(COMPOSE_DRPS) build lacus spiderfoot

up-core:
	$(COMPOSE) $(COMPOSE_CORE) up -d

up-soar:
	$(COMPOSE) $(COMPOSE_SOAR) up -d

up-drps:
	$(COMPOSE) $(COMPOSE_DRPS) up -d

up-all:
	$(COMPOSE) $(COMPOSE_ALL) up -d

down:
	$(COMPOSE) $(COMPOSE_ALL) down

restart:
	$(COMPOSE) $(COMPOSE_CORE) restart orchestrator worker beat

logs:
	$(COMPOSE) $(COMPOSE_ALL) logs -f --tail=100 $(or $(S),orchestrator)

ps:
	$(COMPOSE) $(COMPOSE_ALL) ps

health:
	./scripts/healthcheck.sh

clean:
	$(COMPOSE) $(COMPOSE_ALL) down -v

nuke: clean
	docker rmi -f digital_printing/orchestrator:latest \
	             digital_printing/projectdiscovery:latest \
	             digital_printing/theharvester:latest \
	             digital_printing/lacus:latest \
	             digital_printing/spiderfoot:latest 2>/dev/null || true
