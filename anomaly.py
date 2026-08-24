#!/usr/bin/env python3
"""Anomaly detection for Solana ecosystem metrics.

Compares the current snapshot against historical snapshots (data-history.jsonl)
and flags significant deviations. Appends each snapshot to history for future
comparisons. Zero dependencies.
"""
import json
import os
from datetime import datetime, timezone

HISTORY_FILE = "data-history.jsonl"
# deviation thresholds (fraction of baseline)
THRESHOLDS = {
    "avg_tps_5h": 0.30,          # 30% TPS drop/spike
    "validators_delinquent": 1.0, # 100% increase in delinquent validators
    "sol_price_usd": 0.10,        # 10% SOL price move
    "defi_tvl_billion": 0.15,     # 15% TVL change
}


def load_history() -> list:
    if not os.path.exists(HISTORY_FILE):
        return []
    out = []
    with open(HISTORY_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return out


def append_history(snap: dict) -> None:
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(snap, ensure_ascii=False) + "\n")


def _flat_metrics(snap: dict) -> dict:
    """Flatten nested snapshot into comparable scalar metrics."""
    n, e = snap.get("network", {}), snap.get("economic", {})
    return {
        "avg_tps_5h": n.get("avg_tps_5h"),
        "validators_delinquent": n.get("validators_delinquent"),
        "sol_price_usd": e.get("sol_price_usd"),
        "defi_tvl_billion": e.get("defi_tvl_billion"),
    }


def detect_anomalies(snapshot: dict, history: list) -> list:
    """Return list of {metric, current, baseline, deviation_pct, severity}."""
    anomalies = []
    cur = _flat_metrics(snapshot)
    if not history:
        return [{"metric": "*", "note": "no history yet — baseline established"}]
    # baseline = mean of last N snapshots (excluding zero/None)
    window = history[-20:]
    for metric, threshold in THRESHOLDS.items():
        vals = [h_metric for snap_h in window
                for h_metric in [_flat_metrics(snap_h).get(metric)]
                if isinstance(h_metric, (int, float)) and h_metric > 0]
        cur_val = cur.get(metric)
        if not vals or not isinstance(cur_val, (int, float)) or cur_val <= 0:
            continue
        baseline = sum(vals) / len(vals)
        deviation = (cur_val - baseline) / baseline
        if abs(deviation) >= threshold:
            direction = "spike" if deviation > 0 else "drop"
            severity = "CRITICAL" if abs(deviation) >= threshold * 2 else "WARNING"
            anomalies.append({
                "metric": metric,
                "current": round(cur_val, 3),
                "baseline": round(baseline, 3),
                "deviation_pct": round(deviation * 100, 1),
                "direction": direction,
                "severity": severity,
            })
    return anomalies


def run(snapshot: dict) -> dict:
    """Append to history, then detect. Returns anomaly report."""
    history = load_history()
    # don't double-append identical timestamps within same run
    anomalies = detect_anomalies(snapshot, history)
    append_history(snapshot)
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "history_size": len(history),
        "anomalies_detected": len(anomalies),
        "anomalies": anomalies,
    }


if __name__ == "__main__":
    snap = json.load(open("data.json"))
    report = run(snap)
    print(json.dumps(report, indent=2))
