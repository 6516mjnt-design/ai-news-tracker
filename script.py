import datetime
import urllib.parse
import feedparser
import pandas as pd

# 対象メディアを産経新聞のみに絞り込み
PAPERS = {
    "sankei": "sankei.com"
}

# 「新モデル・新機能・発表」に特化したキーワード設定
KEYWORDS = '(intitle:"新モデル" OR intitle:"新機能" OR intitle:"発表" OR intitle:"リリース" OR intitle:"公開") (intitle:"AI" OR intitle:"生成AI" OR intitle:"LLM") -intitle:株 -intitle:市況'
CSV_FILENAME = "ai_news_stats.csv"

def get_google_news_rss(query: str):
    encoded_query = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ja&gl=JP&ceid=JP:ja"
    return feedparser.parse(url)

def collect_daily_ai_stats():
    today = datetime.date.today().strftime("%Y-%m-%d")
    
    domain = PAPERS["sankei"]
    search_query = f"{KEYWORDS} site:{domain} when:1d"
    
    feed = get_google_news_rss(search_query)
    
    titles = [entry.title for entry in feed.entries]
    article_count = len(titles)
    
    # 複数タイトルをパイプ(|)区切りで結合
    titles_str = " | ".join(titles) if titles else "なし"
    
    results = {
        "date": today,
        "sankei_count": article_count,
        "sankei_titles": titles_str
    }
    
    print(f"・産経新聞 ({domain}): {article_count} 件")
    if titles:
        print("  タイトル:")
        for t in titles:
            print(f"   - {t}")

    return results

def save_to_csv(data_dict, filename=CSV_FILENAME):
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