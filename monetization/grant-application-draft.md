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

Solo builder/operator. Shipped, working, public infrastructure with full
commit history at https://github.com/fliptrigga13/solana-ecosystem-dashboard:
hourly auto-updating pipeline (Python stdlib only), failure-mode hardening
(loud source-outage failure, publication state machine, refresh locking,
atomic writes), a keyed read API with tiered rate limits, and a tiered
anomaly-alert engine — all tested (API 25/25, alerts 27/27, repair probes
9/9) and documented in the public repo.

[OWNER: add name/handle + one line on background if desired — optional.]

## 5. Budget

**Proposed by Farrow 2026-09-27 — owner adjusts numbers or total before
submitting.** Anchored on the Foundation's ~$40k average public-good check
(Foundation CPO, Mar 2026). Milestones are independently shippable so partial
funding still delivers value.

| # | Milestone | Deliverable | Proposed budget |
|---|-----------|-------------|-----------------|
| 1 | Reliability hardening | Failure-mode repairs merged to main and verified in production (work complete; funds final integration + monitoring) | $6,000 |
| 2 | Public data API (free tier) | Hosted read API over snapshots/history, documented, rate-limited free keys, usage metering | $12,000 |
| 3 | Alerting for the commons | Hosted hourly alert engine; free-tier anomaly alerts (delinquency spikes, TPS drops) via Telegram/webhook | $10,000 |
| 4 | Coverage expansion | Additional RWA issuers, per-epoch validator performance, fee-market breakdowns | $12,000 |
| | **Total ask** | | **$40,000** |

[OWNER: confirm or edit the total and per-milestone split — this is the only
budget decision needed.]

## 6. Sustainability

Paid tiers (pro API keys, instant alerts, sponsored placements — all disclosed)
fund ongoing operation. Grant funding accelerates the public-goods layers
(free API tier, free alerts, coverage expansion); the public dashboard itself
remains free forever.

## 7. Links

- Live dashboard: https://fliptrigga13.github.io/solana-ecosystem-dashboard/
- Repo: https://github.com/fliptrigga13/solana-ecosystem-dashboard
- Contact: TODO@yourdomain.com
