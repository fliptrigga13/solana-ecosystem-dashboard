# Solana Ecosystem Dashboard

![hourly](https://fliptrigga13.github.io/solana-ecosystem-dashboard/badge.svg)
![license](https://img.shields.io/badge/license-MIT-green)

Automated, zero-API-key Solana ecosystem monitor. Produces an interactive
dark-theme dashboard, Markdown report, and JSON snapshot — refreshing hourly.

**Built for:** Superteam Canada bounty — *"Develop Solana Ecosystem
Auto-Updating Report & Interactive Dashboard"* (1,000 USDG)

> **For validators & builders:** free hourly alert digests (Telegram/email/
> webhook) and a paid data API (`/v1/snapshot` free tier · pro $49/mo ·
> enterprise $499/mo). Featured validator/project slots from $150/mo.
> Details: [`api/DOCS.md`](api/DOCS.md), [`alerts/tiers.md`](alerts/tiers.md),
> [`sponsors.json`](sponsors.json).

## Quick start

```bash
python autoupdate.py            # one refresh cycle (collect + detect + generate)
python autoupdate.py --loop     # built-in hourly auto-update loop
python autoupdate.py --loop 900 # custom interval (seconds)
```

Outputs after each cycle:

| File | Format | Purpose |
|---|---|---|
| `index.html` | Interactive dark-theme HTML | Human dashboard (**live** on GitHub Pages) |
| `report.md` | Markdown | Human-readable summary |
| `data.json` | JSON | Machine-readable snapshot |
| `data-history.jsonl` | JSONL | Historical snapshots for anomaly baseline |

## Live deployment

- **Dashboard:** https://fliptrigga13.github.io/solana-ecosystem-dashboard/
- **Auto-update:** the pipeline rebuilds everything on a configurable
  schedule (`.github/workflows/update.yml` runs hourly in CI; a local
  Task Scheduler job runs the same pipeline hourly today — see note below)
  and commits fresh outputs to `main`, so the commit history is public
  proof of continuous automated updates.

> **Status note (2026-08-25):** GitHub Actions runs are temporarily blocked
> by a repository-owner billing lock; until it clears, an identical local
> pipeline produces the same timestamped "data refresh" commits hourly.
- Data sources are free/public; no API keys anywhere.

## Metrics covered

**Network:** avg/peak TPS (5h window), slot, block height, epoch progress,
active validators, delinquent validators, total stake, top-10 validators by
stake with commission rates, Nakamoto coefficient, top-10/top-20 stake share,
native staking APY estimate.

**Validator economics (Stakewiz):** stake-weighted avg APY, commission, uptime,
and client share — Jito-Solana vs Agave vs Firedancer.

**MEV:** Jito MEV tips revenue 24h + live tip-floor market (median landed tip).

**Market structure:** per-venue DEX volume (PumpSwap, Orca, Raydium, …),
per-issuer stablecoin supply (USDC, USDT, USDGO, USD1, …).

**Governance:** latest SIMD proposals + Agave/Firedancer releases via GitHub.

**Economic & DeFi:** SOL price + 24h change, market cap, DeFi TVL,
stablecoin supply, 24h DEX volume, 24h fees, 24h REV, derived avg fee per
transaction.

**Ecosystem:** per-chain tokenized assets (RWA incl. xStocks equities),
ecosystem & community news feed (Solana Forums + Decrypt RSS), and an
upcoming-upgrades panel (Alpenglow, SIMD-0525).

**Anomaly detection:** rolling-baseline checks with severity levels —
TPS ±30%, delinquent surge >100%, SOL price ±10%, TVL ±15%, stablecoins ±5%,
DEX volume ±50%, fees/REV ±60%, RWA TVL ±10%, Nakamoto ±10%, validator APY ±15%,
MEV tips ±50%. Missing core metrics fail the
run loudly instead of publishing nulls.

## Data sources (all free, no API keys)

- Solana public RPC: `getEpochInfo`, `getRecentPerformanceSamples`,
  `getVoteAccounts`, `getTokenSupply`, `getInflationRate`
- DeFiLlama public API: DeFi TVL
- DeFiLlama stablecoins API: stablecoin circulating supply on Solana + per-issuer breakdown
- DeFiLlama overviews: DEX volume, protocol fees/REV, per-chain RWA TVLs,
  per-venue DEX volume, Jito MEV tips revenue
- RWA fallbacks (when DeFiLlama's per-chain RWA series is empty): on-chain
  token supply x NAV (BUIDL), Ondo issuer API, vault balances (Hastra),
  Jupiter token supply x underlying share price (xStocks, Ondo Global Markets),
  Yahoo Finance underlying closes for price gaps. Per-asset source recorded in
  each snapshot (`rwa.rwa_sources`).
- CoinGecko public API: SOL price / market cap
- Stakewiz public API: validator APY, commission, version, client identity (Jito)
- Jito bundles API: live tip-floor percentiles
- GitHub REST API (unauthenticated): SIMD proposals, Agave/Firedancer releases
- News RSS: forum.solana.com/latest.rss + decrypt.co/feed (Solana-filtered)

## Architecture

```
collector.py      fetch network + economic data from free public sources
anomaly.py        compare against rolling history; flag deviations
generate_report.py    produce report.md
generate_dashboard.py produce dashboard.html (Chart.js dark theme)
autoupdate.py     orchestrator: collect -> detect -> generate (loop or once)
```

Zero third-party dependencies. Python 3.10+ standard library only.
Same proven pattern as [Bounty Radar](https://github.com/fliptrigga13/bounty-radar).

## Scheduling

Built-in loop:
```bash
python autoupdate.py --loop 3600   # hourly
```

Or via OS scheduler:
- **Linux cron:** `0 * * * * cd /path/to/solana-dashboard && python3 autoupdate.py`
- **Windows Task Scheduler:** action `python.exe`, argument `autoupdate.py`,
  start-in directory = project folder

## License

MIT
