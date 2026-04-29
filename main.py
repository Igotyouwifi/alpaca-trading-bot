from flask import Flask, jsonify, request
import os
import pandas as pd
import alpaca_trade_api as tradeapi

app = Flask(__name__)

# =========================
# CONFIG
# =========================
API_KEY = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
AUTO_TRADE = os.getenv("AUTO_TRADE", "false").lower() == "true"
TIMEFRAME = "1Min"

api = tradeapi.REST(API_KEY, SECRET_KEY, BASE_URL) if API_KEY and SECRET_KEY else None

# =========================
# TIERS
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
        "features": ["RSI", "MACD", "volume filter", "advanced scoring"]
    },
    "elite": {
        "price": "$29.99/month",
        "symbols": ["AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "META", "GOOGL", "AMD"],
        "min_score_buy": 70,
        "max_score_sell": 30,
        "auto_trade": False,
        "features": ["more stocks", "stronger scoring", "better filters"]
    },
    "ultra": {
        "price": "$59.99/month",
        "symbols": ["AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "META", "GOOGL", "AMD", "PLTR", "NFLX"],
        "min_score_buy": 68,
        "max_score_sell": 32,
        "auto_trade": True,
        "features": ["automation access", "advanced scoring", "premium signals"]
    },
    "mastery_plus": {
        "price": "$499/month",
        "symbols": ["AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "META", "GOOGL", "AMD", "PLTR", "NFLX", "AVGO", "SMCI", "COIN", "MSTR"],
        "min_score_buy": 65,
        "max_score_sell": 35,
        "auto_trade": True,
        "features": ["top tier", "largest stock list", "automation", "premium signal engine", "crypto watchlist", "daily report"]
    }
}

CRYPTO_SYMBOLS = ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD"]

LICENSE_KEYS = {
    "STARTER-DEMO": "starter",
    "PRO-DEMO": "pro",
    "ELITE-DEMO": "elite",
    "ULTRA-DEMO": "ultra",
    "MASTER-DEMO": "mastery_plus"
}

# =========================
# DATA ENGINE
# =========================
def get_data(symbol):
    if api and "-" not in symbol:
        try:
            bars = api.get_bars(
                symbol,
                TIMEFRAME,
                limit=100,
                feed="iex"
            ).df

            if bars is not None and not bars.empty:
                return bars[["open", "high", "low", "close", "volume"]]

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
            return pd.DataFrame()

        if isinstance(yf_df.columns, pd.MultiIndex):
            yf_df.columns = [col[0] for col in yf_df.columns]

        yf_df = yf_df.rename(columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume"
        })

        needed = ["open", "high", "low", "close", "volume"]

        for col in needed:
            if col not in yf_df.columns:
                return pd.DataFrame()

        return yf_df[needed].dropna()

    except Exception as e:
        print(f"YFINANCE ERROR FOR {symbol}: {e}")
        return pd.DataFrame()

# =========================
# INDICATORS
# =========================
def calculate_indicators(df):
    df = df.copy()

    df["ma_fast"] = df["close"].rolling(5).mean()
    df["ma_slow"] = df["close"].rolling(20).mean()

    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / (loss + 0.000001)
    df["rsi"] = 100 - (100 / (1 + rs))

    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()

    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()

    df["avg_volume"] = df["volume"].rolling(20).mean()

    return df.dropna()

# =========================
# SCORING ENGINE
# =========================
def score_symbol(df, tier_config):
    latest = df.iloc[-1]
    score = 50
    reasons = []

    if latest["ma_fast"] > latest["ma_slow"]:
        score += 20
        reasons.append("bullish_trend")
    else:
        score -= 20
        reasons.append("bearish_trend")

    if latest["rsi"] < 30:
        score += 20
        reasons.append("oversold_rsi")
    elif latest["rsi"] > 70:
        score -= 20
        reasons.append("overbought_rsi")
    else:
        reasons.append("neutral_rsi")

    if latest["macd"] > latest["macd_signal"]:
        score += 20
        reasons.append("bullish_macd")
    else:
        score -= 20
        reasons.append("bearish_macd")

    if latest["volume"] > latest["avg_volume"]:
        score += 10
        reasons.append("volume_confirmed")
    else:
        score -= 5
        reasons.append("weak_volume")

    volatility = (df["close"].max() - df["close"].min()) / df["close"].mean()

    if volatility > 0.08:
        score -= 30
        reasons.append("high_volatility_risk")
    elif volatility < 0.04:
        score += 10
        reasons.append("stable_volatility")

    score = max(0, min(100, int(score)))

    if score >= tier_config["min_score_buy"]:
        signal = "buy"
        confidence = "high"
    elif score <= tier_config["max_score_sell"]:
        signal = "sell"
        confidence = "high"
    elif score >= 60:
        signal = "watch_buy"
        confidence = "medium"
    elif score <= 40:
        signal = "watch_sell"
        confidence = "medium"
    else:
        signal = "hold"
        confidence = "low"

    return score, signal, confidence, reasons

# =========================
# SIGNAL GENERATOR
# =========================
def generate_signal(symbol, tier_config):
    try:
        df = get_data(symbol)

        if df.empty:
            return {
                "symbol": symbol,
                "signal": "hold",
                "score": 0,
                "confidence": "none",
                "reason": "no_data_available",
                "order_status": "not_executed"
            }

        if len(df) < 30:
            return {
                "symbol": symbol,
                "signal": "hold",
                "score": 0,
                "confidence": "none",
                "bars_received": len(df),
                "reason": "not_enough_market_data",
                "order_status": "not_executed"
            }

        df = calculate_indicators(df)

        if df.empty or len(df) < 5:
            return {
                "symbol": symbol,
                "signal": "hold",
                "score": 0,
                "confidence": "none",
                "reason": "not_enough_indicator_data",
                "order_status": "not_executed"
            }

        score, signal, confidence, reasons = score_symbol(df, tier_config)

        return {
            "symbol": symbol,
            "signal": signal,
            "score": score,
            "confidence": confidence,
            "reasons": reasons,
            "last_price": round(float(df["close"].iloc[-1]), 2),
            "bars_received": len(df),
            "order_status": "not_executed"
        }

    except Exception as e:
        return {
            "symbol": symbol,
            "signal": "hold",
            "score": 0,
            "confidence": "error",
            "reason": str(e),
            "order_status": "not_executed"
        }

# =========================
# ACCOUNT REPORT
# =========================
def get_account_report():
    if not api:
        return {
            "status": "error",
            "reason": "alpaca_api_not_loaded"
        }

    try:
        account = api.get_account()
        positions = api.list_positions()

        open_positions = []
        total_unrealized_pl = 0.0
        total_intraday_pl = 0.0

        for p in positions:
            unrealized_pl = float(p.unrealized_pl)
            intraday_pl = float(getattr(p, "unrealized_intraday_pl", 0) or 0)

            total_unrealized_pl += unrealized_pl
            total_intraday_pl += intraday_pl

            open_positions.append({
                "symbol": p.symbol,
                "qty": p.qty,
                "market_value": p.market_value,
                "avg_entry_price": p.avg_entry_price,
                "current_price": p.current_price,
                "unrealized_pl": p.unrealized_pl,
                "unrealized_intraday_pl": getattr(p, "unrealized_intraday_pl", "0")
            })

        return {
            "status": "ok",
            "account_status": account.status,
            "cash": account.cash,
            "buying_power": account.buying_power,
            "portfolio_value": account.portfolio_value,
            "equity": account.equity,
            "total_unrealized_pl": round(total_unrealized_pl, 2),
            "today_unrealized_pl": round(total_intraday_pl, 2),
            "positions": open_positions
        }

    except Exception as e:
        return {
            "status": "error",
            "reason": str(e)
        }

# =========================
# BOT RUNNER
# =========================
def run_bot(tier_name, execute=False, crypto=False):
    tier_config = TIERS.get(tier_name, TIERS["starter"])

    if crypto:
        symbols = CRYPTO_SYMBOLS
    else:
        symbols = tier_config["symbols"]

    results = []

    for symbol in symbols:
        data = generate_signal(symbol, tier_config)
        order_status = "not_executed"

        if execute and AUTO_TRADE and tier_config["auto_trade"] and api and "-" not in symbol:
            try:
                if data["signal"] == "buy":
                    api.submit_order(
                        symbol=symbol,
                        qty=1,
                        side="buy",
                        type="market",
                        time_in_force="gtc"
                    )
                    order_status = "buy_order_sent"

                elif data["signal"] == "sell":
                    api.submit_order(
                        symbol=symbol,
                        qty=1,
                        side="sell",
                        type="market",
                        time_in_force="gtc"
                    )
                    order_status = "sell_order_sent"

            except Exception as e:
                order_status = f"order_error: {str(e)}"

        data["order_status"] = order_status
        results.append(data)

    return {
        "tier": tier_name,
        "auto_trade": AUTO_TRADE and tier_config["auto_trade"],
        "crypto_mode": crypto,
        "signals": results
    }

# =========================
# ROUTES
# =========================
@app.route("/")
def home():
    return jsonify({
        "status": "AI STOCK AGENT RUNNING",
        "auto_trade": AUTO_TRADE,
        "routes": [
            "/dashboard",
            "/signals?tier=pro",
            "/signals?tier=mastery_plus",
            "/crypto?tier=mastery_plus",
            "/trade?tier=ultra",
            "/report",
            "/tiers",
            "/debug",
            "/license?key=PRO-DEMO"
        ]
    })

@app.route("/signals")
def signals():
    tier = request.args.get("tier", "starter")
    return jsonify(run_bot(tier, execute=False, crypto=False))

@app.route("/crypto")
def crypto():
    tier = request.args.get("tier", "mastery_plus")
    return jsonify(run_bot(tier, execute=False, crypto=True))

@app.route("/trade")
def trade():
    tier = request.args.get("tier", "starter")
    return jsonify(run_bot(tier, execute=True, crypto=False))

@app.route("/report")
def report():
    return jsonify(get_account_report())

@app.route("/tiers")
def tiers():
    return jsonify(TIERS)

@app.route("/license")
def license_check():
    key = request.args.get("key", "")
    tier = LICENSE_KEYS.get(key)

    if not tier:
        return jsonify({
            "valid": False,
            "tier": None
        })

    return jsonify({
        "valid": True,
        "tier": tier,
        "features": TIERS[tier]["features"],
        "price": TIERS[tier]["price"]
    })

@app.route("/debug")
def debug():
    return jsonify({
        "api_key_loaded": API_KEY is not None and len(API_KEY) > 5,
        "secret_key_loaded": SECRET_KEY is not None and len(SECRET_KEY) > 5,
        "auto_trade": AUTO_TRADE,
        "base_url": BASE_URL
    })

@app.route("/dashboard")
def dashboard():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>AI Stock Agent Dashboard</title>
        <style>
            body {
                background: #0f172a;
                color: white;
                font-family: Arial, sans-serif;
                padding: 30px;
            }
            h1 { color: #38bdf8; }
            h2 { color: #e0f2fe; }
            button {
                padding: 10px 15px;
                margin: 5px;
                border: none;
                border-radius: 8px;
                background: #38bdf8;
                color: black;
                font-weight: bold;
                cursor: pointer;
            }
            .card {
                background: #1e293b;
                padding: 20px;
                margin: 15px 0;
                border-radius: 12px;
            }
            .buy { color: #22c55e; font-weight: bold; }
            .sell { color: #ef4444; font-weight: bold; }
            .hold, .watch_buy, .watch_sell { color: #facc15; font-weight: bold; }
            .score { font-size: 22px; font-weight: bold; }
            .grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
                gap: 15px;
            }
        </style>
    </head>
    <body>
        <h1>AI Stock Agent Dashboard</h1>
        <p>Status: Running</p>

        <button onclick="loadSignals('starter')">Starter</button>
        <button onclick="loadSignals('pro')">Pro</button>
        <button onclick="loadSignals('elite')">Elite</button>
        <button onclick="loadSignals('ultra')">Ultra</button>
        <button onclick="loadSignals('mastery_plus')">Mastery Plus</button>
        <button onclick="loadCrypto()">Crypto</button>
        <button onclick="loadReport()">Daily Report</button>

        <div id="report"></div>
        <div id="signals"></div>

        <script>
            async function loadSignals(tier) {
                document.getElementById("report").innerHTML = "";
                document.getElementById("signals").innerHTML = "<p>Loading signals...</p>";

                const res = await fetch("/signals?tier=" + tier);
                const data = await res.json();

                renderSignals(data);
            }

            async function loadCrypto() {
                document.getElementById("report").innerHTML = "";
                document.getElementById("signals").innerHTML = "<p>Loading crypto...</p>";

                const res = await fetch("/crypto?tier=mastery_plus");
                const data = await res.json();

                renderSignals(data);
            }

            async function loadReport() {
                document.getElementById("signals").innerHTML = "";
                document.getElementById("report").innerHTML = "<p>Loading report...</p>";

                const res = await fetch("/report");
                const data = await res.json();

                let html = "<h2>Daily Account Report</h2>";
                html += `<div class="card">
                   