#!/usr/bin/env python3
"""Alert check CLI for the Solana Ecosystem Dashboard.

Pipeline: load data.json + data-history.jsonl -> anomaly.detect_anomalies ->
rules.evaluate -> filter per subscriber (tier / rules / min_severity) ->
cooldown dedupe via alerts/sent.json -> deliver.

Exit 0 on operational success even if individual deliveries fail (failures
are counted and reported). Non-zero only on fatal errors (missing data,
unreadable config).

Recommended: run hourly via cron.

Zero dependencies.
"""
import json
import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)   # anomaly.py
sys.path.insert(0, HERE)   # rules.py, deliver.py

import anomaly  # noqa: E402
import deliver  # noqa: E402
import rules    # noqa: E402

SEVERITY_RANK = {"INFO": 0, "WARNING": 1, "CRITICAL": 2}

# Per-tier resend cooldowns (seconds): don't resend the same
# tier+rule_id+severity while the last send is younger than this.
COOLDOWNS = {
    "free": 7 * 24 * 3600,  # 7 days
    "pro": 3600,            # 1 hour
    "team": 900,            # 15 minutes
}

SUBSCRIBERS_FILE = os.path.join(HERE, "subscribers.json")
SENT_FILE = os.path.join(HERE, "sent.json")


def load_json(path: str, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def atomic_write_json(path: str, obj) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)
    os.replace(tmp, path)


def subscriber_wants(sub: dict, event: dict) -> bool:
    """Tier/rules/min_severity filter for one subscriber + event."""
    wanted = sub.get("rules") or []
    if "*" not in wanted and event.get("rule_id") not in wanted:
        return False
    min_sev = (sub.get("min_severity") or "WARNING").upper()
    ev_sev = (event.get("severity") or "INFO").upper()
    return SEVERITY_RANK.get(ev_sev, 0) >= SEVERITY_RANK.get(min_sev, 1)


def dedupe_key(tier: str, event: dict) -> str:
    return f"{tier}:{event.get('rule_id')}:{event.get('severity')}"


def _parse_ts(ts: str):
    try:
        return datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        return None


def should_send(sent: dict, tier: str, event: dict, now: datetime) -> bool:
    """True unless the same tier+rule+severity was sent within the cooldown."""
    last = _parse_ts(sent.get(dedupe_key(tier, event)))
    if last is None:
        return True
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    cooldown = COOLDOWNS.get(tier, COOLDOWNS["free"])
    return (now - last).total_seconds() >= cooldown


def main() -> int:
    os.chdir(ROOT)  # anomaly.py resolves data-history.jsonl relative to cwd
    data_path = os.path.join(ROOT, "data.json")
    snapshot = load_json(data_path, None)
    if not isinstance(snapshot, dict):
        print(f"alerts: FATAL: cannot read {data_path}", file=sys.stderr)
        return 1

    history = anomaly.load_history()
    anomalies = anomaly.detect_anomalies(snapshot, history)
    events = rules.evaluate(snapshot, history, anomalies)

    config = load_json(SUBSCRIBERS_FILE, {})
    subscribers = config.get("subscribers", []) if isinstance(config, dict) else []
    sent = load_json(SENT_FILE, {})
    if not isinstance(sent, dict):
        sent = {}

    now = datetime.now(timezone.utc)
    delivered = failed = skipped_filter = skipped_cooldown = skipped_disabled = 0

    for sub in subscribers:
        # Safety default: a subscriber only receives alerts when explicitly
        # enabled. Example/placeholder entries ship with enabled=false so a
        # fresh checkout can never spam placeholder destinations.
        if not sub.get("enabled"):
            skipped_disabled += 1
            continue
        tier = sub.get("tier", "free")
        channel = sub.get("channel")
        destination = sub.get("destination")
        if not channel or not destination:
            continue
        for event in events:
            if not subscriber_wants(sub, event):
                skipped_filter += 1
                continue
            if not should_send(sent, tier, event, now):
                skipped_cooldown += 1
                continue
            ok = deliver.send(channel, destination, event)
            if ok:
                delivered += 1
                sent[dedupe_key(tier, event)] = now.isoformat()
            else:
                failed += 1

    atomic_write_json(SENT_FILE, sent)
    print(
        f"alerts: {len(events)} events, {len(subscribers)} subscribers, "
        f"{delivered} delivered, {failed} failed, "
        f"{skipped_filter} filtered, {skipped_cooldown} cooldown-skipped, "
        f"{skipped_disabled} disabled-skipped"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
