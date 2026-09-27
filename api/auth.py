#!/usr/bin/env python3
"""API key management for the Solana dashboard data API.

Keys are never stored in plaintext. Only SHA-256 hashes live in keys.json;
the plaintext key is shown to the operator exactly once at issuance time
(see mkkey.py) and must be delivered to the customer out of band.

Storage layout (keys.json):
    { "<sha256 hex>": {"name": str, "tier": "free|pro|enterprise",
                        "created": "<iso8601>", "revoked": bool} }
"""
import hashlib
import json
import os
import secrets
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
API_DIR = os.environ.get("API_DIR", HERE)
KEYS_FILE = os.path.join(API_DIR, "keys.json")

TIERS = ("free", "pro", "enterprise")

# Requests per rolling 24h window. None = unlimited.
TIER_QUOTAS = {
    "free": 60,
    "pro": 10000,
    "enterprise": None,
}

# Which routes each tier may call.
TIER_ENDPOINTS = {
    "free": {"/v1/snapshot", "/v1/metrics"},
    "pro": {"/v1/snapshot", "/v1/metrics", "/v1/history", "/v1/anomalies"},
    "enterprise": {"/v1/snapshot", "/v1/metrics", "/v1/history", "/v1/anomalies"},
}

KEY_PREFIX = "sk_"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def hash_key(plaintext: str) -> str:
    """SHA-256 hex digest of a plaintext API key."""
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def load_keys() -> dict:
    try:
        with open(KEYS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_keys(keys: dict) -> None:
    os.makedirs(API_DIR, exist_ok=True)
    tmp = KEYS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(keys, f, indent=2, sort_keys=True)
    os.replace(tmp, KEYS_FILE)


def create_key(name: str, tier: str) -> str:
    """Create a key for `name` at `tier`. Returns the PLAINTEXT key (once).

    Only the hash is persisted. Raises ValueError on bad tier or duplicate name.
    """
    if tier not in TIERS:
        raise ValueError("tier must be one of %s" % (TIERS,))
    keys = load_keys()
    for rec in keys.values():
        if rec.get("name") == name and not rec.get("revoked"):
            raise ValueError("an active key named %r already exists" % name)
    plaintext = KEY_PREFIX + secrets.token_urlsafe(32)
    keys[hash_key(plaintext)] = {
        "name": name,
        "tier": tier,
        "created": _now_iso(),
        "revoked": False,
    }
    _save_keys(keys)
    return plaintext


def find_by_name(name: str):
    """Return (key_hash, record) for an active key with this name, else None."""
    for kh, rec in load_keys().items():
        if rec.get("name") == name and not rec.get("revoked"):
            return kh, rec
    return None


def revoke(name_or_hash_prefix: str) -> bool:
    """Revoke by key name or by hash prefix. Returns True if something revoked."""
    keys = load_keys()
    changed = False
    for kh, rec in keys.items():
        if rec.get("revoked"):
            continue
        if rec.get("name") == name_or_hash_prefix or kh.startswith(name_or_hash_prefix):
            rec["revoked"] = True
            changed = True
    if changed:
        _save_keys(keys)
    return changed


def verify(plaintext: str):
    """Return the key record (including key_hash) for a plaintext key, else None.

    The record includes a 'revoked' flag; callers decide how to handle it.
    Never raises on malformed input.
    """
    if not isinstance(plaintext, str) or not plaintext:
        return None
    rec = load_keys().get(hash_key(plaintext))
    if rec is None:
        return None
    return dict(rec, key_hash=hash_key(plaintext))
