import yfinance as yf
import pandas as pd
from datetime import datetime, timezone, timedelta
import time

# === JUISTE AEX-TICKERS ===
AEX_TICKERS = [
    "ADYEN.AS", "AGN.AS", "AKZA.AS", "ASM.AS", "ASML.AS",
    "BESI.AS", "DSFIR.AS", "EXO.AS", "HEIA.AS", "IMCD.AS",
    "INGA.AS", "KPN.AS", "MT.AS", "PHIA.AS", "PRX.AS",
    "RAND.AS", "REN.AS", "SHELL.AS", "TKAY.AS", "UNA.AS",
    "VPK.AS", "WKL.AS"
]

# === 100 GROOTSTE US-BEDRIJVEN ===
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
    Downloadt dagelijkse koersdata voor een lijst tickers.
    Eerst batch, daarna per ticker met pauzes indien nodig.
    """
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

    # Fallback: één voor één
    result = {}
    for i, t in enumerate(tickers):
        try:
            df = yf.download(t, period=period, interval="1d", progress=False)
            if not df.empty:
                result[t] = df
        except:
            continue
        if (i + 1) % 10 == 0:
            time.sleep(0.5)
    return result

def scan_all_patterns():
    """
    Scant op twee patronen:
    1. Bearish Gap: N+1 open < N low én N+1 close < N+1 open
    2. Bullish Gap: N+1 open > N high én N+1 close > N+1 open
    Retourneert DataFrame met kolom 'Signaaltype'.
    """
    all_tickers = AEX_TICKERS + US_TICKERS
    batch_size = 50
    results = []

    for i in range(0, len(all_tickers), batch_size):
        batch = all_tickers[i:i+batch_size]
        data = fetch_ticker_data(batch, period="5d")
        if i + batch_size < len(all_tickers):
            time.sleep(0.3)

        for ticker, df in data.items():
            if df is None or len(df) < 2:
                continue
            try:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.droplevel(1)
                if not isinstance(df.index, pd.DatetimeIndex):
                    df.index = pd.to_datetime(df.index)

                # We hebben de laatste twee voltooide dagen nodig: N (eergisteren), N+1 (gisteren)
                if len(df) < 2:
                    continue
                dag_n = df.iloc[-2]
                dag_n1 = df.iloc[-1]

                low_n = float(dag_n['Low'])
                high_n = float(dag_n['High'])
                open_n1 = float(dag_n1['Open'])
                close_n1 = float(dag_n1['Close'])

                date_n1 = dag_n1.name.strftime('%Y-%m-%d') if hasattr(dag_n1.name, 'strftime') else str(dag_n1.name)[:10]
                exchange = "AEX" if ticker.endswith('.AS') else "NYSE/NASDAQ"
                ticker_clean = ticker.replace('.AS', '')

                # --- Bearish Gap ---
                if open_n1 < low_n and close_n1 < open_n1:
                    gap_pct = ((low_n - open_n1) / low_n) * 100
                    candle_pct = ((close_n1 - open_n1) / open_n1) * 100
                    results.append({
                        'Ticker': ticker_clean,
                        'Datum': date_n1,
                        'Exchange': exchange,
                        'Dag N High': round(high_n, 2),
                        'Dag N Low': round(low_n, 2),
                        'N+1 Open': round(open_n1, 2),
                        'N+1 Close': round(close_n1, 2),
                        'Gap %': round(gap_pct, 2),
                        'Candle %': round(candle_pct, 2),
                        'Signaaltype': 'Bearish Gap'
                    })

                # --- Bullish Gap ---
                if open_n1 > high_n and close_n1 > open_n1:
                    gap_pct = ((open_n1 - high_n) / high_n) * 100
                    candle_pct = ((close_n1 - open_n1) / open_n1) * 100
                    results.append({
                        'Ticker': ticker_clean,
                        'Datum': date_n1,
                        'Exchange': exchange,
                        'Dag N High': round(high_n, 2),
                        'Dag N Low': round(low_n, 2),
                        'N+1 Open': round(open_n1, 2),
                        'N+1 Close': round(close_n1, 2),
                        'Gap %': round(gap_pct, 2),
                        'Candle %': round(candle_pct, 2),
                        'Signaaltype': 'Bullish Gap'
                    })

            except Exception:
                continue

    df = pd.DataFrame(results)
    if not df.empty:
        # Sorteer op signaaltype en dan op absolute gap (grootste eerst)
        df = df.sort_values(['Signaaltype', 'Gap %'], ascending=[True, False])
    return df

def get_market_status():
    """Bepaal of de AEX- en US-beurzen geopend zijn (Nederlandse tijd)."""
    now = datetime.now(timezone.utc) + timedelta(hours=2)
    hour = now.hour
    minute = now.minute
    weekday = now.weekday()

    if weekday >= 5:
        return {"AEX": "🔴 Weekend", "US": "🔴 Weekend"}

    # AEX (9:00 - 17:30)
    if hour < 9:
        aex = "⏳ AEX nog niet open"
    elif hour < 17 or (hour == 17 and minute < 30):
        aex = "🟢 AEX open"
    else:
        aex = "🔴 AEX gesloten"

    # US (15:30 - 22:00)
    if hour < 15 or (hour == 15 and minute < 30):
        us = "⏳ US nog niet open"
    elif hour < 22:
        us = "🟢 US open"
    else:
        us = "🔴 US gesloten"

    return {"AEX": aex, "US": us}