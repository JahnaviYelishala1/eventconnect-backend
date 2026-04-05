"""Safe smoke test for the deployed API.

- Fetches OpenAPI schema from /openapi.json
- Calls only GET/HEAD endpoints that have NO path params (no {id})
- Never calls POST/PUT/PATCH/DELETE to avoid side effects (emails, payments, DB writes)

Usage:
  python scripts/smoke_endpoints.py --base-url https://eventconnect-backend.onrender.com

Exit codes:
  0: no 5xx/network failures in tested endpoints
  1: at least one tested endpoint failed (5xx or request error)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
from dataclasses import dataclass
from typing import Any

import requests


@dataclass(frozen=True)
class Result:
    method: str
    path: str
    url: str
    status: int | None
    ok: bool
    note: str
    elapsed_ms: int


def _join(base_url: str, path: str) -> str:
    return urllib.parse.urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))


def _is_safe_to_call(method: str, path: str) -> bool:
    if method.lower() not in {"get", "head"}:
        return False
    if "{" in path or "}" in path:
        return False
    # Skip websocket routes that show up in the app (not in OpenAPI, but be defensive)
    if path.startswith("/ws") or "/ws/" in path:
        return False
    return True


def _load_openapi(base_url: str, timeout: float) -> dict[str, Any]:
    url = _join(base_url, "/openapi.json")
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _call(session: requests.Session, method: str, url: str, timeout: float) -> tuple[int, str]:
    r = session.request(method=method.upper(), url=url, timeout=timeout, allow_redirects=True)
    return r.status_code, r.headers.get("content-type", "")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://eventconnect-backend.onrender.com")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()

    base_url: str = args.base_url
    timeout: float = args.timeout
    limit: int = args.limit

    try:
        openapi = _load_openapi(base_url, timeout=timeout)
    except Exception as exc:
        print(f"FAILED: could not load OpenAPI schema from {base_url}/openapi.json: {exc}")
        return 1

    paths: dict[str, Any] = openapi.get("paths", {})

    candidates: list[tuple[str, str]] = []
    for path, ops in paths.items():
        if not isinstance(ops, dict):
            continue
        for method in ops.keys():
            if _is_safe_to_call(method, path):
                candidates.append((method.upper(), path))

    candidates = sorted(set(candidates))
    if limit:
        candidates = candidates[:limit]

    session = requests.Session()

    results: list[Result] = []
    failures = 0

    for method, path in candidates:
        url = _join(base_url, path)
        t0 = time.perf_counter()
        try:
            status, content_type = _call(session, method, url, timeout=timeout)
            elapsed_ms = int((time.perf_counter() - t0) * 1000)

            # Interpret status codes:
            # - 2xx/3xx: OK
            # - 401/403: protected but route is reachable (OK)
            # - 422: likely requires query params (still indicates route + validation working)
            # - 404: potential routing issue
            # - 5xx: server error
            ok = (
                200 <= status < 400
                or status in {401, 403, 422}
            )
            note = content_type
            if status in {401, 403}:
                note = "protected (auth required)"
            elif status == 422:
                note = "validation error (likely missing query/body)"
            elif status == 404:
                note = "not found"

            if not ok:
                failures += 1

            results.append(Result(method, path, url, status, ok, note, elapsed_ms))
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            failures += 1
            results.append(Result(method, path, url, None, False, f"request error: {exc}", elapsed_ms))

    ok_count = sum(1 for r in results if r.ok)
    total = len(results)

    print(f"Base URL: {base_url}")
    print(f"Tested endpoints: {total} (safe GET/HEAD only; no path params)")
    print(f"OK: {ok_count}  FAIL: {failures}")

    if failures:
        print("\nFailures:")
        for r in results:
            if r.ok:
                continue
            print(f"- {r.method} {r.path} -> {r.status} ({r.note}) {r.elapsed_ms}ms")

    # Optional: emit JSON summary for CI
    summary = {
        "base_url": base_url,
        "tested": total,
        "ok": ok_count,
        "fail": failures,
        "results": [r.__dict__ for r in results],
    }
    print("\n--- JSON ---")
    print(json.dumps(summary, indent=2))

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
