"""Tests for the anomaly alert (worker/alerts.py). No network, no keys.

Run from the repo root:  python3 -m unittest discover -s worker/tests -t . -v
"""
import contextlib
import io
import unittest
from datetime import date, timedelta

from worker import alerts

START = date(2026, 7, 1)


def history(leads, spend=40.0, channel="meta", start=START):
    """Fact rows, one per day, from a list of daily lead counts."""
    return [{"analysis_date": (start + timedelta(days=i)).isoformat(), "channel": channel,
             "spend_usd": str(spend), "reported_leads": str(n)} for i, n in enumerate(leads)]


class AnomalyRule(unittest.TestCase):
    def test_fires_on_a_week_of_zero_leads_after_a_normal_month(self):
        # Like Meta, Aug 4-10 2026: about 2 leads a day, then 7 days of spend with 0 leads.
        rows = history([2] * 28 + [0] * 7 + [3] * 5)
        [a] = alerts.anomalies(rows, since=START)
        self.assertEqual((a.channel, a.start, a.end, a.days), ("meta", date(2026, 7, 29), date(2026, 8, 4), 7))
        self.assertEqual(a.spend, 280.0)
        self.assertAlmostEqual(a.expected, 14.0)

    def test_single_zero_days_never_fire(self):
        self.assertEqual(alerts.anomalies(history([2, 0] * 30), since=START), [])

    def test_two_zero_days_is_too_short(self):
        self.assertEqual(alerts.anomalies(history([3] * 28 + [0, 0] + [3] * 5), since=START), [])

    def test_quiet_channel_does_not_fire(self):
        # 1 lead a day: 3 zero days expects only 3 leads, a normal quiet stretch.
        self.assertEqual(alerts.anomalies(history([1] * 28 + [0] * 3 + [1] * 3), since=START), [])

    def test_no_spend_is_not_an_anomaly(self):
        # A paused campaign: no spend and no leads is expected, not an alert.
        rows = history([2] * 28) + history([0] * 7, spend=0, start=START + timedelta(days=28))
        self.assertEqual(alerts.anomalies(rows, since=START), [])

    def test_streak_still_running_at_the_end_fires(self):
        [a] = alerts.anomalies(history([3] * 28 + [0] * 4), since=START)
        self.assertEqual(a.days, 4)

    def test_free_channels_are_ignored(self):
        self.assertEqual(alerts.anomalies(history([3] * 28 + [0] * 7, channel="gbp"), since=START), [])

    def test_rows_for_one_day_are_summed_first(self):
        # Two campaigns on the same day: one with 0 leads doesn't make the day zero.
        rows = history([2] * 35) + history([0] * 35, start=START)
        self.assertEqual(alerts.anomalies(rows, since=START), [])

    def test_only_recent_streaks_by_default(self):
        old = history([2] * 28 + [0] * 7 + [2] * 30)
        self.assertEqual(alerts.anomalies(old), [])
        self.assertEqual(len(alerts.anomalies(old, since=START)), 1)


class Alerting(unittest.TestCase):
    def test_key_is_stable_while_a_streak_grows(self):
        a = alerts.anomalies(history([3] * 28 + [0] * 4), since=START)[0]
        b = alerts.anomalies(history([3] * 28 + [0] * 6), since=START)[0]
        self.assertEqual(a.key, b.key)

    def test_issue_body_has_totals_and_the_key_only(self):
        a = alerts.Anomaly("meta", date(2026, 8, 4), date(2026, 8, 10), 291.15, 16.2)
        text = alerts.body(a)
        self.assertIn("$291.15", text)
        self.assertIn("<!-- anomaly:meta:2026-08-04 -->", text)
        self.assertEqual(a.title(), "Anomaly: Meta reported 0 leads for 7 days (2026-08-04 to 2026-08-10) "
                                    "while spending $291.15")

    def test_notify_opens_each_anomaly_once(self):
        a = alerts.Anomaly("meta", date(2026, 8, 4), date(2026, 8, 10), 291.15, 16.2)
        b = alerts.Anomaly("meta", date(2026, 10, 4), date(2026, 10, 8), 234.94, 11.2)
        sent = []

        def fake_send(url, headers, body=None, method="GET"):
            sent.append((method, body))
            if method == "GET":  # one issue already exists for the August streak
                return [{"number": 80, "body": alerts.body(a)}], {}
            return {"number": 81}, {}

        real, alerts.send = alerts.send, fake_send
        try:
            with contextlib.redirect_stdout(io.StringIO()):  # keep fake "opened issue" lines out of CI logs
                self.assertEqual(alerts.notify([a, b], "owner/repo", "token"), [81])
        finally:
            alerts.send = real
        posts = [body for method, body in sent if method == "POST"]
        self.assertEqual([p["title"] for p in posts], [b.title()])


if __name__ == "__main__":
    unittest.main()
