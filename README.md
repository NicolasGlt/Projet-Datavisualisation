[github](https://github.com/NicolasGlt/Projet-Datavisualisation)
# 🔭 Supervision Opérationnelle — Prometheus + Grafana + Loki

Stack de supervision complète et reproductible pour une API web, répondant aux 5 questions opérationnelles fondamentales :

> Le service est-il UP ? Quel est le taux d'erreur ? Quelle est la latence (p95) ? Y a-t-il de la saturation ? Qu'est-ce qui explique un pic ?

---

## 📦 Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Docker Compose                        │
│                                                           │
│  demo-api (FastAPI)  ──metrics──►  Prometheus             │
│  node-exporter       ──metrics──►  Prometheus             │
│                                        │                  │
│  demo-api (logs) ─► Promtail ─► Loki  │                  │
│                                        ▼                  │
│                                    Grafana ◄── User       │
│                                        │                  │
│  Prometheus ──alerts──► Alertmanager  │                  │
└─────────────────────────────────────────────────────────┘
```

| Composant       | Rôle                                  | Port  |
|-----------------|---------------------------------------|-------|
| `demo-api`      | API FastAPI instrumentée              | 8000  |
| `prometheus`    | Collecte et stockage des métriques    | 9090  |
| `grafana`       | Dashboards et alertes visuelles       | 3000  |
| `alertmanager`  | Routage et déduplication des alertes  | 9093  |
| `node-exporter` | Métriques système (CPU/RAM/FS/réseau) | 9100  |
| `loki`          | Agrégation des logs                   | 3100  |
| `promtail`      | Agent de collecte des logs Docker     | 9080  |

---

## 🚀 Démarrage rapide

### Prérequis
- Docker ≥ 24 et Docker Compose v2
- Ports libres : 3000, 8000, 9090, 9093, 9100, 3100

### Lancer la stack

```bash
# 1. Cloner le repo
git clone <url-du-repo>
cd supervision-projet

# 2. Démarrer tous les services
docker compose up -d --build

# 3. Vérifier que tout est UP
docker compose ps
```

### Accès aux interfaces

| Interface        | URL                          | Login          |
|------------------|------------------------------|----------------|
| Grafana          | http://localhost:3000        | admin / admin123 |
| Prometheus UI    | http://localhost:9090        | —              |
| Alertmanager     | http://localhost:9093        | —              |
| API /metrics     | http://localhost:8000/metrics| —              |

### Générer du trafic (pour peupler les dashboards)

```bash
# Depuis la racine du repo
pip install httpx
python api/load_generator.py --url http://localhost:8000 --rps 5
```

### Arrêter la stack

```bash
docker compose down

# Arrêt avec suppression des volumes (reset complet)
docker compose down -v
```

### Rechargement à chaud de la config Prometheus

```bash
curl -X POST http://localhost:9090/-/reload
```

---

## 📐 SLI / SLO définis

### SLI 1 — Disponibilité (taux de succès)

**Définition :** proportion de requêtes HTTP aboutissant avec un code 2xx ou 3xx.

```promql
1 - (
  sum(rate(http_requests_total{http_status=~"5.."}[5m]))
  / sum(rate(http_requests_total[5m]))
)
```

**SLO :** ≥ 99,5 % de requêtes sans erreur 5xx sur une fenêtre glissante de 5 minutes.

**Justification :** Un taux de 0,5 % d'erreurs 5xx correspond à ~1 requête sur 200. En dessous, l'impact utilisateur est négligeable ; au-dessus, c'est un signe de dysfonctionnement systémique.

---

### SLI 2 — Latence (percentile 95)

**Définition :** temps de réponse au-dessous duquel se situent 95 % des requêtes.

```promql
histogram_quantile(0.95,
  sum by (le) (
    rate(http_request_duration_seconds_bucket[5m])
  )
)
```

**SLO :** p95 < 1 seconde en conditions normales.

**Justification :** Au-delà d'1 s, la majorité des frameworks web commencent à retransmettre ou à afficher des indicateurs de chargement, dégradant l'expérience utilisateur. Le p95 (et non le p50) évite d'ignorer les cas lents qui restent fréquents.

---

## 🔍 Requêtes PromQL clés

| # | Objectif               | Requête simplifiée                                                              |
|---|------------------------|---------------------------------------------------------------------------------|
| 1 | UP/DOWN                | `up{job="demo-api"}`                                                            |
| 2 | Trafic (req/s)         | `sum(rate(http_requests_total[2m]))`                                            |
| 3 | Taux erreurs 5xx       | `sum(rate(http_requests_total{http_status=~"5.."}[2m])) / sum(rate(...))`      |
| 4 | Latence p95            | `histogram_quantile(0.95, sum by (le) (rate(..._bucket[5m])))`                  |
| 5 | CPU %                  | `(1 - avg(rate(node_cpu_seconds_total{mode="idle"}[2m]))) * 100`               |
| 6 | Top 5 endpoints        | `topk(5, sum by (endpoint) (rate(http_requests_total[5m])))`                    |

> Fichier complet avec 15+ requêtes documentées : `prometheus/promql_queries.promql`

---

## 📊 Dashboards Grafana

### N1 — API Overview (vue principale)
**UID :** `api-overview` | **URL :** http://localhost:3000/d/api-overview

Répondre en 1 écran aux questions : UP ? Taux erreur ? Latence ? Trafic ?

Panneaux :
- Stat : Service UP / Disponibilité SLO % / req/s / taux erreurs 5xx / latence p95
- Time series : Trafic par endpoint / Erreurs 4xx+5xx dans le temps / p50+p95+p99
- Table : Top 5 endpoints les plus lents
- Texte : Liens drilldown N2 + Loki Explore

**Variable :** `$job` (sélecteur de service) + `$env` (environnement)

---

### N2 — Infra / Système (diagnostic)
**UID :** `infra-system` | **URL :** http://localhost:3000/d/infra-system

Pour corréler un incident API avec la saturation système.

Panneaux :
- CPU utilisé % (avec iowait séparé)
- RAM disponible vs utilisée (bytes)
- Espace disque % sur `/`
- Réseau entrant/sortant (Bps)

**Variable :** `$instance` (sélecteur de machine)

---

## 🔔 Alertes

| Alerte                  | Type          | Seuil                    | Sévérité | Durée |
|-------------------------|---------------|--------------------------|----------|-------|
| `HighErrorRate`         | Symptôme métier | > 5% erreurs 5xx        | critical | 2m    |
| `HighP95Latency`        | Symptôme métier | p95 > 1s                | warning  | 3m    |
| `ServiceDown`           | Symptôme métier | up == 0                 | critical | 1m    |
| `LowMemoryAvailable`    | Saturation    | RAM dispo < 15%          | warning  | 5m    |
| `HighCPUUsage`          | Saturation    | CPU > 80%                | warning  | 5m    |
| `PrometheusTargetDown`  | Qualité collecte | up == 0 (toutes targets) | warning | 2m  |
| `ScrapeSamplesZero`     | Qualité collecte | samples == 0            | warning  | 5m    |

Chaque alerte contient :
- **labels :** `service`, `severity`, `env`
- **annotations :** message humain + description technique + lien dashboard + **action concrète à effectuer**

---

## 📋 Requêtes LogQL (Loki — bonus)

### LogQL 1 — Logs d'erreurs du service API

```logql
{service="demo-api"} | json | level="error"
```

**Utilité :** Corréler un pic de 5xx Prometheus avec les messages d'erreur détaillés.

---

### LogQL 2 — Volume d'erreurs par minute (métrique depuis logs)

```logql
sum(rate({service="demo-api"} | json | level="error" [1m]))
```

**Utilité :** Voir si un pic d'erreurs HTTP correspond à un pic de logs ERROR (même fenêtre temporelle que le dashboard Prometheus).

---

## 🗂 Structure du repo

```
supervision-projet/
├── docker-compose.yml          # Stack complète
├── api/
│   ├── Dockerfile
│   ├── main.py                 # API FastAPI instrumentée
│   ├── requirements.txt
│   └── load_generator.py       # Générateur de trafic
├── prometheus/
│   ├── prometheus.yml          # Config scrape
│   ├── promql_queries.promql   # 15+ requêtes documentées
│   └── rules/
│       ├── recording_rules.yml # Pré-calcul des métriques coûteuses
│       └── alert_rules.yml     # 7 alertes actionnables
├── grafana/
│   ├── provisioning/
│   │   ├── datasources/        # Prometheus + Loki auto-provisionnés
│   │   └── dashboards/         # Chargement auto des JSON
│   └── dashboards/
│       ├── api-overview.json   # Dashboard N1
│       └── infra-system.json   # Dashboard N2
├── alertmanager/
│   └── alertmanager.yml        # Routing + inhibition
├── loki/
│   └── loki-config.yml
└── promtail/
    └── promtail-config.yml     # Collecte logs Docker
```

---

## 🎯 Simulation d'incident (démo 2 min)

```bash
# 1. Démarrer le générateur de trafic
python api/load_generator.py --rps 5 &

# 2. Ouvrir Grafana : http://localhost:3000/d/api-overview

# 3. Provoquer un pic d'erreurs (appels manuels)
for i in {1..20}; do curl -s http://localhost:8000/api/error > /dev/null; done

# 4. Observer dans Grafana :
#    → Stat "taux erreurs 5xx" passe au rouge
#    → Time series "Erreurs 4xx/5xx" spike

# 5. Corréler avec les logs Loki :
#    → Grafana > Explore > Loki
#    → {service="demo-api"} | json | level="error"

# 6. Provoquer une latence élevée
for i in {1..5}; do curl -s http://localhost:8000/api/slow &; done
wait

# 7. Observer : stat p95 passe en orange/rouge
#    → Table "Top 5 endpoints lents" → /api/slow en tête
```
