# data_fetcher.py
import yfinance as yf
import pandas as pd

def fetch_current_price(ticker: str) -> float:
    info = yf.download(tickers=ticker, period="1d", interval="1m")
    if info.empty:
        return None
    return float(info['Close'].iloc[-1])

# data_fetcher.py
import yfinance as yf
import pandas as pd

def fetch_historical(ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    tk = yf.Ticker(ticker)
    df = tk.history(period=period, interval=interval, actions=False)
    df = df.reset_index()
    df.rename(columns={'Date': 'datetime'}, inplace=True)
    return df

def fetch_summary(ticker: str) -> dict:
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
        "Dividend Yield": info.get("dividendYield", "N/A"),
        "52-Week High": info.get("fiftyTwoWeekHigh", "N/A"),
        "52-Week Low": info.get("fiftyTwoWeekLow", "N/A"),
        "Website": info.get("website", "N/A"),
    }
    return summary


if __name__ == "__main__":
    print(fetch_summary("AAPL"))
