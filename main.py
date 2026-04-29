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
# CONFIG
# =========================
API_KEY = os.getenv("ALPACA_API_KEY", "")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")

PAPER_URL = "https://paper-api.alpaca.markets"
LIVE_URL = "https://api.alpaca.markets"

# Keep this false until everything is tested.
LIVE_TRADING_ENABLED = os.getenv("LIVE_TRADING_ENABLED", "false").lower() == "true"

# Internal demo/paper state. This does NOT place Alpaca paper orders.
ORDERS = []
POSITIONS = {}

TRADE_COOLDOWN_SECONDS = 60 * 60
MAX_TRADES_PER_SYMBOL_PER_DAY = 1
ALLOW_SHORT_SELLING = False

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


def tier_index(tier):
    try:
        return TIER_ORDER.index(tier)
    except ValueError:
        return 0


def get_config(tier):
    return TIER_CONFIGS.get(tier, TIER_CONFIGS["starter"])


def tier_from_key(key):
    return LICENSE_KEYS.get((key or "").strip().upper())


def can_access_tier(requested_tier, key):
    if requested_tier == "starter":
        return True

    unlocked = tier_from_key(key)
    if not unlocked:
        return False

    return tier_index(unlocked) >= tier_index(requested_tier)


def locked_response(requested_tier):
    return jsonify({
        "locked": True,
        "requested_tier": requested_tier,
        "message": "Enter a valid license key to unlock this tier.",
        "hint": "Use PRO-DEMO, ELITE-DEMO, ULTRA-DEMO, or MASTER-DEMO while testing."
    }), 403


def get_watchlist(tier):
    cfg = get_config(tier)
    return cfg["symbols"] + cfg["crypto_symbols"]


def get_data(symbol, period="5d", interval="5m"):
    try:
        df = yf.Ticker(symbol).history(period=period, interval=interval, auto_adjust=True, prepost=False)

        if df is None or df.empty:
            return pd.DataFrame()

        df = df.rename(columns=str.lower).dropna()

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
        "asset_type": "crypto" if symbol.endswith("-USD") else "stock",
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
        "asset_type": "crypto" if symbol.endswith("-USD") else "stock",
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
        client.submit_order(symbol=symbol, qty=qty, side=side, type="market", time_in_force="gtc")
        return f"live_{side}_submitted"
    except Exception as e:
        return f"live_error_{str(e)[:80]}"


def state_key(tier, symbol):
    return f"{tier}:{symbol}"


def paper_position_qty(tier, symbol):
    item = POSITIONS.get(state_key(tier, symbol))
    return int(item.get("qty", 0)) if item else 0


def trades_today_count(tier, symbol):
    today = datetime.now(timezone.utc).date()
    count = 0

    for order in ORDERS:
        if order.get("tier") != tier or order.get("symbol") != symbol:
            continue

        try:
            order_date = datetime.fromisoformat(order.get("timestamp")).date()
            if order_date == today:
                count += 1
        except Exception:
            pass

    return count


def last_trade_seconds_ago(tier, symbol):
    latest_time = None

    for order in ORDERS:
        if order.get("tier") != tier or order.get("symbol") != symbol:
            continue

        try:
            order_time = datetime.fromisoformat(order.get("timestamp"))
            if latest_time is None or order_time > latest_time:
                latest_time = order_time
        except Exception:
            pass

    if latest_time is None:
        return None

    return (datetime.now(timezone.utc) - latest_time).total_seconds()


def record_paper_trade(tier, symbol, side, price):
    key = state_key(tier, symbol)
    current = POSITIONS.get(key, {"qty": 0, "entry_price": 0, "symbol": symbol, "tier": tier})
    qty = int(current.get("qty", 0))

    if side == "buy":
        qty += 1
        current["entry_price"] = price
    elif side == "sell":
        qty -= 1

    if qty <= 0:
        POSITIONS.pop(key, None)
    else:
        current["qty"] = qty
        current["last_price"] = price
        current["timestamp"] = datetime.now(timezone.utc).isoformat()
        POSITIONS[key] = current

    ORDERS.append({
        "symbol": symbol,
        "side": side,
        "entry_price": price,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "paper",
        "tier": tier
    })


def execute_trade_cycle(tier, mode="paper"):
    cfg = get_config(tier)
    signals_data = get_signals_for_tier(tier)
    results = []

    for item in signals_data["signals"]:
        item = dict(item)
        symbol = item["symbol"]

        if item["bars_received"] == 0 or item["last_price"] == 0:
            item["order_status"] = "not_executed_no_data"
            results.append(item)
            continue

        signal = item["signal"]
        current_qty = paper_position_qty(tier, symbol)
        seconds_ago = last_trade_seconds_ago(tier, symbol)
        today_count = trades_today_count(tier, symbol)

        if seconds_ago is not None and seconds_ago < TRADE_COOLDOWN_SECONDS:
            item["order_status"] = "blocked_cooldown"
            results.append(item)
            continue

        if today_count >= MAX_TRADES_PER_SYMBOL_PER_DAY:
            item["order_status"] = "blocked_daily_limit"
            results.append(item)
            continue

        trade_side = None

        if signal == "buy":
            if current_qty > 0:
                item["order_status"] = "already_holding_no_repeat_buy"
                results.append(item)
                continue
            trade_side = "buy"

        elif signal == "sell":
            if current_qty > 0:
                trade_side = "sell"
            else:
                item["order_status"] = "sell_signal_no_position_warning_only"
                results.append(item)
                continue

        else:
            item["order_status"] = "not_executed"
            results.append(item)
            continue

        if mode == "paper":
            if not cfg["paper_trading"]:
                item["order_status"] = "paper_trading_not_allowed"
            else:
                item["order_status"] = f"paper_{trade_side}"
                record_paper_trade(tier, symbol, trade_side, item["last_price"])

        elif mode == "live":
            if not cfg["live_trading_allowed"]:
                item["order_status"] = "live_trading_not_allowed"
            elif not LIVE_TRADING_ENABLED:
                item["order_status"] = "live_trading_disabled_in_environment"
            elif trade_side == "sell" and current_qty <= 0:
                item["order_status"] = "live_sell_blocked_no_position"
            elif trade_side == "buy" and current_qty > 0:
                item["order_status"] = "live_buy_blocked_already_holding"
            else:
                item["order_status"] = place_live_order(symbol, trade_side, qty=1)

        else:
            item["order_status"] = "invalid_mode"

        results.append(item)

    return {
        "tier": tier,
        "mode": mode,
        "safety_rules": {
            "short_selling_allowed": ALLOW_SHORT_SELLING,
            "cooldown_seconds": TRADE_COOLDOWN_SECONDS,
            "max_trades_per_symbol_per_day": MAX_TRADES_PER_SYMBOL_PER_DAY,
            "sell_requires_position": True,
            "repeat_buy_blocked": True
        },
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
    items = []

    for key, position in POSITIONS.items():
        if position.get("tier") != tier:
            continue

        symbol = position["symbol"]
        current = latest_price(symbol)
        entry = float(position.get("entry_price", 0))
        qty = int(position.get("qty", 0))

        if current <= 0 or entry <= 0 or qty <= 0:
            continue

        pnl_pct = round(((current - entry) / entry) * 100, 2)

        items.append({
            "symbol": symbol,
            "qty": qty,
            "entry_price": round(entry, 2),
            "current_price": current,
            "pnl_pct": pnl_pct,
            "mode": "internal_paper",
            "timestamp": position.get("timestamp", "")
        })

    if not items:
        signals = get_signals_for_tier(tier)["signals"]
        for s in signals:
            if s["signal"] == "buy" and s["last_price"] > 0:
                items.append({
                    "symbol": s["symbol"],
                    "qty": 0,
                    "entry_price": s["last_price"],
                    "current_price": s["last_price"],
                    "pnl_pct": 0,
                    "mode": "buy_signal_preview",
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
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>AI Stock Agent Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --bg: #060914;
            --panel: rgba(15, 23, 42, .92);
            --panel2: #0f172a;
            --border: rgba(148, 163, 184, .22);
            --text: #eef2ff;
            --muted: #94a3b8;
            --blue: #3b82f6;
            --green: #10b981;
            --red: #ef4444;
            --yellow: #f59e0b;
        }
        * { box-sizing: border-box; }
        body {
            margin: 0;
            font-family: Inter, Arial, sans-serif;
            background:
                radial-gradient(circle at 15% 15%, rgba(37,99,235,.28), transparent 34%),
                radial-gradient(circle at 90% 10%, rgba(16,185,129,.18), transparent 30%),
                linear-gradient(180deg, #060914, #0b1020 45%, #070a12);
            color: var(--text);
        }
        .wrap { max-width: 1450px; margin: auto; padding: 20px; }
        .hero {
            border: 1px solid var(--border);
            border-radius: 28px;
            padding: 26px;
            background: linear-gradient(135deg, rgba(15,23,42,.94), rgba(30,41,59,.78));
            box-shadow: 0 24px 90px rgba(0,0,0,.35);
            margin-bottom: 18px;
        }
        .topbar { display:flex; justify-content:space-between; gap:16px; flex-wrap:wrap; align-items:flex-start; }
        h1 { margin: 0 0 8px; font-size: clamp(28px, 4vw, 48px); letter-spacing: -1px; }
        h2 { margin: 0 0 14px; }
        h3 { margin: 0 0 10px; }
        p { color:#cbd5e1; }
        .badge { display:inline-flex; gap:8px; align-items:center; padding:8px 12px; border:1px solid var(--border); border-radius:999px; background:rgba(15,23,42,.8); color:#dbeafe; font-weight:700; }
        .tabs { display:flex; flex-wrap:wrap; gap:10px; margin-top:18px; }
        button, input {
            border:0; border-radius:14px; padding:12px 15px; font-weight:800;
        }
        button { cursor:pointer; color:white; background:linear-gradient(135deg,#2563eb,#3b82f6); }
        button:hover { filter:brightness(1.12); transform:translateY(-1px); }
        button.dark { background:#1f2937; border:1px solid var(--border); }
        button.green { background:linear-gradient(135deg,#059669,#10b981); }
        button.red { background:linear-gradient(135deg,#b91c1c,#ef4444); }
        button.gold { background:linear-gradient(135deg,#92400e,#f59e0b); }
        input { background:#0b1220; color:white; border:1px solid var(--border); min-width:260px; outline:none; }
        .panel {
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 24px;
            padding: 18px;
            margin-bottom: 18px;
            box-shadow: 0 10px 40px rgba(0,0,0,.22);
        }
        .grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(270px, 1fr)); gap:14px; }
        .stats { display:grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap:14px; }
        .card, .stat {
            background: linear-gradient(180deg, rgba(15,23,42,.95), rgba(15,23,42,.72));
            border: 1px solid var(--border);
            border-radius: 20px;
            padding: 16px;
        }
        .label { color: var(--muted); font-size: 13px; margin-bottom:6px; }
        .value { font-size: 22px; font-weight: 900; }
        .muted { color: var(--muted); }
        .pill {
            display:inline-block; border-radius:999px; padding:6px 10px; font-size:12px; font-weight:900; text-transform:uppercase;
        }
        .buy { background:rgba(16,185,129,.18); color:#86efac; border:1px solid rgba(16,185,129,.35); }
        .sell { background:rgba(239,68,68,.16); color:#fecaca; border:1px solid rgba(239,68,68,.35); }
        .watch_buy { background:rgba(59,130,246,.18); color:#bfdbfe; border:1px solid rgba(59,130,246,.35); }
        .watch_sell { background:rgba(245,158,11,.17); color:#fde68a; border:1px solid rgba(245,158,11,.35); }
        .hold { background:rgba(148,163,184,.16); color:#e2e8f0; border:1px solid rgba(148,163,184,.25); }
        .rows { display:flex; flex-direction:column; gap:10px; }
        .row { display:flex; justify-content:space-between; gap:10px; border-top:1px solid rgba(148,163,184,.12); padding-top:10px; }
        .actions { display:flex; flex-wrap:wrap; gap:10px; align-items:center; }
        .split { display:grid; grid-template-columns: 1.15fr .85fr; gap:18px; }
        canvas { max-height: 260px; }
        .notice { border:1px solid rgba(245,158,11,.35); background:rgba(245,158,11,.12); border-radius:18px; padding:14px; color:#fde68a; }
        @media (max-width: 920px) { .split { grid-template-columns:1fr; } }
    </style>
</head>
<body>
<div class="wrap">
    <section class="hero">
        <div class="topbar">
            <div>
                <div class="badge">â AI Stock Agent Running</div>
                <h1>AI Stock Agent Dashboard</h1>
                <p>Clean signals, tier access, crypto, internal paper trading, safety rules, reports, and premium charts.</p>
            </div>
            <div class="card" style="min-width:320px;">
                <h3>License Access</h3>
                <p class="muted">No key = Starter only. Demo keys work for testing.</p>
                <div class="actions">
                    <input id="licenseInput" placeholder="Enter license key">
                    <button onclick="saveKey()" class="green">Unlock</button>
                    <button onclick="clearKey()" class="dark">Clear</button>
                </div>
                <p id="licenseStatus" class="muted"></p>
            </div>
        </div>

        <div class="tabs">
            <button onclick="loadTier('starter')">Starter</button>
            <button onclick="loadTier('pro')">Pro</button>
            <button onclick="loadTier('elite')">Elite</button>
            <button onclick="loadTier('ultra')">Ultra</button>
            <button onclick="loadTier('mastery_plus')" class="gold">Mastery Plus</button>
            <button onclick="loadTiers()" class="dark">All Tiers</button>
            <button onclick="loadReport()" class="dark">Daily Report</button>
            <button onclick="loadStatus()" class="dark">Status</button>
        </div>
    </section>

    <section class="panel">
        <div class="topbar">
            <div>
                <h2 id="title">Loading...</h2>
                <p id="subtitle" class="muted"></p>
            </div>
            <div id="actions" class="actions"></div>
        </div>
        <div class="stats" id="stats"></div>
    </section>

    <section class="split">
        <div class="panel">
            <h2>Stock Signals</h2>
            <div class="grid" id="stocks"></div>
        </div>
        <div class="panel">
            <h2>Crypto Signals</h2>
            <div class="grid" id="crypto"></div>
        </div>
    </section>

    <section class="panel">
        <h2>Top Tier Bot Positions / Charts</h2>
        <p class="muted">Ultra and Mastery Plus show bot positions or buy-signal previews.</p>
        <div class="grid" id="portfolio"></div>
    </section>

    <section class="panel">
        <h2>Details</h2>
        <div id="details"></div>
    </section>
</div>

<script>
let currentTier = localStorage.getItem("tier") || "starter";
let licenseKey = localStorage.getItem("licenseKey") || "";
let charts = {};

document.getElementById("licenseInput").value = licenseKey;

function money(v) { return "$" + Number(v || 0).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2}); }
function pct(v) { return Number(v || 0).toFixed(2) + "%"; }
function assetName(s) { return s.symbol.includes("-USD") ? "Crypto" : "Stock"; }

function badgeClass(signal) {
    if (signal === "buy") return "pill buy";
    if (signal === "sell") return "pill sell";
    if (signal === "watch_buy") return "pill watch_buy";
    if (signal === "watch_sell") return "pill watch_sell";
    return "pill hold";
}

async function getJSON(url) {
    const sep = url.includes("?") ? "&" : "?";
    const fullUrl = url + sep + "key=" + encodeURIComponent(licenseKey);
    const res = await fetch(fullUrl);
    const data = await res.json();
    if (!res.ok) throw data;
    return data;
}

async function saveKey() {
    licenseKey = document.getElementById("licenseInput").value.trim();
    localStorage.setItem("licenseKey", licenseKey);
    await checkLicense();
    await loadTier(currentTier);
}

function clearKey() {
    licenseKey = "";
    localStorage.removeItem("licenseKey");
    document.getElementById("licenseInput").value = "";
    document.getElementById("licenseStatus").innerText = "Starter access only.";
    loadTier("starter");
}

async function checkLicense() {
    try {
        const res = await fetch("/license?key=" + encodeURIComponent(licenseKey));
        const data = await res.json();
        document.getElementById("licenseStatus").innerText = data.valid ? "Unlocked: " + data.name : "Starter access only.";
    } catch {
        document.getElementById("licenseStatus").innerText = "Starter access only.";
    }
}

function lockedHTML(err) {
    return `
        <div class="notice">
            <h3>Tier locked</h3>
            <p>${err.message || "Enter a valid license key."}</p>
            <p><b>Testing keys:</b> PRO-DEMO, ELITE-DEMO, ULTRA-DEMO, MASTER-DEMO</p>
        </div>
    `;
}

async function loadTier(tier) {
    currentTier = tier;
    localStorage.setItem("tier", tier);

    document.getElementById("title").innerText = "Loading " + tier + "...";
    document.getElementById("subtitle").innerText = "";
    document.getElementById("stocks").innerHTML = "";
    document.getElementById("crypto").innerHTML = "";
    document.getElementById("portfolio").innerHTML = "";
    document.getElementById("details").innerHTML = "";
    document.getElementById("stats").innerHTML = "";
    document.getElementById("actions").innerHTML = "";

    let tiers, data, report;

    try {
        tiers = await getJSON("/tiers");
        data = await getJSON("/signals?tier=" + tier);
        report = await getJSON("/report?tier=" + tier);
    } catch (err) {
        document.getElementById("title").innerText = "Access Locked";
        document.getElementById("details").innerHTML = lockedHTML(err);
        return;
    }

    const t = tiers[tier];

    document.getElementById("title").innerText = t.name + " â " + t.price;
    document.getElementById("subtitle").innerText = t.upgrade_message || "";

    const buyCount = data.signals.filter(s => s.signal === "buy").length;
    const sellCount = data.signals.filter(s => s.signal === "sell").length;
    const holdCount = data.signals.filter(s => s.signal === "hold").length;
    const watchCount = data.signals.filter(s => s.signal.includes("watch")).length;

    document.getElementById("stats").innerHTML = `
        <div class="stat"><div class="label">Trial</div><div class="value">${t.trial}</div></div>
        <div class="stat"><div class="label">Discount</div><div class="value">${t.welcome_discount}</div></div>
        <div class="stat"><div class="label">Paper Trading</div><div class="value">${t.paper_trading}</div></div>
        <div class="stat"><div class="label">Live Trading</div><div class="value">${t.live_trading_allowed}</div></div>
        <div class="stat"><div class="label">Buy</div><div class="value">${buyCount}</div></div>
        <div class="stat"><div class="label">Bearish</div><div class="value">${sellCount}</div></div>
        <div class="stat"><div class="label">Watch</div><div class="value">${watchCount}</div></div>
        <div class="stat"><div class="label">Hold</div><div class="value">${holdCount}</div></div>
        <div class="stat"><div class="label">Orders Today</div><div class="value">${report.today_orders}</div></div>
        <div class="stat"><div class="label">Open PnL</div><div class="value">${pct(report.open_pnl_pct_sum)}</div></div>
    `;

    let actionHTML = `<button class="dark" onclick="loadTier(currentTier)">Refresh</button>`;

    if (t.paper_trading) actionHTML += `<button onclick="runBot('paper')" class="green">Run Safe Paper Bot</button>`;
    if (t.live_trading_allowed) actionHTML += `<button onclick="runBot('live')" class="red">Try Live Bot</button>`;

    document.getElementById("actions").innerHTML = actionHTML;

    document.getElementById("stocks").innerHTML = renderCards(data.signals.filter(s => !s.symbol.includes("-USD")));
    document.getElementById("crypto").innerHTML = renderCards(data.signals.filter(s => s.symbol.includes("-USD")));

    document.getElementById("details").innerHTML = `
        <div class="grid">
            <div class="card">
                <h3>${t.name}</h3>
                <div class="rows">
                    <div class="row"><span>Alerts</span><b>${t.alert_channels.join(", ")}</b></div>
                    <div class="row"><span>Login Options</span><b>${t.login_options.join(", ")}</b></div>
                    <div class="row"><span>Broker Options</span><b>${t.broker_options.join(", ")}</b></div>
                    <div class="row"><span>Stocks</span><b>${t.symbols.length}</b></div>
                    <div class="row"><span>Crypto</span><b>${t.crypto_symbols.length}</b></div>
                </div>
            </div>
            <div class="card">
                <h3>Features</h3>
                <ul>${t.features.map(f => `<li>${f}</li>`).join("")}</ul>
            </div>
            <div class="card">
                <h3>Safety Rules</h3>
                <ul>
                    <li>No short selling in internal paper mode</li>
                    <li>Sell only closes an owned paper position</li>
                    <li>Repeated buys are blocked</li>
                    <li>1 trade per symbol per day</li>
                    <li>1 hour cooldown per symbol</li>
                    <li>Live trading is locked unless environment says true</li>
                </ul>
            </div>
        </div>
    `;

    await loadPortfolio(tier);
}

function renderCards(items) {
    if (!items.length) return `<div class="card">No data available.</div>`;

    return items.map(s => `
        <div class="card">
            <div class="topbar">
                <h3>${s.symbol}</h3>
                <span class="${badgeClass(s.signal)}">${s.signal === "sell" ? "bearish" : s.signal}</span>
            </div>
            <div class="rows">
                <div class="row"><span>Asset</span><b>${assetName(s)}</b></div>
                <div class="row"><span>Score</span><b>${s.score}/100</b></div>
                <div class="row"><span>Confidence</span><b>${s.confidence}</b></div>
                <div class="row"><span>Last Price</span><b>${money(s.last_price)}</b></div>
                <div class="row"><span>Bars</span><b>${s.bars_received}</b></div>
                <div class="row"><span>Order</span><b>${s.order_status}</b></div>
            </div>
            <p class="muted"><b>Reasons:</b> ${s.reasons.join(", ")}</p>
        </div>
    `).join("");
}

async function runBot(mode) {
    try {
        const result = await getJSON(`/trade?tier=${currentTier}&mode=${mode}`);
        document.getElementById("details").innerHTML = `
            <div class="notice">
                <h3>Bot run completed</h3>
                <p>Mode: ${result.mode}. Short selling: ${result.safety_rules.short_selling_allowed}. Max trades/day: ${result.safety_rules.max_trades_per_symbol_per_day}.</p>
                <p>Sell signals without positions are now warnings only.</p>
            </div>
        ` + document.getElementById("details").innerHTML;
        await loadTier(currentTier);
    } catch (err) {
        document.getElementById("details").innerHTML = lockedHTML(err);
    }
}

async function loadReport() {
    try {
        const report = await getJSON("/report?tier=" + currentTier);
        document.getElementById("details").innerHTML = `
            <div class="card">
                <h3>Daily Report â ${currentTier}</h3>
                <p><b>Orders Today:</b> ${report.today_orders}</p>
                <p><b>Open Positions:</b> ${report.open_positions}</p>
                <p><b>Open PnL % Sum:</b> ${report.open_pnl_pct_sum}%</p>
                <p><b>Generated At:</b> ${report.generated_at}</p>
            </div>
        `;
    } catch (err) {
        document.getElementById("details").innerHTML = lockedHTML(err);
    }
}

async function loadTiers() {
    const tiers = await getJSON("/tiers");
    document.getElementById("details").innerHTML = `<div class="grid">` + Object.keys(tiers).map(k => {
        const t = tiers[k];
        return `
            <div class="card">
                <h3>${t.name}</h3>
                <p><b>Price:</b> ${t.price}</p>
                <p><b>Trial:</b> ${t.trial}</p>
                <p><b>Discount:</b> ${t.welcome_discount}</p>
                <p><b>Stocks:</b> ${t.symbols.length}</p>
                <p><b>Crypto:</b> ${t.crypto_symbols.length}</p>
                <p>${t.upgrade_message}</p>
            </div>
        `;
    }).join("") + `</div>`;
}

async function loadStatus() {
    const status = await getJSON("/status");
    document.getElementById("details").innerHTML = `
        <div class="card">
            <h3>Status</h3>
            <pre style="white-space:pre-wrap;color:#cbd5e1;">${JSON.stringify(status, null, 2)}</pre>
        </div>
    `;
}

async function loadPortfolio(tier) {
    const box = document.getElementById("portfolio");

    if (!["ultra", "mastery_plus"].includes(tier)) {
        box.innerHTML = `<div class="card">Live graph monitoring is available on Ultra and Mastery Plus.</div>`;
        return;
    }

    try {
        const data = await getJSON("/portfolio?tier=" + tier);

        if (!data.items.length) {
            box.innerHTML = `<div class="card">No bot positions or buy previews yet.</div>`;
            return;
        }

        box.innerHTML = data.items.map((p, i) => `
            <div class="card">
                <h3>${p.symbol}</h3>
                <div class="rows">
                    <div class="row"><span>Qty</span><b>${p.qty}</b></div>
                    <div class="row"><span>Entry</span><b>${money(p.entry_price)}</b></div>
                    <div class="row"><span>Current</span><b>${money(p.current_price)}</b></div>
                    <div class="row"><span>PnL</span><b>${pct(p.pnl_pct)}</b></div>
                    <div class="row"><span>Mode</span><b>${p.mode}</b></div>
                </div>
                <canvas id="chart_${i}"></canvas>
            </div>
        `).join("");

        for (let i = 0; i < data.items.length; i++) {
            await drawChart("chart_" + i, data.items[i].symbol);
        }
    } catch (err) {
        box.innerHTML = lockedHTML(err);
    }
}

async function drawChart(id, symbol) {
    const data = await getJSON("/chart-data?symbol=" + encodeURIComponent(symbol));
    const canvas = document.getElementById(id);
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    if (charts[id]) charts[id].destroy();

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
            plugins: { legend: { labels: { color: "white" } } },
            scales: {
                x: { ticks: { color: "#cbd5e1" } },
                y: { ticks: { color: "#cbd5e1" } }
            }
        }
    });
}

checkLicense();
loadTier(currentTier);
</script>
</body>
</html>
""")


@app.route("/status")
def status():
    return jsonify({
        "status": "AI STOCK AGENT RUNNING",
        "live_trading_enabled": LIVE_TRADING_ENABLED,
        "paper_mode": "internal_safe_simulation",
        "safety_rules": {
            "short_selling_allowed": ALLOW_SHORT_SELLING,
            "cooldown_seconds": TRADE_COOLDOWN_SECONDS,
            "max_trades_per_symbol_per_day": MAX_TRADES_PER_SYMBOL_PER_DAY,
            "sell_requires_position": True,
            "repeat_buy_blocked": True
        },
        "routes": [
            "/",
            "/tiers",
            "/signals?tier=pro&key=PRO-DEMO",
            "/signals?tier=mastery_plus&key=MASTER-DEMO",
            "/trade?tier=ultra&mode=paper&key=ULTRA-DEMO",
            "/portfolio?tier=ultra&key=ULTRA-DEMO",
            "/report?tier=mastery_plus&key=MASTER-DEMO",
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
        "live_trading_enabled": LIVE_TRADING_ENABLED,
        "open_internal_positions": len(POSITIONS),
        "internal_orders": len(ORDERS)
    })


@app.route("/tiers")
def tiers():
    return jsonify(TIER_CONFIGS)


@app.route("/signals")
def signals():
    tier = request.args.get("tier", "starter")
    key = request.args.get("key", "")

    if not can_access_tier(tier, key):
        return locked_response(tier)

    return jsonify(get_signals_for_tier(tier))


@app.route("/trade")
def trade():
    tier = request.args.get("tier", "starter")
    mode = request.args.get("mode", "paper")
    key = request.args.get("key", "")

    if not can_access_tier(tier, key):
        return locked_response(tier)

    return jsonify(execute_trade_cycle(tier, mode))


@app.route("/portfolio")
def portfolio():
    tier = request.args.get("tier", "starter")
    key = request.args.get("key", "")

    if not can_access_tier(tier, key):
        return locked_response(tier)

    return jsonify({
        "tier": tier,
        "items": get_open_positions(tier)
    })


@app.route("/report")
def report():
    tier = request.args.get("tier", "starter")
    key = request.args.get("key", "")

    if not can_access_tier(tier, key):
        return locked_response(tier)

    return jsonify(get_daily_report(tier))


@app.route("/chart-data")
def chart_data():
    symbol = request.args.get("symbol", "AAPL")
    df = get_data(symbol, period="1d", interval="5m")

    if df.empty:
        return jsonify({"symbol": symbol, "labels": [], "prices": []})

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

    return jsonify({"symbol": symbol, "labels": labels, "prices": prices})


@app.route("/license")
def license_check():
    key = request.args.get("key", "")
    tier = tier_from_key(key)

    if not tier:
        return jsonify({"valid": False, "tier": None, "name": "Starter only"})

    return jsonify({
        "valid": True,
        "tier": tier,
        "name": TIER_CONFIGS[tier]["name"],
        "price": TIER_CONFIGS[tier]["price"],
        "features": TIER_CONFIGS[tier]["features"]
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
