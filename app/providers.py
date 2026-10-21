"""Rate providers. Every provider returns {metal: (bank_buys, bank_sells)} per gram, RUB."""
import json, ssl, pathlib, datetime as dt, urllib.request, xml.etree.ElementTree as ET

METALS = {"gold": ("A98", "1"), "silver": ("A99", "2"), "platinum": ("A76", "3"), "palladium": ("A33", "4")}
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
      "Accept": "application/json, text/xml, */*", "Accept-Language": "ru-RU,ru;q=0.9",
      "Referer": "https://www.sberbank.ru/ru/person/investments/values/omsc"}
SBER_URLS = ["https://www.sberbank.ru/proxy/services/rates/public/v2/actual?rateType=PMR-3&isoCodes[]=A98&isoCodes[]=A99&isoCodes[]=A76&isoCodes[]=A33"]
_ISO = {v[0]: k for k, v in METALS.items()}
_CBR = {v[1]: k for k, v in METALS.items()}

# sberbank.ru is signed by the Russian Ministry of Digital Development CA ("Russian Trusted Root CA"),
# which Python does not trust out of the box -> every Sber request failed with CERTIFICATE_VERIFY_FAILED
# and the app silently fell back to the Bank of Russia (one price, zero spread). Trust it in addition
# to the normal system roots.
_CTX = ssl.create_default_context()
for _f in sorted((pathlib.Path(__file__).parent / "certs").glob("*.crt")):
    try:
        _CTX.load_verify_locations(str(_f))
    except Exception:
        pass

def _get(url, timeout=10):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout, context=_CTX).read()

def _num(v):
    try:
        return float(str(v).replace(",", ".").replace(" ", ""))
    except (TypeError, ValueError):
        return None

def _bs(d):
    """(buy, sell) from a dict whose keys contain 'buy' and 'sell' (rateBuy, buy, buyValue, ...)."""
    b = next((_num(v) for k, v in d.items() if "buy" in k.lower() and _num(v) is not None), None)
    s = next((_num(v) for k, v in d.items() if "sell" in k.lower() and _num(v) is not None), None)
    return (b, s) if b is not None and s is not None else None

def _first(o):
    """First buy/sell pair found anywhere inside o (first = smallest amount tier)."""
    if isinstance(o, dict):
        r = _bs(o)
        if r:
            return r
        o = list(o.values())
    if isinstance(o, list):
        for v in o:
            r = _first(v)
            if r:
                return r
    return None

def _walk(o, out):
    """Finds metal codes either as a field (currencyCode/isoCode/code) or as a dict key."""
    if isinstance(o, dict):
        code = next((o[k] for k in ("currencyCode", "isoCode", "isoCurrency", "code") if o.get(k) in _ISO), None)
        r = _bs(o) if code else None
        if code and r:
            out.setdefault(_ISO[code], r)
        for k, v in o.items():
            if k in _ISO and _ISO[k] not in out:
                r = _first(v)
                if r:
                    out[_ISO[k]] = r
            _walk(v, out)
    elif isinstance(o, list):
        for v in o:
            _walk(v, out)

def parse_sber(raw):
    out = {}
    _walk(json.loads(raw), out)
    return out

def parse_tiers(raw):
    """Sber v2: {"A98": {"rateList": [{rangeAmountBottom, rangeAmountUpper, rateBuy, rateSell}, ...]}}
    -> {metal: [(from_grams, to_grams, buy, sell), ...]} sorted by amount. Empty dict for other formats."""
    try:
        d = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
    except ValueError:
        return {}
    out = {}
    if isinstance(d, dict):
        for code, v in d.items():
            if code in _ISO and isinstance(v, dict) and isinstance(v.get("rateList"), list):
                try:
                    out[_ISO[code]] = sorted((float(r["rangeAmountBottom"]), float(r["rangeAmountUpper"]),
                                              float(r["rateBuy"]), float(r["rateSell"])) for r in v["rateList"])
                except (KeyError, TypeError, ValueError):
                    pass
    return out

def tier_rate(tiers, grams):
    """(buy, sell) that applies to an operation of `grams` grams."""
    for lo, hi, b, s in tiers:
        if lo <= grams <= hi:
            return b, s
    return tuple(tiers[-1][2:]) if grams > tiers[-1][1] else tuple(tiers[0][2:])

def parse_cbr(raw):
    """-> [(metal, unix_ts, buy, sell)]"""
    rows = []
    for r in ET.fromstring(raw).iter("Record"):
        m = _CBR.get(r.get("Code"))
        if m:
            ts = dt.datetime.strptime(r.get("Date"), "%d.%m.%Y").replace(hour=12).timestamp()
            f = lambda tag: float(r.find(tag).text.replace(",", "."))
            rows.append((m, ts, f("Buy"), f("Sell")))
    return rows

def parse_csv(raw):
    """Collector file: ts,metal,buy,sell -> [(metal, ts, buy, sell)]"""
    import csv, io
    return [(r["metal"], float(r["ts"]), float(r["buy"]), float(r["sell"]))
            for r in csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))) if r["metal"] in METALS]

def cbr_range(d1, d2):
    url = f"https://www.cbr.ru/scripts/xml_metall.asp?date_req1={d1:%d/%m/%Y}&date_req2={d2:%d/%m/%Y}"
    return parse_cbr(_get(url, 30))

def fetch_live(urls):
    """Try Sberbank endpoints first, then fall back to the Bank of Russia.
    -> (source, {metal: (buy, sell)}, {metal: amount tiers})"""
    for u in urls:
        try:
            raw = _get(u)
            r = parse_sber(raw)
            if r:
                tiers = parse_tiers(raw)
                for m, t in tiers.items():   # smallest-amount tier = the headline rate
                    r[m] = t[0][2:]
                return "sber", r, tiers
        except Exception:
            pass
    today = dt.date.today()
    latest = {}
    for m, ts, b, s in sorted(cbr_range(today - dt.timedelta(days=10), today + dt.timedelta(days=1))):
        latest[m] = (b, s)
    if not latest:
        raise RuntimeError("no data")
    return "cbr", latest, {}
