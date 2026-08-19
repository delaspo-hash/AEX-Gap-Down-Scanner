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

def fetch_daily_data(tickers, period="5d"):
    """
    Haalt dagelijkse koersdata op voor een lijst tickers.
    Retourneert dict {ticker: DataFrame} of lege dict.
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

def fetch_today_open_prices(tickers):
    """
    Haalt voor vandaag de openingskoers op via intraday (1-minuut) data.
    Retourneert dict {ticker: float open_price} of leeg.
    """
    if not tickers:
        return {}
    # Probeer batch-download
    try:
        data = yf.download(tickers, period="1d", interval="1m", progress=False, group_by='ticker')
        opens = {}
        for t in tickers:
            if t in data and not data[t].empty:
                df = data[t]
                # De eerste candle van de dag is de opening
                # Zorg dat we alleen de reguliere sessie hebben; yfinance kan pre-market bevatten,
                # maar we vertrouwen op de eerste rij na opening.
                if 'Open' in df.columns:
                    opens[t] = float(df.iloc[0]['Open'])
        if opens:
            return opens
    except:
        pass

    # Fallback: één voor één
    opens = {}
    for t in tickers:
        try:
            df = yf.download(t, period="1d", interval="1m", progress=False)
            if not df.empty and 'Open' in df.columns:
                opens[t] = float(df.iloc[0]['Open'])
        except:
            continue
    return opens

def scan_all_patterns():
    """
    Scant op openingsgaps van vandaag t.o.v. de verwachte vorige handelsdag.
    Gebruikt dagdata voor vorige handelsdagen en intraday-data voor de opening van vandaag.
    Alleen als beide datums correct aanwezig zijn, wordt het aandeel getoond.
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

    # Dagdata ophalen (vorige handelsdagen)
    daily_data = fetch_daily_data(all_tickers, period="5d")

    # Openingskoersen van vandaag ophalen (intraday)
    today_opens = fetch_today_open_prices(all_tickers)

    # Combineer
    for ticker, df in daily_data.items():
        if df is None or len(df) < 1:
            continue
        try:
            # Kolommen opschonen en index datetime maken
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)

            # Zoek de verwachte vorige handelsdag
            df_prev = df[df.index.date == expected_prev_date]
            if df_prev.empty:
                continue
            prev_row = df_prev.iloc[-1]
            prev_high = float(prev_row['High'])
            prev_low = float(prev_row['Low'])

            # Openingskoers van vandaag
            open_today = today_opens.get(ticker)
            if open_today is None or pd.isna(open_today):
                continue

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