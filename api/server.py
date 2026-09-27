#!/usr/bin/env python3
"""Paid JSON data API for the Solana Ecosystem Dashboard. Stdlib only.

Run:  python3 api/server.py            (PORT env, default 8080; binds 127.0.0.1)
        DATA_DIR=/path/to/repo python3 api/server.py

Deploy behind a reverse proxy that terminates TLS; never expose this directly.
"""
import json
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
API_DIR = os.environ.get("API_DIR", HERE)
DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(HERE))

sys.path.insert(0, HERE)
sys.path.insert(0, DATA_DIR)

import auth  # noqa: E402
import limits  # noqa: E402

SNAPSHOT_FILE = os.path.join(DATA_DIR, "data.json")
HISTORY_FILE = os.path.join(DATA_DIR, "data-history.jsonl")
HISTORY_LIMIT_CAP = 500

# Flattened scalar metrics available via /v1/metrics?name=...
METRIC_PATHS = {
    "avg_tps_5h": ("network", "avg_tps_5h"),
    "max_tps_5h": ("network", "max_tps_5h"),
    "epoch": ("network", "epoch"),
    "epoch_progress_pct": ("network", "epoch_progress_pct"),
    "validators_active": ("network", "validators_active"),
    "validators_delinquent": ("network", "validators_delinquent"),
    "sol_price_usd": ("economic", "sol_price_usd"),
    "sol_price_change_24h_pct": ("economic", "sol_price_change_24h_pct"),
    "defi_tvl_billion": ("economic", "defi_tvl_billion"),
    "stablecoin_supply_billion": ("defi", "stablecoin_supply_billion"),
    "dex_volume_24h_billion": ("defi", "dex_volume_24h_billion"),
    "fees_24h_million": ("defi", "fees_24h_million"),
    "rev_24h_million": ("defi", "rev_24h_million"),
    "avg_fee_per_txn_usd": ("defi", "avg_fee_per_txn_usd"),
    "tokenized_assets_billion": ("rwa", "tokenized_assets_billion"),
    "nakamoto_coefficient": ("network", "nakamoto_coefficient"),
    "top10_stake_share_pct": ("network", "top10_stake_share_pct"),
    "native_apy_estimate_pct": ("network", "native_apy_estimate_pct"),
    "avg_validator_apy_pct": ("validators", "avg_apy_pct"),
    "avg_validator_commission_pct": ("validators", "avg_commission_pct"),
    "jito_client_share_pct": ("validators", "client_share_pct", "jito-solana"),
    "jito_mev_tips_24h_usd": ("mev", "jito_mev_tips_24h_usd"),
    "jito_tip_floor_median_sol": ("mev", "jito_tip_floor_median_sol"),
}

limiter = limits.RateLimiter(os.path.join(API_DIR, "usage.json"))


def load_snapshot():
    try:
        with open(SNAPSHOT_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def load_history():
    out = []
    try:
        with open(HISTORY_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        pass
    return out


def _metric_value(snap: dict, name: str):
    path = METRIC_PATHS[name]
    val = snap
    for key in path:
        val = val.get(key) if isinstance(val, dict) else None
        if val is None:
            break
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        return None
    return val


def dispatch(method: str, path: str, headers: dict, _limiter=None):
    """Route one request. Returns (status_code, body_dict, extra_headers).

    Pure logic — no sockets — so tests can exercise it directly.
    """
    headers = {str(k).lower(): v for k, v in (headers or {}).items()}
    parsed = urllib.parse.urlparse(path)
    route = parsed.path
    qs = urllib.parse.parse_qs(parsed.query)

    if method != "GET":
        return 405, {"error": "method not allowed"}, {}

    if route == "/v1/health":
        snap = load_snapshot()
        return 200, {
            "ok": True,
            "snapshot_ts": snap.get("collected_at") if isinstance(snap, dict) else None,
        }, {}

    if route not in ("/v1/snapshot", "/v1/history", "/v1/metrics", "/v1/anomalies"):
        return 404, {"error": "not found"}, {}

    # ---- auth ----
    api_key = headers.get("x-api-key")
    if not api_key:
        return 401, {"error": "missing api key: send it in the X-API-Key header"}, {}
    rec = auth.verify(api_key)
    if rec is None:
        return 401, {"error": "invalid api key"}, {}
    if rec.get("revoked"):
        return 401, {"error": "api key revoked"}, {}
    if auth.is_expired(rec):
        return 401, {"error": "api key expired"}, {}
    tier = rec.get("tier")

    # ---- tier gating ----
    if route not in auth.TIER_ENDPOINTS.get(tier, set()):
        return 403, {
            "error": "tier '%s' may not access %s (requires pro or enterprise)" % (tier, route)
        }, {}

    # ---- rate limiting ----
    quota = auth.TIER_QUOTAS.get(tier)
    if quota is not None:
        lim = _limiter if _limiter is not None else limiter
        allowed, remaining, retry_after = lim.check(rec["key_hash"], quota)
        if not allowed:
            return 429, {
                "error": "rate limit exceeded",
                "retry_after_seconds": retry_after,
            }, {"Retry-After": str(retry_after)}

    # ---- routes ----
    if route == "/v1/snapshot":
        snap = load_snapshot()
        if snap is None:
            return 503, {"error": "snapshot data unavailable"}, {}
        return 200, snap, {}

    if route == "/v1/history":
        raw = qs.get("limit", ["100"])[0]
        try:
            limit = int(raw)
        except (ValueError, TypeError):
            return 400, {"error": "limit must be an integer"}, {}
        if limit < 1:
            return 400, {"error": "limit must be >= 1"}, {}
        limit = min(limit, HISTORY_LIMIT_CAP)
        hist = load_history()
        snaps = hist[-limit:]
        return 200, {"snapshots": snaps, "count": len(snaps), "limit": limit}, {}

    if route == "/v1/metrics":
        name = qs.get("name", [None])[0]
        if not name:
            return 400, {
                "error": "missing 'name' query parameter",
                "available": sorted(METRIC_PATHS),
            }, {}
        if name not in METRIC_PATHS:
            return 400, {
                "error": "unknown metric %r" % name,
                "available": sorted(METRIC_PATHS),
            }, {}
        points = []
        for snap in load_history():
            val = _metric_value(snap, name)
            if val is None:
                continue
            points.append({"t": snap.get("collected_at"), "v": val})
        return 200, {"metric": name, "points": points, "count": len(points)}, {}

    if route == "/v1/anomalies":
        snap = load_snapshot()
        if snap is None:
            return 503, {"error": "snapshot data unavailable"}, {}
        try:
            import anomaly
        except ImportError:
            return 503, {"error": "anomaly module unavailable"}, {}
        findings = anomaly.detect_anomalies(snap, load_history())
        return 200, {
            "snapshot_ts": snap.get("collected_at"),
            "anomalies": findings,
            "count": len(findings),
        }, {}

    return 404, {"error": "not found"}, {}  # pragma: no cover


class APIHandler(BaseHTTPRequestHandler):
    server_version = "SolanaDataAPI/1.0"

    def do_GET(self):
        status, body, extra = dispatch("GET", self.path, dict(self.headers))
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        for k, v in extra.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args):
        # Minimal access log: never includes request headers (no key material).
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main():
    port = int(os.environ.get("PORT", "8080"))
    server = ThreadingHTTPServer(("127.0.0.1", port), APIHandler)
    print("solana data api on 127.0.0.1:%d (DATA_DIR=%s)" % (port, DATA_DIR), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
