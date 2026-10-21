def calc(ops, bank_buy):
    """Weighted-average cost. ops: dicts with ts, kind('buy'|'sell'), grams, total (RUB)."""
    grams = cost = realized = 0.0
    for o in sorted(ops, key=lambda o: o["ts"]):
        if o["kind"] == "buy":
            grams += o["grams"]; cost += o["total"]
        elif grams > 0:
            g = min(o["grams"], grams)
            proceeds = o["total"] * g / o["grams"]
            avg = cost / grams
            realized += proceeds - avg * g
            cost -= avg * g; grams -= g
    value = grams * (bank_buy or 0)          # what the bank pays you right now
    unreal = value - cost
    return {"grams": grams, "invested": cost, "avg": cost / grams if grams else 0.0, "value": value,
            "unreal": unreal, "pct": unreal / cost * 100 if cost else 0.0,
            "realized": realized, "total": unreal + realized}
