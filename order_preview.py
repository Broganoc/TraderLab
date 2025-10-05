import logging
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QLabel
import datetime

# Configure logging
logging.basicConfig(level=logging.DEBUG, filename='traderlab.log', filemode='w')
logger = logging.getLogger(__name__)

class OrderPreviewDialog(QDialog):
    def __init__(self, parent, trade, price, bid, ask, vol=0, oi=0, is_option=False):
        super().__init__(parent)
        logger.debug(f"Initializing OrderPreviewDialog for trade: {trade}")
        self.setWindowTitle("Order Preview")
        self.trade = trade
        self.market_price = price
        self.bid = bid
        self.ask = ask
        self.vol = vol
        self.oi = oi
        self.is_option = is_option
        self.multiplier = 100 if is_option else 1
        self.limit_price = None

        try:
            layout = QVBoxLayout()

            # Ticker
            self.ticker_label = QLabel(f"Ticker: {trade['ticker']}")
            layout.addWidget(self.ticker_label)

            # Type/Strike/Expiry for options
            if is_option:
                expiry = trade['expiry']
                expiry_str = expiry.strftime("%Y-%m-%d") if isinstance(expiry, datetime.date) else str(expiry)
                self.type_label = QLabel(f"Type: {trade['opt_type']} | Strike: ${trade['strike']:.2f} | Expiry: {expiry_str}")
                layout.addWidget(self.type_label)

            # Quantity edit
            layout.addWidget(QLabel("Quantity:"))
            self.quantity_edit = QLineEdit(str(trade['quantity']))
            layout.addWidget(self.quantity_edit)

            # Limit price edit
            layout.addWidget(QLabel("Limit Price (optional, leave blank for market order):"))
            self.limit_price_edit = QLineEdit()
            self.limit_price_edit.setPlaceholderText(f"Market Price: ${price:.2f}")
            layout.addWidget(self.limit_price_edit)

            # Price info
            self.price_label = QLabel(f"Estimated Price/Premium: ${price:.2f}")
            layout.addWidget(self.price_label)

            # Bid/Ask
            if bid > 0 or ask > 0:
                self.bid_ask_label = QLabel(f"Bid: ${bid:.2f} | Ask: ${ask:.2f}")
                layout.addWidget(self.bid_ask_label)

            # Liquidity info
            self.liquidity_label = QLabel(f"Volume: {vol:,}")
            if is_option:
                self.liquidity_label.setText(f"Volume: {vol:,} | Open Interest: {oi:,}")
            layout.addWidget(self.liquidity_label)

            # Low liquidity warning for options
            if is_option and (vol < 10 or oi < 50):
                warning = QLabel("Warning: Low liquidity (may have wide spreads or stale prices)")
                warning.setStyleSheet("color: red; font-weight: bold;")
                layout.addWidget(warning)

            # Total cost
            self.total_cost_label = QLabel()
            self.update_total_cost()
            layout.addWidget(self.total_cost_label)

            # Buttons
            btn_box = QHBoxLayout()
            confirm_btn = QPushButton("Confirm Order")
            confirm_btn.clicked.connect(self.accept)
            cancel_btn = QPushButton("Cancel")
            cancel_btn.clicked.connect(self.reject)
            btn_box.addWidget(confirm_btn)
            btn_box.addWidget(cancel_btn)
            layout.addLayout(btn_box)

            self.setLayout(layout)
            self.quantity_edit.textChanged.connect(self.update_total_cost)
            self.limit_price_edit.textChanged.connect(self.update_total_cost)
            logger.debug("OrderPreviewDialog initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing OrderPreviewDialog: {e}")
            raise

    def update_total_cost(self):
        try:
            qty = int(self.quantity_edit.text())
            if qty <= 0:
                raise ValueError("Quantity must be positive")
            limit_price_text = self.limit_price_edit.text().strip()
            price = float(limit_price_text) if limit_price_text else self.market_price
            if limit_price_text and price <= 0:
                raise ValueError("Limit price must be positive")
            self.limit_price = price if limit_price_text else None
            total = qty * self.multiplier * price
            self.total_cost_label.setText(f"Estimated Total Cost: ${total:,.2f}")
            logger.debug(f"Updated total cost: ${total:,.2f} (using {'limit' if limit_price_text else 'market'} price: ${price:.2f})")
        except ValueError as e:
            self.total_cost_label.setText(f"Invalid input: {str(e)}")
            logger.error(f"Error updating total cost: {e}")

    def get_edited_trade(self):
        try:
            qty = int(self.quantity_edit.text())
            if qty <= 0:
                raise ValueError("Quantity must be positive")
            self.trade['quantity'] = qty
            if self.limit_price is not None:
                self.trade['limit_price'] = self.limit_price
            logger.debug(f"Returning edited trade: {self.trade}")
            return self.trade
        except ValueError as e:
            logger.error(f"Error getting edited trade: {e}")
            return None

    def exec(self):
        logger.debug("Executing OrderPreviewDialog")
        try:
            result = super().exec()
            logger.debug(f"OrderPreviewDialog exec result: {result}")
            return result
        except Exception as e:
            logger.error(f"Error in OrderPreviewDialog exec: {e}")
            raise
        finally:
            logger.debug("Cleaning up OrderPreviewDialog")
            self.deleteLater()