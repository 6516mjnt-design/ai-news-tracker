import datetime
import urllib.parse
import feedparser
import pandas as pd

PAPERS = {
    "日本経済新聞": "nikkei.com",
    "朝日新聞": "asahi.com",
    "読売新聞": "yomiuri.co.jp",
    "毎日新聞": "mainichi.jp",
    "産経新聞": "sankei.com"
}

KEYWORDS = "(AI OR 人工知能 OR 生成AI OR ChatGPT)"

def get_google_news_rss(query: str):
    encoded_query = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ja&gl=JP&ceid=JP:ja"
    return feedparser.parse(url)

def collect_daily_ai_stats():
    today = datetime.date.today().strftime("%Y-%m-%d")
    results = {"date": today}
    
    print(f"=== {today} のAI関連記事集計を開始します ===")
    
    for paper_name, domain in PAPERS.items():
        search_query = f"{KEYWORDS} site:{domain}"
        feed = get_google_news_rss(search_query)
        article_count = len(feed.entries)
        results[paper_name] = article_count
        print(f"・{paper_name} ({domain}): {article_count} 件")
        
    return results

def save_to_csv(data_dict, filename="ai_news_stats.csv"):
    df_new = pd.DataFrame([data_dict])
    
    try:
        df_existing = pd.read_csv(filename)
        df_updated = pd.concat([df_existing, df_new], ignore_index=True)
        df_updated.drop_duplicates(subset=["date"], keep="last", inplace=True)
    except FileNotFoundError:
        df_updated = df_new
        
    df_updated.to_csv(filename, index=False, encoding="utf-8-sig")
    print(f"\n集計データを '{filename}' に保存しました。")

if __name__ == "__main__":
    stats = collect_daily_ai_stats()
    save_to_csv(stats)