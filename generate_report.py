#!/usr/bin/env python3
"""Generate report.md (human-readable) from data.json."""
import json
from datetime import datetime

snap = json.load(open("data.json"))
n, e = snap["network"], snap["economic"]
d, r = snap.get("defi", {}), snap.get("rwa", {})
from collector import UPCOMING_UPDATES

lines = [
    "# Solana Ecosystem Report",
    f"*Auto-generated: {snap['collected_at']}*",
    "",
    "## Network Performance",
    f"- **Slot:** {n['slot']:,} · **Block height:** {n['block_height']:,}",
    f"- **Epoch:** {n['epoch']} ({n['epoch_progress_pct']}% complete)",
    f"- **Avg TPS (5h):** {n['avg_tps_5h']:,.0f} · **Peak:** {n['max_tps_5h']:,.0f}",
    "",
    "## Validators",
    f"- **Active:** {n['validators_active']:,} · **Delinquent:** {n['validators_delinquent']}",
    f"- **Total stake:** {n['total_stake_sol_million']:,.1f}M SOL",
    "",
    "| Validator | Stake (M SOL) | Commission |",
    "|---|---|---|",
]
for v in n["top_validators"]:
    lines.append(f"| {v['name']} | {v['stake_sol_million']:,} | {v['commission']}% |")

lines += ["", "## Economic Indicators"]
if e.get("sol_price_usd"):
    lines.append(f"- **SOL price:** ${e['sol_price_usd']} ({e.get('sol_price_change_24h_pct','?')}% 24h)")
if e.get("sol_market_cap_billion"):
    lines.append(f"- **Market cap:** ${e['sol_market_cap_billion']}B")
if e.get("defi_tvl_billion"):
    lines.append(f"- **DeFi TVL:** ${e['defi_tvl_billion']}B")

lines += ["", "## DeFi Depth"]
if d.get("stablecoin_supply_billion"):
    lines.append(f"- **Stablecoin supply:** ${d['stablecoin_supply_billion']}B")
if d.get("dex_volume_24h_billion"):
    lines.append(f"- **DEX volume (24h):** ${d['dex_volume_24h_billion']}B ({d.get('dex_volume_change_24h_pct','?')}% 1d)")
if d.get("fees_24h_million"):
    lines.append(f"- **Fees (24h):** ${d['fees_24h_million']}M")
if d.get("rev_24h_million"):
    lines.append(f"- **REV (24h):** ${d['rev_24h_million']}M")

lines += ["", "## Tokenized Assets on Solana"]
if r.get("tokenized_assets_billion"):
    lines.append(f"- **Top-6 RWA TVL on Solana:** ${r['tokenized_assets_billion']}B")
for name, tvl in (r.get("rwa_top") or {}).items():
    lines.append(f"  - {name}: ${tvl}B")

lines += ["", "## Upcoming Network Upgrades"]
for u in UPCOMING_UPDATES:
    lines.append(f"- **[{u['name']}]({u['url']})** — {u['detail']} · {u['status']}")

open("report.md", "w", encoding="utf-8").write("\n".join(lines))
print("report.md written,", len(lines), "lines")
