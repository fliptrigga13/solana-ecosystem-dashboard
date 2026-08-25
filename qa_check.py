#!/usr/bin/env python3
"""Post-refresh sanity check for the Days 6-8 gap-fill additions."""
import json

s = json.load(open("data.json"))
news = s.get("news", {})
print("news items:", len(news.get("items", [])),
      "| feeds_ok:", news.get("feeds_ok"), "| errors:", news.get("errors"))
for i in news.get("items", [])[:4]:
    print("  -", i["date"], i["source"][:12].ljust(12), i["title"][:60])
n, d = s["network"], s["defi"]
print("est_daily_txns:", n.get("est_daily_txns"),
      "| avg_fee_per_txn:", d.get("avg_fee_per_txn_usd"))
assert len(news.get("items", [])) >= 4, "too few news items"
assert news.get("feeds_ok", 0) >= 1, "no feed succeeded"
assert isinstance(n.get("est_daily_txns"), int) and n["est_daily_txns"] > 0
assert isinstance(d.get("avg_fee_per_txn_usd"), float) and d["avg_fee_per_txn_usd"] > 0
# titles must not carry raw angle brackets (injection guard)
bad = [i for i in news["items"] if "<" in i["title"] or ">" in i["title"]]
assert not bad, f"unsanitized titles: {bad}"
print("QA-CHECK PASS")
