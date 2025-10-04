import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget,
    QVBoxLayout, QPushButton, QLineEdit, QLabel,
    QGridLayout, QGroupBox, QHBoxLayout, QComboBox
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QEvent
from data_fetcher import fetch_historical, fetch_summary
from chart_builder import get_chart_html
from options_tab import OptionsTab  # Import OptionsTab
import pandas as pd
import numpy as np
import gc
import tracemalloc  # Optional for profiling

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
        self.setLayout(layout)

    def load_ticker(self):
        tk = self.ticker_input.text().strip().upper()
        if not tk:
            return

        df = fetch_historical(tk, period="3mo", interval="1d")
        if df.empty:
            self.labels["Name"].setText("No data found")
            del df
            gc.collect()
            return

        # Update info card
        summary = fetch_summary(tk)
        for key, lbl in self.labels.items():
            lbl.setText(str(summary.get(key, "N/A")))

        # Update parent ticker and other tabs
        if self.parent_window:
            self.parent_window.current_ticker = tk
            self.parent_window.charts_tab.load_chart()
            self.parent_window.options_tab.load_expirations(tk)  # Update OptionsTab

        del df
        gc.collect()

class ChartsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.active_plots = ["Candlestick"]  # Default plot
        self.custom_chart_config = None  # Store Chart.js config (e.g., from OptionsTab)

        layout = QVBoxLayout()

        # Controls layout
        control_layout = QHBoxLayout()

        # Interval & Period
        self.interval_box = QComboBox()
        self.interval_box.addItems(["1d", "1h", "30m", "15m", "5m"])
        self.period_box = QComboBox()
        self.period_box.addItems(["1mo", "3mo", "6mo", "1y", "max"])

        # Plot type selector
        self.new_plot_box = QComboBox()
        self.new_plot_box.addItems([
            "Candlestick", "Volume", "Line", "RSI", "MACD", "Bollinger Bands"
        ])

        # Add/Remove buttons
        self.add_plot_btn = QPushButton("Add Plot")
        self.remove_plot_btn = QPushButton("Remove Last Plot")
        self.add_plot_btn.clicked.connect(self.add_plot)
        self.remove_plot_btn.clicked.connect(self.remove_last_plot)

        # Refresh button
        self.refresh_btn = QPushButton("Refresh Chart")
        self.refresh_btn.clicked.connect(self.load_chart)

        # Button to show custom chart (e.g., payoff diagram)
        self.custom_chart_btn = QPushButton("Show Custom Chart")
        self.custom_chart_btn.clicked.connect(self.load_custom_chart)
        self.custom_chart_btn.setEnabled(False)  # Enabled when config is set

        # Add controls to layout
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

        # Chart display
        self.web = QWebEngineView()

        layout.addLayout(control_layout)
        layout.addWidget(self.web)
        self.setLayout(layout)

    def clear_web_view(self):
        """Clear the QWebEngineView to release memory."""
        self.web.page().deleteLater()
        self.web.setPage(None)
        self.web.setHtml("")

    def add_plot(self):
        plot_type = self.new_plot_box.currentText()
        if plot_type not in self.active_plots:
            self.active_plots.append(plot_type)
            self.load_chart()

    def remove_last_plot(self):
        if len(self.active_plots) > 0:
            self.active_plots.pop()
            self.load_chart()

    def load_chart(self):
        ticker = self.parent_window.current_ticker
        if not ticker:
            self.web.setHtml("<h3>No ticker selected.</h3>")
            return

        self.custom_chart_config = None  # Reset custom config
        self.clear_web_view()  # Clear previous content
        interval = self.interval_box.currentText()
        period = self.period_box.currentText()
        html = get_chart_html(ticker, interval=interval, period=period, plots=self.active_plots)
        self.web.setHtml(html)
        self.custom_chart_btn.setEnabled(False)  # Disable until new config is set

    def set_custom_chart(self, chart_config):
        """Set a custom Chart.js config (e.g., from OptionsTab)."""
        self.custom_chart_config = chart_config
        self.custom_chart_btn.setEnabled(True)

    def load_custom_chart(self):
        """Render the custom Chart.js config in the QWebEngineView."""
        if not self.custom_chart_config:
            self.web.setHtml("<h3>No custom chart available.</h3>")
            return

        self.clear_web_view()  # Clear previous content
        # Create HTML to render the Chart.js chart
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
        self.web.setHtml(html)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("""
            QLabel {
                font-size: 14px;
            }
            QGroupBox {
                font-size: 16px;
                font-weight: bold;
                border: 1px solid gray;
                border-radius: 6px;
                margin-top: 10px;
                padding: 10px;
            }
            QTableWidget {
                font-size: 12px;
            }
            QPushButton {
                font-size: 12px;
                padding: 5px;
            }
            QComboBox, QLineEdit {
                font-size: 12px;
            }
        """)
        self.setWindowTitle("TraderLab - Prototype")
        self.resize(1200, 800)

        self.current_ticker = "AAPL"  # Default ticker

        # Initialize tabs
        tabs = QTabWidget()
        self.lookup_tab = LookupTab(self)
        self.charts_tab = ChartsTab(self)
        self.options_tab = OptionsTab(self)  # Add OptionsTab

        # Add tabs to QTabWidget
        tabs.addTab(self.lookup_tab, "Lookup")
        tabs.addTab(self.charts_tab, "Chart Builder")
        tabs.addTab(self.options_tab, "Options Chain")

        self.setCentralWidget(tabs)

        # Connect OptionsTab's payoff diagram to ChartsTab
        self.options_tab.show_payoff_diagram = self.override_show_payoff_diagram

    def override_show_payoff_diagram(self):
        """Override OptionsTab's show_payoff_diagram to pass config to ChartsTab."""
        selected = self.options_tab.table.selectedItems()
        if not selected:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "No Selection", "Please select an option to view its payoff.")
            return

        row = self.options_tab.table.currentRow()
        strike_item = self.options_tab.table.item(row, 1)  # Assuming strike is in column 1
        type_item = self.options_tab.table.item(row, 0) if "Type" in self.options_tab.table.horizontalHeaderItem(0).text() else None
        if not strike_item:
            return

        strike = float(strike_item.text())
        option_type = type_item.text() if type_item else "Call"
        premium = float(self.options_tab.table.item(row, 2).text()) if self.options_tab.table.item(row, 2) else 0

        # Generate price range for payoff
        prices = np.linspace(max(0, strike - 50), strike + 50, 100)
        payoffs = []
        for price in prices:
            if option_type == "Call":
                payoff = max(0, price - strike) - premium
            else:
                payoff = max(0, strike - price) - premium
            payoffs.append(payoff)

        # Create Chart.js config
        chart_config = {
            "type": "line",
            "data": {
                "labels": [f"{p:.2f}" for p in prices],
                "datasets": [{
                    "label": f"{option_type} Payoff (Strike: {strike})",
                    "data": payoffs,
                    "borderColor": "#1E90FF",
                    "backgroundColor": "rgba(30, 144, 255, 0.1)",
                    "fill": True,
                    "tension": 0.1
                }]
            },
            "options": {
                "scales": {
                    "x": {"title": {"display": True, "text": "Underlying Price"}},
                    "y": {"title": {"display": True, "text": "Payoff"}}
                },
                "plugins": {
                    "title": {"display": True, "text": f"{option_type} Option Payoff"}
                }
            }
        }

        # Pass config to ChartsTab and switch to it
        self.charts_tab.set_custom_chart(chart_config)
        self.charts_tab.load_custom_chart()
        self.centralWidget().setCurrentWidget(self.charts_tab)

    def closeEvent(self, event: QEvent):
        """Clean up on application close."""
        # Disconnect signals
        try:
            self.lookup_tab.ticker_input.returnPressed.disconnect()
            self.charts_tab.add_plot_btn.clicked.disconnect()
            self.charts_tab.remove_plot_btn.clicked.disconnect()
            self.charts_tab.refresh_btn.clicked.disconnect()
            self.charts_tab.custom_chart_btn.clicked.disconnect()
            if hasattr(self.options_tab, 'payoff_window') and self.options_tab.payoff_window:
                self.options_tab.payoff_window.close()
        except:
            pass  # Ignore if not connected

        # Clear QWebEngineView
        self.charts_tab.clear_web_view()

        # Force garbage collection
        gc.collect()
        event.accept()

if __name__ == "__main__":
    # Optional: Start tracemalloc for profiling
    # tracemalloc.start()

    app = QApplication(sys.argv)
    mw = MainWindow()
    mw.show()
    try:
        sys.exit(app.exec())
    finally:
        # Optional: Print top memory consumers
        # snapshot = tracemalloc.take_snapshot()
        # top_stats = snapshot.statistics('lineno')
        # print("Top memory consumers:")
        # for stat in top_stats[:10]:
        #     print(stat)

        app.deleteLater()  # Ensure QApplication is deleted
        gc.collect()  # Force garbage collection