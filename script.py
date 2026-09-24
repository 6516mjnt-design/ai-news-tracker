import datetime
import os
import urllib.parse
import feedparser
import pandas as pd

PAPERS = {
    "nikkei": "nikkei.com",
    "asahi": "asahi.com",
    "yomiuri": "yomiuri.co.jp",
    "mainichi": "mainichi.jp",
    "sankei": "sankei.com"
}

# 検索キーワード
KEYWORDS = '(intitle:"AI" OR intitle:人工知能 OR intitle:生成AI OR intitle:ChatGPT) -intitle:株 -intitle:市況'
CSV_FILENAME = "ai_news_stats.csv"

def get_google_news_rss(query: str):
    encoded_query = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ja&gl=JP&ceid=JP:ja"
    return feedparser.parse(url)

def get_last_recorded_date(filename: str) -> datetime.date:
    """CSVから最終記録日を取得する。ファイルがない場合は7日前を返す。"""
    if os.path.exists(filename):
        try:
            df = pd.read_csv(filename)
            if not df.empty and "date" in df.columns:
                last_date_str = str(df["date"].iloc[-1]).strip()
                # YYYY-MM-DD または YYYY/MM/DD の両方に対応
                last_date_str = last_date_str.replace("/", "-")
                return datetime.datetime.strptime(last_date_str, "%Y-%m-%d").date()
        except Exception as e:
            print(f"CSV読み込み警告: {e}")
    
    # ファイルがない、または空の場合は最大さかのぼり期間（7日前）を返す
    return datetime.date.today() - datetime.timedelta(days=7)

def collect_stats_for_date(target_date: datetime.date) -> dict:
    """指定された日付（1日分）のニュース件数を集計する"""
    date_str = target_date.strftime("%Y-%m-%d")
    next_date_str = (target_date + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    
    print(f"\n--- 【{date_str}】のデータ取得中 ---")
    results = {"date": date_str}

    # Google News RSS 用の日付範囲指定 (after:開始日 before:終了日)
    time_filter = f"after:{date_str} before:{next_date_str}"

    for paper_key, domain in PAPERS.items():
        search_query = f"{KEYWORDS} site:{domain} {time_filter}"
        feed = get_google_news_rss(search_query)
        article_count = len(feed.entries)
        results[paper_key] = article_count
        print(f"・{paper_key} ({domain}): {article_count} 件")

    return results

def append_to_csv(new_records: list, filename: str = CSV_FILENAME):
    """取得した複数の日次データをCSVへ追記・保存する"""
    if not new_records:
        return

    df_new = pd.DataFrame(new_records)
    
    if os.path.exists(filename):
        try:
            df_existing = pd.read_csv(filename)
            df_updated = pd.concat([df_existing, df_new], ignore_index=True)
            df_updated.drop_duplicates(subset=["date"], keep="last", inplace=True)
        except (FileNotFoundError, pd.errors.EmptyDataError):
            df_updated = df_new
    else:
        df_updated = df_new
        
    df_updated.to_csv(filename, index=False, encoding="utf-8-sig")
    print(f"\n集計データを '{filename}' に保存しました。")

def main():
    today = datetime.date.today()
    last_date = get_last_recorded_date(CSV_FILENAME)
    
    # 取得対象日（最終記録日の翌日 ～ 今日）を算出
    start_date = last_date + datetime.timedelta(days=1)
    
    # 1週間（7日前）より古い場合は最大7日前からスタート
    max_lookback_date = today - datetime.timedelta(days=7)
    if start_date < max_lookback_date:
        start_date = max_lookback_date

    if start_date > today:
        print("最新のデータまで取得済みです。更新はありません。")
        return

    print(f"最終記録日: {last_date}")
    print(f"未取得期間: {start_date} ～ {today} のデータを自動補填します。")

    new_records = []
    current_date = start_date
    while current_date <= today:
        stats = collect_stats_for_date(current_date)
        new_records.append(stats)
        current_date += datetime.timedelta(days=1)

    append_to_csv(new_records)

if __name__ == "__main__":
    main()