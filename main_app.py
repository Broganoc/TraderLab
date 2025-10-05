# main_app.py
import sys
import datetime
import numpy as np
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget,
    QVBoxLayout, QPushButton, QLineEdit, QLabel,
    QGridLayout, QGroupBox, QHBoxLayout, QComboBox,
    QMessageBox, QDialog  # Added QDialog import
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QTimer
from data_fetcher import fetch_historical, fetch_summary
from chart_builder import get_chart_html
from options_tab import OptionsTab
from trade_simulator import TradeSimulatorTab, OrderHandler
from order_preview import OrderPreviewDialog
import logging
import gc

# Configure logging
logging.basicConfig(level=logging.DEBUG, filename='traderlab.log', filemode='w')
logger = logging.getLogger(__name__)

class LookupTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        layout = QVBoxLayout()

        # Input + Button
        self.ticker_input = QLineEdit()
        self.ticker_input.setPlaceholderText("Enter ticker e.g. AAPL")
        btn = QPushButton("Search")
        btn.clicked.connect(self.load_ticker)
        layout.addWidget(self.ticker_input)
        layout.addWidget(btn)

        # Info Card
        self.info_group = QGroupBox("Company Information")
        self.info_layout = QGridLayout()
        self.labels = {}
        fields = [
            "Symbol", "Name", "Sector", "Industry", "Market Cap",
            "Current Price", "PE Ratio (TTM)", "EPS (TTM)", "Dividend Yield",
            "52-Week High", "52-Week Low", "Website"
        ]
        for i, field in enumerate(fields):
            lbl_field = QLabel(f"{field}:")
            lbl_field.setStyleSheet("font-weight: bold;")
            lbl_value = QLabel("N/A")
            self.labels[field] = lbl_value
            self.info_layout.addWidget(lbl_field, i, 0)
            self.info_layout.addWidget(lbl_value, i, 1)

        self.info_group.setLayout(self.info_layout)
        layout.addWidget(self.info_group)

        # Purchase section
        purchase_group = QGroupBox("Purchase Stock")
        purchase_layout = QHBoxLayout()
        self.quantity_edit = QLineEdit()
        self.quantity_edit.setPlaceholderText("Quantity (e.g., 100)")
        self.quantity_edit.setFixedWidth(100)
        purchase_layout.addWidget(QLabel("Quantity:"))
        purchase_layout.addWidget(self.quantity_edit)
        btn_buy = QPushButton("Buy Stock")
        btn_buy.clicked.connect(self.buy_stock)
        purchase_layout.addWidget(btn_buy)
        purchase_group.setLayout(purchase_layout)
        layout.addWidget(purchase_group)

        self.setLayout(layout)

    def load_ticker(self):
        tk = self.ticker_input.text().strip().upper()
        if not tk:
            QMessageBox.warning(self, "Error", "Please enter a ticker symbol.")
            return

        try:
            df = fetch_historical(tk, period="3mo", interval="1d")
            if df.empty:
                self.labels["Name"].setText("No data found")
                return

            summary = fetch_summary(tk)
            for key, lbl in self.labels.items():
                lbl.setText(str(summary.get(key, "N/A")))

            # Update parent ticker and other tabs
            if self.parent_window:
                self.parent_window.current_ticker = tk
                QTimer.singleShot(0, self.parent_window.charts_tab.load_chart)
                self.parent_window.options_tab.load_expirations(tk)
            logger.debug(f"Loaded ticker {tk}")
        except Exception as e:
            logger.error(f"Failed to load ticker {tk}: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load ticker {tk}: {e}")

    def buy_stock(self):
        tk = self.ticker_input.text().strip().upper()
        logger.debug(f"Attempting to buy stock for ticker {tk}")
        if not tk:
            QMessageBox.warning(self, "Error", "Please enter a ticker symbol.")
            logger.warning("No ticker symbol entered")
            return

        try:
            qty = int(self.quantity_edit.text())
            if qty <= 0:
                raise ValueError("Quantity must be positive.")
        except ValueError as e:
            QMessageBox.warning(self, "Error", "Please enter a valid positive integer for quantity.")
            logger.error(f"Invalid quantity: {e}")
            return

        try:
            # Fetch stock data for preview
            price, bid, ask, vol = self.parent_window.order_handler._get_current_stock_data(tk)
            logger.debug(f"Fetched stock data for {tk}: price=${price:.2f}, bid=${bid:.2f}, ask=${ask:.2f}, vol={vol}")
            if price <= 0.0:
                QMessageBox.warning(self, "Price Error", f"Could not fetch current price for {tk}.")
                logger.error(f"Invalid price for {tk}: {price}")
                return

            trade = {
                'type': 'stock',
                'ticker': tk,
                'quantity': qty,
                'buy_date': datetime.date.today()
            }

            # Show preview dialog
            logger.debug("Opening OrderPreviewDialog")
            dialog = OrderPreviewDialog(self, trade, price, bid, ask, vol)
            try:
                result = dialog.exec()
                logger.debug(f"OrderPreviewDialog result: {result}")
                if result == QDialog.DialogCode.Accepted:
                    edited_trade = dialog.get_edited_trade()
                    if edited_trade:
                        success = self.parent_window.order_handler.place_buy_order(edited_trade, self)
                        if success:
                            QMessageBox.information(self, "Success", f"Bought {edited_trade['quantity']} shares of {tk} at ${edited_trade.get('buy_price', 0.0):.2f}.")
                            self.parent_window.trade_simulator_tab.load_portfolio()
                            logger.info(f"Successfully bought {edited_trade['quantity']} shares of {tk}")
                        else:
                            logger.error("Order placement failed")
                    else:
                        logger.warning("No valid trade returned from OrderPreviewDialog")
                else:
                    logger.debug("Order preview cancelled")
            except Exception as e:
                logger.error(f"Error executing OrderPreviewDialog: {e}")
                QMessageBox.critical(self, "Error", f"Failed to execute order preview: {e}")
            finally:
                dialog.deleteLater()  # Ensure dialog is cleaned up
                gc.collect()
        except Exception as e:
            logger.error(f"Error in buy_stock: {e}")
            QMessageBox.critical(self, "Error", f"Failed to place order: {e}")

class ChartsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.active_plots = ["Candlestick"]
        self.custom_chart_config = None

        layout = QVBoxLayout()
        control_layout = QHBoxLayout()

        self.interval_box = QComboBox()
        self.interval_box.addItems(["1d", "1h", "30m", "15m", "5m"])
        self.period_box = QComboBox()
        self.period_box.addItems(["1mo", "3mo", "6mo", "1y", "max"])
        self.new_plot_box = QComboBox()
        self.new_plot_box.addItems([
            "Candlestick", "Volume", "Line", "RSI", "MACD", "Bollinger Bands"
        ])

        self.add_plot_btn = QPushButton("Add Plot")
        self.remove_plot_btn = QPushButton("Remove Last Plot")
        self.add_plot_btn.clicked.connect(self.add_plot)
        self.remove_plot_btn.clicked.connect(self.remove_last_plot)

        self.refresh_btn = QPushButton("Refresh Chart")
        self.refresh_btn.clicked.connect(self.load_chart)

        self.custom_chart_btn = QPushButton("Show Custom Chart")
        self.custom_chart_btn.clicked.connect(self.load_custom_chart)
        self.custom_chart_btn.setEnabled(False)

        control_layout.addWidget(QLabel("Interval:"))
        control_layout.addWidget(self.interval_box)
        control_layout.addSpacing(10)
        control_layout.addWidget(QLabel("Period:"))
        control_layout.addWidget(self.period_box)
        control_layout.addSpacing(10)
        control_layout.addWidget(QLabel("Plot Type:"))
        control_layout.addWidget(self.new_plot_box)
        control_layout.addWidget(self.add_plot_btn)
        control_layout.addWidget(self.remove_plot_btn)
        control_layout.addSpacing(10)
        control_layout.addWidget(self.refresh_btn)
        control_layout.addWidget(self.custom_chart_btn)

        self.web = QWebEngineView()

        layout.addLayout(control_layout)
        layout.addWidget(self.web)
        self.setLayout(layout)

    def add_plot(self):
        plot_type = self.new_plot_box.currentText()
        if plot_type not in self.active_plots:
            self.active_plots.append(plot_type)
            QTimer.singleShot(0, self.load_chart)

    def remove_last_plot(self):
        if len(self.active_plots) > 1:
            self.active_plots.pop()
            QTimer.singleShot(0, self.load_chart)

    def load_chart(self):
        ticker = self.parent_window.current_ticker if self.parent_window else None
        if not ticker:
            self.web.setHtml("<h3>No ticker selected.</h3>")
            return

        try:
            html = get_chart_html(
                ticker,
                interval=self.interval_box.currentText(),
                period=self.period_box.currentText(),
                plots=self.active_plots
            )
            QTimer.singleShot(0, lambda: self.web.setHtml(html))
            self.custom_chart_btn.setEnabled(False)
            logger.debug(f"Loaded chart for {ticker}")
        except Exception as e:
            logger.error(f"Error loading chart for {ticker}: {e}")
            self.web.setHtml(f"<h3>Error loading chart: {str(e)}</h3>")

    def set_custom_chart(self, chart_config):
        self.custom_chart_config = chart_config
        self.custom_chart_btn.setEnabled(True)

    def load_custom_chart(self):
        if not self.custom_chart_config:
            self.web.setHtml("<h3>No custom chart available.</h3>")
            return

        try:
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
            </head>
            <body>
                <canvas id="chart" style="width:100%; height:100%"></canvas>
                <script>
                    const ctx = document.getElementById('chart').getContext('2d');
                    new Chart(ctx, {self.custom_chart_config});
                </script>
            </body>
            </html>
            """
            QTimer.singleShot(0, lambda: self.web.setHtml(html))
            logger.debug("Loaded custom chart")
        except Exception as e:
            logger.error(f"Error loading custom chart: {e}")
            self.web.setHtml(f"<h3>Error loading custom chart: {str(e)}</h3>")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TraderLab - Prototype")
        self.resize(1200, 800)
        self.current_ticker = "AAPL"
        self.portfolio = []
        self.cash_balance = 100000.0
        self.order_handler = OrderHandler(self)

        self.setStyleSheet("""
            QLabel { font-size: 14px; }
            QGroupBox { font-size: 16px; font-weight: bold; border: 1px solid gray; border-radius: 6px; margin-top: 10px; padding: 10px; }
            QTableWidget { font-size: 12px; }
            QPushButton { font-size: 12px; padding: 5px; }
            QComboBox, QLineEdit { font-size: 12px; }
        """)

        tabs = QTabWidget()
        self.lookup_tab = LookupTab(self)
        self.charts_tab = ChartsTab(self)
        self.options_tab = OptionsTab(self)
        self.trade_simulator_tab = TradeSimulatorTab(self)

        tabs.addTab(self.lookup_tab, "Lookup")
        tabs.addTab(self.charts_tab, "Chart Builder")
        tabs.addTab(self.options_tab, "Options Chain")
        tabs.addTab(self.trade_simulator_tab, "Trade Simulator")

        self.setCentralWidget(tabs)
        logger.debug("MainWindow initialized")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    mw = MainWindow()
    mw.show()
    logger.debug("Application started")
    sys.exit(app.exec())