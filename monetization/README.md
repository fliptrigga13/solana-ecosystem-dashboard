# Monetization — Solana Ecosystem Dashboard

Five revenue tracks, all built on branch `monetization`. Stdlib-only, same as the
rest of the repo. Nothing here touches the data pipeline's integrity: sponsored
content is display-only and always disclosed; paid tiers never degrade the free
public dashboard.

> **Base note:** this branch is based on `main` (e864997) and does **not** include
> the Step 10 failure-mode repairs (`step10-failure-mode-repairs`, unmerged).
> If those repairs merge to main, rebase this branch onto the new main.

## Wiring (how it all connects)

- **Alerts** run inside the normal refresh: `autoupdate.refresh()` calls
  `alerts/check.main()` after the dashboard is generated. Alert failures can
  never break a refresh (delivery failures are counted, exit 0; anything
  unexpected is caught and logged).
- **Safety default:** a subscriber only receives alerts with `"enabled": true`
  in `alerts/subscribers.json`. Example entries ship disabled, so a fresh
  checkout can never spam placeholder destinations.
- `alerts/sent.json` (cooldown state) is included in the hourly-watch autocommit
  file list so dedupe state persists across runs.
- **API** serves the repo's own data files by default (`DATA_DIR` defaults to
  the repo root; override with env). Localhost-only; put a TLS reverse proxy
  in front.
- **Sponsorships** render during `generate_dashboard.py`; `sponsors.json` is
  optional — missing file means no sponsored slots, page builds normally.

## 1. Validator sponsorships — `sponsors.json` + `generate_dashboard.py`

- Featured validator strip rendered above the organic "Top Validators by Stake"
  table; matching rows in the validator and RWA tables get a gold "Sponsored" badge.
- Rankings and data are never affected — placement is display-only.
- Enable a sponsor: set `enabled: true` on an entry in `sponsors.json`.
- An "Advertise on this dashboard" card with contact email renders on every build.
- **Owner TODO:** set `contact_email`, set
  `pricing.validator_featured_usd_per_month` / `project_featured_usd_per_month`.

## 2. Alert subscriptions — `alerts/`

- `alerts/rules.py`: 10 rules on top of `anomaly.py` (tps_drop, delinquent_spike,
  price_move, tvl_move, stablecoin_move, dex_volume_spike, fee_spike, rwa_move,
  finality_spike, epoch_ending). Thresholds reused from `anomaly.THRESHOLDS` — drift breaks tests.
  `finality_spike` is spike-only by design: a finality *drop* is the Alpenglow
  upgrade working (12.8s → ~0.15s), not a page-worthy event.
- `alerts/deliver.py`: Telegram / email / webhook backends. Never raise; failures
  return False and are logged.
- `alerts/check.py`: hourly CLI. Per-subscriber rule + severity filtering, per-tier
  cooldown dedupe via `alerts/sent.json` (free 7d / pro 1h / team 15m).
- `alerts/tiers.md`: Free / Pro / Team definitions.
- 42/42 tests pass (`python3 alerts/test_alerts.py`).
- **Owner TODO:** prices in `tiers.md`; `TELEGRAM_BOT_TOKEN`; `SMTP_*` env vars;
  cron schedule for `check.py`; real subscribers in `subscribers.json`;
  billing/signup flow (Stripe).

## 3. Data API — `api/`

- `api/server.py`: `GET /v1/health` (open), `/v1/snapshot`, `/v1/metrics?name=X`
  (free+), `/v1/history?limit=N`, `/v1/anomalies` (pro+). Localhost-only by design;
  run behind a TLS reverse proxy.
- `api/auth.py` + `api/mkkey.py`: API keys, SHA-256 hashes only in `keys.json`,
  plaintext shown once at issuance. Tiers: free 1k req/day, pro 10k req/day,
  enterprise unlimited.
- `api/limits.py`: rolling-24h sliding window, persisted to `usage.json`.
- 29/29 tests pass (`python3 api/test_api.py`). Full docs in `api/README.md`.
- **Owner TODO:** pro/enterprise prices; hosting + TLS; key distribution process;
  Stripe billing webhook for auto issue/revoke.

## 4. Sponsored project placements

Same system as (1) — `sponsors.json` `projects` list, "Sponsored" badges on RWA
table rows, same pricing/contact TODOs.

## 5. Grant — `monetization/grant-application-draft.md`

Solana Foundation application draft: public-goods framing, 4 independently
shippable milestones, sustainability via paid tiers with the public dashboard
free forever.
**Owner TODO:** budget per milestone, team description, contact email.

## Honest prerequisite

All five need traffic. Distribution (sharing, SEO, validator/community outreach)
is the business; this is the product. Consider the grant (5) and free alert/API
tiers as the distribution engine for the paid tracks (1–4).
