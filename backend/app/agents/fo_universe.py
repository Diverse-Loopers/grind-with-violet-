"""
F&O Universe Configuration & Contract Specifications.
Extracted directly from the trader playbook rules.
Contains lot sizes, strike intervals, and standard margin requirements
for Indices and 100+ Indian F&O Stocks (including midcaps and small high-volatility names).
"""

from typing import Dict, Any

# Lot sizes for Index and Full Equity F&O Universe from Playbook
LOT_SIZES: Dict[str, int] = {
    # Major Indices
    "NIFTY": 25,
    "BANKNIFTY": 15,
    "FINNIFTY": 40,
    "MIDCPNIFTY": 75,
    "SENSEX": 10,
    "BANKEX": 10,

    # Large Caps & Institutional Core
    "RELIANCE": 250,
    "TCS": 175,
    "INFY": 400,
    "HDFCBANK": 550,
    "ICICIBANK": 700,
    "SBIN": 1500,
    "BHARTIARTL": 950,
    "ITC": 1600,
    "KOTAKBANK": 400,
    "LT": 300,
    "AXISBANK": 1200,
    "ASIANPAINT": 200,
    "MARUTI": 100,
    "TITAN": 375,
    "SUNPHARMA": 700,
    "HINDUNILVR": 300,
    "BAJFINANCE": 125,
    "HCLTECH": 700,
    "TATAMOTORS": 1425,
    "WIPRO": 1500,
    "CIPLA": 650,
    "TECHM": 600,
    "ONGC": 3850,
    "COALINDIA": 4200,

    # High-Beta, Midcaps & Small F&O Stocks (High Return Potential)
    "TRENT": 400,
    "TATAPOWER": 3375,
    "HAL": 300,
    "BEL": 5700,
    "BHEL": 10500,
    "IDEA": 70000,
    "PNB": 16000,
    "CANBK": 2700,
    "BANKBARODA": 5850,
    "FEDERALBNK": 5000,
    "IDFCFIRSTB": 15000,
    "GMRINFRA": 22500,
    "COFORGE": 150,
    "PERSISTENT": 175,
    "MOTHERSON": 6750,
    "SAIL": 8000,
    "NATIONALUM": 7500,
    "HINDALCO": 1400,
    "TATASTEEL": 5500,
    "JINDALSTEL": 1250,
    "VEDL": 2000,
    "DLF": 1650,
    "GODREJPROP": 425,
    "IRCTC": 875,
    "MCX": 400,
    "DIXON": 125,
    "POLYCAB": 300,
    "DELTACORP": 2800,
    "ZEEL": 3000,
    "RBLBANK": 5000,
    "AMBUJACEM": 1800,
    "ADANIENT": 250,
    "ADANIPORTS": 625,
}

# Standard strike intervals for generating realistic option chains
STRIKE_INTERVALS: Dict[str, float] = {
    "NIFTY": 50.0,
    "BANKNIFTY": 100.0,
    "FINNIFTY": 50.0,
    "MIDCPNIFTY": 25.0,
    "SENSEX": 100.0,
    "BANKEX": 100.0,

    "SBIN": 5.0,
    "TCS": 20.0,
    "INFY": 10.0,
    "ITC": 5.0,
    "ONGC": 2.5,
    "CIPLA": 10.0,
    "RELIANCE": 20.0,
    "HDFCBANK": 10.0,
    "ICICIBANK": 10.0,
    "AXISBANK": 10.0,
    "TECHM": 10.0,
    "BEL": 2.5,
    "BHEL": 2.5,
    "COALINDIA": 2.5,
    "ASIANPAINT": 20.0,
    "TATAMOTORS": 10.0,
    "TATASTEEL": 2.5,
    "WIPRO": 5.0,
    "LT": 20.0,
    "BHARTIARTL": 10.0,
    "MARUTI": 50.0,
    "SUNPHARMA": 10.0,
    "HINDUNILVR": 20.0,
    "KOTAKBANK": 20.0,
    "BAJFINANCE": 50.0,
    "TRENT": 50.0,
    "TATAPOWER": 5.0,
    "HAL": 25.0,
    "PNB": 1.0,
    "CANBK": 2.5,
    "IDEA": 0.5,
    "COFORGE": 50.0,
    "DLF": 10.0,
    "ADANIENT": 25.0,
}

# Default scanning universe: 4 Indices + 36 Top Liquid Large, Midcap, and High-Volatility F&O Stocks
EXPANDED_RADAR_SYMBOLS = [
    # Indices
    "NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY",
    # Large Caps
    "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "SBIN", "BHARTIARTL", "ITC", "KOTAKBANK", "LT",
    # Momentum High-Beta Midcaps & Small F&O
    "TRENT", "TATAPOWER", "HAL", "BEL", "BHEL", "COFORGE", "DLF", "DIXON", "POLYCAB",
    # High-Volume / Breakout Small Stocks
    "PNB", "CANBK", "BANKBARODA", "FEDERALBNK", "IDFCFIRSTB", "GMRINFRA", "IDEA",
    # Metals & Energy
    "TATASTEEL", "JINDALSTEL", "HINDALCO", "SAIL", "VEDL", "ONGC", "COALINDIA",
    # Auto & Pharma
    "TATAMOTORS", "MARUTI", "SUNPHARMA", "CIPLA", "TECHM", "WIPRO"
]


def get_lot_size(symbol: str) -> int:
    return LOT_SIZES.get(symbol.upper(), 500)


def get_strike_interval(symbol: str) -> float:
    return STRIKE_INTERVALS.get(symbol.upper(), 10.0)


def get_margin_percent(symbol: str) -> float:
    return 20.0
