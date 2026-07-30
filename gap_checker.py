import yfinance as yf
import pandas as pd
from datetime import datetime, timezone, timedelta

AEX_TICKERS = [
    "ADYEN.AS", "AGN.AS", "AKZA.AS", "ASM.AS", "ASML.AS",
    "BESI.AS", "DSM.AS", "EXO.AS", "HEIA.AS", "HEIN.AS",
    "IMCD.AS", "INGA.AS", "KPN.AS", "MT.AS", "PHIA.AS",
    "PRX.AS", "RAND.AS", "REL.AS", "SHELL.AS", "TKWY.AS",
    "UNA.AS", "VPK.AS", "WKL.AS"
]

US_TICKERS = [
    "AAPL", "MSFT", "AMZN", "GOOGL", "GOOG", "META", "TSLA", "BRK-B", "JPM", "V",
    "JNJ", "WMT", "PG", "MA", "UNH", "HD", "BAC", "DIS", "ADBE", "CRM",
    "NFLX", "INTC", "CSCO", "VZ", "KO", "PEP", "MRK", "ABT", "WFC", "TMO",
    "NVDA", "AVGO", "AMD", "QCOM", "TXN", "AMAT", "MU", "ADI", "LRCX", "KLAC",
    "COST", "NKE", "DHR", "LLY", "MDT", "LIN", "UPS", "RTX", "HON", "UNP",
    "LOW", "ORCL", "MS", "GS", "BLK", "C", "AXP", "AMGN", "SPGI", "NOW",
    "INTU", "ISRG", "BKNG", "SCHW", "DE", "PLD", "AMT", "ADP", "CB", "MMC",
    "T", "BMY", "GILD", "CI", "CVS", "MDLZ", "SBUX", "MO", "SO", "DUK",
    "NEE", "CAT", "BA", "GE", "GM", "F", "UBER", "PYPL", "SQ", "ZM",
    "SNAP", "PINS", "ROKU", "DKNG", "CRWD", "NET", "DDOG", "SNOW", "PLTR", "U"
]

def fetch_ticker_data(tickers, period="5d"):
    """Download batch of individueel, retourneert dict {ticker: DataFrame}"""
    if not tickers:
        return {}
    try:
        data = yf.download(tickers, period=period, interval="1d", progress=False, group_by='ticker')
        if len(tickers) == 1:
            data = {tickers[0]: data}
        if data and any(not df.empty for df in data.values()):
            return data
    except:
        pass
    # fallback per ticker
    result = {}
    for t in tickers:
        try:
            df = yf.download(t, period=period, interval="1d", progress=False)
            if not df.empty:
                result[t] = df
        except:
            continue
    return result

def scan_all_patterns():
    """
    Scant op twee patronen:
    1. Bearish Gap (bestaand): N+1 open < N low én N+1 close < N+1 open
    2. Dubbele Gap Down (nieuw): N+1 high < N low én N+2 open < N low
    Retourneert DataFrame met alle signalen en kolom 'Signaaltype'.
    """
    all_tickers = AEX_TICKERS + US_TICKERS
    batch_size = 50
    results = []

    for i in range(0, len(all_tickers), batch_size):
        batch = all_tickers[i:i+batch_size]
        data = fetch_ticker_data(batch, period="5d")
        for ticker, df in data.items():
            if df is None or len(df) < 3:
                continue
            try:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.droplevel(1)
                if not isinstance(df.index, pd.DatetimeIndex):
                    df.index = pd.to_datetime(df.index)

                # Gebruik de laatste drie voltooide dagen: N (index -3), N+1 (-2), N+2 (-1)
                if len(df) < 3:
                    continue
                dag_n = df.iloc[-3]
                dag_n1 = df.iloc[-2]
                dag_n2 = df.iloc[-1]   # dit is gisteren

                low_n = float(dag_n['Low'])
                open_n1 = float(dag_n1['Open'])
                close_n1 = float(dag_n1['Close'])
                high_n1 = float(dag_n1['High'])
                open_n2 = float(dag_n2['Open'])
                close_n2 = float(dag_n2['Close'])
                date_n1 = dag_n1.name.strftime('%Y-%m-%d') if hasattr(dag_n1.name, 'strftime') else str(dag_n1.name)[:10]
                exchange = "AEX" if ticker.endswith('.AS') else "NYSE/NASDAQ"
                ticker_clean = ticker.replace('.AS', '')

                # Patroon 1: Bearish Gap (open N+1 < low N, close N+1 < open N+1)
                if open_n1 < low_n and close_n1 < open_n1:
                    gap_pct = ((low_n - open_n1) / low_n) * 100
                    candle_pct = ((close_n1 - open_n1) / open_n1) * 100
                    results.append({
                        'Ticker': ticker_clean,
                        'Datum': date_n1,
                        'Exchange': exchange,
                        'Dag N Low': round(low_n, 2),
                        'N+1 Open': round(open_n1, 2),
                        'N+1 Close': round(close_n1, 2),
                        'Gap %': round(gap_pct, 2),
                        'Candle %': round(candle_pct, 2),
                        'Signaaltype': 'Bearish Gap'
                    })

                # Patroon 2: Dubbele Gap Down (high N+1 < low N, open N+2 < low N)
                if high_n1 < low_n and open_n2 < low_n:
                    gap_pct_n1 = ((low_n - open_n1) / low_n) * 100  # gap van N+1
                    gap_pct_n2 = ((low_n - open_n2) / low_n) * 100  # gap van N+2
                    results.append({
                        'Ticker': ticker_clean,
                        'Datum': f"{date_n1} → {dag_n2.name.strftime('%Y-%m-%d') if hasattr(dag_n2.name, 'strftime') else str(dag_n2.name)[:10]}",
                        'Exchange': exchange,
                        'Dag N Low': round(low_n, 2),
                        'N+1 Open': round(open_n1, 2),
                        'N+1 Close': round(close_n1, 2),
                        'Gap %': round(gap_pct_n2, 2),   # toon de tweede gap
                        'Candle %': round(gap_pct_n1, 2), # eerste gap
                        'Signaaltype': 'Dubbele Gap Down'
                    })
            except Exception as e:
                continue

    df = pd.DataFrame(results)
    if not df.empty:
        df = df.sort_values(['Signaaltype', 'Gap %'], ascending=[False, False])
    return df

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