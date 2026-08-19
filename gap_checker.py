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
    Scant op openingsgaps van vandaag t.o.v. de verwachte vorige handelsdag.
    Vergelijkt de openingskoers van vandaag met de high/low van die vorige dag.
    Als de verwachte vorige dag ontbreekt, wordt het aandeel overgeslagen.
    """
    all_tickers = AEX_TICKERS + BEL20_TICKERS
    batch_size = 50
    results = []

    nederland_nu = datetime.now(timezone.utc) + timedelta(hours=2)
    today_nl = nederland_nu.date()
    scan_time = nederland_nu.strftime('%H:%M:%S')

    # Verwachte vorige handelsdag bepalen
    if today_nl.weekday() == 0:  # maandag -> vrijdag
        expected_prev_date = today_nl - timedelta(days=3)
    else:
        expected_prev_date = today_nl - timedelta(days=1)

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

                # Rij van vandaag moet aanwezig zijn
                df_today = df[df.index.date == today_nl]
                if df_today.empty:
                    continue
                today_row = df_today.iloc[-1]
                open_today = float(today_row['Open'])
                if pd.isna(open_today):
                    continue

                # Rij van de verwachte vorige handelsdag moet exact bestaan
                df_prev = df[df.index.date == expected_prev_date]
                if df_prev.empty:
                    continue
                prev_row = df_prev.iloc[-1]
                prev_high = float(prev_row['High'])
                prev_low = float(prev_row['Low'])

                if ticker.endswith('.AS'):
                    exchange = "Amsterdam"
                    ticker_clean = ticker.replace('.AS', '')
                elif ticker.endswith('.BR'):
                    exchange = "Brussel"
                    ticker_clean = ticker.replace('.BR', '')
                else:
                    exchange = "Onbekend"
                    ticker_clean = ticker

                # --- Bearish Gap (open < low vorige dag) ---
                if open_today < prev_low:
                    gap_pct = ((prev_low - open_today) / prev_low) * 100
                    results.append({
                        'Datum': today_nl.strftime('%Y-%m-%d'),
                        'Tijdstip': scan_time,
                        'Exchange': exchange,
                        'Ticker': ticker_clean,
                        'Vorige High': round(prev_high, 2),
                        'Vorige Low': round(prev_low, 2),
                        'Open Vandaag': round(open_today, 2),
                        'Gap %': round(gap_pct, 2),
                        'Signaaltype': 'Bearish Gap'
                    })

                # --- Bullish Gap (open > high vorige dag) ---
                if open_today > prev_high:
                    gap_pct = ((open_today - prev_high) / prev_high) * 100
                    results.append({
                        'Datum': today_nl.strftime('%Y-%m-%d'),
                        'Tijdstip': scan_time,
                        'Exchange': exchange,
                        'Ticker': ticker_clean,
                        'Vorige High': round(prev_high, 2),
                        'Vorige Low': round(prev_low, 2),
                        'Open Vandaag': round(open_today, 2),
                        'Gap %': round(gap_pct, 2),
                        'Signaaltype': 'Bullish Gap'
                    })

            except Exception:
                continue

    df = pd.DataFrame(results)
    if not df.empty:
        df = df.sort_values(
            ['Datum', 'Tijdstip', 'Exchange', 'Ticker'],
            ascending=[False, False, True, True]
        )
    return df

def get_market_status():
    """Bepaal of Euronext (Amsterdam & Brussel) geopend is (Nederlandse tijd)."""
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