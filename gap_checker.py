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

SNAPSHOT_FILE = "snapshot.json"
CACHE_FILE = "cache.json"

def get_stock_data(ticker):
    """Haal 5 dagen koersdata op"""
    data = yf.download(ticker, period="5d", interval="1d", progress=False)
    if len(data) < 2:
        return None
    return data

def is_snapshot_today():
    """Check of er vandaag al een snapshot is gemaakt"""
    if not os.path.exists(SNAPSHOT_FILE):
        return False
    with open(SNAPSHOT_FILE, 'r') as f:
        snap = json.load(f)
    return snap.get('date') == datetime.now(timezone.utc).strftime('%Y-%m-%d')

def save_snapshot(df):
    """Sla snapshot op voor vandaag"""
    snapshot = {
        'date': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
        'time': (datetime.now(timezone.utc) + timedelta(hours=2)).strftime('%H:%M'),
        'data': df.to_dict('records')
    }
    with open(SNAPSHOT_FILE, 'w') as f:
        json.dump(snapshot, f)

def load_snapshot():
    """Laad de snapshot van vandaag"""
    with open(SNAPSHOT_FILE, 'r') as f:
        snap = json.load(f)
    return pd.DataFrame(snap['data']), snap['time']

def check_gap_down():
    """Check alle AEX fondsen op gap downs"""
    # Als er al een snapshot is voor vandaag, gebruik die
    try:
        if is_snapshot_today():
            return load_snapshot()
    except:
        pass  # Bestand corrupt of niet leesbaar, gewoon opnieuw ophalen
    
    # Anders: nieuwe data ophalen
    gap_downs = []
    nederland_nu = datetime.now(timezone.utc) + timedelta(hours=2)
    
    for ticker in AEX_TICKERS:
        try:
            data = get_stock_data(ticker)
            if data is None:
                continue
                
            prev_day = data.iloc[-2]
            last_day = data.iloc[-1]
            
            prev_low = float(prev_day['Low'].iloc[0])
            prev_close = float(prev_day['Close'].iloc[0])
            today_open = float(last_day['Open'].iloc[0])
            
            if today_open < prev_low:
                gap_pct = ((prev_low - today_open) / prev_low) * 100
                gap_downs.append({
                    'Ticker': ticker.replace('.AS', ''),
                    'Slot gisteren': round(prev_close, 2),
                    'Low gisteren': round(prev_low, 2),
                    'Open vandaag': round(today_open, 2),
                    'Gap %': round(gap_pct, 2)
                })
        except:
            continue
    
    df = pd.DataFrame(gap_downs)
    if not df.empty:
        df = df.sort_values('Gap %', ascending=False)
    
    # Alleen snapshot opslaan als de beurs open is geweest
    if nederland_nu.hour >= 9:
        try:
            save_snapshot(df)
        except:
            pass
    
    return df, (datetime.now(timezone.utc) + timedelta(hours=2)).strftime('%H:%M')

def get_market_status():
    """Check of de beurs open is (Nederlandse tijd)"""
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
    """Haal info op over de snapshot"""
    try:
        if is_snapshot_today():
            _, time = load_snapshot()
            return f"📸 Snapshot van {time}"
    except:
        pass
    return "🔄 Live data"