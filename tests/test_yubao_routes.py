from fastapi.testclient import TestClient

from app.main import create_main_app


def test_yubao_readonly_endpoints_and_sql_page_size_limit():
    app = create_main_app()
    client = TestClient(app)

    words_resp = client.get('/api/yubao/vocabulary/words', params={'limit': 5})
    assert words_resp.status_code == 200
    words_data = words_resp.json()
    assert words_data['total'] >= len(words_data['items'])
    assert len(words_data['items']) <= 5
    assert all(isinstance(item, str) and item.strip() for item in words_data['items'])

    all_words_resp = client.get('/api/yubao/vocabulary/words', params={'all': 'true'})
    assert all_words_resp.status_code == 200
    all_words_data = all_words_resp.json()
    assert all_words_data['total'] == len(all_words_data['items'])
    assert len(all_words_data['items']) > len(words_data['items'])

    sample_word = words_data['items'][0]
    vocab_items_resp = client.get('/api/yubao/vocabulary/items', params={'word': sample_word, 'page_size': 100})
    assert vocab_items_resp.status_code == 200
    vocab_items_data = vocab_items_resp.json()
    assert vocab_items_data['page_size'] == 100
    assert vocab_items_data['total'] >= len(vocab_items_data['items'])
    assert len(vocab_items_data['items']) >= 1
    assert all(item['word'] == sample_word for item in vocab_items_data['items'])

    sentences_resp = client.get('/api/yubao/grammar/sentences', params={'limit': 5})
    assert sentences_resp.status_code == 200
    sentences_data = sentences_resp.json()
    assert sentences_data['total'] >= len(sentences_data['items'])
    assert len(sentences_data['items']) <= 5
    assert all(isinstance(item, str) and item.strip() for item in sentences_data['items'])

    sample_sentence = sentences_data['items'][0]
    grammar_items_resp = client.get('/api/yubao/grammar/items', params={'sentence': sample_sentence, 'page_size': 100})
    assert grammar_items_resp.status_code == 200
    grammar_items_data = grammar_items_resp.json()
    assert grammar_items_data['page_size'] == 100
    assert grammar_items_data['total'] >= len(grammar_items_data['items'])
    assert len(grammar_items_data['items']) >= 1
    assert all(item['sentence'] == sample_sentence for item in grammar_items_data['items'])

    sql_limit_resp = client.post(
        '/sql/query',
        json={
            'db_key': 'yubao',
            'table_name': 'vocabulary',
            'page': 1,
            'page_size': 51,
            'sort_by': None,
            'sort_desc': False,
            'filters': {},
            'search_text': '',
            'search_columns': [],
        },
    )
    assert sql_limit_resp.status_code == 422
