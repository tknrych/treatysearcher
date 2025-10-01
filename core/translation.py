import re
import streamlit as st

def evaluate_translation(aoai_client, gpt_model, original_text: str, translated_text: str) -> float:
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
        response = aoai_client.chat.completions.create(
            model=gpt_model,
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


def _get_single_translation(aoai_client, gpt_model, text_to_translate: str, context_english: str, context_japanese: str, glossary: dict, previous_translation: str = None) -> str:
    """指定された英文を翻訳する内部関数。"""
    system_prompt = "あなたは、外務省の優秀な翻訳官です。条約のような、法的拘束力を持つ厳格な文書の翻訳を専門としています。与えられた指示に一字一句正確に従ってください。"
    
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
        response = aoai_client.chat.completions.create(model=gpt_model, messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], temperature=0.0, stop=["</answer>"])
        return (response.choices[0].message.content or "翻訳結果を取得できませんでした。").strip()
    except Exception as e:
        return f"翻訳中にエラーが発生しました: {e}"

@st.cache_data(show_spinner=False)
def get_translation_with_retry(_aoai_client, _gpt_model, text_to_translate: str, context_english: str, context_japanese: str, glossary: dict) -> tuple[str, float]:
    """自己評価と再試行を伴う翻訳処理"""
    MAX_RETRIES, SCORE_THRESHOLD, best_translation, best_score = 3, 0.9, "", -1.0
    if not _gpt_model: 
        return "翻訳機能に必要なGPTモデルのデプロイ名が設定されていません。", 0.0

    if glossary:
        st.info(f"選択された用語を適用します: {glossary}")

    for i in range(MAX_RETRIES):
        with st.spinner(f"翻訳を生成中... (試行 {i+1}/{MAX_RETRIES})"):
            current_translation = _get_single_translation(_aoai_client, _gpt_model, text_to_translate, context_english, context_japanese, glossary, best_translation if i > 0 else None)
            if "翻訳中にエラーが発生しました" in current_translation: 
                return current_translation, 0.0
            
            current_score = evaluate_translation(_aoai_client, _gpt_model, text_to_translate, current_translation)
            st.write(f"試行 {i+1}: スコア = {current_score:.2f}, 翻訳 = '{current_translation}'")
            
            if current_score > best_score:
                best_score, best_translation = current_score, current_translation
            if best_score >= SCORE_THRESHOLD:
                st.write(f"品質基準 ({SCORE_THRESHOLD}) を満たしました。")
                break
    return best_translation, best_score