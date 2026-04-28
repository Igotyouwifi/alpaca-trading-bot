```python
import os
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from flask import Flask, jsonify, render_template_string
from alpaca_trade_api import REST

# ============================================
# CONFIG
# ============================================

API_KEY = os.environ.get("APCA_API_KEY_ID", "your-api-key")
API_SECRET = os.environ.get("APCA_API_SECRET_KEY", "your-secret-key")
BASE_URL = "https://paper-api.alpaca.markets"

WATCHLIST = [
    "AAPL", "TSLA", "NVDA", "MSFT", "AMZN",
    "GOOGL", "META", "AMD", "SPY", "QQQ"
]

app = Flask(__name__)
api = REST(API_KEY, API_SECRET, BASE_URL, api_version='v2')

# ============================================
# SIGNAL LOG (in-memory, persists until redeploy)
# ============================================

signal_history = []

def log_signal(symbol, signal, confidence, rsi, ma_trend, volume_spike, price):
    global signal_history
    signal_history.append({
        "timestamp": datetime.now().isoformat(),
        "symbol": symbol,
        "signal": signal,
        "confidence": confidence,
        "rsi": rsi,
        "ma_trend": ma_trend,
        "volume_spike": volume_spike,
        "price": price
    })
    # keep last 1000 entries
    signal_history = signal_history[-1000:]

# ============================================
# TECHNICAL ANALYSIS ENGINE
# ============================================

def calculate_rsi(closes, period=14):
    delta = closes.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    if loss.iloc[-1] == 0:
        return 50.0  # neutral if no losses
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return round(rsi.iloc[-1], 2)

def calculate_macd(closes):
    ema12 = closes.ewm(span=12, adjust=False).mean()
    ema26 = closes.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    histogram = macd_line - signal_line
    
    return {
        "macd": round(macd_line.iloc[-1], 4),
        "signal_line": round(signal_line.iloc[-1], 4),
        "histogram": round(histogram.iloc[-1], 4),
        "bullish": macd_line.iloc[-1] > signal_line.iloc[-1]
    }

def calculate_volatility(closes, period=20):
    returns = closes.pct_change().dropna()
    if len(returns) < period:
        return 0.0
    volatility = returns.rolling(window=period).std().iloc[-1]
    return round(volatility * 100, 4)

def generate_signal(symbol):
    try:
        # pull 60 days of daily bars
        bars = api.get_bars(
            symbol,
            '1Day',
            start=(datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d'),
            end=datetime.now().strftime('%Y-%m-%d'),
            limit=60
        )
        
        if not bars or len(bars) < 26:
            return {
                "symbol": symbol,
                "signal": "NO DATA",
                "confidence": 0,
                "rsi": 0,
                "ma_trend": "unknown",
                "macd": {},
                "volume_spike": False,
                "volatility": 0,
                "price": 0,
                "risk_blocked": False,
                "error": None
            }
        
        df = pd.DataFrame({
            'close': [bar.c for bar in bars],
            'high': [bar.h for bar in bars],
            'low': [bar.l for bar in bars],
            'volume': [bar.v for bar in bars]
        })
        
        current_price = df['close'].iloc[-1]
        
        # ---- INDICATOR 1: MOVING AVERAGES ----
        df['ma5'] = df['close'].rolling(window=5).mean()
        df['ma20'] = df['close'].rolling(window=20).mean()
        
        ma_short = df['ma5'].iloc[-1]
        ma_long = df['ma20'].iloc[-1]
        
        ma_score = 0
        if ma_short > ma_long:
            ma_score = 1
            ma_trend = "bullish"
        elif ma_short < ma_long:
            ma_score = -1
            ma_trend = "bearish"
        else:
            ma_trend = "neutral"
        
        # how far apart are the MAs (strength of trend)
        ma_spread = abs(ma_short - ma_long) / ma_long * 100
        if ma_spread > 2:
            ma_score *= 1.3  # strong trend bonus
        
        # ---- INDICATOR 2: RSI ----
        rsi_value = calculate_rsi(df['close'])
        
        rsi_score = 0
        if rsi_value < 25:
            rsi_score = 1.5   # very oversold
        elif rsi_value < 30:
            rsi_score = 1     # oversold
        elif rsi_value < 40:
            rsi_score = 0.5   # slightly oversold
        elif rsi_value > 75:
            rsi_score = -1.5  # very overbought
        elif rsi_value > 70:
            rsi_score = -1    # overbought
        elif rsi_value > 60:
            rsi_score = -0.5  # slightly overbought
        
        # ---- INDICATOR 3: MACD ----
        macd_data = calculate_macd(df['close'])
        
        macd_score = 0
        if macd_data['bullish'] and macd_data['histogram'] > 0:
            macd_score = 1
        elif not macd_data['bullish'] and macd_data['histogram'] < 0:
            macd_score = -1
        
        # ---- INDICATOR 4: VOLUME ----
        df['vol_avg'] = df['volume'].rolling(window=20).mean()
        current_vol = df['volume'].iloc[-1]
        avg_vol = df['vol_avg'].iloc[-1]
        
        volume_spike = False
        volume_multiplier = 1.0
        if avg_vol > 0:
            vol_ratio = current_vol / avg_vol
            if vol_ratio > 1.5:
                volume_spike = True
                volume_multiplier = 1.3  # volume confirms the move
        
        # ---- RISK FILTER: VOLATILITY ----
        volatility = calculate_volatility(df['close'])
        
        risk_blocked = False
        if volatility > 5.0:
            risk_blocked = True  # too volatile, block the trade
        
        # ---- COMBINE ALL SCORES ----
        raw_score = (ma_score + rsi_score + macd_score) * volume_multiplier
        
        # normalize to 0-100 confidence
        # raw_score range is roughly -5 to +5
        confidence = min(max((raw_score + 4) * 12.5, 0), 100)
        confidence = round(confidence, 1)
        
        # ---- DETERMINE SIGNAL ----
        if risk_blocked:
            signal = "HOLD"
            confidence = min(confidence, 30)  # cap confidence when risk blocked
        elif raw_score >= 2.5:
            signal = "STRONG BUY"
        elif raw_score >= 1.0:
            signal = "BUY"
        elif raw_score <= -2.5:
            signal = "STRONG SELL"
        elif raw_score <= -1.0:
            signal = "SELL"
        else:
            signal = "HOLD"
        
        # ---- LOG THE SIGNAL ----
        log_signal(symbol, signal, confidence, rsi_value, ma_trend, volume_spike, current_price)
        
        return {
            "symbol": symbol,
            "signal": signal,
            "confidence": confidence,
            "rsi": rsi_value,
            "ma_trend": ma_trend,
            "macd": macd_data,
            "volume_spike": volume_spike,
            "volatility": volatility,
            "price": round(current_price, 2),
            "risk_blocked": risk_blocked,
            "error": None
        }
        
    except Exception as e:
        return {
            "symbol": symbol,
            "signal": "ERROR",
            "confidence": 0,
            "rsi": 0,
            "ma_trend": "unknown",
            "macd": {},
            "volume_spike": False,
            "volatility": 0,
            "price": 0,
            "risk_blocked": False,
            "error": str(e)
        }

def get_all_signals():
    signals = []
    for symbol in WATCHLIST:
        result = generate_signal(symbol)
        signals.append(result)
    return signals

# ============================================
# PAPER TRADE EXECUTION
# ============================================

def execute_paper_trade(symbol, signal):
    try:
        if signal in ["BUY", "STRONG BUY"]:
            order = api.submit_order(
                symbol=symbol,
                qty=1,
                side='buy',
                type='market',
                time_in_force='day'
            )
            return {"executed": True, "side": "buy", "order_id": order.id}
        
        elif signal in ["SELL", "STRONG SELL"]:
            # check if we have a position to sell
            try:
                position = api.get_position(symbol)
                if int(position.qty) > 0:
                    order = api.submit_order(
                        symbol=symbol,
                        qty=1,
                        side='sell',
                        type='market',
                        time_in_force='day'
                    )
                    return {"executed": True, "side": "sell", "order_id": order.id}
                else:
                    return {"executed": False, "reason": "no position to sell"}
            except:
                return {"executed": False, "reason": "no position found"}
        
        else:
            return {"executed": False, "reason": "signal is HOLD or blocked"}
    
    except Exception as e:
        return {"executed": False, "reason": str(e)}

# ============================================
# DASHBOARD HTML
# ============================================

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Trading Bot</title>
    <meta http-equiv="refresh" content="60">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            background: #0a0a0f;
            color: #e0e0e0;
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            padding: 20px;
            min-height: 100vh;
        }
        
        .header {
            text-align: center;
            padding: 30px 0;
            border-bottom: 1px solid #1a1a2e;
            margin-bottom: 30px;
        }
        
        .header h1 {
            font-size: 28px;
            color: #00ff88;
            margin-bottom: 8px;
            letter-spacing: 2px;
        }
        
        .header .subtitle {
            color: #555;
            font-size: 13px;
        }
        
        .header .live-dot {
            display: inline-block;
            width: 8px;
            height: 8px;
            background: #00ff88;
            border-radius: 50%;
            margin-right: 6px;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }
        
        .stats-bar {
            display: flex;
            justify-content: center;
            gap: 40px;
            margin-bottom: 30px;
            flex-wrap: wrap;
        }
        
        .stat {
            text-align: center;
        }
        
        .stat-value {
            font-size: 24px;
            font-weight: bold;
            color: #fff;
        }
        
        .stat-label {
            font-size: 11px;
            color: #555;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 16px;
            max-width: 1200px;
            margin: 0 auto;
        }
        
        .card {
            background: #111118;
            border: 1px solid #1a1a2e;
            border-radius: 12px;
            padding: 20px;
            transition: border-color 0.3s;
        }
        
        .card:hover {
            border-color: #333;
        }
        
        .card-top {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
        }
        
        .symbol {
            font-size: 22px;
            font-weight: 700;
            color: #fff;
        }
        
        .price {
            font-size: 16px;
            color: #888;
        }
        
        .signal-badge {
            display: inline-block;
            padding: 6px 14px;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 700;
            letter-spacing: 1px;
            margin-bottom: 14px;
        }
        
        .signal-badge.strong-buy {
            background: #00ff8822;
            color: #00ff88;
            border: 1px solid #00ff8844;
        }
        .signal-badge.buy {
            background: #00cc6622;
            color: #00cc66;
            border: 1px solid #00cc6644;
        }
        .signal-badge.hold {
            background: #ffaa0022;
            color: #ffaa00;
            border: 1px solid #ffaa0044;
        }
        .signal-badge.sell {
            background: #ff444422;
            color: #ff4444;
            border: 1px solid #ff444444;
        }
        .signal-badge.strong-sell {
            background: #ff000022;
            color: #ff0000;
            border: 1px solid #ff000044;
        }
        .signal-badge.error, .signal-badge.no-data {
            background: #33333322;
            color: #666;
            border: 1px solid #33333344;
        }
        
        .details-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            font-size: 12px;
            color: #777;
            margin-bottom: 14px;
        }
        
        .detail-item {
            display: flex;
            justify-content: space-between;
        }
        
        .detail-label { color: #555; }
        .detail-value { color: #aaa; font-weight: 600; }
        
        .confidence-bar-container {
            width: 100%;
            height: 6px;
            background: #1a1a2e;
            border-radius: 3px;
            overflow: hidden;
        }
        
        .confidence-bar-fill {
            height: 100%;
            border-radius: 3px;
            transition: width 1s ease;
        }
        
        .confidence-label {
            display: flex;
            justify-content: space-between;
            font-size: 11px;
            color: #555;
            margin-top: 4px;
        }
        
        .risk-warning {
            margin-top: 10px;
            padding: 6px 10px;
            background: #ff444411;
            border: 1px solid #ff444433;
            border-radius: 4px;
            font-size: 11px;
            color: #ff6666;
        }
        
        .footer {
            text-align: center;
            margin-top: 40px;
            padding: 20px;
            border-top: 1px solid #1a1a2e;
        }
        
        .footer p {
            color: #333;
            font-size: 11px;
            line-height: 1.8;
        }
        
        .endpoints {
            max-width: 600px;
            margin: 20px auto;
            background: #111118;
            border: 1px solid #1a1a2e;
            border-radius: 8px;
            padding: 16px;
        }
        
        .endpoints h3 {
            color: #555;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 10px;
        }
        
        .endpoint {
            display: flex;
            justify-content: space-between;
            padding: 4px 0;
            font-size: 13px;
        }
        
        .endpoint-path { color: #00ff88; font-family: monospace; }
        .endpoint-desc { color: #555; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🤖 AI TRADING SIGNALS</h1>
        <p class="subtitle">
            <span class="live-dot"></span>
            LIVE | Paper Trading Mode | Auto-refreshes every 60s | 
            Last update: {{ updated }}
        </p>
    </div>
    
    <div class="stats-bar">
        <div class="stat">
            <div class="stat-value" style="color: #00ff88;">{{ buy_count }}</div>
            <div class="stat-label">Buy Signals</div>
        </div>
        <div class="stat">
            <div class="stat-value" style="color: #ffaa00;">{{ hold_count }}</div>
            <div class="stat-label">Hold</div>
        </div>
        <div class="stat">
            <div class="stat-value" style="color: #ff4444;">{{ sell_count }}</div>
            <div class="stat-label">Sell Signals</div>
        </div>
        <div class="stat">
            <div class="stat-value">{{ signals|length }}</div>
            <div class="stat-label">Stocks Tracked</div>
        </div>
    </div>
    
    <div class="grid">
        {% for s in signals %}
        <div class="card">
            <div class="card-top">
                <span class="symbol">{{ s.symbol }}</span>
                <span class="price">${{ s.price }}</span>
            </div>
            
            {% set css_class = s.signal|lower|replace(' ', '-') %}
            <div class="signal-badge {{ css_class }}">
                {{ s.signal }}
            </div>
            
            <div class="details-grid">
                <div class="detail-item">
                    <span class="detail-label">RSI</span>
                    <span class="detail-value">{{ s.rsi }}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Trend</span>
                    <span class="detail-value">{{ s.ma_trend }}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">MACD</span>
                    <span class="detail-value">
                        {% if s.macd and s.macd.bullish is defined %}
                            {{ "Bullish" if s.macd.bullish else "Bearish" }}
                        {% else %}
                            N/A
                        {% endif %}
                    </span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Volume</span>
                    <span class="detail-value">
                        {{ "🔥 Spike" if s.volume_spike else "Normal" }}
                    </span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Volatility</span>
                    <span class="detail-value">{{ s.volatility }}%</span>
                </div>
            </div>
            
            <div class="confidence-label">
                <span>Confidence</span>
                <span>{{ s.confidence }}%</span>
            </div>
            <div class="confidence-bar-container">
                <div class="confidence-bar-fill" style="
                    width: {{ s.confidence }}%;
                    background: {% if s.confidence >= 70 %}#00ff88
                    {% elif s.confidence >= 40 %}#ffaa00
                    {% else %}#ff4444{% endif %};
                "></div>
            </div>
            
            {% if s.risk_blocked %}
            <div class="risk-warning">
                ⚠️ HIGH VOLATILITY — Trade blocked by risk filter
            </div>
            {% endif %}
            
            {% if s.error %}
            <div class="risk-warning">
                ❌ Error: {{ s.error }}
            </div>
            {% endif %}
        </div>
        {% endfor %}
    </div>
    
    <div class="endpoints">
        <h3>API Endpoints</h3>
        <div class="endpoint">
            <span class="endpoint-path">GET /</span>
            <span class="endpoint-desc">This dashboard</span>
        </div>
        <div class="endpoint">
            <span class="endpoint-path">GET /trade</span>
            <span class="endpoint-desc">JSON signals data</span>
        </div>
        <div class="endpoint">
            <span class="endpoint-path">GET /status</span>
            <span class="endpoint-desc">Bot health check</span>
        </div>
        <div class="endpoint">
            <span class="endpoint-path">GET /history</span>
            <span class="endpoint-desc">Signal history log</span>
        </div>
    </div>
    
    <div class="footer">
        <p>
            ⚠️ DISCLAIMER: This is a paper trading bot for educational and research purposes only.<br>
            This is NOT financial advice. Past signals do not guarantee future performance.<br>
            Never trade real money based solely on automated signals.<br>
            Built with Python + Flask + Alpaca API
        </p>
    </div>
</body>
</html>
"""

# ============================================
# FLASK ROUTES
# ============================================

@app.route('/')
def dashboard():
    signals = get_all_signals()
    
    buy_count = sum(1 for s in signals if s['signal'] in ['BUY', 'STRONG BUY'])
    sell_count = sum(1 for s in signals if s['signal'] in ['SELL', 'STRONG SELL'])
    hold_count = sum(1 for s in signals if s['signal'] == 'HOLD')
    
    return render_template_string(
        DASHBOARD_HTML,
        signals=signals,
        buy_count=buy_count,
        sell_count=sell_count,
        hold_count=hold_count,
        updated=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    )

@app.route('/trade')
def trade():
    signals = get_all_signals()
    
    results = []
    for s in signals:
        trade_result = execute_paper_trade(s['symbol'], s['signal'])
        s['trade'] = trade_result
        results.append(s)
    
    return jsonify({
        "timestamp": datetime.now().isoformat(),
        "signals": results,
        "summary": {
            "total": len(results),
            "buys": sum(1 for r in results if r['signal'] in ['BUY', 'STRONG BUY']),
            "sells": sum(1 for r in results if r['signal'] in ['SELL', 'STRONG SELL']),
            "holds": sum(1 for r in results if r['signal'] == 'HOLD')
        }
    })

@app.route('/signals')
def signals_only():
    """Returns signals without executing trades"""
    signals = get_all_signals()
    return jsonify({
        "timestamp": datetime.now().isoformat(),
        "signals": signals
    })

@app.route('/status')
def status():
    try:
        account = api.get_account()
        market_clock = api.get_clock()
        
        return jsonify({
            "bot": "online",
            "timestamp": datetime.now().isoformat(),
            "market": {
                "is_open": market_clock.is_open,
                "next_open": str(market_clock.next_open),
                "next_close": str(market_clock.next_close)
            },
            "account": {
                "portfolio_value": account.portfolio_value,
                "cash": account.cash,
                "buying_power": account.buying_power
            },
            "watchlist": WATCHLIST,
            "total_stocks_tracked": len(WATCHLIST),
            "signals_logged": len(signal_history),
            "version": "2.0"
        })
    except Exception as e:
        return jsonify({
            "bot": "online",
            "timestamp": datetime.now().isoformat(),
            "alpaca_connection": "error",
            "error": str(e),
            "version": "2.0"
        })

@app.route('/history')
def history():
    return jsonify({
        "total_signals_logged": len(signal_history),
        "showing_last_50": signal_history[-50:],
        "timestamp": datetime.now().isoformat()
    })

@app.route('/health')
def health():
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})

# ============================================
# RUN
# ============================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
```

---

## What This Gives You

### 6 Working Endpoints

| Endpoint | What It Does |
|---|---|
| `GET /` | Full visual dashboard with live signals |
| `GET /trade` | Generates signals AND executes paper trades |
| `GET /signals` | Signals only, no execution (safe to call anytime) |
| `GET /status` | Bot health, market status, account info |
| `GET /history` | Last 50 logged signals |
| `GET /health` | Simple uptime check for monitoring |

### Upgraded Signal Engine
- **Moving Average crossover** (trend)
- **RSI** with granular scoring (not just above/below 30/70)
- **MACD** with histogram analysis (momentum)
- **Volume spike detection** (confirmation)
- **Volatility filter** (risk management)
- **Confidence score 0–100** (combined weighted output)
- **6 signal levels**: STRONG BUY, BUY, HOLD, SELL, STRONG SELL, ERROR

### Professional Dashboard
- Dark theme
- Auto-refreshes every 60 seconds
- Shows all 10 stocks with price, signal, indicators, confidence bar
- Risk warnings when volatility blocks trades
- Summary stats at top
- API documentation built in
- Disclaimer at bottom

### Paper Trade Execution
- `/trade` endpoint auto-executes on Alpaca paper account
- Buys 1 share on BUY/STRONG BUY signals
- Only sells if you hold a position
- Returns execution results in JSON

### Signal Logging
- Every signal stored in memory
- Viewable at `/history`
- Tracks timestamp, symbol, signal, confidence, price, indicators

---

## Your `requirements.txt`

Make sure this is in your Render project:

```
flask
alpaca-trade-api
pandas
numpy
```

---

## Environment Variables on Render

In your Render dashboard, make sure you have:

```
APCA_API_KEY_ID = your-alpaca-api-key
APCA_API_SECRET_KEY = your-alpaca-secret-key
```

---


