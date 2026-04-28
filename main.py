from flask import Flask, jsonify
import alpaca_trade_api as tradeapi
import os

app = Flask(__name__)

# =========================
# ENV VARIABLES
# =========================
API_KEY = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
BASE_URL = "https://paper-api.alpaca.markets"

api = tradeapi.REST(API_KEY, SECRET_KEY, BASE_URL)

SYMBOLS = ["AAPL", "TSLA", "NVDA"]
TIMEFRAME = "1Min"

# =========================
# SIGNAL ENGINE
# =========================
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

# =========================
# RISK FILTER
# =========================
def risk_filter(symbol):
    bars = api.get_bars(symbol, TIMEFRAME, limit=20).df

    if len(bars) < 20:
        return False

    volatility = (bars["close"].max() - bars["close"].min()) / bars["close"].mean()

    return volatility <= 0.05

# =========================
# TRADE ENGINE
# =========================
def trade():
    results = []

    for symbol in SYMBOLS:
        signal = get_signal(symbol)

        if signal == "buy" and risk_filter(symbol):
            api.submit_order(symbol=symbol, qty=1, side="buy", type="market", time_in_force="gtc")

        elif signal == "sell" and risk_filter(symbol):
            api.submit_order(symbol=symbol, qty=1, side="sell", type="market", time_in_force="gtc")

        results.append({"symbol": symbol, "signal": signal})

    return results

# =========================
# ROUTES
# =========================
@app.route("/")
def home():
    return "Bot running"

@app.route("/trade")
def run_trade():
    return jsonify(trade())

# =========================
# START
# =========================
if __name__ == "__main__":
    app.run()