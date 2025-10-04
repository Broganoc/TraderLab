from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QMessageBox, QGroupBox, QGridLayout
from PyQt6.QtCore import Qt, QTimer
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
import numpy as np
import gc
import logging

from scipy.stats import norm

from option_pricing import black_scholes, calculate_greeks

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class PayoffVisualizer(QWidget):
    def __init__(self, ticker, underlying_price, strike, option_type, premium, initial_days, sigma, risk_free_rate, dividend_yield):
        super().__init__()
        self.ticker = ticker
        self.underlying_price = underlying_price
        self.strike = strike
        self.option_type = option_type
        self.premium = premium
        self.initial_days = initial_days
        self.sigma = sigma
        self.risk_free_rate = risk_free_rate
        self.dividend_yield = dividend_yield
        self.prices = np.linspace(max(0, strike - 50), strike + 50, 100)
        self.selected_price = underlying_price if isinstance(underlying_price, (int, float)) else strike
        self.selected_sigma = sigma if isinstance(sigma, (int, float)) else 0.2
        self.update_timer = QTimer()
        self.update_timer.setSingleShot(True)
        self.update_timer.timeout.connect(self._update_payoff_plot)
        self.canvas = None
        self.fig = None
        self.is_closing = False
        self.payoff_cache = {}  # Cache for Black-Scholes results
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle(f"Payoff Simulator – {self.ticker}")
        layout = QVBoxLayout()

        # Control panel with sliders
        control_layout = QVBoxLayout()

        # Days to expiration slider
        days_layout = QHBoxLayout()
        self.days_label = QLabel(f"Days to Expiration: {self.initial_days}")
        self.days_label.setToolTip("Adjust days until option expiration")
        self.days_slider = QSlider(Qt.Orientation.Horizontal)
        self.days_slider.setRange(0, self.initial_days)
        self.days_slider.setValue(self.initial_days)
        self.days_slider.valueChanged.connect(self.schedule_update)
        days_layout.addWidget(self.days_label)
        days_layout.addWidget(self.days_slider)
        control_layout.addLayout(days_layout)

        # Stock price slider
        price_layout = QHBoxLayout()
        self.price_label = QLabel(f"Simulated Stock Price: ${self.selected_price:.2f}")
        self.price_label.setToolTip("Simulate different underlying stock prices")
        self.price_slider = QSlider(Qt.Orientation.Horizontal)
        price_range_min = max(0, self.strike - 50)
        price_range_max = self.strike + 50
        self.price_slider.setRange(int(price_range_min * 100), int(price_range_max * 100))
        self.price_slider.setValue(int(self.selected_price * 100))
        self.price_slider.setTickInterval(100)  # 1 dollar increments
        self.price_slider.setSingleStep(10)  # 0.1 dollar steps
        self.price_slider.valueChanged.connect(self.schedule_update)
        price_layout.addWidget(self.price_label)
        price_layout.addWidget(self.price_slider)
        control_layout.addLayout(price_layout)

        # Implied volatility slider
        vol_layout = QHBoxLayout()
        self.vol_label = QLabel(f"Implied Volatility: {self.selected_sigma*100:.2f}%")
        self.vol_label.setToolTip("Simulate different implied volatility levels")
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(5, 100)  # 5% to 100% volatility
        self.vol_slider.setValue(int(self.selected_sigma * 100))
        self.vol_slider.setTickInterval(5)
        self.vol_slider.setSingleStep(1)  # 1% steps
        self.vol_slider.valueChanged.connect(self.schedule_update)
        vol_layout.addWidget(self.vol_label)
        vol_layout.addWidget(self.vol_slider)
        control_layout.addLayout(vol_layout)

        # Metrics panel
        metrics_group = QGroupBox("Option Metrics")
        metrics_layout = QGridLayout()
        self.profit_label = QLabel("Profit/Loss: $0.00 ($0.00 per contract)")
        self.profit_label.setToolTip("Profit or loss at the simulated stock price")
        self.return_label = QLabel("Return: 0.00%")
        self.return_label.setToolTip("Percentage return based on premium")
        self.delta_label = QLabel("Delta: N/A")
        self.delta_label.setToolTip("Rate of change of option price per $1 change in stock price")
        self.gamma_label = QLabel("Gamma: N/A")
        self.gamma_label.setToolTip("Rate of change of Delta per $1 change in stock price")
        self.theta_label = QLabel("Theta: N/A")
        self.theta_label.setToolTip("Daily option price decay due to time")
        self.vega_label = QLabel("Vega: N/A")
        self.vega_label.setToolTip("Option price change per 1% change in volatility")
        self.break_even_label = QLabel("Break-even Price: N/A")
        self.break_even_label.setToolTip("Stock price where profit/loss is zero")
        self.prob_profit_label = QLabel("Probability of Profit: N/A")
        self.prob_profit_label.setToolTip("Likelihood of option expiring in-the-money")
        self.max_profit_label = QLabel("Max Profit: N/A")
        self.max_profit_label.setToolTip("Maximum potential profit at expiration")
        self.max_loss_label = QLabel("Max Loss: N/A")
        self.max_loss_label.setToolTip("Maximum potential loss at expiration")

        metrics_layout.addWidget(QLabel("Profit/Loss:"), 0, 0)
        metrics_layout.addWidget(self.profit_label, 0, 1)
        metrics_layout.addWidget(QLabel("Return:"), 1, 0)
        metrics_layout.addWidget(self.return_label, 1, 1)
        metrics_layout.addWidget(QLabel("Delta:"), 2, 0)
        metrics_layout.addWidget(self.delta_label, 2, 1)
        metrics_layout.addWidget(QLabel("Gamma:"), 3, 0)
        metrics_layout.addWidget(self.gamma_label, 3, 1)
        metrics_layout.addWidget(QLabel("Theta:"), 4, 0)
        metrics_layout.addWidget(self.theta_label, 4, 1)
        metrics_layout.addWidget(QLabel("Vega:"), 5, 0)
        metrics_layout.addWidget(self.vega_label, 5, 1)
        metrics_layout.addWidget(QLabel("Break-even Price:"), 6, 0)
        metrics_layout.addWidget(self.break_even_label, 6, 1)
        metrics_layout.addWidget(QLabel("Probability of Profit:"), 7, 0)
        metrics_layout.addWidget(self.prob_profit_label, 7, 1)
        metrics_layout.addWidget(QLabel("Max Profit:"), 8, 0)
        metrics_layout.addWidget(self.max_profit_label, 8, 1)
        metrics_layout.addWidget(QLabel("Max Loss:"), 9, 0)
        metrics_layout.addWidget(self.max_loss_label, 9, 1)
        metrics_group.setLayout(metrics_layout)
        control_layout.addWidget(metrics_group)

        layout.addLayout(control_layout)

        # Canvas
        self.fig, self.ax = plt.subplots(figsize=(8, 5))
        self.canvas = FigureCanvas(self.fig)
        layout.addWidget(self.canvas)

        self.setLayout(layout)
        self.resize(900, 700)
        self.schedule_update()

    def schedule_update(self):
        """Schedule a plot update with a 150ms debounce to prevent rapid redraws."""
        if not self.is_closing and not self.update_timer.isActive():
            self.update_timer.start(150)

    def _update_payoff_plot(self):
        """Update the payoff plot and metrics."""
        if self.is_closing or not self.canvas or not self.fig:
            logger.debug("Skipping update: window is closing or canvas/fig is deleted")
            return

        try:
            # Update from sliders
            days_left = self.days_slider.value()
            self.selected_price = self.price_slider.value() / 100.0
            self.selected_sigma = self.vol_slider.value() / 100.0
            t = days_left / 365.0
            cache_key = (days_left, self.selected_sigma, self.option_type)

            # Calculate payoffs (use cache if available)
            if cache_key not in self.payoff_cache:
                payoffs = []
                for p in self.prices:
                    value = black_scholes(p, self.strike, t, self.risk_free_rate, self.selected_sigma, self.option_type, self.dividend_yield)
                    if not np.isfinite(value):
                        logger.warning(f"Non-finite Black-Scholes value for price={p}, t={t}, sigma={self.selected_sigma}")
                        value = 0.0
                    payoffs.append(value - self.premium)
                self.payoff_cache[cache_key] = payoffs
            else:
                payoffs = self.payoff_cache[cache_key]
                logger.debug("Using cached payoffs")

            # Calculate break-even for plot
            break_even = self.strike + self.premium if self.option_type == "Call" else self.strike - self.premium

            # Update plot
            self.ax.clear()
            self.ax.plot(self.prices, payoffs, label=f"{self.option_type} Payoff (Days: {days_left}, IV: {self.selected_sigma*100:.1f}%)")
            self.ax.axvline(x=self.selected_price, color='r', linestyle='--', label=f"Simulated Price: ${self.selected_price:.2f}")
            self.ax.axvline(x=break_even, color='g', linestyle=':', label=f"Break-even: ${break_even:.2f}")
            self.ax.axhline(y=0, color='k', linestyle='-', alpha=0.3)
            self.ax.set_xlabel("Underlying Price")
            self.ax.set_ylabel("Profit/Loss per Share")
            self.ax.set_title(f"{self.option_type} Option Payoff Simulator")
            self.ax.legend()
            self.ax.grid(True)
            if self.canvas:
                self.canvas.draw()
            logger.debug("Payoff plot updated successfully")

            # Update metrics
            if isinstance(self.selected_price, (int, float)):
                current_value = black_scholes(
                    self.selected_price, self.strike, t, self.risk_free_rate, self.selected_sigma, self.option_type, self.dividend_yield
                )
                if not np.isfinite(current_value):
                    logger.warning(f"Non-finite Black-Scholes value for selected_price={self.selected_price}")
                    current_value = 0.0
                profit_per_share = current_value - self.premium
                profit_per_contract = profit_per_share * 100
                total_profit = profit_per_contract
                return_pct = (profit_per_share / self.premium * 100) if self.premium > 0 else 0.0
                self.profit_label.setText(f"Profit/Loss: ${total_profit:.2f} (${profit_per_contract:.2f} per contract)")
                self.return_label.setText(f"Return: {return_pct:.2f}%")
            else:
                self.profit_label.setText("Profit/Loss: N/A")
                self.return_label.setText("Return: N/A")

            # Update Greeks
            greeks = calculate_greeks(
                self.selected_price, self.strike, t, self.risk_free_rate, self.selected_sigma, self.option_type, self.dividend_yield
            )
            self.delta_label.setText(f"Delta: {greeks['delta']:.4f}" if np.isfinite(greeks['delta']) else "Delta: N/A")
            self.gamma_label.setText(f"Gamma: {greeks['gamma']:.4f}" if np.isfinite(greeks['gamma']) else "Gamma: N/A")
            self.theta_label.setText(f"Theta: {greeks['theta']:.4f}" if np.isfinite(greeks['theta']) else "Theta: N/A")
            self.vega_label.setText(f"Vega: {greeks['vega']:.4f}" if np.isfinite(greeks['vega']) else "Vega: N/A")

            # Update break-even and probabilities
            self.break_even_label.setText(f"Break-even Price: ${break_even:.2f}")

            try:
                d2 = (np.log(self.selected_price / self.strike) +
                      (self.risk_free_rate - self.dividend_yield - 0.5 * self.selected_sigma ** 2) * t) / (self.selected_sigma * np.sqrt(t))
                prob_profit = norm.cdf(d2) if self.option_type == "Call" else norm.cdf(-d2)
                if not np.isfinite(prob_profit):
                    logger.warning(f"Non-finite probability of profit for selected_price={self.selected_price}, t={t}, sigma={self.selected_sigma}")
                    prob_profit = 0.0
                self.prob_profit_label.setText(f"Probability of Profit: {prob_profit*100:.2f}%")
            except (ValueError, ZeroDivisionError):
                self.prob_profit_label.setText("Probability of Profit: N/A")

            # Update max profit/loss
            if self.option_type == "Call":
                max_profit = "Unlimited"
                max_loss = self.premium * 100
            else:
                max_profit = f"${(self.strike - self.premium) * 100:.2f}"
                max_loss = self.premium * 100
            self.max_profit_label.setText(f"Max Profit: {max_profit}")
            self.max_loss_label.setText(f"Max Loss: ${max_loss:.2f}")

            self.days_label.setText(f"Days to Expiration: {days_left}")
            self.price_label.setText(f"Simulated Stock Price: ${self.selected_price:.2f}")
            self.vol_label.setText(f"Implied Volatility: {self.selected_sigma*100:.2f}%")

        except Exception as e:
            if not self.is_closing:
                logger.error(f"Error updating payoff plot: {e}")
                QMessageBox.critical(self, "Error", f"Failed to update payoff diagram: {e}")

    def closeEvent(self, event):
        """Handle window close event and clean up resources."""
        try:
            self.is_closing = True
            self.update_timer.stop()
            if self.canvas:
                self.canvas.setParent(None)
                self.canvas.deleteLater()
                self.canvas = None
            if self.fig:
                plt.close(self.fig)
                self.fig = None
            self.payoff_cache.clear()
            gc.collect()
            logger.debug("PayoffVisualizer closed and resources cleaned up")
        except Exception as e:
            logger.error(f"Error in closeEvent: {e}")
        event.accept()