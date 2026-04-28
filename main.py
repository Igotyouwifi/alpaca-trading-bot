```python
from flask import Flask, jsonify, render_template_string
from alpaca_trade_api import REST
import pandas as pd
import os
from datetime import datetime, timedelta
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Alpaca API Setup
ALPACA_API_KEY = os.getenv("APCA_API_KEY_ID")
ALPACA_SECRET_KEY = os.getenv("APCA_API_SECRET_KEY")
BASE_URL = "https://paper-api.alpaca.markets"

api = REST(ALPACA_API_KEY, ALPACA_SECRET_KEY, BASE_URL)

WATCHLIST = ["AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "GOOGL", "META", "AMD", "SPY", "QQQ"]

def calculate_indicators(symbol, timeframe="day"):
    try:
        bars = api.get_bars(symbol, timeframe, limit=100)
        
        if len(bars) < 20:
            logger.warning(f"Not enough data for {symbol}")
            return None
        
        df = pd.DataFrame({
            'close': [bar.c for bar in bars],
            'high': [bar.h for bar in bars],
            'low': [bar.l for bar in bars],
            'volume': [bar.v for bar in bars]
        })
        
        # Moving Averages
        df['ma5'] = df['close'].rolling(window=5).mean()
        df['ma20'] = df['close'].rolling(window=20).mean()
        
        # RSI
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # MACD
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = exp1 - exp2
        df['signal_line'] = df['macd'].ewm(span=9, adjust=False).mean()
        
        # Volatility
        df['volatility'] = df['close'].rolling(window=20).std() / df['close'].rolling(window=20).mean()
        
        latest = df.iloc[-1]
        
        return {
            'ma5': float(latest['ma5']),
            'ma20': float(latest['ma20']),
            'rsi': float(latest['rsi']),
            'macd': float(latest['macd']),
            'signal_line': float(latest['signal_line']),
            'volatility': float(latest['volatility']),
            'close': float(latest['close'])
        }
    
    except Exception as e:
        logger.error(f"Error calculating indicators for {symbol}: {str(e)}")
        return None

def generate_signal(symbol):
    indicators = calculate_indicators(symbol)
    
    if not indicators:
        return {
            'symbol': symbol,
            'signal': 'ERROR',
            'confidence': 0,
            'reason': 'Insufficient data'
        }
    
    ma5 = indicators['ma5']
    ma20 = indicators['ma20']
    rsi = indicators['rsi']
    macd = indicators['macd']
    signal_line = indicators['signal_line']
    volatility = indicators['volatility']
    
    # Risk check
    if volatility > 0.05:
        return {
            'symbol': symbol,
            'signal': 'HOLD',
            'confidence': 0,
            'reason': 'High volatility - avoiding trades'
        }
    
    # Signal scoring
    score = 0
    
    # MA crossover
    if ma5 > ma20:
        score += 1.5
    else:
        score -= 1.5
    
    # RSI
    if rsi < 30:
        score += 1.0
    elif rsi > 70:
        score -= 1.0
    
    # MACD
    if macd > signal_line:
        score += 1.0
    else:
        score -= 1.0
    
    confidence = min(max((score + 3) * 16.67, 0), 100)
    
    if score >= 2:
        signal = "STRONG BUY"
    elif score >= 0.5:
        signal = "BUY"
    elif score <= -2:
        signal = "STRONG SELL"
    elif score <= -0.5:
        signal = "SELL"
    else:
        signal = "HOLD"
    
    return {
        'symbol': symbol,
        'signal': signal,
        'confidence': round(confidence, 1),
        'rsi': round(rsi, 2),
        'ma_trend': 'bullish' if ma5 > ma20 else 'bearish',
        'macd_trend': 'bullish' if macd > signal_line else 'bearish'
    }

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>AI Trading Signals</title>
    <meta http-equiv="refresh" content="60">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            background: #0a0a0a; 
            color: #ffffff; 
            font-family: 'Courier New', monospace;
            padding: 20px;
        }
        h1 { 
            text-align: center; 
            margin-bottom: 10px;
            color: #00ff88;
            font-size: 28px;
        }
        .subtitle {
            text-align: center;
            color: #666;
            margin-bottom: 40px;
            font-size: 12px;
        }
        .signals-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            max-width: 1200px;
            margin: 0 auto;
        }
        .card {
            background: #111;
            border: 1px solid #222;
            border-radius: 12px;
            padding: 20px;
        }
        .symbol {
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 12px;
        }
        .signal {
            font-size: 18px;
            font-weight: bold;
            padding: 8px 12px;
            border-radius: 6px;
            display: inline-block;
            margin-bottom: 16px;
        }
        .signal.strong-buy { 
            background: #00ff8840; 
            color: #00ff88; 
            border: 1px solid #00ff88;
        }
        .signal.buy { 
            background: #00dd6640; 
            color: #00dd66; 
            border: 1px solid #00dd66;
        }
        .signal.sell { 
            background: #ff444440; 
            color: #ff4444; 
            border: 1px solid #ff4444;
        }
        .signal.strong-sell { 
            background: #dd000040; 
            color: #dd0000; 
            border: 1px solid #dd0000;
        }
        .signal.hold { 
            background: #ffaa0040; 
            color: #ffaa00; 
            border: 1px solid #ffaa00;
        }
        .signal.error { 
            background: #66666640; 
            color: #999; 
            border: 1px solid #666;
        }
        .details { 
            color: #aaa; 
            font-size: 13px; 
            line-height: 1.8;
        }
        .confidence-bar {
            width: 100%;
            height: 6px;
            background: #222;
            border-radius: 3px;
            margin-top: 12px;
            overflow: hidden;
        }
        .confidence-fill {
            height: 100%;
            border-radius: 3px;
            transition: width 0.5s;
        }
        .disclaimer {
            text-align: center;
            color: #444;
            font-size: 11px;
            margin-top: 50px;
            padding: 20px;
        }
        .timestamp {
            text-align: center;
            color: #555;
            font-size: 11px;
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <h1>🤖 AI TRADING SIGNALS</h1>
    <p class="subtitle">Paper Trading | Auto-refreshes every 60 seconds</p>
    <p class="timestamp">Last updated: {{ timestamp }}</p>
    
    <div class="signals-grid">
        {% for stock in signals %}
        <div class="card">
            <div class="symbol">{{ stock.symbol }}</div>
            <div class="signal {{ stock.signal|lower|replace(' ', '-') }}">
                {{ stock.signal }}
            </div>
            <div class="details">
                {% if stock.confidence > 0 %}
                Confidence: {{ stock.confidence }}%<br>
                RSI: {{ stock.rsi }}<br>
                MA Trend: {{ stock.ma_trend }}<br>
                MACD: {{ stock.macd_trend }}
                {% else %}
                {{ stock.reason }}
                {% endif %}
            </div>
            {% if stock.confidence > 0 %}
            <div class="confidence-bar">
                <div class="confidence-fill" style="
                    width: {{ stock.confidence }}%;
                    background: {% if stock.confidence > 70 %}#00ff88
                    {% elif stock.confidence > 40 %}#ffaa00
                    {% else %}#ff4444{% endif %};
                "></div>
            </div>
            {% endif %}
        </div>
        {% endfor %}
    </div>
    
    <div class="disclaimer">
        WARNING: This is educational/paper trading only. Not financial advice. Do not trade real money based on these signals.
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    signals = [generate_signal(symbol) for symbol in WATCHLIST]
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    return render_template_string(DASHBOARD_HTML, signals=signals, timestamp=timestamp)

@app.route('/trade')
def trade():
    signals = [generate_signal(symbol) for symbol in WATCHLIST]
    return jsonify(signals)

@app.route('/status')
def status():
    return jsonify({
        'status': 'online',
        'timestamp': datetime.now().isoformat(),
        'watchlist': WATCHLIST,
        'mode': 'paper_trading'
    })

@app.route('/health')
def health():
    return jsonify({'health': 'ok'}), 200

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
```

Then:

```bash
git add main.py
git commit -m "complete rewrite with dashboard and improved signals"
git push
```

