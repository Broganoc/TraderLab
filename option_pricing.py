from scipy.stats import norm
import math
import logging
import numpy as np

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def black_scholes(S, K, t, r, sigma, option_type, q=0.0):
    """
    Calculate option price using Black-Scholes model.
    S: Current stock price
    K: Strike price
    t: Time to expiration (in years)
    r: Risk-free rate
    sigma: Implied volatility
    option_type: 'Call' or 'Put'
    q: Dividend yield
    """
    try:
        if not all(np.isfinite([S, K, t, r, sigma, q])):
            logger.warning(f"Non-finite inputs in black_scholes: S={S}, K={K}, t={t}, r={r}, sigma={sigma}, q={q}")
            return 0.0
        if t <= 0:
            if option_type == "Call":
                return max(0, S - K)
            else:
                return max(0, K - S)
        d1 = (math.log(S / K) + (r - q + 0.5 * sigma ** 2) * t) / (sigma * math.sqrt(t))
        d2 = d1 - sigma * math.sqrt(t)
        if not all(np.isfinite([d1, d2])):
            logger.warning(f"Non-finite d1={d1} or d2={d2} in black_scholes")
            return 0.0
        if option_type == "Call":
            price = S * math.exp(-q * t) * norm.cdf(d1) - K * math.exp(-r * t) * norm.cdf(d2)
        else:
            price = K * math.exp(-r * t) * norm.cdf(-d2) - S * math.exp(-q * t) * norm.cdf(-d1)
        if not np.isfinite(price):
            logger.warning(f"Non-finite Black-Scholes price: {price}")
            return 0.0
        return price
    except (ValueError, ZeroDivisionError) as e:
        logger.warning(f"Error in black_scholes: {e}")
        return 0.0

def calculate_greeks(S, K, t, r, sigma, option_type, q=0.0):
    """
    Calculate option Greeks: Delta, Gamma, Theta, Vega.
    Returns a dictionary with the values.
    """
    try:
        if not all(np.isfinite([S, K, t, r, sigma, q])):
            logger.warning(f"Non-finite inputs in calculate_greeks: S={S}, K={K}, t={t}, r={r}, sigma={sigma}, q={q}")
            return {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}
        if t <= 0:
            if option_type == "Call":
                delta = 1.0 if S > K else 0.0
            else:
                delta = -1.0 if S < K else 0.0
            return {"delta": delta, "gamma": 0.0, "theta": 0.0, "vega": 0.0}

        d1 = (math.log(S / K) + (r - q + 0.5 * sigma ** 2) * t) / (sigma * math.sqrt(t))
        d2 = d1 - sigma * math.sqrt(t)
        if not all(np.isfinite([d1, d2])):
            logger.warning(f"Non-finite d1={d1} or d2={d2} in calculate_greeks")
            return {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}

        # Delta
        if option_type == "Call":
            delta = math.exp(-q * t) * norm.cdf(d1)
        else:
            delta = math.exp(-q * t) * (norm.cdf(d1) - 1)

        # Gamma
        gamma = math.exp(-q * t) * norm.pdf(d1) / (S * sigma * math.sqrt(t))

        # Theta
        if option_type == "Call":
            theta = (-S * math.exp(-q * t) * norm.pdf(d1) * sigma / (2 * math.sqrt(t)) -
                     r * K * math.exp(-r * t) * norm.cdf(d2) +
                     q * S * math.exp(-q * t) * norm.cdf(d1))
        else:
            theta = (-S * math.exp(-q * t) * norm.pdf(d1) * sigma / (2 * math.sqrt(t)) +
                     r * K * math.exp(-r * t) * norm.cdf(-d2) -
                     q * S * math.exp(-q * t) * norm.cdf(-d1))
        theta /= 365.0  # Convert to daily time decay

        # Vega
        vega = S * math.exp(-q * t) * norm.pdf(d1) * math.sqrt(t) / 100  # Per 1% change in volatility

        if not all(np.isfinite([delta, gamma, theta, vega])):
            logger.warning(f"Non-finite Greeks: delta={delta}, gamma={gamma}, theta={theta}, vega={vega}")
            return {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}

        return {"delta": delta, "gamma": gamma, "theta": theta, "vega": vega}
    except (ValueError, ZeroDivisionError) as e:
        logger.warning(f"Error in calculate_greeks: {e}")
        return {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}