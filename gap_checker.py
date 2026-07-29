import yfinance as yf
import pandas as pd
from datetime import datetime, timezone, timedelta
import json
import os
import time

AEX_TICKERS = [
    "ADYEN.AS", "AGN.AS", "AKZA.AS", "ASM.AS", "ASML.AS",
    "BESI.AS", "DSM.AS", "EXO.AS", "HEIA.AS", "HEIN.AS",
    "IMCD.AS", "INGA.AS", "KPN.AS", "MT.AS", "PHIA.AS",
    "PRX.AS", "RAND.AS", "REL.AS", "SHELL.AS", "TKWY.AS",
    "UNA.AS", "VPK.AS", "WKL.AS"
]

HISTORY_FILE = "history.json"
TICKER_CACHE = "ticker_cache.json"

# --- TICKERLIJSTEN ---
def fetch_sp500_tickers():
    try:
        url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv"
        df = pd.read_csv(url)
        return [t.replace('.', '-') for t in df['Symbol'].tolist()]
    except:
        return ["AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "BRK-B", "JPM", "V",
                "JNJ", "WMT", "PG", "MA", "UNH", "HD", "BAC", "DIS", "ADBE", "CRM"]

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

# --- DATA OPHALEN (10 dagen) ---
def download_all_tickers_data(tickers):
    """Batch download van de laatste 10 dagen voor een lijst tickers."""
    if not tickers:
        return {}
    try:
        print(f"Download batch van {len(tickers)} tickers...")
        data = yf.download(tickers, period="10d", interval="1d", progress=False, group_by='ticker')
        if len(tickers) == 1:
            data = {tickers[0]: data}
        return data
    except Exception as e:
        print(f"Batch mislukt: {e}")
        return {}

def get_all_data():
    """Haal data op voor AEX + US tickers (10 dagen)."""
    us = get_all_us_tickers()
    all_tickers = AEX_TICKERS + us
    return download_all_tickers_data(all_tickers)

# --- HISTORIE BEHEREN ---
def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE, 'r') as f:
        return json.load(f)

def save_history(history):
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)

# --- SCAN ALLE BESCHIKBARE DATA (laatste 10 dagen) ---
def scan_all():
    """Scan alle tickers over de laatste 10 dagen en voeg nieuwe signalen toe aan history."""
    history = load_history()
    existing = set()
    for e in history:
        existing.add((e['Ticker'], e['Datum']))

    raw_data = get_all_data()
    new_entries = []

    for ticker, df in raw_data.items():
        if df is None or len(df) < 2:
            continue
        try:
            # Zorg voor juiste kolomnamen (soms MultiIndex)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
            # Itereer over dagen
            for i in range(1, len(df)):
                prev = df.iloc[i-1]
                curr = df.iloc[i]
                low_prev = float(prev['Low'])
                open_curr = float(curr['Open'])
                close_curr = float(curr['Close'])

                if open_curr < low_prev and close_curr < open_curr:
                    gap_pct = ((low_prev - open_curr) / low_prev) * 100
                    candle_pct = ((close_curr - open_curr) / open_curr) * 100
                    date_str = df.index[i].strftime('%Y-%m-%d')
                    ticker_clean = ticker.replace('.AS', '')
                    if (ticker_clean, date_str) not in existing:
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
                        existing.add((ticker_clean, date_str))
        except Exception as e:
            print(f"Fout bij {ticker}: {e}")
            continue

    if new_entries:
        history.extend(new_entries)
        save_history(history)
        print(f"{len(new_entries)} nieuwe signalen toegevoegd.")
    else:
        print("Geen nieuwe signalen gevonden.")
    return history

# --- HOOFDFUNCTIE ---
def check_bearish_gap():
    history = scan_all()
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
    # US 15:30-22:00
    if hour < 15 or (hour == 15 and minute < 30):
        us = "⏳ US nog niet open"
    elif hour < 22:
        us = "🟢 US open"
    else:
        us = "🔴 US gesloten"
    return {"AEX": aex, "US": us}

def get_snapshot_info():
    return "📊 Altijd actuele data (laatste 10 dagen)"