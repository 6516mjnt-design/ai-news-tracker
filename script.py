import datetime
import os
import re
import urllib.parse

import feedparser
import pandas as pd

CSV_FILENAME = "ai_news_v2.csv"  # 旧CSVは廃却し、新規ファイルで蓄積を開始
RETENTION_DAYS = 30
SEARCH_WINDOW = "when:7d"

# ---------------------------------------------------------------
# 検索クエリ（Google News RSS）
#   ※ source:"..." 演算子はRSSで効きにくいため使わず、
#     媒体名は取得後に entry.source.title で判定する
# ---------------------------------------------------------------
AI_QUERY_JA = (
    '(生成AI OR 人工知能 OR オープンAI OR OpenAI OR ChatGPT OR '
    'アンソロピック OR Anthropic OR "Claude AI" OR "Gemini AI" OR LLM OR '
    'フィジカルAI OR 超知能 OR "SIエージェント" OR "AIエージェント")'
)
GOV_QUERY_JA = (
    '(日本政府 OR 官邸 OR 首相 OR 内閣府 OR デジタル庁 OR 経産省 OR 経済産業省 OR '
    '総務省 OR 文科省 OR 審議会 OR AI規制 OR AI推進 OR AI戦略 OR AI法案)'
)
SECURITY_QUERY_JA = '(サイバー OR セキュリティ OR ハッカー OR ハッキング)'

AI_QUERY_EN = (
    '("Generative AI" OR "Artificial Intelligence" OR OpenAI OR ChatGPT OR '
    '"Google DeepMind" OR "Gemini AI" OR Anthropic OR "Claude AI" OR Copilot OR '
    '"Physical AI" OR Superintelligence OR "AI agent")'
)
SECURITY_QUERY_EN = (
    '("cybersecurity" OR "cyber attack" OR "cyberattack" OR hacker OR hacking OR '
    '"security breach")'
)

# 検索クエリ一覧: (クエリ文字列, hl, gl, ceid)
QUERIES = [
    # 日本国内（主要紙・NHK・通信社）
    (f"(日本経済新聞 OR 日経 OR 読売新聞 OR 朝日新聞 OR 毎日新聞 OR 産経新聞 OR NHK OR ロイター OR ブルームバーグ) AND {AI_QUERY_JA} {SEARCH_WINDOW}", "ja", "JP", "JP:ja"),
    # 日本政府・政策
    (f"{GOV_QUERY_JA} AND {AI_QUERY_JA} {SEARCH_WINDOW}", "ja", "JP", "JP:ja"),
    # 日本語のAI×セキュリティ
    (f"{SECURITY_QUERY_JA} AND {AI_QUERY_JA} {SEARCH_WINDOW}", "ja", "JP", "JP:ja"),
    # 米国・英国・海外メディア（媒体名は取得後に判定）
    (f"(CNN OR Reuters OR AP OR Bloomberg OR \"Wall Street Journal\" OR \"New York Times\" OR "
     f"\"Washington Post\" OR \"NBC News\" OR \"ABC News\" OR \"CBS News\" OR BBC OR "
     f"\"Financial Times\" OR Guardian OR Telegraph OR Independent) AND {AI_QUERY_EN} {SEARCH_WINDOW}",
     "en-US", "US", "US:en"),
    # 海外のAI×セキュリティ
    (f"{SECURITY_QUERY_EN} AND {AI_QUERY_EN} {SEARCH_WINDOW}", "en-US", "US", "US:en"),
]

# 許可する媒体名（entry.source.title に部分一致で判定、大文字小文字無視）
ALLOWED_SOURCES = [
    # 日本
    "日本経済新聞", "日経", "読売新聞", "朝日新聞", "毎日新聞", "産経", "NHK",
    "ロイター", "Reuters", "ブルームバーグ", "Bloomberg",
    # 米国
    "CNN", "Associated Press", "AP News", "Bloomberg", "Wall Street Journal",
    "The New York Times", "The Washington Post", "NBC News", "ABC News", "CBS News",
    # 英国
    "BBC", "Financial Times", "The Guardian", "The Telegraph", "The Independent",
]

# AI関連判定（タイトル＋概要）。英字は前後が英字でない場合のみ一致させ、
# 「生成AI」など日本語に隣接する表記も拾う
AI_PATTERN = re.compile(
    r"(生成AI|人工知能|超知能|フィジカルAI|(?<![A-Za-z])AI(?![A-Za-z])|OpenAI|ChatGPT|"
    r"Anthropic|アンソロピック|(?<![A-Za-z])Claude(?![A-Za-z])|Gemini|(?<![A-Za-z])LLM|"
    r"Copilot|Superintelligence|Physical AI|アンソロピック|オープンAI|オープンＡＩ|"
    r"Artificial Intelligence|Generative AI)",
    re.IGNORECASE,
)


def get_google_news_rss(query: str, hl: str, gl: str, ceid: str):
    encoded = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl={hl}&gl={gl}&ceid={ceid}"
    return feedparser.parse(url)


def clean_title(raw: str) -> str:
    """末尾の媒体名（「 - X」「 | X」「（X）」）を除去する"""
    title = raw
    title = re.sub(r"\s+[-–|｜]\s+[^-–|｜]+$", "", title)
    title = re.sub(r"\s*[（(][^（()）]+[)）]\s*$", "", title)
    return title.strip()


def source_name(entry) -> str:
    src = getattr(entry, "source", None)
    if src and getattr(src, "title", None):
        return src.title.strip()
    # フォールバック: タイトル末尾から推定
    m = re.search(r"(?:\s[-–|｜]\s|[（(])([^-–|｜（()）]+)[)）]?\s*$", entry.title)
    return m.group(1).strip() if m else "不明"


def is_allowed_source(name: str) -> bool:
    low = name.lower()
    return any(allowed.lower() in low for allowed in ALLOWED_SOURCES)


def is_ai_related(entry) -> bool:
    text = f"{entry.title} {getattr(entry, 'summary', '')}"
    return bool(AI_PATTERN.search(text))


def normalize_key(title: str) -> str:
    """重複判定用：空白・記号・大文字小文字を揃える"""
    return re.sub(r"[\s\W_]+", "", title).lower()


def fetch_news():
    raw_entries = []
    for query, hl, gl, ceid in QUERIES:
        feed = get_google_news_rss(query, hl, gl, ceid)
        raw_entries.extend(feed.entries)

    rows = []
    seen = set()
    for entry in raw_entries:
        source = source_name(entry)
        if not is_allowed_source(source):
            continue
        if not is_ai_related(entry):
            continue

        title = clean_title(entry.title)
        key = normalize_key(title)
        if key in seen:
            continue
        seen.add(key)

        if getattr(entry, "published_parsed", None):
            # 配信日時はUTCなので日本時間(+9h)に補正
            pub = datetime.datetime(*entry.published_parsed[:6]) + datetime.timedelta(hours=9)
            date_str = pub.strftime("%Y-%m-%d")
        else:
            date_str = datetime.datetime.now().strftime("%Y-%m-%d")

        rows.append({"date": date_str, "news_title": title, "news_source": source})

    return rows


def rebuild_and_collect_all_news():
    print("AI関連ニュースの取得を開始します...")
    rows = fetch_news()
    print(f"AI関連かつ許可媒体の記事: {len(rows)} 件（重複排除後）")

    df = pd.DataFrame(rows, columns=["date", "news_title", "news_source"])

    # 直近30日分のみ保持（既存CSVは読み込まない）
    df["date_dt"] = pd.to_datetime(df["date"], errors="coerce")
    cutoff = datetime.datetime.now() - datetime.timedelta(days=RETENTION_DAYS)
    df = df[df["date_dt"] >= cutoff].drop(columns=["date_dt"])

    df.sort_values(by=["date", "news_source"], ascending=[False, True], inplace=True)
    df.to_csv(CSV_FILENAME, index=False, encoding="utf-8-sig")
    print(f"'{CSV_FILENAME}' に保存しました（{len(df)} 行）。")


if __name__ == "__main__":
    rebuild_and_collect_all_news()
