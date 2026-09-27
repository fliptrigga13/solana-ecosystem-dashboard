#!/usr/bin/env python3
"""Unit tests for the data API. Stdlib only, no network.

Exercises dispatch() directly plus auth/limits units. Uses temp dirs for
API_DIR (keys/usage storage) and DATA_DIR (data.json, data-history.jsonl,
and a copy of the repo's anomaly.py).
"""
import importlib
import json
import os
import shutil
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API_DIR_REAL = os.path.join(REPO, "api")


def make_snapshot(i):
    return {
        "collected_at": "2026-09-27T%02d:00:00+00:00" % i,
        "network": {
            "avg_tps_5h": 4000.0 + i * 10,
            "max_tps_5h": 5000.0,
            "epoch": 1032,
            "epoch_progress_pct": 20.0,
            "validators_active": 677,
            "validators_delinquent": 12,
        },
        "economic": {
            "sol_price_usd": 100.0 + i,
            "sol_price_change_24h_pct": -3.0,
            "defi_tvl_billion": 5.8,
        },
        "defi": {"stablecoin_supply_billion": 16.4, "fees_24h_million": 15.0,
                 "rev_24h_million": 6.7, "avg_fee_per_txn_usd": 0.04,
                 "dex_volume_24h_billion": 3.0, "dex_volume_change_24h_pct": 10.0},
        "rwa": {"tokenized_assets_billion": 1.78,
                "rwa_top": {"Hastra": 0.149}},
        "news": {"items": [], "feeds_ok": 1, "errors": []},
    }


class APITestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="api_test_")
        cls.api_dir = os.path.join(cls.tmp, "api")
        cls.data_dir = os.path.join(cls.tmp, "data")
        os.makedirs(cls.api_dir)
        os.makedirs(cls.data_dir)
        os.environ["API_DIR"] = cls.api_dir
        os.environ["DATA_DIR"] = cls.data_dir

        snap = make_snapshot(10)
        with open(os.path.join(cls.data_dir, "data.json"), "w") as f:
            json.dump(snap, f)
        # history: 8 full lines + 2 sparse (old format: network+economic only)
        with open(os.path.join(cls.data_dir, "data-history.jsonl"), "w") as f:
            for i in range(8):
                f.write(json.dumps(make_snapshot(i)) + "\n")
            for i in range(2):
                s = make_snapshot(i)
                f.write(json.dumps({"collected_at": s["collected_at"],
                                    "network": s["network"],
                                    "economic": s["economic"]}) + "\n")
        shutil.copy(os.path.join(REPO, "anomaly.py"),
                    os.path.join(cls.data_dir, "anomaly.py"))

        sys.path.insert(0, API_DIR_REAL)
        for mod in ("auth", "limits", "server"):
            sys.modules.pop(mod, None)
        cls.auth = importlib.import_module("auth")
        cls.limits = importlib.import_module("limits")
        cls.server = importlib.import_module("server")

        cls.free_key = cls.auth.create_key("t-free", "free")
        cls.pro_key = cls.auth.create_key("t-pro", "pro")
        cls.ent_key = cls.auth.create_key("t-ent", "enterprise")
        dead = cls.auth.create_key("t-dead", "free")
        cls.auth.revoke("t-dead")
        cls.dead_key = dead

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    # -- helpers ---------------------------------------------------------
    def call(self, path, key="__free__", method="GET", headers=None, limiter=None):
        h = dict(headers or {})
        if key == "__free__":
            h["X-API-Key"] = self.free_key
        elif key is not None:
            h["X-API-Key"] = key
        return self.server.dispatch(method, path, h, _limiter=limiter)

    # -- health ----------------------------------------------------------
    def test_health_no_auth(self):
        status, body, _ = self.server.dispatch("GET", "/v1/health", {})
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        self.assertEqual(body["snapshot_ts"], "2026-09-27T10:00:00+00:00")

    # -- auth ------------------------------------------------------------
    def test_missing_key_401(self):
        status, body, _ = self.call("/v1/snapshot", key=None)
        self.assertEqual(status, 401)
        self.assertIn("missing", body["error"])

    def test_invalid_key_401(self):
        status, body, _ = self.call("/v1/snapshot", key="sk_bogus")
        self.assertEqual(status, 401)
        self.assertIn("invalid", body["error"])

    def test_revoked_key_401(self):
        status, body, _ = self.call("/v1/snapshot", key=self.dead_key)
        self.assertEqual(status, 401)
        self.assertIn("revoked", body["error"])

    def test_header_case_insensitive(self):
        status, _, _ = self.server.dispatch(
            "GET", "/v1/snapshot", {"X-Api-KEY": self.free_key})
        self.assertEqual(status, 200)

    def test_plaintext_never_stored(self):
        with open(os.path.join(self.api_dir, "keys.json")) as f:
            raw = f.read()
        self.assertNotIn(self.free_key, raw)
        self.assertIn(self.auth.hash_key(self.free_key), raw)

    # -- tier gating ------------------------------------------------------
    def test_free_snapshot_ok(self):
        status, body, _ = self.call("/v1/snapshot")
        self.assertEqual(status, 200)
        for k in ("collected_at", "network", "economic", "defi", "rwa", "news"):
            self.assertIn(k, body)

    def test_free_metrics_ok(self):
        status, body, _ = self.call("/v1/metrics?name=avg_tps_5h")
        self.assertEqual(status, 200)
        self.assertEqual(body["metric"], "avg_tps_5h")
        self.assertEqual(body["count"], 10)
        self.assertEqual(body["points"][0],
                         {"t": "2026-09-27T00:00:00+00:00", "v": 4000.0})

    def test_free_history_403(self):
        status, body, _ = self.call("/v1/history")
        self.assertEqual(status, 403)
        self.assertIn("pro", body["error"])

    def test_free_anomalies_403(self):
        status, body, _ = self.call("/v1/anomalies")
        self.assertEqual(status, 403)

    def test_pro_history_ok(self):
        status, body, _ = self.call("/v1/history?limit=3", key=self.pro_key)
        self.assertEqual(status, 200)
        self.assertEqual(body["count"], 3)
        self.assertEqual(len(body["snapshots"]), 3)

    def test_pro_anomalies_ok(self):
        status, body, _ = self.call("/v1/anomalies", key=self.pro_key)
        self.assertEqual(status, 200)
        self.assertIn("snapshot_ts", body)
        self.assertIsInstance(body["anomalies"], list)
        self.assertEqual(body["count"], len(body["anomalies"]))

    def test_enterprise_history_ok(self):
        status, body, _ = self.call("/v1/history", key=self.ent_key)
        self.assertEqual(status, 200)
        self.assertEqual(body["count"], 10)

    # -- history limits ----------------------------------------------------
    def test_history_cap_500(self):
        status, body, _ = self.call("/v1/history?limit=9999", key=self.pro_key)
        self.assertEqual(status, 200)
        self.assertEqual(body["limit"], 500)
        self.assertLessEqual(body["count"], 500)

    def test_history_bad_limit(self):
        for q in ("limit=abc", "limit=0", "limit=-5"):
            status, body, _ = self.call("/v1/history?" + q, key=self.pro_key)
            self.assertEqual(status, 400, q)

    def test_history_default_limit(self):
        status, body, _ = self.call("/v1/history", key=self.pro_key)
        self.assertEqual(status, 200)
        self.assertEqual(body["limit"], 100)
        self.assertEqual(body["count"], 10)

    # -- metrics validation -------------------------------------------------
    def test_metrics_missing_name_400(self):
        status, body, _ = self.call("/v1/metrics")
        self.assertEqual(status, 400)
        self.assertIn("available", body)

    def test_metrics_unknown_name_400(self):
        status, body, _ = self.call("/v1/metrics?name=nope")
        self.assertEqual(status, 400)

    def test_metrics_skips_sparse_snapshots(self):
        # avg_fee_per_txn_usd only exists in the 8 full snapshots
        status, body, _ = self.call("/v1/metrics?name=avg_fee_per_txn_usd")
        self.assertEqual(status, 200)
        self.assertEqual(body["count"], 8)

    # -- routing -------------------------------------------------------------
    def test_unknown_path_404(self):
        status, body, _ = self.server.dispatch("GET", "/nope", {})
        self.assertEqual(status, 404)

    def test_method_not_allowed(self):
        status, body, _ = self.call("/v1/snapshot", method="POST")
        self.assertEqual(status, 405)

    # -- rate limiting ----------------------------------------------------------
    def test_limiter_unit(self):
        usage = os.path.join(self.tmp, "u1.json")
        lim = self.limits.RateLimiter(usage, save_every_s=3600)
        kh = "abc123"
        self.assertEqual(lim.check(kh, 2, now=1000.0)[:2], (True, 1))
        self.assertEqual(lim.check(kh, 2, now=1001.0)[:2], (True, 0))
        allowed, remaining, retry = lim.check(kh, 2, now=1002.0)
        self.assertFalse(allowed)
        self.assertEqual(remaining, 0)
        self.assertGreater(retry, 0)
        # window slides: after 24h the first hit expires
        allowed, _, _ = lim.check(kh, 2, now=1000.0 + 86401)
        self.assertTrue(allowed)

    def test_limiter_persists(self):
        usage = os.path.join(self.tmp, "u2.json")
        lim = self.limits.RateLimiter(usage, save_every_s=3600)
        lim.check("k", 1, now=2000.0)
        lim.save()
        lim2 = self.limits.RateLimiter(usage, save_every_s=3600)
        allowed, _, _ = lim2.check("k", 1, now=2001.0)
        self.assertFalse(allowed)

    def test_dispatch_429(self):
        old = self.auth.TIER_QUOTAS["free"]
        self.auth.TIER_QUOTAS["free"] = 2
        self.addCleanup(lambda: self.auth.TIER_QUOTAS.__setitem__("free", old))
        fresh = self.limits.RateLimiter(
            os.path.join(self.tmp, "u3.json"), save_every_s=3600)
        key = self.auth.create_key("t-rl", "free")
        h = {"X-API-Key": key}
        self.assertEqual(self.server.dispatch("GET", "/v1/snapshot", h,
                                              _limiter=fresh)[0], 200)
        self.assertEqual(self.server.dispatch("GET", "/v1/snapshot", h,
                                              _limiter=fresh)[0], 200)
        status, body, extra = self.server.dispatch("GET", "/v1/snapshot", h,
                                                   _limiter=fresh)
        self.assertEqual(status, 429)
        self.assertIn("Retry-After", extra)

    # -- mkkey -------------------------------------------------------------
    def test_expired_key_401(self):
        exp = self.auth.create_key("t-exp", "pro", expires_in_days=1)
        # force it into the past
        keys = self.auth.load_keys()
        kh = self.auth.hash_key(exp)
        keys[kh]["expires_at"] = "2020-01-01T00:00:00+00:00"
        import json as _json
        with open(self.auth.KEYS_FILE, "w") as f:
            _json.dump(keys, f)
        status, body, _ = self.call("/v1/snapshot", key=exp)
        self.assertEqual(status, 401)
        self.assertIn("expired", body["error"])
        # a non-expiring key still works
        self.assertFalse(self.auth.is_expired(
            self.auth.verify(self.pro_key)))

    def test_mkkey_create_list_revoke(self):
        import mkkey
        pt = mkkey.cmd_create("t-cli", "pro")
        self.assertTrue(pt.startswith("sk_"))
        names = [r[1] for r in mkkey.cmd_list()]
        self.assertIn("t-cli", names)
        # list output contains no plaintext
        self.assertNotIn(pt, json.dumps(mkkey.cmd_list()))
        self.assertTrue(mkkey.cmd_revoke("t-cli"))
        self.assertIsNone(self.auth.find_by_name("t-cli"))
        with self.assertRaises(ValueError):
            mkkey.cmd_create("t-bad", "platinum")

    def test_mkkey_expires_in_days(self):
        import mkkey
        pt = mkkey.cmd_create("t-eval", "pro", expires_in_days=14)
        kh = self.auth.hash_key(pt)
        rec = self.auth.load_keys()[kh]
        self.assertIsNotNone(rec.get("expires_at"))
        self.assertFalse(self.auth.is_expired(rec))
        # invalid values rejected
        with self.assertRaises(ValueError):
            mkkey.cmd_create("t-eval2", "pro", expires_in_days=0)
        with self.assertRaises(ValueError):
            mkkey.cmd_create("t-eval3", "pro", expires_in_days=-5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
