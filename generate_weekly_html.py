import datetime
import os
import re
import sys
import unicodedata
from zoneinfo import ZoneInfo

import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "ai_news_v2.csv")  # script.py の出力先と一致させる
OUTPUT_PATH = os.path.join(BASE_DIR, "weekly_news_raw.txt")
JST = ZoneInfo("Asia/Tokyo")

# 旧データ向けのノイズ除外。AI関連判定済みのデータでは「murder」「pilot」「shooting」などが
# AI記事まで除外してしまうため、既定では使わない。必要な語だけ追加する。
NOISE_KEYWORDS = ["撮るしん"]


def nfkc(text: str) -> str:
    return unicodedata.normalize("NFKC", str(text or ""))


def resolve_period(mode: str, target_date: str | None):
    # 実行環境のUTC日付ではなく日本時間の日付で判定する（月曜朝7時JSTに実行するため）
    if target_date:
        today = datetime.datetime.strptime(target_date, "%Y-%m-%d").date()
    else:
        today = datetime.datetime.now(JST).date()

    if mode == "last_week":
        # 直前の月曜〜日曜（月曜に実行すると、先週1週間分になる）
        last_monday = today - datetime.timedelta(days=today.weekday() + 7)
        last_sunday = last_monday + datetime.timedelta(days=6)
    else:
        # 直近7日間（本日を含まず、昨日までの7日間）
        last_sunday = today - datetime.timedelta(days=1)
        last_monday = today - datetime.timedelta(days=7)
    return last_monday, last_sunday


def extract_weekly_data(mode: str = "last_week", target_date: str | None = None) -> None:
    last_monday, last_sunday = resolve_period(mode, target_date)
    monday_str = last_monday.strftime("%Y-%m-%d")
    sunday_str = last_sunday.strftime("%Y-%m-%d")

    print("=" * 40)
    print(f"集計対象期間: {monday_str} 〜 {sunday_str}")
    print("=" * 40)

    if not os.path.exists(CSV_PATH):
        # 以前は return で正常終了していたため、失敗が気づかれなかった
        print(f"エラー: {CSV_PATH} が見つかりません。")
        sys.exit(1)

    df = pd.read_csv(CSV_PATH, dtype=str, encoding="utf-8-sig")
    df["date_str"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    df = df.dropna(subset=["date_str", "news_title"])

    mask = (df["date_str"] >= monday_str) & (df["date_str"] <= sunday_str)
    week_df = df[mask].copy()

    # タイトルの表記揺れを吸収して重複排除
    week_df["_key"] = week_df["news_title"].map(lambda t: re.sub(r"[\s\W_]+", "", nfkc(t)).lower())
    week_df = week_df.drop_duplicates(subset=["_key"]).drop(columns=["_key"])

    for kw in NOISE_KEYWORDS:
        week_df = week_df[~week_df["news_title"].str.contains(kw, case=False, na=False, regex=False)]

    week_df = week_df.sort_values(by=["date_str", "news_source"], ascending=[False, True])

    print(f"抽出件数: {len(week_df)} 件")
    if week_df.empty:
        print("警告: 対象期間の記事がありません。日次収集が期間内に動いたかを確認してください。")

    lines = [f"【対象期間: {monday_str} 〜 {sunday_str}】（総件数: {len(week_df)}件）", ""]
    for _, row in week_df.iterrows():
        url = str(row.get("news_url", "") or "").strip()
        suffix = f" {url}" if url and url != "nan" else ""
        lines.append(f"- [{row['date_str']}] {row['news_title']} ({row['news_source']}){suffix}")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"成功: {OUTPUT_PATH} にデータを出力しました。")


if __name__ == "__main__":
    # 毎週月曜（JST）に先週分を取得する
    extract_weekly_data(mode="last_week")
