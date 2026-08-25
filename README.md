# Solana Ecosystem Dashboard

Automated, zero-API-key Solana ecosystem monitor. Produces an interactive
dark-theme dashboard, Markdown report, and JSON snapshot — refreshing on a
configurable schedule.

**Built for:** Superteam Canada bounty — *"Develop Solana Ecosystem
Auto-Updating Report & Interactive Dashboard"* (1,000 USDG)

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
stake with commission rates.

**Economic & DeFi:** SOL price + 24h change, market cap, DeFi TVL,
stablecoin supply, 24h DEX volume, 24h fees, 24h REV, derived avg fee per
transaction.

**Ecosystem:** per-chain tokenized assets (RWA incl. xStocks equities),
ecosystem & community news feed (Solana Forums + Decrypt RSS), and an
upcoming-upgrades panel (Alpenglow, SIMD-0525).

**Anomaly detection:** rolling-baseline checks with severity levels —
TPS ±30%, delinquent surge >100%, SOL price ±10%, TVL ±15%, stablecoins ±5%,
DEX volume ±50%, fees/REV ±60%, RWA TVL ±10%. Missing core metrics fail the
run loudly instead of publishing nulls.

## Data sources (all free, no API keys)

- Solana public RPC: `getEpochInfo`, `getRecentPerformanceSamples`,
  `getVoteAccounts`, `getTokenSupply`
- DeFiLlama public API: DeFi TVL
- DeFiLlama stablecoins API: stablecoin circulating supply on Solana
- DeFiLlama overviews: DEX volume, protocol fees/REV, per-chain RWA TVLs
- CoinGecko public API: SOL price / market cap
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
