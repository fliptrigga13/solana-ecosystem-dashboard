#!/usr/bin/env python3
"""Stdlib unittest for the alerts/ subscription engine. No real network."""
import json
import os
import sys
import unittest
import urllib.error
from datetime import datetime, timedelta, timezone
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import anomaly  # noqa: E402
import check    # noqa: E402
import deliver  # noqa: E402
import rules    # noqa: E402


def make_snapshot(**overrides):
    snap = {
        "collected_at": "2026-09-27T00:00:00+00:00",
        "network": {
            "avg_tps_5h": 4000.0, "max_tps_5h": 5000.0,
            "epoch": 1032, "epoch_progress_pct": 20.0,
            "validators_active": 677, "validators_delinquent": 10,
        },
        "economic": {"sol_price_usd": 100.0, "defi_tvl_billion": 5.0},
        "defi": {
            "stablecoin_supply_billion": 16.0, "dex_volume_24h_billion": 3.0,
            "fees_24h_million": 15.0, "rev_24h_million": 6.0,
        },
        "rwa": {"tokenized_assets_billion": 1.7},
    }
    for section, vals in overrides.items():
        snap.setdefault(section, {}).update(vals)
    return snap


def make_history(n=20, **overrides):
    return [make_snapshot(**overrides) for _ in range(n)]


class TestRules(unittest.TestCase):
    def test_tps_drop_fires_critical(self):
        history = make_history()
        snap = make_snapshot(network={"avg_tps_5h": 1000.0})  # -75% vs 4000
        anomalies = anomaly.detect_anomalies(snap, history)
        events = rules.evaluate(snap, history, anomalies)
        tps = [e for e in events if e["rule_id"] == "tps_drop"]
        self.assertEqual(len(tps), 1)
        self.assertEqual(tps[0]["severity"], "CRITICAL")  # 75% >= 2x30% threshold
        self.assertEqual(tps[0]["metric"], "avg_tps_5h")
        self.assertIn("deviation_pct", tps[0])
        for key in ("rule_id", "severity", "title", "detail", "metric",
                    "current", "baseline", "deviation_pct", "ts"):
            self.assertIn(key, tps[0])

    def test_tps_spike_does_not_fire_tps_drop(self):
        history = make_history()
        snap = make_snapshot(network={"avg_tps_5h": 8000.0})  # +100% spike
        anomalies = anomaly.detect_anomalies(snap, history)
        events = rules.evaluate(snap, history, anomalies)
        self.assertFalse([e for e in events if e["rule_id"] == "tps_drop"])

    def test_price_move_fires_both_directions(self):
        history = make_history()
        for price, direction in ((85.0, "drop"), (115.0, "spike")):  # +/-15% vs 100
            snap = make_snapshot(economic={"sol_price_usd": price})
            anomalies = anomaly.detect_anomalies(snap, history)
            events = rules.evaluate(snap, history, anomalies)
            pm = [e for e in events if e["rule_id"] == "price_move"]
            self.assertEqual(len(pm), 1, f"price {price}")
            self.assertEqual(pm[0]["severity"], "WARNING")  # 15% < 2x10%

    def test_epoch_ending_info(self):
        snap = make_snapshot(network={"epoch_progress_pct": 96.5})
        events = rules.evaluate(snap, [], [])
        epoch = [e for e in events if e["rule_id"] == "epoch_ending"]
        self.assertEqual(len(epoch), 1)
        self.assertEqual(epoch[0]["severity"], "INFO")

    def test_epoch_ending_not_firing(self):
        snap = make_snapshot(network={"epoch_progress_pct": 20.02})
        events = rules.evaluate(snap, [], [])
        self.assertFalse([e for e in events if e["rule_id"] == "epoch_ending"])

    def test_no_history_note_entry_skipped(self):
        snap = make_snapshot()
        anomalies = anomaly.detect_anomalies(snap, [])  # [{"metric": "*", ...}]
        events = rules.evaluate(snap, [], anomalies)
        self.assertEqual(events, [])

    def test_delinquent_spike(self):
        history = make_history()
        snap = make_snapshot(network={"validators_delinquent": 30})  # +200% vs 10
        anomalies = anomaly.detect_anomalies(snap, history)
        events = rules.evaluate(snap, history, anomalies)
        d = [e for e in events if e["rule_id"] == "delinquent_spike"]
        self.assertEqual(len(d), 1)
        self.assertEqual(d[0]["severity"], "CRITICAL")  # 200% >= 2x100%

    def test_thresholds_come_from_anomaly(self):
        # rules must not define their own thresholds; single source of truth.
        for rule_id, spec in rules.RULE_DEFS.items():
            self.assertIn(spec["metric"], anomaly.THRESHOLDS)


class TestFiltering(unittest.TestCase):
    def _event(self, rule_id="tps_drop", severity="WARNING"):
        return {"rule_id": rule_id, "severity": severity, "title": "t",
                "detail": "d", "metric": "m", "current": 1, "baseline": 2,
                "deviation_pct": -50.0, "ts": "2026-09-27T00:00:00+00:00"}

    def test_min_severity_filters_info(self):
        sub = {"rules": ["*"], "min_severity": "WARNING"}
        self.assertFalse(check.subscriber_wants(sub, self._event(severity="INFO")))
        self.assertTrue(check.subscriber_wants(sub, self._event(severity="WARNING")))
        self.assertTrue(check.subscriber_wants(sub, self._event(severity="CRITICAL")))

    def test_pro_gets_info(self):
        sub = {"rules": ["*"], "min_severity": "INFO"}
        self.assertTrue(check.subscriber_wants(sub, self._event(severity="INFO")))

    def test_rule_list_filter(self):
        sub = {"rules": ["price_move"], "min_severity": "INFO"}
        self.assertFalse(check.subscriber_wants(sub, self._event(rule_id="tps_drop")))
        self.assertTrue(check.subscriber_wants(sub, self._event(rule_id="price_move")))

    def test_wildcard_rule(self):
        sub = {"rules": ["*"], "min_severity": "INFO"}
        self.assertTrue(check.subscriber_wants(sub, self._event(rule_id="rwa_move")))


class TestCooldown(unittest.TestCase):
    def _event(self):
        return {"rule_id": "tps_drop", "severity": "WARNING"}

    def test_no_prior_send(self):
        now = datetime.now(timezone.utc)
        self.assertTrue(check.should_send({}, "free", self._event(), now))

    def test_within_cooldown_skipped(self):
        now = datetime.now(timezone.utc)
        sent = {"free:tps_drop:WARNING": (now - timedelta(hours=1)).isoformat()}
        self.assertFalse(check.should_send(sent, "free", self._event(), now))

    def test_after_cooldown_sends(self):
        now = datetime.now(timezone.utc)
        old = (now - timedelta(days=8)).isoformat()
        sent = {"free:tps_drop:WARNING": old}
        self.assertTrue(check.should_send(sent, "free", self._event(), now))

    def test_pro_cooldown_shorter_than_free(self):
        now = datetime.now(timezone.utc)
        two_hours_ago = (now - timedelta(hours=2)).isoformat()
        sent = {"pro:tps_drop:WARNING": two_hours_ago}
        self.assertTrue(check.should_send(sent, "pro", self._event(), now))
        sent = {"free:tps_drop:WARNING": two_hours_ago}
        self.assertFalse(check.should_send(sent, "free", self._event(), now))

    def test_cooldown_key_includes_tier_and_severity(self):
        now = datetime.now(timezone.utc)
        sent = {"free:tps_drop:WARNING": (now - timedelta(minutes=1)).isoformat()}
        crit = {"rule_id": "tps_drop", "severity": "CRITICAL"}
        self.assertTrue(check.should_send(sent, "free", crit, now))
        self.assertTrue(check.should_send(sent, "pro", self._event(), now))


class TestDelivery(unittest.TestCase):
    def _event(self):
        return {"rule_id": "tps_drop", "severity": "WARNING", "title": "TPS drop",
                "detail": "dropped", "metric": "avg_tps_5h", "current": 1000,
                "baseline": 4000, "deviation_pct": -75.0,
                "ts": "2026-09-27T00:00:00+00:00"}

    def test_webhook_failure_returns_false(self):
        with mock.patch.object(deliver, "_http_post",
                               side_effect=urllib.error.URLError("nope")):
            self.assertFalse(deliver.send_webhook("https://example.com/hook", self._event()))
            self.assertFalse(deliver.send("webhook", "https://example.com/hook", self._event()))

    def test_webhook_success(self):
        with mock.patch.object(deliver, "_http_post", return_value=True):
            self.assertTrue(deliver.send_webhook("https://example.com/hook", self._event()))

    def test_telegram_failure_returns_false(self):
        with mock.patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "x"}), \
             mock.patch.object(deliver, "_http_post", return_value=False):
            self.assertFalse(deliver.send_telegram("123", self._event()))

    def test_telegram_no_token_returns_false(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TELEGRAM_BOT_TOKEN", None)
            self.assertFalse(deliver.send_telegram("123", self._event()))

    def test_email_failure_returns_false(self):
        with mock.patch.dict(os.environ, {"SMTP_HOST": "smtp.example.com"}), \
             mock.patch("smtplib.SMTP", side_effect=OSError("conn refused")):
            self.assertFalse(deliver.send_email("a@example.com", self._event()))

    def test_email_no_host_returns_false(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SMTP_HOST", None)
            self.assertFalse(deliver.send_email("a@example.com", self._event()))

    def test_unknown_channel_returns_false(self):
        self.assertFalse(deliver.send("smoke-signal", "dest", self._event()))

    def test_send_never_raises(self):
        with mock.patch.object(deliver, "_http_post", side_effect=RuntimeError("boom")):
            self.assertFalse(deliver.send("webhook", "https://example.com", self._event()))


class TestDigest(unittest.TestCase):
    def _events(self):
        return [
            {"rule_id": "tps_drop", "severity": "WARNING", "title": "TPS drop",
             "detail": "dropped", "ts": "2026-09-27T00:00:00+00:00"},
            {"rule_id": "price_move", "severity": "CRITICAL", "title": "SOL -8%",
             "detail": "moved", "ts": "2026-09-27T00:00:00+00:00"},
        ]

    def test_format_digest_lists_all_events(self):
        text = deliver.format_digest(self._events())
        self.assertIn("2 alert(s)", text)
        self.assertIn("TPS drop", text)
        self.assertIn("SOL -8%", text)

    def test_format_digest_empty(self):
        self.assertIn("0 alert(s)", deliver.format_digest([]))

    def test_send_digest_empty_is_noop_success(self):
        self.assertTrue(deliver.send_digest("webhook", "https://example.com", []))

    def test_send_digest_webhook_posts_combined_payload(self):
        captured = {}

        def fake_post(url, payload, content_type="application/json"):
            captured["url"] = url
            captured["payload"] = json.loads(payload.decode())
            return True

        with mock.patch.object(deliver, "_http_post", side_effect=fake_post):
            self.assertTrue(deliver.send_digest("webhook", "https://example.com/hook",
                                               self._events()))
        self.assertEqual(captured["payload"]["type"], "solana_dashboard_digest")
        self.assertEqual(len(captured["payload"]["events"]), 2)

    def test_send_digest_webhook_failure_returns_false(self):
        with mock.patch.object(deliver, "_http_post",
                               side_effect=urllib.error.URLError("nope")):
            self.assertFalse(deliver.send_digest("webhook", "https://example.com",
                                                self._events()))

    def test_send_digest_unknown_channel_returns_false(self):
        self.assertFalse(deliver.send_digest("smoke-signal", "dest", self._events()))

    def test_send_digest_never_raises(self):
        with mock.patch.object(deliver, "_http_post", side_effect=RuntimeError("boom")):
            self.assertFalse(deliver.send_digest("webhook", "https://example.com",
                                                self._events()))

    def test_telegram_digest_no_token_returns_false(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TELEGRAM_BOT_TOKEN", None)
            self.assertFalse(deliver.send_digest("telegram", "123", self._events()))

    def test_email_digest_no_host_returns_false(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SMTP_HOST", None)
            self.assertFalse(deliver.send_digest("email", "a@example.com", self._events()))


class TestFreeTierBatching(unittest.TestCase):
    def _run_check_with_subscriber(self, tier):
        # check.main against a fabricated event set: patch rules.evaluate to
        # return two WARNING events, then observe delivery calls.
        import tempfile
        tmp = tempfile.mkdtemp()
        subs = os.path.join(tmp, "subscribers.json")
        sent = os.path.join(tmp, "sent.json")
        with open(subs, "w") as f:
            json.dump({"subscribers": [{
                "id": "s1", "channel": "webhook",
                "destination": "https://example.com/hook",
                "tier": tier, "rules": ["*"], "min_severity": "WARNING",
                "enabled": True,
            }]}, f)
        events = [
            {"rule_id": "tps_drop", "severity": "WARNING", "title": "TPS drop",
             "ts": "2026-09-27T00:00:00+00:00"},
            {"rule_id": "price_move", "severity": "WARNING", "title": "SOL move",
             "ts": "2026-09-27T00:00:00+00:00"},
        ]
        with mock.patch.object(check, "SUBSCRIBERS_FILE", subs), \
             mock.patch.object(check, "SENT_FILE", sent), \
             mock.patch.object(check.rules, "evaluate", return_value=events), \
             mock.patch.object(check.deliver, "send") as msend, \
             mock.patch.object(check.deliver, "send_digest") as mdigest:
            self.assertEqual(check.main(), 0)
        return msend, mdigest, json.load(open(sent))

    def test_free_tier_sends_one_digest_not_per_event(self):
        msend, mdigest, sent = self._run_check_with_subscriber("free")
        msend.assert_not_called()
        mdigest.assert_called_once()
        args = mdigest.call_args[0]
        self.assertEqual(args[0], "webhook")
        self.assertEqual(len(args[2]), 2)
        # both events recorded in cooldown state
        self.assertEqual(len(sent), 2)

    def test_pro_tier_sends_per_event_not_digest(self):
        msend, mdigest, sent = self._run_check_with_subscriber("pro")
        mdigest.assert_not_called()
        self.assertEqual(msend.call_count, 2)
        self.assertEqual(len(sent), 2)


class TestEndToEndDryRun(unittest.TestCase):
    def test_check_runs_with_no_subscribers(self):
        # check.main with empty subscribers: exercises load/evaluate/dedupe paths.
        import tempfile
        tmp = tempfile.mkdtemp()
        subs = os.path.join(tmp, "subscribers.json")
        sent = os.path.join(tmp, "sent.json")
        with open(subs, "w") as f:
            json.dump({"subscribers": []}, f)
        with mock.patch.object(check, "SUBSCRIBERS_FILE", subs), \
             mock.patch.object(check, "SENT_FILE", sent):
            self.assertEqual(check.main(), 0)
        self.assertTrue(os.path.exists(sent))

    def test_disabled_subscribers_are_skipped(self):
        # Safety default: without enabled=true, no delivery is attempted,
        # even when events fire.
        import tempfile
        tmp = tempfile.mkdtemp()
        subs = os.path.join(tmp, "subscribers.json")
        sent = os.path.join(tmp, "sent.json")
        with open(subs, "w") as f:
            json.dump({"subscribers": [{
                "id": "placeholder", "channel": "webhook",
                "destination": "https://example.com/hook",
                "tier": "pro", "rules": ["*"], "min_severity": "INFO",
                # "enabled" absent -> must be skipped
            }]}, f)
        with mock.patch.object(check, "SUBSCRIBERS_FILE", subs), \
             mock.patch.object(check, "SENT_FILE", sent), \
             mock.patch.object(check.deliver, "send") as msend:
            self.assertEqual(check.main(), 0)
            msend.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
