#!/usr/bin/env python3
"""Anomaly detection self-test: injected breach fires; normal values stay quiet."""
import anomaly

HIST = []
for i in range(6):
    HIST.append({
        "network": {"avg_tps_5h": 4000, "validators_delinquent": 8},
        "economic": {"sol_price_usd": 98.0, "defi_tvl_billion": 5.6},
        "defi": {"stablecoin_supply_billion": 16.3,
                 "dex_volume_24h_billion": 3.0,
                 "fees_24h_million": 15.0, "rev_24h_million": 6.0},
        "rwa": {"tokenized_assets_billion": 1.6},
    })

CUR_STABLE_DROP = {
    "network": {"avg_tps_5h": 4050, "validators_delinquent": 9},
    "economic": {"sol_price_usd": 98.4, "defi_tvl_billion": 5.65},
    "defi": {"stablecoin_supply_billion": 14.2,   # -12.9% vs baseline -> threshold 5%
             "dex_volume_24h_billion": 3.1,
             "fees_24h_million": 15.2, "rev_24h_million": 6.1},
    "rwa": {"tokenized_assets_billion": 1.62},
}

anoms = anomaly.detect_anomalies(CUR_STABLE_DROP, HIST)
fired = [a["metric"] for a in anoms if a.get("metric") != "*"]
print("fired:", fired)
assert fired == ["stablecoin_supply_billion"], f"expected only stablecoin to fire, got {fired}"
a = anoms[0]
print(f"PASS fire: {a['metric']} {a['direction']} {a['deviation_pct']}% "
      f"({a['severity']}, current {a['current']} vs baseline {a['baseline']})")

QUIET = {
    "network": {"avg_tps_5h": 4100, "validators_delinquent": 10},
    "economic": {"sol_price_usd": 99.0, "defi_tvl_billion": 5.7},
    "defi": {"stablecoin_supply_billion": 16.5,
             "dex_volume_24h_billion": 3.2,
             "fees_24h_million": 15.5, "rev_24h_million": 6.2},
    "rwa": {"tokenized_assets_billion": 1.65},
}
anoms_q = [a for a in anomaly.detect_anomalies(QUIET, HIST) if a.get("metric") != "*"]
print("quiet-run fired:", [a["metric"] for a in anoms_q])
assert not anoms_q
print("PASS quiet: no false positives on normal variation")
print("ANOMALY TESTS PASS")
