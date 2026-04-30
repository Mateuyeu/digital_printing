# Utilisation

## Workflow MSSP type

Pour chaque nouveau client :

1. **Onboarding** — créer le tenant et son périmètre
2. **Recon initiale** — full_recon une première fois pour cartographier
3. **Activation DRPS** — enregistrer les trackers AIL, lancer un sweep IntelX/Dehashed
4. **Mise sous surveillance** — schedule hebdo (EASM) + quotidien (DRPS)
5. **Reporting** — rapport mensuel auto-poussé au client

## API REST

L'orchestrator expose l'API sur `http://localhost:8080/api/v1` (Swagger UI : `/docs`).
Tous les endpoints requièrent une auth HTTP Basic (admin par défaut).

### Clients (tenants)

```bash
# Lister
curl -u admin:pwd http://localhost:8080/api/v1/clients

# Créer
curl -u admin:pwd -X POST -H "Content-Type: application/json" \
  http://localhost:8080/api/v1/clients \
  -d '{"slug":"acme","name":"ACME Corp","contact_email":"contact@acme.com"}'

# Détail
curl -u admin:pwd http://localhost:8080/api/v1/clients/acme

# Suppression (cascade : scopes, scans, findings, reports)
curl -u admin:pwd -X DELETE http://localhost:8080/api/v1/clients/acme
```

### Scopes

Types disponibles :

| Kind | Exemple | Utilisé par |
|---|---|---|
| `domain`         | `acme.com`            | subfinder, dnsx, httpx, nuclei, theHarvester, SpiderFoot |
| `ip`             | `198.51.100.10`       | naabu, httpx, nuclei |
| `cidr`           | `198.51.100.0/24`     | naabu |
| `asn`            | `AS64500`             | (info pour rapport, manuel) |
| `keyword`        | `ACME`                | IntelX, Dehashed, AIL trackers |
| `email`          | `contact@acme.com`    | Dehashed, IntelX |
| `brand`          | `ACME Corporation`    | AIL trackers, DRPS social |
| `executive`      | `Jane Doe (CEO)`      | AIL trackers, IntelX |
| `social_handle`  | `@acmecorp`           | AIL trackers (Telegram/X/etc) |
| `crypto_wallet`  | `bc1q...`             | AIL trackers, OSINT |

```bash
# Ajouter un scope
curl -u admin:pwd -X POST -H "Content-Type: application/json" \
  http://localhost:8080/api/v1/clients/acme/scopes \
  -d '{"kind":"domain","value":"acme.com","note":"main brand"}'

# Lister les scopes
curl -u admin:pwd http://localhost:8080/api/v1/clients/acme/scopes
```

### Lancer un scan

```bash
# Full recon EASM avec push automatique
curl -u admin:pwd -X POST -H "Content-Type: application/json" \
  http://localhost:8080/api/v1/clients/acme/scans \
  -d '{
    "kind": "full_recon",
    "parameters": {
      "auto_push_thehive": true,
      "auto_push_misp": true
    }
  }'
```

Types de scan :

| Kind | Description |
|---|---|
| `easm_discovery` | subfinder + dnsx + naabu (cartographie) |
| `easm_http` | httpx (HTTP fingerprint, tech detect) |
| `easm_vuln` | nuclei (vulnerability scan) |
| `easm_crawl` | katana (endpoints/JS) |
| `easm_cve` | cvemap (lookup par produit, cf params.products) |
| `easm_osint` | theHarvester + SpiderFoot |
| `drps_leaks` | IntelX + Dehashed |
| `drps_ail` | AIL search/trackers (cf params.action=register) |
| `drps_darkweb` | LACUS via Tor (cf params.urls + params.proxy) |
| `drps_social` | AIL+LACUS sur réseaux alternatifs (params.invite_urls) |
| `full_recon` | pipeline EASM complet |

### Findings

```bash
# Lister les findings d'un client (filtrage)
curl -u admin:pwd "http://localhost:8080/api/v1/clients/acme/findings?severity=critical"
curl -u admin:pwd "http://localhost:8080/api/v1/clients/acme/findings?kind=vulnerability&limit=50"

# Pousser un finding spécifique vers TheHive
curl -u admin:pwd -X POST \
  http://localhost:8080/api/v1/clients/acme/findings/123/push-thehive

# Pousser vers MISP
curl -u admin:pwd -X POST \
  http://localhost:8080/api/v1/clients/acme/findings/123/push-misp
```

### Rapports

```bash
# Demander un rapport (asynchrone)
curl -u admin:pwd -X POST -H "Content-Type: application/json" \
  http://localhost:8080/api/v1/clients/acme/reports \
  -d '{
    "period_days": 30,
    "title": "Rapport mensuel ACME - Avril 2026",
    "include_easm": true,
    "include_drps": true
  }'

# Lister les rapports
curl -u admin:pwd http://localhost:8080/api/v1/clients/acme/reports

# Télécharger PDF
curl -u admin:pwd http://localhost:8080/api/v1/clients/acme/reports/1/pdf -o rapport.pdf
```

### Healthcheck intégrations

```bash
curl -u admin:pwd http://localhost:8080/api/v1/integrations/health | jq
```

Sortie :
```json
{
  "thehive":    {"status": "ok", "version": "5.4.0"},
  "cortex":     {"status": "ok", "code": 200},
  "misp":       {"status": "ok", "version": "2.4.x"},
  "spiderfoot": {"status": "ok", "code": 200},
  "ail":        {"status": "ok", "code": 200},
  "lacus":      {"status": "ok", "code": 200},
  "intelx":     {"status": "ok", "credits": 950},
  "dehashed":   {"status": "ok", "code": 200}
}
```

## Scripts CLI

```bash
./scripts/add-client.sh acme "ACME Corp" contact@acme.com
./scripts/add-client.sh acme --add-scope domain  acme.com
./scripts/add-client.sh acme --add-scope keyword "ACME"
./scripts/add-client.sh --list

./scripts/run-scan.sh acme full_recon --push-thehive --push-misp
./scripts/run-scan.sh acme drps_leaks
./scripts/run-scan.sh acme easm_cve '{"products":["nginx","wordpress"]}'
./scripts/run-scan.sh acme drps_darkweb '{"urls":["http://example.onion/forum"],"proxy":"tor"}'

./scripts/list-findings.sh acme critical
./scripts/list-findings.sh acme high vulnerability

./scripts/generate-report.sh acme 30 "Rapport mensuel ACME - Avril 2026"
./scripts/generate-report.sh acme --list
./scripts/generate-report.sh acme --download 1

./scripts/healthcheck.sh
```

## Schedules

Le service `beat` exécute par défaut :

- **Dimanche 02:00 UTC** — full_recon EASM pour tous les clients actifs (auto-push)
- **Tous les jours 04:00 UTC** — drps_leaks + drps_ail pour tous les clients actifs (auto-push)

Pour ajouter ou modifier des schedules, éditer
`orchestrator/app/workers/tasks.py` :

```python
celery_app.conf.beat_schedule = {
    "easm-weekly": {"task": "tasks.scheduled_easm_recon",
                    "schedule": crontab(day_of_week="sun", hour=2, minute=0)},
    "drps-daily":  {"task": "tasks.scheduled_drps_sweep",
                    "schedule": crontab(hour=4, minute=0)},
    # Ajouter ici:
    "drps-darkweb-weekly": {
        "task": "tasks.scheduled_darkweb_sweep",
        "schedule": crontab(day_of_week="wed", hour=3, minute=0),
    },
}
```

Puis `docker compose restart beat`.

## Workflows MSSP

### Onboarding complet d'un client

```bash
SLUG=acme
NAME="ACME Corp"
EMAIL=secops@acme.com

# 1. Créer le tenant
./scripts/add-client.sh "$SLUG" "$NAME" "$EMAIL"

# 2. Charger le périmètre
for d in acme.com acme.io acme.eu; do
  ./scripts/add-client.sh "$SLUG" --add-scope domain "$d"
done

for kw in "ACME" "ACME Corporation" "acmecorp"; do
  ./scripts/add-client.sh "$SLUG" --add-scope keyword "$kw"
done

./scripts/add-client.sh "$SLUG" --add-scope email "support@acme.com"
./scripts/add-client.sh "$SLUG" --add-scope brand "ACME"
./scripts/add-client.sh "$SLUG" --add-scope executive "John Smith"

# 3. Recon initiale
./scripts/run-scan.sh "$SLUG" full_recon --push-thehive --push-misp

# 4. Enregistrer trackers AIL persistants
./scripts/run-scan.sh "$SLUG" drps_ail '{"action":"register"}'

# 5. Premier sweep DRPS
./scripts/run-scan.sh "$SLUG" drps_leaks --push-thehive --push-misp

# 6. Vérifier
./scripts/list-findings.sh "$SLUG" critical
./scripts/list-findings.sh "$SLUG" high

# 7. Rapport initial
./scripts/generate-report.sh "$SLUG" 30 "Rapport initial $NAME"
```

### Ajout d'une URL .onion à surveiller

```bash
# Capture immédiate via Tor
./scripts/run-scan.sh acme drps_darkweb \
  '{"urls":["http://abcdef0123456789.onion/forum/index.php"],
    "proxy":"tor",
    "depth":2,
    "wait":true,
    "max_wait":900}'

# Récupérer le résultat
./scripts/list-findings.sh acme medium darkweb_capture
```

### Réponse à incident

Quand TheHive détecte une alerte critique :

1. L'analyste promote l'alerte en case
2. Lance les analyzers Cortex (VirusTotal, Shodan, MISP, …) sur les
   observables
3. Si confirmé : enrichit le case avec un export MISP automatique
4. La réponse (blocklist, takedown) déclenche un responder Cortex

L'orchestrator publie aussi un webhook (à brancher dans
`config/thehive/application.conf`) pour des intégrations sortantes
(Slack, Teams, mail).

## Format des findings

Exemple d'objet `Finding` retourné par l'API :

```json
{
  "id": 4521,
  "client_id": 1,
  "scan_id": 88,
  "kind": "vulnerability",
  "severity": "high",
  "title": "Apache HTTP Server CVE-2024-12345",
  "description": "Apache 2.4.x is vulnerable to ...",
  "asset": "https://www.acme.com",
  "source": "nuclei",
  "fingerprint": "9f1c4b...",
  "iocs": [
    {"type": "url", "value": "https://www.acme.com"},
    {"type": "cve", "value": "CVE-2024-12345"}
  ],
  "pushed_to_thehive": true,
  "pushed_to_misp": true,
  "thehive_alert_id": "~1234",
  "misp_event_id": "abc-1234-def-5678",
  "first_seen": "2026-04-15T03:12:00Z",
  "last_seen": "2026-04-30T03:08:11Z"
}
```

## Métriques Prometheus

L'orchestrator expose `/metrics` (Prometheus). Brancher Grafana pour
surveiller :

- `http_requests_total` par route
- `http_request_duration_seconds`
- nombre de tâches Celery en attente / actives (via `celery_active_tasks`)

## FAQ

**Q : Mon scan échoue avec `image not found: digital_printing/projectdiscovery:latest`**
R : Lancer `make build` ou `./scripts/setup.sh build-only` pour construire
l'image scanner.

**Q : MISP retourne 401 sur le push**
R : Régénérer la clé admin depuis l'UI MISP (Administration → List Auth Keys),
mettre à jour `MISP_API_KEY` dans `.env`, `docker compose restart worker`.

**Q : TheHive ne démarre pas**
R : Cassandra prend ~60-120s au premier boot. Voir `docker compose logs cassandra thehive`.
S'assurer que `vm.max_map_count >= 262144`.

**Q : Comment exclure un domaine d'un scan déjà programmé ?**
R : Mettre à jour le scope avec `in_scope=false` (PUT non encore exposé,
faire `DELETE` puis recréer). Au prochain scan il sera ignoré.

**Q : Combien de temps pour un full_recon ?**
R : Dépend de la taille du périmètre. Ordre de grandeur :
- 5 domaines : 30 min
- 50 domaines : 2 h
- 500 domaines : 8 h+ (ajuster Nuclei rate-limit et threads dans `.env`)
