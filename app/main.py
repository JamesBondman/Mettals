import json, os, sys, time, threading, datetime as dt, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app import providers, portfolio
from app.store import Store

DATA = pathlib.Path(os.getenv("APPDATA", ROOT)) / "MetalsTracker"; DATA.mkdir(exist_ok=True)
CFG_FILE = DATA / "config.json"
SBER_URLS = ["https://www.sberbank.ru/proxy/services/rates/public/v2/actual?rateType=PMR-3&isoCodes[]=A98&isoCodes[]=A99&isoCodes[]=A76&isoCodes[]=A33"]
DEFAULTS = {"lang": "en", "interval": 60, "fx": True}
TITLE = "Metals Tracker"

def read_locale(path):
    d = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1); d[k.strip()] = v.strip()
    return d

class Api:
    def __init__(self):
        self._db = Store(DATA / "rates.db")
        self._cfg = dict(DEFAULTS)
        if CFG_FILE.exists():
            self._cfg.update(json.loads(CFG_FILE.read_text(encoding="utf-8")))
        self._cfg.pop("sber_urls", None)  # old versions saved outdated URLs here
        self._status = {"ok": False, "src": "", "ts": 0}
        self._tiers = {}
        self._wake = threading.Event(); self._imp = 0
        threading.Thread(target=self._poll, daemon=True).start()

    def _poll(self):
        if not self._db.has_cbr():
            try:
                end = dt.date.today()
                for m, ts, b, s in providers.cbr_range(end - dt.timedelta(days=370), end):
                    self._db.add_rate(m, ts, b, s, "cbr")
            except Exception:
                pass
        while True:
            if time.time() - self._imp > 600:
                self._import_history(); self._imp = time.time()
            try:
                src, rates, self._tiers = providers.fetch_live(([self._cfg["rates_url"]] if self._cfg.get("rates_url") else []) + SBER_URLS)
                now = time.time()
                for m, (b, s) in rates.items():
                    self._db.add_rate(m, now, b, s, src)
                self._status = {"ok": True, "src": src, "ts": now}
            except Exception:
                self._status = {**self._status, "ok": False}
            self._wake.wait(max(15, int(self._cfg["interval"]))); self._wake.clear()

    def _import_history(self):
        """Adds rows recorded by the GitHub collector while this computer was off."""
        url = self._cfg.get("history_url")
        if not url:
            return
        try:
            have = {(m, ts) for m, ts in self._db.q("select metal,ts from rates where src='gh'")}
            new = [(m, ts, b, s, "gh") for m, ts, b, s in providers.parse_csv(providers._get(url, 30)) if (m, ts) not in have]
            if new:
                self._db.add_many(new)
        except Exception:
            pass

    # ---- exposed to the UI ----
    def locales(self): return {p.stem: read_locale(p).get("lang.name", p.stem) for p in (ROOT / "locales").glob("*.txt")}
    def locale(self, code): return read_locale(ROOT / "locales" / f"{code}.txt")
    def config(self): return dict(self._cfg)
    def set_config(self, k, v):
        self._cfg[k] = v; CFG_FILE.write_text(json.dumps(self._cfg, indent=1), encoding="utf-8")
    def set_rates_url(self, url):
        self.set_config("rates_url", url.strip()); self._wake.set()
    def set_history_url(self, url):
        self.set_config("history_url", url.strip()); self._imp = 0; self._wake.set()
    def snapshot(self):
        rates = {}
        for m in providers.METALS:
            r = self._db.latest(m)
            if r and self._status.get("src") == "sber" and self._tiers.get(m):
                r["tiers"] = self._tiers[m]   # amount tiers, used by "at current price"
            rates[m] = r
        return {"status": self._status, "rates": rates}
    def history(self, m, a, b): return self._db.history(m, a, b)
    def ops(self, m): return self._db.ops(m)
    def add_op(self, m, kind, grams, price, ts):
        self._db.q("insert into ops(metal,ts,kind,grams,total) values(?,?,?,?,?)", (m, ts, kind, grams, grams * price))
    def del_op(self, i): self._db.q("delete from ops where id=?", (i,))
    def portfolio(self, m):
        r = self._db.latest(m)
        return portfolio.calc(self._db.ops(m), r["buy"] if r else 0)
    def overview(self):
        ms = {m: self.portfolio(m) for m in providers.METALS}
        return {"metals": ms, **{k: sum(p[k] for p in ms.values()) for k in ("value", "invested", "unreal", "realized")}}
    def export_ops(self):
        return json.dumps({m: self._db.ops(m) for m in providers.METALS})
    def import_ops(self, text):
        for m, lst in json.loads(text).items():
            for o in lst:
                self._db.q("insert into ops(metal,ts,kind,grams,total) values(?,?,?,?,?)", (m, o["ts"], o["kind"], o["grams"], o["total"]))

def apply_icon():
    """Sets the taskbar/title icon straight through the Windows API (pythonw would show the Python logo)."""
    try:
        import ctypes
        from ctypes import c_void_p, c_uint, c_size_t, c_int, c_wchar_p
        u = ctypes.windll.user32
        u.FindWindowW.restype = c_void_p; u.FindWindowW.argtypes = [c_wchar_p, c_wchar_p]
        u.LoadImageW.restype = c_void_p; u.LoadImageW.argtypes = [c_void_p, c_wchar_p, c_uint, c_int, c_int, c_uint]
        u.SendMessageW.argtypes = [c_void_p, c_uint, c_size_t, c_void_p]
        h = None
        for _ in range(60):
            h = u.FindWindowW(None, TITLE)
            if h: break
            time.sleep(0.25)
        if not h: return
        ico = str(ROOT / "assets" / "icon.ico")
        for size, which in ((32, 1), (16, 0)):  # WM_SETICON: 1 = big (taskbar), 0 = small (title bar)
            u.SendMessageW(h, 0x80, which, u.LoadImageW(None, ico, 1, size, size, 0x10))
    except Exception:
        pass

if __name__ == "__main__":
    import webview
    try:  # own taskbar identity instead of grouping under Python
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("MetalsTracker.App")
    except Exception:
        pass
    win = webview.create_window(TITLE, str(ROOT / "ui" / "index.html"), js_api=Api(),
                                width=1180, height=760, min_size=(1000, 650), background_color="#0d0f12")
    threading.Thread(target=apply_icon, daemon=True).start()
    webview.start()
