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

def get_stock_data(ticker):
    """Haal 10 dagen koersdata op voor voldoende historie"""
    data = yf.download(ticker, period="10d", interval="1d", progress=False)
    if len(data) < 3:
        return None
    return data

def is_snapshot_today():
    """Check of er vandaag al een snapshot is gemaakt"""
    if not os.path.exists(SNAPSHOT_FILE):
        return False
    try:
        with open(SNAPSHOT_FILE, 'r') as f:
            snap = json.load(f)
        return snap.get('date') == datetime.now(timezone.utc).strftime('%Y-%m-%d')
    except:
        return False

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

def check_bearish_gap():
    """
    Zoek bearish gap down + bearish candle patroon:
    Dag N+1 open < Dag N low (gap down)
    Dag N+1 close < Dag N+1 open (bearish candle)
    """
    if is_snapshot_today():
        return load_snapshot()
    
    results = []
    nederland_nu = datetime.now(timezone.utc) + timedelta(hours=2)
    
    for ticker in AEX_TICKERS:
        try:
            data = get_stock_data(ticker)
            if data is None or len(data) < 3:
                continue
            
            # Dag N = 3 dagen geleden, Dag N+1 = 2 dagen geleden, Dag N+2 = gisteren
            dag_n = data.iloc[-3]    # dag N
            dag_n1 = data.iloc[-2]   # dag N+1
            dag_n2 = data.iloc[-1]   # dag N+2 (vandaag/gisteren)
            
            open_n = float(dag_n['Open'].iloc[0])
            high_n = float(dag_n['High'].iloc[0])
            low_n = float(dag_n['Low'].iloc[0])
            close_n = float(dag_n['Close'].iloc[0])
            
            open_n1 = float(dag_n1['Open'].iloc[0])
            high_n1 = float(dag_n1['High'].iloc[0])
            low_n1 = float(dag_n1['Low'].iloc[0])
            close_n1 = float(dag_n1['Close'].iloc[0])
            
            open_n2 = float(dag_n2['Open'].iloc[0])
            
            # Conditie 1: N+1 open < N low (gap down)
            gap_down = open_n1 < low_n
            
            # Conditie 2: N+1 close < N+1 open (bearish candle)
            bearish_candle = close_n1 < open_n1
            
            if gap_down and bearish_candle:
                gap_pct = ((low_n - open_n1) / low_n) * 100
                candle_pct = ((open_n1 - close_n1) / open_n1) * 100
                
                results.append({
                    'Ticker': ticker.replace('.AS', ''),
                    'Dag N Low': round(low_n, 2),
                    'N+1 Open': round(open_n1, 2),
                    'N+1 Close': round(close_n1, 2),
                    'Gap %': round(gap_pct, 2),
                    'Candle %': round(candle_pct, 2)
                })
        except:
            continue
    
    df = pd.DataFrame(results)
    if not df.empty:
        df = df.sort_values('Gap %', ascending=False)
    
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
    try:
        if is_snapshot_today():
            _, time = load_snapshot()
            return f"📸 Snapshot van {time}"
    except:
        pass
    return "🔄 Live data"