from flask import Flask, jsonify, request, render_template_string
import os
from datetime import datetime, timezone
import pandas as pd
import numpy as np
import yfinance as yf

try:
    import alpaca_trade_api as tradeapi
except Exception:
    tradeapi = None

app = Flask(__name__)

# =========================
# SECURITY / CONFIG
# =========================
API_KEY = os.getenv("ALPACA_API_KEY", "")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")

PAPER_URL = "https://paper-api.alpaca.markets"
LIVE_URL = "https://api.alpaca.markets"

LIVE_TRADING_ENABLED = os.getenv("LIVE_TRADING_ENABLED", "false").lower() == "true"

ORDERS = []

TIER_ORDER = ["starter", "pro", "elite", "ultra", "mastery_plus"]

NICE_NAMES = {
    "starter": "Starter Trial",
    "pro": "Pro",
    "elite": "Elite",
    "ultra": "Ultra",
    "mastery_plus": "Mastery Plus"
}

TIER_CONFIGS = {
    "starter": {
        "price": "Free 3-day trial, then $4.99/month",
        "trial": "3-day free trial",
        "welcome_discount": "None",
        "symbols": ["AAPL", "TSLA"],
        "crypto_symbols": ["BTC-USD"],
        "min_score_buy": 85,
        "max_score_sell": 15,
        "auto_trade": False,
        "paper_trading": False,
        "live_trading_allowed": False,
        "email_only": False,
        "delay_minutes": 0,
        "alert_channels": ["Email"],
        "login_options": ["Email", "Phone"],
        "broker_options": ["Alpaca preview only"],
        "features": [
            "3-day free trial",
            "2 real-time stock signals",
            "1 crypto signal",
            "confidence score",
            "signal reasons",
            "email alerts",
            "limited dashboard preview",
            "no auto trading"
        ],
        "upgrade_message": "Starter gives a real preview. Upgrade for more stocks, crypto, alerts, paper trading, and automation."
    },

    "pro": {
        "price": "$9.99/month",
        "trial": "1-day free trial",
        "welcome_discount": "First month $4.99",
        "symbols": [
            "AAPL", "TSLA", "NVDA", "MSFT", "AMZN",
            "META", "GOOGL", "AMD"
        ],
        "crypto_symbols": ["BTC-USD", "ETH-USD"],
        "min_score_buy": 75,
        "max_score_sell": 25,
        "auto_trade": False,
        "paper_trading": True,
        "live_trading_allowed": False,
        "email_only": False,
        "delay_minutes": 0,
        "alert_channels": ["Email", "SMS", "Discord"],
        "login_options": ["Email", "Phone", "Google", "Apple", "Discord"],
        "broker_options": ["Alpaca paper preview", "Webull coming soon"],
        "features": [
            "1-day free trial",
            "first month welcome discount",
            "8 stock signals",
            "2 crypto signals",
            "email alerts",
            "SMS alerts",
            "Discord alerts",
            "RSI",
            "MACD",
            "volume filter",
            "confidence scoring",
            "paper trading preview"
        ],
        "upgrade_message": "Upgrade to Elite for more stocks, more crypto, stronger filters, and simulated profit/loss."
    },

    "elite": {
        "price": "$29.99/month",
        "trial": "No trial",
        "welcome_discount": "None",
        "symbols": [
            "AAPL", "TSLA", "NVDA", "MSFT", "AMZN",
            "META", "GOOGL", "AMD", "PLTR", "NFLX",
            "AVGO", "SMCI", "COIN", "MSTR", "SHOP"
        ],
        "crypto_symbols": [
            "BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "DOGE-USD"
        ],
        "min_score_buy": 70,
        "max_score_sell": 30,
        "auto_trade": False,
        "paper_trading": True,
        "live_trading_allowed": False,
        "email_only": False,
        "delay_minutes": 0,
        "alert_channels": ["Email", "SMS", "Discord"],
        "login_options": ["Email", "Phone", "Google", "Apple", "Discord"],
        "broker_options": ["Alpaca paper", "Webull coming soon", "More brokers later"],
        "features": [
            "15 stock signals",
            "5 crypto signals",
            "stronger scoring",
            "confidence engine",
            "paper trading simulator",
            "daily simulated profit/loss",
            "email alerts",
            "SMS alerts",
            "Discord alerts",
            "better filtering"
        ],
        "upgrade_message": "Upgrade to Ultra for paper auto-trading, live charts, and bigger watchlists."
    },

    "ultra": {
        "price": "$59.99/month",
        "trial": "No trial",
        "welcome_discount": "None",
        "symbols": [
            "AAPL", "TSLA", "NVDA", "MSFT", "AMZN",
            "META", "GOOGL", "AMD", "PLTR", "NFLX",
            "AVGO", "SMCI", "COIN", "MSTR", "SHOP",
            "BABA", "TSM", "NIO", "RIVN", "LCID",
            "JPM", "BAC", "WMT", "COST", "DIS",
            "PYPL", "SOFI", "UBER", "SNOW", "CRWD"
        ],
        "crypto_symbols": [
            "BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "DOGE-USD",
            "ADA-USD", "AVAX-USD", "LINK-USD", "LTC-USD", "DOT-USD"
        ],
        "min_score_buy": 68,
        "max_score_sell": 32,
        "auto_trade": True,
        "paper_trading": True,
        "live_trading_allowed": False,
        "email_only": False,
        "delay_minutes": 0,
        "alert_channels": ["Email", "SMS", "Discord"],
        "login_options": ["Email", "Phone", "Google", "Apple", "Discord"],
        "broker_options": ["Alpaca paper", "Webull coming soon", "More brokers later"],
        "features": [
            "30 stock signals",
            "10 crypto signals",
            "paper auto-trading",
            "live stock charts",
            "live crypto charts",
            "daily profit/loss report",
            "email alerts",
            "SMS alerts",
            "Discord alerts",
            "automation access"
        ],
        "upgrade_message": "Upgrade to Mastery Plus for worldwide/global stock scanning, full crypto access, and optional live trading."
    },

    "mastery_plus": {
        "price": "$499/month",
        "trial": "Premium access",
        "welcome_discount": "None",
        "symbols": [
            "AAPL", "TSLA", "NVDA", "MSFT", "AMZN",
            "META", "GOOGL", "AMD", "PLTR", "NFLX",
            "AVGO", "SMCI", "COIN", "MSTR", "SHOP",
            "JPM", "BAC", "WMT", "COST", "DIS",
            "PYPL", "SOFI", "UBER", "SNOW", "CRWD",
            "ADBE", "ORCL", "CRM", "INTC", "QCOM",
            "SPY", "QQQ", "DIA", "IWM", "ARKK",
            "TSM", "BABA", "NIO", "PDD", "JD",
            "ASML", "ARM", "SONY", "TM", "HMC",
            "7203.T", "6758.T", "9984.T",
            "005930.KS",
            "0700.HK", "9988.HK",
            "RMS.PA", "MC.PA",
            "BMW.DE", "VOW3.DE",
            "HSBA.L", "BP.L"
        ],
        "crypto_symbols": [
            "BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "DOGE-USD",
            "ADA-USD", "AVAX-USD", "LINK-USD", "LTC-USD", "DOT-USD",
            "MATIC-USD", "ATOM-USD", "NEAR-USD", "APT-USD", "ARB-USD",
            "OP-USD", "UNI-USD", "AAVE-USD", "FIL-USD", "ETC-USD"
        ],
        "min_score_buy": 65,
        "max_score_sell": 35,
        "auto_trade": True,
        "paper_trading": True,
        "live_trading_allowed": True,
        "email_only": False,
        "delay_minutes": 0,
        "alert_channels": ["Email", "SMS", "Discord"],
        "login_options": ["Email", "Phone", "Google", "Apple", "Discord"],
        "broker_options": ["Alpaca", "Webull coming soon", "SnapTrade-style brokers later"],
        "features": [
            "worldwide/global stock scanning",
            "US stocks",
            "international stocks",
            "ETFs",
            "20 crypto signals",
            "paper trading autopilot",
            "optional live trading",
            "live stock charts",
            "live crypto charts",
            "daily profit/loss email",
            "email alerts",
            "SMS alerts",
            "Discord alerts",
            "premium signal engine",
            "done-for-you mode"
        ],
        "upgrade_message": "Mastery Plus includes the largest stock and crypto access with global market scanning."
    }
}

LICENSE_KEYS = {
    "STARTER-DEMO": "starter",
    "PRO-DEMO": "pro",
    "ELITE-DEMO": "elite",
    "ULTRA-DEMO": "ultra",
    "MASTER-DEMO": "mastery_plus"
}


def get_config(tier):
    return TIER_CONFIGS.get(tier, TIER_CONFIGS["starter"])


def get_watchlist(tier):
    cfg = get_config(tier)
    return cfg["symbols"] + cfg["crypto_symbols"]


def get_alpaca_client(mode="paper"):
    if not tradeapi or not API_KEY or not SECRET_KEY:
        return None

    base_url = LIVE_URL if mode == "live" else PAPER_URL

    try:
        return tradeapi.REST(API_KEY, SECRET_KEY, base_url, api_version="v2")
    except Exception:
        return None


def get_data(symbol, period="5d", interval="5m"):
    try:
        df = yf.Ticker(symbol).history(
            period=period,
            interval=interval,
            auto_adjust=True,
            prepost=False
        )

        if df is None or df.empty:
            return pd.DataFrame()

        df = df.rename(columns=str.lower)
        df = df.dropna()
        return df

    except Exception:
        return pd.DataFrame()


def compute_rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    loss = loss.replace(0, np.nan)
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def analyze_symbol(symbol):
    df = get_data(symbol)

    if df.empty or len(df) < 60:
        return {
            "symbol": symbol,
            "signal": "hold",
            "score": 0,
            "confidence": "none",
            "last_price": 0,
            "reasons": ["no_data_from_yfinance"],
            "bars_received": 0,
            "order_status": "not_executed"
        }

    close = df["close"]
    volume = df["volume"].fillna(0)

    ma20 = close.rolling(20).mean()
    ma50 = close.rolling(50).mean()

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()

    macd = ema12 - ema26
    macd_signal = macd.ewm(span=9, adjust=False).mean()

    rsi = compute_rsi(close)

    last_price = float(close.iloc[-1])
    last_ma20 = float(ma20.iloc[-1])
    last_ma50 = float(ma50.iloc[-1])
    last_macd = float(macd.iloc[-1])
    last_macd_signal = float(macd_signal.iloc[-1])
    last_rsi = float(rsi.iloc[-1])

    avg_volume = float(volume.tail(20).mean()) if len(volume) >= 20 else float(volume.mean())
    last_volume = float(volume.iloc[-1])

    volatility = float(close.pct_change().dropna().tail(20).std()) if len(close) >= 20 else 0.0

    score = 50
    reasons = []

    if last_price > last_ma20 > last_ma50:
        score += 20
        reasons.append("bullish_trend")
    else:
        score -= 20
        reasons.append("bearish_or_weak_trend")

    if last_rsi < 35:
        score += 10
        reasons.append("oversold_rsi")
    elif last_rsi > 70:
        score -= 10
        reasons.append("overbought_rsi")
    else:
        reasons.append("neutral_rsi")

    if last_macd > last_macd_signal:
        score += 15
        reasons.append("bullish_macd")
    else:
        score -= 15
        reasons.append("bearish_macd")

    if avg_volume > 0 and last_volume >= avg_volume * 0.9:
        score += 10
        reasons.append("volume_confirmed")
    else:
        reasons.append("low_volume")

    if volatility > 0.03:
        score -= 30
        reasons.append("high_volatility_risk")
    else:
        reasons.append("stable_volatility")

    score = max(0, min(100, int(score)))

    if score >= 80 or score <= 20:
        confidence = "high"
    elif score >= 60 or score <= 40:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "symbol": symbol,
        "signal": "hold",
        "score": score,
        "confidence": confidence,
        "last_price": round(last_price, 2),
        "reasons": reasons,
        "bars_received": int(len(df)),
        "order_status": "not_executed"
    }


def signal_for_score(score, cfg):
    if score >= cfg["min_score_buy"]:
        return "buy"

    if score >= max(60, cfg["min_score_buy"] - 10):
        return "watch_buy"

    if score <= cfg["max_score_sell"]:
        return "sell"

    if score <= cfg["max_score_sell"] + 10:
        return "watch_sell"

    return "hold"


def get_signals_for_tier(tier):
    cfg = get_config(tier)
    watchlist = get_watchlist(tier)
    signals = []

    for symbol in watchlist:
        result = analyze_symbol(symbol)
        result["signal"] = signal_for_score(result["score"], cfg)
        result["delay_minutes"] = cfg["delay_minutes"]
        signals.append(result)

    return {
        "tier": tier,
        "price": cfg["price"],
        "trial": cfg.get("trial", ""),
        "welcome_discount": cfg.get("welcome_discount", ""),
        "auto_trade": cfg["auto_trade"],
        "paper_trading": cfg["paper_trading"],
        "live_trading_allowed": cfg["live_trading_allowed"],
        "alert_channels": cfg["alert_channels"],
        "login_options": cfg["login_options"],
        "broker_options": cfg["broker_options"],
        "signals": signals
    }


def is_live_tradeable_stock(symbol):
    if symbol.endswith("-USD"):
        return False

    if "." in symbol:
        return False

    return True


def place_live_order(symbol, side, qty=1):
    client = get_alpaca_client("live")

    if client is None:
        return "live_api_unavailable"

    if not is_live_tradeable_stock(symbol):
        return "live_symbol_not_supported"

    try:
        client.submit_order(
            symbol=symbol,
            qty=qty,
            side=side,
            type="market",
            time_in_force="gtc"
        )

        return f"live_{side}_submitted"

    except Exception as e:
        return f"live_error_{str(e)[:80]}"


def execute_trade_cycle(tier, mode="paper"):
    cfg = get_config(tier)
    signals_data = get_signals_for_tier(tier)
    results = []

    for item in signals_data["signals"]:
        item = dict(item)

        trade_side = None

        if item["signal"] == "buy":
            trade_side = "buy"
        elif item["signal"] == "sell":
            trade_side = "sell"

        if trade_side is None:
            item["order_status"] = "not_executed"
            results.append(item)
            continue

        if mode == "paper":
            if not cfg["paper_trading"]:
                item["order_status"] = "paper_trading_not_allowed"
            else:
                item["order_status"] = f"paper_{trade_side}"
                ORDERS.append({
                    "symbol": item["symbol"],
                    "side": trade_side,
                    "entry_price": item["last_price"],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "mode": "paper",
                    "tier": tier
                })

        elif mode == "live":
            if not cfg["live_trading_allowed"]:
                item["order_status"] = "live_trading_not_allowed"
            elif not LIVE_TRADING_ENABLED:
                item["order_status"] = "live_trading_disabled_in_environment"
            else:
                status = place_live_order(item["symbol"], trade_side, qty=1)
                item["order_status"] = status

                if status.startswith("live_") and status.endswith("_submitted"):
                    ORDERS.append({
                        "symbol": item["symbol"],
                        "side": trade_side,
                        "entry_price": item["last_price"],
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "mode": "live",
                        "tier": tier
                    })

        else:
            item["order_status"] = "invalid_mode"

        results.append(item)

    return {
        "tier": tier,
        "mode": mode,
        "auto_trade": cfg["auto_trade"],
        "signals": results
    }


def latest_price(symbol):
    df = get_data(symbol, period="1d", interval="5m")

    if df.empty:
        return 0

    return round(float(df["close"].iloc[-1]), 2)


def get_open_positions(tier):
    positions = {}

    for order in ORDERS:
        if order["tier"] != tier:
            continue

        symbol = order["symbol"]

        if order["side"] == "buy":
            positions[symbol] = order

        elif order["side"] == "sell" and symbol in positions:
            del positions[symbol]

    items = []

    for symbol, order in positions.items():
        current = latest_price(symbol)
        entry = float(order["entry_price"])
        pnl_pct = round(((current - entry) / entry) * 100, 2) if entry else 0

        items.append({
            "symbol": symbol,
            "entry_price": round(entry, 2),
            "current_price": current,
            "pnl_pct": pnl_pct,
            "mode": order["mode"],
            "timestamp": order["timestamp"]
        })

    if not items:
        signals = get_signals_for_tier(tier)["signals"]

        for s in signals:
            if s["signal"] == "buy":
                items.append({
                    "symbol": s["symbol"],
                    "entry_price": s["last_price"],
                    "current_price": s["last_price"],
                    "pnl_pct": 0,
                    "mode": "signal_preview",
                    "timestamp": ""
                })

    return items[:8]


def get_daily_report(tier):
    today = datetime.now(timezone.utc).date()
    today_orders = []

    for order in ORDERS:
        if order["tier"] != tier:
            continue

        try:
            order_date = datetime.fromisoformat(order["timestamp"]).date()

            if order_date == today:
                today_orders.append(order)

        except Exception:
            pass

    open_positions = get_open_positions(tier)
    total_open_pnl = round(sum(x["pnl_pct"] for x in open_positions), 2)

    return {
        "tier": tier,
        "today_orders": len(today_orders),
        "open_positions": len(open_positions),
        "open_pnl_pct_sum": total_open_pnl,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


@app.route("/")
def dashboard():
    tier = request.args.get("tier", "starter")

    if tier not in TIER_CONFIGS:
        tier = "starter"

    html = """
    <!doctype html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>AI Stock Agent Dashboard</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

        <style>
            * { box-sizing: border-box; }

            body {
                margin: 0;
                font-family: Arial, sans-serif;
                background: #0b1020;
                color: #f3f5f7;
            }

            .wrap {
                max-width: 1400px;
                margin: 0 auto;
                padding: 20px;
            }

            .hero {
                background: linear-gradient(135deg, #10172a, #1e293b, #0f172a);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 22px;
                padding: 24px;
                margin-bottom: 20px;
                box-shadow: 0 20px 50px rgba(0,0,0,0.25);
            }

            .hero h1 {
                margin: 0 0 10px 0;
                font-size: 30px;
            }

            .hero p {
                margin: 0;
                color: #cbd5e1;
            }

            .tabs {
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                margin-top: 18px;
            }

            .tab {
                text-decoration: none;
                color: #fff;
                background: #1f2937;
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 999px;
                padding: 10px 16px;
                font-size: 14px;
            }

            .tab.active {
                background: #2563eb;
            }

            .panel {
                background: #111827;
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 20px;
                padding: 18px;
                margin-bottom: 20px;
            }

            .stats {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
                gap: 14px;
            }

            .stat {
                background: #0f172a;
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 16px;
                padding: 16px;
            }

            .stat .label {
                font-size: 13px;
                color: #94a3b8;
                margin-bottom: 8px;
            }

            .stat .value {
                font-size: 22px;
                font-weight: bold;
            }

            .actions {
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                margin-top: 10px;
            }

            .btn {
                border: none;
                border-radius: 12px;
                padding: 12px 16px;
                cursor: pointer;
                font-weight: bold;
            }

            .btn.primary { background: #2563eb; color: #fff; }
            .btn.red { background: #dc2626; color: #fff; }
            .btn.dark { background: #1f2937; color: #fff; }

            .grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
                gap: 14px;
            }

            .card {
                background: #0f172a;
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 18px;
                padding: 16px;
            }

            .muted {
                color: #94a3b8;
                font-size: 14px;
            }

            .pill {
                display: inline-block;
                padding: 6px 10px;
                border-radius: 999px;
                font-size: 12px;
                margin-right: 6px;
                margin-bottom: 6px;
                background: #1f2937;
            }

            .buy { background: rgba(5,150,105,0.25); color: #86efac; }
            .watch_buy { background: rgba(37,99,235,0.25); color: #93c5fd; }
            .hold { background: rgba(100,116,139,0.25); color: #cbd5e1; }
            .watch_sell { background: rgba(245,158,11,0.25); color: #fde68a; }
            .sell { background: rgba(220,38,38,0.25); color: #fca5a5; }

            .feature-list {
                padding-left: 18px;
                color: #cbd5e1;
            }

            .chart-box {
                background: #0f172a;
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 18px;
                padding: 12px;
            }

            .two-col {
                display: grid;
                grid-template-columns: 1.2fr 1fr;
                gap: 18px;
            }

            @media (max-width: 980px) {
                .two-col {
                    grid-template-columns: 1fr;
                }
            }
        </style>
    </head>

    <body>
        <div class="wrap">
            <div class="hero">
                <h1>AI Stock Agent Dashboard</h1>
                <p>Signals, crypto, broker-ready structure, paper trading, premium live chart view, alerts, and tiered access.</p>

                <div class="tabs">
                    {% for t in tier_order %}
                        <a class="tab {% if tier == t %}active{% endif %}" href="/?tier={{ t }}">{{ nice_names[t] }}</a>
                    {% endfor %}
                    <a class="tab" href="#crypto-section">Crypto</a>
                    <a class="tab" href="#report-section">Daily Report</a>
                    <a class="tab" href="#tiers-section">Tiers</a>
                </div>
            </div>

            <div class="panel">
                <div class="stats" id="topStats"></div>
                <div class="actions" id="actionButtons"></div>
            </div>

            <div class="two-col">
                <div class="panel">
                    <h2>Signals</h2>
                    <div class="grid" id="signalGrid"></div>
                </div>

                <div class="panel" id="report-section">
                    <h2>Daily Report</h2>
                    <div class="stats" id="reportStats"></div>
                </div>
            </div>

            <div class="panel" id="portfolio-section">
                <h2>Top Tier Live Graphs / Bot Positions</h2>
                <p class="muted">Ultra and Mastery Plus can view chart monitoring for symbols the bot bought or flagged.</p>
                <div class="grid" id="portfolioGrid"></div>
            </div>

            <div class="panel" id="crypto-section">
                <h2>Crypto Signals</h2>
                <div class="grid" id="cryptoGrid"></div>
            </div>

            <div class="panel" id="tiers-section">
                <h2>Subscription Tiers</h2>
                <div class="grid" id="tierGrid"></div>
            </div>
        </div>

        <script>
            const CURRENT_TIER = "{{ tier }}";
            const TOP_CHART_TIERS = ["ultra", "mastery_plus"];
            const chartStore = {};

            function money(v) {
                return "$" + Number(v || 0).toFixed(2);
            }

            function badgeClass(signal) {
                if (signal === "buy") return "pill buy";
                if (signal === "watch_buy") return "pill watch_buy";
                if (signal === "watch_sell") return "pill watch_sell";
                if (signal === "sell") return "pill sell";
                return "pill hold";
            }

            async function getJSON(url) {
                const res = await fetch(url);
                return await res.json();
            }

            function renderTopStats(tierInfo, signalsInfo) {
                const stats = document.getElementById("topStats");
                const buys = signalsInfo.signals.filter(x => x.signal === "buy").length;
                const sells = signalsInfo.signals.filter(x => x.signal === "sell").length;

                stats.innerHTML = `
                    <div class="stat"><div class="label">Tier</div><div class="value">${CURRENT_TIER.replace("_", " ").toUpperCase()}</div></div>
                    <div class="stat"><div class="label">Price</div><div class="value">${tierInfo.price}</div></div>
                    <div class="stat"><div class="label">Trial</div><div class="value">${tierInfo.trial || "N/A"}</div></div>
                    <div class="stat"><div class="label">Discount</div><div class="value">${tierInfo.welcome_discount || "N/A"}</div></div>
                    <div class="stat"><div class="label">Paper Trading</div><div class="value">${tierInfo.paper_trading}</div></div>
                    <div class="stat"><div class="label">Live Trading</div><div class="value">${tierInfo.live_trading_allowed}</div></div>
                    <div class="stat"><div class="label">Buy Signals</div><div class="value">${buys}</div></div>
                    <div class="stat"><div class="label">Sell Signals</div><div class="value">${sells}</div></div>
                `;
            }

            function renderActions(tierInfo) {
                const actions = document.getElementById("actionButtons");
                let html = `<button class="btn dark" onclick="refreshAll()">Refresh Dashboard</button>`;

                if (tierInfo.paper_trading) {
                    html += `<button class="btn primary" onclick="runBot('paper')">Run Paper Bot</button>`;
                }

                if (tierInfo.live_trading_allowed) {
                    html += `<button class="btn red" onclick="runBot('live')">Run Live Bot</button>`;
                }

                actions.innerHTML = html;
            }

            function renderSignals(signalsInfo) {
                const grid = document.getElementById("signalGrid");

                grid.innerHTML = signalsInfo.signals
                    .filter(x => !x.symbol.includes("-USD"))
                    .map(s => `
                        <div class="card">
                            <h3>${s.symbol}</h3>
                            <div class="${badgeClass(s.signal)}">${s.signal}</div>
                            <p><b>Score:</b> ${s.score}</p>
                            <p><b>Confidence:</b> ${s.confidence}</p>
                            <p><b>Last Price:</b> ${money(s.last_price)}</p>
                            <p><b>Bars Received:</b> ${s.bars_received}</p>
                            <p><b>Order Status:</b> ${s.order_status}</p>
                            <p><b>Reasons:</b> ${s.reasons.join(", ")}</p>
                        </div>
                    `)
                    .join("");
            }

            function renderCrypto(signalsInfo) {
                const grid = document.getElementById("cryptoGrid");
                const crypto = signalsInfo.signals.filter(x => x.symbol.includes("-USD"));

                if (!crypto.length) {
                    grid.innerHTML = `<div class="card"><p>No crypto access on this tier.</p></div>`;
                    return;
                }

                grid.innerHTML = crypto.map(s => `
                    <div class="card">
                        <h3>${s.symbol}</h3>
                        <div class="${badgeClass(s.signal)}">${s.signal}</div>
                        <p><b>Score:</b> ${s.score}</p>
                        <p><b>Confidence:</b> ${s.confidence}</p>
                        <p><b>Last Price:</b> ${money(s.last_price)}</p>
                        <p><b>Bars Received:</b> ${s.bars_received}</p>
                        <p><b>Order Status:</b> ${s.order_status}</p>
                        <p><b>Reasons:</b> ${s.reasons.join(", ")}</p>
                    </div>
                `).join("");
            }

            function renderReport(report) {
                const box = document.getElementById("reportStats");

                box.innerHTML = `
                    <div class="stat"><div class="label">Orders Today</div><div class="value">${report.today_orders}</div></div>
                    <div class="stat"><div class="label">Open Positions</div><div class="value">${report.open_positions}</div></div>
                    <div class="stat"><div class="label">Open PnL % Sum</div><div class="value">${report.open_pnl_pct_sum}%</div></div>
                    <div class="stat"><div class="label">Generated At</div><div class="value" style="font-size:16px">${report.generated_at}</div></div>
                `;
            }

            function renderTiers(tiers) {
                const grid = document.getElementById("tierGrid");
                const order = ["starter", "pro", "elite", "ultra", "mastery_plus"];

                grid.innerHTML = order.map(key => {
                    const t = tiers[key];

                    return `
                        <div class="card">
                            <h3>${key.replace("_", " ").toUpperCase()}</h3>
                            <p><b>Price:</b> ${t.price}</p>
                            <p><b>Trial:</b> ${t.trial || "N/A"}</p>
                            <p><b>Welcome Discount:</b> ${t.welcome_discount || "N/A"}</p>
                            <p><b>Auto Trade:</b> ${t.auto_trade}</p>
                            <p><b>Paper Trading:</b> ${t.paper_trading}</p>
                            <p><b>Live Trading:</b> ${t.live_trading_allowed}</p>
                            <p><b>Alerts:</b> ${t.alert_channels.join(", ")}</p>
                            <p><b>Login Options:</b> ${t.login_options.join(", ")}</p>
                            <p><b>Broker Options:</b> ${t.broker_options.join(", ")}</p>
                            <p><b>Stocks:</b> ${t.symbols.join(", ")}</p>
                            <p><b>Crypto:</b> ${t.crypto_symbols.join(", ")}</p>
                            <p><b>Upgrade Message:</b> ${t.upgrade_message}</p>
                            <ul class="feature-list">
                                ${t.features.map(f => `<li>${f}</li>`).join("")}
                            </ul>
                        </div>
                    `;
                }).join("");
            }

            async function renderPortfolio() {
                const box = document.getElementById("portfolioGrid");

                if (!TOP_CHART_TIERS.includes(CURRENT_TIER)) {
                    box.innerHTML = `
                        <div class="card">
                            <h3>Upgrade needed</h3>
                            <p>Live graph monitoring is available on Ultra and Mastery Plus.</p>
                        </div>
                    `;
                    return;
                }

                const data = await getJSON(`/portfolio?tier=${CURRENT_TIER}`);

                if (!data.items.length) {
                    box.innerHTML = `<div class="card"><p>No positions or active buy previews yet.</p></div>`;
                    return;
                }

                box.innerHTML = data.items.map((item, i) => `
                    <div class="chart-box">
                        <h3>${item.symbol}</h3>
                        <p><b>Entry:</b> ${money(item.entry_price)} | <b>Current:</b> ${money(item.current_price)} | <b>PnL:</b> ${item.pnl_pct}%</p>
                        <p><b>Mode:</b> ${item.mode}</p>
                        <canvas id="chart_${i}" height="120"></canvas>
                    </div>
                `).join("");

                for (let i = 0; i < data.items.length; i++) {
                    await drawChart(`chart_${i}`, data.items[i].symbol);
                }
            }

            async function drawChart(canvasId, symbol) {
                const data = await getJSON(`/chart-data?symbol=${encodeURIComponent(symbol)}`);
                const ctx = document.getElementById(canvasId).getContext("2d");

                if (chartStore[canvasId]) {
                    chartStore[canvasId].destroy();
                }

                chartStore[canvasId] = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: data.labels,
                        datasets: [{
                            label: symbol,
                            data: data.prices,
                            tension: 0.25,
                            borderWidth: 2,
                            fill: false
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { labels: { color: "#f3f5f7" } }
                        },
                        scales: {
                            x: { ticks: { color: "#cbd5e1" }, grid: { color: "rgba(255,255,255,0.08)" } },
                            y: { ticks: { color: "#cbd5e1" }, grid: { color: "rgba(255,255,255,0.08)" } }
                        }
                    }
                });
            }

            async function runBot(mode) {
                await getJSON(`/trade?tier=${CURRENT_TIER}&mode=${mode}`);
                await refreshAll();
            }

            async function refreshAll() {
                const [tiers, signals, report] = await Promise.all([
                    getJSON("/tiers"),
                    getJSON(`/signals?tier=${CURRENT_TIER}`),
                    getJSON(`/report?tier=${CURRENT_TIER}`)
                ]);

                renderTopStats(tiers[CURRENT_TIER], signals);
                renderActions(tiers[CURRENT_TIER]);
                renderSignals(signals);
                renderCrypto(signals);
                renderReport(report);
                renderTiers(tiers);
                await renderPortfolio();
            }

            refreshAll();
            setInterval(refreshAll, CURRENT_TIER === "starter" ? 120000 : 30000);
        </script>
    </body>
    </html>
    """

    return render_template_string(
        html,
        tier=tier,
        tier_order=TIER_ORDER,
        nice_names=NICE_NAMES
    )


@app.route("/status")
def status():
    return jsonify({
        "status": "AI STOCK AGENT RUNNING",
        "routes": [
            "/",
            "/signals?tier=pro",
            "/trade?tier=ultra&mode=paper",
            "/tiers",
            "/report?tier=mastery_plus",
            "/portfolio?tier=ultra",
            "/chart-data?symbol=AAPL",
            "/debug"
        ],
        "live_trading_enabled": LIVE_TRADING_ENABLED
    })


@app.route("/debug")
def debug():
    return jsonify({
        "api_key_loaded": bool(API_KEY),
        "secret_key_loaded": bool(SECRET_KEY),
        "paper_url": PAPER_URL,
        "live_url": LIVE_URL,
        "live_trading_enabled": LIVE_TRADING_ENABLED
    })


@app.route("/tiers")
@app.route("/api/tiers")
def tiers():
    return jsonify(TIER_CONFIGS)


@app.route("/signals")
@app.route("/api/signals")
def signals():
    tier = request.args.get("tier", "starter")
    return jsonify(get_signals_for_tier(tier))


@app.route("/trade")
@app.route("/api/trade")
def trade():
    tier = request.args.get("tier", "starter")
    mode = request.args.get("mode", "paper")
    return jsonify(execute_trade_cycle(tier, mode))


@app.route("/portfolio")
@app.route("/api/portfolio")
def portfolio():
    tier = request.args.get("tier", "starter")

    return jsonify({
        "tier": tier,
        "items": get_open_positions(tier)
    })


@app.route("/report")
@app.route("/api/report")
def report():
    tier = request.args.get("tier", "starter")
    return jsonify(get_daily_report(tier))


@app.route("/chart-data")
@app.route("/api/chart-data")
def chart_data():
    symbol = request.args.get("symbol", "AAPL")
    df = get_data(symbol, period="1d", interval="5m")

    if df.empty:
        return jsonify({
            "symbol": symbol,
            "labels": [],
            "prices": []
        })

    labels = []

    for idx in df.index:
        try:
            labels.append(idx.strftime("%H:%M"))
        except Exception:
            labels.append(str(idx))

    prices = [round(float(x), 2) for x in df["close"].tolist()]

    return jsonify({
        "symbol": symbol,
        "labels": labels,
        "prices": prices
    })


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
        "features": TIER_CONFIGS[tier]["features"],
        "price": TIER_CONFIGS[tier]["price"]
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)