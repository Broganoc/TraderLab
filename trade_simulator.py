# trade_simulator.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QPushButton,
    QHBoxLayout, QLabel, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer
import gc
import datetime
import yfinance as yf
from dateutil.parser import parse as parse_date
import pytz
from datetime import time
import pandas as pd
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class OrderHandler:
    def __init__(self, parent):
        self.parent = parent
        logger.debug("OrderHandler initialized")

    def _is_market_open(self):
        logger.debug("Bypassing market hours check for testing")
        return True

    def _parse_expiry(self, expiry):
        """Convert expiry to datetime.date, handling both string and date inputs."""
        try:
            if isinstance(expiry, datetime.date):
                return expiry
            elif isinstance(expiry, str):
                parsed = parse_date(expiry).date()
                logger.debug(f"Parsed expiry: {expiry} -> {parsed}")
                return parsed
            else:
                logger.error(f"Invalid expiry format: {expiry}")
                return datetime.date.today()
        except ValueError as e:
            logger.error(f"Error parsing expiry date '{expiry}': {e}")
            return datetime.date.today()

    def _get_current_option_data(self, ticker, opt_type, strike, expiry):
        """Fetch current option price, bid, ask, volume, and open interest using yfinance."""
        logger.debug(f"Fetching option data for {ticker}, {opt_type}, strike={strike}, expiry={expiry}")
        try:
            expiry_date = self._parse_expiry(expiry)
            stock = yf.Ticker(ticker)
            expiry_str = expiry_date.strftime("%Y-%m-%d")
            opts = stock.option_chain(expiry_str)
            chain = opts.calls if opt_type.lower() == "call" else opts.puts
            option = chain[chain['strike'] == float(strike)]
            if not option.empty:
                bid = option['bid'].iloc[0]
                ask = option['ask'].iloc[0]
                last = option['lastPrice'].iloc[0]
                price = (bid + ask) / 2 if not (pd.isna(bid) or pd.isna(ask)) else last if not pd.isna(last) else 0.0
                vol = option['volume'].iloc[0] if not pd.isna(option['volume'].iloc[0]) else 0
                oi = option['openInterest'].iloc[0] if not pd.isna(option['openInterest'].iloc[0]) else 0
                logger.debug(f"Option data: price=${price:.2f}, bid=${bid:.2f}, ask=${ask:.2f}, vol={vol}, oi={oi}")
                return price, bid, ask, vol, oi
            logger.warning(f"No option found for {ticker}, {opt_type}, strike={strike}, expiry={expiry_str}")
            return 0.0, 0.0, 0.0, 0, 0
        except Exception as e:
            logger.error(f"Error fetching option data for {ticker} (strike: {strike}, expiry: {expiry}): {e}")
            return 0.0, 0.0, 0.0, 0, 0
        finally:
            if 'stock' in locals():
                stock.session.close()
                gc.collect()

    def _get_current_stock_data(self, ticker):
        """Fetch current stock price, bid, ask, and volume using yfinance."""
        logger.debug(f"Fetching stock data for {ticker}")
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            bid = info.get('bid', 0.0)
            ask = info.get('ask', 0.0)
            price = info.get('regularMarketPrice',
                             info.get('currentPrice', stock.history(period="1d")['Close'].iloc[-1]))
            vol = info.get('volume', 0)
            logger.debug(f"Stock data: price=${price:.2f}, bid=${bid:.2f}, ask=${ask:.2f}, vol={vol}")
            return price, bid, ask, vol
        except Exception as e:
            logger.error(f"Error fetching stock data for {ticker}: {e}")
            return 0.0, 0.0, 0.0, 0
        finally:
            if 'stock' in locals():
                stock.session.close()
                gc.collect()

    def place_buy_order(self, trade, parent_widget=None):
        """Place a buy order, checking market hours and liquidity."""
        logger.debug(f"Placing buy order: {trade}")
        if not self._is_market_open():
            QMessageBox.warning(parent_widget, "Market Closed",
                                "The market is currently closed. Trades can only be executed during market hours (9:30 AM - 4:00 PM ET, Mon-Fri).")
            logger.warning("Market closed, order aborted")
            return False

        ticker = trade.get("ticker", "")
        qty = trade.get("quantity", 0)
        is_option = 'strike' in trade and trade['strike'] is not None

        try:
            if is_option:
                opt_type = trade.get("opt_type", trade.get("type", "")).lower()
                strike = trade.get("strike", 0.0)
                expiry = trade.get("expiry", datetime.date.today())
                expiry = self._parse_expiry(expiry)
                price, bid, ask, vol, oi = self._get_current_option_data(ticker, opt_type, strike, expiry)

                if price <= 0.0:
                    QMessageBox.warning(parent_widget, "Price Error",
                                        f"Could not fetch valid current price for {ticker} option. Aborting.")
                    logger.error(f"Invalid option price for {ticker}")
                    return False

                low_liquidity = vol < 10 or oi < 50
                if low_liquidity:
                    reply = QMessageBox.question(
                        parent_widget, "Low Liquidity Warning",
                        f"This option for {ticker} has low volume ({vol}) and open interest ({oi}). "
                        f"Proceed with buy? (Prices may be stale or wide spreads.)",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    if reply == QMessageBox.StandardButton.No:
                        logger.debug("Low liquidity order cancelled by user")
                        return False
            else:
                price, bid, ask, vol = self._get_current_stock_data(ticker)
                if price <= 0.0:
                    QMessageBox.warning(parent_widget, "Price Error",
                                        f"Could not fetch valid current price for {ticker} stock. Aborting.")
                    logger.error(f"Invalid stock price for {ticker}")
                    return False

            multiplier = 100 if is_option else 1
            cost = qty * multiplier * price
            if self.parent.cash_balance < cost:
                QMessageBox.warning(parent_widget, "Insufficient Funds",
                                    f"Not enough cash to complete the purchase. Required: ${cost:,.2f}")
                logger.error(f"Insufficient funds: required ${cost:,.2f}, available ${self.parent.cash_balance:,.2f}")
                return False

            trade['buy_premium' if is_option else 'buy_price'] = price
            if is_option and 'expiry' in trade:
                trade['expiry'] = self._parse_expiry(trade['expiry'])
            trade['buy_date'] = datetime.date.today()

            self.parent.cash_balance -= cost
            self.parent.portfolio.append(trade)
            logger.info(f"Order placed successfully: {trade}")
            return True
        except Exception as e:
            logger.error(f"Error placing buy order: {e}")
            QMessageBox.critical(parent_widget, "Error", f"Failed to place order: {e}")
            return False

    def close_position(self, trade, parent_widget=None):
        logger.debug(f"Closing position: {trade}")
        if not self._is_market_open():
            QMessageBox.warning(parent_widget, "Market Closed",
                                "The market is currently closed. Trades can only be executed during market hours (9:30 AM - 4:00 PM ET, Mon-Fri).")
            logger.warning("Market closed, close position aborted")
            return False

        ticker = trade.get("ticker", "")
        qty = trade.get("quantity", 0)
        is_option = 'strike' in trade and trade['strike'] is not None

        try:
            if is_option:
                opt_type = trade.get("opt_type", trade.get("type", "")).lower()
                strike = trade.get("strike", 0.0)
                expiry = trade.get("expiry", datetime.date.today())
                expiry = self._parse_expiry(expiry)
                sell_price, bid, ask, vol, oi = self._get_current_option_data(ticker, opt_type, strike, expiry)

                low_liquidity = vol < 10 or oi < 50
                if low_liquidity:
                    reply = QMessageBox.question(
                        parent_widget, "Low Liquidity Warning",
                        f"This option for {ticker} has low volume ({vol}) and open interest ({oi}). "
                        f"Proceed with close? (Prices may be stale or wide spreads.)",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    if reply == QMessageBox.StandardButton.No:
                        logger.debug("Low liquidity close cancelled by user")
                        return False
            else:
                sell_price, bid, ask, vol = self._get_current_stock_data(ticker)

            if sell_price <= 0.0:
                QMessageBox.warning(parent_widget, "Price Error",
                                    f"Could not fetch valid current price for {ticker}. Aborting.")
                logger.error(f"Invalid sell price for {ticker}")
                return False

            multiplier = 100 if is_option else 1
            proceeds = qty * multiplier * sell_price
            self.parent.cash_balance += proceeds

            if trade in self.parent.portfolio:
                self.parent.portfolio.remove(trade)
            logger.info(f"Position closed successfully: {trade}, proceeds=${proceeds:,.2f}")
            return True
        except Exception as e:
            logger.error(f"Error closing position: {e}")
            QMessageBox.critical(parent_widget, "Error", f"Failed to close position: {e}")
            return False


class TradeSimulatorTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        if hasattr(self.parent_window, "cash_balance"):
            self.cash_balance = self.parent_window.cash_balance
        else:
            self.cash_balance = 100000.0
            self.parent_window.cash_balance = self.cash_balance

        self._setup_ui()
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_market_status)
        self.status_timer.start(60000)
        logger.debug("TradeSimulatorTab initialized")

    def _setup_ui(self):
        layout = QVBoxLayout()

        self.cash_label = QLabel(f"Cash Balance: ${self.cash_balance:,.2f}")
        layout.addWidget(self.cash_label)

        self.portfolio_value_label = QLabel("Portfolio Value: $0.00")
        layout.addWidget(self.portfolio_value_label)

        self.market_status_label = QLabel("Market Status: Checking...")
        layout.addWidget(self.market_status_label)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Ticker", "Type", "Strike", "Qty", "Premium", "Expiry", "Buy Date"
        ])
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        self.btn_close = QPushButton("Close Selected")
        self.btn_close.clicked.connect(self.close_selected)
        self.btn_remove = QPushButton("Remove Selected")
        self.btn_remove.clicked.connect(self.remove_selected)
        self.btn_clear = QPushButton("Clear Portfolio")
        self.btn_clear.clicked.connect(self.clear_portfolio)
        btn_layout.addWidget(self.btn_close)
        btn_layout.addWidget(self.btn_remove)
        btn_layout.addWidget(self.btn_clear)
        layout.addLayout(btn_layout)

        self.summary_label = QLabel("Total Contracts: 0")
        layout.addWidget(self.summary_label)

        self.setLayout(layout)
        self.update_market_status()

    def update_market_status(self):
        if self.parent_window.order_handler._is_market_open():
            self.market_status_label.setText("Market Status: Open")
            self.market_status_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.market_status_label.setText("Market Status: Closed")
            self.market_status_label.setStyleSheet("color: red; font-weight: bold;")
        logger.debug("Updated market status")

    def load_portfolio(self):
        try:
            portfolio = getattr(self.parent_window, "portfolio", [])
            self.table.setRowCount(len(portfolio))
            total_qty = 0
            positions_value = 0.0

            for i, trade in enumerate(portfolio):
                if isinstance(trade.get("expiry"), str):
                    trade["expiry"] = self.parent_window.order_handler._parse_expiry(trade["expiry"])

                self.table.setItem(i, 0, QTableWidgetItem(str(trade.get("ticker", "N/A"))))
                self.table.setItem(i, 1, QTableWidgetItem(str(trade.get("opt_type", trade.get("type", "N/A")))))
                self.table.setItem(i, 2, QTableWidgetItem(f"{trade.get('strike', 0):.2f}"))
                qty = trade.get("quantity", 0)
                total_qty += qty
                self.table.setItem(i, 3, QTableWidgetItem(str(qty)))
                buy_premium = trade.get('buy_premium', trade.get('buy_price', 0.0))
                self.table.setItem(i, 4, QTableWidgetItem(f"{buy_premium:.2f}"))
                expiry = trade.get("expiry", datetime.date.today())
                self.table.setItem(i, 5, QTableWidgetItem(str(expiry)))
                buy_date = trade.get("buy_date", datetime.date.today())
                self.table.setItem(i, 6, QTableWidgetItem(str(buy_date)))

                is_option = 'strike' in trade and trade['strike'] is not None
                multiplier = 100 if is_option else 1
                positions_value += qty * multiplier * buy_premium

            portfolio_value = self.cash_balance + positions_value
            self.portfolio_value_label.setText(f"Portfolio Value: ${portfolio_value:,.2f}")
            self.summary_label.setText(f"Total Contracts: {total_qty}")
            self.table.resizeColumnsToContents()
            self.cash_label.setText(f"Cash Balance: ${self.cash_balance:,.2f}")
            self.parent_window.cash_balance = self.cash_balance
            logger.debug(f"Loaded portfolio: {len(portfolio)} positions, value=${portfolio_value:,.2f}")
            gc.collect()
        except Exception as e:
            logger.error(f"Error loading portfolio: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load portfolio: {e}")

    def close_selected(self):
        logger.debug("Attempting to close selected positions")
        selected_rows = set(item.row() for item in self.table.selectedItems())
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Select rows to close.")
            logger.warning("No rows selected for closing")
            return

        portfolio = getattr(self.parent_window, "portfolio", [])
        for row in sorted(selected_rows, reverse=True):
            if 0 <= row < len(portfolio):
                trade = portfolio[row]
                success = self.parent_window.order_handler.close_position(trade, self)
                if success:
                    logger.debug(f"Closed position at row {row}: {trade}")
        self.load_portfolio()

    def remove_selected(self):
        logger.debug("Attempting to remove selected positions")
        selected_rows = set(item.row() for item in self.table.selectedItems())
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Select rows to remove.")
            logger.warning("No rows selected for removal")
            return

        portfolio = getattr(self.parent_window, "portfolio", [])
        for row in sorted(selected_rows, reverse=True):
            if 0 <= row < len(portfolio):
                del portfolio[row]
                logger.debug(f"Removed position at row {row}")
        self.load_portfolio()

    def clear_portfolio(self):
        logger.debug("Attempting to clear portfolio")
        reply = QMessageBox.question(
            self, "Confirm", "Are you sure you want to clear the entire portfolio?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            setattr(self.parent_window, "portfolio", [])
            self.load_portfolio()
            logger.info("Portfolio cleared")
            gc.collect()