import datetime
import urllib.parse
import feedparser
import pandas as pd

PAPERS = {
    "nikkei": "nikkei.com"
}

KEYWORDS = '(OpenAI OR ChatGPT OR Gemini OR Claude OR Copilot OR Meta OR Anthropic OR "生成AI" OR "LLM") (intitle:"新モデル" OR intitle:"新機能" OR intitle:"発表" OR intitle:"リリース" OR intitle:"公開") -intitle:株 -intitle:市況 -intitle:PR -intitle:プレスリリース -intitle:無料'
CSV_FILENAME = "ai_news_stats.csv"
RETENTION_DAYS = 30  # 30日分のみ保持

def get_google_news_rss(query: str):
    encoded_query = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ja&gl=JP&ceid=JP:ja"
    return feedparser.parse(url)

def collect_daily_ai_stats():
    today = datetime.date.today().strftime("%Y-%m-%d")
    domain = PAPERS["nikkei"]
    
    search_query = f"{KEYWORDS} site:{domain} when:1d"
    feed = get_google_news_rss(search_query)
    
    raw_titles = [entry.title for entry in feed.entries]
    unique_titles = list(dict.fromkeys(raw_titles))
    article_count = len(unique_titles)
    
    if unique_titles:
        formatted_titles = "\n".join([f"{i+1}. {t}" for i, t in enumerate(unique_titles)])
    else:
        formatted_titles = "なし"
    
    results = {
        "date": today,
        "nikkei_count": article_count,
        "nikkei_titles": formatted_titles
    }
    
    print(f"・日本経済新聞 ({domain}): {article_count} 件取得")
    return results

def save_to_csv_with_cleanup(data_dict, filename=CSV_FILENAME, retention_days=RETENTION_DAYS):
    df_new = pd.DataFrame([data_dict])
    
    try:
        df_existing = pd.read_csv(filename)
        # 過去の集計（産経新聞版等）との列の整合性を合わせる
        df_updated = pd.concat([df_existing, df_new], ignore_index=True)
        df_updated.drop_duplicates(subset=["date"], keep="last", inplace=True)
    except (FileNotFoundError, pd.errors.EmptyDataError):
        df_updated = df_new
        
    # 古いデータの自動破棄処理（日付フォーマットのエラーを吸収）
    df_updated['date_dt'] = pd.to_datetime(df_updated['date'], errors='coerce')
    cutoff_date = datetime.datetime.now() - datetime.timedelta(days=retention_days)
    
    df_filtered = df_updated[df_updated['date_dt'] >= cutoff_date].copy()
    df_filtered.drop(columns=['date_dt'], inplace=True)
    
    df_filtered.to_csv(filename, index=False, encoding="utf-8-sig")
    print(f"\n集計データを '{filename}' に保存しました。（直近 {retention_days} 日分のみ保持）")

if __name__ == "__main__":
    stats = collect_daily_ai_stats()
    save_to_csv_with_cleanup(stats)