import streamlit as st
import pandas as pd
from core.database import init_db, update_glossary_db

def display_maintenance_page():
    """辞書データの編集ページの描画と機能"""
    st.subheader("辞書データの編集")
    st.info("テーブルを直接編集し、「変更を保存」ボタンを押してください。行の追加・削除も可能です。")
    
    conn = init_db()
    
    try:
        db_df = pd.read_sql_query("SELECT id, english_term, japanese_term FROM terms ORDER BY english_term", conn)
        
        edited_df = st.data_editor(
            db_df,
            column_config={
                "id": st.column_config.NumberColumn("ID", disabled=True),
                "english_term": "英語原文",
                "japanese_term": "日本語訳",
            },
            num_rows="dynamic",
            key="glossary_editor",
            width='stretch'
        )

        if st.button("変更を保存 💾", type="primary"):
            update_glossary_db(conn, edited_df, db_df)
            st.success("データベースの変更が正常に保存されました！")
            st.rerun()

    except Exception as e:
        st.error(f"データベース操作中にエラーが発生しました: {e}")
        st.warning("`glossary.db`に`terms`テーブルが存在することを確認してください。")