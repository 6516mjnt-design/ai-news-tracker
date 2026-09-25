import datetime
import urllib.parse
import feedparser
import pandas as pd

PAPERS = {
    "nikkei": "nikkei.com"
}

# 条件を緩和：AI関連用語のみで幅広くヒットさせる（「新モデル」「発表」などの限定を解除）
KEYWORDS = '(OpenAI OR ChatGPT OR Gemini OR Claude OR Copilot OR Meta OR Anthropic OR "生成AI" OR "LLM") -株 -市況 -PR -プレスリリース -無料'
CSV_FILENAME = "ai_news_stats.csv"
RETENTION_DAYS = 30  # 30日分保持

def get_google_news_rss(query: str):
    encoded_query = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ja&gl=JP&ceid=JP:ja"
    return feedparser.parse(url)

def fetch_stats_for_date(target_date_str: str, domain: str):
    """指定した日付（target_date_str: YYYY-MM-DD）の翌日基準でニュースを取得"""
    # 日付から1日前の文字列を計算（after:用）
    dt = datetime.datetime.strptime(target_date_str, "%Y-%m-%d")
    after_date_str = (dt - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    
    search_query = f"{KEYWORDS} site:{domain} after:{after_date_str}"
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
        "nikkei_count": article_count,
        "nikkei_titles": formatted_titles
    }

def collect_and_rebuild_stats():
    # 日本時間（JST）で今日と昨日の日付を取得
    jst_now = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=9)
    today_str = jst_now.strftime("%Y-%m-%d")
    yesterday_str = (jst_now - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    
    domain = PAPERS["nikkei"]
    
    # 昨日（24日）と今日（25日）のデータを同じ最新条件で再取得して基準を統一
    print(f"・[再集計] {yesterday_str} のデータを集計中...")
    stats_yesterday = fetch_stats_for_date(yesterday_str, domain)
    
    print(f"・[再集計] {today_str} のデータを集計中...")
    stats_today = fetch_stats_for_date(today_str, domain)
    
    new_rows = [stats_yesterday, stats_today]
    df_new = pd.DataFrame(new_rows)
    
    try:
        df_existing = pd.read_csv(CSV_FILENAME, dtype=str)
        # 不要な過去列の除去
        unwanted_cols = [col for col in df_existing.columns if 'sankei' in col]
        if unwanted_cols:
            df_existing.drop(columns=unwanted_cols, inplace=True)
            
        # 再取得対象の日付（昨日・今日）の既存行を除去
        target_dates = [today_str, yesterday_str]
        df_existing = df_existing[~df_existing['date'].astype(str).isin(target_dates)].copy()
        
        df_updated = pd.concat([df_existing, df_new], ignore_index=True)
    except (FileNotFoundError, pd.errors.EmptyDataError):
        df_updated = df_new

    # 日付で昇順ソートして列順を整形
    df_updated.sort_values(by="date", inplace=True)
    valid_cols = ['date', 'nikkei_count', 'nikkei_titles']
    df_updated = df_updated[[c for c in valid_cols if c in df_updated.columns]]
    
    df_updated.to_csv(CSV_FILENAME, index=False, encoding="utf-8-sig")
    print(f"\n基準を統一した集計データを '{CSV_FILENAME}' に保存・更新完了しました。")

if __name__ == "__main__":
    collect_and_rebuild_stats()