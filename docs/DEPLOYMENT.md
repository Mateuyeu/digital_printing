# Déploiement

## Prérequis

| Ressource | Minimum (core+drps) | Recommandé (all) |
|---|---|---|
| CPU | 2 vCPU | 8 vCPU |
| RAM | 4 Go | 16 Go |
| Disque | 50 Go SSD | 200 Go SSD |
| OS | Linux x86_64 (kernel ≥ 5.4) | Debian 12 / Ubuntu 22.04 LTS |
| Docker | Engine 24+ avec compose v2 | idem |

## Préparation hôte

```bash
# Elasticsearch (TheHive / Cortex)
sudo sysctl -w vm.max_map_count=262144
echo 'vm.max_map_count=262144' | sudo tee -a /etc/sysctl.d/99-elasticsearch.conf

# Limites fichiers
echo "* soft nofile 65535" | sudo tee -a /etc/security/limits.conf
echo "* hard nofile 65535" | sudo tee -a /etc/security/limits.conf

# Docker (Debian/Ubuntu)
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"   # se relog
```

## Configuration

```bash
git clone <repo> digital_printing
cd digital_printing
cp .env.example .env
$EDITOR .env
```

### Secrets à changer impérativement

| Variable | Description |
|---|---|
| `ORCHESTRATOR_SECRET_KEY` | clé Fernet (générer : `python -c "import secrets;print(secrets.token_urlsafe(64))"`) |
| `ORCHESTRATOR_ADMIN_PASSWORD` | mot de passe admin orchestrator |
| `POSTGRES_PASSWORD` | mot de passe Postgres |
| `THEHIVE_SECRET` | secret TheHive (≥ 64 chars) |
| `THEHIVE_API_KEY` | API key TheHive (créée au premier login) |
| `CORTEX_API_KEY` | API key Cortex |
| `MISP_API_KEY` | API key MISP admin |
| `MISP_MYSQL_PASSWORD` | mot de passe MariaDB MISP |
| `MISP_ADMIN_PASSPHRASE` | mot de passe admin MISP |
| `SPIDERFOOT_PASSWORD` | mot de passe UI SpiderFoot |
| `INTELX_API_KEY`, `DEHASHED_API_KEY` | optionnels |

### Génération des secrets en lot

```bash
for var in ORCHESTRATOR_SECRET_KEY THEHIVE_SECRET POSTGRES_PASSWORD \
           MISP_MYSQL_PASSWORD ORCHESTRATOR_ADMIN_PASSWORD \
           MISP_ADMIN_PASSPHRASE SPIDERFOOT_PASSWORD; do
  echo "$var=$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
done >> .env.generated
# puis copier les valeurs dans .env
```

## Modes de déploiement

### Mode laptop / POC (RAM limitée)

```bash
./scripts/setup.sh core
./scripts/setup.sh drps   # ajoute SpiderFoot/AIL/LACUS
# pas de SOAR — on désactive le push TheHive/MISP
```

### Mode production single-host

```bash
./scripts/setup.sh all
```

Au premier boot :

1. Créer le user admin TheHive :
   - se rendre sur http://localhost:9000
   - admin@thehive.local / secret (par défaut)
   - changer le mdp, créer une organisation `digital-printing`,
     créer un user `orchestrator@thehive.local` avec le rôle `analyst`
   - générer une API key, la copier dans `.env` (`THEHIVE_API_KEY`)
   - `docker compose restart orchestrator worker`
2. Cortex pareil sur http://localhost:9001
3. MISP : login `admin@digital-printing.local` / `${MISP_ADMIN_PASSPHRASE}`,
   activer les feeds OSINT souhaités, l'API key admin est déjà dans `.env`
4. SpiderFoot : authentification automatique avec le user/pass définis dans `.env`

### Mode multi-host (cluster)

Recommandé pour > 50 clients :

| Hôte | Rôle |
|---|---|
| `orch-1` | orchestrator + worker + beat |
| `orch-2..n` | worker (replica) |
| `db-1` | postgres + redis |
| `soar-1` | TheHive + Cassandra + Elasticsearch + Cortex |
| `misp-1` | MISP + MariaDB |
| `drps-1` | SpiderFoot + AIL + LACUS + Tor |

Adapter les services en mode externe via `external: true` sur les réseaux.

## Reverse proxy

Pour une exposition publique, mettre **Caddy** ou **Traefik** devant et activer
SSO/OIDC. Exemple Caddyfile minimal :

```caddy
easm.example.com {
    @api path /api/* /docs* /openapi.json /metrics
    reverse_proxy @api orchestrator:8080
    forward_auth oidc:4181 {
        uri /verify
        copy_headers Remote-User
    }
}

thehive.example.com  { reverse_proxy thehive:9000 }
cortex.example.com   { reverse_proxy cortex:9001 }
misp.example.com     { reverse_proxy misp:443 { transport http { tls_insecure_skip_verify } } }
spiderfoot.example.com { reverse_proxy spiderfoot:5001 }
ail.example.com      { reverse_proxy ail:7000 }
```

## Hardening

### Réseau

- N'exposer **que** le port 443 du reverse proxy.
- Couper l'accès direct aux ports `9000/9001/8088/8443/5001/7000/7100`.
- Whitelist IP source via firewall hôte.

### Containers

```yaml
# Dans docker-compose.yml, ajouter à chaque service public :
read_only: true
tmpfs:
  - /tmp
security_opt:
  - no-new-privileges:true
cap_drop:
  - ALL
```

### Secrets

- Migrer vers `docker secret` ou `vault` en production.
- `.env` ne doit jamais être committé (`.gitignore` déjà en place).

### Backup

```bash
# crontab journalier
0 1 * * *  docker exec digital_printing-postgres-1 pg_dump -U dp digital_printing | gzip > /backup/pg-$(date +\%F).sql.gz
0 2 * * *  docker exec digital_printing-misp-db-1 mysqldump --all-databases -uroot -p<pwd> | gzip > /backup/misp-$(date +\%F).sql.gz
0 3 * * 0  docker run --rm -v digital_printing_cassandra_data:/data -v /backup:/out alpine tar czf /out/cassandra-$(date +\%F).tar.gz /data
```

## Mise à jour

```bash
git pull
docker compose -f docker-compose.yml build orchestrator
docker compose -f docker-compose.yml --profile build build scanner-projectdiscovery scanner-theharvester
docker compose -f docker-compose.yml -f docker-compose.soar.yml -f docker-compose.drps.yml up -d
```

Pour Nuclei templates : reconstruire l'image avec un argument différent
```bash
docker compose -f docker-compose.yml --profile build build \
  --build-arg TEMPLATES_REFRESH=$(date +%F) scanner-projectdiscovery
```

## Diagnostic

```bash
# Logs
docker compose logs -f orchestrator worker
docker compose logs --tail=200 thehive cortex

# DB
docker compose exec postgres psql -U dp digital_printing
\dt
SELECT slug, COUNT(*) FROM clients c JOIN findings f ON f.client_id=c.id GROUP BY slug;

# Celery
docker compose exec orchestrator celery -A app.workers.tasks inspect active
docker compose exec orchestrator celery -A app.workers.tasks inspect scheduled

# Healthcheck global
./scripts/healthcheck.sh
curl -u admin:<pwd> http://localhost:8080/api/v1/integrations/health | jq
```

## Désinstallation

```bash
make clean   # arrete et supprime les volumes (DESTRUCTIF)
make nuke    # + supprime les images
```
