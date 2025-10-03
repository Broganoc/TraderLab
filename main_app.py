# main_app.py
import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget,
    QVBoxLayout, QPushButton, QLineEdit, QLabel,
    QGridLayout, QGroupBox, QHBoxLayout, QComboBox
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from data_fetcher import fetch_historical, fetch_summary
from chart_builder import get_chart_html


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
            return

        # Update info card
        summary = fetch_summary(tk)
        for key, lbl in self.labels.items():
            lbl.setText(str(summary.get(key, "N/A")))

        # Update charts tab
        if self.parent_window:
            self.parent_window.current_ticker = tk
            self.parent_window.charts_tab.load_chart()


class ChartsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.active_plots = ["Candlestick"]  # Default plot

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

        # Chart display
        self.web = QWebEngineView()

        layout.addLayout(control_layout)
        layout.addWidget(self.web)
        self.setLayout(layout)

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

        interval = self.interval_box.currentText()
        period = self.period_box.currentText()
        html = get_chart_html(ticker, interval=interval, period=period, plots=self.active_plots)
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
        """)
        self.setWindowTitle("TraderLab - Prototype")
        self.resize(1200, 800)

        self.current_ticker = "AAPL"  # default

        tabs = QTabWidget()
        self.lookup_tab = LookupTab(self)
        self.charts_tab = ChartsTab(self)

        tabs.addTab(self.lookup_tab, "Lookup")
        tabs.addTab(self.charts_tab, "Chart Builder")

        self.setCentralWidget(tabs)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    mw = MainWindow()
    mw.show()
    sys.exit(app.exec())
