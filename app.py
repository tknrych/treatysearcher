import streamlit as st
import urllib.parse

<<<<<<< HEAD
# ---------- 初期化 ----------
load_dotenv()

# ---------- クライアント初期化 ----------
@st.cache_resource
def init_db():
    """データベース接続を初期化し、コネクションを返す"""
    db_path = os.getenv("DATABASE_PATH")
    return sqlite3.connect(db_path, check_same_thread=False)

@st.cache_data  # このデコレータを追加
def load_all_terms(_conn):
    """DBから全用語をロードする（キャッシュ用）"""
    cursor = _conn.cursor()
    cursor.execute("SELECT english_term, japanese_term FROM terms")
    return cursor.fetchall()

def find_glossary_terms(text: str, conn) -> dict:
    """
    与えられたテキスト内から用語集に登録されている英単語を正規表現で効率的に検索し、
    { 英単語: [日本語訳1, 日本語訳2, ...] } の形式の辞書で返す
    """
    all_terms = load_all_terms(conn) # キャッシュされた結果を呼び出す
    if not all_terms:
        return {}

    # --- 変更点 1: 1つの英語に対し、複数の日本語訳をリストで格納する ---
    term_map = {}
    for en_term, ja_term in all_terms:
        if en_term not in term_map:
            term_map[en_term] = []
        term_map[en_term].append(ja_term)
    # ----------------------------------------------------------------

    # 長い単語からマッチさせるために、キー（英単語）の長さで降順ソート
    sorted_terms = sorted(term_map.keys(), key=len, reverse=True)

    # 単語境界(\b)を使い、意図しない部分一致を防ぐ正規表現パターンを作成
    pattern = r'\b(' + '|'.join(re.escape(term) for term in sorted_terms) + r')\b'

    # 大文字小文字を区別せずに、テキスト中に出現するすべての用語を検索
    matches = re.finditer(pattern, text, re.IGNORECASE)

    # 見つかった単語（重複なし）とその日本語訳リストを格納する
    found_terms = {}
    # --- 変更点 2: lower_term_map もリストを扱えるようにする ---
    lower_term_map = {en.lower(): (en, ja_list) for en, ja_list in term_map.items()}
    # --------------------------------------------------------

    for match in matches:
        matched_text_lower = match.group(1).lower()
        if matched_text_lower in lower_term_map:
            # --- 変更点 3: ja_term ではなく ja_list を受け取る ---
            original_en, ja_list = lower_term_map[matched_text_lower]
            if original_en not in found_terms:
                found_terms[original_en] = ja_list
            # ---------------------------------------------------

    return found_terms

@st.cache_resource
def get_clients():
    search = SearchClient(
        endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
        index_name=os.getenv("AZURE_SEARCH_INDEX"),
        credential=AzureKeyCredential(os.getenv("AZURE_SEARCH_API_KEY")),
    )
    aoai = AzureOpenAI(
        api_key=os.getenv("AZURE_AIS_OPENAI_API_KEY"),
        azure_endpoint=os.getenv("AZURE_AIS_OPENAI_ENDPOINT"),
        api_version=os.getenv("AZURE_AIS_OPENAI_API_VERSION")
    )
    gpt_model = os.getenv("AZURE_AIS_OPENAI_GPT_DEPLOYMENT")
    embed_model = os.getenv("AZURE_AIS_OPENAI_EMBED_DEPLOYMENT")
    return search, aoai, gpt_model, embed_model

search, aoai, GPT_MODEL, EMBED_MODEL = get_clients()

# --- 日本語の対応表を定義 ---
# 品詞 (Universal POS tags) の日本語対応表
pos_tag_japanese = {
    'PROPN': '固有名詞', 'NOUN': '名詞', 'VERB': '動詞', 'ADJ': '形容詞',
    'ADV': '副詞', 'ADP': '前置詞', 'AUX': '助動詞', 'CCONJ': '等位接続詞',
    'SCONJ': '従位接続詞', 'DET': '限定詞', 'INTJ': '間投詞', 'NUM': '数詞',
    'PART': '助詞', 'PRON': '代名詞', 'PUNCT': '句読点', 'SYM': '記号',
    'X': 'その他', 'SPACE': 'スペース'
}
# 係り受け関係 (Universal Dependency Relations) の日本語対応表
deprel_japanese = {
    'nsubj': '名詞主語', 'obj': '目的語', 'iobj': '間接目的語', 'csubj': '節主語',
    'ccomp': '節補語', 'xcomp': '制御補語', 'obl': '斜格補語', 'vocative': '呼格',
    'expl': '虚辞', 'dislocated': '転位', 'advcl': '副詞節修飾', 'advmod': '副詞修飾',
    'discourse': '談話要素', 'aux': '助動詞', 'cop': 'コピュラ', 'mark': '標識',
    'nmod': '名詞修飾', 'appos': '同格', 'nummod': '数詞修飾', 'acl': '節修飾',
    'amod': '形容詞修飾', 'det': '限定詞', 'clf': '類別詞', 'case': '格表示',
    'conj': '接続詞', 'cc': '等位接続詞', 'fixed': '固定表現', 'flat': '平坦構造',
    'compound': '複合語', 'list': 'リスト', 'parataxis': '並列', 'orphan': '孤児',
    'goeswith': '連接', 'reparandum': '訂正', 'punct': '句読点', 'root': '文の根',
    'dep': '不明な依存関係', 'prep': '前置詞修飾', 'agent': '動作主', 'attr': '属性',
    'dobj': '直接目的語', 'pobj': '前置詞の目的語', 'pcomp': '前置詞の補語',
    'relcl': '関係節修飾'
}

# ---------- ヘルパー関数 ----------
def is_japanese(text: str) -> bool:
    return re.search(r"[\u3040-\u30ff\u3400-\u9fff]", text) is not None

@Language.component("pysbd_sentencizer")
def pysbd_sentence_boundaries(doc):
    lang_code = "ja" if is_japanese(doc.text) else "en"
    seg = pysbd.Segmenter(language=lang_code, clean=False, char_span=True)
    sents_char_spans = seg.segment(doc.text)
    start_char_indices = {s.start for s in sents_char_spans}
    for token in doc:
        token.is_sent_start = True if token.i == 0 or token.idx in start_char_indices else False
    return doc

# ---------- NLPモデルのロード ----------
@st.cache_resource
def load_nlp_model(model_name="en_core_web_lg"):
    try:
        nlp = spacy.load(model_name)
        nlp.add_pipe("pysbd_sentencizer", before="parser")
        return nlp
    except OSError:
        st.warning(f"spaCyモデル '{model_name}' のロードに失敗しました。")
        return None

@st.cache_resource
def load_stanza_model():
    """Stanzaの英語モデルをダウンロードしてロードする。GPUが利用可能なら使用する。"""
    try:
        # GPUが利用可能かチェック
        use_gpu = torch.cuda.is_available()      
        stanza.download('en')
        return stanza.Pipeline('en', use_gpu=use_gpu)
    except Exception as e:
        st.error(f"Stanzaモデルのロード中にエラーが発生しました: {e}")
        return None

nlp = load_nlp_model()
stanza_nlp = load_stanza_model()

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
    return html.escape(s, quote=False)

def merge_server_highlights(full_text: str, highlight_snippets: list[str]) -> str:
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
    if not full_text or not query:
        return _escape_html(full_text)
    text = _escape_html(full_text)
    clean_query = query.strip().strip('"')
    q_esc = _escape_html(clean_query)
    if q_esc:
        pattern = re.compile(re.escape(q_esc), re.IGNORECASE)
        text = pattern.sub(lambda m: f"<em>{m.group(0)}</em>", text)
    return text

def evaluate_translation(original_text: str, translated_text: str) -> float:
    """翻訳の品質を評価し、0.0から1.0のスコアを返す。"""
    system_prompt = "あなたは、翻訳品質を厳格に評価する専門家です。与えられた指示に従い、評価スコアのみを出力してください。"
    user_prompt = f"""以下の英語原文と日本語訳を比較し、翻訳の品質を評価してください。

## 評価基準
- **正確性**: 誤訳がなく、原文の意図が正しく伝わっているか。
- **完全性**: 翻訳漏れ（単語、フレーズ、文）がないか。
- **自然さ**: 日本語として不自然な表現がないか。

## 出力形式
評価スコアを `Score: <0.0から1.0までの数値>` の形式で、数値のみを出力してください。
例: `Score: 0.95`

---

## 評価対象
<original_en>{original_text}</original_en>
<translation_jp>{translated_text}</translation_jp>

## あなたの評価
<answer>
Score:
"""
    try:
        response = aoai.chat.completions.create(
            model=GPT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.0,
            max_tokens=10,
        )
        result_text = response.choices[0].message.content or ""
        match = re.search(r"([0-9.]+)", result_text)
        if match:
            return float(match.group(1))
        st.warning(f"翻訳スコアの解析に失敗しました。レスポンス: '{result_text}'")
        return 0.0
    except Exception as e:
        st.error(f"翻訳評価中にエラーが発生しました: {e}")
        return 0.0

def _get_single_translation(text_to_translate: str, context_english: str, context_japanese: str, glossary: dict, previous_translation: str = None) -> str:
    """指定された英文を翻訳する内部関数。用語集の指示を追加。"""
    system_prompt = "あなたは、外務省の優秀な翻訳官です。条約のような、法的拘束力を持つ厳格な文書の翻訳を専門としています。与えられた指示に一字一句正確に従ってください。"
    
    # 用語集の指示を作成
    glossary_instruction = ""
    if glossary:
        glossary_items = "\n".join([f"- `{en}` -> `{ja}`" for en, ja in glossary.items()])
        glossary_instruction = f"""## 用語集（最優先）
下記の用語集を**必ず**使用し、指定通りの日本語訳を適用してください。
{glossary_items}

"""
    
    instruction = f"""{glossary_instruction}1.  下記の各例文を**最優先の模範**とし、その構造と書式を厳密に模倣してください。
2.  **最重要**: 複雑な修飾語句がどの名詞に係るのか（係り受け）を正確に反映してください。
3.  **書式ルール**:
    - **日付**: `2005年`は`二千〇五年`ではなく`二千五年`のように、公文書として一般的な漢数字で表記してください。`2000年`は`二千年`とします。
    - **金額**: `七十九億...円（七、九三三、...円）`のように、**位取りを含んだ漢数字**と、括弧書きで**カンマ区切りのアラビア数字**を必ず併記してください。
4.  参照情報（英語原文と現在の日本語訳）の文体や用語を最大限に尊重し、`<translate_this>`内の英文のみを翻訳します。
5.  最終的な翻訳結果の**本文のみ**を出力してください。解説や`<answer>`のようなタグは一切含めないでください。"""
    
    if previous_translation:
        instruction = f"""以前の翻訳には誤りがありました。
<previous_bad_translation>{previous_translation}</previous_bad_translation>
この誤りを厳密に修正し、下記の指示と例文に合致する、より正確で自然な翻訳を生成してください。\n\n""" + instruction
    
    syntax_example_en = "RECOGNISING the previous activities carried out by the GIF under the Framework Agreement for International Collaboration on Research and Development of Generation IV Nuclear Energy Systems, done at Washington on 28 February 2005, as extended by the Agreement to Extend the Framework Agreement, which entered into force on 26 February 2015 (hereinafter referred to as the ‘2005 GIF Framework Agreement’), which expires on 28 February 2025..."
    syntax_example_jp = "二千二十五年二月二十八日に期間満了する、二千五年二月二十八日にワシントンで作成された第4世代原子力システムの研究開発に関する国際協力のための枠組み協定であって、二千十五年二月二十六日に発効した同協定を延長する協定により延長されたもの（以下「二千五年GIF枠組み協定」という。）の下でGIFが実施したこれまでの活動...を認識し、"
    format_example_en = "The total amount of the Debts will be five hundred and thirty-eight million nine hundred and seven thousand one hundred and forty-two yen (\\7,933,321,265) on December 8, 2025."
    format_example_jp = "債務の総額は、二千二十五年十二月八日に、七十九億三千三百三十二万千二百六十五円（七、九三三、三二一、二六五円）になる。"
    user_prompt = f"""あなたは、提供された参照情報に基づき、指定された英文を翻訳する任務を負っています。
## 指示
{instruction}
---
## 例文1: 複雑な構文
<example>
    <context_en>{syntax_example_en}</context_en>
    <context_jp>{syntax_example_jp}</context_jp>
    <translate_this>RECOGNISING the Framework Agreement, done at Washington on 28 February 2005, which expires on 28 February 2025</translate_this>
    <answer>二千二十五年二月二十八日に期間満了する、二千五年二月二十八日にワシントンで作成された枠組み協定を認識し、</answer>
</example>
## 例文2: 日付と金額の書式
<example>
    <context_en>{format_example_en}</context_en>
    <context_jp>{format_example_jp}</context_jp>
    <translate_this>The total amount will be five hundred and thirty-eight million yen (\\538,000,000).</translate_this>
    <answer>債務の総額は、五億三千八百万円（五三八、〇〇〇、〇〇〇円）になる。</answer>
</example>
---
## あなたのタスク (Your Task)
<task>
    <context_en>{context_english}</context_en>
    <context_jp>{context_japanese}</context_jp>
    <translate_this>{text_to_translate}</translate_this>
    <answer>
</task>
"""
    try:
        response = aoai.chat.completions.create(model=GPT_MODEL, messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], temperature=0.0, stop=["</answer>"])
        return (response.choices[0].message.content or "翻訳結果を取得できませんでした。").strip()
    except Exception as e:
        return f"翻訳中にエラーが発生しました: {e}"

@st.cache_data(show_spinner=False)
def get_translation_with_retry(text_to_translate: str, context_english: str, context_japanese: str, glossary: dict) -> tuple[str, float]:
    MAX_RETRIES, SCORE_THRESHOLD, best_translation, best_score = 3, 0.9, "", -1.0
    if not GPT_MODEL: 
        return "翻訳機能に必要なGPTモデルのデプロイ名が設定されていません。", 0.0

    # 適用する用語集があればUIに表示
    if glossary:
        st.info(f"選択された用語を適用します: {glossary}")

    for i in range(MAX_RETRIES):
        with st.spinner(f"翻訳を生成中... (試行 {i+1}/{MAX_RETRIES})"):
            # _get_single_translation に UIから渡された glossary を渡す
            current_translation = _get_single_translation(text_to_translate, context_english, context_japanese, glossary, best_translation if i > 0 else None)
            if "翻訳中にエラーが発生しました" in current_translation: 
                return current_translation, 0.0
            current_score = evaluate_translation(text_to_translate, current_translation)
            st.write(f"試行 {i+1}: スコア = {current_score:.2f}, 翻訳 = '{current_translation}'")
            if current_score > best_score:
                best_score, best_translation = current_score, current_translation
            if best_score >= SCORE_THRESHOLD:
                st.write(f"品質基準 ({SCORE_THRESHOLD}) を満たしました。")
                break
    return best_translation, best_score

def perform_search(query_text: str, enable_title_search: bool, mode_override: str = None, match_type_override: str = None) -> tuple[list, str]:
    """
    Azure Search を実行する。
    mode_override と match_type_override を指定することで、UIの設定を無視して検索方法を強制できる。
    """
    t0 = time.perf_counter()
    
    # 引数で指定があればそれを使い、なければUI（session_state）から設定を取得
    mode_now = mode_override if mode_override is not None else st.session_state.get("mode_radio", "ハイブリッド (文字列検索 + あいまい検索)")
    match_type_now = match_type_override if match_type_override is not None else st.session_state.get("match_type_radio", "部分一致 (OR)")
    
    lang_mode = st.session_state.get("lang_mode_radio", "言語自動判定")
    
    is_title_search = enable_title_search

    if is_title_search:
        is_ja_q, text_fields, vec_field, mode_now = True, ["jp_title"], "japaneseVector", "文字列検索のみ"
    else:
        is_ja_q = is_japanese(query_text) if lang_mode == "言語自動判定" else (lang_mode == "日本語")
        text_fields, vec_field = (["jp_text"], "japaneseVector") if is_ja_q else (["en_text"], "englishVector")
    
    # 「完全一致」が指定された場合は、クエリをダブルクォートで囲む
    search_q = f'"{query_text.strip()}"' if match_type_now == "完全一致 (Phrase)" else query_text.strip()
    
    common_kwargs = dict(select=["en_text", "jp_text", "sourceFile", "line_number", "jp_title", "valid_date"], top=st.session_state.get("topk_slider", 10), include_total_count=True)

    odata_filters = []
    if st.session_state.get("date_filter_enabled", False):
        start_date = st.session_state.get("start_date")
        end_date = st.session_state.get("end_date")
        
        # 日付の妥当性を再度チェック
        if start_date and end_date and start_date <= end_date:
            # Azure SearchはDateTimeOffset形式を要求するため、ISO 8601形式のUTCで指定
            # 開始日はその日の始まり (00:00:00Z)
            start_date_str = datetime.combine(start_date, datetime.min.time()).isoformat() + "Z"
            # 終了日はその日の終わり (23:59:59Z)
            end_date_str = datetime.combine(end_date, datetime.max.time()).isoformat() + "Z"
            
            date_filter_query = f"valid_date ge {start_date_str} and valid_date le {end_date_str}"
            odata_filters.append(date_filter_query)
    
    if odata_filters:
        common_kwargs['filter'] = " and ".join(odata_filters)

    if is_title_search: 
        common_kwargs["order_by"] = "line_number asc"
    
    search_args = {}
    if mode_now in ["ハイブリッド (文字列検索 + あいまい検索)", "文字列検索のみ"]:
        search_args.update({'search_text': search_q, 'search_fields': text_fields, 'highlight_fields': ",".join(text_fields), 'highlight_pre_tag': "<em>", 'highlight_post_tag': "</em>"})
    
    if mode_now in ["ハイブリッド (文字列検索 + あいまい検索)", "あいまい検索のみ"]:
        try:
            emb = aoai.embeddings.create(model=EMBED_MODEL, input=[query_text]).data[0].embedding
            search_args['vector_queries'] = [VectorizedQuery(vector=emb, fields=vec_field, k_nearest_neighbors=st.session_state.get("kvec_slider", 30))]
        except Exception as e: st.warning(f"Embeddingの作成に失敗しました: {e}")
    
    if not search_args:
        st.error("検索引数を構築できませんでした。")
        return [], ""
    
    results = search.search(**common_kwargs, **search_args)
    result_list = list(results)
    
    # 表示用のメタデータを作成
    display_match_type = "完全一致" if match_type_now == "完全一致 (Phrase)" else "部分一致"
    metadata = f"検索モード: **{mode_now} ({display_match_type})** | 言語: {lang_mode} | Top={common_kwargs['top']} | Time: {(time.perf_counter() - t0) * 1000:.1f} ms | Hits: {results.get_count()}"
    
    st.session_state.is_last_query_ja = is_ja_q
    return result_list, metadata

@st.cache_data(show_spinner="条約全文を取得中...")
def fetch_full_treaty_text(source_file: str) -> list:
    """指定されたsourceFileの全チャンクを行番号順に取得する"""
    try:
        escaped_source_file = source_file.replace("'", "''")
        odata_filter = f"sourceFile eq '{escaped_source_file}'"
        results = search.search(
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

# ==============================================================================
# ---------- UI描画ロジック ----------
# ==============================================================================

def display_analysis_page(text_to_analyze: str):
    """原文解析専用ページの描画"""
    st.title("⚙️原文の係り受け解析")
    st.markdown("---")
    st.markdown(f"**解析対象テキスト:**")
    st.markdown(f"> {text_to_analyze.replace(chr(10), chr(10) + '> ')}")
    st.markdown("---")
    if not stanza_nlp:
        st.error("Stanzaモデルがロードされていません。")
        return
    try:
        doc = stanza_nlp(text_to_analyze)
        dot = graphviz.Digraph(graph_attr={'rankdir': 'TB'}, node_attr={'shape': 'record', 'fontname': 'sans-serif'}, edge_attr={'fontsize': '10', 'fontname': 'sans-serif'})
        for sent in doc.sentences:
            for word in sent.words:
                node_id = f"{sent.index+1}_{word.id}"
                pos_ja = pos_tag_japanese.get(word.upos, word.upos)
                dot.node(node_id, label=f"{{{word.text}|{pos_ja}}}")
            for word in sent.words:
                if word.head > 0:
                    head_id = f"{sent.index+1}_{word.head}"
                    node_id = f"{sent.index+1}_{word.id}"
                    deprel_ja = deprel_japanese.get(word.deprel, word.deprel)
                    dot.edge(head_id, node_id, label=deprel_ja)
        st.write("### 解析結果")
        st.graphviz_chart(dot)
    except Exception as e:
        st.error(f"テキスト解析中にエラーが発生しました: {e}")

def display_full_treaty_page(treaty_id: str):
    """全文表示専用ページの描画"""
    treaty_title = ""
    try:
        escaped_treaty_id = treaty_id.replace("'", "''")
        odata_filter = f"sourceFile eq '{escaped_treaty_id}'"
        results = search.search(
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
    if full_treaty_chunks := fetch_full_treaty_text(treaty_id):
        full_en_text = "\n\n".join([c.get("en_text", "") for c in full_treaty_chunks])
        full_ja_text = "\n\n".join([c.get("jp_text", "") for c in full_treaty_chunks])
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("日本語全文")
            st.text_area("Japanese Full Text", full_ja_text, height=800, key="modal_ja_text", label_visibility="collapsed")
        with col2:
            st.subheader("英語全文")
            st.text_area("English Full Text", full_en_text, height=800, key="modal_en_text", label_visibility="collapsed")
    else:
        st.error("全文データの取得に失敗しました。")

def display_maintenance_page():
    """辞書データの編集ページの描画と機能"""
    st.subheader("辞書データの編集")
    st.info("テーブルを直接編集し、「変更を保存」ボタンを押してください。行の追加・削除も可能です。")
    
    conn = init_db()
    
    # --- 現在のデータを読み込んで表示 ---
    try:
        # st.data_editorで扱いやすいようにPandas DataFrameとして読み込む
        db_df = pd.read_sql_query("SELECT id, english_term, japanese_term FROM terms ORDER BY english_term", conn)
        
        # ユーザーが編集するためのデータエディタを表示
        edited_df = st.data_editor(
            db_df,
            column_config={
                "id": st.column_config.NumberColumn("ID", disabled=True), # IDは編集不可にする
                "english_term": "英語原文",
                "japanese_term": "日本語訳",
            },
            num_rows="dynamic", # 行の追加と削除を有効にする
            key="glossary_editor",
            width='stretch'
        )

        if st.button("変更を保存 💾", type="primary"):
            cursor = conn.cursor()
            
            # --- 変更前後の差分を見つけてDBに反映 ---
            orig_ids = set(db_df['id'])
            edited_ids = set(edited_df['id'].dropna()) # 新規行はIDがNaNなので除外
            
            # 1. 削除された行を特定
            deleted_ids = orig_ids - edited_ids
            if deleted_ids:
                cursor.executemany("DELETE FROM terms WHERE id = ?", [(id,) for id in deleted_ids])
                st.write(f"🗑️ {len(deleted_ids)}件の用語を削除しました。")

            # 2. 追加された行を特定
            new_rows = edited_df[edited_df['id'].isna()]
            if not new_rows.empty:
                insert_data = [
                    (row['english_term'], row['japanese_term'])
                    for _, row in new_rows.iterrows()
                    if pd.notna(row['english_term']) and pd.notna(row['japanese_term']) # 空の行は無視
                ]
                if insert_data:
                    cursor.executemany(
                        "INSERT INTO terms (english_term, japanese_term) VALUES (?, ?)",
                        insert_data
                    )
                    st.write(f"✨ {len(insert_data)}件の用語を追加しました。")

            # 3. 変更された行を特定
            # 変更前のデータとマージして、値が異なる行を見つける
            comparison_df = pd.merge(db_df, edited_df, on='id', how='inner', suffixes=('_orig', '_new'))

            # 変更があったかどうかを判定するマスクを初期化
            update_mask = pd.Series([False] * len(comparison_df))

            # 'english_term' カラムの変更をチェック
            if 'english_term_orig' in comparison_df.columns and 'english_term_new' in comparison_df.columns:
                update_mask |= (comparison_df['english_term_orig'] != comparison_df['english_term_new'])

            # 'japanese_term' カラムの変更をチェック
            if 'japanese_term_orig' in comparison_df.columns and 'japanese_term_new' in comparison_df.columns:
                update_mask |= (comparison_df['japanese_term_orig'] != comparison_df['japanese_term_new'])

            updated_rows = comparison_df[update_mask]            
            if not updated_rows.empty:
                update_data = [
                    (row['english_term_new'], row['japanese_term_new'], row['id'])
                    for _, row in updated_rows.iterrows()
                ]
                cursor.executemany(
                    "UPDATE terms SET english_term = ?, japanese_term = ? WHERE id = ?",
                    update_data
                )
                st.write(f"✏️ {len(update_data)}件の用語を更新しました。")

            conn.commit()
            load_all_terms.clear()
            st.success("データベースの変更が正常に保存されました！")
            st.rerun() # 画面を再読み込みして最新の状態を表示

    except Exception as e:
        st.error(f"データベース操作中にエラーが発生しました: {e}")
        st.warning("`glossary.db`に`terms`テーブルが存在し、`id`, `english_term`, `japanese_term`カラムがあることを確認してください。")

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
    # 今後の機能拡張のために、編集後のテキストは edited_text 変数で受け取っておきます。

def display_term_search_results_page(term: str):
    """用語の完全一致検索の結果を専用ページに表示する"""
    st.title(f"🔍 用語検索結果: \"{term}\"")
    st.info("指定された用語での完全一致検索結果を表示します。")

    # 既存の検索関数を「完全一致」で実行
    # 検索キーワードをダブルクォーテーションで囲むと完全一致検索になる
    results, metadata = perform_search(
        query_text=term, 
        enable_title_search=False,
        mode_override="文字列検索のみ",
        match_type_override="完全一致 (Phrase)"
    )

    st.caption(metadata)
    st.divider()

    if not results:
        st.warning("検索結果が見つかりませんでした。")
        return

    # 類似文検索結果と同じレイアウトで結果を表示
    for result_item in results:
        res_en, res_ja, source_file = result_item.get("en_text", ""), result_item.get("jp_text", ""), result_item.get("sourceFile", "")
        jp_title = result_item.get("jp_title", "")
        valid_date = result_item.get("valid_date", "") # valid_date を取得
        source_file_display = source_file.replace(".csv", ".pdf")
        
        title_prefix = f"**{jp_title}**" if jp_title else ""
        valid_date_str = result_item.get("valid_date", "")
        date_display = ""
        if valid_date_str:
            try:
                # ISO形式の日付文字列をdatetimeオブジェクトに変換し、指定の書式にフォーマット
                formatted_date = datetime.fromisoformat(valid_date_str.replace('Z', '+00:00')).strftime('%Y年%m月%d日')
                date_display = f" | 効力発生日: **{formatted_date}**"
            except (ValueError, TypeError):
                # パースに失敗した場合は、元の文字列をそのまま表示
                date_display = f" | 効力発生日: **{valid_date_str}**"

        metadata_str = f"{title_prefix}{date_display} | Source: **{source_file_display}#{result_item['line_number']}** | Score: {result_item['@search.score']:.4f}"

        res_col1, res_col2 = st.columns([0.8, 0.2])
        with res_col1: st.markdown(metadata_str)
        with res_col2: st.markdown(f'<a href="?view_treaty={urllib.parse.quote(source_file)}" target="_blank" rel="noopener noreferrer">条約全文を開く</a>', unsafe_allow_html=True)
        
        # ハイライト処理
        if is_japanese(term):
            en_html_highlighted = _escape_html(res_en)
            ja_html_highlighted = client_side_highlight(res_ja, term)
        else:
            en_html_highlighted = client_side_highlight(res_en, term)
            ja_html_highlighted = _escape_html(res_ja)        
        st.markdown(f"**英語原文:**<br>{en_html_highlighted}", unsafe_allow_html=True)
        st.markdown(f"**日本語訳:**<br>{ja_html_highlighted}", unsafe_allow_html=True)
        st.divider()

def display_search_interface():
    """メインの検索インターフェースを描画"""
    db_conn = init_db()

    # 安定化のため、テキストボックスの状態変数を最初に初期化
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
            # 1950年1月1日をデフォルトの開始日とする
            default_start = datetime(1950, 1, 1).date()
            
            start_date = st.date_input(
                "開始日", 
                value=default_start, 
                key="start_date"
            )
            end_date = st.date_input(
                "終了日", 
                value=today, 
                key="end_date"
            )

            # 日付の妥当性チェック
            if start_date > end_date:
                st.error("エラー: 終了日は開始日以降に設定してください。")

    tab_text_search, tab_title_search, tab_maintenance = st.tabs(["✍️ 条約本文検索", "📜 条約名検索", "📖 辞書データの編集"])

    with tab_title_search:
        st.subheader("条約名で検索")
        q_title = st.text_input("検索したい条約名（日本語）を入力してください", key="query_input_title")

        col1_title, col2_title, _ = st.columns([1, 1, 5])
        with col1_title:
            run_clicked_title = st.button("🔍条約名検索", key="search_button_title")
        with col2_title:
            st.button("🧹入力消去　　", key="clear_button_title", on_click=_clear_title_tab_results)

        if run_clicked_title and q_title.strip():
            st.session_state.last_query_title = q_title
            try:
                results, metadata = perform_search(q_title, enable_title_search=True)
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
                    # ハイライト結果があれば、それを結合して表示
                    highlighted_title = " ... ".join(highlighted_snippets)
                else:
                    # なければクライアントサイドでハイライト
                    query_to_display = st.session_state.last_query_title
                    highlighted_title = client_side_highlight(jp_title, query_to_display)                
                st.markdown(f"##### {highlighted_title}", unsafe_allow_html=True)
                res_col1, res_col2 = st.columns([0.75, 0.25])
                with res_col1:
                    valid_date_str = r.get("valid_date", "")
                    date_display = ""
                    if valid_date_str:
                        try:
                            # ISO形式の日付文字列をdatetimeオブジェクトに変換し、指定の書式にフォーマット
                            formatted_date = datetime.fromisoformat(valid_date_str.replace('Z', '+00:00')).strftime('%Y年%m月%d日')
                            date_display = f" | 効力発生日: **{formatted_date}**"
                        except (ValueError, TypeError):
                            # パースに失敗した場合は、元の文字列をそのまま表示
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
            # 「文章分割」ボタンが押された時だけNLPモデルの存在チェック
            elif not nlp and start_analysis_clicked:
                st.error("NLPモデルのロードに失敗しました。")
            else:
                st.session_state.segmented_sentences = []
                
                # 「文章分割」ボタンが押された場合の処理
                if start_analysis_clicked:
                    doc = nlp(mask_list_markers(pasted_text))
                    for sent in doc.sents:
                        if original_sent_text := unmask_list_markers(sent.text).strip():
                            st.session_state.segmented_sentences.append({"text": original_sent_text, "search_results": None})
                
                # 「文章分割しない」ボタンが押された場合の処理
                elif no_split_clicked:
                    # テキスト全体を一つの要素としてリストに追加
                    st.session_state.segmented_sentences.append({"text": pasted_text.strip(), "search_results": None})

        if "segmented_sentences" in st.session_state:
            st.markdown("---")
            
            num_sents = len(st.session_state.segmented_sentences)
            if num_sents > 1:
                st.write(f"▼ {num_sents} 件の文に分割されました ▼")
            else:
                st.write(f"▼ 1 件の文として処理します ▼")

            for i, sentence_data in enumerate(st.session_state.segmented_sentences):
                with st.expander(f"文 {i+1}: {sentence_data['text'][:80]}..."):
                    original_text = sentence_data['text']
                    st.markdown(f"📘**原文:**\n> {original_text.replace(chr(10), chr(10) + '> ')}")

                    # --- ボタンを中央に寄せるための列定義 ---
                    # [空白, ボタン1, ボタン2, ボタン3, ボタン4, 空白] の比率で列を作成
                    c1, c2, c3, c4, _, _ = st.columns([2, 2, 2, 2, 3, 3])

                    with c1: # 類似条約文検索ボタン
                        if st.button("🔍類似条約文検索", key=f"search_{i}"):
                            try:
                                results, metadata = perform_search(sentence_data['text'], enable_title_search=False)
                                st.session_state.segmented_sentences[i]["search_results"] = [{"checked": False, **res} for res in results]
                                if "ai_translation" in st.session_state.segmented_sentences[i]:
                                    del st.session_state.segmented_sentences[i]["ai_translation"]
                                st.rerun()
                            except Exception as e: st.error(f"検索中にエラーが発生しました: {e}")

                    with c2: # 係り受け解析ボタン
                        is_disabled = not (original_text and not is_japanese(original_text))
                        if st.button("⚙️ 係り受け解析", key=f"analysis_{i}", disabled=is_disabled, help="解析対象は英語の文のみです。"):
                            url_to_open = f"?analyze_text={urllib.parse.quote(original_text)}"
                            st.components.v1.html(f"<script>window.open('{url_to_open}', '_blank');</script>", height=0)

                    with c3: # 辞書参照ボタン
                        if st.button("📖登録辞書参照", key=f"glossary_{i}"):
                            found_terms_dict = find_glossary_terms(original_text, db_conn)
                            term_list_for_display = []
                            for en_term, ja_term_list in found_terms_dict.items():
                                for ja_term in ja_term_list:
                                    term_list_for_display.append(
                                        {"en": en_term, "ja": ja_term, "checked": False}
                                    )
                            st.session_state.segmented_sentences[i]["found_terms"] = term_list_for_display
                            st.rerun()

                    with c4: # 参照して日本語訳ボタン
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
                                    translation, score = get_translation_with_retry(original_text, context_english, context_japanese, glossary_to_use)
                                    st.session_state.segmented_sentences[i]["ai_translation"] = {"text": translation, "score": score}
                                    st.rerun()
                        else:
                            st.button("🔤参照して日本語訳", disabled=True, key=f"translate_all_{i}_disabled", help="先に類似文検索を実行してください。")

                    # 1. AI翻訳結果 (存在する場合のみ表示)
                    if "ai_translation" in sentence_data and sentence_data["ai_translation"]:
                        # ラベルをst.markdownで外出しにする
                        st.markdown("---")
                        st.markdown("🔤**AI翻訳結果:**")
                        translation_data = sentence_data["ai_translation"]
                        # st.infoには翻訳テキスト本体のみを表示
                        st.info(f"{translation_data['text']} (翻訳スコア: {translation_data['score']:.2f})")

                        translated_text = translation_data['text']
                        if st.button("📝 平仄確認処理", key=f"check_text_{i}"):
                            url_to_open = f"?check_text={urllib.parse.quote(translated_text)}"
                            st.components.v1.html(f"<script>window.open('{url_to_open}', '_blank');</script>", height=0)

                    # 2. 適用する辞書用語
                    # "found_terms"キーが存在するかどうか（=ボタンが押された後か）をチェック
                    if "found_terms" in sentence_data:
                        st.markdown("---")
                        # 用語リストが空でないかチェック
                        if sentence_data["found_terms"]:
                            st.markdown("📖**適用する辞書用語を選択:**")
                            separator_html = "<div style='background-color: #ddd; height: 1px; margin: 10px 0;'></div>"
                            with st.container(border=True):
                                header_cols = st.columns([0.1, 0.45, 0.45])
                                header_cols[0].markdown("**適用**")
                                header_cols[1].markdown("**英語原文**")
                                header_cols[2].markdown("**日本語訳**")
                                for term_idx, term_data in enumerate(sentence_data["found_terms"]):
                                    st.markdown(separator_html, unsafe_allow_html=True)
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
                            # 用語リストが空の場合のメッセージ
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
                                    is_checked = st.checkbox(
                                        " ",
                                        value=result_item.get("checked", False),
                                        key=f"res_check_{i}_{j}",
                                        label_visibility="collapsed",
                                        help="この行を翻訳の参照に含める"
                                    )
                                    st.session_state.segmented_sentences[i]["search_results"][j]["checked"] = is_checked

                                with content_col:
                                    res_en, res_ja, source_file = result_item.get("en_text", ""), result_item.get("jp_text", ""), result_item.get("sourceFile", "")
                                    highlights = result_item.get("@search.highlights") or {}
                                    en_snips, ja_snips = highlights.get("en_text", []), highlights.get("jp_text", [])
                                    jp_title_tab2 = result_item.get("jp_title", "")
                                    valid_date = result_item.get("valid_date", "") # valid_date を取得
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
=======
# 各ページの描画関数をインポート
from views.search_interface import display_search_interface
from views.full_treaty_page import display_full_treaty_page
from views.analysis_page import display_analysis_page
from views.term_search_page import display_term_search_results_page
from views.check_page import display_check_page
>>>>>>> feature/code-refactor

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
<<<<<<< HEAD
text_to_check_encoded = query_params.get("check_text") 
=======
text_to_check_encoded = query_params.get("check_text")
>>>>>>> feature/code-refactor

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
    display_check_page(decoded_text)
else:
    # デフォルトはメインの検索インターフェース
    display_search_interface()