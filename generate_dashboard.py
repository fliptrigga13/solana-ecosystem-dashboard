#!/usr/bin/env python3
"""Generate interactive dark-theme dashboard (single HTML file, Chart.js via CDN)."""
import json
import io_safety

snap = json.load(open("data.json"))
n, e = snap["network"], snap["economic"]
d, r = snap.get("defi", {}), snap.get("rwa", {})
from collector import UPCOMING_UPDATES

# --- Sponsorships (monetization) ---
# sponsors.json is optional; missing/empty file => no sponsored slots rendered.
# Featured slots are display-only and ALWAYS carry a "Sponsored" disclosure badge.
try:
    _sponsors = json.load(open("sponsors.json"))
except (FileNotFoundError, json.JSONDecodeError):
    _sponsors = {}
CONTACT_EMAIL = _sponsors.get("contact_email", "TODO@yourdomain.com")
FEATURED_VALIDATORS = [v for v in _sponsors.get("validators", []) if v.get("enabled")]
FEATURED_PROJECTS = [p for p in _sponsors.get("projects", []) if p.get("enabled")]
SPONSORED_VAL_NAMES = [v["name_match"].lower() for v in FEATURED_VALIDATORS if v.get("name_match")]
SPONSORED_PROJ_NAMES = [p["name_match"].lower() for p in FEATURED_PROJECTS if p.get("name_match")]

def _featured_val_html():
    if not FEATURED_VALIDATORS:
        return ""
    cards = []
    for v in FEATURED_VALIDATORS:
        name = v.get("name_match", "Featured validator")
        url = v.get("url", "#")
        tagline = v.get("tagline", "")
        cards.append(
            f'<a href="{url}" target="_blank" rel="noopener sponsored" '
            f'style="text-decoration:none;color:inherit;">'
            f'<div class="card featured"><span class="badge-sponsored">Sponsored</span>'
            f'<div style="font-weight:700;">&#9733; {name}</div>'
            f'<div style="font-size:.8rem;color:var(--muted);margin-top:4px;">{tagline}</div>'
            f'</div></a>')
    return ('<div class="card" style="margin-bottom:16px;"><h3>Featured Validators</h3>'
            '<div class="grid">' + "".join(cards) + "</div></div>")

html = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Solana Ecosystem Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
  :root { --bg:#0b0f1a; --card:#111827; --border:#1f2937; --brand:#9945FF; --green:#14F195; --text:#e2e8f0; --muted:#94a3b8;}
  * { margin:0; box-sizing:border-box; }
  body { background:var(--bg); color:var(--text); font-family:system-ui,-apple-system,sans-serif; padding:24px; }
  h1 { font-size:1.6rem; } .sub { color:var(--muted); font-size:.8rem; font-family:monospace; }
  .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:16px; margin:20px 0; }
  .card { background:var(--card); border:1px solid var(--border); border-radius:12px; padding:18px; }
  .stat .v { font-size:2rem; font-weight:700; color:var(--green); }
  .stat .l { color:var(--muted); font-size:.75rem; text-transform:uppercase; letter-spacing:.08em; }
  table { width:100%; border-collapse:collapse; }
  th,td { padding:10px; text-align:left; border-bottom:1px solid var(--border); font-size:.85rem;}
  th { color:var(--muted); text-transform:uppercase; font-size:.7rem; }
  .badge-sponsored { display:inline-block; font-size:.65rem; font-weight:700; letter-spacing:.06em;
    text-transform:uppercase; color:#0b0f1a; background:#fbbf24; border-radius:4px; padding:2px 6px; margin-bottom:6px; }
  .featured { border-color:#fbbf24; }
  .ad-card { border-style:dashed; }
</style></head><body>
<h1>🟣 Solana Ecosystem Dashboard</h1>
<p class="sub">Auto-updated: __TIMESTAMP__</p>
<div class="grid">
  <div class="card stat"><div class="v">__AVG_TPS__</div><div class="l">Avg TPS (5h)</div></div>
  <div class="card stat"><div class="v">__MAX_TPS__</div><div class="l">Peak TPS</div></div>
  <div class="card stat"><div class="v">__EPOCH_PCT__%</div><div class="l">Epoch __EPOCH__ progress</div></div>
  <div class="card stat"><div class="v">$__SOL_PRICE__</div><div class="l">SOL price (24h: __SOL_CHG__%)</div></div>
  <div class="card stat"><div class="v">$__DEFI_TVL__B</div><div class="l">DeFi TVL</div></div>
  <div class="card stat"><div class="v">$__STABLES__B</div><div class="l">Stablecoin supply</div></div>
  <div class="card stat"><div class="v">$__DEX_VOL__B</div><div class="l">DEX volume 24h (__DEX_CHG__%)</div></div>
  <div class="card stat"><div class="v">$__RWA__B</div><div class="l">Tokenized assets (top-6)</div></div>
  <div class="card stat"><div class="v">$__FEES__M</div><div class="l">Fees 24h</div></div>
  <div class="card stat"><div class="v">$__REV__M</div><div class="l">REV 24h</div></div>
  <div class="card stat"><div class="v">$__FEE_TXN__</div><div class="l">Avg fee / txn (derived)</div></div>
  <div class="card stat"><div class="v">__VALIDATORS__</div><div class="l">Active validators</div></div>
  <div class="card stat"><div class="v">__DELINQ__</div><div class="l">Delinquent</div></div>
</div>
__FEATURED_VALIDATORS__
<div style="display:grid; grid-template-columns:1fr 1fr; gap:16px;">
  <div class="card"><h3>Top Validators by Stake</h3>
    <table id="validators"><tr><th>Validator</th><th>Stake (M SOL)</th><th>Commission</th></tr></table></div>
  <div class="card"><canvas id="stakeChart"></canvas></div>
</div>
<div style="display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-top:16px;">
  <div class="card"><h3>Tokenized Assets on Solana (RWA)</h3>
    <table id="rwaTable"><tr><th>Asset</th><th>TVL on Solana ($B)</th></tr></table></div>
  <div class="card"><h3>Upcoming Network Upgrades</h3><div id="upgrades"></div></div>
</div>
<div class="card" style="margin-top:16px;"><h3>Ecosystem &amp; Community News</h3><div id="news"></div></div>
<div class="card ad-card" style="margin-top:16px;"><h3>Advertise on this dashboard</h3>
<div style="font-size:.85rem;color:var(--muted);">Featured validator and project placements available.
Slots are display-only, never affect rankings or data, and are always labeled <span class="badge-sponsored">Sponsored</span>.
Contact: __CONTACT_EMAIL__</div></div>
<script>
const data = __DATA__;
const ns = document.getElementById('news');
(data.news?.items || []).forEach(item => {
  ns.insertAdjacentHTML('beforeend',
    `<div style="padding:8px 0;border-bottom:1px solid var(--border);font-size:.85rem;">
       <a href="${item.link}" target="_blank" rel="noopener" style="color:#e2e8f0;text-decoration:none;">${item.title}</a>
       <span style="font-size:.72rem;color:#94a3b8;margin-left:6px;">${item.source}${item.date ? ' · ' + item.date : ''}</span>
     </div>`);
});
const vt = document.getElementById('validators');
const sponsoredVals = __SPONSORED_VAL_NAMES__;
data.network.top_validators.forEach(v => {
  const isSponsored = sponsoredVals.includes((v.name || '').toLowerCase());
  const badge = isSponsored ? ' <span class="badge-sponsored">Sponsored</span>' : '';
  vt.insertAdjacentHTML('beforeend', `<tr><td>${v.name}${badge}</td><td>${v.stake_sol_million.toLocaleString()}</td><td>${v.commission}%</td></tr>`);
});
const rt = document.getElementById('rwaTable');
const sponsoredProjs = __SPONSORED_PROJ_NAMES__;
Object.entries(data.rwa?.rwa_top || {}).forEach(([name, tvl]) => {
  const isSponsored = sponsoredProjs.includes((name || '').toLowerCase());
  const badge = isSponsored ? ' <span class="badge-sponsored">Sponsored</span>' : '';
  rt.insertAdjacentHTML('beforeend', `<tr><td>${name}${badge}</td><td>$${tvl.toLocaleString()}</td></tr>`);
});
const up = document.getElementById('upgrades');
__UPGRADES__.forEach(u => {
  up.insertAdjacentHTML('beforeend',
    `<div style="margin-bottom:12px;"><a href="${u.url}" target="_blank" rel="noopener" style="color:#14F195;text-decoration:none;font-weight:600;">${u.name}</a>
     <div style="font-size:.8rem;color:#e2e8f0;margin-top:2px;">${u.detail}</div>
     <div style="font-size:.72rem;color:#94a3b8;">${u.status}</div></div>`);
});
new Chart(document.getElementById('stakeChart'), {
  type: 'bar',
  data: { labels: data.network.top_validators.map(v=>v.name),
    datasets: [{ label: 'Stake (M SOL)', data: data.network.top_validators.map(v=>v.stake_sol_million),
      backgroundColor: '#9945FF' }]},
  options: { plugins:{legend:{display:false}}, scales:{ x:{ticks:{color:'#94a3b8'}}, y:{ticks:{color:'#94a3b8'}} } }
});
</script></body></html>"""

html = (html
        .replace("__TIMESTAMP__", snap["collected_at"])
        .replace("__AVG_TPS__", f"{n['avg_tps_5h']:,}")
        .replace("__MAX_TPS__", f"{n['max_tps_5h']:,}")
        .replace("__EPOCH_PCT__", str(n["epoch_progress_pct"]))
        .replace("__EPOCH__", str(n["epoch"]))
        .replace("__SOL_PRICE__", str(e.get("sol_price_usd") or "—"))
        .replace("__SOL_CHG__", str(e.get("sol_price_change_24h_pct") or "—"))
        .replace("__DEFI_TVL__", str(e.get("defi_tvl_billion") or "—"))
        .replace("__STABLES__", str(d.get("stablecoin_supply_billion") or "—"))
        .replace("__DEX_VOL__", str(d.get("dex_volume_24h_billion") or "—"))
        .replace("__DEX_CHG__", str(d.get("dex_volume_change_24h_pct") if d.get("dex_volume_change_24h_pct") is not None else "—"))
        .replace("__RWA__", str(r.get("tokenized_assets_billion") or "—"))
        .replace("__FEES__", str(d.get("fees_24h_million") or "—"))
        .replace("__REV__", str(d.get("rev_24h_million") or "—"))
        .replace("__FEE_TXN__", str(d.get("avg_fee_per_txn_usd") or "—"))
        .replace("__VALIDATORS__", f"{n['validators_active']:,}")
        .replace("__DELINQ__", str(n["validators_delinquent"]))
        .replace("__UPGRADES__", json.dumps(UPCOMING_UPDATES))
        .replace("__DATA__", json.dumps(snap))
        .replace("__FEATURED_VALIDATORS__", _featured_val_html())
        .replace("__SPONSORED_VAL_NAMES__", json.dumps(SPONSORED_VAL_NAMES))
        .replace("__SPONSORED_PROJ_NAMES__", json.dumps(SPONSORED_PROJ_NAMES))
        .replace("__CONTACT_EMAIL__", CONTACT_EMAIL))

io_safety.atomic_write_text("index.html", html)
print("index.html written,", len(html), "bytes")
