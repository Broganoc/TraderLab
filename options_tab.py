# options_tab.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QTableWidget, QTableWidgetItem, QMessageBox, QCheckBox, QLineEdit,
    QGroupBox, QDialog  # Added QDialog import
)
from PyQt6.QtCore import Qt
import pandas as pd
import datetime
import gc
import logging
from option_data import fetch_option_chain
from payoff_visualizer import PayoffVisualizer
from dateutil.parser import parse as parse_date
from order_preview import OrderPreviewDialog

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class OptionsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.current_ticker = None
        self.underlying_price = None
        self.risk_free_rate = 0.05
        self.dividend_yield = None
        self.payoff_visualizer = None
        self._setup_ui()
        logger.debug("OptionsTab initialized")

    def _setup_ui(self):
        main_layout = QVBoxLayout()
        control_layout = QHBoxLayout()

        self.ticker_info_label = QLabel("Underlying: No data")
        self.ticker_info_label.setStyleSheet("font-size: 14px; padding: 5px;")

        self.expiration_box = QComboBox()
        self.option_type = QComboBox()
        self.option_type.addItems(["Calls", "Puts", "Both"])
        self.option_type.currentTextChanged.connect(self.load_options)

        self.strike_min = QLineEdit()
        self.strike_min.setPlaceholderText("Min Strike")
        self.strike_max = QLineEdit()
        self.strike_max.setPlaceholderText("Max Strike")

        self.sort_box = QComboBox()
        self.sort_box.addItems(["Strike", "Volume", "Open Interest", "Implied Volatility"])

        self.refresh_btn = QPushButton("Refresh Options")
        self.refresh_btn.clicked.connect(self.load_options)
        self.payoff_btn = QPushButton("Show Payoff Diagram")
        self.payoff_btn.clicked.connect(self.show_payoff_diagram)
        self.payoff_btn.setEnabled(False)

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

        self.table = QTableWidget()
        self.table.itemSelectionChanged.connect(self.enable_payoff_button)

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
                gc.collect()

    def load_options(self):
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
        self.payoff_btn.setEnabled(bool(self.table.selectedItems()))

    def update_table_columns(self):
        self.load_options()

    def buy_option(self):
        logger.debug("Attempting to buy option")
        if not self.table.selectedItems():
            logger.warning("No option selected for purchase")
            QMessageBox.warning(self, "No Selection", "Select an option first.")
            return

        try:
            qty = int(self.option_quantity_edit.text())
            if qty <= 0:
                raise ValueError("Quantity must be positive")
        except ValueError as e:
            logger.error(f"Invalid quantity entered: {e}")
            QMessageBox.warning(self, "Error", "Quantity must be a positive integer.")
            return

        try:
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

            strike = float(strike_item.text())
            option_type = type_item.text()
            expiry = self.expiration_box.currentText()
            expiry_date = parse_date(expiry).date()
            logger.debug(f"Option details: {self.current_ticker}, {option_type}, strike={strike}, expiry={expiry}")

            # Fetch data for preview
            opt_type_lower = option_type.lower()
            price, bid, ask, vol, oi = self.parent_window.order_handler._get_current_option_data(self.current_ticker, opt_type_lower, strike, expiry_date)
            logger.debug(f"Fetched option data: price=${price:.2f}, bid=${bid:.2f}, ask=${ask:.2f}, vol={vol}, oi={oi}")
            if price <= 0.0:
                QMessageBox.warning(self, "Price Error", f"Could not fetch current price for option.")
                logger.error(f"Invalid option price for {self.current_ticker}")
                return

            trade = {
                "ticker": self.current_ticker,
                "opt_type": option_type,
                "strike": strike,
                "quantity": qty,
                "expiry": expiry_date,
                "buy_date": datetime.date.today()
            }

            # Show preview dialog
            logger.debug("Opening OrderPreviewDialog for option")
            dialog = OrderPreviewDialog(self, trade, price, bid, ask, vol, oi, True)
            try:
                result = dialog.exec()
                logger.debug(f"OrderPreviewDialog result: {result}")
                if result == QDialog.DialogCode.Accepted:
                    edited_trade = dialog.get_edited_trade()
                    if edited_trade:
                        success = self.parent_window.order_handler.place_buy_order(edited_trade, self)
                        if success:
                            QMessageBox.information(self, "Success", f"Bought {edited_trade['quantity']} {option_type} option(s) for {self.current_ticker} at ${edited_trade.get('buy_premium', 0.0):.2f}.")
                            self.parent_window.trade_simulator_tab.load_portfolio()
                            logger.info(f"Successfully bought {edited_trade['quantity']} {option_type} options for {self.current_ticker}")
                        else:
                            logger.error("Option order placement failed")
                    else:
                        logger.warning("No valid trade returned from OrderPreviewDialog")
                else:
                    logger.debug("Option order preview cancelled")
            except Exception as e:
                logger.error(f"Error executing OrderPreviewDialog: {e}")
                QMessageBox.critical(self, "Error", f"Failed to execute order preview: {e}")
            finally:
                dialog.deleteLater()  # Ensure dialog is cleaned up
                gc.collect()
        except Exception as e:
            logger.error(f"Error in buy_option: {e}")
            QMessageBox.critical(self, "Error", f"Failed to place option order: {e}")

    def show_payoff_diagram(self):
        logger.debug("Attempting to show payoff diagram")
        if not self.table.selectedItems():
            logger.warning("No option selected for payoff diagram")
            QMessageBox.warning(self, "No Selection", "Select an option first.")
            return

        try:
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

            strike = float(strike_item.text())
            option_type = type_item.text()
            premium = float(premium_item.text())
            expiry_str = self.expiration_box.currentText()
            expiry_date = parse_date(expiry_str).date()
            current_date = datetime.date.today()
            initial_days = max(0, (expiry_date - current_date).days)
            sigma = float(vol_item.text().rstrip('%')) / 100 if vol_item and vol_item.text().rstrip('%') else 0.2
            if not vol_item:
                logger.warning("Implied Volatility not found, using default 20%")
                QMessageBox.warning(self, "Warning", "Implied Volatility not found. Using default 20%.")

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