import datetime
import urllib.parse
import feedparser
import pandas as pd

# AI関連用語を幅広く収集（サイト制限を解除）
KEYWORDS = '(OpenAI OR ChatGPT OR Gemini OR Claude OR Copilot OR Meta OR Anthropic OR "生成AI" OR "LLM") -株 -市況 -PR -プレスリリース -無料'
CSV_FILENAME = "ai_news_stats.csv"
RETENTION_DAYS = 30  # 30日分保持

def get_google_news_rss(query: str):
    encoded_query = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ja&gl=JP&ceid=JP:ja"
    return feedparser.parse(url)

def collect_daily_ai_stats():
    jst_now = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=9)
    today_str = jst_now.strftime("%Y-%m-%d")
    yesterday_str = (jst_now - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    
    # 直近ニュースを幅広く取得
    search_query = f"{KEYWORDS} after:{yesterday_str}"
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
    
    print(f"・主要AIニュース: {article_count} 件取得 [{today_str}]")
    return results

def clean_and_save_csv(data_dict, filename=CSV_FILENAME, retention_days=RETENTION_DAYS):
    df_new = pd.DataFrame([data_dict])
    
    try:
        df_existing = pd.read_csv(filename, dtype=str)
        
        # 日付表記の統一（2026/9/24 → 2026-09-24）
        df_existing['date'] = pd.to_datetime(df_existing['date'], errors='coerce').dt.strftime('%Y-%m-%d')
        
        # 不要な列の削除
        unwanted_cols = [col for col in df_existing.columns if 'sankei' in col]
        if unwanted_cols:
            df_existing.drop(columns=unwanted_cols, inplace=True)
            
        # 過去の同日データがある場合、件数が多い（情報量が多い）ほうを優先保持する
        df_existing['count_num'] = pd.to_numeric(df_existing['nikkei_count'], errors='coerce').fillna(0)
        df_existing.sort_values(by=['date', 'count_num'], ascending=[True, False], inplace=True)
        df_existing.drop_duplicates(subset=['date'], keep='first', inplace=True)
        df_existing.drop(columns=['count_num'], inplace=True)
        
        # 本日分を追加（本日分が既にあれば最新データで更新）
        df_existing = df_existing[df_existing['date'] != data_dict['date']]
        df_updated = pd.concat([df_existing, df_new], ignore_index=True)
    except (FileNotFoundError, pd.errors.EmptyDataError):
        df_updated = df_new

    # 30日以上前の古いデータを削除
    df_updated['date_dt'] = pd.to_datetime(df_updated['date'], errors='coerce')
    cutoff_date = datetime.datetime.now() - datetime.timedelta(days=retention_days)
    df_filtered = df_updated[df_updated['date_dt'] >= cutoff_date].copy()
    df_filtered.drop(columns=['date_dt'], inplace=True)

    # 日付昇順で整列
    df_filtered.sort_values(by="date", inplace=True)
    valid_cols = ['date', 'nikkei_count', 'nikkei_titles']
    df_filtered = df_filtered[[c for c in valid_cols if c in df_filtered.columns]]
    
    df_filtered.to_csv(filename, index=False, encoding="utf-8-sig")
    print(f"\nCSVファイルを整理し、'{filename}' に正常保存しました。")

if __name__ == "__main__":
    stats = collect_daily_ai_stats()
    clean_and_save_csv(stats)