import yfinance as yf
import pandas as pd
from datetime import datetime, timezone, timedelta

# AEX fondsen
AEX_TICKERS = [
    "ADYEN.AS", "AGN.AS", "AKZA.AS", "ASM.AS", "ASML.AS",
    "BESI.AS", "DSM.AS", "EXO.AS", "HEIA.AS", "HEIN.AS",
    "IMCD.AS", "INGA.AS", "KPN.AS", "MT.AS", "PHIA.AS",
    "PRX.AS", "RAND.AS", "REL.AS", "SHELL.AS", "TKWY.AS",
    "UNA.AS", "VPK.AS", "WKL.AS"
]

def get_stock_data(ticker):
    """Haal koersdata op voor 1 ticker"""
    data = yf.download(ticker, period="5d", interval="1d", progress=False)
    if len(data) < 2:
        return None
    return data

def check_gap_down():
    """Check alle AEX fondsen op gap downs"""
    gap_downs = []
    today = datetime.now().date()
    
    for ticker in AEX_TICKERS:
        try:
            data = get_stock_data(ticker)
            if data is None:
                continue
                
            prev_day = data.iloc[-2]
            last_day = data.iloc[-1]
            
            prev_low = float(prev_day['Low'].iloc[0])
            today_open = float(last_day['Open'].iloc[0])
            prev_close = float(prev_day['Close'].iloc[0])
            
            # Gap down: opening lager dan low vorige dag
            if today_open < prev_low:
                gap_pct = ((prev_low - today_open) / prev_low) * 100
                gap_downs.append({
                    'Ticker': ticker.replace('.AS', ''),
                    'Slot gisteren': round(prev_close, 2),
                    'Low gisteren': round(prev_low, 2),
                    'Open vandaag': round(today_open, 2),
                    'Gap %': round(gap_pct, 2)
                })
        except Exception as e:
            continue
    
    return pd.DataFrame(gap_downs).sort_values('Gap %', ascending=False)

def get_market_status():
    """Check of de beurs open is (Nederlandse tijd)"""
    now = datetime.now(timezone.utc) + timedelta(hours=2)
    hour = now.hour
    weekday = now.weekday()  # 0 = maandag, 6 = zondag
    
    # Weekend
    if weekday >= 5:
        return "🔴 Weekend - Beurs gesloten"
    
    # Doordeweeks
    if hour < 9:
        return "⏳ Beurs nog niet open"
    elif hour < 17:
        return "🟢 Beurs is open"
    else:
        return "🔴 Beurs gesloten"