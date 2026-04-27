from flask import Flask
import os
import time
import requests
import pandas as pd
from ta.momentum import RSIIndicator

app = Flask(__name__)

API_KEY = os.getenv("APCA_API_KEY_ID")
SECRET_KEY = os.getenv("APCA_API_SECRET_KEY")
BASE_URL = "https://paper-api.alpaca.markets"

STOCKS = [
    "AAPL", "TSLA", "MSFT", "NVDA", "AMZN",
    "META", "GOOGL", "AMD", "NFLX", "PLTR"
]

headers = {
    "APCA-API-KEY-ID": API_KEY,
    "APCA-API-SECRET-KEY": SECRET_KEY
}


# ---------------------------
# GET PRICE DATA
# ---------------------------
def get_bars(symbol):
    url = f"{BASE_URL}/v2/stocks/{symbol}/bars?timeframe=5Min&limit=50"
    r = requests.get(url, headers=headers)
    data = r.json()

    if "bars" not in data:
        return None

    closes = [bar["c"] for bar in data["bars"]]
    return closes


# ---------------------------
# AI SCORE ENGINE
# ---------------------------
def analyze_stock(symbol):
    prices = get_bars(symbol)
    if not prices or len(prices) < 20:
        return None

    df = pd.DataFrame(prices, columns=["close"])

    rsi = RSIIndicator(df["close"]).rsi().iloc[-1]

    score = 50  # neutral base

    # RSI logic (core AI signal)
    if rsi < 30:
        score += 30  # oversold → bullish
    elif rsi > 70:
        score -= 30  # overbought → bearish

    return {
        "symbol": symbol,
        "rsi": rsi,
        "score": score
    }


# ---------------------------
# TRADE DECISION ENGINE
# ---------------------------
def decide_trade(signal):
    if signal["score"] >= 75:
        return "BUY"
    elif signal["score"] <= 25:
        return "SELL"
    else:
        return "HOLD"


# ---------------------------
# SCANNER LOOP
# ---------------------------
def scan_market():
    results = []

    for stock in STOCKS:
        signal = analyze_stock(stock)
        if signal:
            decision = decide_trade(signal)
            signal["decision"] = decision
            results.append(signal)

    return results


# ---------------------------
# FLASK ROUTE
# ---------------------------
@app.route("/")
def home():
    signals = scan_market()

    return {
        "status": "running",
        "signals": signals
    }


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)