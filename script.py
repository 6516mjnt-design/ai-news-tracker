import datetime
import urllib.parse
import feedparser
import pandas as pd

# 対象メディア
PAPERS = {
    "nikkei": "nikkei.com"
}

# 主要AI企業・モデルに特化＋ノイズ除外の検索クエリ
# (日経新聞内の重要AIニュースに厳選)
KEYWORDS = '(OpenAI OR ChatGPT OR Gemini OR Claude OR Copilot OR Meta OR Anthropic) (intitle:"新モデル" OR intitle:"新機能" OR intitle:"発表" OR intitle:"リリース" OR intitle:"公開") -intitle:株 -intitle:市況 -intitle:PR -intitle:プレスリリース -intitle:無料 -intitle:診断'
CSV_FILENAME = "ai_news_stats.csv"

def get_google_news_rss(query: str):
    encoded_query = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ja&gl=JP&ceid=JP:ja"
    return feedparser.parse(url)

def collect_daily_ai_stats():
    today = datetime.date.today().strftime("%Y-%m-%d")
    domain = PAPERS["nikkei"]
    
    # site:nikkei.com を確実に適用
    search_query = f"{KEYWORDS} site:{domain} when:1d"
    
    feed = get_google_news_rss(search_query)
    
    # 重複タイトルを除外して取得
    raw_titles = [entry.title for entry in feed.entries]
    unique_titles = list(dict.fromkeys(raw_titles))
    article_count = len(unique_titles)
    
    # 改行で縦に綺麗に並べる（番号付き）
    if unique_titles:
        formatted_titles = "\n".join([f"{i+1}. {t}" for i, t in enumerate(unique_titles)])
    else:
        formatted_titles = "なし"
    
    results = {
        "date": today,
        "nikkei_count": article_count,
        "nikkei_titles": formatted_titles
    }
    
    print(f"・日本経済新聞 ({domain}): {article_count} 件")
    if unique_titles:
        print("  タイトル:")
        for t in unique_titles:
            print(f"   - {t}")

    return results

def save_to_csv(data_dict, filename=CSV_FILENAME):
    df_new = pd.DataFrame([data_dict])
    
    try:
        df_existing = pd.read_csv(filename)
        # 既存列を整理して更新
        df_updated = pd.concat([df_existing, df_new], ignore_index=True)
        df_updated.drop_duplicates(subset=["date"], keep="last", inplace=True)
    except (FileNotFoundError, pd.errors.EmptyDataError):
        df_updated = df_new
        
    df_updated.to_csv(filename, index=False, encoding="utf-8-sig")
    print(f"\n集計データを '{filename}' に保存しました。")

if __name__ == "__main__":
    stats = collect_daily_ai_stats()
    save_to_csv(stats)