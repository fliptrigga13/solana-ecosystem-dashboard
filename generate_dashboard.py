#!/usr/bin/env python3
"""Generate interactive dark-theme dashboard (single HTML file, Chart.js via CDN)."""
import json
import io_safety

snap = json.load(open("data.json"))
n, e = snap["network"], snap["economic"]
d, r = snap.get("defi", {}), snap.get("rwa", {})
v = snap.get("validators", {})
dv = snap.get("dex_venues", {})
si = snap.get("stablecoin_issuers", {})
mev = snap.get("mev", {})
gov = snap.get("governance", {})
fin = snap.get("finality", {})
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

# Build featured-validator HTML at top level (not inside a function):
# this file is exec()'d by autoupdate.refresh(), and functions defined here
# would resolve globals against autoupdate's module namespace, not this file's
# exec scope. Top-level sequential code is the file's existing style.
_featured_cards = []
for _v in FEATURED_VALIDATORS:
    _name = _v.get("name_match", "Featured validator")
    _url = _v.get("url", "#")
    _tagline = _v.get("tagline", "")
    _featured_cards.append(
        f'<a href="{_url}" target="_blank" rel="noopener sponsored" '
        f'style="text-decoration:none;color:inherit;">'
        f'<div class="card featured"><span class="badge-sponsored">Sponsored</span>'
        f'<div style="font-weight:700;">&#9733; {_name}</div>'
        f'<div style="font-size:.8rem;color:var(--muted);margin-top:4px;">{_tagline}</div>'
        f'</div></a>')
if _featured_cards:
    FEATURED_VALIDATORS_HTML = (
        '<div class="card" style="margin-bottom:16px;"><h3>Featured Validators</h3>'
        '<div class="grid">' + "".join(_featured_cards) + "</div></div>")
else:
    FEATURED_VALIDATORS_HTML = ""

html = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Solana Ecosystem Dashboard</title>
<meta name="description" content="Hourly-updated Solana network stats: TPS, finality, validators, Nakamoto coefficient, validator APY, client diversity, SOL price, DeFi TVL, stablecoins, DEX volume by venue, Jito MEV, RWA. Free API + alerts.">
<link rel="canonical" href="https://fliptrigga13.github.io/solana-ecosystem-dashboard/">
<meta property="og:title" content="Solana Ecosystem Dashboard">
<meta property="og:description" content="Hourly-updated Solana network stats: TPS, Nakamoto coefficient, validator APY, DEX venues, Jito MEV, stablecoin issuers, RWA. Free API + alerts.">
<meta property="og:type" content="website">
<meta property="og:url" content="https://fliptrigga13.github.io/solana-ecosystem-dashboard/">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="Solana Ecosystem Dashboard">
<meta name="twitter:description" content="Hourly-updated Solana network stats. Free API + alerts for validators and builders.">
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Dataset","name":"Solana Ecosystem Dashboard",
 "description":"Hourly snapshots of Solana network health: TPS, fees, validators, Nakamoto coefficient, validator APY and client diversity, SOL price, DeFi TVL, stablecoins, DEX volume by venue, Jito MEV tips, tokenized real-world assets, SIMD governance.",
 "url":"https://fliptrigga13.github.io/solana-ecosystem-dashboard/",
 "keywords":["Solana","blockchain","validator","DeFi","TVL","cryptocurrency","Nakamoto coefficient","MEV","DEX volume","staking APY","stablecoin"],
 "temporalCoverage":"2026-07-02/..","measurementTechnique":"automated hourly collection",
 "distribution":[{"@type":"DataDownload","contentUrl":"https://fliptrigga13.github.io/solana-ecosystem-dashboard/data.json","encodingFormat":"application/json"}]}
</script>
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
  <div class="card stat"><div class="v">__FINALITY__s</div><div class="l">Finality (measured)</div></div>
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
  <div class="card stat"><div class="v">__NAKAMOTO__</div><div class="l">Nakamoto coefficient</div></div>
  <div class="card stat"><div class="v">__JITO_SHARE__%</div><div class="l">Jito client share (stake)</div></div>
  <div class="card stat"><div class="v">__VAL_APY__%</div><div class="l">Avg validator APY</div></div>
  <div class="card stat"><div class="v">$__MEV_TIPS__K</div><div class="l">Jito MEV tips 24h (__MEV_CHG__%)</div></div>
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
<div style="display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-top:16px;">
  <div class="card"><h3>DEX Volume by Venue (24h)</h3>
    <table id="dexTable"><tr><th>Venue</th><th>Volume 24h ($M)</th></tr></table></div>
  <div class="card"><h3>Stablecoin Issuers on Solana</h3>
    <table id="stableTable"><tr><th>Issuer</th><th>Supply ($B)</th></tr></table></div>
</div>
<div style="display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-top:16px;">
  <div class="card"><h3>Client Diversity (stake-weighted)</h3><canvas id="clientChart"></canvas>
    <div style="font-size:.72rem;color:var(--muted);margin-top:8px;">Top-10 stake share: __TOP10_SHARE__% · Top-20: __TOP20_SHARE__%</div></div>
  <div class="card"><h3>Governance &amp; Client Releases</h3><div id="governance"></div></div>
</div>
<div class="card" style="margin-top:16px;"><h3>Ecosystem &amp; Community News</h3><div id="news"></div></div>
<div class="card ad-card" style="margin-top:16px;"><h3>Advertise on this dashboard</h3>
<div style="font-size:.85rem;color:var(--muted);">Featured validator and project placements available.
Slots are display-only, never affect rankings or data, and are always labeled <span class="badge-sponsored">Sponsored</span>.
Contact: __CONTACT_EMAIL__</div></div>
<div class="card" style="margin-top:16px;"><h3>Builders</h3>
<div style="font-size:.85rem;color:var(--muted);">
&#128241; <b>Free alerts</b> — hourly Telegram / email / webhook digests on TPS drops, price moves, delinquency spikes.
&nbsp; <b>API</b> — <span style="font-family:monospace;">GET /v1/snapshot</span> free tier, pro from $49/mo.
&nbsp; Embed this dashboard on your site:<br>
<span style="font-family:monospace;font-size:.75rem;">&lt;a href="https://fliptrigga13.github.io/solana-ecosystem-dashboard/"&gt;&lt;img src="https://fliptrigga13.github.io/solana-ecosystem-dashboard/badge.svg" alt="Solana Ecosystem Dashboard"&gt;&lt;/a&gt;</span>
</div></div>
<footer style="margin-top:24px;color:var(--muted);font-size:.75rem;text-align:center;">
Solana Ecosystem Dashboard · data: <a href="data.json" style="color:var(--muted);">data.json</a> ·
history: <a href="https://github.com/fliptrigga13/solana-ecosystem-dashboard" style="color:var(--muted);">GitHub</a>
</footer>
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
const dx = document.getElementById('dexTable');
(data.dex_venues?.venues || []).forEach(x => {
  dx.insertAdjacentHTML('beforeend', `<tr><td>${x.name}</td><td>$${x.volume_24h_million.toLocaleString()}</td></tr>`);
});
const st = document.getElementById('stableTable');
(data.stablecoin_issuers?.issuers || []).forEach(x => {
  st.insertAdjacentHTML('beforeend', `<tr><td>${x.name}</td><td>$${x.supply_billion.toLocaleString()}</td></tr>`);
});
const gv = document.getElementById('governance');
(data.governance?.latest_simds || []).forEach(s => {
  const stateColor = s.state === 'open' ? '#14F195' : '#94a3b8';
  gv.insertAdjacentHTML('beforeend',
    `<div style="padding:6px 0;border-bottom:1px solid var(--border);font-size:.85rem;">
       <a href="https://github.com/solana-foundation/solana-improvement-documents/pull/${s.number}" target="_blank" rel="noopener" style="color:#e2e8f0;text-decoration:none;">SIMD-${s.number}: ${s.title}</a>
       <span style="font-size:.72rem;color:${stateColor};margin-left:6px;">${s.state}</span></div>`);
});
const rel = data.governance?.client_releases || {};
Object.entries({agave: 'Agave', firedancer: 'Firedancer'}).forEach(([key, label]) => {
  const r = rel[key];
  if (r) gv.insertAdjacentHTML('beforeend',
    `<div style="font-size:.8rem;color:#94a3b8;margin-top:8px;">${label} latest: <b style="color:#e2e8f0;">${r.tag}</b> · ${r.published}</div>`);
});
const cs = data.validators?.client_share_pct || {};
new Chart(document.getElementById('clientChart'), {
  type: 'doughnut',
  data: { labels: Object.keys(cs),
    datasets: [{ data: Object.values(cs),
      backgroundColor: ['#9945FF', '#14F195', '#fbbf24', '#38bdf8'] }]},
  options: { plugins:{legend:{labels:{color:'#94a3b8', boxWidth:12}}} }
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
        .replace("__FINALITY__", str(fin.get("finality_estimate_s") or "—"))
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
        .replace("__NAKAMOTO__", str(n.get("nakamoto_coefficient") or "—"))
        .replace("__JITO_SHARE__", str((v.get("client_share_pct") or {}).get("jito-solana") or "—"))
        .replace("__VAL_APY__", str(v.get("avg_apy_pct") or "—"))
        .replace("__MEV_TIPS__", str(round((mev.get("jito_mev_tips_24h_usd") or 0) / 1000)) if mev.get("jito_mev_tips_24h_usd") else "—")
        .replace("__MEV_CHG__", str(mev.get("jito_mev_tips_change_pct") if mev.get("jito_mev_tips_change_pct") is not None else "—"))
        .replace("__TOP10_SHARE__", str(n.get("top10_stake_share_pct") or "—"))
        .replace("__TOP20_SHARE__", str(n.get("top20_stake_share_pct") or "—"))
        .replace("__UPGRADES__", json.dumps(UPCOMING_UPDATES))
        .replace("__DATA__", json.dumps(snap))
        .replace("__FEATURED_VALIDATORS__", FEATURED_VALIDATORS_HTML)
        .replace("__SPONSORED_VAL_NAMES__", json.dumps(SPONSORED_VAL_NAMES))
        .replace("__SPONSORED_PROJ_NAMES__", json.dumps(SPONSORED_PROJ_NAMES))
        .replace("__CONTACT_EMAIL__", CONTACT_EMAIL))

io_safety.atomic_write_text("index.html", html)
print("index.html written,", len(html), "bytes")

# --- Embeddable badge (passive promotion: every embed is a backlink) ---
# badge.svg is regenerated hourly with live TPS + SOL price. Validators and
# sites embed it with the snippet in the Builders card above.
_badge_tps = n.get("avg_tps_5h")
_badge_price = e.get("sol_price_usd")
_badge_val = (
    f"SOL ${round(_badge_price, 2):,} · {int(_badge_tps):,} TPS"
    if _badge_tps is not None and _badge_price is not None
    else "solana dashboard"
)
_label, _value = "solana dashboard", _badge_val
_lw = 8 * len(_label) + 16
_vw = 8 * len(_value) + 16
_badge_svg = (
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{_lw + _vw}" height="20">'
    f'<rect width="{_lw}" height="20" fill="#9945FF"/>'
    f'<rect x="{_lw}" width="{_vw}" height="20" fill="#0b0f1a"/>'
    f'<text x="{_lw / 2}" y="14" fill="#ffffff" font-size="11" font-family="monospace" text-anchor="middle">{_label}</text>'
    f'<text x="{_lw + _vw / 2}" y="14" fill="#14F195" font-size="11" font-family="monospace" text-anchor="middle">{_value}</text>'
    "</svg>"
)
io_safety.atomic_write_text("badge.svg", _badge_svg)
print("badge.svg written,", len(_badge_svg), "bytes")
