#!/usr/bin/env python3
"""Alert rule evaluation for the Solana Ecosystem Dashboard.

Maps anomaly-detector output (plus one direct snapshot check) onto named,
subscriber-facing alert rules. Thresholds live in exactly one place:
anomaly.THRESHOLDS — this module reuses them and never duplicates them.

Zero dependencies.
"""
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import anomaly  # noqa: E402

# rule_id -> anomaly metric + which deviation directions fire the rule.
RULE_DEFS = {
    "tps_drop":         {"metric": "avg_tps_5h",               "directions": ("drop",)},
    "delinquent_spike": {"metric": "validators_delinquent",    "directions": ("spike",)},
    "price_move":       {"metric": "sol_price_usd",            "directions": ("drop", "spike")},
    "tvl_move":         {"metric": "defi_tvl_billion",         "directions": ("drop", "spike")},
    "stablecoin_move":  {"metric": "stablecoin_supply_billion","directions": ("drop", "spike")},
    "dex_volume_spike": {"metric": "dex_volume_24h_billion",   "directions": ("spike",)},
    "fee_spike":        {"metric": "fees_24h_million",         "directions": ("spike",)},
    "rwa_move":         {"metric": "tokenized_assets_billion", "directions": ("drop", "spike")},
    # Spike-only by design: a finality *drop* is the Alpenglow upgrade
    # working (12.8s -> ~0.15s), not something to alert on. A spike means
    # the chain is failing to finalize — page-worthy.
    "finality_spike":   {"metric": "finality_estimate_s",    "directions": ("spike",)},
}

TITLES = {
    "tps_drop": "TPS drop detected",
    "delinquent_spike": "Delinquent validator spike",
    "price_move": "SOL price move",
    "tvl_move": "DeFi TVL move",
    "stablecoin_move": "Stablecoin supply move",
    "dex_volume_spike": "DEX volume spike",
    "fee_spike": "Fee spike",
    "rwa_move": "Tokenized-assets (RWA) move",
    "finality_spike": "Finality spike detected",
    "epoch_ending": "Epoch ending soon",
}

EPOCH_ENDING_PCT = 95.0  # epoch_progress_pct above this fires epoch_ending (INFO)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _event_from_anomaly(rule_id: str, a: dict) -> dict:
    direction = a["direction"]
    arrow = "down" if direction == "drop" else "up"
    return {
        "rule_id": rule_id,
        "severity": a["severity"],
        "title": TITLES[rule_id],
        "detail": (
            f"{a['metric']} moved {arrow} {abs(a['deviation_pct'])}% "
            f"(current {a['current']} vs baseline {a['baseline']})"
        ),
        "metric": a["metric"],
        "current": a["current"],
        "baseline": a["baseline"],
        "deviation_pct": a["deviation_pct"],
        "ts": _now_iso(),
    }


def evaluate(snapshot: dict, history: list, anomalies: list) -> list:
    """Evaluate alert rules.

    Args:
        snapshot: current data.json snapshot.
        history: list of past snapshots (unused directly; kept for signature
            symmetry — baselines come from the anomaly report).
        anomalies: output of anomaly.detect_anomalies(snapshot, history).

    Returns:
        List of alert event dicts.
    """
    events = []
    for a in anomalies or []:
        if a.get("metric") == "*" or "metric" not in a:
            continue  # e.g. "no history yet" note entry
        for rule_id, spec in RULE_DEFS.items():
            if spec["metric"] == a["metric"] and a.get("direction") in spec["directions"]:
                events.append(_event_from_anomaly(rule_id, a))

    # epoch_ending is a direct snapshot check, not an anomaly: INFO only.
    pct = (snapshot.get("network") or {}).get("epoch_progress_pct")
    if isinstance(pct, (int, float)) and pct > EPOCH_ENDING_PCT:
        events.append({
            "rule_id": "epoch_ending",
            "severity": "INFO",
            "title": TITLES["epoch_ending"],
            "detail": f"epoch { (snapshot.get('network') or {}).get('epoch') } "
                      f"is {round(pct, 1)}% complete",
            "metric": "epoch_progress_pct",
            "current": round(pct, 2),
            "baseline": None,
            "deviation_pct": None,
            "ts": _now_iso(),
        })
    return events


def rule_ids() -> list:
    """All known rule ids, including the non-anomaly epoch_ending rule."""
    return list(RULE_DEFS) + ["epoch_ending"]
