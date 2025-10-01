import streamlit as st

def display_check_page(text_to_check: str):
    """平仄確認用の専用ページを描画"""
    st.title("📝 平仄確認処理")
    st.info("AIによる翻訳結果を編集できます。")
    
    edited_text = st.text_area(
        "編集可能な翻訳文",
        value=text_to_check,
        height=400,
        label_visibility="collapsed"
    )