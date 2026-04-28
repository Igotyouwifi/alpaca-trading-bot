```python
from flask import Flask, render_template_string, jsonify
from alpaca.trading.client import TradingClient
import pandas as pd
import os
from datetime import datetime
import json

app = Flask(__name__)

API_KEY = os.getenv("APCA_API_KEY_ID", "YOUR_KEY_HERE")
SECRET_KEY = os.getenv("APCA_API_SECRET_KEY", "YOUR_SECRET_HERE")
BASE_URL = "https://paper-api.alpaca.markets"

client = TradingClient(api_key=API_KEY, secret_key=SECRET_KEY, base_url=BASE_URL)

WATCHLIST = ["AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "GOOGL", "META", "AMD", "SPY", "QQQ"]
SIGNAL_LOG = "signals.json"

def get_bars(symbol, timeframe="1Hour", limit=100):
    try:
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame
        request_params = StockBarsRequest(symbol_or_symbols=symbol, timeframe=TimeFrame.Hour, limit=limit)
        bars = client.get_stock_bars(request_params)
        return bars[symbol] if symbol in bars else None
    except:
        return None

def calculate_rsi(data, period=14):
    if len(data) < period:
        return 50
    delta = data.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1] if not rsi.empty else 50

def generate_signal(symbol):
    try:
        bars = get_bars(symbol, limit=50)
        if bars is None or len(bars) < 20:
            return {"symbol": symbol, "signal": "HOLD", "confidence": 0, "reason": "Insufficient data"}
        
        closes = bars['close']
        ma_short = closes.rolling(window=5).mean()
        ma_long = closes.rolling(window=20).mean()
        
        ma_signal = 0
        if ma_short.iloc[-1] > ma_long.iloc[-1]:
            ma_signal = 1
        elif ma_short.iloc[-1] < ma_long.iloc[-1]:
            ma_signal = -1
        
        rsi = calculate_rsi(closes, period=14)
        rsi_signal = 0
        if rsi < 30:
            rsi_signal = 1
        elif rsi > 70:
            rsi_signal = -1
        
        volumes = bars['volume']
        vol_avg = volumes.rolling(window=20).mean()
        volume_spike = volumes.iloc[-1] > (vol_avg.iloc[-1] * 1.5)
        
        raw_score = ma_signal + rsi_signal
        if volume_spike:
            raw_score *= 1.5
        
        confidence = min(max((raw_score + 2) * 25, 0), 100)
        
        if raw_score >= 1.5:
            signal = "STRONG BUY"
        elif raw_score >= 0.5:
            signal = "BUY"
        elif raw_score <= -1.5:
            signal = "STRONG SELL"
        elif raw_score <= -0.5:
            signal = "SELL"
        else:
            signal = "HOLD"
        
        return {
            "symbol": symbol,
            "signal": signal,
            "confidence": round(confidence, 1),
            "rsi": round(rsi, 2),
            "ma_trend": "bullish" if ma_signal == 1 else "bearish" if ma_signal == -1 else "neutral",
            "volume_spike": bool(volume_spike),
            "price": round(closes.iloc[-1], 2)
        }
    except Exception as e:
        return {"symbol": symbol, "signal": "ERROR", "confidence": 0, "error": str(e)}

def log_signal(signal_data):
    try:
        with open(SIGNAL_LOG, "r") as f:
            logs = json.load(f)
    except:
        logs = []
    
    logs.append({"timestamp": datetime.now().isoformat(), **signal_data})
    logs = logs[-500:]
    
    with open(SIGNAL_LOG, "w") as f:
        json.dump(logs, f)

def get_all_signals():
    signals = []
    for symbol in WATCHLIST:
        signal = generate_signal(symbol)
        if signal["signal"] != "ERROR":
            signals.append(signal)
            log_signal(signal)
    return sorted(signals, key=lambda x: x.get("confidence", 0), reverse=True)

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>🤖 AI Trading Signals</title>
    <meta http-equiv="refresh" content="300">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 100%); color: #ffffff; font-family: 'Courier New', monospace; padding: 20px; min-height: 100vh; }
        h1 { text-align: center; margin-bottom: 10px; color: #00ff88; font-size: 32px; text-shadow: 0 0 10px #00ff8844; }
        .subtitle { text-align: center; color: #888; margin-bottom: 30px; font-size: 12px; }
        .last-updated { text-align: center; color: #666; font-size: 11px; margin-bottom: 20px; }
        .signals-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 15px; max-width: 1200px; margin: 0 auto; }
        .card { background: rgba(15, 15, 25, 0.9); border: 1px solid #222; border-radius: 12px; padding: 20px; backdrop-filter: blur(10px); transition: transform 0.2s, border-color 0.2s; }
        .card:hover { border-color: #444; transform: translateY(-2px); }
        .symbol { font-size: 26px; font-weight: bold; margin-bottom: 12px; color: #00ff88; }
        .signal { font-size: 14px; font-weight: bold; padding: 10px 14px; border-radius: 6px; display: inline-block; margin-bottom: 12px; }
        .signal.strong-buy { background: #00ff8830; color: #00ff88; border: 1px solid #00ff88; }
        .signal.buy { background: #00cc6630; color: #00cc66; border: 1px solid #00cc66; }
        .signal.sell { background: #ff444430; color: #ff4444; border: 1px solid #ff4444; }
        .signal.strong-sell { background: #cc000030; color: #ff2222; border: 1px solid #ff2222; }
        .signal.hold { background: #ffaa0030; color: #ffaa00; border: 1px solid #ffaa00; }
        .details { color: #aaa; font-size: 13px; line-height: 1.8; margin-bottom: 12px; }
        .details span { color: #fff; font-weight: bold; }
        .confidence-bar { width: 100%; height: 6px; background: #222; border-radius: 3px; overflow: hidden; margin-top: 8px; }
        .confidence-fill { height: 100%; border-radius: 3px; transition: width 0.5s; }
        .disclaimer { text-align: center; color: #333; font-size: 10px; margin-top: 40px; padding: 20px; background: rgba(0,0,0,0.3); border-radius: 8px; max-width: 800px; margin-left: auto; margin-right: auto; }
        .error { background: #ff4444; color: white; padding: 20px; border-radius: 8px; text-align: center; max-width: 600px; margin: 20px auto; }
    </style>
</head>
<body>
    <h1>🤖 AI TRADING SIGNALS</h1>
    <p class="subtitle">Real-time signals using MA + RSI + Volume analysis</p>
    <p class="last-updated">Last updated: {{ now }}</p>
    
    {% if signals %}
    <div class="signals-grid">
        {% for stock in signals %}
        <div class="card">
            <div class="symbol">{{ stock.symbol }}</div>
            <div class="signal {{ stock.signal|lower|replace(' ', '-') }}">{{ stock.signal }}</div>
            <div class="details">
                Confidence: <span>{{ stock.confidence }}%</span><br>
                RSI(14): <span>{{ stock.rsi }}</span><br>
                Trend: <span>{{ stock.ma_trend }}</span><br>
                Volume: <span>{{ "✓" if stock.volume_spike else "✗" }}</span><br>
                Price: <span>${{ stock.price }}</span>
            </div>
            <div class="confidence-bar">
                <div class="confidence-fill" style="width: {{ stock.confidence }}%; background: {% if stock.confidence > 70 %}#00ff88{% elif stock.confidence > 40 %}#ffaa00{% else %}#ff4444{% endif %};"></div>
            </div>
        </div>
        {% endfor %}
    </div>
    {% else %}
    <div class="error">⚠️ No signals generated. Check your API keys.</div>
    {% endif %}
    
    <div class="disclaimer">
        ⚠️ <strong>Disclaimer:</strong> Educational purposes only. Not financial advice. Paper trading mode. Use at your own risk.
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    signals = get_all_signals()
    return render_template_string(DASHBOARD_HTML, signals=signals, now=datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"))

@app.route('/trade')
def trade():
    signals = get_all_signals()
    return jsonify(signals)

@app.route('/history')
def history():
    try:
        with open(SIGNAL_LOG, "r") as f:
            logs = json.load(f)
        return jsonify(logs[-100:])
    except:
        return jsonify([])

@app.route('/status')
def status():
    return jsonify({"status": "running", "timestamp": datetime.now().isoformat(), "stocks_monitored": len(WATCHLIST), "watchlist": WATCHLIST})

if __name__ == '__main__':
    app.run(debug=True)
```