#!/usr/bin/env python3
"""Negative tests: every core metric must fail LOUD, never publish silently."""
import copy
import sys
import collector


def expect_fail(fn, label):
    try:
        fn()
    except RuntimeError as exc:
        print(f"PASS {label}: {type(exc).__name__}: {str(exc)[:80]}")
        return True
    print(f"FAIL {label}: no RuntimeError raised")
    return False


# Synthetic complete snapshot (no network calls needed for gate tests).
base = {
    "collected_at": "test",
    "network": {"slot": 1, "block_height": 2, "epoch": 3,
                "avg_tps_5h": 4000, "validators_active": 687,
                "total_stake_sol_million": 435},
    "economic": {"defi_tvl_billion": 5.6, "sol_price_usd": 97.7},
    "defi": {"stablecoin_supply_billion": 16.3,
             "dex_volume_24h_billion": 2.9,
             "fees_24h_million": 14.4, "rev_24h_million": 5.7},
    "rwa": {"tokenized_assets_billion": 1.6},
    "news": {"items": [{"source": "t", "title": "x", "link": "https://a.b",
                        "date": "2026-08-25"}], "feeds_ok": 1, "errors": []},
}

gated_keys = [
    "network.slot", "network.block_height", "network.epoch",
    "network.avg_tps_5h", "network.validators_active",
    "network.total_stake_sol_million",
    "economic.defi_tvl_billion", "economic.sol_price_usd",
    "defi.stablecoin_supply_billion", "defi.dex_volume_24h_billion",
    "defi.fees_24h_million", "defi.rev_24h_million",
    "rwa.tokenized_assets_billion",
]

results = []
for key_path in gated_keys:
    snap = copy.deepcopy(base)
    section, key = key_path.split(".")
    snap[section][key] = None
    results.append(expect_fail(
        lambda s=snap: collector.assert_snapshot_complete(s),
        f"gate:{key_path}"))

# Real-path negative: unreachable feed URL -> zero items -> loud failure.
saved_feeds = collector.NEWS_FEEDS
collector.NEWS_FEEDS = [{"name": "dead", "url": "http://127.0.0.1:9/dead.xml",
                         "filter": None}]
try:
    results.append(expect_fail(collector.fetch_news, "news:zero-items"))
finally:
    collector.NEWS_FEEDS = saved_feeds

passed = sum(results)
print(f"\n{passed}/{len(results)} negative tests passed")
sys.exit(0 if passed == len(results) else 1)
