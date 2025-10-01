import os
import re
import sqlite3
import streamlit as st
import pandas as pd

@st.cache_resource
def init_db():
    """データベース接続を初期化し、コネクションを返す"""
    db_path = os.getenv("DATABASE_PATH")
    return sqlite3.connect(db_path, check_same_thread=False)

@st.cache_data
def load_all_terms(_conn):
    """DBから全用語をロードする（キャッシュ用）"""
    cursor = _conn.cursor()
    cursor.execute("SELECT english_term, japanese_term FROM terms")
    return cursor.fetchall()

def find_glossary_terms(text: str, conn) -> dict:
    """与えられたテキスト内から用語集の英単語を検索し、辞書で返す"""
    all_terms = load_all_terms(conn)
    if not all_terms:
        return {}

    term_map = {}
    for en_term, ja_term in all_terms:
        if en_term not in term_map:
            term_map[en_term] = []
        term_map[en_term].append(ja_term)

    sorted_terms = sorted(term_map.keys(), key=len, reverse=True)
    pattern = r'\b(' + '|'.join(re.escape(term) for term in sorted_terms) + r')\b'
    matches = re.finditer(pattern, text, re.IGNORECASE)

    found_terms = {}
    lower_term_map = {en.lower(): (en, ja_list) for en, ja_list in term_map.items()}

    for match in matches:
        matched_text_lower = match.group(1).lower()
        if matched_text_lower in lower_term_map:
            original_en, ja_list = lower_term_map[matched_text_lower]
            if original_en not in found_terms:
                found_terms[original_en] = ja_list
    return found_terms

def update_glossary_db(conn, edited_df, db_df):
    """データエディタでの変更をデータベースに反映する"""
    cursor = conn.cursor()
    
    orig_ids = set(db_df['id'])
    edited_ids = set(edited_df['id'].dropna())
    
    # 1. 削除された行
    deleted_ids = orig_ids - edited_ids
    if deleted_ids:
        cursor.executemany("DELETE FROM terms WHERE id = ?", [(id,) for id in deleted_ids])
        st.write(f"🗑️ {len(deleted_ids)}件の用語を削除しました。")

    # 2. 追加された行
    new_rows = edited_df[edited_df['id'].isna()]
    if not new_rows.empty:
        insert_data = [
            (row['english_term'], row['japanese_term'])
            for _, row in new_rows.iterrows()
            if pd.notna(row['english_term']) and pd.notna(row['japanese_term'])
        ]
        if insert_data:
            cursor.executemany("INSERT INTO terms (english_term, japanese_term) VALUES (?, ?)", insert_data)
            st.write(f"✨ {len(insert_data)}件の用語を追加しました。")

    # 3. 変更された行
    comparison_df = pd.merge(db_df, edited_df, on='id', how='inner', suffixes=('_orig', '_new'))
    update_mask = (comparison_df['english_term_orig'] != comparison_df['english_term_new']) | \
                  (comparison_df['japanese_term_orig'] != comparison_df['japanese_term_new'])
    updated_rows = comparison_df[update_mask]
    if not updated_rows.empty:
        update_data = [
            (row['english_term_new'], row['japanese_term_new'], row['id'])
            for _, row in updated_rows.iterrows()
        ]
        cursor.executemany("UPDATE terms SET english_term = ?, japanese_term = ? WHERE id = ?", update_data)
        st.write(f"✏️ {len(update_data)}件の用語を更新しました。")

    conn.commit()
    load_all_terms.clear() # キャッシュをクリア