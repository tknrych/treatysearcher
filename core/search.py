import time
import streamlit as st
from datetime import datetime
from azure.search.documents.models import VectorizedQuery
from utils import is_japanese

def perform_search(search_client, aoai_client, embed_model, query_text: str, enable_title_search: bool, mode_override: str = None, match_type_override: str = None, lang_mode_override: str = None) -> tuple[list, str]:
    """Azure Search を実行する"""
    t0 = time.perf_counter()
    
    mode_now = mode_override if mode_override is not None else st.session_state.get("mode_radio")
    match_type_now = match_type_override if match_type_override is not None else st.session_state.get("match_type_radio")
    lang_mode = lang_mode_override if lang_mode_override is not None else st.session_state.get("lang_mode_radio")
        
    if enable_title_search:
        is_ja_q, text_fields, vec_field, mode_now = True, ["jp_title"], "japaneseVector", "文字列検索のみ"
    else:
        is_ja_q = is_japanese(query_text) if lang_mode == "言語自動判定" else (lang_mode == "日本語")
        text_fields, vec_field = (["jp_text"], "japaneseVector") if is_ja_q else (["en_text"], "englishVector")
    
    search_q = f'"{query_text.strip()}"' if match_type_now == "完全一致 (Phrase)" else query_text.strip()
    
    common_kwargs = dict(select=["en_text", "jp_text", "sourceFile", "line_number", "jp_title", "valid_date"], top=st.session_state.get("topk_slider", 10), include_total_count=True)

    # (日付フィルターのロジックは変更なし)
    odata_filters = []
    if st.session_state.get("date_filter_enabled", False):
        start_date = st.session_state.get("start_date")
        end_date = st.session_state.get("end_date")
        if start_date and end_date and start_date <= end_date:
            start_date_str = datetime.combine(start_date, datetime.min.time()).isoformat() + "Z"
            end_date_str = datetime.combine(end_date, datetime.max.time()).isoformat() + "Z"
            date_filter_query = f"valid_date ge {start_date_str} and valid_date le {end_date_str}"
            odata_filters.append(date_filter_query)
    if odata_filters:
        common_kwargs['filter'] = " and ".join(odata_filters)

    if enable_title_search: 
        common_kwargs["order_by"] = "line_number asc"
    
    search_args = {}
    if mode_now in ["ハイブリッド (文字列検索 + あいまい検索)", "文字列検索のみ"]:
        search_args.update({'search_text': search_q, 'search_fields': text_fields, 'highlight_fields': ",".join(text_fields), 'highlight_pre_tag': "<em>", 'highlight_post_tag': "</em>"})
    
    if mode_now in ["ハイブリッド (文字列検索 + あいまい検索)", "あいまい検索のみ"]:
        try:
            emb = aoai_client.embeddings.create(model=embed_model, input=[query_text]).data[0].embedding
            search_args['vector_queries'] = [VectorizedQuery(vector=emb, fields=vec_field, k_nearest_neighbors=st.session_state.get("kvec_slider", 30))]
        except Exception as e: st.warning(f"Embeddingの作成に失敗しました: {e}")
    
    if not search_args:
        st.error("検索引数を構築できませんでした。")
        return [], ""
    
    results = search_client.search(**common_kwargs, **search_args)
    result_list = list(results)
    
    display_match_type = "完全一致" if match_type_now == "完全一致 (Phrase)" else "部分一致"
    metadata = f"検索モード: **{mode_now} ({display_match_type})** | 言語: {lang_mode} | Top={common_kwargs['top']} | Time: {(time.perf_counter() - t0) * 1000:.1f} ms | Hits: {results.get_count()}"
    
    st.session_state.is_last_query_ja = is_ja_q
    return result_list, metadata

@st.cache_data(show_spinner="条約全文を取得中...")
def fetch_full_treaty_text(_search_client, source_file: str) -> list:
    """指定されたsourceFileの全チャンクを行番号順に取得する"""
    try:
        escaped_source_file = source_file.replace("'", "''")
        odata_filter = f"sourceFile eq '{escaped_source_file}'"
        results = _search_client.search(
            search_text="*",
            filter=odata_filter,
            order_by=["line_number asc"],
            select=["en_text", "jp_text", "line_number"],
            top=2000
        )
        return list(results)
    except Exception as e:
        st.error(f"条約全文の取得中にエラーが発生しました: {e}")
        return []