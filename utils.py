import os
import re
import html
import streamlit as st
from pathlib import Path

def is_japanese(text: str) -> bool:
    """テキストに日本語が含まれるかを判定する"""
    return re.search(r"[\u3040-\u30ff\u3400-\u9fff]", text) is not None

def mask_list_markers(text: str) -> str:
    """pysbdが誤認識する可能性のある箇条書きマーカーを一時的に置換する"""
    replacements = {
        '(a)': '__PAREN_A__', '(b)': '__PAREN_B__', '(c)': '__PAREN_C__',
        '(d)': '__PAREN_D__', '(e)': '__PAREN_E__', '(f)': '__PAREN_F__',
        '(i)': '__PAREN_I__', '(ii)': '__PAREN_II__', '(iii)': '__PAREN_III__',
        '(iv)': '__PAREN_IV__',
    }
    for old, new in replacements.items():
        text = re.sub(r'(\s|^)' + re.escape(old) + r'(\s|$|\,)', r'\1' + new + r'\2', text)
    return text

def unmask_list_markers(text: str) -> str:
    """マスキングした文字列を元に戻す"""
    replacements = {
        '__PAREN_A__': '(a)', '__PAREN_B__': '(b)', '__PAREN_C__': '(c)',
        '__PAREN_D__': '(d)', '__PAREN_E__': '(e)', '__PAREN_F__': '(f)',
        '__PAREN_I__': '(i)', '__PAREN_II__': '(ii)', '__PAREN_III__': '(iii)',
        '__PAREN_IV__': '(iv)',
    }
    for new, old in replacements.items():
        text = text.replace(new, old)
    return text

def _escape_html(s: str) -> str:
    """HTMLエスケープを行う"""
    return html.escape(s, quote=False)

def merge_server_highlights(full_text: str, highlight_snippets: list[str]) -> str:
    """Azure Searchのハイライト結果を全文にマージする"""
    if not full_text or not highlight_snippets:
        return _escape_html(full_text)
    text = _escape_html(full_text)
    em_pat = re.compile(r"<em>(.+?)</em>")
    hits = sorted(set(m.group(1) for snip in highlight_snippets for m in em_pat.finditer(snip)), key=len, reverse=True)
    for h in hits:
        if h.strip():
            text = text.replace(_escape_html(h), f"<em>{_escape_html(h)}</em>")
    return text

def client_side_highlight(full_text: str, query: str) -> str:
    """クライアント側で文字列をハイライトする"""
    if not full_text or not query:
        return _escape_html(full_text)
    text = _escape_html(full_text)
    clean_query = query.strip().strip('"')
    q_esc = _escape_html(clean_query)
    if q_esc:
        pattern = re.compile(re.escape(q_esc), re.IGNORECASE)
        text = pattern.sub(lambda m: f"<em>{m.group(0)}</em>", text)
    return text

def _clear_title_tab_results():
    """タブ「条約名検索」の結果をクリアする"""
    keys_to_clear = ["search_results_title", "last_query_title", "metadata_title", "is_ja_q_title"]
    for k in keys_to_clear:
        if k in st.session_state:
            del st.session_state[k]
    if "query_input_title" in st.session_state:
        st.session_state.query_input_title = ""

def _clear_text_tab_results():
    """タブ「本文検索」のキーワード検索結果をクリアする"""
    keys_to_clear = ["search_results", "last_query", "metadata", "translations", "is_last_query_ja"]
    for k in keys_to_clear:
        if k in st.session_state:
            del st.session_state[k]
    if "query_input_text" in st.session_state:
        st.session_state.query_input_text = ""

def _clear_analysis_tab_results():
    """タブ「本文検索」の分析結果をクリアする"""
    keys_to_clear = ["segmented_sentences"]
    for k in keys_to_clear:
        if k in st.session_state:
            del st.session_state[k]
    if "analysis_input" in st.session_state:
        st.session_state.analysis_input = ""

@st.cache_data
def load_joyo_kanji():
    """
    ./ref_docs/joyo-kanji.txt から常用漢字のセットを読み込みます。
    結果はキャッシュされ、アプリのパフォーマンスを向上させます。
    """
    try:
        # このファイルの絶対パスを取得
        current_script_path = os.path.abspath(__file__)
        # このファイルの親ディレクトリ（つまりプロジェクトのルート）を取得
        project_root = os.path.dirname(current_script_path)
        # 正しいパスを組み立てる
        joyo_kanji_path = os.path.join(project_root, "ref_docs", "joyo-kanji.txt")
        
        with open(joyo_kanji_path, "r", encoding="utf-8") as f:
            # ファイル内のすべての文字を連結し、空白文字を削除してセットを作成
            kanji_text = f.read()
            return set(kanji_text.replace(" ", "").replace("\n", ""))
    except FileNotFoundError:
        # エラーメッセージも正しいパスを表示するように修正
        st.error(f"常用漢字ファイルが見つかりません: {joyo_kanji_path}")
        return set()

def find_non_joyo_kanji(text: str) -> list[str]:
    """
    与えられたテキストから常用漢字以外の漢字を抽出し、リストとして返します。

    Args:
        text (str): チェック対象のテキスト。

    Returns:
        list[str]: テキストに含まれる常用漢字以外の漢字のリスト。
                   見つからない場合は空のリストを返します。
    """
    joyo_kanji_set = load_joyo_kanji()
    if not joyo_kanji_set:
        return []

    # テキストから全ての漢字を重複なく抽出
    kanji_in_text = set(re.findall(r'[\u4e00-\u9FFF]', text))

    # 常用漢字セットに含まれていない漢字を特定
    non_joyo_kanji = [kanji for kanji in kanji_in_text if kanji not in joyo_kanji_set]

    return sorted(non_joyo_kanji)