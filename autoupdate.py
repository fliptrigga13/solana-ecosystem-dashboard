#!/usr/bin/env python3
"""Auto-updating wrapper: collect -> anomalies -> report -> dashboard on a schedule.

Usage:
  python autoupdate.py              # one refresh cycle
  RADAR_INTERVAL_SEC controls nothing here; use OS scheduler (cron/Task Scheduler)
  pointing at this script, or run with --loop for a built-in hourly loop.
"""
import os
import subprocess
import sys
import time
import json
from datetime import datetime, timezone
import collector
import anomaly

MAX_CONSECUTIVE_FAILURES = 3  # loop mode: go loud (nonzero exit) after this many


def _maybe_autocommit() -> None:
    """WATCH_AUTOCOMMIT=1: commit+push fresh outputs after a clean refresh.

    Used by the local hourly watch (Task Scheduler) so GitHub Pages keeps
    updating even while Actions is unavailable; off by default for CI.
    """
    if os.environ.get("WATCH_AUTOCOMMIT") != "1":
        return
    subprocess.run(["git", "add", "data.json", "data-history.jsonl",
                    "index.html", "report.md"], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    msg = (f"data refresh {datetime.now(timezone.utc):%Y-%m-%dT%H:%MZ} "
           "(hourly watch)")
    r = subprocess.run(["git", "commit", "-m", msg], capture_output=True,
                       text=True)
    if r.returncode == 0:  # nonzero = nothing changed since last refresh
        subprocess.run(["git", "push", "origin", "main"], check=False,
                       capture_output=True)


def refresh() -> dict:
    snap = collector.collect_all()
    json.dump(snap, open("data.json", "w"), indent=1)

    anomaly_report = anomaly.run(snap)

    # regenerate human/machine outputs
    exec(open("generate_report.py").read())
    exec(open("generate_dashboard.py").read())

    if anomaly_report["anomalies_detected"]:
        for a in anomaly_report["anomalies"]:
            if a.get("metric") != "*":
                print(f"⚠️ ANOMALY [{a['severity']}] {a['metric']}: "
                      f"{a.get('direction')} {a.get('deviation_pct')}% "
                      f"(current {a['current']} vs baseline {a['baseline']})")
    print(f"refresh complete | history: {anomaly_report['history_size']} snapshots")
    _maybe_autocommit()
    return anomaly_report


if __name__ == "__main__":
    if "--loop" in sys.argv:
        interval = 3600
        try:
            interval = int(sys.argv[sys.argv.index("--loop") + 1])
        except (IndexError, ValueError):
            pass
        print(f"auto-update loop started ({interval}s interval). Ctrl+C to stop.")
        consecutive_failures = 0
        while True:
            try:
                refresh()
                consecutive_failures = 0
            except Exception as exc:
                consecutive_failures += 1
                print(f"CYCLE FAILURE ({consecutive_failures}/{MAX_CONSECUTIVE_FAILURES}): "
                      f"{type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    print("too many consecutive failures — exiting nonzero so the "
                          "scheduler/Actions run shows red", file=sys.stderr)
                    sys.exit(1)
            time.sleep(interval)
    else:
        try:
            refresh()
        except Exception as exc:
            print(f"REFRESH FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
            sys.exit(1)
