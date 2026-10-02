import os
import datetime
import pandas as pd

def generate_weekly_report(csv_path='ai_news_stats.csv', target_date=None):
    # 1. 対象期間の計算（指定がない場合は実行日の「前週月曜〜日曜」）
    if target_date is None:
        today = datetime.date.today()
    else:
        today = datetime.datetime.strptime(target_date, "%Y-%m-%d").date()
    
    # 前週の月曜日と日曜日を算出
    last_monday = today - datetime.timedelta(days=today.weekday() + 7)
    last_sunday = last_monday + datetime.timedelta(days=6)
    
    monday_str = last_monday.strftime('%Y-%m-%d')
    sunday_str = last_sunday.strftime('%Y-%m-%d')
    
    print(f"========================================")
    print(f"集計対象期間: {monday_str} 〜 {sunday_str}")
    print(f"========================================")

    # ファイル存在チェック
    if not os.path.exists(csv_path):
        print(f"エラー: {csv_path} が見つかりません。パスを確認してください。")
        return

    # 2. CSVデータの読み込みとフィルタリング
    df = pd.read_csv(csv_path)
    df['date_str'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
    
    # 期間内データ抽出
    mask = (df['date_str'] >= monday_str) & (df['date_str'] <= sunday_str)
    week_df = df[mask].copy()
    
    # 重複タイトルの除外
    week_df = week_df.drop_duplicates(subset=['news_title'])
    
    # ノイズキーワードリスト（非AI関連の除外ルール）
    noise_keywords = [
        'gang rape', 'traffic', 'weather', 'murder', 'baseball', 
        'shooting', 'pilot', 'stabbing', '撮るしん'
    ]
    for kw in noise_keywords:
        week_df = week_df[~week_df['news_title'].str.contains(kw, case=False, na=False)]

    print(f"抽出・除外後ニュース件数: {len(week_df)} 件")

    # 3. カテゴリ自動分類ルール
    categories = {
        "1. フロンティアモデル・主要ベンダー動向": ["OpenAI", "ChatGPT", "Claude", "Anthropic", "Gemini", "Google", "Meta", "dots"],
        "2. 政府規制・ガバナンス・安全保障": ["トランプ", "Trump", "FTC", "規制", "安全", "大統領令", "SI", "スーパーインテリジェンス", "軍", "米中"],
        "3. 産業実装・フィジカルAI・ビジネス": ["ロボット", "フィジカル", "ファナック", "日立", "企業", "自動化", "研修", "BtoB", "広告"],
        "4. 権利・司法・社会への影響": ["訴訟", "声優", "津田健次郎", "権利", "著作権", "ディープフェイク", "雇用", "新聞"]
    }

    categorized_data = {cat: [] for cat in categories}
    uncategorized = []

    for idx, row in week_df.iterrows():
        title = str(row['news_title'])
        source = str(row['news_source'])
        matched = False
        
        for cat, keywords in categories.items():
            if any(kw.lower() in title.lower() for kw in keywords):
                categorized_data[cat].append((title, source))
                matched = True
                break
        
        if not matched:
            uncategorized.append((title, source))

    # 4. HTMLページの生成
    html_content = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI News Weekly Report ({monday_str} - {sunday_str})</title>
    <style>
        :root {{
            --primary-color: #1a365d;
            --accent-color: #2b6cb0;
            --bg-color: #f7fafc;
            --card-bg: #ffffff;
            --text-color: #2d3748;
            --border-color: #e2e8f0;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            line-height: 1.6;
            margin: 0;
            padding: 20px;
        }}
        .container {{ max-width: 900px; margin: 0 auto; }}
        header {{
            background-color: var(--primary-color);
            color: white;
            padding: 25px 20px;
            border-radius: 8px;
            margin-bottom: 20px;
        }}
        header h1 {{ margin: 0 0 10px 0; font-size: 1.7rem; }}
        .meta-info {{
            font-size: 0.9rem;
            background: rgba(255, 255, 255, 0.15);
            padding: 6px 12px;
            border-radius: 4px;
            display: inline-block;
        }}
        .section-card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
        }}
        .section-card h2 {{
            color: var(--primary-color);
            font-size: 1.2rem;
            border-bottom: 2px solid var(--accent-color);
            padding-bottom: 6px;
            margin-top: 0;
        }}
        ul {{ padding-left: 20px; margin-bottom: 0; }}
        li {{ margin-bottom: 10px; font-size: 0.95rem; }}
        .source-tag {{
            background: #edf2f7;
            color: #4a5568;
            font-size: 0.75rem;
            padding: 2px 6px;
            border-radius: 4px;
            margin-left: 6px;
        }}
    </style>
</head>
<body>
<div class="container">
    <header>
        <h1>AI News Weekly Digest</h1>
        <div class="meta-info">
            📅 対象期間: <strong>{monday_str} 〜 {sunday_str}</strong> | 📊 抽出ニュース数: <strong>{len(week_df)} 件</strong>
        </div>
    </header>
"""

    for cat_name, items in categorized_data.items():
        if not items:
            continue
        html_content += f"""
    <div class="section-card">
        <h2>{cat_name} ({len(items)}件)</h2>
        <ul>"""
        for title, source in items[:15]:
            html_content += f"""
            <li><strong>{title}</strong> <span class="source-tag">{source}</span></li>"""
        html_content += """
        </ul>
    </div>"""

    html_content += f"""
    <footer>
        <p style="text-align:center; color:#718096; font-size:0.85rem; margin-top:30px;">
            Generated on {datetime.date.today().strftime('%Y-%m-%d')} | AI News Weekly Digest
        </p>
    </footer>
</div>
</body>
</html>"""

    # 5. docs/ フォルダへ自動出力（GitHub Pages公開用）
    os.makedirs("docs", exist_ok=True)
    
    archive_filename = f"docs/weekly_{monday_str.replace('-', '')}.html"
    latest_filename = "docs/index.html"

    with open(archive_filename, "w", encoding="utf-8") as f:
        f.write(html_content)

    with open(latest_filename, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"成功: 以下のHTMLファイルを出力しました：")
    print(f" - アーカイブ: {archive_filename}")
    print(f" - 最新トップ: {latest_filename}")

if __name__ == "__main__":
    generate_weekly_report()