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
| `dashboard.html` | Interactive dark-theme HTML | Human dashboard |
| `report.md` | Markdown | Human-readable summary |
| `data.json` | JSON | Machine-readable snapshot |
| `data-history.jsonl` | JSONL | Historical snapshots for anomaly baseline |

## Metrics covered

**Network:** avg/peak TPS (5h window), slot, block height, epoch progress,
active validators, delinquent validators, total stake, top-10 validators by
stake with commission rates.

**Economic:** SOL price + 24h change, market cap, DeFi TVL.

**Anomaly detection:** TPS drops/spikes (>30%), delinquent validator surges
(>100%), SOL price moves (>10%), TVL changes (>15%) — with severity levels.

## Data sources (all free, no API keys)

- Solana public RPC: `getEpochInfo`, `getRecentPerformanceSamples`,
  `getVoteAccounts`, `getTokenSupply`
- DeFiLlama public API: DeFi TVL
- CoinGecko public API: SOL price / market cap

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
