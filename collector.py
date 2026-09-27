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
DEFILLAMA_YIELDS = "https://yields.llama.fi"  # NOTE: /pools is ~12MB — too heavy for hourly; not used
COINGECKO = "https://api.coingecko.com/api/v3"
STAKEWIZ = "https://api.stakewiz.com"
JITO_TIP_FLOOR = "https://bundles.jito.wtf/api/v1/bundles/tip_floor"
GITHUB_API = "https://api.github.com"
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
    # --- Decentralization: Nakamoto coefficient + stake concentration ---
    # Sort by activated stake descending; Nakamoto = fewest validators whose
    # combined stake exceeds 1/3 of total (can halt/censor the chain).
    stakes = sorted((v.get("activatedStake", 0) for v in current), reverse=True)
    total_lamports = sum(stakes)
    running, nakamoto = 0, 0
    for s in stakes:
        running += s
        nakamoto += 1
        if running > total_lamports / 3:
            break
    top10_share = sum(stakes[:10]) / total_lamports * 100 if total_lamports else None
    top20_share = sum(stakes[:20]) / total_lamports * 100 if total_lamports else None
    # --- Native staking APY estimate ---
    # inflation_rate.total x (1 - stake-weighted commission). Cheap RPC call.
    native_apy = None
    try:
        infl = rpc("getInflationRate")
        infl_total = infl.get("total")
        if isinstance(infl_total, (int, float)) and total_lamports:
            w_comm = sum(v.get("activatedStake", 0) * (v.get("commission") or 0) / 100
                         for v in current) / total_lamports
            native_apy = round(infl_total * (1 - w_comm) * 100, 2)
    except Exception as exc:
        raise RuntimeError(f"RPC getInflationRate failed: {exc}") from exc
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
        "nakamoto_coefficient": nakamoto,
        "top10_stake_share_pct": round(top10_share, 1) if top10_share else None,
        "top20_stake_share_pct": round(top20_share, 1) if top20_share else None,
        "native_apy_estimate_pct": native_apy,
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
    except Exception as exc:
        # source_outage: fail loudly with source context. Never swallow a
        # market-data failure into silent nulls (the Aug 24 pattern).
        raise RuntimeError(f"CoinGecko price fetch failed: {exc}") from exc
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
    # partial_coverage: fail loudly on missing slugs. Silently skipping a
    # renamed/vanished slug publishes partial RWA coverage as complete.
    missing = [slug for slug in RWA_SLUGS if slug not in protocols]
    if missing:
        raise RuntimeError(f"RWA coverage incomplete — missing slugs: {missing}")
    breakdown, total = {}, 0.0
    for slug in RWA_SLUGS:
        p = protocols[slug]
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


def _client_family(v: dict) -> str:
    """Bucket a Stakewiz validator into a client family.

    Heuristic: Stakewiz's is_jito flag identifies the Jito-Solana client
    (an Agave fork — gossip alone can't separate it). Firedancer-family
    releases use 26.* / 0.* versioning; everything else is Agave-lineage.
    """
    if v.get("is_jito"):
        return "jito-solana"
    ver = v.get("version") or ""
    if ver.startswith("26.") or ver.startswith("0."):
        return "firedancer"
    return "agave"


def collect_validators() -> dict:
    """Validator economics + client diversity from Stakewiz (keyless).

    One request returns all validators: APY estimates, commission, version,
    is_jito flag, uptime. Stake-weighted aggregates.
    """
    try:
        vals = _get_json(STAKEWIZ + "/validators", timeout=30)
    except Exception as exc:
        raise RuntimeError(f"Stakewiz fetch failed: {exc}") from exc
    if not isinstance(vals, list) or not vals:
        raise RuntimeError("Stakewiz returned empty/invalid validator list")
    active = [v for v in vals if not v.get("delinquent")]
    if not active:
        raise RuntimeError("Stakewiz: zero active validators")
    total_stake = sum(v.get("activated_stake", 0) for v in active)
    if not total_stake:
        raise RuntimeError("Stakewiz: zero total active stake")
    w_apy = sum(v.get("activated_stake", 0) * (v.get("apy_estimate") or 0)
                for v in active) / total_stake
    # NOTE: Stakewiz reports commission in basis points (0–10000); /100 → pct.
    w_comm = sum(v.get("activated_stake", 0) * (v.get("commission") or 0)
                 for v in active) / total_stake / 100
    w_uptime = sum(v.get("activated_stake", 0) * (v.get("uptime") or 0)
                   for v in active) / total_stake
    share: dict[str, float] = {}
    for v in active:
        fam = _client_family(v)
        share[fam] = share.get(fam, 0) + v.get("activated_stake", 0)
    return {
        "validators_tracked": len(active),
        "avg_apy_pct": round(w_apy, 2),
        "avg_commission_pct": round(w_comm, 2),
        "avg_uptime_pct": round(w_uptime, 2),
        "client_share_pct": {k: round(s / total_stake * 100, 1)
                             for k, s in sorted(share.items(), key=lambda kv: -kv[1])},
        "jito_validators": sum(1 for v in active if v.get("is_jito")),
    }


def collect_dex_venues() -> dict:
    """Per-venue DEX volume on Solana (DeFiLlama overview, keyless).

    The ?chain=Solana response nests per-protocol breakdown24h under a
    lowercase "solana" key holding {version: volume_usd} — summed per venue.
    """
    try:
        dex = _get_json(DEFILLAMA + "/overview/dexs?chain=Solana", timeout=40)
    except Exception as exc:
        raise RuntimeError(f"DeFiLlama DEX venues fetch failed: {exc}") from exc
    protos = dex.get("protocols")
    if not isinstance(protos, list) or not protos:
        raise RuntimeError("DeFiLlama DEX venues: empty protocol list")
    rows = []
    for p in protos:
        bd = (p.get("breakdown24h") or {}).get("solana") or {}
        vol = sum(v for v in bd.values() if isinstance(v, (int, float)))
        if vol > 0:
            rows.append({"name": p.get("displayName") or p.get("name") or "?",
                         "volume_24h_million": round(vol / 1e6, 1)})
    if not rows:
        raise RuntimeError("DeFiLlama DEX venues: zero Solana venue volume")
    rows.sort(key=lambda r: -r["volume_24h_million"])
    return {"venues": rows[:6],
            "venues_tracked": len(rows)}


def collect_stablecoin_issuers() -> dict:
    """Per-issuer stablecoin supply on Solana (DeFiLlama stablecoins, keyless)."""
    try:
        st = _get_json(DEFILLAMA_STABLES + "/stablecoins?includePrices=true",
                       timeout=30)
    except Exception as exc:
        raise RuntimeError(f"DeFiLlama stablecoin issuers fetch failed: {exc}") from exc
    assets = st.get("peggedAssets")
    if not isinstance(assets, list) or not assets:
        raise RuntimeError("DeFiLlama stablecoins: empty asset list")
    rows = []
    for s in assets:
        sol = ((s.get("chainCirculating") or {}).get("Solana") or {}).get("current") or {}
        v = sol.get("peggedUSD")
        if isinstance(v, (int, float)) and v > 0:
            rows.append({"name": s.get("name") or s.get("symbol") or "?",
                         "supply_billion": round(v / 1e9, 3)})
    if not rows:
        raise RuntimeError("DeFiLlama stablecoins: zero Solana issuer supply")
    rows.sort(key=lambda r: -r["supply_billion"])
    return {"issuers": rows[:6],
            "issuers_tracked": len(rows)}


def collect_mev() -> dict:
    """Jito MEV economics: daily tip revenue + live tip market (keyless)."""
    out = {}
    try:
        fees = _get_json(DEFILLAMA + "/overview/fees?chain=Solana", timeout=30)
    except Exception as exc:
        raise RuntimeError(f"DeFiLlama fees (MEV) fetch failed: {exc}") from exc
    jito = None
    for p in fees.get("protocols") or []:
        if (p.get("displayName") or "") == "Jito MEV Tips":
            jito = p
            break
    if not jito or not isinstance(jito.get("total24h"), (int, float)):
        raise RuntimeError("Jito MEV Tips missing from DeFiLlama fees overview")
    out["jito_mev_tips_24h_usd"] = round(jito["total24h"])
    prev = jito.get("total48hto24h")
    if isinstance(prev, (int, float)) and prev > 0:
        out["jito_mev_tips_change_pct"] = round(
            (jito["total24h"] - prev) / prev * 100, 1)
    try:
        tip = _get_json(JITO_TIP_FLOOR, timeout=20)
    except Exception as exc:
        raise RuntimeError(f"Jito tip_floor fetch failed: {exc}") from exc
    row = tip[0] if isinstance(tip, list) and tip else tip
    med = (row or {}).get("ema_landed_tips_50th_percentile")
    if not isinstance(med, (int, float)) or med <= 0:
        raise RuntimeError(f"Jito tip_floor median missing/invalid: {med!r}")
    out["jito_tip_floor_median_sol"] = med
    return out


def _github(path: str):
    """Keyless GitHub REST call (60 req/hr unauthenticated — we use ~3/hr)."""
    try:
        return _get_json(GITHUB_API + path, timeout=20)
    except Exception as exc:
        raise RuntimeError(f"GitHub API {path} failed: {exc}") from exc


def collect_governance() -> dict:
    """Solana governance + client releases from GitHub (keyless).

    SIMDs live as PRs in solana-foundation/solana-improvement-documents;
    this is the only keyless window into protocol governance.
    """
    prs = _github("/repos/solana-foundation/solana-improvement-documents"
                  "/pulls?state=all&per_page=5&sort=updated&direction=desc")
    if not isinstance(prs, list) or not prs:
        raise RuntimeError("GitHub SIMD PRs: empty response")
    simds = [{"number": pr.get("number"),
              "title": (pr.get("title") or "")[:80],
              "state": pr.get("state")} for pr in prs]
    releases = {}
    for key, repo in (("agave", "anza-xyz/agave"),
                      ("firedancer", "firedancer-io/firedancer")):
        rel = _github(f"/repos/{repo}/releases?per_page=1")
        if not isinstance(rel, list) or not rel:
            raise RuntimeError(f"GitHub releases empty for {repo}")
        releases[key] = {"tag": rel[0].get("tag_name"),
                         "published": (rel[0].get("published_at") or "")[:10]}
    return {"latest_simds": simds, "client_releases": releases}


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
                "validators": collect_validators(),
                "dex_venues": collect_dex_venues(),
                "stablecoin_issuers": collect_stablecoin_issuers(),
                "mev": collect_mev(),
                "governance": collect_governance(),
                "news": fetch_news()}
    # Derived metric: average fee per transaction (24h fees ÷ est. daily txns).
    txns = snapshot["network"].get("est_daily_txns")
    fees_m = snapshot["defi"].get("fees_24h_million")
    if isinstance(txns, (int, float)) and txns > 0 and fees_m:
        snapshot["defi"]["avg_fee_per_txn_usd"] = round(fees_m * 1e6 / txns, 4)
    # Derived: Jito tip-floor median in USD (needs SOL price from economic).
    tip_sol = snapshot["mev"].get("jito_tip_floor_median_sol")
    sol_usd = snapshot["economic"].get("sol_price_usd")
    if isinstance(tip_sol, (int, float)) and isinstance(sol_usd, (int, float)):
        snapshot["mev"]["jito_tip_floor_median_usd"] = round(tip_sol * sol_usd, 6)
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
