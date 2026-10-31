"""Exact aggregation boundaries and allocation scaling for scalar-first groups."""
from collections import Counter
from dataclasses import asdict
import tracemalloc
from types import SimpleNamespace

import pytest

from app.service.vocabulary import query
from app.service.vocabulary.script_variants import standard_word_key
from tests.test_vocabulary_query_resources import database


def reference(rows):
    groups = {}
    for word, location, count in rows:
        key = standard_word_key(word)
        group = groups.setdefault(key, [0, set(), Counter()])
        group[0] += count
        if location:
            group[1].add(location)
        group[2][word] += count
    result = []
    for key, (count, locations, variants) in groups.items():
        words = sorted(variants, key=lambda word: (-variants[word], word))
        result.append(dict(key=key, standard_word=words[0], variants=words,
                           entry_count=count, location_count=len(locations)))
    return sorted(result, key=lambda row: (-row['location_count'], -row['entry_count'], row['standard_word']))


def row_session(rows):
    class Cursor:
        def execute(self, *args):
            return self
        def __iter__(self):
            return iter(rows)
    return SimpleNamespace(connection=lambda: SimpleNamespace(connection=SimpleNamespace(cursor=Cursor)))


@pytest.mark.parametrize('limit', [None, 1, 2, 100])
def test_promotions_preserve_all_variant_counts_ties_and_locations(limit):
    # Rows sorted exactly as SQLite GROUP BY spelling/location. Different
    # spellings of the same normalized key need not be adjacent.
    rows = sorted([
        ('太阳', '', 2), ('太阳', '甲', 3), ('太阳', '乙', 1),
        ('太陽', '甲', 4), ('太陽', '乙', 2),
        ('儿童', '', 3), ('兒童', '', 3),
        ('日頭', '甲', 9), ('日头', '乙', 2),
        ('單詞', '甲', 7), ('独有', '甲', 4),
    ])
    result = query.query_vocabulary_standard_words(session=row_session(rows), limit=limit)
    expected = reference(rows)
    assert result.total == len(expected)
    assert [asdict(word) for word in result.standard_words] == expected[:limit]


def test_same_location_across_users_and_variants_is_counted_once(database):
    conn, session, _ = database
    conn.executemany('INSERT INTO vocabulary_entries(user_id,location_name,standard_word,local_expression,ipa) VALUES (?,?,?,?,?)', [
        (1, '', '兒童', '细人', 'a'), (2, '', '儿童', '细人', 'a'),
        (1, '同名', '兒童', '细人', 'a'), (2, '同名', '儿童', '细人', 'a'),
        (9, '别名', '儿童', '细人', 'a'),
    ])
    conn.commit()
    rows = conn.execute("SELECT standard_word,location_name,COUNT(*) FROM vocabulary_entries WHERE standard_word<>'' GROUP BY standard_word,location_name").fetchall()
    actual = query.query_vocabulary_standard_words(session=session, limit=None)
    assert [asdict(word) for word in actual.standard_words] == reference(rows)


def test_unrestricted_output_is_not_capped_by_compact_state():
    rows = [(f'词条{i:06}', '地点', 1) for i in range(4097)]
    actual = query.query_vocabulary_standard_words(session=row_session(rows), limit=None)
    assert actual.total == len(actual.standard_words) == len(rows)
    assert sum(word.entry_count for word in actual.standard_words) == len(rows)


def test_single_value_groups_avoid_eager_set_and_dict_allocations(monkeypatch):
    # Test the actual aggregation, not OpenCC/cache native allocations. Retain
    # only one output row so this measures intermediate state at 6000 groups.
    rows = [(f'word{i:06}', 'location', 1) for i in range(6000)]
    monkeypatch.setattr(query, 'standard_word_key', lambda word: word)
    tracemalloc.start()
    try:
        actual = query.query_vocabulary_standard_words(session=row_session(rows), limit=1)
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    assert actual.total == len(rows)
    # Baseline eager sets/dicts use >3 MiB here; scalar-first state <1.2 MiB.
    # Generous 2 MiB limit catches eager-per-group containers, not allocator noise.
    assert peak < 2 * 1024 * 1024
