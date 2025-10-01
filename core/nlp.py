import streamlit as st
import spacy
import stanza
import torch
import pysbd
from spacy.language import Language
from utils import is_japanese

@Language.component("pysbd_sentencizer")
def pysbd_sentence_boundaries(doc):
    lang_code = "ja" if is_japanese(doc.text) else "en"
    seg = pysbd.Segmenter(language=lang_code, clean=False, char_span=True)
    sents_char_spans = seg.segment(doc.text)
    start_char_indices = {s.start for s in sents_char_spans}
    for token in doc:
        token.is_sent_start = True if token.i == 0 or token.idx in start_char_indices else False
    return doc

@st.cache_resource
def load_nlp_model(model_name="en_core_web_lg"):
    """spaCyモデルをロードする"""
    try:
        nlp = spacy.load(model_name)
        nlp.add_pipe("pysbd_sentencizer", before="parser")
        return nlp
    except OSError:
        st.warning(f"spaCyモデル '{model_name}' のロードに失敗しました。")
        return None

@st.cache_resource
def load_stanza_model():
    """Stanzaモデルをロードする"""
    try:
        use_gpu = torch.cuda.is_available()
        stanza.download('en')
        return stanza.Pipeline('en', use_gpu=use_gpu)
    except Exception as e:
        st.error(f"Stanzaモデルのロード中にエラーが発生しました: {e}")
        return None