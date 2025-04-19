# sentiment_scanner.py

import requests
from bs4 import BeautifulSoup
from textblob import TextBlob
import snscrape.modules.twitter as sntwitter
import datetime
import re
import numpy as np  # ✅ FIXED: import numpy properly

# === CONFIG ===
REDDIT_URL = "https://api.pushshift.io/reddit/search/submission"
NEWS_SOURCES = [
    "https://finance.yahoo.com",
    "https://www.marketwatch.com/latest-news"
]
HEADERS = {'User-Agent': 'Mozilla/5.0'}

# === Text Cleaner and Sentiment Scorer ===
def clean_text(text):
    text = re.sub(r'http\\S+', '', text)
    return re.sub(r'[^A-Za-z0-9$.,!?\\s]', '', text)

def score_sentiment(text):
    analysis = TextBlob(text)
    return analysis.sentiment.polarity

# === Reddit Sentiment ===
def scan_reddit(ticker):
    params = {
        "subreddit": "stocks,options,wallstreetbets",
        "q": ticker,
        "sort": "desc",
        "size": 50
    }
    try:
        response = requests.get(REDDIT_URL, params=params, timeout=10).json()
        posts = [x.get('title', '') + ' ' + x.get('selftext', '') for x in response.get('data', [])]
        sentiments = [score_sentiment(clean_text(p)) for p in posts if p]
    except Exception as e:
        print(f"Reddit scan failed: {e}")
        return {"reddit_sentiment": 0, "reddit_mentions": 0}
    if not sentiments:
        return {"reddit_sentiment": 0, "reddit_mentions": 0}
    return {
        "reddit_sentiment": round(sum(sentiments) / len(sentiments), 2),
        "reddit_mentions": len(sentiments)
    }

# === Twitter Sentiment ===
def scan_twitter(ticker):
    tweets = []
    limit = 50
    query = f"${ticker} since:{(datetime.date.today() - datetime.timedelta(days=1))}"
    try:
        for i, tweet in enumerate(sntwitter.TwitterSearchScraper(query).get_items()):
            if i > limit:
                break
            tweets.append(tweet.content)
        sentiments = [score_sentiment(clean_text(t)) for t in tweets if t]
    except Exception as e:
        print(f"Twitter scan failed: {e}")
        return {"twitter_sentiment": 0, "twitter_mentions": 0}
    if not sentiments:
        return {"twitter_sentiment": 0, "twitter_mentions": 0}
    return {
        "twitter_sentiment": round(sum(sentiments) / len(sentiments), 2),
        "twitter_mentions": len(sentiments)
    }

# === News Headlines Sentiment ===
def scan_news(ticker):
    all_headlines = []
    for url in NEWS_SOURCES:
        try:
            page = requests.get(url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(page.content, "html.parser")
            headlines = soup.find_all('a')
            for h in headlines:
                text = h.get_text()
                if text and ticker.lower() in text.lower():
                    all_headlines.append(text)
        except:
            continue
    sentiments = [score_sentiment(clean_text(h)) for h in all_headlines if h]
    if not sentiments:
        return {"news_sentiment": 0, "news_mentions": 0}
    return {
        "news_sentiment": round(sum(sentiments) / len(sentiments), 2),
        "news_mentions": len(sentiments)
    }

# === Combine Everything ===
def get_combined_sentiment(ticker):
    reddit = scan_reddit(ticker)
    twitter = scan_twitter(ticker)
    news = scan_news(ticker)
    return {
        **reddit,
        **twitter,
        **news
    }

# === Test Run ===
if __name__ == "__main__":
    result = get_combined_sentiment("TSLA")
    print(result)
