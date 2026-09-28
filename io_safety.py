#!/usr/bin/env python3
"""Crash/concurrency safety for the refresh pipeline.

- refresh_lock: portable exclusive lock for one whole refresh cycle.
  Uses atomic lockfile creation (O_CREAT|O_EXCL) plus a PID staleness
  check, so it works on Windows (Task Scheduler) and Unix without
  fcntl/msvcrt. A second concurrent run fails loudly instead of
  interleaving outputs.
- atomic_write_text / atomic_write_json: write to a temp file in the
  same directory, then os.replace (atomic on both platforms), so a
  killed run never leaves a truncated data.json / report.md / index.html.
"""
import json
import os
import time

LOCKFILE = "refresh.lock"
# A refresh never legitimately runs this long; older locks are stale.
_STALE_AFTER_SEC = 3 * 3600


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except AttributeError:
        # Platform without kill(pid, 0) semantics: fall back to the
        # mtime heuristic in _lock_is_stale.
        return True
    except OSError:
        return False
    except ValueError:
        return False
    return True


def _lock_is_stale(path: str) -> bool:
    try:
        with open(path, encoding="utf-8") as f:
            pid = int(f.read().strip())
    except (OSError, ValueError):
        return True  # unreadable lockfile: not a live holder
    if not _pid_alive(pid):
        return True
    try:
        age = time.time() - os.path.getmtime(path)
    except OSError:
        return True
    return age > _STALE_AFTER_SEC


class refresh_lock:
    """Non-blocking exclusive lock for one refresh cycle."""

    def __init__(self, path: str = LOCKFILE):
        self.path = path
        self._fd = None

    def __enter__(self):
        try:
            self._fd = os.open(self.path,
                               os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if _lock_is_stale(self.path):
                try:
                    os.unlink(self.path)
                except OSError:
                    pass
                self._fd = os.open(self.path,
                                   os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            else:
                raise RuntimeError(
                    "refusing to run: another refresh holds "
                    f"{self.path}") from None
        with os.fdopen(self._fd, "w") as f:
            f.write(str(os.getpid()))
        self._fd = None
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            os.unlink(self.path)
        except OSError:
            pass
        return False


def atomic_write_text(path: str, text: str,
                      encoding: str = "utf-8") -> None:
    """Write text atomically: temp file in the same directory + rename."""
    tmp = f"{path}.tmp.{os.getpid()}"
    with open(tmp, "w", encoding=encoding) as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def atomic_write_json(path: str, obj, indent: int = 1) -> None:
    atomic_write_text(path, json.dumps(obj, indent=indent,
                                      ensure_ascii=False) + "\n")
