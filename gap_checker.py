import yfinance as yf
import pandas as pd
from datetime import datetime, timezone, timedelta

# AEX (ongewijzigd)
AEX_TICKERS = [
    "ADYEN.AS", "AGN.AS", "AKZA.AS", "ASM.AS", "ASML.AS",
    "BESI.AS", "DSM.AS", "EXO.AS", "HEIA.AS", "HEIN.AS",
    "IMCD.AS", "INGA.AS", "KPN.AS", "MT.AS", "PHIA.AS",
    "PRX.AS", "RAND.AS", "REL.AS", "SHELL.AS", "TKWY.AS",
    "UNA.AS", "VPK.AS", "WKL.AS"
]

# Top 100 Amerikaanse bedrijven (NYSE/Nasdaq)
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
    """
    Download data voor een lijst tickers in één batch (of per ticker als batch faalt).
    Retourneert dict: {ticker: DataFrame}
    """
    if not tickers:
        return {}
    try:
        data = yf.download(tickers, period=period, interval="1d", progress=False, group_by='ticker')
        # Normaliseer
        if len(tickers) == 1:
            data = {tickers[0]: data}
        if data and any(not df.empty for df in data.values()):
            return data
    except:
        pass

    # Fallback: één voor één
    result = {}
    for t in tickers:
        try:
            df = yf.download(t, period=period, interval="1d", progress=False)
            if not df.empty:
                result[t] = df
        except:
            continue
    return result

def check_bearish_gaps():
    """
    Scan AEX + US tickers op het bearish gap patroon van de meest recente voltooide dag.
    """
    all_tickers = AEX_TICKERS + US_TICKERS
    # Verdeel in batches van 50 voor stabiliteit
    batch_size = 50
    results = []

    for i in range(0, len(all_tickers), batch_size):
        batch = all_tickers[i:i+batch_size]
        data = fetch_ticker_data(batch, period="5d")
        for ticker, df in data.items():
            if df is None or len(df) < 2:
                continue
            try:
                # Kolommen opschonen (multi-index bij batch)
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.droplevel(1)
                # Index naar datetime
                if not isinstance(df.index, pd.DatetimeIndex):
                    df.index = pd.to_datetime(df.index)

                dag_n = df.iloc[-2]   # eergisteren
                dag_n1 = df.iloc[-1]  # gisteren

                low_n = float(dag_n['Low'])
                open_n1 = float(dag_n1['Open'])
                close_n1 = float(dag_n1['Close'])

                if open_n1 < low_n and close_n1 < open_n1:
                    gap_pct = ((low_n - open_n1) / low_n) * 100
                    candle_pct = ((close_n1 - open_n1) / open_n1) * 100
                    gap_date = dag_n1.name
                    gap_date_str = gap_date.strftime('%Y-%m-%d') if hasattr(gap_date, 'strftime') else str(gap_date)[:10]
                    exchange = "AEX" if ticker.endswith('.AS') else "NYSE/NASDAQ"
                    ticker_clean = ticker.replace('.AS', '')

                    results.append({
                        'Ticker': ticker_clean,
                        'Datum': gap_date_str,
                        'Exchange': exchange,
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
        df = df.sort_values(['Datum', 'Gap %'], ascending=[False, False])
    return df

def get_market_status():
    """Status voor AEX en US (NL tijd)"""
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