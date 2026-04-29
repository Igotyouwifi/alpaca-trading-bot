TIER_CONFIGS = {
    "starter": {
        "price": "Free 3-day trial, then $4.99/month",
        "symbols": ["AAPL", "TSLA"],
        "crypto_symbols": ["BTC-USD"],
        "min_score_buy": 85,
        "max_score_sell": 15,
        "auto_trade": False,
        "paper_trading": False,
        "live_trading_allowed": False,
        "email_only": True,
        "delay_minutes": 0,
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
        "symbols": [
            # US mega-cap / growth
            "AAPL", "TSLA", "NVDA", "MSFT", "AMZN",
            "META", "GOOGL", "AMD", "PLTR", "NFLX",
            "AVGO", "SMCI", "COIN", "MSTR", "SHOP",
            "JPM", "BAC", "WMT", "COST", "DIS",
            "PYPL", "SOFI", "UBER", "SNOW", "CRWD",
            "ADBE", "ORCL", "CRM", "INTC", "QCOM",

            # ETFs / market tracking
            "SPY", "QQQ", "DIA", "IWM", "ARKK",

            # Global / international examples
            "TSM", "BABA", "NIO", "PDD", "JD",
            "ASML", "ARM", "SONY", "TM", "HMC",

            # International exchange examples through yfinance
            "7203.T",     # Toyota Japan
            "6758.T",     # Sony Japan
            "9984.T",     # SoftBank Japan
            "005930.KS",  # Samsung Korea
            "0700.HK",    # Tencent Hong Kong
            "9988.HK",    # Alibaba Hong Kong
            "RMS.PA",     # Hermes Paris
            "MC.PA",      # LVMH Paris
            "BMW.DE",     # BMW Germany
            "VOW3.DE",    # Volkswagen Germany
            "HSBA.L",     # HSBC London
            "BP.L"        # BP London
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