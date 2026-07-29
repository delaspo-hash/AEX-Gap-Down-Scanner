import yfinance as yf
import pandas as pd
from datetime import datetime, timezone, timedelta
import json
import os
import time

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
DATA_CACHE_FILE = "daily_data_cache.json"
BACKFILL_DONE_FLAG = "backfill_done.json"

# === TICKERLIJSTEN (stabiele bron) ===
def fetch_sp500_tickers():
    try:
        url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv"
        df = pd.read_csv(url)
        return [t.replace('.', '-') for t in df['Symbol'].tolist()]
    except:
        return ["AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "BRK-B", "JPM", "V",
                "JNJ", "WMT", "PG", "MA", "UNH", "HD", "BAC", "DIS", "ADBE", "CRM",
                "NFLX", "INTC", "CSCO", "VZ", "KO", "PEP", "MRK", "ABT", "WFC", "TMO"]

def fetch_nasdaq100_tickers():
    try:
        url = "https://raw.githubusercontent.com/arinb23/Nasdaq-100-Companies/main/nasdaq_100_tickers.csv"
        df = pd.read_csv(url)
        col = 'Symbol' if 'Symbol' in df.columns else 'Ticker'
        return [t.replace('.', '-') for t in df[col].tolist() if isinstance(t, str)]
    except:
        return ["NVDA", "AVGO", "AMD", "QCOM", "TXN", "AMAT", "MU", "ADI", "LRCX", "KLAC"]

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

# === BATCH DOWNLOAD (SUPERSNEL) ===
def download_all_tickers_data(tickers, period="10d"):
    """
    Download dagelijkse data voor een lijst tickers in één batch.
    Retourneert dict: {ticker: DataFrame} of leeg bij fout.
    """
    if not tickers:
        return {}
    try:
        print(f"Download batch van {len(tickers)} tickers...")
        data = yf.download(tickers, period=period, interval="1d", progress=False, group_by='ticker')
        # Als er maar 1 ticker is, retourneert yfinance een enkel DataFrame, dus normaliseren
        if len(tickers) == 1:
            data = {tickers[0]: data}
        else:
            # data is dict van DataFrame per ticker
            pass
        return data
    except Exception as e:
        print(f"Batch download mislukt: {e}")
        return {}

# === DAGCACHE VOOR RAUWE DATA ===
def load_daily_cache():
    """Laad de cache van vandaag (dict met ticker -> DataFrame in JSON niet mogelijk, dus slaan we de ruwe data over)"""
    # We kunnen beter een simpele globale variabele in memory gebruiken in Streamlit,
    # maar voor persistente cache tussen runs slaan we niets groots op.
    return None

# We gebruiken een module-level variabele voor data van deze sessie
_session_data_cache = None
_session_cache_date = None

def get_all_data_for_today():
    """
    Haal alle benodigde koersdata op (AEX+US) en cache het in het geheugen voor deze sessie.
    """
    global _session_data_cache, _session_cache_date
    today_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    if _session_data_cache is not None and _session_cache_date == today_str:
        return _session_data_cache

    us_tickers = get_all_us_tickers()
    all_tickers = AEX_TICKERS + us_tickers

    # Download in één batch
    raw_data = download_all_tickers_data(all_tickers, period="10d")
    _session_data_cache = raw_data
    _session_cache_date = today_str
    return raw_data

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

# === BACKFILL (eenmalig) ===
def backfill_history(start_date_str="2026-07-20"):
    if is_backfill_done():
        return
    end_date = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d')
    print(f"Backfill van {start_date_str} tot {end_date}...")
    us_tickers = get_all_us_tickers()
    all_tickers = AEX_TICKERS + us_tickers

    # Batch download voor backfill: 1 call per dag? Liever een range.
    # We downloaden van start_date tot end_date voor alle tickers tegelijk.
    try:
        data = yf.download(all_tickers, start=start_date_str, end=end_date, progress=False, group_by='ticker')
    except:
        data = {}

    history = load_history()
    existing_set = set()
    for e in history:
        existing_set.add((e['Ticker'], e['Datum']))
    new_entries = []

    if isinstance(data, dict):
        for ticker, df in data.items():
            if df.empty or len(df) < 2:
                continue
            for i in range(1, len(df)):
                current_day = df.index[i]
                prev_day = df.iloc[i-1]
                low_prev = float(prev_day['Low'].iloc[0]) if not isinstance(prev_day['Low'], float) else float(prev_day['Low'].iloc[0])
                open_curr = float(curr_day['Open'].iloc[0])
                close_curr = float(curr_day['Close'].iloc[0])
                # (rest van de code zoals eerder)
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
    if new_entries:
        history.extend(new_entries)
        save_history(history)
    mark_backfill_done()

# === DAGELIJKSE SCAN (supersnel) ===
def scan_today():
    history = load_history()
    if is_today_already_scanned():
        return history

    raw_data = get_all_data_for_today()
    new_entries = []

    for ticker, df in raw_data.items():
        if df is None or len(df) < 3:
            continue
        try:
            dag_n = df.iloc[-3]
            dag_n1 = df.iloc[-2]
            low_n = float(dag_n['Low'].iloc[0])
            open_n1 = float(dag_n1['Open'].iloc[0])
            close_n1 = float(dag_n1['Close'].iloc[0])

            if open_n1 < low_n and close_n1 < open_n1:
                gap_pct = ((low_n - open_n1) / low_n) * 100
                candle_pct = ((close_n1 - open_n1) / open_n1) * 100
                gap_date = dag_n1.name
                gap_date_str = gap_date.strftime('%Y-%m-%d') if hasattr(gap_date, 'strftime') else str(gap_date)[:10]
                exchange = "AEX" if ticker in AEX_TICKERS else "NYSE/NASDAQ"
                ticker_clean = ticker.replace('.AS', '')
                new_entries.append({
                    'Datum': gap_date_str,
                    'Ticker': ticker_clean,
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

# === HOOFDFUNCTIE ===
def check_bearish_gap():
    # Backfill alleen als nog niet gedaan (doet niets als flag bestaat)
    if not is_backfill_done():
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
    minute = now.minute
    weekday = now.weekday()

    if weekday >= 5:
        return {"AEX": "🔴 Weekend", "US": "🔴 Weekend"}

    # AEX 9:00-17:30
    if hour < 9:
        aex = "⏳ AEX nog niet open"
    elif hour < 17 or (hour == 17 and minute < 30):
        aex = "🟢 AEX open"
    else:
        aex = "🔴 AEX gesloten"

    # US 15:30-22:00 NL tijd
    if hour < 15 or (hour == 15 and minute < 30):
        us = "⏳ US nog niet open"
    elif hour < 22:
        us = "🟢 US open"
    else:
        us = "🔴 US gesloten"

    return {"AEX": aex, "US": us}

def get_snapshot_info():
    if is_today_already_scanned():
        return "📸 Scan van vandaag uitgevoerd"
    return "🔄 Scan wordt uitgevoerd..."