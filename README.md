# Digital Printing — Plateforme EASM/DRPS multi-tenant FOSS

Infrastructure d'**External Attack Surface Management (EASM)** et de **Digital
Risk Protection Service (DRPS)** clé en main, conçue pour un usage **MSSP
multi-client**, basée exclusivement sur des outils **Free Open Source Software**.

L'orchestrator agrège les résultats de tous les outils dans une base unique,
les pousse sous forme d'alertes dans **TheHive**, exporte les IoC vers **MISP**,
et génère un rapport client (HTML + PDF) périodique ou à la demande.

## Composants intégrés

| Domaine | Outils |
|---|---|
| **EASM Reconnaissance** | ProjectDiscovery (`subfinder`, `dnsx`, `naabu`, `httpx`, `nuclei`, `katana`, `cvemap`), `theHarvester`, `SpiderFoot` |
| **DRPS Surveillance** | `AIL Framework`, `LACUS` (capture Tor / I2P / clearnet), `IntelX`, `Dehashed` |
| **SOAR / Partage** | `TheHive 5`, `Cortex`, `MISP` |
| **Orchestration** | FastAPI + Celery + Redis + PostgreSQL |
| **Reporting** | Jinja2 + wkhtmltopdf (HTML autonome + PDF) |

## Démarrage rapide

```bash
# 1. Configurer les secrets
cp .env.example .env
$EDITOR .env

# 2. Bootstrap (build + démarrage du core)
./scripts/setup.sh core      # core seul (recommandé pour tester)
# ou
./scripts/setup.sh all       # core + SOAR + DRPS

# 3. Vérifier
./scripts/healthcheck.sh

# 4. Créer un client + scopes
./scripts/add-client.sh acme "ACME Corp" contact@acme.com
./scripts/add-client.sh acme --add-scope domain  acme.com
./scripts/add-client.sh acme --add-scope domain  acme.io
./scripts/add-client.sh acme --add-scope keyword "ACME"
./scripts/add-client.sh acme --add-scope brand   "ACME Corporation"
./scripts/add-client.sh acme --add-scope email   contact@acme.com

# 5. Lancer un scan complet (EASM + push automatique TheHive/MISP)
./scripts/run-scan.sh acme full_recon --push-thehive --push-misp

# 6. Lancer un sweep DRPS (leaks)
./scripts/run-scan.sh acme drps_leaks --push-thehive --push-misp

# 7. Générer un rapport mensuel
./scripts/generate-report.sh acme 30 "Rapport mensuel ACME — Avril 2026"
./scripts/generate-report.sh acme --list
./scripts/generate-report.sh acme --download 1
```

## Architecture

```
                  ┌─────────────────────────────────────────────────┐
                  │  Orchestrator (FastAPI)  ← REST/CLI/Webhooks     │
                  │  multi-tenant : Client → Scope → Scan → Finding  │
                  └──────────────┬─────────────────┬─────────────────┘
                                 │                 │
                ┌────────────────┴───────┐   ┌─────┴───────┐
                │  Celery workers        │   │ PostgreSQL  │
                │  (queues: easm/drps/   │   │ Redis       │
                │   reports)             │   │             │
                └─┬──────────────┬───────┘   └─────────────┘
                  │              │
   ┌──────────────┴──┐    ┌──────┴────────────────┐
   │  EASM scanners  │    │  DRPS connectors      │
   │  (containers)   │    │                       │
   │  - subfinder    │    │  - SpiderFoot (HTTP)  │
   │  - dnsx         │    │  - AIL Framework      │
   │  - naabu        │    │  - LACUS (Tor/I2P)    │
   │  - httpx        │    │  - IntelX             │
   │  - nuclei       │    │  - Dehashed           │
   │  - katana       │    └──────┬────────────────┘
   │  - cvemap       │           │
   │  - theHarvester │           │
   └─────────┬───────┘           │
             │                    │
             ▼                    ▼
        ┌──────────────────────────────────────┐
        │  Findings  +  IoCs                    │
        └────────────┬──────────────┬──────────┘
                     │              │
          ┌──────────▼─┐     ┌──────▼──────┐
          │  TheHive 5 │◄────┤   Cortex    │
          │  (alerts)  │     │ (analyzers) │
          └────────────┘     └─────────────┘
                     │
                     ▼
                 ┌────────┐
                 │  MISP  │  ← export IoC pour partage communautaire
                 └────────┘
```

Voir [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) pour les détails.

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — modèle de données, flux, choix techniques
- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) — déploiement on-prem ou cloud, hardening
- [`docs/USAGE.md`](docs/USAGE.md) — opération quotidienne, exemples API, intégrations

## Stack séparable

Trois fichiers `docker-compose` permettent de lancer la plateforme par couches,
selon les besoins et la mémoire disponible :

| Fichier | Services | RAM minimale |
|---|---|---|
| `docker-compose.yml`         | orchestrator, worker, beat, postgres, redis | ~2 Go |
| `docker-compose.soar.yml`    | TheHive 5 + Cassandra + Elasticsearch + Cortex + MISP + MariaDB | ~6 Go |
| `docker-compose.drps.yml`    | SpiderFoot + AIL + LACUS + Tor | ~2 Go |

## Sécurité

- Auth HTTP Basic admin (à mettre derrière un reverse proxy avec SSO/OIDC pour
  une exposition Internet)
- Tous les secrets sont dans `.env` (ne pas commiter)
- Les containers de scan tournent sans privilèges, capabilities minimales
- Communications inter-services via réseaux Docker dédiés
- Audit trail complet en base (`audit_log`)

## Licence

GPL-3.0-or-later (cohérent avec MISP, TheHive, AIL, LACUS, SpiderFoot)
