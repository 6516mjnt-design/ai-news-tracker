import datetime
import urllib.parse
import feedparser
import pandas as pd

# 主要AI用語で広く最新ニュースを収集（サイト制限なし）
KEYWORDS = '(OpenAI OR ChatGPT OR Gemini OR Claude OR Copilot OR Meta OR Anthropic OR "生成AI" OR "LLM") -株 -市況 -PR -プレスリリース -無料'
CSV_FILENAME = "ai_news_stats.csv"
RETENTION_DAYS = 30  # 30日分保持

def get_google_news_rss(query: str):
    encoded_query = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ja&gl=JP&ceid=JP:ja"
    return feedparser.parse(url)

def fetch_stats_for_date(target_date_str: str):
    """指定日のニュースを全体検索で取得"""
    dt = datetime.datetime.strptime(target_date_str, "%Y-%m-%d")
    after_date_str = (dt - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    
    search_query = f"{KEYWORDS} after:{after_date_str}"
    feed = get_google_news_rss(search_query)
    
    raw_titles = [entry.title for entry in feed.entries]
    unique_titles = list(dict.fromkeys(raw_titles))
    article_count = len(unique_titles)
    
    if unique_titles:
        formatted_titles = "\n".join([f"{i+1}. {t}" for i, t in enumerate(unique_titles)])
    else:
        formatted_titles = "該当ニュースなし"
    
    return {
        "date": target_date_str,
        "ai_news_count": article_count,
        "ai_news_titles": formatted_titles
    }

def rebuild_and_clean_csv():
    jst_now = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=9)
    today_str = jst_now.strftime("%Y-%m-%d")
    yesterday_str = (jst_now - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    
    # 9/24 と 9/25 の両方を全サイト基準で再取得（列名も新基準へ）
    stats_yesterday = fetch_stats_for_date(yesterday_str)
    stats_today = fetch_stats_for_date(today_str)
    
    df_new = pd.DataFrame([stats_yesterday, stats_today])
    
    try:
        df_existing = pd.read_csv(CSV_FILENAME, dtype=str)
        # 日付表記統一
        df_existing['date'] = pd.to_datetime(df_existing['date'], errors='coerce').dt.strftime('%Y-%m-%d')
        
        # 不要な旧列（sankei_... / nikkei_...）があれば完全削除
        old_cols = [c for c in df_existing.columns if 'nikkei' in c or 'sankei' in c]
        if old_cols:
            df_existing.drop(columns=old_cols, inplace=True)
            
        # 再取得した日付の旧データを削除して最新データへ置き換え
        target_dates = [today_str, yesterday_str]
        df_existing = df_existing[~df_existing['date'].isin(target_dates)].copy()
        
        df_updated = pd.concat([df_existing, df_new], ignore_index=True)
    except (FileNotFoundError, pd.errors.EmptyDataError):
        df_updated = df_new

    # 日付昇順でソート
    df_updated.sort_values(by="date", inplace=True)
    
    # 列順を標準化 (date, ai_news_count, ai_news_titles)
    valid_cols = ['date', 'ai_news_count', 'ai_news_titles']
    df_updated = df_updated[[c for c in valid_cols if c in df_updated.columns]]
    
    df_updated.to_csv(CSV_FILENAME, index=False, encoding="utf-8-sig")
    print(f"\nCSV構造を更新し、'{CSV_FILENAME}' に保存完了しました。")

if __name__ == "__main__":
    rebuild_and_clean_csv()