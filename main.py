from flask import Flask, jsonify
import os
import alpaca_trade_api as tradeapi
import pandas as pd

app = Flask(__name__)

API_KEY = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
BASE_URL = "https://paper-api.alpaca.markets"

api = tradeapi.REST(API_KEY, SECRET_KEY, BASE_URL)

SYMBOLS = ["AAPL", "TSLA", "NVDA", "MSFT", "AMZN"]
TIMEFRAME = "1Min"
AUTO_TRADE = False

def get_data(symbol):
    bars = api.get_bars(symbol, TIMEFRAME, limit=100).df
    return bars

def calculate_indicators(df):
    df["ma_short"] = df["close"].rolling(5).mean()
    df["ma_long"] = df["close"].rolling(20).mean()

    delta = df["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df["rsi"] = 100 - (100 / (1 + rs))

    exp1 = df["close"].ewm(span=12).mean()
    exp2 = df["close"].ewm(span=26).mean()
    df["macd"] = exp1 - exp2
    df["signal"] = df["macd"].ewm(span=9).mean()

    return df

def score_trade(df):
    score = 0
    reasons = []

    if df["ma_short"].iloc[-1] > df["ma_long"].iloc[-1]:
        score += 30
        reasons.append("trend_up")
    else:
        score -= 30

    if df["rsi"].iloc[-1] < 30:
        score += 20
        reasons.append("oversold")
    elif df["rsi"].iloc[-1] > 70:
        score -= 20

    if df["macd"].iloc[-1] > df["signal"].iloc[-1]:
        score += 25
        reasons.append("macd_bullish")
    else:
        score -= 25

    volatility = (df["close"].max() - df["close"].min()) / df["close"].mean()
    if volatility < 0.03:
        score += 15
        reasons.append("stable")
    else:
        score -= 15

    return score, reasons

def generate_signal(symbol):
    df = get_data(symbol)

    if len(df) < 30:
        return {"symbol": symbol, "signal": "hold", "score": 0}

    df = calculate_indicators(df)
    score, reasons = score_trade(df)

    if score >= 60:
        signal = "buy"
    elif score <= -60:
        signal = "sell"
    else:
        signal = "hold"

    return {
        "symbol": symbol,
        "signal": signal,
        "score": score,
        "reasons": reasons
    }

def trade():
    results = []

    for symbol in SYMBOLS:
        data = generate_signal(symbol)

        if AUTO_TRADE:
            if data["signal"] == "buy":
                api.submit_order(symbol=symbol, qty=1, side="buy", type="market", time_in_force="gtc")
            elif data["signal"] == "sell":
                api.submit_order(symbol=symbol, qty=1, side="sell", type="market", time_in_force="gtc")

        results.append(data)

    return results

@app.route("/")
def home():
    return "AI BOT RUNNING"

@app.route("/signals")
def signals():
    return jsonify(trade())

@app.route("/tiers")
def tiers():
    return jsonify({
        "starter": "free signals",
        "pro": "$9.99/month",
        "elite": "$29.99/month",
        "ultra": "$59.99/month automation"
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)