import yfinance as yf
import pandas as pd
from datetime import datetime, timezone, timedelta
import json
import os
import sys

# === CONSTANTEN ===
AEX_TICKERS = [
    "ADYEN.AS", "AGN.AS", "AKZA.AS", "ASM.AS", "ASML.AS",
    "BESI.AS", "DSM.AS", "EXO.AS", "HEIA.AS", "HEIN.AS",
    "IMCD.AS", "INGA.AS", "KPN.AS", "MT.AS", "PHIA.AS",
    "PRX.AS", "RAND.AS", "REL.AS", "SHELL.AS", "TKWY.AS",
    "UNA.AS", "VPK.AS", "WKL.AS"
]

HISTORY_FILE = "history.json"
TICKER_CACHE = "ticker_cache.json"

# === TICKERLIJSTEN ===
def fetch_sp500_tickers():
    try:
        url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv"
        df = pd.read_csv(url)
        return [t.replace('.', '-') for t in df['Symbol'].tolist()]
    except:
        return ["AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "BRK-B", "JPM", "V"]

def fetch_nasdaq100_tickers():
    try:
        url = "https://raw.githubusercontent.com/arinb23/Nasdaq-100-Companies/main/nasdaq_100_tickers.csv"
        df = pd.read_csv(url)
        col = 'Symbol' if 'Symbol' in df.columns else 'Ticker'
        return [t.replace('.', '-') for t in df[col].tolist() if isinstance(t, str)]
    except:
        return ["NVDA", "AVGO", "AMD", "QCOM", "TXN", "AMAT", "MU", "ADI"]

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

# === DATA OPHALEN (ROBUUST) ===
def download_data_for_tickers(tickers, period="10d"):
    """
    Download data voor een lijst tickers. Eerst batch, bij fout per ticker.
    Retourneert dict: {ticker: DataFrame}
    """
    if not tickers:
        return {}
    # Probeer batch
    try:
        print(f"Batch download van {len(tickers)} tickers...", flush=True)
        data = yf.download(tickers, period=period, interval="1d", progress=False, group_by='ticker')
        # Normaliseren
        if len(tickers) == 1:
            data = {tickers[0]: data}
        # Controleer of we data hebben
        if data and any(not df.empty for df in data.values()):
            print("Batch gelukt.", flush=True)
            return data
        else:
            print("Batch retourneerde lege data, val terug op per ticker.", flush=True)
    except Exception as e:
        print(f"Batch mislukt: {e}. Val terug op per ticker.", flush=True)

    # Fallback: één voor één
    data = {}
    for t in tickers:
        try:
            df = yf.download(t, period=period, interval="1d", progress=False)
            if not df.empty:
                data[t] = df
        except:
            continue
    print(f"Per-ticker download voltooid: {len(data)} tickers.", flush=True)
    return data

def get_all_data():
    us = get_all_us_tickers()
    all_tickers = AEX_TICKERS + us
    return download_data_for_tickers(all_tickers, period="10d")

# === HISTORIE BEHEREN ===
def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE, 'r') as f:
        return json.load(f)

def save_history(history):
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)

# === SCAN FUNCTIE (met logging) ===
def scan_all():
    history = load_history()
    existing = set()
    for e in history:
        existing.add((e['Ticker'], e['Datum']))

    raw_data = get_all_data()
    print(f"Aantal tickers met data: {len(raw_data)}", flush=True)

    new_entries = []
    skipped_empty = 0
    skipped_no_pattern = 0

    for ticker, df in raw_data.items():
        if df is None or len(df) < 2:
            skipped_empty += 1
            continue
        try:
            # Opschonen MultiIndex kolommen (bij batch kunnen die voorkomen)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)

            # Zorg dat de index datetime is
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)

            # Itereer dagen (i=1..len-1)
            for i in range(1, len(df)):
                prev = df.iloc[i-1]
                curr = df.iloc[i]

                # Haal waarden op
                low_prev = float(prev['Low'])
                open_curr = float(curr['Open'])
                close_curr = float(curr['Close'])

                # Conditie
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
                else:
                    skipped_no_pattern += 1
        except Exception as e:
            print(f"Fout bij verwerking {ticker}: {e}", flush=True)
            continue

    print(f"Nieuwe entries: {len(new_entries)}, overgeslagen (leeg): {skipped_empty}, overgeslagen (geen patroon): {skipped_no_pattern}", flush=True)

    if new_entries:
        history.extend(new_entries)
        save_history(history)
    return history

# === HOOFDFUNCTIE VOOR APP ===
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
    if hour < 9:
        aex = "⏳ AEX nog niet open"
    elif hour < 17 or (hour == 17 and minute < 30):
        aex = "🟢 AEX open"
    else:
        aex = "🔴 AEX gesloten"
    if hour < 15 or (hour == 15 and minute < 30):
        us = "⏳ US nog niet open"
    elif hour < 22:
        us = "🟢 US open"
    else:
        us = "🔴 US gesloten"
    return {"AEX": aex, "US": us}

def get_snapshot_info():
    return "📊 Data elke keer vers (10 dagen)"