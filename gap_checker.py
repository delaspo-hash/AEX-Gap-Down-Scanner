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

# === TICKERLIJSTEN (S&P 500 & Nasdaq-100) ===
def fetch_sp500_tickers():
    try:
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        tables = pd.read_html(url)
        return [t.replace('.', '-') for t in tables[0]['Symbol'].tolist()]
    except:
        return []

def fetch_nasdaq100_tickers():
    try:
        url = "https://en.wikipedia.org/wiki/Nasdaq-100"
        for table in pd.read_html(url):
            if 'Ticker' in table.columns or 'Symbol' in table.columns:
                col = 'Ticker' if 'Ticker' in table.columns else 'Symbol'
                return [t.replace('.', '-') for t in table[col].tolist() if isinstance(t, str)]
        return []
    except:
        return []

def get_all_us_tickers():
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

# === DATA OPHALEN VOOR PERIODE ===
def get_stock_data_range(ticker, start_date, end_date):
    """Haal dagelijkse data op tussen start en end (inclusief)"""
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

# === BACKFILL: VANAF EEN BEPAALDE DATUM TOT GISTEREN ===
def backfill_history(start_date_str="2026-07-20"):
    """
    Scan alle dagen van start_date tot gisteren op bearish gap signalen
    en voeg toe aan history.json (geen duplicaten).
    """
    if is_backfill_done():
        return  # al gedaan

    end_date = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d')
    print(f"Backfill van {start_date_str} tot {end_date} gestart...")

    us_tickers = get_all_us_tickers()
    all_tickers = AEX_TICKERS + us_tickers

    history = load_history()
    existing_set = set()  # voorkom duplicaten
    for entry in history:
        existing_set.add((entry['Ticker'], entry['Datum']))

    new_entries = []

    for ticker in all_tickers:
        try:
            # Haal data op van start_date min 5 dagen tot vandaag
            fetch_start = (datetime.strptime(start_date_str, '%Y-%m-%d') - timedelta(days=5)).strftime('%Y-%m-%d')
            data = get_stock_data_range(ticker, fetch_start, end_date)
            if data is None or len(data) < 2:
                continue

            # Loop over alle dagen vanaf start_date tot end_date
            start_dt = pd.to_datetime(start_date_str)
            end_dt = pd.to_datetime(end_date)
            for i in range(len(data)):
                current_day = data.index[i]
                if current_day < start_dt or current_day > end_dt:
                    continue
                if i == 0:  # geen vorige dag beschikbaar
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
        print(f"Backfill voltooid: {len(new_entries)} nieuwe signalen toegevoegd.")
    else:
        print("Backfill: geen nieuwe signalen gevonden.")

    mark_backfill_done()

# === DAGELIJKSE SCAN (alleen vandaag) ===
def scan_today():
    history = load_history()
    if is_today_already_scanned():
        return history

    us_tickers = get_all_us_tickers()
    all_tickers = AEX_TICKERS + us_tickers

    new_entries = []
    today_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    for ticker in all_tickers:
        try:
            data = get_stock_data_range(ticker, None, None)  # gebruik standaard period
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

# === MAIN FUNCTIE VOOR APP ===
def check_bearish_gap():
    # Altijd eerst backfill proberen (doet niets als al gedaan)
    backfill_history("2026-07-20")

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