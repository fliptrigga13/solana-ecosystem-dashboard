#!/usr/bin/env python3
"""One-shot refresh: collect -> data.json -> report.md -> dashboard.html."""
import collector
import generate_report  # noqa: F401 (runs on import)
# generate_report reads data.json; ensure fresh collection first
snap = collector.collect_all()
json.dump(snap, open("data.json", "w"), indent=1)
print("collected; generating report + dashboard")
exec(open("generate_report.py").read().replace('if __name__', 'if False and __name__'))
