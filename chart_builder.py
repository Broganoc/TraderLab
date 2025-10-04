# chart_builder.py
import yfinance as yf
import plotly.graph_objs as go
from plotly.subplots import make_subplots
import gc


def get_chart_html(ticker, interval="1d", period="6mo", plots=["Candlestick"]):
    """
    Builds a chart with multiple stacked plots (Candlestick, Line, RSI, MACD, Bollinger Bands).
    Limits data size to prevent excessive memory usage.
    """
    stock = yf.Ticker(ticker)
    df = stock.history(period=period, interval=interval)

    if df.empty:
        stock.session.close()
        return "<h3>No data available for this ticker/interval/period.</h3>"

    # Downsample if too large to reduce memory usage
    if len(df) > 1000:  # Adjust threshold as needed
        df = df.iloc[::2]  # Take every other row

    n_rows = len(plots)
    fig = make_subplots(
        rows=n_rows, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        subplot_titles=plots
    )

    for i, plot_type in enumerate(plots):
        row = i + 1

        if plot_type == "Candlestick":
            fig.add_trace(go.Candlestick(
                x=df.index,
                open=df['Open'],
                high=df['High'],
                low=df['Low'],
                close=df['Close'],
                name="Candlestick"
            ), row=row, col=1)

        elif plot_type == "Volume":
            fig.add_trace(go.Bar(
                x=df.index,
                y=df['Volume'],
                name="Volume",
                marker=dict(color="rgba(100,100,200,0.5)")
            ), row=row, col=1)

        elif plot_type == "Line":
            fig.add_trace(go.Scatter(
                x=df.index, y=df['Close'], mode='lines', name="Close"
            ), row=row, col=1)

        elif plot_type == "RSI":
            delta = df['Close'].diff()
            gain = delta.clip(lower=0)
            loss = -1 * delta.clip(upper=0)
            avg_gain = gain.rolling(14).mean()
            avg_loss = loss.rolling(14).mean()
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            fig.add_trace(go.Scatter(
                x=df.index, y=rsi, mode='lines', name="RSI"
            ), row=row, col=1)
            fig.update_yaxes(range=[0, 100], row=row, col=1)

        elif plot_type == "MACD":
            ema12 = df['Close'].ewm(span=12, adjust=False).mean()
            ema26 = df['Close'].ewm(span=26, adjust=False).mean()
            macd = ema12 - ema26
            signal = macd.ewm(span=9, adjust=False).mean()
            fig.add_trace(go.Scatter(x=df.index, y=macd, mode='lines', name="MACD"), row=row, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=signal, mode='lines', name="Signal"), row=row, col=1)

        elif plot_type == "Bollinger Bands":
            sma20 = df['Close'].rolling(20).mean()
            std20 = df['Close'].rolling(20).std()
            upper = sma20 + 2 * std20
            lower = sma20 - 2 * std20
            fig.add_trace(go.Scatter(x=df.index, y=df['Close'], mode='lines', name="Close"), row=row, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=upper, mode='lines', name="Upper Band", line=dict(dash='dot')),
                          row=row, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=lower, mode='lines', name="Lower Band", line=dict(dash='dot')),
                          row=row, col=1)

    fig.update_layout(template="plotly_dark", height=300 * n_rows)
    html = fig.to_html(include_plotlyjs="cdn")

    # Cleanup
    del df
    stock.session.close()
    gc.collect()

    return html