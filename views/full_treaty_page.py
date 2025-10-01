import streamlit as st
from core.azure_clients import get_clients
from core.search import fetch_full_treaty_text

def display_full_treaty_page(treaty_id: str):
    """全文表示専用ページの描画"""
    search_client, _, _, _ = get_clients()
    treaty_title = ""
    
    try:
        escaped_treaty_id = treaty_id.replace("'", "''")
        odata_filter = f"sourceFile eq '{escaped_treaty_id}'"
        results = search_client.search(
            search_text="*",
            filter=odata_filter,
            select=["jp_title"],
            top=1
        )
        if first_result := next(results, None):
            treaty_title = first_result.get("jp_title", "")
    except Exception as e:
        st.warning(f"条約名の取得中にエラーが発生しました: {e}")
    
    st.title(treaty_title or "条約全文")
    st.subheader(treaty_id.replace(".csv", ".pdf"))
    
    # fetch_full_treaty_textにクライアントを渡す
    if full_treaty_chunks := fetch_full_treaty_text(search_client, treaty_id):
        full_en_text = "\n\n".join([c.get("en_text", "") for c in full_treaty_chunks])
        full_ja_text = "\n\n".join([c.get("jp_text", "") for c in full_treaty_chunks])
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("日本語全文")
            st.text_area("...", full_ja_text, height=800)
        with col2:
            st.subheader("英語全文")
            st.text_area("...", full_en_text, height=800)
    else:
        st.error("全文データの取得に失敗しました。")