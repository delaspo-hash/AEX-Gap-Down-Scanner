import yfinance as yf
import pandas as pd
from datetime import datetime, timezone, timedelta
import time

# === EURONEXT AMSTERDAM (AEX) ===
AEX_TICKERS = [
    "ADYEN.AS", "AGN.AS", "AKZA.AS", "ASM.AS", "ASML.AS",
    "BESI.AS", "DSFIR.AS", "EXO.AS", "HEIA.AS", "IMCD.AS",
    "INGA.AS", "KPN.AS", "MT.AS", "PHIA.AS", "PRX.AS",
    "RAND.AS", "REN.AS", "SHELL.AS", "TKAY.AS", "UNA.AS",
    "VPK.AS", "WKL.AS"
]

# === EURONEXT BRUSSEL (BEL20 + enkele extra) ===
BEL20_TICKERS = [
    "ABI.BR", "AGS.BR", "ARGX.BR", "BAR.BR", "COFB.BR",
    "COLR.BR", "DEME.BR", "ELI.BR", "GBLB.BR", "KBC.BR",
    "MELE.BR", "PROX.BR", "SOF.BR", "SOLB.BR", "TNET.BR",
    "UCB.BR", "UMI.BR", "VGP.BR", "WDP.BR"
]

def fetch_ticker_data(tickers, period="5d"):
    """Downloadt dagelijkse koersdata voor een lijst tickers."""
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
    Scant op Bearish en Bullish Gap, voegt een tijdstip toe en sorteert
    op Datum (aflopend), Tijdstip (aflopend), Exchange (oplopend), Ticker (oplopend).
    """
    all_tickers = AEX_TICKERS + BEL20_TICKERS
    batch_size = 50
    results = []

    # Eén tijdstip voor de hele scan
    scan_time = datetime.now().strftime('%H:%M:%S')

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

                if len(df) < 2:
                    continue
                dag_n = df.iloc[-2]
                dag_n1 = df.iloc[-1]

                low_n = float(dag_n['Low'])
                high_n = float(dag_n['High'])
                open_n1 = float(dag_n1['Open'])
                close_n1 = float(dag_n1['Close'])

                date_n1 = dag_n1.name.strftime('%Y-%m-%d') if hasattr(dag_n1.name, 'strftime') else str(dag_n1.name)[:10]

                if ticker.endswith('.AS'):
                    exchange = "Amsterdam"
                    ticker_clean = ticker.replace('.AS', '')
                elif ticker.endswith('.BR'):
                    exchange = "Brussel"
                    ticker_clean = ticker.replace('.BR', '')
                else:
                    exchange = "Onbekend"
                    ticker_clean = ticker

                # --- Bearish Gap ---
                if open_n1 < low_n and close_n1 < open_n1:
                    gap_pct = ((low_n - open_n1) / low_n) * 100
                    candle_pct = ((close_n1 - open_n1) / open_n1) * 100
                    results.append({
                        'Datum': date_n1,
                        'Tijdstip': scan_time,
                        'Exchange': exchange,
                        'Ticker': ticker_clean,
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
                        'Datum': date_n1,
                        'Tijdstip': scan_time,
                        'Exchange': exchange,
                        'Ticker': ticker_clean,
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
        # Sorteren: Datum aflopend, Tijdstip aflopend, Exchange oplopend, Ticker oplopend
        df = df.sort_values(
            ['Datum', 'Tijdstip', 'Exchange', 'Ticker'],
            ascending=[False, False, True, True]
        )
    return df

def get_market_status():
    """Bepaal of Euronext (Amsterdam & Brussel) geopend is."""
    now = datetime.now(timezone.utc) + timedelta(hours=2)
    hour = now.hour
    minute = now.minute
    weekday = now.weekday()

    if weekday >= 5:
        return "🔴 Weekend - Euronext gesloten"

    if hour < 9:
        return "⏳ Euronext nog niet open"
    elif hour < 17 or (hour == 17 and minute < 30):
        return "🟢 Euronext open"
    else:
        return "🔴 Euronext gesloten"