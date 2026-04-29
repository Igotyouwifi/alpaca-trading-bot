from flask import Flask, jsonify, request
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

API_KEY = os.getenv("ALPACA_API_KEY", "")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")

PAPER_URL = "https://paper-api.alpaca.markets"
LIVE_URL = "https://api.alpaca.markets"

LIVE_TRADING_ENABLED = os.getenv("LIVE_TRADING_ENABLED", "false").lower() == "true"

ORDERS = []

TIER_ORDER = ["starter", "pro", "elite", "ultra", "mastery_plus"]

TIER_CONFIGS = {
    "starter": {
        "name": "Starter Trial",
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
        "alert_channels": ["Email"],
        "login_options": ["Email", "Phone"],
        "broker_options": ["Alpaca preview only"],
        "features": [
            "2 real-time stock signals",
            "1 crypto signal",
            "confidence score",
            "signal reasons",
            "email alerts",
            "limited preview",
            "no auto trading"
        ],
        "upgrade_message": "Starter gives a real preview. Upgrade for more stocks, crypto, alerts, paper trading, and automation."
    },
    "pro": {
        "name": "Pro",
        "price": "$9.99/month",
        "trial": "1-day free trial",
        "welcome_discount": "First month $4.99",
        "symbols": ["AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "META", "GOOGL", "AMD"],
        "crypto_symbols": ["BTC-USD", "ETH-USD"],
        "min_score_buy": 75,
        "max_score_sell": 25,
        "auto_trade": False,
        "paper_trading": True,
        "live_trading_allowed": False,
        "alert_channels": ["Email", "SMS", "Discord"],
        "login_options": ["Email", "Phone", "Google", "Apple", "Discord"],
        "broker_options": ["Alpaca paper preview", "Webull coming soon"],
        "features": [
            "8 stock signals",
            "2 crypto signals",
            "paper trading preview",
            "RSI",
            "MACD",
            "volume filter",
            "confidence scoring",
            "email/SMS/Discord alerts"
        ],
        "upgrade_message": "Upgrade to Elite for more stocks, more crypto, stronger filters, and simulated profit/loss."
    },
    "elite": {
        "name": "Elite",
        "price": "$29.99/month",
        "trial": "No trial",
        "welcome_discount": "None",
        "symbols": [
            "AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "META", "GOOGL", "AMD",
            "PLTR", "NFLX", "AVGO", "SMCI", "COIN", "MSTR", "SHOP"
        ],
        "crypto_symbols": ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "DOGE-USD"],
        "min_score_buy": 70,
        "max_score_sell": 30,
        "auto_trade": False,
        "paper_trading": True,
        "live_trading_allowed": False,
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
            "better filtering"
        ],
        "upgrade_message": "Upgrade to Ultra for paper auto-trading, live charts, and bigger watchlists."
    },
    "ultra": {
        "name": "Ultra",
        "price": "$59.99/month",
        "trial": "No trial",
        "welcome_discount": "None",
        "symbols": [
            "AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "META", "GOOGL", "AMD",
            "PLTR", "NFLX", "AVGO", "SMCI", "COIN", "MSTR", "SHOP",
            "BABA", "TSM", "NIO", "JPM", "BAC", "WMT", "COST", "DIS",
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
            "automation access"
        ],
        "upgrade_message": "Upgrade to Mastery Plus for worldwide/global stock scanning, full crypto access, and optional live trading."
    },
    "mastery_plus": {
        "name": "Mastery Plus",
        "price": "$499/month",
        "trial": "Premium access",
        "welcome_discount": "None",
        "symbols": [
            "AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "META", "GOOGL", "AMD",
            "PLTR", "NFLX", "AVGO", "SMCI", "COIN", "MSTR", "SHOP",
            "JPM", "BAC", "WMT", "COST", "DIS", "PYPL", "SOFI", "UBER",
            "SNOW", "CRWD", "ADBE", "ORCL", "CRM", "INTC", "QCOM",
            "SPY", "QQQ", "DIA", "IWM", "ARKK",
            "TSM", "BABA", "NIO", "PDD", "JD", "ASML", "ARM", "SONY", "TM",
            "7203.T", "6758.T", "005930.KS", "0700.HK", "9988.HK",
            "RMS.PA", "MC.PA", "BMW.DE", "VOW3.DE", "HSBA.L", "BP.L"
        ],
        "crypto_symbols": [
            "BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "DOGE-USD",
            "ADA-USD", "AVAX-USD", "LINK-USD", "LTC-USD", "DOT-USD",
            "ATOM-USD", "NEAR-USD", "AAVE-USD", "FIL-USD", "ETC-USD"
        ],
        "min_score_buy": 65,
        "max_score_sell": 35,
        "auto_trade": True,
        "paper_trading": True,
        "live_trading_allowed": True,
        "alert_channels": ["Email", "SMS", "Discord"],
        "login_options": ["Email", "Phone", "Google", "Apple", "Discord"],
        "broker_options": ["Alpaca", "Webull coming soon", "SnapTrade-style brokers later"],
        "features": [
            "worldwide/global stock scanning",
            "US stocks",
            "international stocks",
            "ETFs",
            "15 crypto signals",
            "paper trading autopilot",
            "optional live trading",
            "live stock charts",
            "live crypto charts",
            "daily profit/loss email",
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

        if "close" not in df.columns:
            return pd.DataFrame()

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


def no_data_signal(symbol, reason="no_data_available_hold_only"):
    return {
        "symbol": symbol,
        "signal": "hold",
        "score": 0,
        "confidence": "none",
        "last_price": 0,
        "reasons": [reason],
        "bars_received": 0,
        "order_status": "not_executed"
    }


def analyze_symbol(symbol):
    df = get_data(symbol)

    if df.empty or len(df) < 60:
        return no_data_signal(symbol)

    close = df["close"].dropna()

    if close.empty:
        return no_data_signal(symbol)

    last_price = float(close.iloc[-1])

    if not np.isfinite(last_price) or last_price <= 0:
        return no_data_signal(symbol, "no_valid_price_hold_only")

    volume = df["volume"].fillna(0) if "volume" in df.columns else pd.Series([0] * len(df))

    ma20 = close.rolling(20).mean()
    ma50 = close.rolling(50).mean()

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()

    macd = ema12 - ema26
    macd_signal = macd.ewm(span=9, adjust=False).mean()

    rsi = compute_rsi(close)

    last_ma20 = float(ma20.iloc[-1])
    last_ma50 = float(ma50.iloc[-1])
    last_macd = float(macd.iloc[-1])
    last_macd_signal = float(macd_signal.iloc[-1])
    last_rsi = float(rsi.iloc[-1])

    avg_volume = float(volume.tail(20).mean()) if len(volume) >= 20 else float(volume.mean())
    last_volume = float(volume.iloc[-1]) if len(volume) else 0

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
    signals = []

    for symbol in get_watchlist(tier):
        result = analyze_symbol(symbol)

        if result["bars_received"] == 0 or result["last_price"] == 0:
            result["signal"] = "hold"
            result["score"] = 0
            result["confidence"] = "none"
            result["reasons"] = ["no_data_available_hold_only"]
            result["order_status"] = "not_executed"
        else:
            result["signal"] = signal_for_score(result["score"], cfg)

        signals.append(result)

    return {
        "tier": tier,
        "name": cfg["name"],
        "price": cfg["price"],
        "trial": cfg["trial"],
        "welcome_discount": cfg["welcome_discount"],
        "auto_trade": cfg["auto_trade"],
        "paper_trading": cfg["paper_trading"],
        "live_trading_allowed": cfg["live_trading_allowed"],
        "alert_channels": cfg["alert_channels"],
        "login_options": cfg["login_options"],
        "broker_options": cfg["broker_options"],
        "signals": signals
    }


def get_alpaca_client(mode="paper"):
    if not tradeapi or not API_KEY or not SECRET_KEY:
        return None

    base_url = LIVE_URL if mode == "live" else PAPER_URL

    try:
        return tradeapi.REST(API_KEY, SECRET_KEY, base_url, api_version="v2")
    except Exception:
        return None


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

        if item["bars_received"] == 0 or item["last_price"] == 0:
            item["order_status"] = "not_executed_no_data"
            results.append(item)
            continue

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
                item["order_status"] = place_live_order(item["symbol"], trade_side, qty=1)

        else:
            item["order_status"] = "invalid_mode"

        results.append(item)

    return {
        "tier": tier,
        "mode": mode,
        "signals": results
    }


def latest_price(symbol):
    df = get_data(symbol, period="1d", interval="5m")

    if df.empty:
        return 0

    try:
        price = float(df["close"].iloc[-1])

        if not np.isfinite(price) or price <= 0:
            return 0

        return round(price, 2)

    except Exception:
        return 0


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

        if current <= 0 or entry <= 0:
            continue

        pnl_pct = round(((current - entry) / entry) * 100, 2)

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
            if s["signal"] == "buy" and s["last_price"] > 0:
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
    return """
<!DOCTYPE html>
<html>
<head>
    <title>AI Stock Agent Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {
            margin: 0;
            font-family: Arial, sans-serif;
            background: #0b1020;
            color: white;
        }

        .wrap {
            max-width: 1400px;
            margin: auto;
            padding: 20px;
        }

        .hero {
            background: linear-gradient(135deg, #111827, #1e293b);
            border-radius: 22px;
            padding: 25px;
            margin-bottom: 20px;
            border: 1px solid #334155;
        }

        h1 {
            margin-top: 0;
        }

        button {
            border: 0;
            border-radius: 10px;
            padding: 11px 15px;
            margin: 5px;
            font-weight: bold;
            cursor: pointer;
            background: #2563eb;
            color: white;
        }

        button.red {
            background: #dc2626;
        }

        button.dark {
            background: #1f2937;
        }

        .panel {
            background: #111827;
            border: 1px solid #334155;
            border-radius: 18px;
            padding: 18px;
            margin-bottom: 20px;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(270px, 1fr));
            gap: 14px;
        }

        .card {
            background: #0f172a;
            border: 1px solid #334155;
            border-radius: 16px;
            padding: 15px;
        }

        .stat {
            background: #0f172a;
            border: 1px solid #334155;
            border-radius: 16px;
            padding: 15px;
        }

        .label {
            color: #94a3b8;
            font-size: 13px;
        }

        .value {
            font-size: 22px;
            font-weight: bold;
        }

        .pill {
            display: inline-block;
            border-radius: 999px;
            padding: 5px 10px;
            font-weight: bold;
        }

        .buy { background: #064e3b; color: #86efac; }
        .sell { background: #7f1d1d; color: #fecaca; }
        .watch_buy { background: #1e3a8a; color: #bfdbfe; }
        .watch_sell { background: #78350f; color: #fde68a; }
        .hold { background: #334155; color: #e2e8f0; }

        canvas {
            max-height: 260px;
        }

        a {
            color: #93c5fd;
        }
    </style>
</head>
<body>
<div class="wrap">
    <div class="hero">
        <h1>AI Stock Agent Dashboard</h1>
        <p>Signals, crypto, paper trading, premium live charts, tiers, and daily report.</p>

        <button onclick="loadTier('starter')">Starter Trial</button>
        <button onclick="loadTier('pro')">Pro</button>
        <button onclick="loadTier('elite')">Elite</button>
        <button onclick="loadTier('ultra')">Ultra</button>
        <button onclick="loadTier('mastery_plus')">Mastery Plus</button>
        <button class="dark" onclick="loadTiers()">Tiers</button>
        <button class="dark" onclick="loadReport()">Daily Report</button>
    </div>

    <div class="panel">
        <h2 id="title">Loading...</h2>
        <div class="grid" id="stats"></div>
        <div id="actions"></div>
    </div>

    <div class="panel">
        <h2>Stock Signals</h2>
        <div class="grid" id="stocks"></div>
    </div>

    <div class="panel">
        <h2>Crypto Signals</h2>
        <div class="grid" id="crypto"></div>
    </div>

    <div class="panel">
        <h2>Top Tier Bot Positions / Charts</h2>
        <div class="grid" id="portfolio"></div>
    </div>

    <div class="panel">
        <h2>Details</h2>
        <div id="details"></div>
    </div>
</div>

<script>
let currentTier = "pro";
let charts = {};

function money(v) {
    return "$" + Number(v || 0).toFixed(2);
}

function badgeClass(signal) {
    if (signal === "buy") return "pill buy";
    if (signal === "sell") return "pill sell";
    if (signal === "watch_buy") return "pill watch_buy";
    if (signal === "watch_sell") return "pill watch_sell";
    return "pill hold";
}

async function getJSON(url) {
    const res = await fetch(url);
    return await res.json();
}

async function loadTier(tier) {
    currentTier = tier;

    document.getElementById("title").innerText = "Loading " + tier + "...";
    document.getElementById("stocks").innerHTML = "";
    document.getElementById("crypto").innerHTML = "";
    document.getElementById("portfolio").innerHTML = "";
    document.getElementById("details").innerHTML = "";

    const tiers = await getJSON("/tiers");
    const data = await getJSON("/signals?tier=" + tier);
    const report = await getJSON("/report?tier=" + tier);

    const t = tiers[tier];

    document.getElementById("title").innerText = t.name + " — " + t.price;

    const buyCount = data.signals.filter(s => s.signal === "buy").length;
    const sellCount = data.signals.filter(s => s.signal === "sell").length;

    document.getElementById("stats").innerHTML = `
        <div class="stat"><div class="label">Trial</div><div class="value">${t.trial}</div></div>
        <div class="stat"><div class="label">Discount</div><div class="value">${t.welcome_discount}</div></div>
        <div class="stat"><div class="label">Paper Trading</div><div class="value">${t.paper_trading}</div></div>
        <div class="stat"><div class="label">Live Trading</div><div class="value">${t.live_trading_allowed}</div></div>
        <div class="stat"><div class="label">Buy Signals</div><div class="value">${buyCount}</div></div>
        <div class="stat"><div class="label">Sell Signals</div><div class="value">${sellCount}</div></div>
        <div class="stat"><div class="label">Orders Today</div><div class="value">${report.today_orders}</div></div>
        <div class="stat"><div class="label">Open PnL Sum</div><div class="value">${report.open_pnl_pct_sum}%</div></div>
    `;

    let actionHTML = `<button class="dark" onclick="loadTier(currentTier)">Refresh</button>`;

    if (t.paper_trading) {
        actionHTML += `<button onclick="runBot('paper')">Run Paper Bot</button>`;
    }

    if (t.live_trading_allowed) {
        actionHTML += `<button class="red" onclick="runBot('live')">Run Live Bot</button>`;
    }

    document.getElementById("actions").innerHTML = actionHTML;

    const stocks = data.signals.filter(s => !s.symbol.includes("-USD"));
    const crypto = data.signals.filter(s => s.symbol.includes("-USD"));

    document.getElementById("stocks").innerHTML = renderCards(stocks);
    document.getElementById("crypto").innerHTML = renderCards(crypto);

    document.getElementById("details").innerHTML = `
        <div class="card">
            <h3>${t.name}</h3>
            <p><b>Alerts:</b> ${t.alert_channels.join(", ")}</p>
            <p><b>Login Options:</b> ${t.login_options.join(", ")}</p>
            <p><b>Broker Options:</b> ${t.broker_options.join(", ")}</p>
            <p><b>Upgrade Message:</b> ${t.upgrade_message}</p>
            <p><b>Features:</b></p>
            <ul>${t.features.map(f => `<li>${f}</li>`).join("")}</ul>
        </div>
    `;

    await loadPortfolio(tier);
}

function renderCards(items) {
    if (!items.length) {
        return `<div class="card">No data available.</div>`;
    }

    return items.map(s => `
        <div class="card">
            <h3>${s.symbol}</h3>
            <div class="${badgeClass(s.signal)}">${s.signal}</div>
            <p><b>Score:</b> ${s.score}</p>
            <p><b>Confidence:</b> ${s.confidence}</p>
            <p><b>Last Price:</b> ${money(s.last_price)}</p>
            <p><b>Bars:</b> ${s.bars_received}</p>
            <p><b>Order:</b> ${s.order_status}</p>
            <p><b>Reasons:</b> ${s.reasons.join(", ")}</p>
        </div>
    `).join("");
}

async function runBot(mode) {
    await getJSON(`/trade?tier=${currentTier}&mode=${mode}`);
    await loadTier(currentTier);
}

async function loadReport() {
    const report = await getJSON("/report?tier=" + currentTier);
    document.getElementById("details").innerHTML = `
        <div class="card">
            <h3>Daily Report — ${currentTier}</h3>
            <p><b>Orders Today:</b> ${report.today_orders}</p>
            <p><b>Open Positions:</b> ${report.open_positions}</p>
            <p><b>Open PnL % Sum:</b> ${report.open_pnl_pct_sum}%</p>
            <p><b>Generated At:</b> ${report.generated_at}</p>
        </div>
    `;
}

async function loadTiers() {
    const tiers = await getJSON("/tiers");
    document.getElementById("details").innerHTML = Object.keys(tiers).map(k => {
        const t = tiers[k];
        return `
            <div class="card">
                <h3>${t.name}</h3>
                <p><b>Price:</b> ${t.price}</p>
                <p><b>Trial:</b> ${t.trial}</p>
                <p><b>Discount:</b> ${t.welcome_discount}</p>
                <p><b>Stocks:</b> ${t.symbols.join(", ")}</p>
                <p><b>Crypto:</b> ${t.crypto_symbols.join(", ")}</p>
                <p><b>Features:</b> ${t.features.join(", ")}</p>
            </div>
        `;
    }).join("");
}

async function loadPortfolio(tier) {
    const box = document.getElementById("portfolio");

    if (!["ultra", "mastery_plus"].includes(tier)) {
        box.innerHTML = `<div class="card">Live graph monitoring is available on Ultra and Mastery Plus.</div>`;
        return;
    }

    const data = await getJSON("/portfolio?tier=" + tier);

    if (!data.items.length) {
        box.innerHTML = `<div class="card">No bot positions or buy previews yet.</div>`;
        return;
    }

    box.innerHTML = data.items.map((p, i) => `
        <div class="card">
            <h3>${p.symbol}</h3>
            <p><b>Entry:</b> ${money(p.entry_price)}</p>
            <p><b>Current:</b> ${money(p.current_price)}</p>
            <p><b>PnL:</b> ${p.pnl_pct}%</p>
            <canvas id="chart_${i}"></canvas>
        </div>
    `).join("");

    for (let i = 0; i < data.items.length; i++) {
        await drawChart("chart_" + i, data.items[i].symbol);
    }
}

async function drawChart(id, symbol) {
    const data = await getJSON("/chart-data?symbol=" + encodeURIComponent(symbol));
    const ctx = document.getElementById(id).getContext("2d");

    if (charts[id]) {
        charts[id].destroy();
    }

    charts[id] = new Chart(ctx, {
        type: "line",
        data: {
            labels: data.labels,
            datasets: [{
                label: symbol,
                data: data.prices,
                borderWidth: 2,
                tension: 0.25
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { labels: { color: "white" } }
            },
            scales: {
                x: { ticks: { color: "#cbd5e1" } },
                y: { ticks: { color: "#cbd5e1" } }
            }
        }
    });
}

loadTier("pro");
</script>
</body>
</html>
"""


@app.route("/status")
def status():
    return jsonify({
        "status": "AI STOCK AGENT RUNNING",
        "live_trading_enabled": LIVE_TRADING_ENABLED,
        "routes": [
            "/",
            "/tiers",
            "/signals?tier=pro",
            "/signals?tier=mastery_plus",
            "/trade?tier=ultra&mode=paper",
            "/portfolio?tier=ultra",
            "/report?tier=mastery_plus",
            "/chart-data?symbol=AAPL",
            "/license?key=PRO-DEMO",
            "/debug"
        ]
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
def tiers():
    return jsonify(TIER_CONFIGS)


@app.route("/signals")
def signals():
    tier = request.args.get("tier", "starter")
    return jsonify(get_signals_for_tier(tier))


@app.route("/trade")
def trade():
    tier = request.args.get("tier", "starter")
    mode = request.args.get("mode", "paper")
    return jsonify(execute_trade_cycle(tier, mode))


@app.route("/portfolio")
def portfolio():
    tier = request.args.get("tier", "starter")
    return jsonify({
        "tier": tier,
        "items": get_open_positions(tier)
    })


@app.route("/report")
def report():
    tier = request.args.get("tier", "starter")
    return jsonify(get_daily_report(tier))


@app.route("/chart-data")
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
    prices = []

    for idx, row in df.iterrows():
        try:
            price = float(row["close"])

            if np.isfinite(price) and price > 0:
                labels.append(idx.strftime("%H:%M"))
                prices.append(round(price, 2))

        except Exception:
            pass

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
        "price": TIER_CONFIGS[tier]["price"],
        "features": TIER_CONFIGS[tier]["features"]
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)