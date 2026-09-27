# Solana Ecosystem Dashboard — Public Data API

Hourly-updated Solana network data: validators, TPS/fees, SOL price, DeFi TVL,
stablecoins, DEX volume, RWA tokenization. Machine-readable, stable schema,
zero signup wall on the free tier.

Base URL: `https://api.yourdomain.com` *(hosting pending — local dev: `http://127.0.0.1:8080`)*

## Quickstart

```bash
# 1. Get a free key (DM the operator — no card required)
# 2. Call:
curl -H "X-API-Key: <redacted> https://api.yourdomain.com/v1/snapshot
```

Keys go in the `X-API-Key` header. Only SHA-256 hashes are stored server-side;
the plaintext key is shown once at issuance — store it now.

## Endpoints

| Method | Path | Auth | Tier | Description |
|---|---|---|---|---|
| GET | `/v1/health` | no | — | `{ok, snapshot_ts}` liveness probe |
| GET | `/v1/snapshot` | yes | free+ | Latest full snapshot |
| GET | `/v1/metrics?name=X` | yes | free+ | Time series `[{t, v}]` of one metric |
| GET | `/v1/history?limit=N` | yes | pro+ | Last N snapshots, newest last (default 100, cap 500) |
| GET | `/v1/anomalies` | yes | pro+ | Anomaly report: latest snapshot vs history |

Metric names for `/v1/metrics`: `avg_tps_5h`, `max_tps_5h`, `epoch`,
`epoch_progress_pct`, `validators_active`, `validators_delinquent`,
`sol_price_usd`, `sol_price_change_24h_pct`, `defi_tvl_billion`,
`stablecoin_supply_billion`, `dex_volume_24h_billion`, `fees_24h_million`,
`rev_24h_million`, `avg_fee_per_txn_usd`, `tokenized_assets_billion`,
`nakamoto_coefficient`, `top10_stake_share_pct`, `native_apy_estimate_pct`,
`avg_validator_apy_pct`, `avg_validator_commission_pct`, `jito_client_share_pct`,
`jito_mev_tips_24h_usd`, `jito_tip_floor_median_sol`.

Status codes: `200` ok · `400` bad parameter · `401` missing/invalid/revoked key ·
`403` tier insufficient · `404` unknown path · `405` non-GET ·
`429` rate limited (with `Retry-After` header) · `503` data unavailable.

## Tiers, quotas, overage

| Tier | Price | Endpoints | Quota (rolling 24h) | Overage |
|---|---|---|---|---|
| free | $0 | snapshot, metrics | 60 requests | hard cap — upgrade for more |
| pro | **$49/mo** | everything | 10,000 requests | $0.15 per 1,000 requests beyond quota, billed monthly |
| enterprise | **$499/mo** | everything | unlimited | n/a |

Overage policy (proposed 2026-09-27, market-norm: at/below base unit rate):
overage is metered, never throttled mid-month without notice — you get an
email/webhook at 80% and 100% of quota. Enterprise is flat unlimited.

## Key lifecycle

- Issue: operator runs `api/mkkey.py --name <client> --tier <tier>`; key printed once.
- Rotation: revoke old, issue new. No downtime.
- Revocation: immediate. Compromised key? Ask and it's dead in seconds.
- Expiry: time-boxed eval keys available on request.

## Examples

```bash
# Latest snapshot (free tier)
curl -H "X-API-Key: <redacted> https://api.yourdomain.com/v1/snapshot

# SOL price history as a time series (free tier)
curl -H "X-API-Key: <redacted> \
  "https://api.yourdomain.com/v1/metrics?name=sol_price_usd"

# Last 50 snapshots (pro tier)
curl -H "X-API-Key: <redacted> \
  "https://api.yourdomain.com/v1/history?limit=50"

# Current anomaly report (pro tier)
curl -H "X-API-Key: <redacted> https://api.yourdomain.com/v1/anomalies
```

## Data provenance

Every snapshot is committed to the public repo
(`https://github.com/fliptrigga13/solana-ecosystem-dashboard`):
`data.json` (latest) + `data-history.jsonl` (full history). The API serves the
same bytes — audit anything we return against the repo.

## Citing

Researchers: the snapshot schema is stable and every datapoint is traceable to
a repo commit. Cite as: *Solana Ecosystem Dashboard,
https://fliptrigga13.github.io/solana-ecosystem-dashboard/, accessed YYYY-MM-DD.*
