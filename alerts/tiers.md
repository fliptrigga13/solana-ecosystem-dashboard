# Alert subscription tiers

Prices below are placeholders — **TODO (owner): set real prices** before
launching. Everything else (limits, cooldowns, channels) is implemented in
`alerts/check.py`.

## Free — $TODO/mo (currently $0)

- 1 delivery channel (telegram, email, or webhook)
- WARNING and CRITICAL only (no INFO, e.g. no epoch-ending notices)
- Hourly digest cadence (check.py runs hourly via cron; 7-day cooldown dedupe
  means a repeat of the same rule+severity is not resent for 7 days)
- Subscriber picks which rules to follow, or all (`"*"`)

## Pro — $TODO/mo

- Everything in Free, plus:
- All severities including INFO
- Instant delivery on every check run
- All three channels: telegram + email + webhook (one destination each)
- 1-hour cooldown dedupe (repeats of the same rule+severity resend after 1h)

## Team — $TODO/mo

- Everything in Pro, plus:
- Multiple destinations per channel (e.g. several chat IDs / emails)
- Custom rules (owner-defined rule_ids beyond the built-in set)
- 15-minute cooldown dedupe

## TODO (owner)

- [ ] Set Free/Pro/Team prices above
- [ ] Provision Telegram bot token → `TELEGRAM_BOT_TOKEN` env var
- [ ] Provision SMTP credentials → `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`,
      `SMTP_PASS`, `SMTP_FROM` env vars
- [ ] Decide hosting + cron schedule for `alerts/check.py` (recommended: hourly)
- [ ] Decide payment provider + signup flow for Pro/Team (tiers are enforced
      by the `tier` field in `subscribers.json`; there is no billing code yet)
- [ ] Free-tier digest batching: currently each event is delivered
      individually; a true combined hourly digest email/message is future work
