import os
import datetime
import pandas as pd

def extract_weekly_data(csv_path='ai_news_stats.csv', target_date=None):
    # 1. 対象期間の計算（指定がない場合は実行日の「前週月曜〜日曜」）
    if target_date is None:
        today = datetime.date.today()
    else:
        today = datetime.datetime.strptime(target_date, "%Y-%m-%d").date()
    
    last_monday = today - datetime.timedelta(days=today.weekday() + 7)
    last_sunday = last_monday + datetime.timedelta(days=6)
    
    monday_str = last_monday.strftime('%Y-%m-%d')
    sunday_str = last_sunday.strftime('%Y-%m-%d')
    
    print(f"========================================")
    print(f"集計対象期間: {monday_str} 〜 {sunday_str}")
    print(f"========================================")

    if not os.path.exists(csv_path):
        print(f"エラー: {csv_path} が見つかりません。")
        return

    # 2. CSVデータの読み込みとフィルタリング
    df = pd.read_csv(csv_path)
    df['date_str'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
    
    mask = (df['date_str'] >= monday_str) & (df['date_str'] <= sunday_str)
    week_df = df[mask].copy().drop_duplicates(subset=['news_title'])
    
    # ノイズキーワード除外
    noise_keywords = ['gang rape', 'traffic', 'weather', 'murder', 'baseball', 'shooting', 'pilot', 'stabbing', '撮るしん']
    for kw in noise_keywords:
        week_df = week_df[~week_df['news_title'].str.contains(kw, case=False, na=False)]

    print(f"抽出件数: {len(week_df)} 件")

    # 3. テキストファイルとして出力（AIにそのまま渡せる形式）
    output_text = f"【対象期間: {monday_str} 〜 {sunday_str}】（総件数: {len(week_df)}件）\n\n"
    for idx, row in week_df.iterrows():
        output_text += f"- [{row['date_str']}] {row['news_title']} ({row['news_source']})\n"

    output_filename = "weekly_news_raw.txt"
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(output_text)

    print(f"成功: {output_filename} に前週ニュースを出力しました。")

if __name__ == "__main__":
    extract_weekly_data()