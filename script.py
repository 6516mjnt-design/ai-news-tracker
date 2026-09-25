import datetime
import urllib.parse
import feedparser
import pandas as pd

PAPERS = {
    "nikkei": "nikkei.com"
}

# KEYWORDSのintitle制限を外し、Google News RSSの検索漏れを完全防止
KEYWORDS = '(OpenAI OR ChatGPT OR Gemini OR Claude OR "生成AI" OR "LLM") (新モデル OR 新機能 OR 発表 OR リリース OR 公開) -株 -市況 -PR -プレスリリース -無料'
CSV_FILENAME = "ai_news_stats.csv"
RETENTION_DAYS = 30  # 30日分のみ保持

def get_google_news_rss(query: str):
    encoded_query = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ja&gl=JP&ceid=JP:ja"
    return feedparser.parse(url)

def collect_daily_ai_stats():
    # 日本時間（JST）で今日と昨日の日付を取得
    jst_now = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=9)
    today_str = jst_now.strftime("%Y-%m-%d")
    yesterday_str = (jst_now - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    
    domain = PAPERS["nikkei"]
    
    # after: 検索で直近ニュースを確実に集計
    search_query = f"{KEYWORDS} site:{domain} after:{yesterday_str}"
    feed = get_google_news_rss(search_query)
    
    raw_titles = [entry.title for entry in feed.entries]
    unique_titles = list(dict.fromkeys(raw_titles))
    article_count = len(unique_titles)
    
    if unique_titles:
        formatted_titles = "\n".join([f"{i+1}. {t}" for i, t in enumerate(unique_titles)])
    else:
        formatted_titles = "該当ニュースなし"
    
    results = {
        "date": today_str,
        "nikkei_count": article_count,
        "nikkei_titles": formatted_titles
    }
    
    print(f"・日本経済新聞 ({domain}): {article_count} 件取得 [{today_str}]")
    return results

def save_to_csv_with_cleanup(data_dict, filename=CSV_FILENAME, retention_days=RETENTION_DAYS):
    df_new = pd.DataFrame([data_dict])
    
    try:
        df_existing = pd.read_csv(filename)
        
        # 不要な過去の列（sankei_count 等）を削除
        unwanted_cols = [col for col in df_existing.columns if 'sankei' in col]
        if unwanted_cols:
            df_existing.drop(columns=unwanted_cols, inplace=True)
            
        df_updated = pd.concat([df_existing, df_new], ignore_index=True)
        # 同一判定日付は最新実行結果で上書き
        df_updated.drop_duplicates(subset=["date"], keep="last", inplace=True)
    except (FileNotFoundError, pd.errors.EmptyDataError):
        df_updated = df_new
        
    # 30日以上前の古いデータを削除
    df_updated['date_dt'] = pd.to_datetime(df_updated['date'], errors='coerce')
    cutoff_date = datetime.datetime.now() - datetime.timedelta(days=retention_days)
    
    df_filtered = df_updated[df_updated['date_dt'] >= cutoff_date].copy()
    df_filtered.drop(columns=['date_dt'], inplace=True)
    
    # 指定列順に整理
    valid_cols = ['date', 'nikkei_count', 'nikkei_titles']
    df_filtered = df_filtered[[c for c in valid_cols if c in df_filtered.columns]]
    
    df_filtered.to_csv(filename, index=False, encoding="utf-8-sig")
    print(f"\n集計データを '{filename}' に保存しました。")

if __name__ == "__main__":
    stats = collect_daily_ai_stats()
    save_to_csv_with_cleanup(stats)