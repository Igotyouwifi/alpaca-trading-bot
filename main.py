from flask import Flask, jsonify, request, render_template_string
import os
from datetime import datetime, timezone
import pandas as pd
import numpy as np
import yfinance as yf
import requests
import uuid

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

# Server-side broker sessions. Secrets are never sent back to the browser.
# This persists through page refresh while the Render service process stays alive.
# For permanent production storage, use encrypted DB/secret manager, not browser localStorage.
BROKER_CONNECTIONS = {}

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

# Payment-first access keys.
# Give these keys only AFTER payment/trial checkout is completed.
# For real launch, move keys into a database or environment variables.
LICENSE_KEYS = {
    "STARTER-TRIAL-PAID": "starter",
    "PRO-TRIAL-PAID": "pro",
    "PRO-PAID": "pro",
    "ELITE-PAID": "elite",
    "ULTRA-PAID": "ultra",
    "MASTER-PAID": "mastery_plus"
}

PAYMENT_LINKS = {
    "starter": "PUT_YOUR_STARTER_TRIAL_PAYMENT_LINK_HERE",
    "pro": "PUT_YOUR_PRO_PAYMENT_LINK_HERE",
    "elite": "PUT_YOUR_ELITE_PAYMENT_LINK_HERE",
    "ultra": "PUT_YOUR_ULTRA_PAYMENT_LINK_HERE",
    "mastery_plus": "PUT_YOUR_MASTERY_PLUS_PAYMENT_LINK_HERE"
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
    # Payment-first rule:
    # No key means NO trial unlock, not even Starter.
    unlocked = tier_from_key(key)
    if not unlocked:
        return False

    return tier_index(unlocked) >= tier_index(requested_tier)


def locked_response(requested_tier):
    cfg = get_config(requested_tier)
    return jsonify({
        "locked": True,
        "payment_required": True,
        "requested_tier": requested_tier,
        "tier_name": cfg["name"],
        "price": cfg["price"],
        "trial": cfg["trial"],
        "checkout_link": PAYMENT_LINKS.get(requested_tier, ""),
        "message": "Payment method required before trial unlock. Complete checkout, then enter your license key.",
        "next_step": "Replace the checkout_link placeholder in main.py with your real payment link."
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



def mask_secret(value):
    if not value:
        return ""
    value = str(value)
    if len(value) <= 8:
        return value[:2] + "****"
    return value[:4] + "****" + value[-4:]


def alpaca_base_for_mode(mode):
    return LIVE_URL if mode == "live" else PAPER_URL


def test_alpaca_credentials(api_key, secret_key, mode="paper"):
    base_url = alpaca_base_for_mode(mode)
    url = base_url.rstrip("/") + "/v2/account"

    headers = {
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": secret_key
    }

    try:
        response = requests.get(url, headers=headers, timeout=12)

        if response.status_code != 200:
            return {
                "ok": False,
                "status_code": response.status_code,
                "message": "Connection failed. Check the key, secret, and whether it is paper or live."
            }

        data = response.json()

        return {
            "ok": True,
            "status_code": response.status_code,
            "account_status": data.get("status", "unknown"),
            "trading_blocked": data.get("trading_blocked", None),
            "account_blocked": data.get("account_blocked", None),
            "currency": data.get("currency", "USD"),
            "buying_power": data.get("buying_power", None),
            "portfolio_value": data.get("portfolio_value", None),
            "message": "Connected successfully."
        }

    except Exception as e:
        return {
            "ok": False,
            "status_code": 0,
            "message": "Connection error: " + str(e)[:120]
        }


def broker_status_from_token(token):
    item = BROKER_CONNECTIONS.get(token)

    if not item:
        return {
            "connected": False,
            "message": "No broker connected on this server session."
        }

    return {
        "connected": True,
        "mode": item.get("mode", "paper"),
        "api_key_masked": mask_secret(item.get("api_key", "")),
        "account_status": item.get("account_status", "unknown"),
        "trading_blocked": item.get("trading_blocked", None),
        "account_blocked": item.get("account_blocked", None),
        "currency": item.get("currency", "USD"),
        "buying_power": item.get("buying_power", None),
        "portfolio_value": item.get("portfolio_value", None),
        "live_trading_enabled": LIVE_TRADING_ENABLED,
        "message": "Broker connected. Secret is stored server-side only for this running session."
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
            --bg2: #0b1020;
            --panel: rgba(10, 16, 30, .90);
            --panel2: rgba(15, 23, 42, .94);
            --border: rgba(148, 163, 184, .22);
            --text: #eef2ff;
            --soft: #dbeafe;
            --muted: #94a3b8;
            --accent: #4f7cff;
            --accent2: #7c3aed;
            --accent3: #22c55e;
            --glow: rgba(79, 124, 255, .28);
            --heroA: rgba(79,124,255,.22);
            --heroB: rgba(124,58,237,.18);
            --heroC: rgba(34,197,94,.14);
            --buttonText: #ffffff;
            --shadow: rgba(0,0,0,.38);
        }
        * { box-sizing: border-box; }
        html { scroll-behavior: smooth; }
        body {
            margin: 0;
            font-family: Inter, Arial, sans-serif;
            min-height: 100vh;
            background:
                radial-gradient(circle at 8% 10%, var(--heroA), transparent 28%),
                radial-gradient(circle at 88% 12%, var(--heroB), transparent 30%),
                radial-gradient(circle at 60% 80%, var(--heroC), transparent 26%),
                linear-gradient(180deg, var(--bg), var(--bg2) 55%, #050811);
            color: var(--text);
            transition: background .45s ease, color .25s ease;
        }
        .wrap { max-width: 1480px; margin: auto; padding: 24px; }
        .warning-top {
            display:flex;
            justify-content:space-between;
            gap:14px;
            align-items:center;
            margin-bottom:16px;
            padding:14px 16px;
            border-radius:18px;
            border:1px solid rgba(245,158,11,.35);
            background:linear-gradient(135deg, rgba(245,158,11,.18), rgba(15,23,42,.72));
            color:#fde68a;
            box-shadow: 0 10px 34px rgba(0,0,0,.22);
        }
        .warning-mini {
            color:#fef3c7;
            font-size:13px;
            font-weight:800;
            white-space:nowrap;
        }
        .hero {
            position: relative;
            overflow: hidden;
            border: 1px solid var(--border);
            border-radius: 30px;
            padding: 28px;
            background:
                linear-gradient(135deg, rgba(8,12,24,.92), rgba(16,24,40,.84)),
                linear-gradient(135deg, var(--heroA), transparent 48%);
            box-shadow: 0 24px 90px var(--shadow), inset 0 1px 0 rgba(255,255,255,.03);
            margin-bottom: 18px;
        }
        .hero::before {
            content: "";
            position: absolute;
            right: -80px;
            top: -80px;
            width: 260px;
            height: 260px;
            border-radius: 50%;
            background: radial-gradient(circle, var(--glow), transparent 65%);
            filter: blur(18px);
            pointer-events: none;
        }
        .hero::after {
            content: "";
            position: absolute;
            left: -50px;
            bottom: -70px;
            width: 220px;
            height: 220px;
            border-radius: 50%;
            background: radial-gradient(circle, var(--heroB), transparent 70%);
            filter: blur(14px);
            pointer-events: none;
        }
        .topbar { display:flex; justify-content:space-between; gap:16px; flex-wrap:wrap; align-items:flex-start; position:relative; z-index:1; }
        h1 { margin: 0 0 8px; font-size: clamp(30px, 4vw, 52px); line-height: 1; letter-spacing: -1.4px; }
        h2 { margin: 0 0 14px; font-size: 28px; }
        h3 { margin: 0 0 10px; }
        p { color:#cbd5e1; }
        .badge {
            display:inline-flex;
            gap:8px;
            align-items:center;
            padding:8px 12px;
            border:1px solid rgba(255,255,255,.08);
            border-radius:999px;
            background:rgba(255,255,255,.05);
            color:var(--soft);
            font-weight:800;
            backdrop-filter: blur(10px);
        }
        .hero-meta {
            display:flex;
            flex-wrap:wrap;
            gap:10px;
            margin:14px 0 0;
        }
        .theme-badge {
            background: linear-gradient(135deg, rgba(255,255,255,.10), rgba(255,255,255,.04));
            border-color: rgba(255,255,255,.12);
        }
        .tier-glance {
            display:grid;
            grid-template-columns: repeat(3, minmax(120px,1fr));
            gap:10px;
            margin-top:16px;
            max-width: 560px;
        }
        .mini-stat {
            border:1px solid rgba(255,255,255,.08);
            background: rgba(255,255,255,.04);
            border-radius: 16px;
            padding: 12px;
            backdrop-filter: blur(10px);
        }
        .mini-stat .k { color: var(--muted); font-size: 12px; display:block; margin-bottom: 5px; }
        .mini-stat .v { font-size: 18px; font-weight: 900; color: var(--soft); }
        .tabs {
            display:flex;
            flex-wrap:wrap;
            gap:10px;
            margin-top:18px;
            position:relative;
            z-index:1;
        }
        button, input {
            border:0;
            border-radius:14px;
            padding:12px 15px;
            font-weight:800;
        }
        button {
            cursor:pointer;
            color:var(--buttonText);
            background:linear-gradient(135deg,var(--accent),var(--accent2));
            box-shadow: 0 12px 28px rgba(0,0,0,.18);
            transition: transform .18s ease, filter .18s ease, box-shadow .18s ease, border-color .18s ease;
        }
        button:hover { filter:brightness(1.08); transform:translateY(-1px); }
        button.dark {
            background:rgba(255,255,255,.04);
            border:1px solid var(--border);
            color: var(--text);
            box-shadow:none;
        }
        button.green { background:linear-gradient(135deg,#059669,#10b981); }
        button.red { background:linear-gradient(135deg,#b91c1c,#ef4444); }
        button.gold { background:linear-gradient(135deg,#b45309,#f59e0b); }
        button.tier-btn.active {
            outline: 2px solid rgba(255,255,255,.18);
            box-shadow: 0 0 0 3px var(--glow), 0 12px 28px rgba(0,0,0,.22);
        }
        select {
            background:#091120;
            color:white;
            border:1px solid var(--border);
            border-radius:14px;
            padding:12px 15px;
            font-weight:800;
            outline:none;
        }
        select:focus { border-color: var(--accent); box-shadow: 0 0 0 4px var(--glow); }
        .broker-grid {
            display:grid;
            grid-template-columns: 1.1fr .9fr;
            gap:14px;
        }
        .broker-form input { min-width: 210px; }
        .broker-connect {
            border-color: rgba(34,197,94,.22);
        }
        input {
            background:#091120;
            color:white;
            border:1px solid var(--border);
            min-width:260px;
            outline:none;
        }
        input:focus { border-color: var(--accent); box-shadow: 0 0 0 4px var(--glow); }
        .panel {
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 24px;
            padding: 18px;
            margin-bottom: 18px;
            box-shadow: 0 12px 36px rgba(0,0,0,.22), inset 0 1px 0 rgba(255,255,255,.02);
            backdrop-filter: blur(16px);
        }
        .grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(270px, 1fr)); gap:14px; }
        .stats { display:grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap:14px; }
        .card, .stat {
            background: linear-gradient(180deg, rgba(255,255,255,.05), rgba(255,255,255,.02));
            border: 1px solid rgba(255,255,255,.08);
            border-radius: 20px;
            padding: 16px;
            box-shadow: inset 0 1px 0 rgba(255,255,255,.02);
        }
        .stat {
            position: relative;
            overflow: hidden;
        }
        .stat::before {
            content: "";
            position: absolute;
            inset: 0 auto 0 0;
            width: 4px;
            background: linear-gradient(180deg, var(--accent), var(--accent2));
            opacity: .95;
        }
        .label { color: var(--muted); font-size: 13px; margin-bottom:6px; text-transform: uppercase; letter-spacing: .06em; }
        .value { font-size: 22px; font-weight: 900; color: var(--soft); }
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
        .row { display:flex; justify-content:space-between; gap:10px; border-top:1px solid rgba(255,255,255,.08); padding-top:10px; }
        .actions { display:flex; flex-wrap:wrap; gap:10px; align-items:center; }
        .split { display:grid; grid-template-columns: 1.15fr .85fr; gap:18px; }
        .section-head { display:flex; justify-content:space-between; gap:12px; align-items:center; flex-wrap:wrap; margin-bottom:10px; }
        .theme-strip {
            display:flex;
            flex-wrap:wrap;
            gap:8px;
        }
        .theme-chip {
            padding:8px 12px;
            border-radius:999px;
            font-weight:800;
            font-size:12px;
            border:1px solid rgba(255,255,255,.08);
            background:rgba(255,255,255,.04);
            color:var(--soft);
        }
        .theme-card {
            position: relative;
            overflow: hidden;
            min-height: 180px;
        }
        .theme-card::after {
            content: "";
            position: absolute;
            inset: auto -40px -50px auto;
            width: 180px;
            height: 180px;
            border-radius: 50%;
            background: radial-gradient(circle, var(--glow), transparent 66%);
            filter: blur(8px);
            pointer-events: none;
        }
        .tier-emblem {
            width: 56px;
            height: 56px;
            border-radius: 18px;
            display:flex;
            align-items:center;
            justify-content:center;
            font-size: 30px;
            background: linear-gradient(135deg, var(--accent), var(--accent2));
            box-shadow: 0 12px 32px var(--glow);
            margin-bottom: 12px;
        }
        .theme-line {
            height: 8px;
            border-radius: 999px;
            background: linear-gradient(90deg, var(--accent), var(--accent2), var(--accent3));
            margin: 12px 0 4px;
        }
        canvas { max-height: 260px; }
        .notice {
            border:1px solid rgba(245,158,11,.35);
            background:rgba(245,158,11,.12);
            border-radius:18px;
            padding:14px;
            color:#fde68a;
        }
        .footer-note { color: var(--muted); font-size: 12px; }
        .theme-picker-wrap {
            margin-top:18px;
            padding:16px;
            border-radius:22px;
            border:1px solid rgba(255,255,255,.08);
            background: rgba(255,255,255,.035);
            position:relative;
            z-index:1;
        }
        .theme-picker {
            display:grid;
            grid-template-columns: repeat(auto-fit, minmax(165px, 1fr));
            gap:10px;
        }
        .theme-option {
            text-align:left;
            border:1px solid rgba(255,255,255,.10);
            background:rgba(255,255,255,.04);
            color:var(--text);
            border-radius:18px;
            padding:13px;
            box-shadow:none;
        }
        .theme-option:hover {
            border-color:var(--accent);
            box-shadow:0 0 0 4px var(--glow);
        }
        .theme-option.locked {
            opacity:.45;
            cursor:not-allowed;
            filter:grayscale(.2);
        }
        .theme-option.active {
            border-color:var(--accent);
            box-shadow:0 0 0 4px var(--glow), 0 14px 32px rgba(0,0,0,.24);
        }
        .theme-dot {
            width:28px;
            height:28px;
            border-radius:10px;
            display:inline-flex;
            align-items:center;
            justify-content:center;
            margin-bottom:8px;
            background:linear-gradient(135deg,var(--accent),var(--accent2));
            color:white;
            font-size:15px;
        }
        .theme-option-title {
            font-weight:900;
            display:block;
            margin-bottom:3px;
        }
        .theme-option-sub {
            color:var(--muted);
            font-size:12px;
        }

        .card, .stat, .theme-option, .signal-card, .mode-card {
            transition: transform .14s ease, box-shadow .14s ease, border-color .14s ease, filter .14s ease, background .14s ease;
        }
        .card:hover, .stat:hover, .signal-card:hover {
            transform: translateY(-3px);
            border-color: rgba(255,255,255,.18);
            box-shadow: 0 18px 44px rgba(0,0,0,.30), 0 0 0 4px var(--glow);
        }
        .card:active, .stat:active, .theme-option:active, .signal-card:active, button:active, .mode-card:active {
            transform: scale(.985) translateY(1px);
            filter: brightness(1.08);
        }
        button, .mode-card, .theme-option {
            position: relative;
            overflow: hidden;
            -webkit-tap-highlight-color: transparent;
        }
        button::after, .mode-card::after, .theme-option::after {
            content: "";
            position: absolute;
            inset: 0;
            background: radial-gradient(circle at var(--x, 50%) var(--y, 50%), rgba(255,255,255,.22), transparent 35%);
            opacity: 0;
            transition: opacity .22s ease;
            pointer-events: none;
        }
        button:hover::after, .mode-card:hover::after, .theme-option:hover::after {
            opacity: 1;
        }
        .broker-grid {
            display:grid;
            grid-template-columns: 1.05fr .95fr;
            gap:14px;
        }
        .broker-mode-grid {
            display:grid;
            grid-template-columns: repeat(2, minmax(150px, 1fr));
            gap:12px;
            margin-bottom:14px;
        }
        .mode-card {
            cursor:pointer;
            border:1px solid rgba(255,255,255,.10);
            background:linear-gradient(180deg, rgba(255,255,255,.06), rgba(255,255,255,.025));
            color:var(--text);
            border-radius:20px;
            padding:16px;
            min-height:118px;
            text-align:left;
            box-shadow: inset 0 1px 0 rgba(255,255,255,.03);
        }
        .mode-card.active {
            border-color:var(--accent);
            box-shadow:0 0 0 4px var(--glow), 0 18px 44px rgba(0,0,0,.28);
            background:linear-gradient(135deg, rgba(255,255,255,.12), rgba(255,255,255,.035));
        }
        .mode-card.live-mode.active {
            border-color:rgba(239,68,68,.65);
            box-shadow:0 0 0 4px rgba(239,68,68,.18), 0 18px 44px rgba(0,0,0,.30);
        }
        .mode-icon {
            width:44px;
            height:44px;
            border-radius:15px;
            display:flex;
            align-items:center;
            justify-content:center;
            font-size:23px;
            margin-bottom:10px;
            background:linear-gradient(135deg,var(--accent),var(--accent2));
            box-shadow:0 12px 28px var(--glow);
        }
        .mode-title { display:block; font-weight:950; font-size:17px; margin-bottom:4px; }
        .mode-sub { color:var(--muted); font-size:12px; line-height:1.35; }
        .broker-form {
            display:grid;
            grid-template-columns:1fr;
            gap:10px;
        }
        .broker-form input {
            width:100%;
            min-width:0;
            border-radius:16px;
            padding:14px 15px;
        }
        .success-glow {
            border-color:rgba(16,185,129,.45) !important;
            box-shadow:0 0 0 4px rgba(16,185,129,.14), 0 18px 44px rgba(0,0,0,.25) !important;
        }
        .danger-glow {
            border-color:rgba(239,68,68,.45) !important;
            box-shadow:0 0 0 4px rgba(239,68,68,.14), 0 18px 44px rgba(0,0,0,.25) !important;
        }
        .connection-meter {
            height:10px;
            border-radius:999px;
            background:rgba(255,255,255,.08);
            overflow:hidden;
            margin-top:12px;
        }
        .connection-meter > span {
            display:block;
            height:100%;
            width:0%;
            background:linear-gradient(90deg,var(--accent),var(--accent2),var(--accent3));
            border-radius:999px;
            transition:width .45s ease;
        }
        .signal-card { position:relative; overflow:hidden; }
        .signal-card::before {
            content:"";
            position:absolute;
            inset:0 auto 0 0;
            width:4px;
            background:linear-gradient(180deg,var(--accent),var(--accent2));
            opacity:.9;
        }
        .click-hint { color:var(--muted); font-size:12px; margin-top:10px; }

        @media (max-width: 920px) {
            .split { grid-template-columns:1fr; }
            .wrap { padding: 16px; }
            .hero { padding: 20px; }
            .tier-glance { grid-template-columns: 1fr; }
            .warning-top { flex-direction:column; align-items:flex-start; }
            .warning-mini { white-space:normal; }
            .broker-grid { grid-template-columns:1fr; }
            .broker-mode-grid { grid-template-columns:1fr; }
        }
    </style>
</head>
<body>
<div class="wrap">
    <section class="warning-top">
        <div>
            <b>Important:</b> Paper mode is simulation only. Signals are not guaranteed profit. Live trading stays locked unless you manually enable it. Free trials require payment method + license key.
        </div>
        <div class="warning-mini">Never share API keys or license keys.</div>
    </section>

    <section class="hero" id="heroCard">
        <div class="topbar">
            <div>
                <div class="hero-meta">
                    <div class="badge">â AI Stock Agent Running</div>
                    <div class="badge theme-badge" id="themeBadge">Starter Theme Active</div>
                </div>
                <h1>AI Stock Agent Dashboard</h1>
                <p id="heroCopy">Signals, crypto, paper trading, reports, portfolio charts, and tier-based themes.</p>
                <div class="tier-glance">
                    <div class="mini-stat"><span class="k">Active Tier</span><span class="v" id="miniTier">Starter</span></div>
                    <div class="mini-stat"><span class="k">Theme</span><span class="v" id="miniAccent">Neon Blue</span></div>
                    <div class="mini-stat"><span class="k">Access</span><span class="v" id="miniMode">Locked</span></div>
                </div>
            </div>
            <div class="card theme-card" style="min-width:340px; max-width:460px; width:100%;">
                <div class="tier-emblem" id="tierEmblem">â¦</div>
                <h3 id="tierCardTitle">License Access</h3>
                <p class="muted">Enter the license key received after checkout to unlock trial or paid access.</p>
                <div class="actions">
                    <input id="licenseInput" placeholder="Enter license key">
                    <button onclick="saveKey()" class="green">Unlock</button>
                    <button onclick="clearKey()" class="dark">Clear</button>
                </div>
                <div class="theme-line"></div>
                <p id="licenseStatus" class="muted"></p>
            </div>
        </div>

        <div class="tabs">
            <button id="btn-starter" class="tier-btn" onclick="loadTier('starter')">Starter</button>
            <button id="btn-pro" class="tier-btn" onclick="loadTier('pro')">Pro</button>
            <button id="btn-elite" class="tier-btn" onclick="loadTier('elite')">Elite</button>
            <button id="btn-ultra" class="tier-btn" onclick="loadTier('ultra')">Ultra</button>
            <button id="btn-mastery_plus" class="tier-btn gold" onclick="loadTier('mastery_plus')">Mastery Plus</button>
            <button onclick="loadTiers()" class="dark">Plans</button>
            <button onclick="loadReport()" class="dark">Report</button>
            <button onclick="loadStatus()" class="dark">Status</button>
        </div>

        <div class="theme-picker-wrap">
            <div class="section-head">
                <div>
                    <h3>Choose Theme</h3>
                    <p class="muted">Available themes depend on the tier you unlock.</p>
                </div>
                <div class="theme-strip" id="themeAccessChips"></div>
            </div>
            <div class="theme-picker" id="themePicker"></div>
        </div>
    </section>

    <section class="panel broker-connect" id="brokerPanel">
        <div class="topbar">
            <div>
                <h2>Broker Connection</h2>
                <p class="muted">Pick Paper or Live first. The secret is verified server-side and never displayed back.</p>
            </div>
            <div class="badge" id="brokerBadge">Broker: Not connected</div>
        </div>

        <div class="broker-grid">
            <div class="card" id="brokerConnectCard">
                <h3>Choose Account Type</h3>

                <div class="broker-mode-grid">
                    <button type="button" id="modePaper" class="mode-card active" onclick="selectBrokerMode('paper')">
                        <span class="mode-icon">ð§ª</span>
                        <span class="mode-title">Paper Account</span>
                        <span class="mode-sub">Safe testing. No real money. Best for trials and demos.</span>
                    </button>

                    <button type="button" id="modeLive" class="mode-card live-mode" onclick="selectBrokerMode('live')">
                        <span class="mode-icon">â¡</span>
                        <span class="mode-title">Live Account</span>
                        <span class="mode-sub">Real brokerage connection. Orders stay blocked unless live trading is enabled.</span>
                    </button>
                </div>

                <input id="brokerMode" type="hidden" value="paper">

                <div class="broker-form">
                    <input id="brokerKey" placeholder="Alpaca API Key">
                    <input id="brokerSecret" type="password" placeholder="Alpaca Secret Key">
                    <button onclick="connectBroker()" class="green">Connect Broker</button>
                    <button onclick="disconnectBroker()" class="dark">Disconnect</button>
                </div>

                <div class="connection-meter"><span id="connectionMeter"></span></div>
                <p class="click-hint">Paper first. Live can connect, but real live orders stay blocked while LIVE_TRADING_ENABLED=false.</p>
            </div>

            <div class="card" id="brokerStatusCard">
                <h3>Connection Status</h3>
                <div class="rows" id="brokerStatusRows">
                    <div class="row"><span>Status</span><b>Not connected</b></div>
                </div>
            </div>
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
            <div class="section-head">
                <h2>Stock Signals</h2>
                <div class="theme-strip">
                    <span class="theme-chip">Theme-aware cards</span>
                    <span class="theme-chip">Premium tier styling</span>
                </div>
            </div>
            <div class="grid" id="stocks"></div>
        </div>
        <div class="panel">
            <div class="section-head">
                <h2>Crypto Signals</h2>
                <div class="theme-strip">
                    <span class="theme-chip">Crypto heat</span>
                    <span class="theme-chip">Matching accents</span>
                </div>
            </div>
            <div class="grid" id="crypto"></div>
        </div>
    </section>

    <section class="panel">
        <div class="section-head">
            <div>
                <h2>Top Tier Bot Positions / Charts</h2>
                <p class="muted">Ultra and Mastery Plus show bot positions or buy-signal previews.</p>
            </div>
            <div class="theme-strip">
                <span class="theme-chip">Chart panels</span>
                <span class="theme-chip">Upgrade ambiance</span>
            </div>
        </div>
        <div class="grid" id="portfolio"></div>
    </section>

    <section class="panel">
        <div class="section-head">
            <h2>Details</h2>
            <div class="theme-strip" id="detailChips"></div>
        </div>
        <div id="details"></div>
    </section>
</div>

<script>
let currentTier = localStorage.getItem("tier") || "starter";
let licenseKey = localStorage.getItem("licenseKey") || "";
let selectedTheme = localStorage.getItem("selectedTheme") || "";
let brokerToken = localStorage.getItem("brokerToken") || "";
let charts = {};

const TIER_RANK = ["starter", "pro", "elite", "ultra", "mastery_plus"];

const TIER_THEMES = {
    starter: {
        label: "Starter Theme",
        accentName: "Neon Blue",
        emblem: "â¡",
        access: "Starter / Trial",
        heroCopy: "Start clean with a sharp blue launchpad theme built for previews and first-time users.",
        chips: ["Starter vibe", "Blue launch", "Preview access"],
        css: {
            "--bg": "#06101f",
            "--bg2": "#0a1222",
            "--accent": "#3b82f6",
            "--accent2": "#06b6d4",
            "--accent3": "#60a5fa",
            "--glow": "rgba(59,130,246,.28)",
            "--heroA": "rgba(59,130,246,.24)",
            "--heroB": "rgba(6,182,212,.18)",
            "--heroC": "rgba(96,165,250,.12)"
        }
    },
    pro: {
        label: "Pro Theme",
        accentName: "Purple Velocity",
        emblem: "â",
        access: "Pro Access",
        heroCopy: "Pro unlocks a slick purple velocity style for a smarter, sharper trading experience.",
        chips: ["Pro style", "Purple velocity", "Faster feel"],
        css: {
            "--bg": "#0c0818",
            "--bg2": "#140d24",
            "--accent": "#8b5cf6",
            "--accent2": "#6366f1",
            "--accent3": "#c084fc",
            "--glow": "rgba(139,92,246,.28)",
            "--heroA": "rgba(139,92,246,.26)",
            "--heroB": "rgba(99,102,241,.18)",
            "--heroC": "rgba(192,132,252,.12)"
        }
    },
    elite: {
        label: "Elite Theme",
        accentName: "Emerald Prestige",
        emblem: "â¬¢",
        access: "Elite Access",
        heroCopy: "Elite gets an emerald prestige skin that feels more exclusive and polished.",
        chips: ["Elite prestige", "Emerald glow", "Premium engine"],
        css: {
            "--bg": "#07150f",
            "--bg2": "#0a1a14",
            "--accent": "#10b981",
            "--accent2": "#14b8a6",
            "--accent3": "#6ee7b7",
            "--glow": "rgba(16,185,129,.28)",
            "--heroA": "rgba(16,185,129,.24)",
            "--heroB": "rgba(20,184,166,.18)",
            "--heroC": "rgba(110,231,183,.12)"
        }
    },
    ultra: {
        label: "Ultra Theme",
        accentName: "Crimson Heat",
        emblem: "â¬£",
        access: "Ultra Access",
        heroCopy: "Ultra turns the dashboard into a more aggressive crimson heat theme for power users.",
        chips: ["Ultra fire", "Automation ready", "Chart heavy"],
        css: {
            "--bg": "#180809",
            "--bg2": "#1d0b11",
            "--accent": "#ef4444",
            "--accent2": "#f97316",
            "--accent3": "#fb7185",
            "--glow": "rgba(239,68,68,.28)",
            "--heroA": "rgba(239,68,68,.24)",
            "--heroB": "rgba(249,115,22,.18)",
            "--heroC": "rgba(251,113,133,.12)"
        }
    },
    mastery_plus: {
        label: "Mastery Plus Theme",
        accentName: "Black Gold Luxury",
        emblem: "ð",
        access: "Mastery Plus",
        heroCopy: "Mastery Plus unlocks a black-and-gold luxury theme so the highest upgrade feels truly premium.",
        chips: ["Luxury mode", "Global scanner", "Top tier aura"],
        css: {
            "--bg": "#0d0a05",
            "--bg2": "#141006",
            "--accent": "#f59e0b",
            "--accent2": "#facc15",
            "--accent3": "#fbbf24",
            "--glow": "rgba(245,158,11,.30)",
            "--heroA": "rgba(245,158,11,.24)",
            "--heroB": "rgba(250,204,21,.16)",
            "--heroC": "rgba(251,191,36,.10)"
        }
    }
};

function rankOf(tier) {
    const i = TIER_RANK.indexOf(tier);
    return i < 0 ? 0 : i;
}

function themeAllowed(themeTier) {
    return rankOf(themeTier) <= rankOf(currentTier);
}

function effectiveTheme(tier) {
    if (selectedTheme && themeAllowed(selectedTheme)) return selectedTheme;
    return tier;
}

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

function applyTheme(tier) {
    const activeThemeKey = effectiveTheme(tier);
    const theme = TIER_THEMES[activeThemeKey] || TIER_THEMES.starter;
    const root = document.documentElement;
    Object.entries(theme.css).forEach(([k, v]) => root.style.setProperty(k, v));

    document.getElementById("themeBadge").innerText = theme.label + " Active";
    document.getElementById("miniTier").innerText = (TIER_THEMES[tier] || TIER_THEMES.starter).label.replace(" Theme", "");
    document.getElementById("miniAccent").innerText = theme.accentName;
    document.getElementById("miniMode").innerText = licenseKey ? "Unlocked" : "Locked";
    document.getElementById("tierEmblem").innerText = theme.emblem;
    document.getElementById("tierCardTitle").innerText = theme.access;
    document.getElementById("heroCopy").innerText = theme.heroCopy;
    document.getElementById("detailChips").innerHTML = theme.chips.map(chip => `<span class="theme-chip">${chip}</span>`).join("");

    document.querySelectorAll('.tier-btn').forEach(btn => btn.classList.remove('active'));
    const activeBtn = document.getElementById('btn-' + tier);
    if (activeBtn) activeBtn.classList.add('active');

    renderThemePicker();
}

function chooseTheme(themeTier) {
    if (!themeAllowed(themeTier)) return;
    selectedTheme = themeTier;
    localStorage.setItem("selectedTheme", selectedTheme);
    applyTheme(currentTier);
}

function renderThemePicker() {
    const box = document.getElementById("themePicker");
    const chips = document.getElementById("themeAccessChips");
    if (!box) return;

    box.innerHTML = TIER_RANK.map(tierKey => {
        const theme = TIER_THEMES[tierKey];
        const allowed = themeAllowed(tierKey);
        const active = effectiveTheme(currentTier) === tierKey;
        return `
            <button class="theme-option ${allowed ? "" : "locked"} ${active ? "active" : ""}" onclick="chooseTheme('${tierKey}')" ${allowed ? "" : "disabled"}>
                <span class="theme-dot">${theme.emblem}</span>
                <span class="theme-option-title">${theme.label.replace(" Theme", "")}</span>
                <span class="theme-option-sub">${allowed ? theme.accentName : "Unlock higher tier"}</span>
            </button>
        `;
    }).join("");

    if (chips) {
        const unlockedCount = TIER_RANK.filter(themeAllowed).length;
        chips.innerHTML = `
            <span class="theme-chip">${unlockedCount}/5 themes unlocked</span>
            <span class="theme-chip">Current tier: ${(TIER_THEMES[currentTier] || TIER_THEMES.starter).label.replace(" Theme", "")}</span>
        `;
    }
}

function accessText(valid, name) {
    return valid ? `Unlocked: ${name}` : "Locked â payment/license required.";
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
    document.getElementById("licenseStatus").innerText = "Locked â payment/license required.";
    applyTheme("starter");
    loadTier("starter");
}

async function checkLicense() {
    try {
        const res = await fetch("/license?key=" + encodeURIComponent(licenseKey));
        const data = await res.json();
        document.getElementById("licenseStatus").innerText = accessText(data.valid, data.name || data.tier || "tier");
        document.getElementById("miniMode").innerText = data.valid ? "Unlocked" : "Locked";
    } catch {
        document.getElementById("licenseStatus").innerText = "Locked â payment/license required.";
        document.getElementById("miniMode").innerText = "Locked";
    }
}

function lockedHTML(err) {
    return `
        <div class="notice">
            <h3>Tier locked</h3>
            <p>${err.message || "Enter a valid license key."}</p>
            <p><b>Next step:</b> Complete checkout, then enter your license key to unlock your trial or paid tier.</p>
        </div>
    `;
}

async function loadTier(tier) {
    currentTier = tier;
    localStorage.setItem("tier", tier);
    applyTheme(tier);

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
        document.getElementById("subtitle").innerText = "Complete checkout, then enter your license key to unlock this theme.";
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
        <div class="card signal-card">
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
        const theme = TIER_THEMES[k] || TIER_THEMES.starter;
        return `
            <div class="card theme-card">
                <div class="tier-emblem">${theme.emblem}</div>
                <h3>${t.name}</h3>
                <p><b>Price:</b> ${t.price}</p>
                <p><b>Trial:</b> ${t.trial}</p>
                <p><b>Stocks:</b> ${t.symbols.length}</p>
                <p><b>Crypto:</b> ${t.crypto_symbols.length}</p>
                <p><b>Theme:</b> ${theme.accentName}</p>
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



function selectBrokerMode(mode) {
    const paper = document.getElementById("modePaper");
    const live = document.getElementById("modeLive");
    const hidden = document.getElementById("brokerMode");

    if (!hidden || !paper || !live) return;

    hidden.value = mode;

    paper.classList.toggle("active", mode === "paper");
    live.classList.toggle("active", mode === "live");

    const card = document.getElementById("brokerConnectCard");
    if (card) {
        card.classList.remove("success-glow", "danger-glow");
        void card.offsetWidth;
        card.classList.add(mode === "live" ? "danger-glow" : "success-glow");
        setTimeout(() => card.classList.remove("success-glow", "danger-glow"), 520);
    }
}

function setConnectionMeter(percent) {
    const meter = document.getElementById("connectionMeter");
    if (meter) meter.style.width = String(percent || 0) + "%";
}

function brokerRows(data) {
    const statusCard = document.getElementById("brokerStatusCard");

    if (!data.connected) {
        document.getElementById("brokerBadge").innerText = "Broker: Not connected";
        setConnectionMeter(0);

        if (statusCard) {
            statusCard.classList.remove("success-glow");
            statusCard.classList.add("danger-glow");
            setTimeout(() => statusCard.classList.remove("danger-glow"), 700);
        }

        document.getElementById("brokerStatusRows").innerHTML = `
            <div class="row"><span>Status</span><b>Not connected</b></div>
            <div class="row"><span>Message</span><b>${data.message || "Connect your account"}</b></div>
        `;
        return;
    }

    const liveWarning = data.mode === "live" && !data.live_trading_enabled
        ? "Live connected, live orders blocked"
        : "Connected";

    document.getElementById("brokerBadge").innerText = `Broker: ${String(data.mode || "").toUpperCase()} connected`;
    setConnectionMeter(100);

    if (statusCard) {
        statusCard.classList.remove("danger-glow");
        statusCard.classList.add("success-glow");
        setTimeout(() => statusCard.classList.remove("success-glow"), 900);
    }

    document.getElementById("brokerStatusRows").innerHTML = `
        <div class="row"><span>Status</span><b>${liveWarning}</b></div>
        <div class="row"><span>Mode</span><b>${data.mode}</b></div>
        <div class="row"><span>Key</span><b>${data.api_key_masked || "masked"}</b></div>
        <div class="row"><span>Account</span><b>${data.account_status || "unknown"}</b></div>
        <div class="row"><span>Trading Blocked</span><b>${data.trading_blocked}</b></div>
        <div class="row"><span>Currency</span><b>${data.currency || "USD"}</b></div>
        <div class="row"><span>Buying Power</span><b>${data.buying_power || "hidden"}</b></div>
        <div class="row"><span>Live Orders Enabled</span><b>${data.live_trading_enabled}</b></div>
    `;
}

async function loadBrokerStatus() {
    if (!brokerToken) {
        brokerRows({ connected: false, message: "No broker connected." });
        return;
    }

    try {
        const res = await fetch("/broker/status?token=" + encodeURIComponent(brokerToken));
        const data = await res.json();

        if (!data.connected) {
            localStorage.removeItem("brokerToken");
            brokerToken = "";
        }

        brokerRows(data);
    } catch {
        brokerRows({ connected: false, message: "Could not check broker status." });
    }
}

async function connectBroker() {
    const apiKey = document.getElementById("brokerKey").value.trim();
    const secretKey = document.getElementById("brokerSecret").value.trim();
    const mode = document.getElementById("brokerMode").value;

    setConnectionMeter(35);
    brokerRows({ connected: false, message: "Checking broker connection..." });
    setConnectionMeter(55);

    try {
        const res = await fetch("/broker/connect", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                api_key: apiKey,
                secret_key: secretKey,
                mode: mode
            })
        });

        const data = await res.json();

        if (!res.ok || !data.connected) {
            setConnectionMeter(0);
            brokerRows({ connected: false, message: data.message || "Connection failed." });
            return;
        }

        setConnectionMeter(85);
        brokerToken = data.token;
        localStorage.setItem("brokerToken", brokerToken);

        document.getElementById("brokerSecret").value = "";
        brokerRows(data);
    } catch {
        brokerRows({ connected: false, message: "Connection request failed." });
    }
}

async function disconnectBroker() {
    if (brokerToken) {
        try {
            await fetch("/broker/disconnect", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ token: brokerToken })
            });
        } catch {}
    }

    brokerToken = "";
    localStorage.removeItem("brokerToken");
    document.getElementById("brokerKey").value = "";
    document.getElementById("brokerSecret").value = "";
    brokerRows({ connected: false, message: "Broker disconnected." });
}


document.addEventListener("pointermove", (e) => {
    const target = e.target.closest("button, .mode-card, .theme-option");
    if (!target) return;
    const rect = target.getBoundingClientRect();
    target.style.setProperty("--x", (e.clientX - rect.left) + "px");
    target.style.setProperty("--y", (e.clientY - rect.top) + "px");
});

selectBrokerMode("paper");
applyTheme(currentTier);
checkLicense();
loadTier(currentTier);
loadBrokerStatus();
</script>
</body>
</html>
""")



@app.route("/broker/connect", methods=["POST"])
def broker_connect():
    payload = request.get_json(silent=True) or {}

    api_key = str(payload.get("api_key", "")).strip()
    secret_key = str(payload.get("secret_key", "")).strip()
    mode = str(payload.get("mode", "paper")).strip().lower()

    if mode not in ["paper", "live"]:
        mode = "paper"

    if not api_key or not secret_key:
        return jsonify({
            "connected": False,
            "message": "Enter both API key and secret key."
        }), 400

    result = test_alpaca_credentials(api_key, secret_key, mode)

    if not result.get("ok"):
        return jsonify({
            "connected": False,
            "mode": mode,
            "message": result.get("message", "Connection failed."),
            "status_code": result.get("status_code", 0)
        }), 400

    token = uuid.uuid4().hex

    BROKER_CONNECTIONS[token] = {
        "api_key": api_key,
        "secret_key": secret_key,
        "mode": mode,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "account_status": result.get("account_status"),
        "trading_blocked": result.get("trading_blocked"),
        "account_blocked": result.get("account_blocked"),
        "currency": result.get("currency"),
        "buying_power": result.get("buying_power"),
        "portfolio_value": result.get("portfolio_value")
    }

    return jsonify({
        "connected": True,
        "token": token,
        "mode": mode,
        "api_key_masked": mask_secret(api_key),
        "account_status": result.get("account_status"),
        "trading_blocked": result.get("trading_blocked"),
        "account_blocked": result.get("account_blocked"),
        "currency": result.get("currency"),
        "buying_power": result.get("buying_power"),
        "portfolio_value": result.get("portfolio_value"),
        "live_trading_enabled": LIVE_TRADING_ENABLED,
        "message": "Connected successfully. The secret key is not shown again."
    })


@app.route("/broker/status")
def broker_status():
    token = request.args.get("token", "")
    return jsonify(broker_status_from_token(token))


@app.route("/broker/disconnect", methods=["POST"])
def broker_disconnect():
    payload = request.get_json(silent=True) or {}
    token = payload.get("token", "")

    if token in BROKER_CONNECTIONS:
        BROKER_CONNECTIONS.pop(token, None)

    return jsonify({
        "connected": False,
        "message": "Broker disconnected."
    })


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
            "/signals?tier=pro&key=PRO-PAID",
            "/signals?tier=mastery_plus&key=MASTER-PAID",
            "/trade?tier=ultra&mode=paper&key=ULTRA-PAID",
            "/portfolio?tier=ultra&key=ULTRA-PAID",
            "/report?tier=mastery_plus&key=MASTER-PAID",
            "/chart-data?symbol=AAPL",
            "/license?key=PRO-PAID",
            "/broker/connect",
            "/broker/status",
            "/broker/disconnect",
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
        "internal_orders": len(ORDERS),
        "broker_sessions": len(BROKER_CONNECTIONS)
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
        return jsonify({"valid": False, "tier": None, "name": "Payment required", "message": "Complete checkout first, then enter your license key."})

    return jsonify({
        "valid": True,
        "tier": tier,
        "name": TIER_CONFIGS[tier]["name"],
        "price": TIER_CONFIGS[tier]["price"],
        "features": TIER_CONFIGS[tier]["features"]
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
