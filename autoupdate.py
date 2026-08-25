#!/usr/bin/env python3
"""Auto-updating wrapper: collect -> anomalies -> report -> dashboard on a schedule.

Usage:
  python autoupdate.py              # one refresh cycle
  RADAR_INTERVAL_SEC controls nothing here; use OS scheduler (cron/Task Scheduler)
  pointing at this script, or run with --loop for a built-in hourly loop.
"""
import sys
import time
import json
import collector
import anomaly

MAX_CONSECUTIVE_FAILURES = 3  # loop mode: go loud (nonzero exit) after this many


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
