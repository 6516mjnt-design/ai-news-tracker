import datetime
import urllib.parse
import feedparser
import pandas as pd

PAPERS = {
    "nikkei": "nikkei.com"
}

KEYWORDS = '(OpenAI OR ChatGPT OR Gemini OR Claude OR "生成AI" OR "LLM") (新モデル OR 新機能 OR 発表 OR リリリース OR 公開) -株 -市況 -PR -プレスリリース -無料'
CSV_FILENAME = "ai_news_stats.csv"
RETENTION_DAYS = 30

def get_google_news_rss(query: str):
    encoded_query = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ja&gl=JP&ceid=JP:ja"
    return feedparser.parse(url)

def collect_daily_ai_stats():
    jst_now = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=9)
    today_str = jst_now.strftime("%Y-%m-%d")
    yesterday_str = (jst_now - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    
    domain = PAPERS["nikkei"]
    
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
        # csvを文字列として確実に読み込み
        df_existing = pd.read_csv(filename, dtype=str)
        
        # 不要な過去列の削除
        unwanted_cols = [col for col in df_existing.columns if 'sankei' in col]
        if unwanted_cols:
            df_existing.drop(columns=unwanted_cols, inplace=True)
            
        # 今日の日付の行を一旦完全に除去してから、最新の取得結果を追加する
        df_existing = df_existing[df_existing['date'].astype(str) != str(data_dict['date'])].copy()
        df_updated = pd.concat([df_existing, df_new], ignore_index=True)
    except (FileNotFoundError, pd.errors.EmptyDataError):
        df_updated = df_new

    # 日付で並べ替え
    df_updated.sort_values(by="date", inplace=True)
    
    # 保存
    valid_cols = ['date', 'nikkei_count', 'nikkei_titles']
    df_updated = df_updated[[c for c in valid_cols if c in df_updated.columns]]
    df_updated.to_csv(filename, index=False, encoding="utf-8-sig")
    print(f"\n集計データを '{filename}' に書き込み完了しました。")

if __name__ == "__main__":
    stats = collect_daily_ai_stats()
    save_to_csv_with_cleanup(stats)