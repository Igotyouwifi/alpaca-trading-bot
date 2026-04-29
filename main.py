@app.route("/")
@app.route("/dashboard")
def dashboard():
    return '''
<!DOCTYPE html>
<html>
<head>
    <title>AI Stock Agent</title>
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
        .hold, .watch_buy, .watch_sell {
            color: #facc15;
            font-weight: bold;
        }
        .score {
            font-size: 22px;
            font-weight: bold;
        }
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
    <button onclick="loadTiers()">Tiers</button>

    <div id="content"></div>

    <script>
        async function loadSignals(tier) {
            document.getElementById("content").innerHTML = "<p>Loading signals...</p>";
            const res = await fetch("/signals?tier=" + tier);
            const data = await res.json();
            renderSignals(data);
        }

        async function loadCrypto() {
            document.getElementById("content").innerHTML = "<p>Loading crypto...</p>";
            const res = await fetch("/crypto?tier=mastery_plus");
            const data = await res.json();
            renderSignals(data);
        }

        async function loadReport() {
            document.getElementById("content").innerHTML = "<p>Loading report...</p>";
            const res = await fetch("/report");
            const data = await res.json();

            let html = "<h2>Daily Account Report</h2>";
            html += "<div class='card'>";
            html += "<p>Status: " + data.status + "</p>";
            html += "<p>Account Status: " + (data.account_status || "N/A") + "</p>";
            html += "<p>Cash: $" + (data.cash || "N/A") + "</p>";
            html += "<p>Buying Power: $" + (data.buying_power || "N/A") + "</p>";
            html += "<p>Portfolio Value: $" + (data.portfolio_value || "N/A") + "</p>";
            html += "<p>Equity: $" + (data.equity || "N/A") + "</p>";
            html += "<p>Total Unrealized P/L: $" + (data.total_unrealized_pl || 0) + "</p>";
            html += "<p>Today Unrealized P/L: $" + (data.today_unrealized_pl || 0) + "</p>";
            html += "</div>";

            if (data.positions && data.positions.length > 0) {
                html += "<h2>Open Positions</h2><div class='grid'>";
                data.positions.forEach(p => {
                    html += "<div class='card'>";
                    html += "<h2>" + p.symbol + "</h2>";
                    html += "<p>Qty: " + p.qty + "</p>";
                    html += "<p>Market Value: $" + p.market_value + "</p>";
                    html += "<p>Avg Entry: $" + p.avg_entry_price + "</p>";
                    html += "<p>Current Price: $" + p.current_price + "</p>";
                    html += "<p>Unrealized P/L: $" + p.unrealized_pl + "</p>";
                    html += "</div>";
                });
                html += "</div>";
            }

            document.getElementById("content").innerHTML = html;
        }

        async function loadTiers() {
            document.getElementById("content").innerHTML = "<p>Loading tiers...</p>";
            const res = await fetch("/tiers");
            const data = await res.json();

            let html = "<h2>Subscription Tiers</h2><div class='grid'>";

            Object.keys(data).forEach(tier => {
                html += "<div class='card'>";
                html += "<h2>" + tier + "</h2>";
                html += "<p>Price: " + data[tier].price + "</p>";
                html += "<p>Auto Trade: " + data[tier].auto_trade + "</p>";
                html += "<p>Symbols: " + data[tier].symbols.join(", ") + "</p>";
                html += "<p>Features: " + data[tier].features.join(", ") + "</p>";
                html += "</div>";
            });

            html += "</div>";
            document.getElementById("content").innerHTML = html;
        }

        function renderSignals(data) {
            let html = "<h2>Tier: " + data.tier + "</h2>";
            html += "<p>Auto Trade: " + data.auto_trade + "</p>";
            html += "<p>Crypto Mode: " + data.crypto_mode + "</p>";
            html += "<div class='grid'>";

            data.signals.forEach(s => {
                html += "<div class='card'>";
                html += "<h2>" + s.symbol + "</h2>";
                html += "<p>Signal: <span class='" + s.signal + "'>" + s.signal + "</span></p>";
                html += "<p class='score'>Score: " + s.score + "</p>";
                html += "<p>Confidence: " + s.confidence + "</p>";
                html += "<p>Last Price: $" + (s.last_price || "N/A") + "</p>";
                html += "<p>Reasons: " + ((s.reasons || [s.reason || "none"]).join(", ")) + "</p>";
                html += "<p>Bars Received: " + (s.bars_received || "N/A") + "</p>";
                html += "<p>Order Status: " + s.order_status + "</p>";
                html += "</div>";
            });

            html += "</div>";
            document.getElementById("content").innerHTML = html;
        }

        loadSignals("pro");
    </script>
</body>
</html>
'''