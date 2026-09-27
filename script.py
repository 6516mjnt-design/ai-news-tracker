import datetime
import urllib.parse
import os
import feedparser
import pandas as pd

# 日本語キーワード
BASE_KEYWORDS_JA = '生成AI OR 人工知能 OR オープンAI OR OpenAI OR ChatGPT OR グーグル OR Google OR Gemini OR アンソロピック OR Anthropic OR Claude OR Copilot OR LLM OR フィジカルAI OR "Physical AI"'

# 英語キーワード（海外本国用）
BASE_KEYWORDS_EN = '"Generative AI" OR "Artificial Intelligence" OR OpenAI OR ChatGPT OR Google OR Gemini OR Anthropic OR Claude OR Copilot OR "Physical AI"'

CSV_FILENAME = "ai_news_stats.csv"
RETENTION_DAYS = 30  # 30日分保持

def get_google_news_rss(query: str, hl='ja', gl='JP', ceid='JP:ja'):
    encoded_query = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl={hl}&gl={gl}&ceid={ceid}"
    return feedparser.parse(url)

def fetch_news():
    """日米英の主要メディアに絞ってニュースを確実に取得"""
    raw_entries = []
    seen_titles = set()

    def add_entries(feed):
        for entry in feed.entries:
            if entry.title not in seen_titles:
                seen_titles.add(entry.title)
                raw_entries.append(entry)

    # 1. 日本国内 主要5紙 ＋ NHK（日本語設定）
    queries_ja = [
        f"日本経済新聞 OR 日経 {BASE_KEYWORDS_JA}",
        f"読売新聞 {BASE_KEYWORDS_JA}",
        f"朝日新聞 {BASE_KEYWORDS_JA}",
        f"毎日新聞 {BASE_KEYWORDS_JA}",
        f"産経新聞 {BASE_KEYWORDS_JA}",
        f"NHK OR NHKニュース {BASE_KEYWORDS_JA}",
        # 海外メディアの日本語版記事（CNN Japan, BBC Japan等）
        f"CNN {BASE_KEYWORDS_JA}",
        f"BBC {BASE_KEYWORDS_JA}",
        f"ロイター {BASE_KEYWORDS_JA}",
        f"ブルームバーグ {BASE_KEYWORDS_JA}"
    ]
    for q in queries_ja:
        feed = get_google_news_rss(q, hl='ja', gl='JP', ceid='JP:ja')
        add_entries(feed)

    # 2. 米国主要メディア（米国・英語設定 + source演算子）
    us_sources = [
        'source:"CNN"',
        'source:"Reuters"',
        'source:"Associated Press"',
        'source:"Bloomberg"',
        'source:"The Wall Street Journal"',
        'source:"The New York Times"',
        'source:"The Washington Post"',
        'source:"NBC News"',
        'source:"ABC News"',
        'source:"CBS News"'
    ]
    for src in us_sources:
        q = f"{src} AND ({BASE_KEYWORDS_EN})"
        feed = get_google_news_rss(q, hl='en-US', gl='US', ceid='US:en')
        add_entries(feed)

    # 3. 英国主要メディア（英国・英語設定 + source演算子）
    uk_sources = [
        'source:"BBC"',
        'source:"Financial Times"',
        'source:"The Guardian"',
        'source:"The Telegraph"',
        'source:"The Independent"'
    ]
    for src in uk_sources:
        q = f"{src} AND ({BASE_KEYWORDS_EN})"
        feed = get_google_news_rss(q, hl='en-GB', gl='GB', ceid='GB:en')
        add_entries(feed)

    news_list = []
    for entry in raw_entries:
        raw_title = entry.title
        
        # タイトルとソースの分離 ("記事タイトル - メディア名")
        if " - " in raw_title:
            title_part, source_part = raw_title.rsplit(" - ", 1)
        else:
            title_part = raw_title
            source_part = "不明"
            
        # 配信日時の取得（JST補正）
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            pub_date = datetime.datetime(*entry.published_parsed[:6]) + datetime.timedelta(hours=9)
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
    print("日米英主要メディアからのニュース取得を開始します...")
    new_items = fetch_news()
    print(f"取得出来たニュース総数（重複排除後）: {len(new_items)} 件")
    
    df_new = pd.DataFrame(new_items)
    
    if os.path.exists(CSV_FILENAME):
        try:
            df_existing = pd.read_csv(CSV_FILENAME, dtype=str)
            if 'date' in df_existing.columns and 'news_title' in df_existing.columns:
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