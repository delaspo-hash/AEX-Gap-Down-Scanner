import yfinance as yf
import pandas as pd
from datetime import datetime, timezone, timedelta
import json
import os

AEX_TICKERS = [
    "ADYEN.AS", "AGN.AS", "AKZA.AS", "ASM.AS", "ASML.AS",
    "BESI.AS", "DSM.AS", "EXO.AS", "HEIA.AS", "HEIN.AS",
    "IMCD.AS", "INGA.AS", "KPN.AS", "MT.AS", "PHIA.AS",
    "PRX.AS", "RAND.AS", "REL.AS", "SHELL.AS", "TKWY.AS",
    "UNA.AS", "VPK.AS", "WKL.AS"
]

HISTORY_FILE = "history.json"
TODAY_SNAPSHOT_FLAG = "snapshot_done.json"

def get_stock_data(ticker):
    data = yf.download(ticker, period="10d", interval="1d", progress=False)
    if len(data) < 3:
        return None
    return data

def load_history():
    """Laad alle historische signalen"""
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
    """Check of we vandaag al gescand hebben"""
    if not os.path.exists(TODAY_SNAPSHOT_FLAG):
        return False
    try:
        with open(TODAY_SNAPSHOT_FLAG, 'r') as f:
            data = json.load(f)
        return data.get('date') == datetime.now(timezone.utc).strftime('%Y-%m-%d')
    except:
        return False

def mark_today_scanned():
    with open(TODAY_SNAPSHOT_FLAG, 'w') as f:
        json.dump({'date': datetime.now(timezone.utc).strftime('%Y-%m-%d')}, f)

def scan_today():
    """Scan de markt voor nieuwe bearish gap signalen en voeg toe aan historie"""
    history = load_history()
    today_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    
    # Voorkom dubbele scans op dezelfde dag
    if is_today_already_scanned():
        return history  # return bestaande historie zonder opnieuw te fetchen
    
    new_entries = []
    for ticker in AEX_TICKERS:
        try:
            data = get_stock_data(ticker)
            if data is None or len(data) < 3:
                continue
            
            dag_n = data.iloc[-3]
            dag_n1 = data.iloc[-2]
            
            low_n = float(dag_n['Low'].iloc[0])
            open_n1 = float(dag_n1['Open'].iloc[0])
            close_n1 = float(dag_n1['Close'].iloc[0])
            
            # Gap down: N+1 open < N low
            gap_down = open_n1 < low_n
            # Bearish candle: N+1 close < N+1 open
            bearish = close_n1 < open_n1
            
            if gap_down and bearish:
                gap_pct = ((low_n - open_n1) / low_n) * 100  # positief
                candle_pct = ((close_n1 - open_n1) / open_n1) * 100  # negatief
                
                # Bepaal de datum van de gap (N+1) – dat is de handelsdag van dag_n1
                gap_date = dag_n1.name  # index is datetime
                if hasattr(gap_date, 'strftime'):
                    gap_date_str = gap_date.strftime('%Y-%m-%d')
                else:
                    gap_date_str = str(gap_date)[:10]
                
                new_entries.append({
                    'Datum': gap_date_str,
                    'Ticker': ticker.replace('.AS', ''),
                    'Dag N Low': round(low_n, 2),
                    'N+1 Open': round(open_n1, 2),
                    'N+1 Close': round(close_n1, 2),
                    'Gap %': round(gap_pct, 2),
                    'Candle %': round(candle_pct, 2)
                })
        except:
            continue
    
    if new_entries:
        # Voeg toe aan bestaande historie
        history.extend(new_entries)
        save_history(history)
    
    # Markeer vandaag als gescand
    mark_today_scanned()
    return history

def check_bearish_gap():
    """Retourneer de volledige historie als DataFrame, en de huidige tijd"""
    history = scan_today()  # scant indien nodig, anders bestaande historie
    
    if history:
        df = pd.DataFrame(history)
        # Sorteer op datum aflopend, dan op gap % aflopend
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
        return f"📸 Scan van vandaag uitgevoerd"
    return "🔄 Nog niet gescand vandaag"