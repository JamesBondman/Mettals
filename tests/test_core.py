import sys, pathlib, json
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from app.portfolio import calc
from app import providers

def test_example_from_brief():
    ops = [{"ts": 1, "kind": "buy", "grams": 1, "total": 100}, {"ts": 2, "kind": "buy", "grams": 1, "total": 110}]
    r = calc(ops, 108)
    assert r["grams"] == 2 and r["invested"] == 210 and r["avg"] == 105
    assert r["value"] == 216 and r["unreal"] == 6

def test_sell_realizes_profit():
    ops = [{"ts": 1, "kind": "buy", "grams": 2, "total": 200}, {"ts": 2, "kind": "sell", "grams": 1, "total": 130}]
    r = calc(ops, 100)
    assert r["realized"] == 30 and r["grams"] == 1 and r["invested"] == 100

def test_parse_sber():
    raw = json.dumps({"x": [{"currencyCode": "A98", "rateBuy": 9000.5, "rateSell": 9900}]})
    assert providers.parse_sber(raw) == {"gold": (9000.5, 9900.0)}

def test_parse_cbr():
    xml = b'<?xml version="1.0" encoding="windows-1251"?><Metall><Record Date="16.10.2026" Code="1"><Buy>9000,50</Buy><Sell>9100,25</Sell></Record></Metall>'
    r = providers.parse_cbr(xml)
    assert r[0][0] == "gold" and r[0][2] == 9000.5 and r[0][3] == 9100.25

def test_parse_sber_code_as_key():
    raw = json.dumps({"A98": {"rateList": [{"rangeAmountLower": 0, "rateBuy": 1000.5, "rateSell": 1100}, {"rateBuy": 1, "rateSell": 2}]},
                      "A33": [{"buy": "500,5", "sell": "550"}]})
    assert providers.parse_sber(raw) == {"gold": (1000.5, 1100.0), "palladium": (500.5, 550.0)}

def test_parse_sber_v2_tiers():
    # real response shape from /rates/public/v2/actual?rateType=PMR-3 (17.10.2026)
    raw = json.dumps({"A98": {"startDateTime": 1792229235000, "lotSize": 1, "rateList": [
        {"rangeAmountBottom": 0, "rangeAmountUpper": 2.99999999, "rateSell": 11541, "rateBuy": 10596, "symbolBuy": "DOWN"},
        {"rangeAmountBottom": 3, "rangeAmountUpper": 9999999999.99, "rateSell": 11530, "rateBuy": 10596, "symbolBuy": "DOWN"}]}})
    assert providers.parse_sber(raw) == {"gold": (10596.0, 11541.0)}
    t = providers.parse_tiers(raw)["gold"]
    assert providers.tier_rate(t, 1) == (10596.0, 11541.0)
    assert providers.tier_rate(t, 6.3) == (10596.0, 11530.0)

def test_sber_tls_trusts_russian_ca():
    assert any("Russian Trusted Root CA" in str(c.get("subject")) for c in providers._CTX.get_ca_certs())


def test_collector_and_csv_roundtrip(tmp_path):
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "collector"))
    import collect
    f = tmp_path / "r.csv"
    assert collect.append({"gold": (10.0, 11.0)}, f, 1000) == 1
    assert collect.append({"gold": (10.0, 11.0)}, f, 1100) == 0       # unchanged, too soon
    assert collect.append({"gold": (10.5, 11.0)}, f, 1200) == 1       # changed
    assert collect.append({"gold": (10.5, 11.0)}, f, 5000) == 1       # hourly heartbeat
    rows = providers.parse_csv(f.read_bytes())
    assert [r[:2] for r in rows] == [("gold", 1000.0), ("gold", 1200.0), ("gold", 5000.0)]
