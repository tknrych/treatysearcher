import streamlit as st
import re
import os
from core.azure_clients import get_clients
from utils import find_non_joyo_kanji

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
        st.error(f"参照資料ファイルが見つかりません: {file_path}\n`ref_docs` ディレクトリに正しいファイル名のテキストファイルを配置してください。")
        return None

# --- メインの描画関数 ---
def display_check_page(text_to_check: str, original_text: str):
    """文章校正・レビュー処理用の専用ページを描画"""
    st.title("📝 文章校正・レビュー処理")

    st.markdown("##### 英語原文")
    with st.container(border=True):
        st.markdown(original_text.replace('\n', '  \n'))

    st.markdown("##### AI翻訳結果")
    with st.container(border=True):
        st.markdown(text_to_check.replace('\n', '  \n'))

    st.markdown("##### 編集領域")
    edited_text = st.text_area(
        "レビュー対象テキスト",
        value=text_to_check,
        height=300,
        label_visibility="collapsed"
    )

    st.divider()

    # --- レビュー機能の定義 ---
    review_definitions = [
        {"tab_name": "『条約邦文テキスト作成要領』", "filename": "ref_doc_1.txt", "role": "あなたは、日本の内閣法制局または外務省条約局に所属する、条約の邦訳テキスト審査を専門とする熟練した担当官です。あなたの任務は、提供された『条約邦文テキスト作成要領』（通称「黄表紙」）に記載された規則に準拠しているか、極めて厳密かつ詳細にテキストをレビューすることです。"},
        {"tab_name": "『新訂ワークブック法制執務』", "filename": "ref_doc_2.txt", "role": "あなたは、日本の法制執務に精通した専門家です。あなたの任務は、提供された『新訂ワークブック法制執務』に記載された規則に準拠しているか、テキストを詳細にレビューすることです。"},
        {"tab_name": "『法令用字用語必携』", "filename": "ref_doc_3.txt", "role": "あなたは、日本の法令文書における用字用語の専門家です。あなたの任務は、提供された『法令用字用語必携』に基づき、テキストの用字用語が適切かどうかをレビューすることです。"},
        {"tab_name": "『最新公用文用字用語例集』", "filename": "ref_doc_4.txt", "role": "あなたは、現代日本の公用文の表現に詳しい専門家です。あなたの任務は、提供された『最新公用文用字用語例集』に基づき、テキストの表現が公用文として適切かレビューすることです。"},
        {"tab_name": "『法令用語の常識』", "filename": "ref_doc_5.txt", "role": "あなたは、日本の法令用語に関する深い知識を持つ専門家です。あなたの任務は、提供された『法令用語の常識』に基づき、テキストで使われている法令用語が適切かどうかをレビューすることです。"},
        {"tab_name": "『公用文作成の考え方』", "filename": "ref_doc_7.txt", "role": "あなたは、分かりやすい公用文を作成する専門家です。あなたの任務は、提供された『公用文作成の考え方』に基づき、テキストが平易かつ明確な表現になっているかレビューすることです。"}
    ]

    # --- 各種確認機能のタブ ---
    tab_names = ["常用漢字確認"] + [d["tab_name"] for d in review_definitions]
    tabs = st.tabs(tab_names)

    # --- ★ 「常用漢字確認」タブ ---
    with tabs[0]:
        st.info("編集領域のテキストに常用漢字以外の漢字が含まれていないかを確認します。")
        if st.button("常用漢字のみが使用されているかを確認する"):
            if not edited_text.strip():
                st.warning("テキストが入力されていません。")
            else:
                st.write("---")
                with st.spinner("確認中..."):
                    non_joyo_list = find_non_joyo_kanji(edited_text)
                    if non_joyo_list:
                        st.error(f"常用漢字以外の漢字が見つかりました ({len(non_joyo_list)}字):")
                        # 漢字を見やすく表示
                        st.text(" , ".join(non_joyo_list))
                    else:
                        st.success("✅ 常用漢字以外の漢字は見つかりませんでした。")

    # --- 各レビュータブの描画 ---
    for i, definition in enumerate(review_definitions):
        with tabs[i + 1]:
            st.info(f"編集領域のテキストを{definition['tab_name']}に基づきレビューします。")
            if st.button(f"{definition['tab_name']}レビューを実行する", key=f"review_button_{i}"):
                if not edited_text.strip():
                    st.warning("テキストが入力されていません。")
                else:
                    perform_review(
                        document_text=edited_text,
                        reference_filename=definition["filename"],
                        reference_name=definition["tab_name"],
                        system_role_description=definition["role"]
                    )

# --- 機能実行関数 ---
def perform_review(document_text: str, reference_filename: str, reference_name: str, system_role_description: str):
    """指定された参照資料に基づきレビューを実行し、結果を表示する（共通関数）"""
    reference_data = load_reference_doc(reference_filename)
    if not reference_data:
        return 

    try:
        _, aoai_client, gpt_model, _ = get_clients()
        spinner_text = f"{reference_name}に基づいたレビューを実行中です..."
        with st.spinner(spinner_text):
            system_prompt = f"""# 命令書

## あなたの役割
{system_role_description}

## 参照資料
レビューの唯一の基準は、以下に提供する『{reference_name}』の全文です。この資料に記載されている配字、用字、構文、用語の統一に関するすべての規則を絶対的なものとして適用してください。

## 実行タスク
以下の【レビュー対象テキスト】を読み、【参照資料】に照らして、規則からの逸脱がないかを確認してください。
逸脱箇所を発見した場合は、その箇所、問題点、根拠となる規則、そして修正案を具体的に示してください。

## 出力形式
以下の形式で、レビュー結果を整理して出力してください。

---
### 総評
レビュー対象テキスト全体についての簡潔な評価を記述してください。

---
### 詳細なレビュー
問題点を一つずつ、以下の項目でリストアップしてください。問題点が複数ある場合は、このブロックを繰り返してください。問題がない場合は、「指摘事項はありません。」と記述してください。

* **該当箇所:** 問題があるテキストの具体的な場所（例：「第X条(Y)」など）を記述してください。
* **原文:** 問題があるテキストの一文または一部分を引用してください。
* **指摘事項:** どのような点が『{reference_name}』の規則に反しているかを具体的に説明してください。
* **根拠:** 『{reference_name}』のどの規則に準拠していないか、セクション名や番号を引用して明確に示してください。（例：「V 構文の統一 １（１）構成」）
* **修正案:** 規則に沿った正しい表現を提案してください。

---
"""
            user_prompt = f"""# 参照資料『{reference_name}』
{reference_data}

# レビュー対象テキスト
{document_text}
"""
            
            response = aoai_client.chat.completions.create(
                model=gpt_model, messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                temperature=0.0, max_tokens=4000,
            )
            result = response.choices[0].message.content or "結果を取得できませんでした。"
            
            st.subheader(f"📒 {reference_name}レビュー結果")
            with st.container(border=True):
                st.markdown(result.replace('\n', '  \n'))
    except Exception as e:
        st.error(f"レビュー実行中にエラーが発生しました: {e}")