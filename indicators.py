# indicators.py
"""
Simple indicator functions using pandas.
Unused in current code, but kept for potential future use.
"""
import pandas as pd


def sma(series: pd.Series, window: int) -> pd.Series:
    """
    Calculate Simple Moving Average.

    Args:
        series: Pandas Series of data.
        window: Window size for the moving average.

    Returns:
        Pandas Series with SMA values.
    """
    return series.rolling(window).mean()


def ema(series: pd.Series, window: int) -> pd.Series:
    """
    Calculate Exponential Moving Average.

    Args:
        series: Pandas Series of data.
        window: Window size for the EMA.

    Returns:
        Pandas Series with EMA values.
    """
    return series.ewm(span=window, adjust=False).mean()


def rsi(series: pd.Series, window: int = 14) -> pd.Series:
    """
    Calculate Relative Strength Index (RSI).

    Args:
        series: Pandas Series of data (e.g., closing prices).
        window: Period for RSI calculation (default 14).

    Returns:
        Pandas Series with RSI values.
    """
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ma_up = up.ewm(com=window - 1, adjust=False).mean()
    ma_down = down.ewm(com=window - 1, adjust=False).mean()
    rs = ma_up / ma_down
    return 100 - (100 / (1 + rs))