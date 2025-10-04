# data_fetcher.py
import yfinance as yf
import pandas as pd
import gc


def fetch_current_price(ticker: str) -> float:
    """
    Fetches current price (unused in current code, but kept for completeness).
    """
    info = yf.download(tickers=ticker, period="1d", interval="1m")
    if info.empty:
        return None
    price = float(info['Close'].iloc[-1])
    del info
    gc.collect()
    return price


def fetch_historical(ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    try:
        tk = yf.Ticker(ticker)
        df = tk.history(period=period, interval=interval, actions=False)
        if df.empty:
            tk.session.close()
            return pd.DataFrame()
        # Limit rows to prevent excessive memory usage
        if len(df) > 500:  # Stricter threshold
            df = df.iloc[-500:]  # Keep only the last 500 rows
        df = df.reset_index()
        df.rename(columns={'Date': 'datetime'}, inplace=True)
        tk.session.close()  # Close HTTP session
        return df
    except Exception as e:
        print(f"Error in fetch_historical for {ticker}: {e}")
        return pd.DataFrame()


def fetch_summary(ticker: str) -> dict:
    try:
        tk = yf.Ticker(ticker)
        info = tk.info

        summary = {
            "Symbol": ticker,
            "Name": info.get("longName", "N/A"),
            "Sector": info.get("sector", "N/A"),
            "Industry": info.get("industry", "N/A"),
            "Market Cap": f"{info.get('marketCap', 0):,}" if info.get("marketCap") else "N/A",
            "Current Price": info.get("currentPrice", "N/A"),
            "PE Ratio (TTM)": info.get("trailingPE", "N/A"),
            "EPS (TTM)": info.get("trailingEps", "N/A"),
            "Dividend Yield": f"{info.get('dividendYield', 0) * 100:.2f}%" if info.get("dividendYield") else "N/A",
            "52-Week High": info.get("fiftyTwoWeekHigh", "N/A"),
            "52-Week Low": info.get("fiftyTwoWeekLow", "N/A"),
            "Website": info.get("website", "N/A"),
        }
        tk.session.close()  # Close HTTP session
        return summary
    except Exception as e:
        print(f"Error in fetch_summary for {ticker}: {e}")
        return {"Symbol": ticker, "Name": "Error", "Current Price": "N/A"}


if __name__ == "__main__":
    print(fetch_summary("AAPL"))