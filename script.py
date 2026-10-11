import datetime
import os
import re
import unicodedata
import urllib.parse

import feedparser
import pandas as pd

# 保存先はスクリプトと同じフォルダ（実行場所に関係なく同じ場所）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "ai_news_v2.csv")
RETENTION_DAYS = 30
SEARCH_WINDOW = "when:7d"
COLUMNS = ["date", "news_title", "news_source"]

# ---------------------------------------------------------------
# 検索クエリ（Google News RSS）
# ---------------------------------------------------------------
AI_QUERY_JA = (
    '(生成AI OR 人工知能 OR オープンAI OR OpenAI OR ChatGPT OR '
    'アンソロピック OR Anthropic OR Claude OR ジェミニ OR Gemini OR LLM OR '
    'フィジカルAI OR 超知能 OR スーパーインテリジェンス OR "SIエージェント" OR '
    'AIエージェント OR ミュトス OR Mythos OR AI)'
)
GOV_QUERY_JA = (
    '(日本政府 OR 官邸 OR 首相 OR 内閣府 OR デジタル庁 OR 経産省 OR 経済産業省 OR '
    '総務省 OR 文科省 OR 審議会 OR AI規制 OR AI推進 OR AI戦略 OR AI法案)'
)
SECURITY_QUERY_JA = '(サイバー OR セキュリティ OR ハッカー OR ハッキング)'

AI_QUERY_EN = (
    '("Generative AI" OR "Artificial Intelligence" OR OpenAI OR ChatGPT OR '
    '"Google DeepMind" OR "Gemini AI" OR Anthropic OR "Claude AI" OR Copilot OR '
    '"Physical AI" OR Superintelligence OR "AI agent" OR Mythos)'
)
SECURITY_QUERY_EN = (
    '("cybersecurity" OR "cyber attack" OR "cyberattack" OR hacker OR hacking OR '
    '"security breach")'
)

QUERIES = [
    ("国内主要紙・NHK・通信社・専門紙",
     f"(日本経済新聞 OR 日経 OR 読売新聞 OR 朝日新聞 OR 毎日新聞 OR 産経新聞 OR NHK OR ロイター OR "
     f"ブルームバーグ OR 日経ビジネス OR 日経クロステック OR ITmedia OR 時事通信 OR 共同通信) AND {AI_QUERY_JA} {SEARCH_WINDOW}",
     "ja", "JP", "JP:ja"),
    ("日本政府・政策",
     f"{GOV_QUERY_JA} AND {AI_QUERY_JA} {SEARCH_WINDOW}",
     "ja", "JP", "JP:ja"),
    ("日本語のAI×セキュリティ",
     f"{SECURITY_QUERY_JA} AND {AI_QUERY_JA} {SEARCH_WINDOW}",
     "ja", "JP", "JP:ja"),
    ("米英メディア・専門紙",
     f"(CNN OR Reuters OR AP OR Bloomberg OR \"Wall Street Journal\" OR \"New York Times\" OR "
     f"\"Washington Post\" OR \"NBC News\" OR \"ABC News\" OR \"CBS News\" OR BBC OR "
     f"\"Financial Times\" OR Guardian OR Telegraph OR Independent OR Axios OR CNBC OR "
     f"TechCrunch OR \"The Verge\" OR Wired OR \"Hacker News\") AND {AI_QUERY_EN} {SEARCH_WINDOW}",
     "en-US", "US", "US:en"),
    ("海外のAI×セキュリティ",
     f"{SECURITY_QUERY_EN} AND {AI_QUERY_EN} {SEARCH_WINDOW}",
     "en-US", "US", "US:en"),
]

# 許可する媒体名（部分一致・大文字小文字無視）。
# 取得結果の「除外された媒体」を実行ログに出すので、必要に応じて追加してください。
ALLOWED_SOURCES = [
    # 日本
    "日本経済新聞", "日経", "読売新聞", "朝日新聞", "毎日新聞", "産経", "NHK",
    "ロイター", "Reuters", "ブルームバーグ", "Bloomberg", "時事", "共同通信",
    "ITmedia", "日経ビジネス", "日経クロステック", "Japan Times", "CNN.co.jp", "CNN.jp",
    # 米国
    "CNN", "Associated Press", "AP News", "Wall Street Journal", "The New York Times",
    "The Washington Post", "NBC News", "ABC News", "CBS News", "CNBC", "Axios",
    "TechCrunch", "The Verge", "Wired", "The Hacker News", "CyberScoop", "BankInfoSecurity",
    # 英国
    "BBC", "Financial Times", "The Guardian", "The Telegraph", "The Independent",
]

# AI関連判定（NFKC正規化後のタイトル＋概要に対して判定）
AI_PATTERN = re.compile(
    r"(生成AI|人工知能|超知能|スーパーインテリジェンス|フィジカルAI|"
    r"(?<![A-Za-z])AI(?![A-Za-z])|OpenAI|オープンAI|ChatGPT|"
    r"Anthropic|アンソロピック|(?<![A-Za-z])Claude(?![A-Za-z])|"
    r"ジェミニ|Gemini|(?<![A-Za-z])LLM|Copilot|Superintelligence|Physical AI|"
    r"Artificial Intelligence|Generative AI|ミュトス|Mythos|SIエージェント|"
    r"(?<![A-Za-z])SI(?![A-Za-z]))",
    re.IGNORECASE,
)


def nfkc(text: str) -> str:
    """全角英数字（ＡＩ等）を半角に揃える"""
    return unicodedata.normalize("NFKC", text or "")


def get_google_news_rss(query: str, hl: str, gl: str, ceid: str):
    encoded = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl={hl}&gl={gl}&ceid={ceid}"
    return feedparser.parse(url)


def clean_title(raw: str) -> str:
    """末尾の媒体名（「 - X」「 | X」「（X）」）を除去する"""
    title = nfkc(raw)
    title = re.sub(r"\s+[-–|]\s+[^-–|]+$", "", title)
    title = re.sub(r"\s*[(（][^()（）]+[)）]\s*$", "", title)
    return title.strip()


def source_name(entry) -> str:
    src = getattr(entry, "source", None)
    if src and getattr(src, "title", None):
        return src.title.strip()
    m = re.search(r"(?:\s[-–|]\s|[(（])([^-–|()（）]+)[)）]?\s*$", nfkc(entry.title))
    return m.group(1).strip() if m else "不明"


def is_allowed_source(name: str) -> bool:
    low = name.lower()
    return any(allowed.lower() in low for allowed in ALLOWED_SOURCES)


def is_ai_related(entry) -> bool:
    text = nfkc(f"{entry.title} {getattr(entry, 'summary', '')}")
    return bool(AI_PATTERN.search(text))


def normalize_key(title: str) -> str:
    return re.sub(r"[\s\W_]+", "", nfkc(title)).lower()


def fetch_news():
    raw_entries = []
    print("== 取得状況 ==")
    for name, query, hl, gl, ceid in QUERIES:
        feed = get_google_news_rss(query, hl, gl, ceid)
        n = len(feed.entries)
        if feed.bozo and not n:
            status = f"エラー: {feed.get('bozo_exception')}"
        else:
            status = "OK" if n else "0件"
        print(f"  {name}: {n}件 ({status})")
        raw_entries.extend(feed.entries)
    print(f"取得総数（重複前）: {len(raw_entries)} 件")

    rows, seen = [], set()
    excluded_sources = {}
    dropped_ai = 0
    for entry in raw_entries:
        source = source_name(entry)
        if not is_allowed_source(source):
            excluded_sources[source] = excluded_sources.get(source, 0) + 1
            continue
        if not is_ai_related(entry):
            dropped_ai += 1
            continue

        title = clean_title(entry.title)
        key = normalize_key(title)
        if not key or key in seen:
            continue
        seen.add(key)

        if getattr(entry, "published_parsed", None):
            pub = datetime.datetime(*entry.published_parsed[:6]) + datetime.timedelta(hours=9)
            date_str = pub.strftime("%Y-%m-%d")
        else:
            date_str = datetime.datetime.now().strftime("%Y-%m-%d")

        rows.append({"date": date_str, "news_title": title, "news_source": source})

    print(f"AI関連でないため除外: {dropped_ai} 件")
    print("許可外の媒体（件数の多い順・上位15）:")
    for src, cnt in sorted(excluded_sources.items(), key=lambda x: -x[1])[:15]:
        print(f"  {cnt:>4}件  {src}")
    return rows


def load_existing() -> pd.DataFrame:
    """既存CSVを読み込み、蓄積を継続する（これがないと毎回上書きで過去の日が消える）"""
    if not os.path.exists(CSV_PATH):
        return pd.DataFrame(columns=COLUMNS)
    try:
        df = pd.read_csv(CSV_PATH, dtype=str, encoding="utf-8-sig")
        if not set(COLUMNS).issubset(df.columns):
            print("既存CSVの列が想定と違うため、新規に作成します。")
            return pd.DataFrame(columns=COLUMNS)
        return df[COLUMNS]
    except Exception as e:
        print(f"既存CSVの読み込みに失敗（新規作成します）: {e}")
        return pd.DataFrame(columns=COLUMNS)


def rebuild_and_collect_all_news():
    print("AI関連ニュースの取得を開始します...")
    new_rows = fetch_news()
    print(f"今回取得分（重複排除後）: {len(new_rows)} 件")

    df_new = pd.DataFrame(new_rows, columns=COLUMNS)
    df_old = load_existing()
    print(f"既存の蓄積分: {len(df_old)} 行")

    df = pd.concat([df_old, df_new], ignore_index=True)
    df["_key"] = df["news_title"].fillna("").map(normalize_key)
    df.drop_duplicates(subset=["date", "_key"], keep="last", inplace=True)
    df.drop(columns=["_key"], inplace=True)

    df["date_dt"] = pd.to_datetime(df["date"], errors="coerce")
    cutoff = datetime.datetime.now() - datetime.timedelta(days=RETENTION_DAYS)
    df = df[df["date_dt"] >= cutoff].drop(columns=["date_dt"])

    df.sort_values(by=["date", "news_source"], ascending=[False, True], inplace=True)
    df.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")
    print(f"保存しました: {CSV_PATH}（{len(df)} 行）")


if __name__ == "__main__":
    rebuild_and_collect_all_news()
