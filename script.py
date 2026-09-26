import datetime
import urllib.parse
import os
import feedparser
import pandas as pd

KEYWORDS = '(OpenAI OR ChatGPT OR Gemini OR Claude OR Copilot OR Meta OR Anthropic OR "生成AI" OR "LLM") -株 -市況 -PR -プレスリリース -無料'
CSV_FILENAME = "ai_news_stats.csv"
RETENTION_DAYS = 30  # 30日分保持

def get_google_news_rss(query: str):
    encoded_query = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ja&gl=JP&ceid=JP:ja"
    return feedparser.parse(url)

def fetch_news_for_date(target_date_str: str):
    """指定日のニュースを取得し、タイトルと情報源（メディア名）に分離"""
    dt = datetime.datetime.strptime(target_date_str, "%Y-%m-%d")
    after_date_str = (dt - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    
    search_query = f"{KEYWORDS} after:{after_date_str}"
    feed = get_google_news_rss(search_query)
    
    raw_titles = [entry.title for entry in feed.entries]
    unique_titles = list(dict.fromkeys(raw_titles))
    
    news_list = []
    for raw in unique_titles:
        if " - " in raw:
            title_part, source_part = raw.rsplit(" - ", 1)
        else:
            title_part = raw
            source_part = "不明"
            
        news_list.append({
            "date": target_date_str,
            "news_title": title_part,
            "news_source": source_part
        })
    return news_list

def rebuild_and_collect_all_news():
    jst_now = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=9)
    today_str = jst_now.strftime("%Y-%m-%d")
    yesterday_str = (jst_now - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    day_before_yesterday_str = (jst_now - datetime.timedelta(days=2)).strftime("%Y-%m-%d")
    
    # 9月24日、9月25日、本日（9月26日以降）のデータをすべて新しい構造で再取得
    all_new_data = []
    for target_date in [day_before_yesterday_str, yesterday_str, today_str]:
        daily_items = fetch_news_for_date(target_date)
        all_new_data.extend(daily_items)
        print(f"・{target_date} 分: {len(daily_items)} 件取得（タイトル・情報源を分離）")
        
    df_new = pd.DataFrame(all_new_data)
    
    # 既存のCSVがある場合、今回再構築した日付（過去3日分）以外の旧データを引き継ぐ
    if os.path.exists(CSV_FILENAME):
        try:
            df_existing = pd.read_csv(CSV_FILENAME, dtype=str)
            if 'date' in df_existing.columns:
                df_existing['date'] = pd.to_datetime(df_existing['date'], errors='coerce').dt.strftime('%Y-%m-%d')
                target_dates = [day_before_yesterday_str, yesterday_str, today_str]
                # 今回更新する日付を除外して残りの過去データを保持
                df_existing = df_existing[~df_existing['date'].isin(target_dates)].copy()
                
                # 必要な列（date, news_title, news_source）のみ残す
                valid_cols = ['date', 'news_title', 'news_source']
                df_existing = df_existing[[c for c in valid_cols if c in df_existing.columns]]
                df_updated = pd.concat([df_existing, df_new], ignore_index=True)
            else:
                df_updated = df_new
        except Exception:
            df_updated = df_new
    else:
        df_updated = df_new

    # 保持期間（30日）を過ぎた古いデータを削除
    df_updated['date_dt'] = pd.to_datetime(df_updated['date'], errors='coerce')
    cutoff_date = datetime.datetime.now() - datetime.timedelta(days=RETENTION_DAYS)
    df_filtered = df_updated[df_updated['date_dt'] >= cutoff_date].copy()
    df_filtered.drop(columns=['date_dt'], inplace=True)

    # 日付昇順・情報源順で整列
    df_filtered.sort_values(by=["date", "news_source"], inplace=True)
    df_filtered = df_filtered[['date', 'news_title', 'news_source']]
    
    df_filtered.to_csv(CSV_FILENAME, index=False, encoding="utf-8-sig")
    print(f"\nCSV構造を『1行1ニュース（date, news_title, news_source）』へ変更し、'{CSV_FILENAME}' に保存完了しました。")

if __name__ == "__main__":
    rebuild_and_collect_all_news()