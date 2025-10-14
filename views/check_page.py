import streamlit as st
import os
import time
import urllib.parse
from core.azure_clients import get_clients
from utils import find_non_joyo_kanji, _escape_html

# --- データ読み込み（共通関数） ---
@st.cache_data
def load_reference_doc(file_name: str):
    """
    指定された参照資料テキストファイルを読み込みます。
    """
    try:
        current_script_path = os.path.abspath(__file__)
        views_dir = os.path.dirname(current_script_path)
        project_root = os.path.dirname(views_dir)
        file_path = os.path.join(project_root, "ref_docs", file_name)
        
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        st.error(f"参照資料ファイルが見つかりません: {file_path}")
        return None

# --- 個別レビュー実行関数 ---
def perform_individual_review(document_text: str, definition: dict):
    """指定された参照資料に基づきレビューを実行し、結果を返す"""
    reference_name = definition["tab_name"]
    reference_data = load_reference_doc(definition["filename"])
    if not reference_data:
        return None, f"参照資料ファイル {definition['filename']} が見つかりませんでした。"

    try:
        _, aoai_client, gpt_model, _ = get_clients()
        system_prompt = f"""# 命令書
## あなたの役割
{definition["role"]}
## 参照資料
レビューの唯一の基準は、以下に提供する『{reference_name}』の全文です。
## 実行タスク
以下の【レビュー対象テキスト】を読み、【参照資料】に照らして、規則からの逸脱がないかを確認してください。逸脱箇所を発見した場合、その箇所、問題点、根拠、修正案を具体的に示してください。
## 出力形式
* **該当箇所:** ...
* **原文:** ...
* **指摘事項:** ...
* **根拠:** ...
* **修正案:** ...
---
上記の形式で、問題点を一つずつリストアップしてください。問題がない場合は、「指摘事項はありません。」とだけ記述してください。"""
        user_prompt = f"# 参照資料『{reference_name}』\n{reference_data}\n\n# レビュー対象テキスト\n{document_text}"
        
        response = aoai_client.chat.completions.create(
            model=gpt_model, messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            temperature=0.0, max_tokens=4000,
        )
        return response.choices[0].message.content, None
    except Exception as e:
        return None, f"レビュー実行中にエラーが発生しました: {e}"

# --- 統合レポート生成関数 ---
def generate_consolidated_report(document_text: str, non_joyo_report: str, individual_reports: dict, review_order: list):
    """個別のレビュー結果を統合し、最終レポートを生成する"""
    try:
        _, aoai_client, gpt_model, _ = get_clients()

        report_text = f"--- 常用漢字の確認結果 ---\n{non_joyo_report}"
        for name in review_order:
            if name in individual_reports:
                report_text += f"\n\n--- 以下の指摘は『{name}』に基づいています ---\n"
                report_text += individual_reports[name]

        system_prompt = f"""# 命令書
## あなたの役割
あなたは、日本の法制執務、公用文、条約邦訳に関する最高レベルの専門家です。あなたの任務は、提供された複数の専門家によるレビュー結果と常用漢字のチェック結果を統合し、矛盾を解決して、単一の最終的なレビューレポートを作成することです。

## 優先順位のルール
レビュー結果が矛盾・競合する場合は、**後に出てくる指摘（リストの下の方にある指摘）を絶対的なものとして優先して適用してください。** 例えば、「Aとすべき」という指摘と「Bとすべき」という指摘が同じ箇所に対してある場合、後に出てきた方の指摘を採用します。常用漢字に関する指摘は常に有効です。

## 実行タスク
以下の【個別のレビュー結果】を読み、上記の優先順位ルールに従って矛盾を解決し、最終的な指摘事項を統合・整理してください。同じ箇所に対する重複した指摘は一つにまとめてください。

## 出力形式
以下の形式で、最終的なレビュー結果を整理して出力してください。

---
### 総評
レビュー対象テキスト全体についての簡潔な最終評価を記述してください。

---
### 最終的な指摘事項
常用漢字に関する指摘、および各参照資料に基づく指摘をまとめてリストアップしてください。問題点を一つずつ、以下の項目でリストアップしてください。すべての問題を解決した結果、指摘事項がなくなった場合は、「指摘事項はありません。」と記述してください。

* **該当箇所:** 問題があるテキストの具体的な場所を記述してください。
* **原文:** 問題があるテキストの一文または一部分を引用してください。
* **指摘事項:** どのような点が規則に反しているかを具体的に説明してください。
* **根拠:** どの参照資料の規則に準拠しているか、最終的に採用された指摘の根拠（資料名または「常用漢字」）を引用して明確に示してください。
* **最終修正案:** 規則に沿った最終的な表現を提案してください。

---
"""
        user_prompt = f"# 個別のレビュー結果（優先度順）\n{report_text}\n\n# レビュー対象の原文\n{document_text}"
        
        response = aoai_client.chat.completions.create(
            model=gpt_model, messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            temperature=0.0, max_tokens=4000,
        )
        return response.choices[0].message.content, None
    except Exception as e:
        return None, f"統合レポート生成中にエラーが発生しました: {e}"

# --- メインの描画関数 ---
def display_check_page(text_to_check: str, original_text: str, reference_treaties: list = None):
    """文章校正・レビュー処理用の専用ページを描画"""
    st.set_page_config(layout="wide")
    st.title("📝 文章校正・レビュー処理")

    st.markdown("##### 📘英語原文")
    with st.container(border=True):
        st.markdown(original_text.replace('\n', '  \n'))

    st.markdown("##### 🔤AI翻訳結果")
    with st.container(border=True):
        st.markdown(text_to_check.replace('\n', '  \n'))

    st.markdown("##### ✅編集領域")
    edited_text = st.text_area(
        "レビュー対象テキスト",
        value=text_to_check,
        height=300,
        label_visibility="collapsed"
    )

    # 類似文参照データの表示
    if reference_treaties:
        st.markdown("---")
        st.markdown("🔍**参照用 類似条約文:**")
        for i, ref in enumerate(reference_treaties):
            with st.container(border=True):
                jp_title = ref.get("jp_title", "")
                source_file_display = ref.get("sourceFile", "").replace(".csv", ".pdf")
                title_prefix = f"**{jp_title}**" if jp_title else ""
                metadata_str = f"{title_prefix} | Source: **{source_file_display}#{ref.get('line_number', '')}** | Score: {ref.get('score', 0):.4f}"
                st.markdown(metadata_str)
                st.markdown(f"**英語原文:**<br>{_escape_html(ref.get('en_text', ''))}", unsafe_allow_html=True)
                st.markdown(f"**日本語訳:**<br>{_escape_html(ref.get('jp_text', ''))}", unsafe_allow_html=True)

    st.divider()

    # --- レビュー機能の定義（優先順位） ---
    review_definitions = [
        {"tab_name": "公用文作成の考え方", "filename": "ref_doc_7.txt", "role": "あなたは、分かりやすい公用文を作成する専門家です。"},
        {"tab_name": "法令用字用語必携", "filename": "ref_doc_3.txt", "role": "あなたは、日本の法令文書における用字用語の専門家です。"},
        {"tab_name": "最新公用文用字用語例集", "filename": "ref_doc_4.txt", "role": "あなたは、現代日本の公用文の表現に詳しい専門家です。"},
        {"tab_name": "法令用語の常識", "filename": "ref_doc_5.txt", "role": "あなたは、日本の法令用語に関する深い知識を持つ専門家です。"},
        {"tab_name": "新訂ワークブック法制執務", "filename": "ref_doc_2.txt", "role": "あなたは、日本の法制執務に精通した専門家です。"},
        {"tab_name": "条約邦文テキスト作成要領", "filename": "ref_doc_1.txt", "role": "あなたは、日本の内閣法制局または外務省条約局に所属する、条約の邦訳テキスト審査を専門とする熟練した担当官です。"}
    ]

    review_order = [d["tab_name"] for d in review_definitions]

    st.header("📚用字・用語統合確認")
    st.info("下のボタンを押すと、常用漢字チェックと全ての参照資料に基づいたレビューが順番に実行され、最後に単一の最終レポートが生成されます。処理には数分かかることがあります。")

    if st.button("統合レポートを生成する", type="primary"):
        if not edited_text.strip():
            st.warning("テキストが入力されていません。")
        else:
            if 'final_report' in st.session_state:
                del st.session_state.final_report
                
            individual_reports = {}
            error_occurred = False
            
            with st.status("レビュー処理を実行中...", expanded=True) as status:
                # 1. 常用漢字チェック
                st.write("ステップ1/8: 常用漢字を確認しています...")
                non_joyo_list = find_non_joyo_kanji(edited_text)
                if non_joyo_list:
                    non_joyo_report = f"常用漢字以外の漢字が見つかりました ({len(non_joyo_list)}字): {', '.join(non_joyo_list)}"
                else:
                    non_joyo_report = "常用漢字以外の漢字は見つかりませんでした。"
                st.write("✅ ステップ1/8: 常用漢字の確認が完了しました。")
                
                # 2. 個別レビューを順番に実行
                for i, definition in enumerate(review_definitions):
                    doc_name = definition["tab_name"]
                    st.write(f"ステップ{i+2}/8: 『{doc_name}』でレビューを実行しています...")
                    result, error = perform_individual_review(edited_text, definition)
                    if error:
                        st.error(f"『{doc_name}』のレビュー中にエラーが発生しました: {error}")
                        error_occurred = True
                        break
                    individual_reports[doc_name] = result
                    st.write(f"✅ ステップ{i+2}/8: 『{doc_name}』のレビューが完了しました。")
                    time.sleep(1) # APIレート制限を避けるための短い待機

                if not error_occurred:
                    # 3. 最終レポートを生成
                    st.write("ステップ8/8: すべてのレビュー結果を統合しています...")
                    final_report, error = generate_consolidated_report(
                        document_text=edited_text,
                        non_joyo_report=non_joyo_report,
                        individual_reports=individual_reports,
                        review_order=review_order
                    )
                    if error:
                        st.error(f"最終レポートの生成中にエラーが発生しました: {e}")
                        error_occurred = True
                    else:
                        st.session_state.final_report = final_report
                        st.write("✅ ステップ8/8: 最終レポートが生成されました。")
            
            if error_occurred:
                status.update(label="処理中にエラーが発生しました。", state="error", expanded=False)
            else:
                status.update(label="レビュー処理が完了しました。", state="complete", expanded=False)

    if 'final_report' in st.session_state and st.session_state.final_report:
        st.subheader("✅ 最終統合レポート")
        with st.container(border=True):
            st.markdown(st.session_state.final_report.replace('\n', '  \n'))