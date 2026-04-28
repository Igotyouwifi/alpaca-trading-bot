from flask import Flask, jsonify
import alpaca_trade_api as tradeapi
import pandas as pd
import os
import time

app = Flask(__name__)

API_KEY = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
BASE_URL = "https://paper-api.alpaca.markets"

api = tradeapi.REST(API_KEY, SECRET_KEY, BASE_URL)

SYMBOLS = ["AAPL", "TSLA", "NVDA"]
TIMEFRAME = "1Min"

def get_signal(symbol):
    bars = api.get_bars(symbol, TIMEFRAME, limit=50).df

    if len(bars) < 20:
        return "hold"

    bars["ma_short"] = bars["close"].rolling(5).mean()
    bars["ma_long"] = bars["close"].rolling(20).mean()

    if bars["ma_short"].iloc[-1] > bars["ma_long"].iloc[-1]:
        return "buy"
    elif bars["ma_short"].iloc[-1] < bars["ma_long"].iloc[-1]:
        return "sell"
    return "hold"

def trade():
    results = []

    for symbol in SYMBOLS:
        signal = get_signal(symbol)

        if signal == "buy":
            api.submit_order(symbol=symbol, qty=1, side="buy", type="market", time_in_force="gtc")
        elif signal == "sell":
            api.submit_order(symbol=symbol, qty=1, side="sell", type="market", time_in_force="gtc")

        results.append({"symbol": symbol, "signal": signal})

    return results

@app.route("/")
def home():
    return "Bot running"

@app.route("/trade")
def run_trade():
    result = trade()
    return jsonify(result)

if __name__ == "__main__":
    while True:
        trade()
        time.sleep(60)