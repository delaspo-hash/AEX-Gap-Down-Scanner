import yfinance as yf
import pandas as pd
from datetime import datetime, timezone, timedelta
import json
import os

# === CONSTANTEN ===
AEX_TICKERS = [
    "ADYEN.AS", "AGN.AS", "AKZA.AS", "ASM.AS", "ASML.AS",
    "BESI.AS", "DSM.AS", "EXO.AS", "HEIA.AS", "HEIN.AS",
    "IMCD.AS", "INGA.AS", "KPN.AS", "MT.AS", "PHIA.AS",
    "PRX.AS", "RAND.AS", "REL.AS", "SHELL.AS", "TKWY.AS",
    "UNA.AS", "VPK.AS", "WKL.AS"
]

HISTORY_FILE = "history.json"
TODAY_FLAG = "snapshot_done.json"
TICKER_CACHE = "ticker_cache.json"

# === TICKERLIJSTEN OPHALEN (met cache) ===
def fetch_sp500_tickers():
    """Haal S&P 500 tickers van Wikipedia"""
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    try:
        tables = pd.read_html(url)
        df = tables[0]
        tickers = df['Symbol'].tolist()
        return [t.replace('.', '-') for t in tickers]  # Yahoo gebruikt '-' ipv punt
    except:
        return []

def fetch_nasdaq100_tickers():
    """Haal Nasdaq-100 tickers van Wikipedia"""
    url = "https://en.wikipedia.org/wiki/Nasdaq-100"
    try:
        tables = pd.read_html(url)
        # De juiste tabel vinden (meestal de 4e of 3e)
        for table in tables:
            if 'Ticker' in table.columns or 'Symbol' in table.columns:
                col = 'Ticker' if 'Ticker' in table.columns else 'Symbol'
                tickers = table[col].tolist()
                return [t.replace('.', '-') for t in tickers if isinstance(t, str)]
        return []
    except:
        return []

def get_all_us_tickers():
    """Haal S&P500 + Nasdaq-100, gecached voor 1 dag"""
    cache = {}
    if os.path.exists(TICKER_CACHE):
        try:
            with open(TICKER_CACHE, 'r') as f:
                cache = json.load(f)
            if cache.get('date') == datetime.now(timezone.utc).strftime('%Y-%m-%d'):
                return cache['tickers']
        except:
            pass

    sp500 = fetch_sp500_tickers()
    nasdaq100 = fetch_nasdaq100_tickers()

    all_us = list(set(sp500 + nasdaq100))  # uniek
    # Cache opslaan
    cache = {
        'date': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
        'tickers': all_us
    }
    with open(TICKER_CACHE, 'w') as f:
        json.dump(cache, f)
    return all_us

# === DATA OPHALEN ===
def get_stock_data(ticker):
    try:
        data = yf.download(ticker, period="10d", interval="1d", progress=False)
        if len(data) < 3:
            return None
        return data
    except:
        return None

# === HISTORIE BEHEREN ===
def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

def save_history(history):
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)

def is_today_already_scanned():
    if not os.path.exists(TODAY_FLAG):
        return False
    try:
        with open(TODAY_FLAG, 'r') as f:
            data = json.load(f)
        return data.get('date') == datetime.now(timezone.utc).strftime('%Y-%m-%d')
    except:
        return False

def mark_today_scanned():
    with open(TODAY_FLAG, 'w') as f:
        json.dump({'date': datetime.now(timezone.utc).strftime('%Y-%m-%d')}, f)

# === SCAN ===
def scan_today():
    history = load_history()

    if is_today_already_scanned():
        return history

    # Bouw complete tickerlijst: AEX + US
    us_tickers = get_all_us_tickers()
    all_tickers = AEX_TICKERS + us_tickers

    new_entries = []
    for ticker in all_tickers:
        try:
            data = get_stock_data(ticker)
            if data is None or len(data) < 3:
                continue

            dag_n = data.iloc[-3]
            dag_n1 = data.iloc[-2]

            low_n = float(dag_n['Low'].iloc[0])
            open_n1 = float(dag_n1['Open'].iloc[0])
            close_n1 = float(dag_n1['Close'].iloc[0])

            gap_down = open_n1 < low_n
            bearish = close_n1 < open_n1

            if gap_down and bearish:
                gap_pct = ((low_n - open_n1) / low_n) * 100
                candle_pct = ((close_n1 - open_n1) / open_n1) * 100

                gap_date = dag_n1.name
                if hasattr(gap_date, 'strftime'):
                    gap_date_str = gap_date.strftime('%Y-%m-%d')
                else:
                    gap_date_str = str(gap_date)[:10]

                # Exchange bepalen
                if ticker in AEX_TICKERS:
                    exchange = "AEX"
                elif ticker in us_tickers:
                    # Simpele check: NYSE/NASDAQ onderscheiden is niet perfect,
                    # maar we kunnen kijken naar de oorspronkelijke lijst
                    exchange = "NYSE/NASDAQ"
                else:
                    exchange = "US"

                new_entries.append({
                    'Datum': gap_date_str,
                    'Ticker': ticker.replace('.AS', ''),
                    'Exchange': exchange,
                    'Dag N Low': round(low_n, 2),
                    'N+1 Open': round(open_n1, 2),
                    'N+1 Close': round(close_n1, 2),
                    'Gap %': round(gap_pct, 2),
                    'Candle %': round(candle_pct, 2)
                })
        except:
            continue

    if new_entries:
        history.extend(new_entries)
        save_history(history)

    mark_today_scanned()
    return history

def check_bearish_gap():
    history = scan_today()
    if history:
        df = pd.DataFrame(history)
        df = df.sort_values(['Datum', 'Gap %'], ascending=[False, False])
    else:
        df = pd.DataFrame()
    snapshot_time = (datetime.now(timezone.utc) + timedelta(hours=2)).strftime('%H:%M')
    return df, snapshot_time

def get_market_status():
    now = datetime.now(timezone.utc) + timedelta(hours=2)
    hour = now.hour
    weekday = now.weekday()
    if weekday >= 5:
        return "🔴 Weekend - Beurs gesloten"
    if hour < 9:
        return "⏳ Beurs nog niet open"
    elif hour < 17:
        return "🟢 Beurs is open"
    else:
        return "🔴 Beurs gesloten"

def get_snapshot_info():
    if is_today_already_scanned():
        return "📸 Scan van vandaag uitgevoerd"
    return "🔄 Nog niet gescand vandaag"