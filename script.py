import datetime
import urllib.parse
import os
import feedparser
import pandas as pd

# 対象キーワード群
BASE_KEYWORDS = '(OpenAI OR ChatGPT OR Gemini OR Claude OR Copilot OR Meta OR Anthropic OR "生成AI" OR "LLM")'

# 日本の主要メディア・大手新聞社を優先指定（産経新聞・読売新聞を明記）
MEDIA_KEYWORDS = '("日本経済新聞" OR "日経" OR "読売新聞" OR "読売" OR "産経新聞" OR "産経" OR "産経ニュース" OR "朝日新聞" OR "毎日新聞" OR "ITmedia" OR "Impress" OR "ASCII" OR "CNET" OR "ZDNET" OR "ビジネス+IT" OR "Ledge.ai")'

# 不要なノイズ・PR・海外自動翻訳メディアの除外リスト
EXCLUDE_KEYWORDS = '-株 -市況 -PR -プレスリリース -無料 -Межа -디지털투데이 -TradingKey -Unite.AI -Pasquale'

CSV_FILENAME = "ai_news_stats.csv"
RETENTION_DAYS = 30  # 30日分保持

def get_google_news_rss(query: str):
    encoded_query = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ja&gl=JP&ceid=JP:ja"
    return feedparser.parse(url)

def fetch_news_for_date(target_date_str: str):
    """指定日のニュースを取得（大手新聞・主要メディア優先 ＋ 全体枠）"""
    dt = datetime.datetime.strptime(target_date_str, "%Y-%m-%d")
    after_date_str = (dt - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    
    # 検索クエリ1：大手新聞・主要メディア指定のAIニュース
    query_major = f"{BASE_KEYWORDS} AND {MEDIA_KEYWORDS} {EXCLUDE_KEYWORDS} after:{after_date_str}"
    
    # 検索クエリ2：一般的なAIニュース（ノイズ除外適用）
    query_general = f"{BASE_KEYWORDS} {EXCLUDE_KEYWORDS} after:{after_date_str}"
    
    feed_major = get_google_news_rss(query_major)
    feed_general = get_google_news_rss(query_general)
    
    # 大手新聞・主要メディアを先に配置し、全体枠を後ろに結合（優先配置）
    all_entries = feed_major.entries + feed_general.entries
    
    raw_titles = []
    seen_titles = set()
    for entry in all_entries:
        if entry.title not in seen_titles:
            seen_titles.add(entry.title)
            raw_titles.append(entry.title)
            
    news_list = []
    for raw in raw_titles[:100]:  # 1日あたり最大100件
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
    
    all_new_data = []
    for target_date in [day_before_yesterday_str, yesterday_str, today_str]:
        daily_items = fetch_news_for_date(target_date)
        all_new_data.extend(daily_items)
        print(f"・{target_date} 分: {len(daily_items)} 件取得（産経・読売等大手紙優先設定）")
        
    df_new = pd.DataFrame(all_new_data)
    
    if os.path.exists(CSV_FILENAME):
        try:
            df_existing = pd.read_csv(CSV_FILENAME, dtype=str)
            if 'date' in df_existing.columns:
                df_existing['date'] = pd.to_datetime(df_existing['date'], errors='coerce').dt.strftime('%Y-%m-%d')
                target_dates = [day_before_yesterday_str, yesterday_str, today_str]
                df_existing = df_existing[~df_existing['date'].isin(target_dates)].copy()
                
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

    df_filtered.sort_values(by=["date", "news_source"], inplace=True)
    df_filtered = df_filtered[['date', 'news_title', 'news_source']]
    
    df_filtered.to_csv(CSV_FILENAME, index=False, encoding="utf-8-sig")
    print(f"\n'{CSV_FILENAME}' へ更新完了しました。")

if __name__ == "__main__":
    rebuild_and_collect_all_news()