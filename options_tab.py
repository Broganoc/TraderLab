from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QTableWidget, QTableWidgetItem, QMessageBox, QCheckBox, QLineEdit,
    QSlider
)
from PyQt6.QtCore import Qt, QEvent
import yfinance as yf
import pandas as pd
import numpy as np
import datetime
from scipy.stats import norm
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas  # Use QtAgg for PyQt6 compatibility
import matplotlib.pyplot as plt
import gc

class OptionsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.current_ticker = None
        self.underlying_price = None
        self.risk_free_rate = None
        self.dividend_yield = None
        self.payoff_window = None  # For reusing payoff window

        # --- Layout ---
        main_layout = QVBoxLayout()
        control_layout = QHBoxLayout()

        # Ticker info
        self.ticker_info_label = QLabel("Underlying: No data")

        # Expiration date dropdown
        self.expiration_label = QLabel("Expiration Date:")
        self.expiration_box = QComboBox()

        # Option type toggle
        self.option_type = QComboBox()
        self.option_type.addItems(["Calls", "Puts", "Both"])
        self.option_type.currentTextChanged.connect(self.load_options)

        # Filter by strike range
        self.strike_filter_label = QLabel("Strike Range:")
        self.strike_min = QLineEdit()
        self.strike_max = QLineEdit()
        self.strike_min.setPlaceholderText("Min Strike")
        self.strike_max.setPlaceholderText("Max Strike")

        # Sort options
        self.sort_label = QLabel("Sort By:")
        self.sort_box = QComboBox()
        self.sort_box.addItems(["Strike", "Volume", "Open Interest", "Implied Volatility"])

        # Refresh button
        self.refresh_btn = QPushButton("Refresh Options")
        self.refresh_btn.clicked.connect(self.load_options)

        # Payoff diagram button
        self.payoff_btn = QPushButton("Show Payoff Diagram")
        self.payoff_btn.clicked.connect(self.show_payoff_diagram)
        self.payoff_btn.setEnabled(False)

        # Column customization checkboxes
        self.columns_label = QLabel("Select Columns:")
        self.column_checks = {
            "strike": QCheckBox("Strike"),
            "lastPrice": QCheckBox("Last Price"),
            "bid": QCheckBox("Bid"),
            "ask": QCheckBox("Ask"),
            "volume": QCheckBox("Volume"),
            "openInterest": QCheckBox("Open Interest"),
            "impliedVolatility": QCheckBox("Implied Volatility"),
            "delta": QCheckBox("Delta"),
            "gamma": QCheckBox("Gamma"),
            "theta": QCheckBox("Theta")
        }
        for col, check in self.column_checks.items():
            check.setChecked(True)  # All checked by default
            check.stateChanged.connect(self.update_table_columns)

        # Table to display options chain
        self.table = QTableWidget()
        self.table.itemSelectionChanged.connect(self.enable_payoff_button)

        # Add widgets to layouts
        control_layout.addWidget(self.expiration_label)
        control_layout.addWidget(self.expiration_box)
        control_layout.addWidget(self.option_type)
        control_layout.addWidget(self.strike_filter_label)
        control_layout.addWidget(self.strike_min)
        control_layout.addWidget(self.strike_max)
        control_layout.addWidget(self.sort_label)
        control_layout.addWidget(self.sort_box)
        control_layout.addWidget(self.refresh_btn)
        control_layout.addWidget(self.payoff_btn)

        # Column selection layout
        columns_layout = QHBoxLayout()
        columns_layout.addWidget(self.columns_label)
        for check in self.column_checks.values():
            columns_layout.addWidget(check)

        main_layout.addWidget(self.ticker_info_label)
        main_layout.addLayout(control_layout)
        main_layout.addLayout(columns_layout)
        main_layout.addWidget(self.table)
        self.setLayout(main_layout)

    def load_expirations(self, ticker):
        try:
            stock = yf.Ticker(ticker)
            exps = stock.options
            self.expiration_box.clear()

            if not exps:
                QMessageBox.warning(self, "No Options Data",
                                    f"No options data available for {ticker}")
                stock.session.close()
                return

            self.expiration_box.addItems(exps)
            self.current_ticker = ticker
            self.update_ticker_info(stock)
            stock.session.close()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load expirations: {e}")

    def update_ticker_info(self, stock):
        try:
            info = stock.info
            self.underlying_price = info.get("regularMarketPrice", 0)
            pe_ratio = info.get("trailingPE", "N/A")
            change = info.get("regularMarketChangePercent", 0)
            self.dividend_yield = info.get("trailingAnnualDividendYield", 0)
            self.risk_free_rate = self.fetch_risk_free_rate()
            self.ticker_info_label.setText(
                f"Underlying: {self.current_ticker} | Price: ${self.underlying_price:.2f} "
                f"({change:.2f}%) | P/E: {pe_ratio} | Dividend Yield: {self.dividend_yield:.2%} | Risk-Free Rate: {self.risk_free_rate:.2%}"
            )
        except Exception as e:
            self.ticker_info_label.setText(f"Underlying: {self.current_ticker} | Error fetching data")

    def fetch_risk_free_rate(self):
        try:
            irx = yf.download("^IRX", period="5d", progress=False)['Adj Close'].iloc[-1] / 100
            return irx
        except Exception:
            return 0.05  # Default to 5% if fetch fails

    def load_options(self):
        if not self.current_ticker:
            QMessageBox.warning(self, "No Ticker", "Please look up a ticker first.")
            return

        exp = self.expiration_box.currentText()
        if not exp:
            QMessageBox.warning(self, "No Expiration", "Please select an expiration date.")
            return

        df = None
        try:
            stock = yf.Ticker(self.current_ticker)
            chain = stock.option_chain(exp)
            option_type = self.option_type.currentText()

            # Select calls, puts, or both
            if option_type == "Calls":
                df = chain.calls
                df['Type'] = 'Call'  # Add Type for consistency
            elif option_type == "Puts":
                df = chain.puts
                df['Type'] = 'Put'
            else:
                df = pd.concat([chain.calls.assign(Type="Call"), chain.puts.assign(Type="Put")])

            # Debug: Log available columns
            print(f"Available columns in DataFrame: {list(df.columns)}")

            # Calculate time to expiration
            exp_date = datetime.datetime.strptime(exp, '%Y-%m-%d').date()
            today = datetime.date.today()
            t = max((exp_date - today).days / 365.0, 0.0001)  # Avoid division by zero

            # Calculate Greeks if missing or all NaN
            greeks = ['delta', 'gamma', 'theta']
            for greek in greeks:
                if greek not in df.columns or df[greek].isna().all():
                    if greek == 'delta':
                        df[greek] = df.apply(
                            lambda row: self.calculate_delta(row['strike'], self.underlying_price, self.risk_free_rate,
                                                             self.dividend_yield, row['impliedVolatility'], t,
                                                             row['Type']), axis=1)
                    elif greek == 'gamma':
                        df[greek] = df.apply(
                            lambda row: self.calculate_gamma(row['strike'], self.underlying_price, self.risk_free_rate,
                                                             self.dividend_yield, row['impliedVolatility'], t), axis=1)
                    elif greek == 'theta':
                        df[greek] = df.apply(
                            lambda row: self.calculate_theta(row['strike'], self.underlying_price, self.risk_free_rate,
                                                             self.dividend_yield, row['impliedVolatility'], t,
                                                             row['Type']), axis=1)

            # Filter by strike range
            min_strike = self.strike_min.text()
            max_strike = self.strike_max.text()
            if min_strike:
                df = df[df["strike"] >= float(min_strike)]
            if max_strike:
                df = df[df["strike"] <= float(max_strike)]

            # Sort data
            sort_key = self.sort_box.currentText().lower().replace(" ", "")
            if sort_key == "impliedvolatility":
                sort_key = "impliedVolatility"
            elif sort_key == "openinterest":
                sort_key = "openInterest"
            df = df.sort_values(by=sort_key, ascending=True)

            # Limit rows for performance
            df = df.head(50)

            # Warn if Greeks are missing (before calculation)
            missing_greeks = [col for col in greeks if col not in chain.calls.columns]  # Check original
            if missing_greeks:
                print(
                    f"Warning: Missing Greeks from yfinance for {self.current_ticker} ({exp}): {missing_greeks}. Calculated using Black-Scholes.")

            # Update table
            self.update_table(df)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load options chain: {e}")
        finally:
            if df is not None:
                del df
            if 'stock' in locals():
                stock.session.close()
            gc.collect()

    def calculate_delta(self, K, S, r, q, sigma, t, option_type):
        if sigma <= 0 or t <= 0 or S <= 0:
            return np.nan
        d1 = (np.log(S / K) + (r - q + 0.5 * sigma ** 2) * t) / (sigma * np.sqrt(t))
        if option_type == 'Call':
            return np.exp(-q * t) * norm.cdf(d1)
        else:
            return np.exp(-q * t) * (norm.cdf(d1) - 1)

    def calculate_gamma(self, K, S, r, q, sigma, t):
        if sigma <= 0 or t <= 0 or S <= 0:
            return np.nan
        d1 = (np.log(S / K) + (r - q + 0.5 * sigma ** 2) * t) / (sigma * np.sqrt(t))
        return np.exp(-q * t) * norm.pdf(d1) / (S * sigma * np.sqrt(t))

    def calculate_theta(self, K, S, r, q, sigma, t, option_type):
        if sigma <= 0 or t <= 0 or S <= 0:
            return np.nan
        d1 = (np.log(S / K) + (r - q + 0.5 * sigma ** 2) * t) / (sigma * np.sqrt(t))
        d2 = d1 - sigma * np.sqrt(t)
        if option_type == 'Call':
            theta = - (S * np.exp(-q * t) * norm.pdf(d1) * sigma) / (2 * np.sqrt(t)) - r * K * np.exp(
                -r * t) * norm.cdf(d2) + q * S * np.exp(-q * t) * norm.cdf(d1)
        else:
            theta = - (S * np.exp(-q * t) * norm.pdf(d1) * sigma) / (2 * np.sqrt(t)) + r * K * np.exp(
                -r * t) * norm.cdf(-d2) - q * S * np.exp(-q * t) * norm.cdf(-d1)
        return theta / 365  # Convert to daily theta

    def update_table(self, df):
        # Define available columns (matching yfinance DataFrame columns + calculated)
        all_columns = ["Type", "strike", "lastPrice", "bid", "ask", "volume",
                       "openInterest", "impliedVolatility", "delta", "gamma", "theta"]
        # Filter visible columns based on checked boxes and DataFrame columns
        visible_columns = ["Type"] if "Type" in df.columns else []
        visible_columns += [col for col in all_columns[1:] if
                            col in df.columns and self.column_checks.get(col, QCheckBox()).isChecked()]

        self.table.setRowCount(len(df))
        self.table.setColumnCount(len(visible_columns))
        self.table.setHorizontalHeaderLabels([col.replace("openInterest", "Open Interest")
                                             .replace("impliedVolatility", "Implied Volatility")
                                             .replace("lastPrice", "Last Price")
                                             .capitalize() for col in visible_columns])

        for i, row in df.iterrows():
            for j, col in enumerate(visible_columns):
                value = row.get(col, "N/A")
                if isinstance(value, float):
                    if col in ["lastPrice", "bid", "ask", "strike"]:
                        value = f"{value:.2f}"  # Prices to 2 decimals
                    elif col == "impliedVolatility":
                        value = f"{value * 100:.2f}%"  # IV to percentage
                    elif col in ["delta", "gamma", "theta"]:
                        value = f"{value:.4f}" if not pd.isna(value) else "N/A"  # Greeks to 4 decimals
                item = QTableWidgetItem(str(value))

                # Highlight ITM/OTM
                if col == "strike" and self.underlying_price:
                    strike = float(row.get("strike", 0))
                    is_call = row.get("Type", "Call") == "Call"
                    is_itm = (is_call and strike < self.underlying_price) or (
                                not is_call and strike > self.underlying_price)
                    if is_itm:
                        item.setBackground(Qt.GlobalColor.lightGray)

                # Highlight high volume
                if col == "volume" and float(row.get("volume", 0) or 0) > 1000:
                    item.setBackground(Qt.GlobalColor.yellow)

                self.table.setItem(i, j, item)

        self.table.resizeColumnsToContents()

    def update_table_columns(self):
        if self.current_ticker and self.expiration_box.currentText():
            self.load_options()

    def enable_payoff_button(self):
        self.payoff_btn.setEnabled(bool(self.table.selectedItems()))

    def show_payoff_diagram(self):
        """Note: This method is overridden in MainWindow to use Chart.js. This is the local matplotlib version."""
        if not self.table.selectedItems():
            QMessageBox.warning(self, "No Selection", "Please select at least one option.")
            return

        # Collect selected rows
        selected_rows = set(item.row() for item in self.table.selectedItems())
        strikes, premiums, types = [], [], []

        for row in selected_rows:
            strike_item = self.table.item(row, 1)  # Strike column
            type_item = self.table.item(row, 0)  # Call/Put
            premium_item = None

            # Find premium column
            for col in range(self.table.columnCount()):
                header = self.table.horizontalHeaderItem(col).text().lower()
                if "last price" in header:
                    premium_item = self.table.item(row, col)
                    break

            if not (strike_item and premium_item and type_item):
                continue

            strike = float(strike_item.text())
            premium = float(premium_item.text())
            opt_type = type_item.text()

            strikes.append(strike)
            premiums.append(premium)
            types.append(opt_type)

        if not strikes:
            QMessageBox.warning(self, "Error", "Could not extract strikes and premiums.")
            return

        # Store data for reuse when slider moves
        self._payoff_data = (strikes, premiums, types)
        self._spot_price = self.underlying_price or 100

        # Create or reuse payoff window
        if self.payoff_window is None:
            self.payoff_window = QWidget()
            self.payoff_window.closeEvent = self.close_payoff_window  # Custom close handler
            layout = QVBoxLayout(self.payoff_window)

            # Slider label
            self.slider_label = QLabel("Premium Multiplier: 1.0x")
            layout.addWidget(self.slider_label)

            # Slider (50% to 200% premium)
            self.slider = QSlider(Qt.Orientation.Horizontal)
            self.slider.setMinimum(50)
            self.slider.setMaximum(200)
            self.slider.setValue(100)  # start at 1.0x
            self.slider.valueChanged.connect(self.update_payoff_diagram)
            layout.addWidget(self.slider)

            # Matplotlib figure
            self.fig, self.ax = plt.subplots(figsize=(8, 5))
            self.canvas = FigureCanvas(self.fig)
            layout.addWidget(self.canvas)

            self.payoff_window.setWindowTitle("Options Payoff Diagram")
            self.payoff_window.resize(900, 700)
        self.payoff_window.show()
        self.update_payoff_diagram()

    def update_payoff_diagram(self):
        """Update the payoff diagram based on slider value."""
        if not hasattr(self, '_payoff_data'):
            return
        strikes, premiums, types = self._payoff_data
        multiplier = self.slider.value() / 100.0
        self.slider_label.setText(f"Premium Multiplier: {multiplier:.2f}x")

        self.ax.clear()  # Clear previous plot
        spot_range = np.linspace(max(0, min(strikes) - 50), max(strikes) + 50, 100)
        total_payoff = np.zeros_like(spot_range)

        for strike, premium, opt_type in zip(strikes, premiums, types):
            premium_adj = premium * multiplier
            if opt_type == "Call":
                payoff = np.maximum(0, spot_range - strike) - premium_adj
            else:
                payoff = np.maximum(0, strike - spot_range) - premium_adj
            total_payoff += payoff
            self.ax.plot(spot_range, payoff, label=f"{opt_type} (Strike: {strike}, Premium: {premium_adj:.2f})")

        self.ax.plot(spot_range, total_payoff, label="Total Payoff", linewidth=2, color='black')
        self.ax.axhline(0, color='gray', linestyle='--')
        self.ax.axvline(self._spot_price, color='red', linestyle='--', label='Spot Price')
        self.ax.set_xlabel("Underlying Price")
        self.ax.set_ylabel("Payoff")
        self.ax.set_title("Options Payoff Diagram")
        self.ax.legend()
        self.ax.grid(True)
        self.canvas.draw()

    def close_payoff_window(self, event: QEvent):
        """Clean up payoff window resources."""
        if self.payoff_window:
            try:
                self.slider.valueChanged.disconnect()
            except:
                pass  # Ignore if not connected
            plt.close(self.fig)  # Close matplotlib figure
            if hasattr(self, 'canvas'):
                self.canvas.deleteLater()  # Delete canvas
            self.payoff_window = None  # Clear reference
            del self._payoff_data
            gc.collect()
        event.accept()