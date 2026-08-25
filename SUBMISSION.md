# Solana Ecosystem Dashboard — Bounty Submission

Superteam Canada bounty: "Develop Solana Ecosystem Auto-Updating Report & Interactive Dashboard" (1,000 USDG).

## What this is

An automated, zero-API-key Solana ecosystem monitor producing three output formats:
- `index.html` — dark-theme interactive dashboard (Chart.js), live on GitHub Pages: https://fliptrigga13.github.io/solana-ecosystem-dashboard/
- `report.md` — human-readable Markdown report
- `data.json` — machine-readable snapshot

## Metrics covered

**Network:** TPS (avg + peak over 5h), slot, block height, epoch progress
**Validators:** active count, delinquent count, total stake, top-10 by stake with commission
**Economic:** SOL price + 24h change, market cap, DeFi TVL
**DeFi depth:** stablecoin circulating supply on Solana, 24h DEX volume (+1d change), 24h protocol fees, 24h REV
**Tokenized assets (RWA):** per-chain TVL on Solana for the six largest protocols (BlackRock BUIDL, Ondo Yield Assets, xStocks, Hastra, Ondo Global Markets, Invesco USTB)
**Upcoming upgrades panel:** Alpenglow (Votor + Rotor) and SIMD-0525 reduced slot times, with verified status lines

Anomaly detection compares each run against the trailing snapshot history and
flags deviations beyond metric-specific thresholds (e.g. ±5% stablecoin supply,
±10% RWA TVL, ±50% DEX volume) — expanded alongside the new metrics.

## Data sources (all free, no API keys)

- Solana public RPC (`api.mainnet-beta.solana.com`): getEpochInfo, getRecentPerformanceSamples, getVoteAccounts, getTokenSupply
- DeFiLlama public API: DeFi TVL (`api.llama.fi`), DEX volume / fees / revenue overviews (`overview/dexs`, `overview/fees`, `overview/fees?dataType=dailyRevenue`)
- DeFiLlama stablecoins API: Solana stablecoin circulating supply (`stablecoins.llama.fi`)
- DeFiLlama protocols + per-protocol chainTvls: tokenized-asset TVL attributed to Solana specifically (not multi-chain totals)
- CoinGecko public API: SOL price/market cap

Every collected value passes a loud-failure gate: a missing or zero core
metric fails the run with a named error instead of silently publishing nulls.

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
