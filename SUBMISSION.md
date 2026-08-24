# Solana Ecosystem Dashboard — Bounty Submission

Superteam Canada bounty: "Develop Solana Ecosystem Auto-Updating Report & Interactive Dashboard" (1,000 USDG).

## What this is

An automated, zero-API-key Solana ecosystem monitor producing three output formats:
- `dashboard.html` — dark-theme interactive dashboard (Chart.js)
- `report.md` — human-readable Markdown report
- `data.json` — machine-readable snapshot

## Metrics covered

**Network:** TPS (avg + peak over 5h), slot, block height, epoch progress
**Validators:** active count, delinquent count, total stake, top-10 by stake with commission
**Economic:** SOL price + 24h change, market cap, DeFi TVL

## Data sources (all free, no API keys)

- Solana public RPC (`api.mainnet-beta.solana.com`): getEpochInfo, getRecentPerformanceSamples, getVoteAccounts, getTokenSupply
- DeFiLlama public API: DeFi TVL
- CoinGecko public API: SOL price/market cap

## Run it

```bash
python collector.py          # collect -> data.json
python generate_report.py    # data.json -> report.md
python generate_dashboard.py # data.json -> dashboard.html

# or one-shot refresh:
python refresh.py
```

Schedule hourly via cron/Task Scheduler for an auto-updating report.

## Architecture note

Same proven pattern as Bounty Radar (github.com/fliptrigga13/bounty-radar):
poll free sources → normalize → persist → deliver in multiple formats.
Zero third-party dependencies; Python stdlib only.
