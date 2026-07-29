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
BACKFILL_DONE_FLAG = "backfill_done.json"

# === BETERE TICKERLIJSTEN (stabiele bronnen + fallback) ===
def fetch_sp500_tickers():
    """Haal S&P 500 tickers van GitHub CSV (altijd beschikbaar)"""
    try:
        url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv"
        df = pd.read_csv(url)
        tickers = df['Symbol'].tolist()
        return [t.replace('.', '-') for t in tickers]
    except:
        # Fallback: 30 grootste S&P 500 bedrijven
        return ["AAPL", "MSFT", "AMZN", "GOOGL", "GOOG", "META", "TSLA", "BRK-B", "JPM", "V",
                "JNJ", "WMT", "PG", "MA", "UNH", "HD", "BAC", "DIS", "ADBE", "CRM",
                "NFLX", "INTC", "CSCO", "VZ", "KO", "PEP", "MRK", "ABT", "WFC", "TMO"]

def fetch_nasdaq100_tickers():
    """Haal Nasdaq-100 tickers van GitHub CSV"""
    try:
        url = "https://raw.githubusercontent.com/arinb23/Nasdaq-100-Companies/main/nasdaq_100_tickers.csv"
        df = pd.read_csv(url)
        col = 'Symbol' if 'Symbol' in df.columns else 'Ticker'
        tickers = df[col].tolist()
        return [t.replace('.', '-') for t in tickers if isinstance(t, str)]
    except:
        # Fallback: 30 grootste Nasdaq-100 bedrijven
        return ["NVDA", "AVGO", "AMD", "QCOM", "TXN", "AMAT", "MU", "ADI", "LRCX", "KLAC",
                "MRNA", "GILD", "REGN", "VRTX", "BIIB", "ILMN", "ADP", "CTAS", "ROST", "MAR"]

def get_all_us_tickers():
    """S&P500 + Nasdaq-100, gecached voor vandaag"""
    cache = {}
    if os.path.exists(TICKER_CACHE):
        with open(TICKER_CACHE, 'r') as f:
            cache = json.load(f)
        if cache.get('date') == datetime.now(timezone.utc).strftime('%Y-%m-%d'):
            return cache['tickers']

    sp500 = fetch_sp500_tickers()
    nasdaq100 = fetch_nasdaq100_tickers()
    all_us = list(set(sp500 + nasdaq100))
    with open(TICKER_CACHE, 'w') as f:
        json.dump({'date': datetime.now(timezone.utc).strftime('%Y-%m-%d'), 'tickers': all_us}, f)
    return all_us

# === DATA OPHALEN ===
def get_stock_data(ticker):
    """Haal 10 dagen koersdata op (voor dagelijkse scan)"""
    try:
        data = yf.download(ticker, period="10d", interval="1d", progress=False)
        if len(data) < 3:
            return None
        return data
    except:
        return None

def get_stock_data_range(ticker, start_date, end_date):
    """Haal data op tussen twee datums (voor backfill)"""
    try:
        data = yf.download(ticker, start=start_date, end=end_date, progress=False)
        if data.empty or len(data) < 2:
            return None
        return data
    except:
        return None

# === HISTORIE BEHEREN ===
def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE, 'r') as f:
        return json.load(f)

def save_history(history):
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)

def is_today_already_scanned():
    if not os.path.exists(TODAY_FLAG):
        return False
    with open(TODAY_FLAG, 'r') as f:
        data = json.load(f)
    return data.get('date') == datetime.now(timezone.utc).strftime('%Y-%m-%d')

def mark_today_scanned():
    with open(TODAY_FLAG, 'w') as f:
        json.dump({'date': datetime.now(timezone.utc).strftime('%Y-%m-%d')}, f)

def is_backfill_done():
    if not os.path.exists(BACKFILL_DONE_FLAG):
        return False
    with open(BACKFILL_DONE_FLAG, 'r') as f:
        data = json.load(f)
    return data.get('done', False)

def mark_backfill_done():
    with open(BACKFILL_DONE_FLAG, 'w') as f:
        json.dump({'done': True}, f)

# === BACKFILL ===
def backfill_history(start_date_str="2026-07-20"):
    if is_backfill_done():
        return

    end_date = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d')
    print(f"Backfill van {start_date_str} tot {end_date} gestart...")

    us_tickers = get_all_us_tickers()
    all_tickers = AEX_TICKERS + us_tickers

    history = load_history()
    existing_set = set()
    for entry in history:
        existing_set.add((entry['Ticker'], entry['Datum']))

    new_entries = []

    for ticker in all_tickers:
        try:
            fetch_start = (datetime.strptime(start_date_str, '%Y-%m-%d') - timedelta(days=5)).strftime('%Y-%m-%d')
            data = get_stock_data_range(ticker, fetch_start, end_date)
            if data is None or len(data) < 2:
                continue

            start_dt = pd.to_datetime(start_date_str)
            end_dt = pd.to_datetime(end_date)
            for i in range(1, len(data)):
                current_day = data.index[i]
                if current_day < start_dt or current_day > end_dt:
                    continue

                prev_day = data.iloc[i-1]
                curr_day = data.iloc[i]

                low_prev = float(prev_day['Low'].iloc[0])
                open_curr = float(curr_day['Open'].iloc[0])
                close_curr = float(curr_day['Close'].iloc[0])

                if open_curr < low_prev and close_curr < open_curr:
                    gap_pct = ((low_prev - open_curr) / low_prev) * 100
                    candle_pct = ((close_curr - open_curr) / open_curr) * 100
                    date_str = current_day.strftime('%Y-%m-%d')
                    ticker_clean = ticker.replace('.AS', '')

                    if (ticker_clean, date_str) not in existing_set:
                        exchange = "AEX" if ticker in AEX_TICKERS else "NYSE/NASDAQ"
                        new_entries.append({
                            'Datum': date_str,
                            'Ticker': ticker_clean,
                            'Exchange': exchange,
                            'Dag N Low': round(low_prev, 2),
                            'N+1 Open': round(open_curr, 2),
                            'N+1 Close': round(close_curr, 2),
                            'Gap %': round(gap_pct, 2),
                            'Candle %': round(candle_pct, 2)
                        })
                        existing_set.add((ticker_clean, date_str))
        except:
            continue

    if new_entries:
        history.extend(new_entries)
        save_history(history)
        print(f"Backfill voltooid: {len(new_entries)} signalen toegevoegd.")
    else:
        print("Backfill: geen nieuwe signalen gevonden.")

    mark_backfill_done()

# === DAGELIJKSE SCAN ===
def scan_today():
    history = load_history()
    if is_today_already_scanned():
        return history

    us_tickers = get_all_us_tickers()
    all_tickers = AEX_TICKERS + us_tickers

    new_entries = []

    for ticker in all_tickers:
        try:
            data = get_stock_data(ticker)  # gebruikt period="10d"
            if data is None or len(data) < 3:
                continue

            dag_n = data.iloc[-3]
            dag_n1 = data.iloc[-2]

            low_n = float(dag_n['Low'].iloc[0])
            open_n1 = float(dag_n1['Open'].iloc[0])
            close_n1 = float(dag_n1['Close'].iloc[0])

            if open_n1 < low_n and close_n1 < open_n1:
                gap_pct = ((low_n - open_n1) / low_n) * 100
                candle_pct = ((close_n1 - open_n1) / open_n1) * 100
                gap_date = dag_n1.name
                gap_date_str = gap_date.strftime('%Y-%m-%d') if hasattr(gap_date, 'strftime') else str(gap_date)[:10]
                exchange = "AEX" if ticker in AEX_TICKERS else "NYSE/NASDAQ"
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

# === HOOFDFUNCTIE VOOR APP ===
def check_bearish_gap():
    backfill_history("2026-07-20")  # doet niets als al gedaan
    history = scan_today()
    if history:
        df = pd.DataFrame(history)
        df = df.sort_values(['Datum', 'Gap %'], ascending=[False, False])
    else:
        df = pd.DataFrame()
    snapshot_time = (datetime.now(timezone.utc) + timedelta(hours=2)).strftime('%H:%M')
    return df, snapshot_time

def get_market_status():
    """Aparte status voor AEX en US beurzen (NL tijd)"""
    now = datetime.now(timezone.utc) + timedelta(hours=2)
    hour = now.hour
    weekday = now.weekday()

    if weekday >= 5:
        return {"AEX": "🔴 Weekend", "US": "🔴 Weekend"}

    # AEX: 9:00 - 17:30
    if hour < 9:
        aex = "⏳ AEX nog niet open"
    elif hour < 17:
        aex = "🟢 AEX open"
    else:
        aex = "🔴 AEX gesloten"

    # US: 15:30 - 22:00 (gebruik float voor half uur)
    if hour < 15 or (hour == 15 and datetime.now().minute < 30):
        us = "⏳ US nog niet open"
    elif hour < 22:
        us = "🟢 US open"
    else:
        us = "🔴 US gesloten"

    return {"AEX": aex, "US": us}

def get_snapshot_info():
    if is_today_already_scanned():
        return "📸 Scan van vandaag uitgevoerd"
    return "🔄 Nog niet gescand vandaag"