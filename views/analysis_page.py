import streamlit as st
import graphviz
from core.nlp import load_stanza_model
from constants import pos_tag_japanese, deprel_japanese

def display_analysis_page(text_to_analyze: str):
    """原文解析専用ページの描画"""
    st.title("⚙️原文の係り受け解析")
    st.markdown("---")
    st.markdown(f"**解析対象テキスト:**")
    st.markdown(f"> {text_to_analyze.replace(chr(10), chr(10) + '> ')}")
    st.markdown("---")
    
    stanza_nlp = load_stanza_model()
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