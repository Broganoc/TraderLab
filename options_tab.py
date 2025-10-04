from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QTableWidget, QTableWidgetItem, QMessageBox, QCheckBox, QLineEdit,
    QGroupBox, QGridLayout
)
from PyQt6.QtCore import Qt
import pandas as pd
import datetime
import gc
import logging
from option_data import fetch_option_chain
from payoff_visualizer import PayoffVisualizer

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class OptionsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.current_ticker = None
        self.underlying_price = None
        self.risk_free_rate = 0.05  # Realistic default
        self.dividend_yield = None
        self.payoff_visualizer = None
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
        """Load expiration dates for the given ticker."""
        self.current_ticker = ticker
        try:
            stock = fetch_option_chain(ticker, get_stock=True)
            expirations = stock.options
            self.expiration_box.clear()
            self.expiration_box.addItems(expirations)
            info = stock.info
            self.underlying_price = info.get('currentPrice', 'N/A')
            self.dividend_yield = info.get('dividendYield', 0)
            self.ticker_info_label.setText(f"Underlying: {ticker} - Price: {self.underlying_price:.2f}")
            logger.debug(f"Loaded expirations for {ticker}: {expirations}")
        except Exception as e:
            logger.error(f"Error loading expirations for {ticker}: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load expirations for {ticker}: {str(e)}")
        finally:
            if 'stock' in locals():
                stock.session.close()

    def load_options(self):
        """Load options data for the selected expiration and option type."""
        if not self.current_ticker:
            logger.warning("No ticker selected")
            QMessageBox.warning(self, "No Ticker", "Please load a ticker first.")
            return

        exp = self.expiration_box.currentText()
        if not exp:
            logger.warning("No expiration date selected")
            QMessageBox.warning(self, "No Expiration", "Please select an expiration date.")
            return

        try:
            min_strike = float(self.strike_min.text()) if self.strike_min.text() else None
            max_strike = float(self.strike_max.text()) if self.strike_max.text() else None
            df = fetch_option_chain(
                self.current_ticker,
                expiration=exp,
                option_type=self.option_type.currentText(),
                min_strike=min_strike,
                max_strike=max_strike,
                sort_by=self.sort_box.currentText().lower().replace(" ", "")
            )
            if df is None or df.empty:
                logger.warning(f"No options data for {self.current_ticker} on {exp}")
                self.table.clear()
                self.table.setRowCount(0)
                self.table.setColumnCount(0)
                QMessageBox.warning(self, "Warning", f"No options data available for {self.current_ticker} on {exp}")
                return
            self.update_table(df)
            logger.debug(f"Loaded options for {self.current_ticker} on {exp}: {len(df)} rows")
        except Exception as e:
            logger.error(f"Error loading options for {self.current_ticker}: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load options: {str(e)}")

    def update_table(self, df):
        """Update the options table with the provided DataFrame."""
        try:
            if df is None or df.empty:
                self.table.clear()
                self.table.setRowCount(0)
                self.table.setColumnCount(0)
                logger.debug("No data to display in options table")
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
            logger.debug(f"Updated table with {len(df)} rows and {len(visible_cols)} columns")
        except Exception as e:
            logger.error(f"Error updating table: {e}")
            QMessageBox.critical(self, "Error", f"Failed to update options table: {str(e)}")

    def enable_payoff_button(self):
        """Enable the payoff button if a row is selected."""
        self.payoff_btn.setEnabled(bool(self.table.selectedItems()))

    def update_table_columns(self):
        """Reload options when column selection changes."""
        self.load_options()

    def buy_option(self):
        """Handle buying an option and updating the portfolio."""
        if not self.table.selectedItems():
            logger.warning("No option selected for purchase")
            QMessageBox.warning(self, "No Selection", "Select an option first.")
            return

        try:
            qty = int(self.option_quantity_edit.text())
            if qty <= 0:
                raise ValueError("Quantity must be positive")
        except ValueError:
            logger.error("Invalid quantity entered")
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
            logger.error("Missing option details for purchase")
            QMessageBox.warning(self, "Error", "Could not extract option details.")
            return

        try:
            strike = float(strike_item.text())
            option_type = type_item.text()
            premium = float(premium_item.text())
            expiry = self.expiration_box.currentText()
        except ValueError:
            logger.error("Invalid option details for purchase")
            QMessageBox.warning(self, "Error", "Invalid option details.")
            return

        total_cost = qty * premium * 100  # Options are priced per contract (100 shares)
        trade_tab = self.parent_window.trade_simulator_tab

        if total_cost > trade_tab.cash_balance:
            logger.warning(f"Insufficient funds: {total_cost} > {trade_tab.cash_balance}")
            QMessageBox.warning(
                self, "Insufficient Funds",
                f"You need ${total_cost:,.2f} but only have ${trade_tab.cash_balance:,.2f}."
            )
            return

        # Display confirmation dialog
        confirmation_msg = (
            f"Please confirm your option purchase:\n\n"
            f"Ticker: {self.current_ticker}\n"
            f"Option Type: {option_type}\n"
            f"Strike Price: ${strike:.2f}\n"
            f"Quantity: {qty} contracts\n"
            f"Premium per Contract: ${premium:.2f}\n"
            f"Total Cost: ${total_cost:,.2f}\n"
            f"Cash Balance After: ${(trade_tab.cash_balance - total_cost):,.2f}\n"
            f"Expiration: {expiry}"
        )
        reply = QMessageBox.question(
            self, "Confirm Option Purchase", confirmation_msg,
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )

        if reply == QMessageBox.StandardButton.Ok:
            position = {
                "ticker": self.current_ticker,
                "strike": strike,
                "opt_type": option_type,
                "quantity": qty,
                "buy_premium": premium,
                "expiry": expiry,
                "buy_date": datetime.date.today()
            }
            self.parent_window.portfolio.append(position)
            trade_tab.cash_balance -= total_cost
            QMessageBox.information(self, "Bought", f"{qty} {option_type} option(s) bought for {self.current_ticker}")
            trade_tab.load_portfolio()
            gc.collect()
            logger.debug(f"Purchased {qty} {option_type} options for {self.current_ticker}, strike={strike}")
        else:
            logger.debug("Option purchase cancelled")
            QMessageBox.information(self, "Cancelled", "Option purchase cancelled.")

    def show_payoff_diagram(self):
        """Show the payoff diagram for the selected option."""
        if not self.table.selectedItems():
            logger.warning("No option selected for payoff diagram")
            QMessageBox.warning(self, "No Selection", "Select an option first.")
            return

        row = self.table.currentRow()
        strike_item = self.table.item(row, 1)
        type_item = self.table.item(row, 0)
        premium_item = None
        vol_item = None
        for col in range(self.table.columnCount()):
            header = self.table.horizontalHeaderItem(col).text().lower()
            if "last price" in header:
                premium_item = self.table.item(row, col)
            if "implied volatility" in header:
                vol_item = self.table.item(row, col)

        if not (strike_item and type_item and premium_item):
            logger.error("Missing option details for payoff diagram")
            QMessageBox.warning(self, "Error", "Could not extract option details.")
            return

        try:
            strike = float(strike_item.text())
            option_type = type_item.text()
            premium = float(premium_item.text())
            expiry_str = self.expiration_box.currentText()
            expiry_date = datetime.datetime.strptime(expiry_str, '%Y-%m-%d').date()
            current_date = datetime.date.today()
            initial_days = max(0, (expiry_date - current_date).days)
            sigma = float(vol_item.text().rstrip('%')) / 100 if vol_item and vol_item.text().rstrip('%') else 0.2
            if not vol_item:
                logger.warning("Implied Volatility not found, using default 20%")
                QMessageBox.warning(self, "Warning", "Implied Volatility not found. Using default 20%.")
        except ValueError as e:
            logger.error(f"Invalid option details for payoff diagram: {e}")
            QMessageBox.warning(self, "Error", "Invalid option details.")
            return

        try:
            self.payoff_visualizer = PayoffVisualizer(
                ticker=self.current_ticker,
                underlying_price=self.underlying_price,
                strike=strike,
                option_type=option_type,
                premium=premium,
                initial_days=initial_days,
                sigma=sigma,
                risk_free_rate=self.risk_free_rate,
                dividend_yield=self.dividend_yield
            )
            self.payoff_visualizer.show()
            logger.debug(f"Opened PayoffVisualizer for {self.current_ticker}, {option_type}, strike={strike}")
        except Exception as e:
            logger.error(f"Error opening payoff visualizer: {e}")
            QMessageBox.critical(self, "Error", f"Failed to show payoff diagram: {str(e)}")