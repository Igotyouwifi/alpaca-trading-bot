from flask import Flask, jsonify, request
import alpaca_trade_api as tradeapi
import pandas as pd
import os

app = Flask(__name__)

# =========================
# API SETTINGS
# =========================
API_KEY = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
BASE_URL = "https://paper-api.alpaca.markets"

AUTO_TRADE = os.getenv("AUTO_TRADE", "false").lower() == "true"

api = tradeapi.REST(API_KEY, SECRET_KEY, BASE_URL)

TIMEFRAME = "1Min"

# =========================
# TIER SYSTEM
# =========================
TIERS = {
    "starter": {
        "price": "$0/month",
        "symbols": ["AAPL", "TSLA"],
        "min_score_buy": 80,
        "max_score_sell": 20,
        "auto_trade": False,
        "features": ["basic signals", "2 stocks", "no auto trading"]
    },
    "pro": {
        "price": "$9.99/month",
        "symbols": ["AAPL", "TSLA", "NVDA", "MSFT", "AMZN"],
        "min_score_buy": 75,
        "max_score_sell": 25,
        "auto_trade": False,
        "features": ["advanced signals", "5 stocks", "RSI", "MACD", "volume filter"]
    },
    "elite": {
        "price": "$29.99/month",
        "symbols": ["AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "META", "GOOGL", "AMD"],
        "min_score_buy": 70,
        "max_score_sell": 30,
        "auto_trade": False,
        "features": ["stronger scoring", "more stocks", "better filters", "confidence engine"]
    },
    "ultra": {
        "price": "$59.99/month",
        "symbols": ["AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "META", "GOOGL", "AMD", "PLTR", "NFLX"],
        "min_score_buy": 68,
        "max_score_sell": 32,
        "auto_trade": True,
        "features": ["full automation", "highest tier", "auto trading allowed", "advanced scoring"]
    },
    "mastery_plus": {
        "price": "$499/month",
        "symbols": ["AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "META", "GOOGL", "AMD", "PLTR", "NFLX", "AVGO", "SMCI", "COIN", "MSTR"],
        "min_score_buy": 65,
        "max_score_sell": 35,
        "auto_trade": True,
        "features": [
            "top tier",
            "largest symbol list",
            "highest automation access",
            "advanced scoring",
            "premium signal engine"
        ]
    }
}

# =========================
# DATA ENGINE
# =========================
def get_data(symbol):
    try:
        bars = api.get_bars(
            symbol,
            TIMEFRAME,
            limit=100,
            feed="iex"
        ).df

        if bars is not None and not bars.empty:
            return bars

        print(f"ALPACA EMPTY DATA FOR {symbol}, USING YFINANCE FALLBACK")

    except Exception as e:
        print(f"ALPACA DATA ERROR FOR {symbol}: {e}")

    try:
        import yfinance as yf

        yf_df = yf.download(
            symbol,
            period="5d",
            interval="1m",
            progress=False,
            auto_adjust=False
        )

        if yf_df is None or yf_df.empty:
            print(f"YFINANCE ALSO EMPTY FOR {symbol}")
            return pd.DataFrame()

        yf_df = yf_df.rename(columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume"
        })

        return yf_df[["open", "high", "low", "close", "volume"]]

    except Exception as e:
        print(f"YFINANCE ERROR FOR {symbol}: {e}")
        return pd.DataFrame()

# =========================
# INDICATORS
# =========================
def calculate_indicators(df):
    df = df.copy()

    df["ma_fast"] = df["close"].rolling(5).mean()
    df["ma_mid"] = df["close"].rolling(20).mean()
    df["ma_slow"] = df["close"].rolling(50).mean()

    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / (loss + 0.000001)
    df["rsi"] = 100 - (100 / (1 + rs))

    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()

    df["volume_avg"] = df["volume"].rolling(20).mean()
    df["volume_spike"] = df["volume"] / (df["volume_avg"] + 0.000001)

    df["volatility"] = (df["high"].rolling(20).max() - df["low"].rolling(20).min()) / df["close"].rolling(20).mean()

    return df

# =========================
# SCORING ENGINE
# =========================
def score_symbol(symbol):
    df = get_data(symbol)

    if df.empty:
        return {
            "symbol": symbol,
            "signal": "hold",
            "score": 0,
            "confidence": "none",
            "reason": "no_data_from_alpaca"
        }

    if len(df) < 60:
        return {
            "symbol": symbol,
            "signal": "hold",
            "score": 0,
            "confidence": "none",
            "bars_received": len(df),
            "reason": "not_enough_market_data"
        }

    df = calculate_indicators(df)
    latest = df.iloc[-1]

    score = 50
    reasons = []

    # Trend
    if latest["ma_fast"] > latest["ma_mid"]:
        score += 15
        reasons.append("fast_trend_up")
    else:
        score -= 15
        reasons.append("fast_trend_down")

    if latest["ma_mid"] > latest["ma_slow"]:
        score += 15
        reasons.append("long_trend_up")
    else:
        score -= 15
        reasons.append("long_trend_down")

    # RSI
    if latest["rsi"] < 30:
        score += 15
        reasons.append("rsi_oversold")
    elif latest["rsi"] > 70:
        score -= 15
        reasons.append("rsi_overbought")
    else:
        reasons.append("rsi_neutral")

    # MACD
    if latest["macd"] > latest["macd_signal"]:
        score += 15
        reasons.append("macd_bullish")
    else:
        score -= 15
        reasons.append("macd_bearish")

    # Volume
    if latest["volume_spike"] > 1.5:
        score += 10
        reasons.append("volume_spike")
    else:
        reasons.append("normal_volume")

    # Volatility safety
    if latest["volatility"] > 0.05:
        score -= 25
        reasons.append("high_volatility_risk")
    else:
        score += 10
        reasons.append("stable_volatility")

    score = max(0, min(100, int(score)))

    if score >= 75:
        signal = "buy"
        confidence = "high"
    elif score >= 60:
        signal = "buy"
        confidence = "medium"
    elif score <= 25:
        signal = "sell"
        confidence = "high"
    elif score <= 40:
        signal = "sell"
        confidence = "medium"
    else:
        signal = "hold"
        confidence = "low"

    return {
        "symbol": symbol,
        "signal": signal,
        "score": score,
        "confidence": confidence,
        "price": round(float(latest["close"]), 2),
        "rsi": round(float(latest["rsi"]), 2),
        "macd": round(float(latest["macd"]), 4),
        "volatility": round(float(latest["volatility"]), 4),
        "volume_spike": round(float(latest["volume_spike"]), 2),
        "reasons": reasons
    }

# =========================
# SIGNAL RUNNER
# =========================
def run_signals(tier_name):
    tier = TIERS.get(tier_name, TIERS["starter"])
    results = []

    for symbol in tier["symbols"]:
        data = score_symbol(symbol)

        if data["signal"] == "buy" and data["score"] < tier["min_score_buy"]:
            data["signal"] = "hold"
            data["blocked_reason"] = "score_below_tier_buy_threshold"

        if data["signal"] == "sell" and data["score"] > tier["max_score_sell"]:
            data["signal"] = "hold"
            data["blocked_reason"] = "score_above_tier_sell_threshold"

        results.append(data)

    return results

# =========================
# TRADE EXECUTION
# =========================
def execute_trades(tier_name):
    tier = TIERS.get(tier_name, TIERS["starter"])
    signals = run_signals(tier_name)
    executed = []

    if not AUTO_TRADE:
        return {
            "auto_trade": False,
            "message": "AUTO_TRADE is off. Signals only.",
            "signals": signals
        }

    if not tier["auto_trade"]:
        return {
            "auto_trade": False,
            "message": "This tier does not allow auto trading.",
            "signals": signals
        }

    for item in signals:
        symbol = item["symbol"]
        signal = item["signal"]

        try:
            if signal == "buy":
                api.submit_order(
                    symbol=symbol,
                    qty=1,
                    side="buy",
                    type="market",
                    time_in_force="gtc"
                )
                executed.append({"symbol": symbol, "action": "buy", "status": "submitted"})

            elif signal == "sell":
                api.submit_order(
                    symbol=symbol,
                    qty=1,
                    side="sell",
                    type="market",
                    time_in_force="gtc"
                )
                executed.append({"symbol": symbol, "action": "sell", "status": "submitted"})

        except Exception as e:
            executed.append({"symbol": symbol, "action": signal, "status": "error", "error": str(e)})

    return {
        "auto_trade": True,
        "tier": tier_name,
        "executed": executed,
        "signals": signals
    }

# =========================
# ROUTES
# =========================
@app.route("/")
def home():
    return jsonify({
        "status": "AI STOCK AGENT RUNNING",
        "routes": ["/signals?tier=pro", "/trade?tier=ultra", "/tiers"],
        "auto_trade": AUTO_TRADE
    })

@app.route("/signals")
def signals():
    tier = request.args.get("tier", "starter").lower()
    return jsonify({
        "tier": tier,
        "auto_trade": False,
        "signals": run_signals(tier)
    })

@app.route("/trade")
def trade():
    tier = request.args.get("tier", "starter").lower()
    return jsonify(execute_trades(tier))

@app.route("/tiers")
def tiers():
    return jsonify(TIERS)

# =========================
# START
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)