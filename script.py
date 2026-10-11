import datetime
import os
import re
import time
import unicodedata
import urllib.parse

import feedparser
import pandas as pd

# 保存先はスクリプトと同じフォルダ（実行場所に関係なく同じ場所）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "ai_news_v2.csv")
RETENTION_DAYS = 30
# 通常実行は直近7日。環境変数 BACKFILL=1 のときは直近30日を取得して欠けた日を補う
BACKFILL = os.environ.get("BACKFILL", "0") == "1"
SEARCH_WINDOW = "when:30d" if BACKFILL else "when:7d"
REQUEST_INTERVAL_SEC = 0.5  # 連続アクセスを避けるための待機
COLUMNS = ["date", "news_title", "news_source"]

# ---------------------------------------------------------------
# 検索クエリ（Google News RSS）
#   長いOR条件を1本にまとめると返却件数が偏るため、
#   キーワードごとに短いクエリへ分けて取得件数を増やす。
#   媒体の絞り込みは取得後に行う（ALLOWED_SOURCES）。
# ---------------------------------------------------------------
KEYWORDS_JA = [
    "生成AI", "人工知能", "AI", "オープンAI", "アンソロピック", "ChatGPT",
    "ジェミニ AI", "Claude AI", "AIエージェント", "フィジカルAI", "超知能",
    "スーパーインテリジェンス", "LLM", "AI規制", "AI法案", "AI 政府",
    "AI サイバー", "AI セキュリティ", "AI ハッキング", "AI 著作権",
]
KEYWORDS_EN = [
    "generative AI", "artificial intelligence", "AI", "OpenAI", "Anthropic",
    "ChatGPT", "Gemini AI", "Claude AI", "Microsoft Copilot", "AI agent",
    "superintelligence", "AI regulation", "AI cybersecurity", "AI hacking",
    "AI security breach", "Physical AI",
]

QUERIES = []
for kw in KEYWORDS_JA:
    QUERIES.append((f"JA: {kw}", f"{kw} {SEARCH_WINDOW}", "ja", "JP", "JP:ja"))
for kw in KEYWORDS_EN:
    QUERIES.append((f"US: {kw}", f"{kw} {SEARCH_WINDOW}", "en-US", "US", "US:en"))
    QUERIES.append((f"UK: {kw}", f"{kw} {SEARCH_WINDOW}", "en-GB", "GB", "GB:en"))

# 許可する媒体名（部分一致・大文字小文字無視）。
# 除外された媒体は実行ログに件数付きで出るので、必要に応じて追加してください。
ALLOWED_SOURCES = [
    # 日本
    "日本経済新聞", "日経", "読売新聞", "朝日新聞", "毎日新聞", "産経", "NHK",
    "ロイター", "Reuters", "ブルームバーグ", "Bloomberg", "時事", "共同通信",
    "ITmedia", "日経ビジネス", "日経クロステック", "Japan Times", "CNN.co.jp", "CNN.jp",
    "東洋経済", "ダイヤモンド", "JBpress", "ASCII", "インプレス", "Impress",
    # 米国
    "CNN", "Associated Press", "AP News", "Wall Street Journal", "The New York Times",
    "The Washington Post", "NBC News", "ABC News", "CBS News", "CNBC", "Axios",
    "TechCrunch", "The Verge", "Wired", "The Hacker News", "CyberScoop", "BankInfoSecurity",
    "Bloomberg.com", "Fortune", "Forbes", "Business Insider", "Politico",
    # 英国
    "BBC", "Financial Times", "The Guardian", "The Telegraph", "The Independent",
    "The Times", "Sky News", "The Stack",
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


# 表記揺れを統一する（左側に含まれる表記を右側の名称にまとめる）
SOURCE_ALIASES = [
    ("日経クロステック", "日経クロステック"),
    ("日経ビジネス", "日経ビジネス"),
    ("日本経済新聞", "日本経済新聞"),
    ("インプレス", "Impress Watch"),
    ("Impress", "Impress Watch"),
    ("ITmedia", "ITmedia"),
    ("NHK", "NHK"),
    ("時事", "時事通信"),
    ("産経", "産経新聞"),
    ("Forbes JAPAN", "Forbes JAPAN"),
    ("Business Insider Japan", "Business Insider Japan"),
    ("Business Insider", "Business Insider"),
    ("Bloomberg", "Bloomberg"),
    ("Reuters", "Reuters"),
    ("ロイター", "Reuters"),
    ("CNN", "CNN"),
    ("Politico", "Politico"),
    ("POLITICO", "Politico"),
]


def canonical_source(name: str) -> str:
    for pattern, canonical in SOURCE_ALIASES:
        if pattern.lower() in name.lower():
            return canonical
    return name


def source_name(entry) -> str:
    src = getattr(entry, "source", None)
    if src and getattr(src, "title", None):
        return canonical_source(src.title.strip())
    m = re.search(r"(?:\s[-–|]\s|[(（])([^-–|()（）]+)[)）]?\s*$", nfkc(entry.title))
    return canonical_source(m.group(1).strip()) if m else "不明"


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
    print("== 取得状況（クエリごと） ==")
    for name, query, hl, gl, ceid in QUERIES:
        feed = get_google_news_rss(query, hl, gl, ceid)
        n = len(feed.entries)
        if feed.bozo and not n:
            status = f"エラー: {feed.get('bozo_exception')}"
        else:
            status = "OK" if n else "0件"
        print(f"  {name}: {n}件 ({status})")
        raw_entries.extend(feed.entries)
        time.sleep(REQUEST_INTERVAL_SEC)
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
    print("許可外の媒体（件数の多い順・上位20）:")
    for src, cnt in sorted(excluded_sources.items(), key=lambda x: -x[1])[:20]:
        print(f"  {cnt:>4}件  {src}")
    return rows


def load_existing() -> pd.DataFrame:
    """既存CSVを読み込み、蓄積を継続する"""
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
