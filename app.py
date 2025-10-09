import streamlit as st
import urllib.parse

# 各ページの描画関数をインポート
from views.search_interface import display_search_interface
from views.full_treaty_page import display_full_treaty_page
from views.analysis_page import display_analysis_page
from views.term_search_page import display_term_search_results_page
from views.check_page import display_check_page

# ==============================================================================
# --- メインロジック：表示モードの切り替え ---
# ==============================================================================
st.set_page_config(page_title="条約文検索", layout="wide")

# アプリケーション全体で利用するCSSスタイル
st.markdown("""
<style>
    /* フォントサイズ設定 */
    html, body, [class*="st-"], [class*="css-"] {
        font-size: 16px;
    }
    /* ボタン幅を最大化 */
    div[data-testid="stHorizontalBlock"] div[data-testid="stButton"] > button {
        width: 100%;
    }
    /* ハイライト用のスタイル */
    em {
        background-color: #FFFF00; /* 黄色の背景色 */
        font-style: normal;      /* イタリック体を解除 */
    }
</style>
""", unsafe_allow_html=True)

# URLのクエリパラメータを解析
query_params = st.query_params
treaty_id_to_display = query_params.get("view_treaty")
text_to_analyze_encoded = query_params.get("analyze_text")
term_to_search_encoded = query_params.get("search_term")
text_to_check_encoded = query_params.get("check_text")
original_text_encoded = query_params.get("original_text") 

# パラメータに応じて描画するページを切り替え
if treaty_id_to_display:
    display_full_treaty_page(treaty_id_to_display)
elif text_to_analyze_encoded:
    decoded_text = urllib.parse.unquote(text_to_analyze_encoded)
    display_analysis_page(decoded_text)
elif term_to_search_encoded:
    decoded_term = urllib.parse.unquote(term_to_search_encoded)
    display_term_search_results_page(decoded_term)
elif text_to_check_encoded:
    decoded_text = urllib.parse.unquote(text_to_check_encoded)
    original_text = urllib.parse.unquote(original_text_encoded)
    display_check_page(decoded_text, original_text)
else:
    # デフォルトはメインの検索インターフェース
    display_search_interface()