#!/usr/bin/env python3
"""Solana ecosystem data collector — free public sources only, no API keys.

Collects network, validator, and economic metrics. Writes structured JSON
for the dashboard and Markdown report generators.
"""
import json
import urllib.request
from datetime import datetime, timezone

RPC_ENDPOINTS = [
    "https://api.mainnet-beta.solana.com",
    "https://solana-rpc.publicnode.com",  # fallback if primary rate-limits
]
DEFILLAMA = "https://api.llama.fi"
COINGECKO = "https://api.coingecko.com/api/v3"
UA = {"User-Agent": "solana-dashboard/1.0", "Accept": "application/json"}


def _get_json(url: str, body: dict | None = None, timeout: int = 20):
    data = json.dumps(body).encode() if body is not None else None
    headers = dict(UA)
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def rpc(method: str, params: list | None = None) -> dict:
    last_err: Exception | None = None
    for base in RPC_ENDPOINTS:
        try:
            res = _get_json(base, {"jsonrpc": "2.0", "id": 1,
                                   "method": method, "params": params or []})
            if "error" in res:
                raise RuntimeError(f"RPC error {method}: {res['error']}")
            return res["result"]
        except Exception as exc:  # try next endpoint
            last_err = exc
    raise RuntimeError(f"all {len(RPC_ENDPOINTS)} RPC endpoints failed "
                       f"for {method}: {last_err}")


def collect_network() -> dict:
    epoch = rpc("getEpochInfo")
    perf = rpc("getRecentPerformanceSamples", [60])  # last ~60 x 5min samples
    tps_samples = []
    for s in perf:
        if s.get("numTransactions") and s.get("samplePeriodSecs"):
            tps_samples.append(s["numTransactions"] / s["samplePeriodSecs"])
    supply = rpc("getTokenSupply", ["So11111111111111111111111111111111111111112"])
    vote_accounts = rpc("getVoteAccounts")
    current = vote_accounts.get("current", [])
    delinquent = vote_accounts.get("delinquent", [])
    total_stake = sum(v.get("activatedStake", 0) for v in current) / 1e9  # lamports→SOL
    top_validators = sorted(current, key=lambda v: -v.get("activatedStake", 0))[:10]
    return {
        "slot": epoch.get("absoluteSlot"),
        "block_height": epoch.get("blockHeight"),
        "epoch": epoch.get("epoch"),
        "epoch_progress_pct": round(100 * epoch.get("slotIndex", 0) /
                                    max(epoch.get("slotsInEpoch", 1), 1), 2),
        "avg_tps_5h": round(sum(tps_samples) / len(tps_samples), 0) if tps_samples else None,
        "max_tps_5h": round(max(tps_samples), 0) if tps_samples else None,
        "validators_active": len(current),
        "validators_delinquent": len(delinquent),
        "total_stake_sol_million": round(total_stake / 1e6, 1),
        "top_validators": [
            {"name": (v.get("nodePubkey") or "")[:12] + "…",
             "stake_sol_million": round(v.get("activatedStake", 0) / 1e9 / 1e6, 1),
             "commission": v.get("commission")}
            for v in top_validators],
    }


def collect_economic() -> dict:
    out = {}
    try:
        # /v2/historicalChainTvl/<chain> — last point is current TVL.
        # NOTE: /protocols/solana 404s (endpoint doesn't exist); that was the
        # cause of the silent defi_tvl_billion=null on Aug 24.
        dl = _get_json(DEFILLAMA + "/v2/historicalChainTvl/Solana")
        out["defi_tvl_billion"] = round(dl[-1].get("tvl", 0) / 1e9, 3)
    except Exception as exc:
        raise RuntimeError(f"DeFiLlama TVL fetch failed: {exc}") from exc
    try:
        cg = _get_json(COINGECKO + "/simple/price?ids=solana&vs_currencies=usd"
                       "&include_24hr_change=true&include_market_cap=true")
        sol = cg.get("solana", {})
        out["sol_price_usd"] = sol.get("usd")
        out["sol_price_change_24h_pct"] = round(sol.get("usd_24h_change", 0), 2)
        out["sol_market_cap_billion"] = round((sol.get("usd_market_cap") or 0) / 1e9, 2)
    except Exception:
        pass
    return out


def collect_all() -> dict:
    snapshot = {"collected_at": datetime.now(timezone.utc).isoformat(),
                "network": collect_network(), "economic": collect_economic()}
    assert_snapshot_complete(snapshot)
    return snapshot


def assert_snapshot_complete(snapshot: dict) -> None:
    """Loud-failure gate: refuse to publish a partial snapshot.

    Every run must produce real values for the core metrics; a missing one
    means a source broke and the pipeline should fail loudly, not silently
    write nulls (which is how the Aug 24 TVL bug hid for a full day).
    """
    n, e = snapshot["network"], snapshot["economic"]
    required = {
        "network.slot": n.get("slot"),
        "network.block_height": n.get("block_height"),
        "network.epoch": n.get("epoch"),
        "network.avg_tps_5h": n.get("avg_tps_5h"),
        "network.validators_active": n.get("validators_active"),
        "network.total_stake_sol_million": n.get("total_stake_sol_million"),
        "economic.defi_tvl_billion": e.get("defi_tvl_billion"),
        "economic.sol_price_usd": e.get("sol_price_usd"),
    }
    missing = [k for k, v in required.items()
               if not isinstance(v, (int, float)) or isinstance(v, bool)
               or v <= 0]
    if missing:
        raise RuntimeError(f"incomplete snapshot — missing/invalid: {missing}")


if __name__ == "__main__":
    snap = collect_all()
    print(json.dumps(snap, indent=2)[:1500])
