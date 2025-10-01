import os
import streamlit as st
from dotenv import load_dotenv
from openai import AzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient

# .envファイルから環境変数をロード
load_dotenv()

@st.cache_resource
def get_clients():
    """Azure SearchとAzure OpenAIのクライアントを初期化して返す"""
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