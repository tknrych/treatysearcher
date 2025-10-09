import streamlit as st
import urllib.parse
from datetime import datetime

from core.azure_clients import get_clients
from core.search import perform_search
from utils import is_japanese, _escape_html, client_side_highlight

def display_term_search_results_page(term: str):
    """用語の完全一致検索の結果を専用ページに表示する"""
    search_client, aoai_client, _, embed_model = get_clients()
    
    st.title(f"🔍 用語検索結果: \"{term}\"")
    st.info("指定された用語での完全一致検索結果を表示します。")

    results, metadata = perform_search(
        search_client, aoai_client, embed_model,
        query_text=term, 
        enable_title_search=False,
        mode_override="文字列検索のみ",
        match_type_override="完全一致 (Phrase)",
        lang_mode_override="言語自動判定"
    )

    st.caption(metadata)
    st.divider()

    if not results:
        st.warning("検索結果が見つかりませんでした。")
        return

    for result_item in results:
        res_en, res_ja, source_file = result_item.get("en_text", ""), result_item.get("jp_text", ""), result_item.get("sourceFile", "")
        jp_title = result_item.get("jp_title", "")
        source_file_display = source_file.replace(".csv", ".pdf")
        
        title_prefix = f"**{jp_title}**" if jp_title else ""
        valid_date_str = result_item.get("valid_date", "")
        date_display = ""
        if valid_date_str:
            try:
                formatted_date = datetime.fromisoformat(valid_date_str.replace('Z', '+00:00')).strftime('%Y年%m月%d日')
                date_display = f" | 効力発生日: **{formatted_date}**"
            except (ValueError, TypeError):
                date_display = f" | 効力発生日: **{valid_date_str}**"

        metadata_str = f"{title_prefix}{date_display} | Source: **{source_file_display}#{result_item['line_number']}** | Score: {result_item['@search.score']:.4f}"

        res_col1, res_col2 = st.columns([0.8, 0.2])
        with res_col1: st.markdown(metadata_str)
        with res_col2: st.markdown(f'<a href="?view_treaty={urllib.parse.quote(source_file)}" target="_blank" rel="noopener noreferrer">条約全文を開く</a>', unsafe_allow_html=True)
        
        if is_japanese(term):
            en_html_highlighted = _escape_html(res_en)
            ja_html_highlighted = client_side_highlight(res_ja, term)
        else:
            en_html_highlighted = client_side_highlight(res_en, term)
            ja_html_highlighted = _escape_html(res_ja)
            
        st.markdown(f"**英語原文:**<br>{en_html_highlighted}", unsafe_allow_html=True)
        st.markdown(f"**日本語訳:**<br>{ja_html_highlighted}", unsafe_allow_html=True)
        st.divider()