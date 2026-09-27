# Solana Foundation Grant Application — DRAFT
**Project:** Solana Ecosystem Dashboard (https://fliptrigga13.github.io/solana-ecosystem-dashboard/)
**Status:** Draft — TODOs marked for owner before submission
**Date:** 2026-09-27

---

## 1. Project summary

The Solana Ecosystem Dashboard is a public, auto-updating, zero-dependency dashboard
tracking the health of the Solana network: throughput (TPS), SOL price, DeFi TVL,
stablecoin supply, DEX volume, fees/REV, validator set (active/delinquent, top by stake),
tokenized real-world assets (RWA), upcoming network upgrades, and ecosystem news.

It refreshes hourly via GitHub Actions, publishes a machine-readable snapshot
(`data.json`) plus full history (`data-history.jsonl`), and renders a single-file
interactive dashboard. The entire pipeline is Python stdlib only — no build step,
no vendor lock-in, fully auditable.

## 2. Public-goods case

- **Open data:** every snapshot is committed to the public repo; anyone can audit,
  fork, or build on the history. No paywall on the public dashboard.
- **Network health transparency:** delinquent-validator tracking, TPS anomaly
  detection, and fee/REV trends serve validators, researchers, and the community.
- **Composability:** the snapshot schema is stable and documented; the planned
  public API (free tier) will let other ecosystem projects consume the data.

## 3. What the grant funds (milestones)

| # | Milestone | Deliverable | TODO budget |
|---|-----------|-------------|-------------|
| 1 | Reliability hardening | Step 10 failure-mode repairs merged to main (loud source-outage failure, publication state machine, refresh locking, atomic writes, history dedup) | TODO |
| 2 | Public data API (free tier) | Documented read API over snapshots/history, rate-limited free keys | TODO |
| 3 | Alerting for the commons | Free-tier anomaly alerts (delinquency spikes, TPS drops) via Telegram/email | TODO |
| 4 | Coverage expansion | Additional RWA issuers, per-epoch validator performance, fee-market breakdowns | TODO |

## 4. Team

TODO: team description. Solo builder with shipped, working, public infrastructure
(commit history at https://github.com/fliptrigga13/solana-ecosystem-dashboard).

## 5. Budget

TODO: total ask + breakdown per milestone. Keep milestones independently shippable
so partial funding still delivers value.

## 6. Sustainability

Paid tiers (pro API keys, instant alerts, sponsored placements — all disclosed)
fund ongoing operation. Grant funding accelerates the public-goods layers
(free API tier, free alerts, coverage expansion); the public dashboard itself
remains free forever.

## 7. Links

- Live dashboard: https://fliptrigga13.github.io/solana-ecosystem-dashboard/
- Repo: https://github.com/fliptrigga13/solana-ecosystem-dashboard
- Contact: TODO@yourdomain.com
