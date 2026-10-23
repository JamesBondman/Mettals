"""Runs on GitHub Actions: asks Sberbank for the current rates and appends them to data/rates.csv."""
import csv, sys, time, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app import providers

CSV = ROOT / "data" / "rates.csv"

def last_rows(path):
    last = {}
    if path.exists():
        for r in csv.DictReader(path.open(encoding="utf-8")):
            last[r["metal"]] = (float(r["buy"]), float(r["sell"]), float(r["ts"]))
    return last

def append(rates, path, now):
    """Writes a row when the rate changed, or at least once an hour."""
    last = last_rows(path)
    new = [(int(now), m, b, s) for m, (b, s) in rates.items()
           if m not in last or last[m][:2] != (b, s) or now - last[m][2] >= 1500]
    if new:
        path.parent.mkdir(exist_ok=True)
        fresh = not path.exists()
        with path.open("a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if fresh:
                w.writerow(["ts", "metal", "buy", "sell"])
            w.writerows(new)
    return len(new)

if __name__ == "__main__":
    err, rates = None, {}
    for _ in range(3):
        try:
            rates = providers.parse_sber(providers._get(providers.SBER_URLS[0], 20))
            if rates:
                break
        except Exception as e:
            err = e; time.sleep(5)
    if not rates:
        sys.exit(f"Sberbank request failed: {err}")
    print("new rows:", append(rates, CSV, time.time()))
