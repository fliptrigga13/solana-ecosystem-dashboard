"""Focused tests for the finality metric (collector.collect_finality).

Uses mocks — no network. Proves the fail-closed contract: bad RPC data
raises RuntimeError loudly instead of publishing a plausible-looking
fabricated finality number.
"""
import os
import sys
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import collector

PASS, FAIL = "PASS", "FAIL"
results = []


def check(name, fn):
    try:
        fn()
        results.append((PASS, name))
    except Exception as e:  # noqa: BLE001
        results.append((FAIL, f"{name}: {type(e).__name__}: {e}"))


def good_samples(n=30, slot_s=0.4):
    # numSlots=2500 over 1000s => 0.4s/slot, mirroring pre-Alpenglow cadence.
    return [{"numSlots": 2500, "numTransactions": 10_000_000,
             "samplePeriodSecs": 2500 * slot_s} for _ in range(n)]


def run_finality(samples, tip, fin):
    with mock.patch.object(collector, "rpc") as m:
        def side(method, params=None):
            if method == "getRecentPerformanceSamples":
                return samples
            if method == "getSlot":
                if params and params[0].get("commitment") == "processed":
                    return tip
                return fin
            raise AssertionError(f"unexpected RPC {method}")
        m.side_effect = side
        return collector.collect_finality()


# ---------------------------------------------------------------- happy path
def t_happy_path_pre_alpenglow():
    r = run_finality(good_samples(), tip=300_000_032, fin=300_000_000)
    assert r["finality_lag_slots"] == 32, r
    assert r["finality_estimate_s"] == 12.8, r
    assert r["avg_slot_time_s"] == 0.4, r
    assert r["finalized_slot"] == 300_000_000 and r["tip_slot"] == 300_000_032
    assert "processed-tip slot" in r["method"], r
check("happy path: 32-slot lag x 0.4s cadence -> 12.8s finality",
      t_happy_path_pre_alpenglow)


def t_happy_path_alpenglow_regime():
    # Post-Alpenglow: tiny lag, fast slots — same code path, small number.
    r = run_finality(good_samples(slot_s=0.15), tip=400_000_002, fin=400_000_000)
    assert r["finality_lag_slots"] == 2, r
    assert r["finality_estimate_s"] == 0.3, r
check("alpenglow regime: 2-slot lag x 0.15s cadence -> 0.3s (no code change)",
      t_happy_path_alpenglow_regime)


# ------------------------------------------------------- fail-closed cases
def t_too_few_samples_raises():
    try:
        run_finality(good_samples(n=4), tip=10, fin=5)
    except RuntimeError as e:
        assert "slot-cadence" in str(e), e
        return
    raise AssertionError("no RuntimeError")
check("fail-closed: <5 usable cadence samples -> RuntimeError",
      t_too_few_samples_raises)


def t_zero_samples_raises():
    try:
        run_finality([], tip=10, fin=5)
    except RuntimeError as e:
        assert "slot-cadence" in str(e), e
        return
    raise AssertionError("no RuntimeError")
check("fail-closed: empty performance samples -> RuntimeError",
      t_zero_samples_raises)


def t_implausible_slot_time_raises():
    try:
        run_finality(good_samples(slot_s=50.0), tip=10, fin=5)
    except RuntimeError as e:
        assert "implausible avg slot time" in str(e), e
        return
    raise AssertionError("no RuntimeError")
check("fail-closed: 50s/slot cadence -> RuntimeError",
      t_implausible_slot_time_raises)


def t_negative_lag_raises():
    try:
        run_finality(good_samples(), tip=100, fin=200)
    except RuntimeError as e:
        assert "ahead of processed tip" in str(e), e
        return
    raise AssertionError("no RuntimeError")
check("fail-closed: finalized ahead of tip -> RuntimeError",
      t_negative_lag_raises)


def t_absurd_lag_raises():
    try:
        run_finality(good_samples(), tip=1_000_000, fin=900_000)
    except RuntimeError as e:
        assert "implausible lag" in str(e), e
        return
    raise AssertionError("no RuntimeError")
check("fail-closed: 100k-slot lag (stale node) -> RuntimeError",
      t_absurd_lag_raises)


def t_bad_slot_type_raises():
    try:
        run_finality(good_samples(), tip="not-a-slot", fin=5)
    except RuntimeError as e:
        assert "bad processed tip slot" in str(e), e
        return
    raise AssertionError("no RuntimeError")
check("fail-closed: non-int tip slot -> RuntimeError",
      t_bad_slot_type_raises)


def t_none_finalized_raises():
    try:
        run_finality(good_samples(), tip=10, fin=None)
    except RuntimeError as e:
        assert "bad finalized slot" in str(e), e
        return
    raise AssertionError("no RuntimeError")
check("fail-closed: None finalized slot -> RuntimeError",
      t_none_finalized_raises)


# ------------------------------------------------- publish-gate integration
def complete_snapshot(finality):
    return {
        "collected_at": "test",
        "network": {"slot": 1, "block_height": 2, "epoch": 3,
                    "avg_tps_5h": 4000, "validators_active": 687,
                    "total_stake_sol_million": 435},
        "economic": {"defi_tvl_billion": 5.6, "sol_price_usd": 97.7},
        "defi": {"stablecoin_supply_billion": 16.3,
                 "dex_volume_24h_billion": 2.9,
                 "fees_24h_million": 14.4, "rev_24h_million": 5.7},
        "rwa": {"tokenized_assets_billion": 1.6},
        "finality": finality,
        "news": {"items": [{"source": "t", "title": "x", "link": "https://a.b",
                            "date": "2026-08-25"}], "feeds_ok": 1, "errors": []},
    }


def t_gate_accepts_valid_finality():
    collector.assert_snapshot_complete(
        complete_snapshot({"finality_estimate_s": 12.8}))
check("gate: valid finality passes assert_snapshot_complete",
      t_gate_accepts_valid_finality)


def _expect_gate_fail(finality, label):
    try:
        collector.assert_snapshot_complete(complete_snapshot(finality))
    except RuntimeError:
        return
    raise AssertionError(f"gate accepted {label}")


def t_gate_rejects_missing_finality():
    _expect_gate_fail({}, "missing")
check("gate: missing finality section -> RuntimeError",
      t_gate_rejects_missing_finality)


def t_gate_rejects_zero_finality():
    _expect_gate_fail({"finality_estimate_s": 0.0}, "zero")
check("gate: 0.0s finality (provider quirk) -> RuntimeError, never ships",
      t_gate_rejects_zero_finality)


def t_gate_rejects_negative_finality():
    _expect_gate_fail({"finality_estimate_s": -3.0}, "negative")
check("gate: negative finality -> RuntimeError",
      t_gate_rejects_negative_finality)


print()
for status, name in results:
    print(f"{status} {name}")
passed = sum(1 for s, _ in results if s == PASS)
print(f"\n{passed}/{len(results)} finality tests passed")
sys.exit(0 if passed == len(results) else 1)
