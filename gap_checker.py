import yfinance as yf
import pandas as pd
from datetime import datetime, timezone, timedelta

# Alleen AEX (je kunt later eenvoudig uitbreiden)
AEX_TICKERS = [
    "ADYEN.AS", "AGN.AS", "AKZA.AS", "ASM.AS", "ASML.AS",
    "BESI.AS", "DSM.AS", "EXO.AS", "HEIA.AS", "HEIN.AS",
    "IMCD.AS", "INGA.AS", "KPN.AS", "MT.AS", "PHIA.AS",
    "PRX.AS", "RAND.AS", "REL.AS", "SHELL.AS", "TKWY.AS",
    "UNA.AS", "VPK.AS", "WKL.AS"
]

def get_stock_data(ticker):
    """Haal 5 dagen koersdata op (genoeg voor N en N+1)"""
    try:
        data = yf.download(ticker, period="5d", interval="1d", progress=False)
        if len(data) < 2:
            return None
        return data
    except:
        return None

def check_gap_down():
    """
    Scan alle AEX-fondsen op het bearish gap patroon van gisteren (N+1) t.o.v. eergisteren (N):
    - Open(N+1) < Low(N)  (gap down)
    - Close(N+1) < Open(N+1) (bearish candle)
    Retourneert DataFrame met de signalen van de meest recente voltooide dag.
    """
    gap_downs = []
    today = datetime.now(timezone.utc).date()

    for ticker in AEX_TICKERS:
        try:
            data = get_stock_data(ticker)
            if data is None:
                continue

            # De laatste twee dagen in de data zijn N (eergisteren) en N+1 (gisteren)
            dag_n = data.iloc[-2]   # eergisteren
            dag_n1 = data.iloc[-1]  # gisteren (meest recente volledige dag)

            low_n = float(dag_n['Low'].iloc[0])
            open_n1 = float(dag_n1['Open'].iloc[0])
            close_n1 = float(dag_n1['Close'].iloc[0])

            if open_n1 < low_n and close_n1 < open_n1:
                gap_pct = ((low_n - open_n1) / low_n) * 100
                candle_pct = ((close_n1 - open_n1) / open_n1) * 100
                gap_date = dag_n1.name
                gap_date_str = gap_date.strftime('%Y-%m-%d') if hasattr(gap_date, 'strftime') else str(gap_date)[:10]

                gap_downs.append({
                    'Ticker': ticker.replace('.AS', ''),
                    'Datum': gap_date_str,
                    'Dag N Low': round(low_n, 2),
                    'N+1 Open': round(open_n1, 2),
                    'N+1 Close': round(close_n1, 2),
                    'Gap %': round(gap_pct, 2),
                    'Candle %': round(candle_pct, 2)
                })
        except:
            continue

    df = pd.DataFrame(gap_downs)
    if not df.empty:
        df = df.sort_values('Gap %', ascending=False)
    return df

def get_market_status():
    """Status voor AEX (NL tijd)"""
    now = datetime.now(timezone.utc) + timedelta(hours=2)
    hour = now.hour
    minute = now.minute
    weekday = now.weekday()

    if weekday >= 5:
        return "🔴 Weekend - Beurs gesloten"
    if hour < 9:
        return "⏳ Beurs nog niet open"
    elif hour < 17 or (hour == 17 and minute < 30):
        return "🟢 Beurs is open"
    else:
        return "🔴 Beurs gesloten"