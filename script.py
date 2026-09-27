import datetime
import urllib.parse
import os
import feedparser
import pandas as pd

# 対象キーワード群（RSSで誤作動を起こさないシンプル表記）
BASE_KEYWORDS = '生成AI OR 人工知能 OR OpenAI OR ChatGPT OR Gemini OR Claude OR Copilot OR LLM'

CSV_FILENAME = "ai_news_stats.csv"
RETENTION_DAYS = 30  # 30日分保持

def get_google_news_rss(query: str):
    encoded_query = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ja&gl=JP&ceid=JP:ja"
    return feedparser.parse(url)

def fetch_news():
    """Google ニュースRSSから確実に対象新聞社・主要メディアの記事を取得"""
    
    # 互換性を重視した個別クエリ（site: や過度な括弧を使わない）
    queries = [
        # 大手全国紙
        f"産経新聞 {BASE_KEYWORDS}",
        f"読売新聞 {BASE_KEYWORDS}",
        f"日本経済新聞 {BASE_KEYWORDS}",
        f"日経 {BASE_KEYWORDS}",
        f"朝日新聞 {BASE_KEYWORDS}",
        f"毎日新聞 {BASE_KEYWORDS}",
        # 主要IT・ビジネスメディア
        f"ITmedia {BASE_KEYWORDS}",
        f"Impress {BASE_KEYWORDS}",
        f"ASCII {BASE_KEYWORDS}",
        f"CNET {BASE_KEYWORDS}",
        # 全体補完クエリ
        f"生成AI OR 人工知能"
    ]
    
    raw_entries = []
    seen_titles = set()
    
    for q in queries:
        feed = get_google_news_rss(q)
        for entry in feed.entries:
            if entry.title not in seen_titles:
                seen_titles.add(entry.title)
                raw_entries.append(entry)
                
    news_list = []
    for entry in raw_entries:
        raw_title = entry.title
        
        # タイトルとソースの分離 ("記事タイトル - メディア名")
        if " - " in raw_title:
            title_part, source_part = raw_title.rsplit(" - ", 1)
        else:
            title_part = raw_title
            source_part = "不明"
            
        # 配信日時の取得（RSSの published_parsed から日付文字列を生成）
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            pub_date = datetime.datetime(*entry.published_parsed[:6]) + datetime.timedelta(hours=9) # JST補正
            date_str = pub_date.strftime("%Y-%m-%d")
        else:
            date_str = datetime.datetime.now().strftime("%Y-%m-%d")
            
        news_list.append({
            "date": date_str,
            "news_title": title_part,
            "news_source": source_part
        })
        
    return news_list

def rebuild_and_collect_all_news():
    print("ニュースデータの取得を開始します...")
    new_items = fetch_news()
    print(f"取得できたニュース総数（重複排除後）: {len(new_items)} 件")
    
    df_new = pd.DataFrame(new_items)
    
    if os.path.exists(CSV_FILENAME):
        try:
            df_existing = pd.read_csv(CSV_FILENAME, dtype=str)
            if 'date' in df_existing.columns and 'news_title' in df_existing.columns:
                # 既存データと新規データを結合して重複削除
                df_combined = pd.concat([df_existing, df_new], ignore_index=True)
                df_combined.drop_duplicates(subset=['date', 'news_title'], inplace=True)
            else:
                df_combined = df_new
        except Exception:
            df_combined = df_new
    else:
        df_combined = df_new

    # 直近30日分のデータのみ保持
    df_combined['date_dt'] = pd.to_datetime(df_combined['date'], errors='coerce')
    cutoff_date = datetime.datetime.now() - datetime.timedelta(days=RETENTION_DAYS)
    df_filtered = df_combined[df_combined['date_dt'] >= cutoff_date].copy()
    df_filtered.drop(columns=['date_dt'], inplace=True)

    df_filtered.sort_values(by=["date", "news_source"], ascending=[False, True], inplace=True)
    df_filtered = df_filtered[['date', 'news_title', 'news_source']]
    
    df_filtered.to_csv(CSV_FILENAME, index=False, encoding="utf-8-sig")
    print(f"\n'{CSV_FILENAME}' へ無事に更新・保存しました。")

if __name__ == "__main__":
    rebuild_and_collect_all_news()