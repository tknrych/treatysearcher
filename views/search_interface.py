import streamlit as st
import urllib.parse
from datetime import datetime

# 必要な関数を各モジュールからインポート
from core.azure_clients import get_clients
from core.database import init_db, find_glossary_terms
from core.nlp import load_nlp_model
from core.search import perform_search
from core.translation import get_translation_with_retry
from utils import (
    _clear_title_tab_results,
    _clear_analysis_tab_results,
    mask_list_markers,
    unmask_list_markers,
    is_japanese,
    merge_server_highlights,
    client_side_highlight,
    _escape_html
)
from .maintenance_page import display_maintenance_page

def display_search_interface():
    """メインの検索インターフェースを描画"""
    # --- 初期化処理 ---
    search_client, aoai_client, gpt_model, embed_model = get_clients()
    db_conn = init_db()
    nlp = load_nlp_model()

    # --- UI描画 ---
    if "query_input_title" not in st.session_state:
        st.session_state.query_input_title = ""
    if "analysis_input" not in st.session_state:
        st.session_state.analysis_input = ""

    with st.sidebar:
        st.title("条約文検索")
        st.subheader("検索オプション")
        st.radio("検索言語", ["言語自動判定", "英語", "日本語"], key="lang_mode_radio")
        st.radio("検索モード", ["ハイブリッド (文字列検索 + あいまい検索)", "文字列検索のみ", "あいまい検索のみ"], key="mode_radio")
        st.radio("一致方法", ["部分一致 (OR)", "完全一致 (Phrase)"], key="match_type_radio")
        st.slider("上位 (表示件数)", 1, 50, 10, key="topk_slider")
        st.slider("k (あいまい検索 近接度)", 1, 200, 30, key="kvec_slider")

        st.divider()
        st.subheader("日付フィルター")
        if st.checkbox("効力発生日で絞り込み", key="date_filter_enabled"):
            today = datetime.now().date()
            default_start = datetime(1950, 1, 1).date()

            start_date = st.date_input("開始日", value=default_start, key="start_date")
            end_date = st.date_input("終了日", value=today, key="end_date")

            if start_date > end_date:
                st.error("エラー: 終了日は開始日以降に設定してください。")

    tab_text_search, tab_title_search, tab_maintenance = st.tabs(["✍️ 条約本文検索", "📜 条約名検索", "📖 翻訳辞書データの編集"])

    with tab_title_search:
        st.subheader("条約名で検索")
        q_title = st.text_input("検索したい条約名（日本語）を入力してください", key="query_input_title")

        col1_title, col2_title, _ = st.columns([1, 1, 5])
        with col1_title:
            run_clicked_title = st.button("🔍条約名検索", key="search_button_title")
        with col2_title:
            st.button("🧹入力消去　", key="clear_button_title", on_click=_clear_title_tab_results)

        if run_clicked_title and q_title.strip():
            st.session_state.last_query_title = q_title
            try:
                results, metadata = perform_search(search_client, aoai_client, embed_model, q_title, enable_title_search=True)
                st.session_state.search_results_title = results
                st.session_state.metadata_title = metadata
            except Exception as e:
                st.exception(e)
                st.session_state.search_results_title = None
        elif run_clicked_title and not q_title.strip():
            st.warning("検索キーワードを入力してください。")

        if "search_results_title" in st.session_state and st.session_state.search_results_title is not None:
            st.divider()
            st.caption(st.session_state.metadata_title)
            results_to_display = st.session_state.search_results_title
            if not results_to_display:
                st.info("検索結果は0件でした。")

            displayed_files = set()
            for r in results_to_display:
                source_file = r.get("sourceFile", "")
                if source_file in displayed_files:
                    continue
                displayed_files.add(source_file)
                jp_title = r.get("jp_title", "")
                source_file_display = source_file.replace(".csv", ".pdf")
                highlights = r.get("@search.highlights", {})
                highlighted_snippets = highlights.get("jp_title", [])

                if highlighted_snippets:
                    highlighted_title = " ... ".join(highlighted_snippets)
                else:
                    query_to_display = st.session_state.last_query_title
                    highlighted_title = client_side_highlight(jp_title, query_to_display)

                st.markdown(f"##### {highlighted_title}", unsafe_allow_html=True)
                res_col1, res_col2 = st.columns([0.75, 0.25])
                with res_col1:
                    valid_date_str = r.get("valid_date", "")
                    date_display = ""
                    if valid_date_str:
                        try:
                            formatted_date = datetime.fromisoformat(valid_date_str.replace('Z', '+00:00')).strftime('%Y年%m月%d日')
                            date_display = f" | 効力発生日: **{formatted_date}**"
                        except (ValueError, TypeError):
                            date_display = f" | 効力発生日: **{valid_date_str}**"
                    st.markdown(f"**ファイル名:** {source_file_display}{date_display}")
                with res_col2:
                    st.markdown(f'<a href="?view_treaty={urllib.parse.quote(source_file)}" target="_blank" rel="noopener noreferrer">条約全文を別タブで開く</a>', unsafe_allow_html=True)
                st.markdown("---")

    with tab_text_search:
        st.subheader("テキスト分割・類似条約文検索")
        pasted_text = st.text_area("対象となるテキストを貼り付け", height=200, key="analysis_input")

        col1_tab2, col2_tab2, col3_tab2, _, _, _ = st.columns([2, 2, 2, 3, 3, 3])
        with col1_tab2:
            start_analysis_clicked = st.button("✂️文章分割する　", key="start_analysis_button")
        with col2_tab2:
            no_split_clicked = st.button("📝文章分割しない", key="no_split_button")
        with col3_tab2:
            st.button("🧹入力消去　　　", key="clear_button_analysis", on_click=_clear_analysis_tab_results)

        if start_analysis_clicked or no_split_clicked:
            if not pasted_text.strip():
                st.warning("テキストを入力してください。")
            elif not nlp and start_analysis_clicked:
                st.error("NLPモデルのロードに失敗しました。")
            else:
                st.session_state.segmented_sentences = []
                if start_analysis_clicked:
                    doc = nlp(mask_list_markers(pasted_text))
                    for sent in doc.sents:
                        if original_sent_text := unmask_list_markers(sent.text).strip():
                            st.session_state.segmented_sentences.append({"text": original_sent_text, "search_results": None})
                elif no_split_clicked:
                    st.session_state.segmented_sentences.append({"text": pasted_text.strip(), "search_results": None})

        if "segmented_sentences" in st.session_state:
            st.markdown("---")
            num_sents = len(st.session_state.segmented_sentences)
            st.write(f"▼ {num_sents} 件の文に分割されました ▼" if num_sents > 1 else "▼ 1 件の文として処理します ▼")

            for i, sentence_data in enumerate(st.session_state.segmented_sentences):
                # フリーワード検索用の状態を初期化
                if f"fw_search_results_{i}" not in st.session_state:
                    st.session_state[f"fw_search_results_{i}"] = None
                if f"show_fw_search_{i}" not in st.session_state:
                    st.session_state[f"show_fw_search_{i}"] = False
                if f"fw_query_{i}" not in st.session_state:
                    st.session_state[f"fw_query_{i}"] = ""

                with st.expander(f"文 {i+1}: {sentence_data['text'][:80]}..."):
                    original_text = sentence_data['text']
                    st.markdown(f"📘**原文:**\n> {original_text.replace(chr(10), '  ' + chr(10) + '> ')}")

                    # ボタン用の列を5列に変更
                    c1, c2, c3, c_new, c4, _ = st.columns([2, 2, 2, 2, 2, 2])
                    with c1:
                        if st.button("🔍類似条約文検索", key=f"search_{i}"):
                            try:
                                results, metadata = perform_search(search_client, aoai_client, embed_model, sentence_data['text'], enable_title_search=False)
                                st.session_state.segmented_sentences[i]["search_results"] = [{"checked": False, **res} for res in results]
                                if "ai_translation" in st.session_state.segmented_sentences[i]:
                                    del st.session_state.segmented_sentences[i]["ai_translation"]
                                st.rerun()
                            except Exception as e: st.error(f"検索中にエラーが発生しました: {e}")
                    with c2:
                        is_disabled = not (original_text and not is_japanese(original_text))
                        if st.button("⚙️ 係り受け解析", key=f"analysis_{i}", disabled=is_disabled, help="解析対象は英語の文のみです。"):
                            url_to_open = f"?analyze_text={urllib.parse.quote(original_text)}"
                            st.components.v1.html(f"<script>window.open('{url_to_open}', '_blank');</script>", height=0)
                    with c3:
                        if st.button("📖登録辞書参照", key=f"glossary_{i}"):
                            found_terms_dict = find_glossary_terms(original_text, db_conn)
                            term_list_for_display = []
                            for en_term, ja_term_list in found_terms_dict.items():
                                for ja_term in ja_term_list:
                                    term_list_for_display.append({"en": en_term, "ja": ja_term, "checked": False})
                            st.session_state.segmented_sentences[i]["found_terms"] = term_list_for_display
                            st.rerun()
                    # フリーワード検索ボタン
                    with c_new:
                        if st.button("💬フリーワード検索", key=f"fw_search_show_{i}"):
                            st.session_state[f"show_fw_search_{i}"] = not st.session_state[f"show_fw_search_{i}"]
                            # 検索窓を開くときに以前の検索結果をクリア
                            if st.session_state[f"show_fw_search_{i}"]:
                                st.session_state[f"fw_search_results_{i}"] = None
                                st.session_state[f"fw_query_{i}"] = ""
                            st.rerun()
                    with c4:
                        if sentence_data.get("search_results"):
                            if st.button("🔤参照して日本語訳", key=f"translate_all_{i}"):
                                selected_results = [res for res in sentence_data["search_results"] if res.get("checked", False)]
                                if not selected_results:
                                    st.warning("翻訳の参照として使用する行を少なくとも1つ選択してください。")
                                else:
                                    context_english = "\\n\\n---\\n\\n".join([r.get("en_text", "") for r in selected_results])
                                    context_japanese = "\\n\\n---\\n\\n".join([r.get("jp_text", "") for r in selected_results])
                                    glossary_to_use = {}
                                    if "found_terms" in sentence_data and sentence_data["found_terms"]:
                                        for term_data in sentence_data["found_terms"]:
                                            if term_data["checked"]:
                                                glossary_to_use[term_data["en"]] = term_data["ja"]
                                    translation, score = get_translation_with_retry(aoai_client, gpt_model, original_text, context_english, context_japanese, glossary_to_use)
                                    st.session_state.segmented_sentences[i]["ai_translation"] = {"text": translation, "score": score}
                                    st.rerun()
                        else:
                            st.button("🔤参照して日本語訳", disabled=True, key=f"translate_all_{i}_disabled", help="先に類似文検索を実行してください。")

                    # ### 変更 ### フリーワード検索のUIとロジック
                    if st.session_state[f"show_fw_search_{i}"]:
                        with st.container(border=True):
                            st.markdown("##### 💬 フリーワードで条約本文を検索")
                            fw_query = st.text_input("検索キーワードを入力", key=f"fw_query_input_{i}", value=st.session_state[f"fw_query_{i}"])
                            st.session_state[f"fw_query_{i}"] = fw_query # 入力をstateに保存

                            fw_c1, fw_c2, fw_c3, _ = st.columns([1,1,1,4])
                            with fw_c1:
                                if st.button("検索実行", key=f"fw_search_run_{i}"):
                                    if fw_query.strip():
                                        try:
                                            results, _ = perform_search(search_client, aoai_client, embed_model, fw_query, enable_title_search=False)
                                            st.session_state[f"fw_search_results_{i}"] = [{"checked": False, **res} for res in results]
                                        except Exception as e:
                                            st.error(f"検索中にエラーが発生しました: {e}")
                                    else:
                                        st.warning("キーワードを入力してください。")
                                    st.rerun()
                            with fw_c2:
                                add_button_disabled = st.session_state[f"fw_search_results_{i}"] is None
                                if st.button("選択行を追加", key=f"fw_add_results_{i}", disabled=add_button_disabled):
                                    selected_fw_results = [res for res in st.session_state[f"fw_search_results_{i}"] if res["checked"]]
                                    if not st.session_state.segmented_sentences[i].get("search_results"):
                                        st.session_state.segmented_sentences[i]["search_results"] = []
                                    # チェックボックスの状態をリセットして追加
                                    for res in selected_fw_results: res["checked"] = False
                                    st.session_state.segmented_sentences[i]["search_results"] = selected_fw_results + st.session_state.segmented_sentences[i]["search_results"]
                                    st.session_state[f"show_fw_search_{i}"] = False # UIを閉じる
                                    st.rerun()
                            with fw_c3:
                                if st.button("閉じる", key=f"fw_close_{i}"):
                                    st.session_state[f"show_fw_search_{i}"] = False
                                    st.rerun()

                            # ### 変更 ### フリーワード検索結果を詳細表示
                            if st.session_state[f"fw_search_results_{i}"] is not None:
                                st.markdown("---")
                                st.markdown("##### 検索結果")
                                is_ja_q_for_highlight = is_japanese(fw_query)

                                for fw_idx, fw_res in enumerate(st.session_state[f"fw_search_results_{i}"]):
                                    with st.container(border=True):
                                        check_col, content_col = st.columns([0.08, 0.92])
                                        with check_col:
                                            is_checked = st.checkbox(" ", value=fw_res.get("checked", False), key=f"fw_res_check_{i}_{fw_idx}", label_visibility="collapsed")
                                            st.session_state[f"fw_search_results_{i}"][fw_idx]["checked"] = is_checked

                                        with content_col:
                                            res_en, res_ja, source_file = fw_res.get("en_text", ""), fw_res.get("jp_text", ""), fw_res.get("sourceFile", "")
                                            highlights = fw_res.get("@search.highlights") or {}
                                            en_snips, ja_snips = highlights.get("en_text", []), highlights.get("jp_text", [])
                                            jp_title = fw_res.get("jp_title", "")
                                            source_file_display = source_file.replace(".csv", ".pdf")
                                            title_prefix = f"**{jp_title}**" if jp_title else ""
                                            valid_date_str = fw_res.get("valid_date", "")
                                            date_display = ""
                                            if valid_date_str:
                                                try:
                                                    formatted_date = datetime.fromisoformat(valid_date_str.replace('Z', '+00:00')).strftime('%Y年%m月%d日')
                                                    date_display = f" | 効力発生日: **{formatted_date}**"
                                                except (ValueError, TypeError):
                                                    date_display = f" | 効力発生日: **{valid_date_str}**"
                                            metadata_str = f"{title_prefix}{date_display} | Source: **{source_file_display}#{fw_res['line_number']}** | Score: {fw_res['@search.score']:.4f}"
                                            res_c1, res_c2 = st.columns([0.8, 0.2])
                                            with res_c1: st.markdown(metadata_str)
                                            with res_c2: st.markdown(f'<a href="?view_treaty={urllib.parse.quote(source_file)}" target="_blank" rel="noopener noreferrer">条約全文を開く</a>', unsafe_allow_html=True)

                                            if is_ja_q_for_highlight:
                                                ja_html_highlighted = merge_server_highlights(res_ja, ja_snips) if ja_snips else client_side_highlight(res_ja, fw_query)
                                                en_html_highlighted = _escape_html(res_en)
                                            else:
                                                en_html_highlighted = merge_server_highlights(res_en, en_snips) if en_snips else client_side_highlight(res_en, fw_query)
                                                ja_html_highlighted = _escape_html(res_ja)
                                            st.markdown(f"**英語原文:**<br>{en_html_highlighted}", unsafe_allow_html=True)
                                            st.markdown(f"**日本語訳:**<br>{ja_html_highlighted}", unsafe_allow_html=True)


                    # 1. AI翻訳結果
                    if "ai_translation" in sentence_data and sentence_data["ai_translation"]:
                        st.markdown("---")
                        st.markdown("🔤**AI翻訳結果:**")
                        translation_data = sentence_data["ai_translation"]
                        with st.container(border=True):
                            display_text = f"{translation_data['text']} (翻訳スコア: {translation_data['score']:.2f})"
                            st.markdown(display_text.replace('\n', '  \n'))
                        translated_text = translation_data['text']
                        if st.button("📝 平仄確認処理", key=f"check_text_{i}"):
                            original_text_to_pass = sentence_data.get('text', '')
                            url_to_open = f"?check_text={urllib.parse.quote(translated_text)}&original_text={urllib.parse.quote(original_text_to_pass)}"

                            st.components.v1.html(f"<script>window.open('{url_to_open}', '_blank');</script>", height=0)

                    # 2. 適用する辞書用語
                    if "found_terms" in sentence_data:
                        st.markdown("---")
                        if sentence_data["found_terms"]:
                            st.markdown("📖**適用する辞書用語を選択:**")
                            with st.container(border=True):
                                header_cols = st.columns([0.1, 0.45, 0.45])
                                header_cols[0].markdown("**適用**")
                                header_cols[1].markdown("**英語原文**")
                                header_cols[2].markdown("**日本語訳**")
                                for term_idx, term_data in enumerate(sentence_data["found_terms"]):
                                    st.markdown("<div style='background-color: #ddd; height: 1px; margin: 10px 0;'></div>", unsafe_allow_html=True)
                                    row_cols = st.columns([0.1, 0.45, 0.45], vertical_alignment="center")
                                    with row_cols[0]:
                                        is_checked = st.checkbox(" ", value=term_data["checked"], key=f"term_check_{i}_{term_idx}", label_visibility="collapsed")
                                        st.session_state.segmented_sentences[i]["found_terms"][term_idx]["checked"] = is_checked
                                    with row_cols[1]:
                                        en_term = term_data["en"]
                                        en_url = f"?search_term={urllib.parse.quote(en_term)}"
                                        st.markdown(f'<a href="{en_url}" target="_blank" style="text-decoration: none;">{en_term}</a>', unsafe_allow_html=True)
                                    with row_cols[2]:
                                        ja_term = term_data["ja"]
                                        ja_url = f"?search_term={urllib.parse.quote(ja_term)}"
                                        st.markdown(f'<a href="{ja_url}" target="_blank" style="text-decoration: none;">{ja_term}</a>', unsafe_allow_html=True)
                        else:
                            st.info("📖 該当する登録辞書用語はありませんでした。")

                    # 3. 類似文検索結果
                    if sentence_data.get("search_results"):
                        st.markdown("---")
                        st.markdown("🔍**類似文検索結果:**（翻訳の参照として使用する行を選択してください）")
                        query_for_highlight = sentence_data['text']
                        is_ja_q_for_highlight = st.session_state.get("is_last_query_ja", is_japanese(query_for_highlight))
                        for j, result_item in enumerate(sentence_data["search_results"]):
                            with st.container(border=True):
                                check_col, content_col = st.columns([0.08, 0.92])
                                with check_col:
                                    is_checked = st.checkbox(" ", value=result_item.get("checked", False), key=f"res_check_{i}_{j}", label_visibility="collapsed", help="この行を翻訳の参照に含める")
                                    st.session_state.segmented_sentences[i]["search_results"][j]["checked"] = is_checked
                                with content_col:
                                    res_en, res_ja, source_file = result_item.get("en_text", ""), result_item.get("jp_text", ""), result_item.get("sourceFile", "")
                                    highlights = result_item.get("@search.highlights") or {}
                                    en_snips, ja_snips = highlights.get("en_text", []), highlights.get("jp_text", [])
                                    jp_title_tab2 = result_item.get("jp_title", "")
                                    source_file_display_tab2 = source_file.replace(".csv", ".pdf")
                                    title_prefix_tab2 = f"**{jp_title_tab2}**" if jp_title_tab2 else ""
                                    valid_date_str = result_item.get("valid_date", "")
                                    date_display_tab2 = ""
                                    if valid_date_str:
                                        try:
                                            formatted_date = datetime.fromisoformat(valid_date_str.replace('Z', '+00:00')).strftime('%Y年%m月%d日')
                                            date_display_tab2 = f" | 効力発生日: **{formatted_date}**"
                                        except (ValueError, TypeError):
                                            date_display_tab2 = f" | 効力発生日: **{valid_date_str}**"
                                    metadata_str = f"{title_prefix_tab2}{date_display_tab2} | Source: **{source_file_display_tab2}#{result_item['line_number']}** | Score: {result_item['@search.score']:.4f}"
                                    res_col1_tab2, res_col2_tab2 = st.columns([0.8, 0.2])
                                    with res_col1_tab2: st.markdown(metadata_str)
                                    with res_col2_tab2: st.markdown(f'<a href="?view_treaty={urllib.parse.quote(source_file)}" target="_blank" rel="noopener noreferrer">条約全文を開く</a>', unsafe_allow_html=True)
                                    if is_ja_q_for_highlight:
                                        ja_html_highlighted = merge_server_highlights(res_ja, ja_snips) if ja_snips else client_side_highlight(res_ja, query_for_highlight)
                                        en_html_highlighted = _escape_html(res_en)
                                    else:
                                        en_html_highlighted = merge_server_highlights(res_en, en_snips) if en_snips else client_side_highlight(res_en, query_for_highlight)
                                        ja_html_highlighted = _escape_html(res_ja)
                                    st.markdown(f"**英語原文:**<br>{en_html_highlighted}", unsafe_allow_html=True)
                                    st.markdown(f"**日本語訳:**<br>{ja_html_highlighted}", unsafe_allow_html=True)

    with tab_maintenance:
        display_maintenance_page()