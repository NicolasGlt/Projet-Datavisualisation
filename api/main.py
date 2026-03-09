import time
import random
import logging
import sys
from fastapi import FastAPI, Request, Response
from prometheus_client import (
    Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
)

# ── Logging structuré (Loki-friendly) ─────────────────────────────────────────
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='%(asctime)s level=%(levelname)s service=demo-api %(message)s'
)
logger = logging.getLogger("demo-api")

app = FastAPI(title="Demo API")

# ── Métriques Prometheus ───────────────────────────────────────────────────────
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "http_status"]
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)

IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "HTTP requests currently in progress",
    ["method", "endpoint"]
)

ERROR_COUNT = Counter(
    "http_errors_total",
    "Total HTTP errors (4xx/5xx)",
    ["method", "endpoint", "http_status"]
)

# ── Middleware de métriques ────────────────────────────────────────────────────
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    method = request.method
    path = request.url.path

    # Ignorer /metrics lui-même
    if path == "/metrics":
        return await call_next(request)

    IN_PROGRESS.labels(method=method, endpoint=path).inc()
    start = time.time()
    try:
        response = await call_next(request)
        duration = time.time() - start
        status = response.status_code

        REQUEST_COUNT.labels(method=method, endpoint=path, http_status=status).inc()
        REQUEST_LATENCY.labels(method=method, endpoint=path).observe(duration)

        if status >= 400:
            ERROR_COUNT.labels(method=method, endpoint=path, http_status=status).inc()
            logger.warning(f"path={path} method={method} status={status} duration={duration:.3f}s")
        else:
            logger.info(f"path={path} method={method} status={status} duration={duration:.3f}s")

        return response
    finally:
        IN_PROGRESS.labels(method=method, endpoint=path).dec()

# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {"status": "ok", "service": "demo-api"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/api/products")
async def get_products():
    await _simulate_work(0.05, 0.3)
    return {"products": [{"id": i, "name": f"Product {i}"} for i in range(1, 11)]}

@app.get("/api/orders")
async def get_orders():
    await _simulate_work(0.1, 0.5)
    if random.random() < 0.05:   # 5% d'erreurs
        logger.error("path=/api/orders method=GET error=database_timeout")
        return Response(status_code=503, content="Service Unavailable")
    return {"orders": [{"id": i, "status": "shipped"} for i in range(1, 6)]}

@app.get("/api/users/{user_id}")
async def get_user(user_id: int):
    await _simulate_work(0.02, 0.15)
    if user_id > 1000:
        logger.warning(f"path=/api/users/{user_id} error=not_found")
        return Response(status_code=404, content="User not found")
    return {"id": user_id, "name": f"User {user_id}", "active": True}

@app.get("/api/slow")
async def slow_endpoint():
    """Endpoint volontairement lent pour tester les alertes de latence."""
    await _simulate_work(1.0, 3.0)
    return {"message": "slow response"}

@app.get("/api/error")
async def force_error():
    """Endpoint qui retourne toujours une erreur 500."""
    logger.error("path=/api/error method=GET error=forced_internal_error")
    return Response(status_code=500, content="Internal Server Error")

@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

# ── Utilitaire ─────────────────────────────────────────────────────────────────
async def _simulate_work(min_s: float, max_s: float):
    import asyncio
    await asyncio.sleep(random.uniform(min_s, max_s))
