"""Focused tests for the RWA fallback layer (collector.py).

Uses mocks — no network. Complements the live validation done during
development (Jupiter v3 supplies verified byte-identical to on-chain,
Ondo API, Yahoo v8, BUIDL supply, Hastra vault balances).
"""
import json
import sys
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
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


def fake_protocols(slugs):
    return [{"slug": s, "name": s.title()} for s in slugs]


# ---------------------------------------------------------------- primary
def t_primary_used_when_series_present():
    series = [{"totalLiquidityUSD": 1.5e9}, {"totalLiquidityUSD": 1.6e9}]
    with mock.patch.object(collector, "_get_json") as g:
        def side(url, body=None):
            if url.endswith("/protocols"):
                return fake_protocols(collector.RWA_SLUGS)
            return {"chainTvls": {"Solana": {"tvl": series}}}
        g.side_effect = side
        r = collector.collect_rwa()
    assert r["tokenized_assets_billion"] == round(1.6 * len(collector.RWA_SLUGS), 3), r
    assert all(v == "defillama" for v in r["rwa_sources"].values()), r["rwa_sources"]
check("primary DeFiLlama path used when Solana series present", t_primary_used_when_series_present)


def t_empty_series_uses_fallback():
    with mock.patch.object(collector, "_get_json") as g, \
         mock.patch.object(collector, "_rwa_fallback_value",
                           return_value=(0.777, "fallback-src")) as fb:
        def side(url, body=None):
            if url.endswith("/protocols"):
                return fake_protocols(collector.RWA_SLUGS)
            if url.endswith("invesco-ustb"):
                # the one slug whose DeFiLlama series is healthy: no fallback
                return {"chainTvls": {"Solana": {"tvl": [
                    {"totalLiquidityUSD": 2e8}]}}}
            return {"chainTvls": {"Solana": {"tvl": []}}}  # empty -> fallback
        g.side_effect = side
        r = collector.collect_rwa()
    nfb = len(collector.RWA_SLUGS) - 1
    assert fb.call_count == nfb, fb.call_count
    assert r["rwa_sources"]["Invesco-Ustb"] == "defillama", r["rwa_sources"]
    assert r["tokenized_assets_billion"] == round(0.777 * nfb + 0.2, 3)
check("empty DeFiLlama series -> fallback used; healthy slug stays primary",
      t_empty_series_uses_fallback)


def t_both_fail_raises_naming_slug():
    with mock.patch.object(collector, "_get_json") as g, \
         mock.patch.object(collector, "_rwa_fallback_value",
                           side_effect=RuntimeError("boom")):
        def side(url, body=None):
            if url.endswith("/protocols"):
                return fake_protocols(collector.RWA_SLUGS)
            return {"chainTvls": {}}  # missing -> fallback -> boom
        g.side_effect = side
        try:
            collector.collect_rwa()
        except RuntimeError as e:
            assert collector.RWA_SLUGS[0] in str(e), str(e)
            assert "boom" in str(e), str(e)
            return
    raise AssertionError("did not raise")
check("primary + fallback both fail -> loud error naming the slug", t_both_fail_raises_naming_slug)


def t_missing_slug_still_fails():
    # partial_coverage regression: a vanished slug must fail loudly.
    with mock.patch.object(collector, "_get_json",
                           return_value=fake_protocols(collector.RWA_SLUGS[1:])):
        try:
            collector.collect_rwa()
        except RuntimeError as e:
            assert collector.RWA_SLUGS[0] in str(e), str(e)
            return
    raise AssertionError("did not raise")
check("missing slug still fails loudly (partial_coverage)", t_missing_slug_still_fails)


# ---------------------------------------------------------------- baskets
def _jup_payload(entries):
    # entries: mint -> (price, supply)
    d = {}
    for m, (px, sc) in entries.items():
        e = {}
        if px:
            e["stockData"] = {"price": px}
        if sc:
            e["scaledUiConfig"] = {"circSupplyPrescaled": sc}
        d[m] = e
    return d


def t_basket_jupiter_only():
    cfg = {"kind": "jupiter_basket", "mints": [
        {"mint": "M1", "label": "A", "ticker": "A"},
        {"mint": "M2", "label": "B", "ticker": "B"}]}
    with mock.patch.object(collector, "_get_json",
                           return_value=_jup_payload({"M1": (10.0, 100.0),
                                                      "M2": (5.0, 50.0)})):
        val, src = collector._rwa_fallback_value("x", cfg)
    assert abs(val - 1250.0 / 1e9) < 1e-12, val
check("jupiter_basket: pure-Jupiter supply x price math", t_basket_jupiter_only)


def t_basket_gap_filled_via_rpc_and_yahoo():
    cfg = {"kind": "jupiter_basket", "mints": [
        {"mint": "M1", "label": "A", "ticker": "A"},
        {"mint": "M2", "label": "B", "ticker": "B"}]}
    with mock.patch.object(collector, "_get_json",
                           return_value=_jup_payload({"M1": (10.0, 100.0),
                                                      "M2": (None, None)})), \
         mock.patch.object(collector, "_rpc_batch",
                           return_value={0: {"value": {"amount": "200",
                                                       "decimals": 0}}}), \
         mock.patch.object(collector, "_yahoo_prices",
                           return_value={"B": 7.0}):
        val, src = collector._rwa_fallback_value("x", cfg)
    # 100*10 + 200*7 = 2400
    assert abs(val - 2400.0 / 1e9) < 1e-12, val
check("jupiter_basket: RPC supply + Yahoo price fill Jupiter gaps", t_basket_gap_filled_via_rpc_and_yahoo)


def t_basket_unpriced_nonzero_supply_raises():
    cfg = {"kind": "jupiter_basket", "mints": [
        {"mint": "M9", "label": "Ghost", "ticker": "NOHOPE"}]}
    with mock.patch.object(collector, "_get_json", return_value={}), \
         mock.patch.object(collector, "_rpc_batch",
                           return_value={0: {"value": {"amount": "5",
                                                       "decimals": 0}}}), \
         mock.patch.object(collector, "_yahoo_prices", return_value={}):
        try:
            collector._rwa_fallback_value("x", cfg)
        except RuntimeError as e:
            assert "Ghost" in str(e), str(e)
            return
    raise AssertionError("did not raise")
check("jupiter_basket: nonzero supply + no price -> loud, names token", t_basket_unpriced_nonzero_supply_raises)


def t_basket_zero_supply_unpriced_ok():
    cfg = {"kind": "jupiter_basket", "mints": [
        {"mint": "M0", "label": "Dead", "ticker": "NOHOPE"}]}
    with mock.patch.object(collector, "_get_json", return_value={}), \
         mock.patch.object(collector, "_rpc_batch",
                           return_value={0: {"value": {"amount": "0",
                                                       "decimals": 0}}}):
        try:
            collector._rwa_fallback_value("x", cfg)
        except RuntimeError:
            return  # zero-total guard fired, as required
    raise AssertionError("did not raise")
check("jupiter_basket: all-zero basket fails via zero-total guard",
      t_basket_zero_supply_unpriced_ok)


# ---------------------------------------------------------------- spl_nav / ondo_api / vault
def t_spl_nav():
    cfg = {"kind": "spl_nav", "nav_usd": 1.0, "mints": ["BM"]}
    with mock.patch.object(collector, "_rpc_batch",
                           return_value={0: {"value": {"amount": "987884399070000",
                                                       "decimals": 6}}}):
        val, src = collector._rwa_fallback_value("blackrock-buidl", cfg)
    assert abs(val - 0.98788439907) < 1e-9, val
check("spl_nav: supply x $1 NAV math", t_spl_nav)


def t_ondo_api():
    cfg = {"kind": "ondo_api", "symbol": "usdy", "chain": "solana"}
    payload = {"assets": [{"symbol": "ousg", "tvlUsd": {"solana": 1}},
                           {"symbol": "usdy",
                            "tvlUsd": {"solana": 179102683.53}}]}
    with mock.patch.object(collector, "_get_json", return_value=payload):
        val, src = collector._rwa_fallback_value("ondo-yield-assets", cfg)
    assert abs(val - 0.17910268353) < 1e-9, val
check("ondo_api: issuer tvlUsd.solana math", t_ondo_api)


def t_vault_balances():
    cfg = {"kind": "vault_balances", "usd_per_token": 1.0,
           "accounts": ["A", "B", "C"]}
    with mock.patch.object(collector, "_rpc_batch", return_value={
            0: {"value": {"uiAmount": 729596.888335}},
            1: {"value": {"uiAmount": 130917295.631854}},
            2: {"value": {"uiAmount": 36557083.192192}}}):
        val, src = collector._rwa_fallback_value("hastra", cfg)
    assert abs(val - 0.168203975611381) < 1e-9, val
check("vault_balances: three-vault sum math", t_vault_balances)


# ---------------------------------------------------------------- yahoo
def t_yahoo_usd_sentinel_and_dash():
    seen = {}

    def fake_get(url, body=None):
        seen["url"] = url
        return {"chart": {"result": [{
            "indicators": {"quote": [{"close": [None, 505.48]}]},
            "meta": {}}]}}

    with mock.patch.object(collector, "_get_json", side_effect=fake_get):
        out = collector._yahoo_prices(["BRK.B", "USD"])
    assert out["USD"] == 1.0, out
    assert out["BRK.B"] == 505.48, out
    assert "BRK-B" in seen["url"], seen["url"]
check("yahoo: USD sentinel=1.0 and '.'->'-' normalization", t_yahoo_usd_sentinel_and_dash)


# ---------------------------------------------------------------- _rpc_batch vs local mock server
class MockRPC(BaseHTTPRequestHandler):
    mode = "ok"  # or "no_batch"

    def do_POST(self):
        ln = int(self.headers["Content-Length"])
        payload = json.loads(self.rfile.read(ln))

        def one(item):
            return {"jsonrpc": "2.0", "id": item["id"],
                    "result": {"echo": item["params"]}}

        if isinstance(payload, list) and self.mode == "no_batch":
            self.send_response(403)
            self.end_headers()
            return
        body = json.dumps([one(i) for i in payload] if isinstance(payload, list)
                          else one(payload)).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def t_rpc_batch_chunking_and_fallback():
    srv = HTTPServer(("127.0.0.1", 0), MockRPC)
    port = srv.server_address[1]
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        with mock.patch.object(collector, "RPC_ENDPOINTS",
                               [f"http://127.0.0.1:{port}"]):
            # 25 calls -> 3 chunks (10/10/5), ids must map back correctly
            calls = [("m%d" % i, ["p%d" % i]) for i in range(25)]
            out = collector._rpc_batch(calls)
            assert len(out) == 25, len(out)
            for i in range(25):
                assert out[i] == {"echo": ["p%d" % i]}, (i, out[i])
            # now make the server refuse batches -> singles fallback
            MockRPC.mode = "no_batch"
            out = collector._rpc_batch(calls[:3])
            assert len(out) == 3, out
            for i in range(3):
                assert out[i] == {"echo": ["p%d" % i]}, (i, out[i])
    finally:
        MockRPC.mode = "ok"
        srv.shutdown()
check("_rpc_batch: chunked ids correct; batch-403 falls back to singles", t_rpc_batch_chunking_and_fallback)


print(f"\n{sum(1 for s, _ in results if s == PASS)}/{len(results)} passed")
for s, name in results:
    if s == FAIL:
        print(f"  {s}: {name}")
sys.exit(1 if any(s == FAIL for s, _ in results) else 0)
