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
        while True:
            try:
                refresh()
            except Exception as exc:
                print(f"cycle error (continuing): {type(exc).__name__}: {exc}")
            time.sleep(interval)
    else:
        refresh()
