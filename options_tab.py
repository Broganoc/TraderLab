# options_tab.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QTableWidget, QTableWidgetItem, QMessageBox, QCheckBox, QLineEdit,
    QSlider, QGroupBox, QGridLayout
)
from PyQt6.QtCore import Qt, QEvent
import yfinance as yf
import pandas as pd
import numpy as np
import datetime
from scipy.stats import norm
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
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
        self.payoff_window = None
        self._payoff_data = None

        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout()
        control_layout = QHBoxLayout()

        # Ticker info
        self.ticker_info_label = QLabel("Underlying: No data")
        self.ticker_info_label.setStyleSheet("font-size: 14px; padding: 5px;")

        # Expiration dropdown
        self.expiration_box = QComboBox()

        # Option type
        self.option_type = QComboBox()
        self.option_type.addItems(["Calls", "Puts", "Both"])
        self.option_type.currentTextChanged.connect(self.load_options)

        # Strike filter
        self.strike_min = QLineEdit()
        self.strike_min.setPlaceholderText("Min Strike")
        self.strike_max = QLineEdit()
        self.strike_max.setPlaceholderText("Max Strike")

        # Sort
        self.sort_box = QComboBox()
        self.sort_box.addItems(["Strike", "Volume", "Open Interest", "Implied Volatility"])

        # Refresh / Payoff buttons
        self.refresh_btn = QPushButton("Refresh Options")
        self.refresh_btn.clicked.connect(self.load_options)
        self.payoff_btn = QPushButton("Show Payoff Diagram")
        self.payoff_btn.clicked.connect(self.show_payoff_diagram)
        self.payoff_btn.setEnabled(False)

        # Column selection
        self.column_checks = {}
        columns = ["strike", "lastPrice", "bid", "ask", "volume", "openInterest",
                   "impliedVolatility", "delta", "gamma", "theta"]
        columns_layout = QHBoxLayout()
        columns_layout.addWidget(QLabel("Select Columns:"))
        for col in columns:
            chk = QCheckBox(col.capitalize())
            chk.setChecked(True)
            chk.stateChanged.connect(self.update_table_columns)
            self.column_checks[col] = chk
            columns_layout.addWidget(chk)

        # Table
        self.table = QTableWidget()
        self.table.itemSelectionChanged.connect(self.enable_payoff_button)

        # Purchase section
        purchase_group = QGroupBox("Purchase Option")
        purchase_layout = QHBoxLayout()
        self.option_quantity_edit = QLineEdit()
        self.option_quantity_edit.setPlaceholderText("Quantity")
        self.option_quantity_edit.setFixedWidth(100)
        purchase_layout.addWidget(QLabel("Contracts:"))
        purchase_layout.addWidget(self.option_quantity_edit)
        btn_buy_option = QPushButton("Buy Option")
        btn_buy_option.clicked.connect(self.buy_option)
        purchase_layout.addWidget(btn_buy_option)
        purchase_group.setLayout(purchase_layout)

        # Assemble layouts
        control_layout.addWidget(QLabel("Expiration:"))
        control_layout.addWidget(self.expiration_box)
        control_layout.addWidget(self.option_type)
        control_layout.addWidget(QLabel("Strike Range:"))
        control_layout.addWidget(self.strike_min)
        control_layout.addWidget(self.strike_max)
        control_layout.addWidget(QLabel("Sort By:"))
        control_layout.addWidget(self.sort_box)
        control_layout.addWidget(self.refresh_btn)
        control_layout.addWidget(self.payoff_btn)

        main_layout.addWidget(self.ticker_info_label)
        main_layout.addLayout(control_layout)
        main_layout.addLayout(columns_layout)
        main_layout.addWidget(self.table)
        main_layout.addWidget(purchase_group)
        self.setLayout(main_layout)

    def load_expirations(self, ticker):
        self.current_ticker = ticker
        try:
            stock = yf.Ticker(ticker)
            expirations = stock.options
            self.expiration_box.clear()
            self.expiration_box.addItems(expirations)
            info = stock.info
            self.underlying_price = info.get('currentPrice', 'N/A')
            self.risk_free_rate = 0.01  # Dummy value
            self.dividend_yield = info.get('dividendYield', 0)
            self.ticker_info_label.setText(f"Underlying: {ticker} - Price: {self.underlying_price:.2f}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load expirations for {ticker}: {e}")
        finally:
            if 'stock' in locals():
                stock.session.close()

    # ------------------------- Core Logic -------------------------

    def load_options(self):
        if not self.current_ticker:
            QMessageBox.warning(self, "No Ticker", "Please load a ticker first.")
            return

        exp = self.expiration_box.currentText()
        if not exp:
            QMessageBox.warning(self, "No Expiration", "Please select an expiration date.")
            return

        df = None
        try:
            stock = yf.Ticker(self.current_ticker)
            chain = stock.option_chain(exp)
            opt_type = self.option_type.currentText()
            if opt_type == "Calls":
                df = chain.calls.assign(Type="Call")
            elif opt_type == "Puts":
                df = chain.puts.assign(Type="Put")
            else:
                df = pd.concat([chain.calls.assign(Type="Call"), chain.puts.assign(Type="Put")])

            # Strike filter
            if self.strike_min.text():
                df = df[df["strike"] >= float(self.strike_min.text())]
            if self.strike_max.text():
                df = df[df["strike"] <= float(self.strike_max.text())]

            # Sort
            sort_key = self.sort_box.currentText().lower().replace(" ", "")
            if sort_key == "openinterest": sort_key = "openInterest"
            if sort_key == "impliedvolatility": sort_key = "impliedVolatility"
            if sort_key not in df.columns:
                sort_key = "strike"
            df = df.sort_values(by=sort_key, ascending=True).head(50)

            self.update_table(df)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load options: {e}")
        finally:
            if df is not None: del df
            if 'stock' in locals(): stock.session.close()
            gc.collect()

    def update_table(self, df):
        if df is None or df.empty:
            self.table.clear()
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
            return

        all_cols = ["Type", "strike", "lastPrice", "bid", "ask", "volume",
                    "openInterest", "impliedVolatility", "delta", "gamma", "theta"]
        visible_cols = ["Type"] + [c for c in all_cols[1:] if self.column_checks.get(c, QCheckBox()).isChecked() and c in df.columns]

        self.table.setRowCount(len(df))
        self.table.setColumnCount(len(visible_cols))
        self.table.setHorizontalHeaderLabels([c.replace("lastPrice", "Last Price")
                                              .replace("openInterest", "Open Interest")
                                              .replace("impliedVolatility", "Implied Volatility")
                                              .capitalize() for c in visible_cols])

        for i, row in df.iterrows():
            for j, col in enumerate(visible_cols):
                value = row.get(col, "N/A")
                if isinstance(value, float):
                    if col in ["strike", "lastPrice", "bid", "ask"]:
                        value = f"{value:.2f}"
                    elif col == "impliedVolatility":
                        value = f"{value*100:.2f}%"
                    else:
                        value = f"{value:.4f}" if not pd.isna(value) else "N/A"
                self.table.setItem(i, j, QTableWidgetItem(str(value)))

        self.table.resizeColumnsToContents()

    def enable_payoff_button(self):
        self.payoff_btn.setEnabled(bool(self.table.selectedItems()))

    def update_table_columns(self):
        self.load_options()

    def buy_option(self):
        if not self.table.selectedItems():
            QMessageBox.warning(self, "No Selection", "Select an option first.")
            return

        try:
            qty = int(self.option_quantity_edit.text())
            if qty <= 0:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "Error", "Quantity must be a positive integer.")
            return

        row = self.table.currentRow()
        strike_item = self.table.item(row, 1)
        type_item = self.table.item(row, 0)
        premium_item = None
        for col in range(self.table.columnCount()):
            header = self.table.horizontalHeaderItem(col).text().lower()
            if "last price" in header:
                premium_item = self.table.item(row, col)

        if not (strike_item and type_item and premium_item):
            QMessageBox.warning(self, "Error", "Could not extract option details.")
            return

        position = {
            "ticker": self.current_ticker,
            "strike": float(strike_item.text()),
            "opt_type": type_item.text(),
            "quantity": qty,
            "buy_premium": float(premium_item.text()),
            "expiry": self.expiration_box.currentText(),
            "buy_date": datetime.date.today()
        }
        self.parent_window.portfolio.append(position)
        QMessageBox.information(self, "Bought", f"{qty} {type_item.text()} option(s) bought for {self.current_ticker}")
        self.parent_window.trade_simulator_tab.load_portfolio()
        gc.collect()

    # ------------------------- Safe Payoff Diagram -------------------------

    def show_payoff_diagram(self):
        if not self.table.selectedItems():
            QMessageBox.warning(self, "No Selection", "Select an option first.")
            return

        row = self.table.currentRow()
        strike_item = self.table.item(row, 1)
        type_item = self.table.item(row, 0)
        premium_item = None
        for col in range(self.table.columnCount()):
            header = self.table.horizontalHeaderItem(col).text().lower()
            if "last price" in header:
                premium_item = self.table.item(row, col)
        if not (strike_item and type_item and premium_item):
            QMessageBox.warning(self, "Error", "Could not extract option details.")
            return

        try:
            strike = float(strike_item.text())
            option_type = type_item.text()
            premium = float(premium_item.text())
        except ValueError:
            QMessageBox.warning(self, "Error", "Invalid option details.")
            return

        prices = np.linspace(max(0, strike - 50), strike + 50, 100)
        payoffs = [max(0, price - strike) - premium if option_type == "Call" else max(0, strike - price) - premium for price in prices]

        if self.payoff_window is None:
            self.payoff_window = QWidget()
            self.payoff_window.setWindowTitle(f"Payoff – {self.current_ticker}")
            layout = QVBoxLayout(self.payoff_window)
            self.fig, self.ax = plt.subplots(figsize=(8, 5))
            self.canvas = FigureCanvas(self.fig)
            layout.addWidget(self.canvas)
            self.payoff_window.resize(900, 700)
            self.payoff_window.closeEvent = self.close_payoff_window

        self.ax.clear()
        self.ax.plot(prices, payoffs, label=f"{option_type} Payoff (Strike: {strike})")
        self.ax.set_xlabel("Underlying Price")
        self.ax.set_ylabel("Payoff")
        self.ax.set_title(f"{option_type} Option Payoff")
        self.ax.legend()
        self.canvas.draw()
        self.payoff_window.show()

    def close_payoff_window(self, event: QEvent):
        if self.payoff_window:
            try:
                if hasattr(self, 'canvas') and self.canvas:
                    self.canvas.setParent(None)
                    self.canvas.deleteLater()
                if hasattr(self, 'fig') and self.fig:
                    plt.close(self.fig)
                self.payoff_window = None
                if hasattr(self, '_payoff_data'): del self._payoff_data
                gc.collect()
            except Exception:
                pass
        event.accept()