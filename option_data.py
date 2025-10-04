# option_data.py
import yfinance as yf
import pandas as pd
import gc


def fetch_option_chain(ticker, expiration=None, option_type="Both", min_strike=None, max_strike=None, sort_by="strike", get_stock=False):
    """
    Fetch option chain data for a given ticker and apply filters.
    If get_stock=True, return the yfinance Ticker object instead of DataFrame.
    """
    try:
        stock = yf.Ticker(ticker)
        if get_stock:
            return stock

        if not expiration:
            raise ValueError("Expiration date is required for option chain.")

        chain = stock.option_chain(expiration)
        if option_type == "Calls":
            df = chain.calls.assign(Type="Call")
        elif option_type == "Puts":
            df = chain.puts.assign(Type="Put")
        else:
            df = pd.concat([chain.calls.assign(Type="Call"), chain.puts.assign(Type="Put")])

        # Apply strike filters
        if min_strike is not None:
            df = df[df["strike"] >= min_strike]
        if max_strike is not None:
            df = df[df["strike"] <= max_strike]

        # Map sort key
        sort_key = sort_by
        if sort_key == "openinterest":
            sort_key = "openInterest"
        elif sort_key == "impliedvolatility":
            sort_key = "impliedVolatility"
        if sort_key not in df.columns:
            sort_key = "strike"

        # Sort and limit to 50 rows
        df = df.sort_values(by=sort_key, ascending=True).head(50)

        stock.session.close()
        return df
    except Exception as e:
        print(f"Error in fetch_option_chain for {ticker}: {e}")
        return pd.DataFrame()
    finally:
        if 'df' in locals():
            del df
        if 'stock' in locals():
            stock.session.close()
        gc.collect()