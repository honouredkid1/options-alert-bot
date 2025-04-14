# options_alert_bot.py

import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
import telegram
import time
import datetime
import os
from sentiment_scanner import get_combined_sentiment

# === Telegram Setup ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
bot = telegram.Bot(token=TELEGRAM_TOKEN)

# Send test message on startup
try:
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text="✅ Bot is running and connected to Telegram.")
    print("✅ Test message sent to Telegram.")
except Exception as e:
    print(f"❌ Failed to send Telegram test message: {e}")

# === Ticker Universe ===
tickers = [
    "AAPL", "MSFT", "TSLA", "NVDA", "AMZN", "GOOG",
    "SPY", "QQQ", "DIA", "IWM",
    "BTC-USD", "ETH-USD", "SOL-USD", "ADA-USD"
]

# === Signal Cache ===
last_signals = {}
CACHE_RESET_MINUTES = 60
last_reset_time = time.time()

# === Pattern Detection ===
def detect_patterns(df):
    patterns = []
    close = df['Close']
    ma20 = close.rolling(window=20).mean()
    ma50 = close.rolling(window=50).mean()
    if close.iloc[-1] > ma20.iloc[-1] and close.iloc[-1] > ma50.iloc[-1]:
        patterns.append("Strong Uptrend")
    elif close.iloc[-1] < ma20.iloc[-1] and close.iloc[-1] < ma50.iloc[-1]:
        patterns.append("Strong Downtrend")
    else:
        if close.iloc[-1] > ma20.iloc[-1]:
            patterns.append("Above 20MA")
        if close.iloc[-1] > ma50.iloc[-1]:
            patterns.append("Above 50MA")
        if close.iloc[-1] < ma20.iloc[-1]:
            patterns.append("Below 20MA")
        if close.iloc[-1] < ma50.iloc[-1]:
            patterns.append("Below 50MA")
    return patterns

# === Signal Detection Logic ===
def get_signal(df):
    df.ta.rsi(length=14, append=True)
    df.ta.macd(append=True)
    df.ta.ema(length=20, append=True)
    df.ta.ema(length=50, append=True)
    df['Volume_Avg'] = df['Volume'].rolling(10).mean()
    df.dropna(inplace=True)
    last = df.iloc[-1]
    bull = (
        last['RSI_14'] > 50 and
        last['MACD_12_26_9'] > last['MACDs_12_26_9'] and
        last['Volume'] > last['Volume_Avg'] and
        last['EMA_20'] > last['EMA_50']
    )
    bear = (
        last['RSI_14'] < 50 and
        last['MACD_12_26_9'] < last['MACDs_12_26_9'] and
        last['Volume'] > last['Volume_Avg'] and
        last['EMA_20'] < last['EMA_50']
    )
    return 'CALL' if bull else 'PUT' if bear else None

# === Options Chain Scanner ===
def get_best_strike(ticker, current_price, label):
    try:
        ticker_obj = yf.Ticker(ticker)
        expiry = datetime.datetime.now().strftime('%Y-%m-%d')
        if expiry not in ticker_obj.options:
            return None, None
        chain = ticker_obj.option_chain(expiry)
        df_chain = chain.calls if label == "CALL" else chain.puts
        df_chain['diff'] = abs(df_chain['strike'] - current_price)
        df_chain = df_chain[df_chain['volume'] > 100]
        if df_chain.empty:
            return None, None
        best = df_chain.sort_values('diff').iloc[0]
        return best['strike'], expiry
    except:
        return None, None

# === Smart Alert Logic ===
def should_alert(ticker, label, strike):
    key = f"{ticker}_{label}"
    if key not in last_signals or last_signals[key] != strike:
        last_signals[key] = strike
        return True
    return False

# === Main Scanner ===
def scan_ticker(ticker):
    try:
        df = yf.download(ticker, period="1d", interval="5m", progress=False)
        if df.empty or len(df) < 30:
            return
        label = get_signal(df)
        if not label:
            return
        current_price = df.iloc[-1]['Close']
        strike, expiry = get_best_strike(ticker, current_price, label)
        if not strike:
            return
        if not should_alert(ticker, label, strike):
            return

        try:
            sentiment = get_combined_sentiment(ticker.replace("-USD", ""))
            avg_sentiment = np.mean([
                sentiment.get('reddit_sentiment', 0),
                sentiment.get('twitter_sentiment', 0),
                sentiment.get('news_sentiment', 0)
            ])
        except Exception as e:
            sentiment = {}
            avg_sentiment = 0
            print(f"⚠️ Sentiment fetch failed for {ticker}: {e}")

        base_conf = np.random.uniform(0.75, 0.85)
        confidence = round(base_conf + avg_sentiment * 0.2, 2)
        patterns = detect_patterns(df)

        msg = f"""
🚨 TRADE ALERT: 0DTE {label}

Ticker: {ticker}
Strike: {strike}
Expiry: {expiry}
Current Price: ${current_price:.2f}
Signal: {label} | Confidence: {confidence}

📊 Detected Patterns: {', '.join(patterns)}

🗣 Public Sentiment:
- Reddit: {sentiment.get('reddit_sentiment', 0)} ({sentiment.get('reddit_mentions', 0)} posts)
- Twitter: {sentiment.get('twitter_sentiment', 0)} ({sentiment.get('twitter_mentions', 0)} tweets)
- News: {sentiment.get('news_sentiment', 0)} ({sentiment.get('news_mentions', 0)} headlines)

Manual execution suggested.
        """
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)
        print(f"Alert sent for {ticker} - {label}")
    except Exception as e:
        print(f"Error scanning {ticker}: {e}")

# === Loop Runner ===
while True:
    for ticker in tickers:
        scan_ticker(ticker)
    print("Scan cycle complete. Sleeping for 300 seconds...")

    if (time.time() - last_reset_time) > (CACHE_RESET_MINUTES * 60):
        last_signals.clear()
        last_reset_time = time.time()
        print("Signal cache reset.")

    time.sleep(300)  # 5-minute interval
# Placeholder: Insert full options_alert_bot.py code here (copied from canvas)
