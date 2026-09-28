# Solana Dashboard Data API

Paid JSON API over the Solana Ecosystem Dashboard data. **Stdlib only**
(`http.server`, no Flask/FastAPI) — matching the repo's zero-dependency ethos.
Python 3.10+.

## Quick start

```bash
# from the repo root
python3 api/mkkey.py --name acme --tier pro     # prints the key ONCE
PORT=8080 DATA_DIR=/path/to/repo python3 api/server.py

curl -H "X-API-Key: <key>" http://127.0.0.1:8080/v1/snapshot
```

`DATA_DIR` defaults to the repo root (where `data.json` lives); `API_DIR`
defaults to `api/` (where `keys.json` / `usage.json` live).

## Endpoints

| Method | Path | Auth | Tier | Description |
|---|---|---|---|---|
| GET | `/v1/health` | no | — | `{ok, snapshot_ts}` liveness probe |
| GET | `/v1/snapshot` | yes | free+ | Latest full snapshot (`data.json`) |
| GET | `/v1/history?limit=N` | yes | pro+ | Last N snapshots, newest last (default 100, cap 500) |
| GET | `/v1/metrics?name=X` | yes | free+ | Time series `[{t, v}]` of one metric across history |
| GET | `/v1/anomalies` | yes | pro+ | Anomaly report: latest snapshot vs history (repo's `anomaly.py`) |

Available `name` values for `/v1/metrics`: `avg_tps_5h`, `max_tps_5h`,
`epoch`, `epoch_progress_pct`, `validators_active`, `validators_delinquent`,
`sol_price_usd`, `sol_price_change_24h_pct`, `defi_tvl_billion`,
`stablecoin_supply_billion`, `dex_volume_24h_billion`, `fees_24h_million`,
`rev_24h_million`, `avg_fee_per_txn_usd`, `tokenized_assets_billion`.

Status codes: `200` ok · `400` bad parameter · `401` missing/invalid/revoked
key · `403` tier insufficient · `404` unknown path · `405` non-GET ·
`429` rate limited (with `Retry-After` header) · `503` data unavailable.

### Example calls

```bash
curl http://127.0.0.1:8080/v1/health
curl -H "X-API-Key: <key>" "http://127.0.0.1:8080/v1/history?limit=50"
curl -H "X-API-Key: <key>" "http://127.0.0.1:8080/v1/metrics?name=sol_price_usd"
curl -H "X-API-Key: <key>" http://127.0.0.1:8080/v1/anomalies
```

## Auth & tiers

Keys go in the `X-API-Key` header. Only **SHA-256 hashes** are stored in
`api/keys.json` — plaintext keys are never logged or persisted. The plaintext
is shown exactly once at issuance; deliver it to the customer out of band.

| Tier | Price | Endpoints | Rate limit |
|---|---|---|---|
| free | $0 | snapshot, metrics | 60 req / rolling 24h |
| pro | **$49/mo** | everything | 10,000 req / rolling 24h |
| enterprise | **$499/mo** | everything | unlimited |

### Key lifecycle

```bash
python3 api/mkkey.py --name acme --tier pro   # issue (prints key ONCE)
python3 api/mkkey.py --list                   # list (hash prefixes only)
python3 api/mkkey.py --revoke acme            # revoke by name or hash prefix
```

Rotation = revoke the old key, issue a new one. There is no expiry field yet;
add one to `auth.py` if you need time-boxed keys.

## Rate limiting

Per-key rolling 24h sliding window, kept in memory and flushed to
`api/usage.json` every 60s and on clean shutdown, so restarts don't reset
abuse counters. Exceeding the quota returns `429` with `Retry-After`.

## Files

- `server.py` — HTTP server + routing (`dispatch()` is pure logic, no sockets)
- `auth.py` — key issuance/verification, tier definitions and quotas
- `limits.py` — sliding-window rate limiter with usage persistence
- `mkkey.py` — operator CLI for key management
- `test_api.py` — `unittest` suite (no network): `python3 api/test_api.py`

## Deployment notes

- **Run behind a reverse proxy with TLS** (nginx/Caddy). This server binds
  `127.0.0.1` only and speaks plain HTTP — never expose it directly.
- Point `DATA_DIR` at a checkout that the hourly `autoupdate.py` refreshes so
  the API always serves the latest snapshot.
- Restrict file permissions: `chmod 600 api/keys.json api/usage.json`;
  back up `keys.json` (losing it orphans every customer key).
- Run under a process supervisor (systemd) with `PORT` set; logs go to stderr
  and never include key material.
- `usage.json` grows with distinct keys × hits; prune entries for revoked keys
  periodically if the key population churns.

## TODO (owner)

- [x] Prices set by owner 2026-09-27: pro $49/mo, enterprise $499/mo (change anytime)
- [ ] Choose hosting + TLS termination (reverse proxy config)
- [ ] Key distribution process (how customers receive their one-time key)
- [ ] Billing integration (e.g. Stripe) + webhook to auto-issue/revoke keys
- [ ] Consider key expiry for trial/pro keys
