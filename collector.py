#!/usr/bin/env python3
"""Solana ecosystem data collector — free public sources only, no API keys.

Collects network, validator, and economic metrics. Writes structured JSON
for the dashboard and Markdown report generators.
"""
import json
import urllib.request
from datetime import datetime, timezone

RPC = "https://api.mainnet-beta.solana.com"
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
    res = _get_json(RPC, {"jsonrpc": "2.0", "id": 1,
                          "method": method, "params": params or []})
    if "error" in res:
        raise RuntimeError(f"RPC error {method}: {res['error']}")
    return res["result"]


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
        dl = _get_json(DEFILLAMA + "/protocols/solana")
        out["defi_tvl_billion"] = round(dl.get("tvl", 0) / 1e9, 3)
    except Exception:
        out["defi_tvl_billion"] = None
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
    return snapshot


if __name__ == "__main__":
    snap = collect_all()
    print(json.dumps(snap, indent=2)[:1500])
