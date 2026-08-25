#!/usr/bin/env python3
"""One-shot refresh: collect -> data.json -> report.md -> dashboard.html."""
import autoupdate

if __name__ == "__main__":
    # single cycle; exits nonzero (loud) if collection or generation fails
    autoupdate.refresh()
