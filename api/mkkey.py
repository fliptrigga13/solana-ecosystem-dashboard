#!/usr/bin/env python3
"""Issue, list, and revoke API keys.

The plaintext key is printed EXACTLY ONCE at creation. Only its SHA-256 hash
is stored (see auth.py). Deliver the printed key to the customer out of band
and do not paste it into tickets, docs, or chat logs.

Usage:
    python3 api/mkkey.py --name acme --tier pro
    python3 api/mkkey.py --name eval-acme --tier pro --expires-in-days 14
    python3 api/mkkey.py --list
    python3 api/mkkey.py --revoke acme
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import auth  # noqa: E402


def cmd_create(name: str, tier: str, expires_in_days=None) -> str:
    """Create a key; returns plaintext (caller prints it once)."""
    return auth.create_key(name, tier, expires_in_days=expires_in_days)


def cmd_list() -> list:
    """Return [(hash_prefix, name, tier, created, expires_at, revoked)] — no plaintext."""
    rows = []
    for kh, rec in sorted(auth.load_keys().items(),
                          key=lambda kv: kv[1].get("created", "")):
        rows.append((kh[:12], rec.get("name"), rec.get("tier"),
                     rec.get("created"), rec.get("expires_at"),
                     bool(rec.get("revoked"))))
    return rows


def cmd_revoke(name_or_hash: str) -> bool:
    return auth.revoke(name_or_hash)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Manage data API keys.")
    ap.add_argument("--name", help="customer/label name for the new key")
    ap.add_argument("--tier", choices=list(auth.TIERS),
                    help="tier for the new key")
    ap.add_argument("--expires-in-days", type=int, default=None,
                    help="time-box the key (eval keys); omit for no expiry")
    ap.add_argument("--list", action="store_true", help="list keys (hashes only)")
    ap.add_argument("--revoke", metavar="NAME_OR_HASH",
                    help="revoke a key by name or hash prefix")
    args = ap.parse_args(argv)

    if args.list:
        rows = cmd_list()
        if not rows:
            print("no keys issued yet")
        for hp, name, tier, created, expires_at, revoked in rows:
            print("%s  %-20s %-10s %s expires=%s %s" % (
                hp, name, tier, created, expires_at or "never",
                "REVOKED" if revoked else "active"))
        return 0
    if args.revoke:
        if cmd_revoke(args.revoke):
            print("revoked %s" % args.revoke)
            return 0
        print("no active key matched %r" % args.revoke)
        return 1
    if args.name and args.tier:
        try:
            plaintext = cmd_create(args.name, args.tier,
                                   expires_in_days=args.expires_in_days)
        except ValueError as e:
            print("error: %s" % e, file=sys.stderr)
            return 1
        print("API key for %r (%s) — shown ONCE, store it now:" % (args.name, args.tier))
        if args.expires_in_days:
            print("expires in %s days" % args.expires_in_days)
        print(plaintext)
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
