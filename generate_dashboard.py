#!/usr/bin/env python3
"""Generate interactive dark-theme dashboard (single HTML file, Chart.js via CDN)."""
import json

snap = json.load(open("data.json"))
n, e = snap["network"], snap["economic"]

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
</style></head><body>
<h1>🟣 Solana Ecosystem Dashboard</h1>
<p class="sub">Auto-updated: __TIMESTAMP__</p>
<div class="grid">
  <div class="card stat"><div class="v">__AVG_TPS__</div><div class="l">Avg TPS (5h)</div></div>
  <div class="card stat"><div class="v">__MAX_TPS__</div><div class="l">Peak TPS</div></div>
  <div class="card stat"><div class="v">__EPOCH_PCT__%</div><div class="l">Epoch __EPOCH__ progress</div></div>
  <div class="card stat"><div class="v">$__SOL_PRICE__</div><div class="l">SOL price (24h: __SOL_CHG__%)</div></div>
  <div class="card stat"><div class="v">__VALIDATORS__</div><div class="l">Active validators</div></div>
  <div class="card stat"><div class="v">__DELINQ__</div><div class="l">Delinquent</div></div>
</div>
<div style="display:grid; grid-template-columns:1fr 1fr; gap:16px;">
  <div class="card"><h3>Top Validators by Stake</h3>
    <table id="validators"><tr><th>Validator</th><th>Stake (M SOL)</th><th>Commission</th></tr></table></div>
  <div class="card"><canvas id="stakeChart"></canvas></div>
</div>
<script>
const data = __DATA__;
const vt = document.getElementById('validators');
data.network.top_validators.forEach(v => {
  vt.insertAdjacentHTML('beforeend', `<tr><td>${v.name}</td><td>${v.stake_sol_million.toLocaleString()}</td><td>${v.commission}%</td></tr>`);
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
        .replace("__VALIDATORS__", f"{n['validators_active']:,}")
        .replace("__DELINQ__", str(n["validators_delinquent"]))
        .replace("__DATA__", json.dumps(snap)))

open("dashboard.html", "w", encoding="utf-8").write(html)
print("dashboard.html written,", len(html), "bytes")
