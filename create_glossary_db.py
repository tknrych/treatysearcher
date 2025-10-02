import sqlite3

# データベースに接続（ファイルが存在しない場合は新規作成される）
conn = sqlite3.connect('glossary.db')
cursor = conn.cursor()

# 用語集テーブルを作成
cursor.execute('''
CREATE TABLE IF NOT EXISTS terms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    english_term TEXT NOT NULL UNIQUE,
    japanese_term TEXT NOT NULL
)
''')

# 例として対訳データを挿入
try:
    cursor.execute("INSERT INTO terms (english_term, japanese_term) VALUES (?, ?)",
                   ('political commitment', '政治的な決意'))
    print("用語 'political commitment' を追加しました。")
except sqlite3.IntegrityError:
    print("用語 'political commitment' は既に追加されています。")

# 変更をコミットして接続を閉じる
conn.commit()
conn.close()

print("データベース 'glossary.db' の準備が完了しました。")