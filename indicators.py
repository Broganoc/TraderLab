# indicators.py
import pandas as pd

def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window).mean()

def ema(series: pd.Series, window: int) -> pd.Series:
    return series.ewm(span=window, adjust=False).mean()

def rsi(series: pd.Series, window: int = 14) -> pd.Series:
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ma_up = up.ewm(com=window-1, adjust=False).mean()
    ma_down = down.ewm(com=window-1, adjust=False).mean()
    rs = ma_up / ma_down
    return 100 - (100 / (1 + rs))
