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