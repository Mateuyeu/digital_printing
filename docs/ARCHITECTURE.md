# Architecture

## Vue d'ensemble

La plateforme est composée de **3 couches** déployables séparément :

1. **Core** : orchestrator FastAPI, workers Celery, PostgreSQL, Redis, scanner images
2. **SOAR** : TheHive 5 + Cortex + MISP (gestion des alertes et partage IoC)
3. **DRPS** : SpiderFoot, AIL Framework, LACUS, Tor (collecte sur surface visible et alternative)

Chaque couche est un fichier `docker-compose.*.yml` séparé qui partage les
réseaux Docker `dp_core`, `dp_soar`, `dp_drps`. L'orchestrator est connecté
aux trois.

## Modèle de données multi-tenant

Toutes les ressources sont scopées par `client_id`. Hiérarchie :

```
Client (slug, name, settings, misp_org_uuid, thehive_org)
  │
  ├── Scope[]             — domaine, IP, CIDR, ASN, mot-clé, email, marque,
  │                         exécutif, handle social, wallet crypto
  │
  ├── Scan[]              — exécution unitaire (kind = full_recon, easm_*,
  │     │                   drps_*) avec status (pending/running/completed/failed)
  │     │
  │     └── Finding[]    — résultat dédupliqué (fingerprint SHA256 sur 48 hex)
  │                         severity, kind, title, asset, source, raw, iocs[]
  │                         flags pushed_to_thehive / pushed_to_misp
  │
  └── Report[]            — agrégat HTML+PDF sur une fenêtre temporelle
```

- **Déduplication** : table unique `findings` avec contrainte unique
  `(client_id, kind, fingerprint)`. Un nouvel asset met à jour `last_seen` ;
  une nouvelle vulnérabilité crée une ligne.
- **IoCs** : stockés en JSONB dans `Finding.iocs` (liste de `{type, value}`).
  Types reconnus : `domain`, `ipv4`, `ipv6`, `email`, `url`, `cve`, `hash`,
  `btc`, `credential`, etc.
- **Audit** : table `audit_log` (action, actor, target, detail, timestamp).

## Flux de scan EASM (full_recon)

```
   ┌─ scopes(domain) ────────► subfinder ──► [+subdomains]
   │                                   │
   │                                   ▼
   │  scopes(ip,cidr) ──────────► dnsx ──► [+resolved IPs]
   │                                   │
   │                                   ▼
   │                             naabu ──► [+open ports]
   │                                   │
   │                                   ▼
   │                              httpx ──► [+http_services + tech_detect]
   │                                   │
   │                              ┌────┴───┐
   │                              ▼         ▼
   │                            katana    nuclei ──► [+vulns]
   │                              │         │
   │                              ▼         ▼
   │                        [+endpoints]  [+CVEs détectées]
   │                                   │
   │                                   ▼
   │                              cvemap (sur tech_detect)
   │
   └─ scopes(domain) ────► theHarvester + SpiderFoot ──► [+OSINT]
```

## Flux DRPS

```
scopes(brand,keyword,email) ─┬─► IntelX search    ──► [+leak_intelx]
                              │
                              ├─► Dehashed search ──► [+leak_credential]
                              │
                              ├─► AIL trackers     ──► [+paste_match]
                              │   (mots-clés, regex)
                              │
                              └─► LACUS captures   ──► [+darkweb_capture]
                                  via Tor (.onion) ou I2P (.i2p)
                                  ou clearnet (forums, marketplace)
```

Pour les **réseaux sociaux alternatifs** (Telegram, Discord, Session) :
- AIL crawler enregistre des trackers sur les invitations / handles
- LACUS capture les pages d'invitation et les rend en HAR
- Les findings remontent dans la base avec `source=lacus-social`

## Flux d'export SOAR

```
Finding (severity ≥ medium par défaut)
   │
   ├─── push_finding_to_thehive  ──► TheHive Alert
   │     - title scopé client
   │     - tags : client:<slug>, kind:<>, source:<>
   │     - observables = iocs avec dataType
   │     - severity mappée 1..4
   │
   └─── push_finding_to_misp     ──► MISP Event
         - distribution = 0 (org seulement)
         - threat_level mappé
         - tags : client:<slug>, tlp:amber, kind:<>
         - attributs = iocs convertis (domain, ip-dst, email-src,
                                       url, sha256, btc, leaked-credentials)
```

L'auto-push est activé par scan via `parameters.auto_push_thehive=true` et
`parameters.auto_push_misp=true`. On peut aussi pousser unitairement un finding
via `POST /findings/{id}/push-thehive` ou `/push-misp`.

## Schedules

Le service `beat` (Celery) exécute :

- `scheduled_easm_recon` — chaque dimanche 02:00 UTC, FULL_RECON pour tous
  les clients actifs avec auto-push
- `scheduled_drps_sweep` — chaque jour 04:00 UTC, DRPS_LEAKS + DRPS_AIL
  pour tous les clients actifs avec auto-push

À adapter dans `orchestrator/app/workers/tasks.py` (`celery_app.conf.beat_schedule`).

## Choix techniques

### Pourquoi FastAPI + Celery ?

- API typée par Pydantic, OpenAPI gratuit
- Celery découple les scans (longs) de l'API (sync)
- Redis comme broker — léger, déjà nécessaire pour le cache

### Pourquoi un container par scan plutôt qu'un binaire local ?

- Isolation : un scan Nuclei buggué ne peut pas étouffer le worker
- Tags d'image versionnables (cache nuclei-templates par build)
- Capabilities minimales (`cap_add: NET_RAW` pour `naabu`, le reste droppé)
- L'image `digital_printing/projectdiscovery` regroupe tous les outils PD pour
  réduire le nombre d'images

### Pourquoi PostgreSQL et pas SQLite ?

- Concurrence des workers Celery
- JSONB natif pour `findings.raw`, `findings.iocs`, `scans.summary`
- Indexes composites efficaces pour les requêtes multi-tenant

### Pourquoi LACUS pour le dark web et pas un crawler simple ?

- LACUS = Playwright + proxy management → vrai rendu JS, screenshots,
  HAR complet
- Support natif Tor / I2P / proxies via `socks5://`
- Découplé de AIL (peut être interrogé directement via l'API)

### Pourquoi AIL en plus de SpiderFoot ?

- AIL est conçu pour la **chasse persistante** (trackers continus)
- SpiderFoot fait des **scans ponctuels** profonds
- AIL ingère paste, social, telegram via des **crawlers persistants**
- SpiderFoot couvre l'OSINT large (200+ modules)

## Réseaux Docker

- `dp_core` — orchestrator, worker, beat, postgres, redis
- `dp_soar` — Cassandra, Elasticsearch, TheHive, Cortex, MISP, MariaDB
- `dp_drps` — SpiderFoot, AIL, LACUS, Tor

L'orchestrator est connecté aux trois pour pouvoir piloter directement
les API.

## Volumes persistants

| Volume | Contenu | Backup |
|---|---|---|
| `pg_data` | base orchestrator (clients, scans, findings) | **critique** — dump quotidien |
| `cassandra_data` | TheHive (cases, alerts) | critique |
| `elasticsearch_data` | TheHive index + Cortex jobs | recréable depuis Cassandra |
| `misp_db` | MISP (événements, attributs) | **critique** |
| `misp_files` | attachments MISP | important |
| `spiderfoot_data` | scans SpiderFoot | recréable |
| `ail_data` | pastes capturés | important |
| `report_data` | rapports HTML/PDF | recréable |

## Limites connues

- **L'image MISP officielle** prend ~3 minutes au premier boot (génération
  GPG, init DB) — patience.
- **Cassandra + Elasticsearch** demandent de la RAM (~3 Go combined).
  Sur petite VM, ne lancer que `core` + `drps`.
- **`vm.max_map_count >= 262144`** requis sur l'hôte pour Elasticsearch.
- **theHarvester** dépend de sources publiques rate-limitées (CertSpotter,
  crt.sh, etc.) — résultats variables.
- **Dehashed** et **IntelX** requièrent une API key payante (free tier limité).
