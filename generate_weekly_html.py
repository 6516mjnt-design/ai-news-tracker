import os
import datetime
import pandas as pd

def extract_weekly_data(csv_path='ai_news_stats.csv', target_date=None, mode='last_week'):
    """
    mode='last_week': 実行日に関わらず「先週の月曜日〜日曜日」を取得
    mode='recent_7days': 実行日から「直近7日間」を取得
    """
    if target_date:
        today = datetime.datetime.strptime(target_date, "%Y-%m-%d").date()
    else:
        today = datetime.date.today()
    
    if mode == 'last_week':
        # 先週の月曜〜日曜
        last_monday = today - datetime.timedelta(days=today.weekday() + 7)
        last_sunday = last_monday + datetime.timedelta(days=6)
    else:
        # 直近7日間（本日含まず昨日までの7日間）
        last_sunday = today - datetime.timedelta(days=1)
        last_monday = today - datetime.timedelta(days=7)
    
    monday_str = last_monday.strftime('%Y-%m-%d')
    sunday_str = last_sunday.strftime('%Y-%m-%d')
    
    print(f"========================================")
    print(f"集計対象期間: {monday_str} 〜 {sunday_str}")
    print(f"========================================")

    if not os.path.exists(csv_path):
        print(f"エラー: {csv_path} が見つかりません。")
        return

    df = pd.read_csv(csv_path)
    df['date_str'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
    
    mask = (df['date_str'] >= monday_str) & (df['date_str'] <= sunday_str)
    week_df = df[mask].copy().drop_duplicates(subset=['news_title'])
    
    # ノイズ除外
    noise_keywords = ['gang rape', 'traffic', 'weather', 'murder', 'baseball', 'shooting', 'pilot', 'stabbing', '撮るしん']
    for kw in noise_keywords:
        week_df = week_df[~week_df['news_title'].str.contains(kw, case=False, na=False)]

    print(f"抽出件数: {len(week_df)} 件")

    output_text = f"【対象期間: {monday_str} 〜 {sunday_str}】（総件数: {len(week_df)}件）\n\n"
    for idx, row in week_df.iterrows():
        output_text += f"- [{row['date_str']}] {row['news_title']} ({row['news_source']})\n"

    output_filename = "weekly_news_raw.txt"
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(output_text)

    print(f"成功: {output_filename} にデータを出力しました。")

if __name__ == "__main__":
    # 普段は先週分を取得。直近7日間にしたい場合は mode='recent_7days' に変更可能
    extract_weekly_data(mode='last_week')