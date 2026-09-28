#!/usr/bin/env python3
"""Delivery backends for dashboard alerts. Stdlib only.

Each backend exposes send(destination, event) -> bool.
Backends NEVER raise on delivery failure: they return False and log.

Secrets come from environment variables only — never hardcoded:
    TELEGRAM_BOT_TOKEN   bot token for the Telegram backend
    SMTP_HOST            SMTP server hostname
    SMTP_PORT            SMTP server port (default 587)
    SMTP_USER            SMTP username
    SMTP_PASS            SMTP password
    SMTP_FROM            From: address for alert emails
    SMTP_USE_TLS         "0" to disable STARTTLS (default enabled)
"""
import json
import logging
import os
import smtplib
import urllib.error
import urllib.request
from email.message import EmailMessage

log = logging.getLogger("alerts.deliver")

_HTTP_TIMEOUT = 10


def format_text(event: dict) -> str:
    """Human-readable one-message rendering of an alert event."""
    lines = [f"[{event.get('severity', '?')}] {event.get('title', 'alert')}"]
    if event.get("detail"):
        lines.append(event["detail"])
    metric, current, baseline = event.get("metric"), event.get("current"), event.get("baseline")
    if metric and current is not None and baseline is not None:
        lines.append(f"{metric}: {current} (baseline {baseline})")
    if event.get("ts"):
        lines.append(event["ts"])
    return "\n".join(lines)


def _http_post(url: str, payload: bytes, content_type: str = "application/json") -> bool:
    """POST payload to url. Returns True on 2xx, False otherwise. Never raises."""
    try:
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": content_type, "User-Agent": "solana-dashboard-alerts/1.0"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
            return 200 <= resp.status < 300
    except Exception as exc:  # never raise: network, DNS, TLS, HTTP errors
        log.warning("HTTP POST to %s failed: %s", url.split("?")[0], exc)
        return False


def send_telegram(destination: str, event: dict) -> bool:
    """Send via Telegram Bot API. destination = chat_id. Never raises."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        log.warning("telegram delivery skipped: TELEGRAM_BOT_TOKEN not set")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({"chat_id": destination, "text": format_text(event)}).encode("utf-8")
    try:
        return _http_post(url, payload)
    except Exception as exc:  # never raise
        log.warning("telegram delivery failed: %s", exc)
        return False


def send_email(destination: str, event: dict) -> bool:
    """Send via SMTP. destination = recipient email address. Never raises."""
    host = os.environ.get("SMTP_HOST")
    if not host:
        log.warning("email delivery skipped: SMTP_HOST not set")
        return False
    try:
        port = int(os.environ.get("SMTP_PORT", "587"))
        msg = EmailMessage()
        msg["From"] = os.environ.get("SMTP_FROM", os.environ.get("SMTP_USER", "alerts@localhost"))
        msg["To"] = destination
        msg["Subject"] = f"[solana-dashboard] [{event.get('severity', '?')}] {event.get('title', 'alert')}"
        msg.set_content(format_text(event))
        with smtplib.SMTP(host, port, timeout=_HTTP_TIMEOUT) as smtp:
            if os.environ.get("SMTP_USE_TLS", "1") != "0":
                smtp.starttls()
            user, password = os.environ.get("SMTP_USER"), os.environ.get("SMTP_PASS")
            if user and password:
                smtp.login(user, password)
            smtp.send_message(msg)
        return True
    except Exception as exc:  # never raise
        log.warning("email delivery to %s failed: %s", destination, exc)
        return False


def send_webhook(destination: str, event: dict) -> bool:
    """POST the event JSON to a subscriber URL. Never raises."""
    payload = json.dumps({"type": "solana_dashboard_alert", "event": event}).encode("utf-8")
    try:
        return _http_post(destination, payload)
    except Exception as exc:  # never raise
        log.warning("webhook delivery to %s failed: %s", destination, exc)
        return False


BACKENDS = {
    "telegram": send_telegram,
    "email": send_email,
    "webhook": send_webhook,
}


def format_digest(events: list) -> str:
    """Human-readable combined rendering of several alert events."""
    lines = [f"Solana dashboard digest — {len(events)} alert(s)"]
    for event in events:
        lines.append("")
        lines.append(format_text(event))
    return "\n".join(lines)


def _send_digest_telegram(destination: str, events: list) -> bool:
    """One Telegram message carrying the whole digest. Never raises."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        log.warning("telegram digest skipped: TELEGRAM_BOT_TOKEN not set")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({"chat_id": destination, "text": format_digest(events)}).encode("utf-8")
    try:
        return _http_post(url, payload)
    except Exception as exc:  # never raise
        log.warning("telegram digest failed: %s", exc)
        return False


def _send_digest_email(destination: str, events: list) -> bool:
    """One email carrying the whole digest. Never raises."""
    host = os.environ.get("SMTP_HOST")
    if not host:
        log.warning("email digest skipped: SMTP_HOST not set")
        return False
    try:
        port = int(os.environ.get("SMTP_PORT", "587"))
        msg = EmailMessage()
        msg["From"] = os.environ.get("SMTP_FROM", os.environ.get("SMTP_USER", "alerts@localhost"))
        msg["To"] = destination
        msg["Subject"] = f"[solana-dashboard] digest: {len(events)} alert(s)"
        msg.set_content(format_digest(events))
        with smtplib.SMTP(host, port, timeout=_HTTP_TIMEOUT) as smtp:
            if os.environ.get("SMTP_USE_TLS", "1") != "0":
                smtp.starttls()
            user, password = os.environ.get("SMTP_USER"), os.environ.get("SMTP_PASS")
            if user and password:
                smtp.login(user, password)
            smtp.send_message(msg)
        return True
    except Exception as exc:  # never raise
        log.warning("email digest to %s failed: %s", destination, exc)
        return False


def _send_digest_webhook(destination: str, events: list) -> bool:
    """POST the whole digest as one JSON payload. Never raises."""
    payload = json.dumps({"type": "solana_dashboard_digest", "events": events}).encode("utf-8")
    try:
        return _http_post(destination, payload)
    except Exception as exc:  # never raise
        log.warning("webhook digest to %s failed: %s", destination, exc)
        return False


DIGEST_BACKENDS = {
    "telegram": _send_digest_telegram,
    "email": _send_digest_email,
    "webhook": _send_digest_webhook,
}


def send_digest(channel: str, destination: str, events: list) -> bool:
    """Send several events as one combined digest message. Never raises."""
    if not events:
        return True
    backend = DIGEST_BACKENDS.get(channel)
    if backend is None:
        log.warning("unknown alert channel for digest: %r", channel)
        return False
    try:
        return bool(backend(destination, events))
    except Exception as exc:  # belt and braces: backends must never raise
        log.warning("digest backend %s raised unexpectedly: %s", channel, exc)
        return False


def send(channel: str, destination: str, event: dict) -> bool:
    """Dispatch to the backend for channel. Unknown channel -> False, never raises."""
    backend = BACKENDS.get(channel)
    if backend is None:
        log.warning("unknown alert channel: %r", channel)
        return False
    try:
        return bool(backend(destination, event))
    except Exception as exc:  # belt and braces: backends must never raise
        log.warning("backend %s raised unexpectedly: %s", channel, exc)
        return False
