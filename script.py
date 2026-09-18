import datetime
import urllib.parse
import feedparser
import pandas as pd

PAPERS = {
    "nikkei": "nikkei.com",
    "asahi": "asahi.com",
    "yomiuri": "yomiuri.co.jp",
    "mainichi": "mainichi.jp",
    "sankei": "sankei.com"
}

# 検索キーワード
KEYWORDS = '(intitle:"AI" OR intitle:人工知能 OR intitle:生成AI OR intitle:ChatGPT) -intitle:株 -intitle:市況'

def get_google_news_rss(query: str):
    encoded_query = urllib.parse.quote(query)
    # 検索クエリをエンコードしてURLを生成
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ja&gl=JP&ceid=JP:ja"
    return feedparser.parse(url)

def collect_daily_ai_stats():
    today = datetime.date.today().strftime("%Y-%m-%d")
    results = {"date": today}

    for paper_key, domain in PAPERS.items():
        # 日経新聞だけ直近12時間に絞り込み、他社は直近24時間のままにする
        time_frame = "when:12h" if paper_key == "nikkei" else "when:1d"
        search_query = f"{KEYWORDS} site:{domain} {time_frame}"
        
        feed = get_google_news_rss(search_query)
        article_count = len(feed.entries)
        results[paper_key] = article_count
        print(f"・{paper_key} ({domain}): {article_count} 件")

    return results

def save_to_csv(data_dict, filename="ai_news_stats.csv"):
    df_new = pd.DataFrame([data_dict])
    
    try:
        df_existing = pd.read_csv(filename)
        df_updated = pd.concat([df_existing, df_new], ignore_index=True)
        df_updated.drop_duplicates(subset=["date"], keep="last", inplace=True)
    except (FileNotFoundError, pd.errors.EmptyDataError):
        df_updated = df_new
        
    df_updated.to_csv(filename, index=False, encoding="utf-8-sig")
    print(f"\n集計データを '{filename}' に保存しました。")

if __name__ == "__main__":
    stats = collect_daily_ai_stats()
    save_to_csv(stats)