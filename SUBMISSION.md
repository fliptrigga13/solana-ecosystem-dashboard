# Solana Ecosystem Dashboard — Bounty Submission (v2)

Superteam Canada bounty: "Develop Solana Ecosystem Auto-Updating Report &
Interactive Dashboard" ($1,000 USDG · deadline 2026-08-31 23:59 EDT).

## What this is

An automated, zero-API-key Solana ecosystem monitor producing three output
formats from every refresh:

- `index.html` — dark-theme interactive dashboard (Chart.js), live on GitHub
  Pages: https://fliptrigga13.github.io/solana-ecosystem-dashboard/
- `report.md` — human-readable Markdown report
  https://github.com/fliptrigga13/solana-ecosystem-dashboard/blob/main/report.md
- `data.json` — machine-readable snapshot
  https://github.com/fliptrigga13/solana-ecosystem-dashboard/blob/main/data.json

## Requirements coverage (listing §5)

| Listing asks | Shipped where |
|---|---|
| TPS, slot time, block height, epoch progress | Dashboard stat cards; report "Network Performance"; data.json network.* |
| Active vs delinquent validators, stake distribution, top validators, commission tracking | Stat cards + top-10 table with commission; report "Validators" |
| Delinquency alerts | anomaly.py threshold (>100% delinquent surge) fires WARNING/CRITICAL |
| SOL price movements | Stat card with 24h change; ±10% anomaly threshold |
| Stablecoin supply | DeFiLlama stablecoincharts/Solana → stat card + report |
| DEX volume | DeFiLlama overview/dexs/Solana (24h + 1d change) |
| REV (Real Economic Value) | DeFiLlama dailyRevenue overview → stat card + report |
| Transaction fees | 24h protocol fees **plus derived avg fee per transaction** (24h fees ÷ est. daily txns) |
| Tokenized asset volumes (esp. equities) | Per-chain RWA panel: BlackRock BUIDL, xStocks tokenized equities, Ondo, Hastra, Invesco USTB |
| Ecosystem & community news | Keyless RSS section: official Solana Forums + Decrypt (Solana-filtered), rendered as linked feed |
| Upcoming upgrades (Alpenglow, SIMD-525) | Upgrades panel with verified status lines + source links |

## Automation

- Pipeline: `collector.py` → `anomaly.py` → `generate_report.py` +
  `generate_dashboard.py`, orchestrated by `autoupdate.py`
  (loop mode or one-shot per external scheduler trigger).
- Configurable interval everywhere: `--loop <seconds>`, cron/Task Scheduler,
  or the repo's GitHub Actions workflow `.github/workflows/update.yml`
  (`schedule: hourly`).
- Every refresh appends a full snapshot to `data-history.jsonl` and is
  committed to `main` — the commit history doubles as an uptime log.
- Zero API keys, zero third-party dependencies: Python 3.10+ stdlib only.

**Honest status note (Aug 25):** GitHub Actions runs are currently blocked by
a repository-owner account billing lock ("The job was not started because
your account is locked due to a billing issue"). The hourly rebuild design is
fully in place in-repo; until the lock clears, a local Task Scheduler job
runs the identical pipeline hourly and pushes the same "data refresh"
commits — see the commit history for real, timestamped hourly-refresh
evidence. Commit history available on request / visible in-repo either way.

## Anomaly detection

Every refresh compares against a rolling window of the last 20 stored
snapshots with metric-specific thresholds: TPS ±30%, delinquent validators
+100%, SOL price ±10%, TVL ±15%, stablecoins ±5%, DEX volume ±50%,
fees/REV ±60%, RWA TVL ±10%. Breaches carry direction, magnitude, and
WARNING/CRITICAL severity. A missing or zero core metric fails the run
loudly (named RuntimeError) — partial snapshots are never published silently.

## Data sources (all free, no API keys)

- Solana public RPC `api.mainnet-beta.solana.com` (+ publicnode fallback):
  getEpochInfo, getRecentPerformanceSamples, getVoteAccounts, getTokenSupply
- DeFiLlama family: chain TVL, stablecoin supply, DEX volume, fees/revenue,
  per-chain RWA protocol TVLs
- CoinGecko public API: SOL price, market cap
- News RSS: forum.solana.com/latest.rss + decrypt.co/feed (Solana-filtered)

## Setup & run

```bash
python autoupdate.py            # one refresh cycle
python autoupdate.py --loop     # built-in hourly loop
```

Outputs land in `index.html` / `report.md` / `data.json`. Schedule via cron,
Windows Task Scheduler (`watch_hourly.cmd` included), or push to GitHub and
let Actions run it hourly.

## QA evidence (executed Aug 25, 2026)

- Loud-failure gate: 13/13 core metrics individually nulled → named
  RuntimeError each (qa_negative_tests.py)
- News zero-item case → loud failure (dead-feed test)
- Anomaly fire/quiet: injected -12.9% stablecoin move fired CRITICAL;
  normal variation stayed silent (qa_anomaly_tests.py)
- Live render check (dedicated headless Chrome CDP): 13 stat cards,
  8 news links, RWA + validator tables, upgrades panel, chart canvas,
  dark theme rgb(11,15,26) — all PASS on the deployed Pages URL
- Live raw output check: data.json served with news items and
  avg_fee_per_txn_usd present
