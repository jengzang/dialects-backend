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


def test_sql_tree_full_returns_lazy_fallback_when_result_too_large():
    app = create_main_app()
    client = TestClient(app)

    resp = client.post(
        '/sql/tree/full',
        json={
            'db_key': 'village',
            'table_name': '广东省自然村',
            'level_columns': [0, 1, 2, 3, 4],
            'data_columns': [],
            'filters': None,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data['mode'] == 'lazy_fallback'
    assert data['reason'] == 'full_tree_row_limit_exceeded'
    assert data['limit'] == 5000
    assert data['levels'] == 5
    bootstrap = data['lazy_bootstrap']
    # bootstrap 是 {城市: [区县列表]}，保留父级上下文避免重名
    assert isinstance(bootstrap, dict)
    assert len(bootstrap) >= 1
    first_city = next(iter(bootstrap))
    assert isinstance(bootstrap[first_city], list)
    # 东莞等不设区城市应包含 "(空)" 占位符
    all_children = [v for vals in bootstrap.values() for v in vals]
    assert all_children


def test_sql_tree_lazy_root_is_limited_and_child_level_continues():
    app = create_main_app()
    client = TestClient(app)

    root_resp = client.post(
        '/sql/tree/lazy',
        json={
            'db_key': 'village',
            'table_name': '广东省自然村',
            'level_columns': [0, 1, 2, 3, 4],
            'parent_path': None,
            'filters': None,
        },
    )
    assert root_resp.status_code == 200
    root = root_resp.json()
    assert root['level'] == 0
    assert root['parent_path'] is None
    assert len(root['children']) <= 100
    assert root['total'] <= 100
    assert root['truncated'] is False
    assert root['children']

    # 直接用第一个城市，空中间层会返回 ["(空)"] 占位符
    first_city = root['children'][0]
    child_resp = client.post(
        '/sql/tree/lazy',
        json={
            'db_key': 'village',
            'table_name': '广东省自然村',
            'level_columns': [0, 1, 2, 3, 4],
            'parent_path': [first_city],
            'filters': None,
        },
    )
    assert child_resp.status_code == 200
    child = child_resp.json()
    assert child['level'] == 1
    assert child['parent_path'] == [first_city]
    assert child['children'], f'{first_city} level-1 应该有子节点或占位符'
    assert child['truncated'] is False

    # 如果 level-1 是占位符（如东莞市不设区），验证能继续下钻到 level-2
    if child['children'] == ['(空)']:
        grandchild_resp = client.post(
            '/sql/tree/lazy',
            json={
                'db_key': 'village',
                'table_name': '广东省自然村',
                'level_columns': [0, 1, 2, 3, 4],
                'parent_path': [first_city, '(空)'],
                'filters': None,
            },
        )
        assert grandchild_resp.status_code == 200
        grandchild = grandchild_resp.json()
        assert grandchild['level'] == 2
        assert grandchild['children']
