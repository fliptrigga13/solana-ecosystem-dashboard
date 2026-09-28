#!/usr/bin/env python3
"""In-memory per-key sliding-window rate limiter with periodic persistence.

Counters live in memory for speed and are flushed to usage.json periodically
(and on clean shutdown) so a restart does not reset abuse counters.
Format: { "<key_hash>": [<unix ts>, ...] } — hashes only, never plaintext keys.
"""
import atexit
import json
import os
import time
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
API_DIR = os.environ.get("API_DIR", HERE)
USAGE_FILE = os.path.join(API_DIR, "usage.json")

WINDOW_SECONDS = 86400  # rolling 24h


class RateLimiter:
    def __init__(self, usage_file: str = USAGE_FILE, save_every_s: int = 60):
        self.usage_file = usage_file
        self.save_every_s = save_every_s
        self._last_save = 0.0
        self.hits: dict = {}
        self._load()
        try:
            atexit.register(self.save)
        except Exception:
            pass

    def _load(self) -> None:
        try:
            with open(self.usage_file, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                for kh, stamps in data.items():
                    if isinstance(stamps, list):
                        self.hits[kh] = deque(float(s) for s in stamps)
        except (OSError, ValueError):
            pass

    def save(self) -> None:
        try:
            d = os.path.dirname(self.usage_file)
            if d:
                os.makedirs(d, exist_ok=True)
            tmp = self.usage_file + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({kh: list(dq) for kh, dq in self.hits.items()}, f)
            os.replace(tmp, self.usage_file)
        except OSError:
            pass

    def _maybe_save(self, now: float) -> None:
        if now - self._last_save >= self.save_every_s:
            self._last_save = now
            self.save()

    def check(self, key_hash: str, quota: int, now: float = None):
        """Record a hit and report (allowed, remaining, retry_after_seconds).

        `quota` is max requests per rolling 24h window. `now` is injectable
        for tests.
        """
        now = time.time() if now is None else float(now)
        dq = self.hits.setdefault(key_hash, deque())
        cutoff = now - WINDOW_SECONDS
        while dq and dq[0] <= cutoff:
            dq.popleft()
        if len(dq) >= quota:
            retry_after = int(dq[0] + WINDOW_SECONDS - now) + 1
            self._maybe_save(now)
            return False, 0, max(retry_after, 1)
        dq.append(now)
        self._maybe_save(now)
        return True, quota - len(dq), 0
