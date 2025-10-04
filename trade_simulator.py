# trade_simulator.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QPushButton,
    QHBoxLayout, QLabel, QMessageBox
)
from PyQt6.QtCore import Qt
import gc
import datetime


class TradeSimulatorTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent  # main window reference
        self.portfolio = []          # list of trades
        self.cash_balance = 100000.0  # Initial cash balance
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout()

        # Cash balance label
        self.cash_label = QLabel(f"Cash Balance: ${self.cash_balance:,.2f}")
        layout.addWidget(self.cash_label)

        # Portfolio table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Ticker", "Type", "Strike", "Qty", "Premium", "Expiry", "Buy Date"
        ])
        layout.addWidget(self.table)

        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_remove = QPushButton("Remove Selected")
        self.btn_remove.clicked.connect(self.remove_selected)
        self.btn_clear = QPushButton("Clear Portfolio")
        self.btn_clear.clicked.connect(self.clear_portfolio)
        btn_layout.addWidget(self.btn_remove)
        btn_layout.addWidget(self.btn_clear)
        layout.addLayout(btn_layout)

        # Summary label
        self.summary_label = QLabel("Total Contracts: 0")
        layout.addWidget(self.summary_label)

        self.setLayout(layout)

    # ---------------- Portfolio Management ----------------

    def load_portfolio(self):
        """Load the portfolio into the table safely."""
        try:
            portfolio = getattr(self.parent_window, "portfolio", [])
            self.table.setRowCount(len(portfolio))
            total_qty = 0

            for i, trade in enumerate(portfolio):
                self.table.setItem(i, 0, QTableWidgetItem(str(trade.get("ticker", "N/A"))))
                self.table.setItem(i, 1, QTableWidgetItem(str(trade.get("opt_type", trade.get("type", "N/A")))))
                self.table.setItem(i, 2, QTableWidgetItem(f"{trade.get('strike', 0):.2f}"))
                qty = trade.get("quantity", 0)
                total_qty += qty
                self.table.setItem(i, 3, QTableWidgetItem(str(qty)))
                self.table.setItem(i, 4, QTableWidgetItem(f"{trade.get('buy_premium', trade.get('buy_price', 0.0)):.2f}"))
                self.table.setItem(i, 5, QTableWidgetItem(str(trade.get("expiry", "N/A"))))
                buy_date = trade.get("buy_date", datetime.date.today())
                self.table.setItem(i, 6, QTableWidgetItem(str(buy_date)))

            self.summary_label.setText(f"Total Contracts: {total_qty}")
            self.table.resizeColumnsToContents()
            self.cash_label.setText(f"Cash Balance: ${self.cash_balance:,.2f}")
            gc.collect()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load portfolio: {e}")

    def remove_selected(self):
        """Remove selected trades safely."""
        selected_rows = set(item.row() for item in self.table.selectedItems())
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Select rows to remove.")
            return

        portfolio = getattr(self.parent_window, "portfolio", [])
        # Remove trades in reverse to avoid index issues
        for row in sorted(selected_rows, reverse=True):
            if 0 <= row < len(portfolio):
                del portfolio[row]

        self.load_portfolio()

    def clear_portfolio(self):
        """Clear entire portfolio safely."""
        reply = QMessageBox.question(
            self, "Confirm", "Are you sure you want to clear the entire portfolio?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            setattr(self.parent_window, "portfolio", [])
            self.load_portfolio()
            gc.collect()