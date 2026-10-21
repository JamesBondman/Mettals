# Metals — Sberbank precious metals tracker

## Run (Windows 10/11)
1. Install Python 3.10+ once (python.org, tick "Add to PATH").
2. Double-click `install.bat`. It sets up a private environment, installs pywebview and puts a **Metals** shortcut on the desktop.
3. Start the app from the shortcut (no console window).

## Data
- `app/providers.py` tries the Sberbank endpoints listed in `config.json` (`sber_urls`, in %APPDATA%\MetalsTracker), then falls back to Bank of Russia rates.
- The header shows which source is active. The Sberbank endpoints were NOT verified from the build environment (no internet there). If the header says "Bank of Russia (fallback)", open sberbank.ru/ru/quotes/metalbullion, find the request in browser DevTools (Network) and put its URL into `sber_urls`. The parser accepts any JSON that holds currencyCode A98/A99/A76/A33 with rateBuy/rateSell.
- History: one year is back-filled from the Bank of Russia on first run; after that every poll is stored locally (SQLite).

## Languages
Copy `locales/en.txt` to `locales/xx.txt`, translate the values, set `lang.name` and `meta.intl`. It appears in Settings automatically.

## Tests
`python -m pytest tests`

## Notes
- "Bank buys" is the rate at which the bank buys from you, so "if sold now" uses it.
- A starting balance is just a purchase operation with your average price.
- Profit uses weighted-average cost. FIFO, price alerts and chart zoom are not implemented yet.
