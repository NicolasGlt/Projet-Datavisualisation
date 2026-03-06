#!/usr/bin/env python3
"""
load_generator.py — génère du trafic réaliste vers l'API de démo.
Usage : python load_generator.py [--url http://localhost:8000] [--rps 5]
"""
import asyncio
import random
import argparse
import httpx

ENDPOINTS = [
    ("/api/products",    "GET",  0.40),
    ("/api/orders",      "GET",  0.25),
    ("/api/users/1",     "GET",  0.15),
    ("/api/users/9999",  "GET",  0.05),   # → 404
    ("/api/slow",        "GET",  0.05),   # → latence élevée
    ("/api/error",       "GET",  0.05),   # → 500
    ("/health",          "GET",  0.05),
]

async def send_request(client: httpx.AsyncClient, base_url: str):
    path, method, _ = random.choices(
        ENDPOINTS, weights=[e[2] for e in ENDPOINTS], k=1
    )[0]
    try:
        await client.request(method, f"{base_url}{path}", timeout=10)
    except Exception as e:
        print(f"[ERR] {method} {path} → {e}")

async def main(base_url: str, rps: int):
    print(f"🚀 Load generator → {base_url} at ~{rps} req/s  (Ctrl+C to stop)")
    async with httpx.AsyncClient() as client:
        while True:
            tasks = [send_request(client, base_url) for _ in range(rps)]
            await asyncio.gather(*tasks)
            await asyncio.sleep(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--rps", type=int, default=5)
    args = parser.parse_args()
    asyncio.run(main(args.url, args.rps))
