#!/usr/bin/env python3
"""Solana ecosystem data collector — free public sources only, no API keys.

Collects network, validator, and economic metrics. Writes structured JSON
for the dashboard and Markdown report generators.
"""
import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

RPC_ENDPOINTS = [
    "https://api.mainnet-beta.solana.com",
    "https://solana-rpc.publicnode.com",  # fallback if primary rate-limits
]
DEFILLAMA = "https://api.llama.fi"
DEFILLAMA_STABLES = "https://stablecoins.llama.fi"
COINGECKO = "https://api.coingecko.com/api/v3"
# Keyless news feeds for the ecosystem & community news section.
NEWS_FEEDS = [
    {"name": "Solana Forums", "url": "https://forum.solana.com/latest.rss",
     "filter": None},  # official community forum — take latest topics
    {"name": "Decrypt", "url": "https://decrypt.co/feed",
     "filter": "solana"},  # industry feed, Solana mentions only
]
NEWS_MAX_ITEMS = 8
# Top RWA protocols on Solana whose per-chain TVL we track (verified slugs).
RWA_SLUGS = ["blackrock-buidl", "ondo-yield-assets", "xstocks",
             "hastra", "ondo-global-markets", "invesco-ustb"]
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
    # Estimated daily transaction count from the same performance samples
    # (used to derive avg fee per transaction in collect_all).
    tot_txn = sum(s.get("numTransactions") or 0 for s in perf)
    tot_secs = sum(s.get("samplePeriodSecs") or 0 for s in perf)
    return {
        "slot": epoch.get("absoluteSlot"),
        "block_height": epoch.get("blockHeight"),
        "epoch": epoch.get("epoch"),
        "epoch_progress_pct": round(100 * epoch.get("slotIndex", 0) /
                                    max(epoch.get("slotsInEpoch", 1), 1), 2),
        "avg_tps_5h": round(sum(tps_samples) / len(tps_samples), 0) if tps_samples else None,
        "max_tps_5h": round(max(tps_samples), 0) if tps_samples else None,
        "est_daily_txns": round(tot_txn / tot_secs * 86400) if tot_secs else None,
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


def collect_defi() -> dict:
    """DeFi depth metrics from the same zero-key DeFiLlama family of APIs."""
    out = {}
    # Stablecoin circulating supply on Solana (last point of the chain chart).
    dl = _get_json(DEFILLAMA_STABLES + "/stablecoincharts/Solana")
    peg = (dl[-1].get("totalCirculating") or {}).get("peggedUSD")
    if not isinstance(peg, (int, float)) or peg <= 0:
        raise RuntimeError(f"stablecoin supply missing/invalid: {peg!r}")
    out["stablecoin_supply_billion"] = round(peg / 1e9, 3)

    # DEX volume + fees/revenue overviews share one response shape.
    dex = _get_json(DEFILLAMA + "/overview/dexs/Solana")
    if not isinstance(dex.get("total24h"), (int, float)) or dex["total24h"] <= 0:
        raise RuntimeError(f"DEX volume missing/invalid: {dex.get('total24h')!r}")
    out["dex_volume_24h_billion"] = round(dex["total24h"] / 1e9, 3)
    out["dex_volume_change_24h_pct"] = round(dex.get("change_1d") or 0, 1)

    fees = _get_json(DEFILLAMA + "/overview/fees/Solana")
    rev = _get_json(DEFILLAMA +
                    "/overview/fees/Solana?dataType=dailyRevenue")
    for key, payload in (("fees_24h_million", fees), ("rev_24h_million", rev)):
        v = payload.get("total24h")
        if not isinstance(v, (int, float)) or v <= 0:
            raise RuntimeError(f"{key} missing/invalid: {v!r}")
        out[key] = round(v / 1e6, 2)
    return out


def collect_rwa() -> dict:
    """Tokenized real-world assets deployed on Solana.

    Uses each protocol's per-chain TVL (chainTvls.Solana), NOT the
    protocol-total figure — several of these are multi-chain and the total
    would overcount by ~6x.
    """
    protocols = {p.get("slug"): p for p in _get_json(DEFILLAMA + "/protocols")}
    breakdown, total = {}, 0.0
    for slug in RWA_SLUGS:
        p = protocols.get(slug)
        if not p:
            continue  # slug renamed upstream; skip rather than fail the run
        detail = _get_json(f"{DEFILLAMA}/protocol/{slug}")
        sol_series = ((detail.get("chainTvls") or {}).get("Solana") or {}).get("tvl") or []
        if not sol_series:
            raise RuntimeError(f"RWA {slug}: no Solana TVL series")
        val = sol_series[-1].get("totalLiquidityUSD", 0) / 1e9
        breakdown[p.get("name", slug)] = round(val, 3)
        total += val
    if total <= 0:
        raise RuntimeError("RWA sum is zero/empty — source likely broken")
    return {"tokenized_assets_billion": round(total, 3),
            "rwa_top": dict(sorted(breakdown.items(),
                                   key=lambda kv: -kv[1])[:4])}


def fetch_news() -> dict:
    """Ecosystem & community news from keyless RSS feeds (stdlib parser only).

    Merges items newest-first, capped at NEWS_MAX_ITEMS. Loud gate: zero
    items across every feed fails the run — an empty news section must
    never ship silently.
    """
    items, errors = [], []
    for feed in NEWS_FEEDS:
        try:
            req = urllib.request.Request(
                feed["url"], headers={"User-Agent": UA["User-Agent"]})
            with urllib.request.urlopen(req, timeout=15) as r:
                root = ET.fromstring(r.read())
            for it in root.iter("item"):
                title = (it.findtext("title") or "").strip()
                link = (it.findtext("link") or "").strip()
                pub = (it.findtext("pubDate") or "").strip()
                desc = (it.findtext("description") or "").strip()
                if not title or not link:
                    continue
                needle = feed.get("filter")
                if needle and needle not in (title + " " + desc).lower():
                    continue
                date_iso = ""
                if pub:
                    try:
                        date_iso = parsedate_to_datetime(pub).date().isoformat()
                    except (TypeError, ValueError):
                        pass
                items.append({"source": feed["name"],
                              # neutralize angle brackets so titles can't inject markup
                              "title": title[:140].replace("<", "").replace(">", ""),
                              "link": link, "date": date_iso})
        except Exception as exc:
            errors.append(f"{feed['name']}: {exc}")
    items.sort(key=lambda x: x.get("date") or "", reverse=True)
    items = items[:NEWS_MAX_ITEMS]
    if not items:
        raise RuntimeError("news feeds returned zero items "
                           f"(feed errors: {errors or 'none'})")
    return {"items": items,
            "feeds_ok": len(NEWS_FEEDS) - len(errors),
            "errors": errors}


def collect_all() -> dict:
    snapshot = {"collected_at": datetime.now(timezone.utc).isoformat(),
                "network": collect_network(), "economic": collect_economic(),
                "defi": collect_defi(), "rwa": collect_rwa(),
                "news": fetch_news()}
    # Derived metric: average fee per transaction (24h fees ÷ est. daily txns).
    txns = snapshot["network"].get("est_daily_txns")
    fees_m = snapshot["defi"].get("fees_24h_million")
    if isinstance(txns, (int, float)) and txns > 0 and fees_m:
        snapshot["defi"]["avg_fee_per_txn_usd"] = round(fees_m * 1e6 / txns, 4)
    assert_snapshot_complete(snapshot)
    return snapshot


UPCOMING_UPDATES = [
    # Facts verified 2026-08-25 against solana.com/upgrades pages.
    {"name": "Alpenglow",
     "detail": "Votor consensus + Rotor propagation; finality ~12.8s → ~150ms",
     "status": "Mainnet target Q3 2026 · BLS/VAT prereq live since Jul 22, 2026",
     "url": "https://solana.com/upgrades/alpenglow"},
    {"name": "SIMD-0525 · Reduced Slot Times",
     "detail": "Slot time 400ms → 200ms in four feature-gated steps",
     "status": "Step 1 activated on testnet Aug 5, 2026",
     "url": "https://solana.com/upgrades/reduced-slot-times"},
]


def assert_snapshot_complete(snapshot: dict) -> None:
    """Loud-failure gate: refuse to publish a partial snapshot.

    Every run must produce real values for the core metrics; a missing one
    means a source broke and the pipeline should fail loudly, not silently
    write nulls (which is how the Aug 24 TVL bug hid for a full day).
    """
    n, e = snapshot["network"], snapshot["economic"]
    d, r = snapshot.get("defi", {}), snapshot.get("rwa", {})
    required = {
        "network.slot": n.get("slot"),
        "network.block_height": n.get("block_height"),
        "network.epoch": n.get("epoch"),
        "network.avg_tps_5h": n.get("avg_tps_5h"),
        "network.validators_active": n.get("validators_active"),
        "network.total_stake_sol_million": n.get("total_stake_sol_million"),
        "economic.defi_tvl_billion": e.get("defi_tvl_billion"),
        "economic.sol_price_usd": e.get("sol_price_usd"),
        "defi.stablecoin_supply_billion": d.get("stablecoin_supply_billion"),
        "defi.dex_volume_24h_billion": d.get("dex_volume_24h_billion"),
        "defi.fees_24h_million": d.get("fees_24h_million"),
        "defi.rev_24h_million": d.get("rev_24h_million"),
        "rwa.tokenized_assets_billion": r.get("tokenized_assets_billion"),
    }
    missing = [k for k, v in required.items()
               if not isinstance(v, (int, float)) or isinstance(v, bool)
               or v <= 0]
    if missing:
        raise RuntimeError(f"incomplete snapshot — missing/invalid: {missing}")


if __name__ == "__main__":
    snap = collect_all()
    print(json.dumps(snap, indent=2)[:1500])
