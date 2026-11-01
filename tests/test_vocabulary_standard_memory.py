"""Exact location membership and bounded-memory regression for full aggregation."""
from dataclasses import asdict
import tracemalloc

import pytest

from app.service.vocabulary import query
from tests.test_vocabulary_compact_groups import reference, row_session
from tests.test_vocabulary_query_resources import database


def test_multilocation_group_state_has_lower_allocation_peak(monkeypatch):
    rows = [(f'word{i:06}', location, 1) for i in range(10000) for location in ('甲','乙','丙')]
    monkeypatch.setattr(query, 'standard_word_key', lambda word: word)
    tracemalloc.start()
    try:
        result = query.query_vocabulary_standard_words(session=row_session(rows), limit=1)
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    assert result.total == 10000
    assert result.standard_words[0].location_count == 3
    assert result.standard_words[0].entry_count == 3
    # Existing scalar-first state exceeds3MiB; compact membership fits <2MiB.
    assert peak < 2 * 1024 * 1024


@pytest.mark.parametrize('places', [0,1,8,255,256,257,520])
@pytest.mark.parametrize('limit', [None,1,1000])
def test_membership_boundary_keeps_all_places_counts_variants_and_order(places, limit):
    locations = [f'地点{i:04}' for i in range(places)]
    rows = sorted([
        *[('太阳', location, i%3+1) for i,location in enumerate(locations)],
        *[('太陽', location, 2) for location in locations[::2]],
        ('太阳','',2),('太陽','',1),('儿童','',3),('兒童','',3),
        ('甲词', '地点0000', 1),('乙词','地点0519',1),
    ])
    result = query.query_vocabulary_standard_words(session=row_session(rows), limit=limit)
    expected = reference(rows)
    assert result.total == len(expected)
    assert [asdict(r) for r in result.standard_words] == expected[:limit]


def test_large_location_diversity_singletons_stays_compact(monkeypatch):
    rows = [(f'word{i:06}',f'place{i:06}',1) for i in range(6000)]
    monkeypatch.setattr(query,'standard_word_key',lambda word:word)
    tracemalloc.start()
    try:
        result=query.query_vocabulary_standard_words(session=row_session(rows),limit=1)
        peak=tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    assert result.total==6000
    assert result.standard_words[0].location_count==1
    # A bitmap whose width keeps growing, or an eager overflow set per word,
    # breaks this bound. Sparse overflow must retain scalar-first membership.
    assert peak < 2 * 1024 * 1024


def test_unrestricted_standard_words_keeps_every_group_and_all_variants():
    rows=sorted([(f'词条{i:06}',f'地点{i%530:04}',i%7+1) for i in range(7001)] +
        [('太阳','',2),('太阳','甲',3),('太陽','甲',4),('太陽','乙',6)])
    expected=reference(rows)
    result=query.query_vocabulary_standard_words(session=row_session(rows),limit=None)
    assert result.total==len(result.standard_words)==len(expected)
    assert [asdict(x) for x in result.standard_words]==expected


def test_sql_filters_users_orphans_and_canonical_merging_stay_exact(database):
    conn,session,sql=database
    conn.executemany('INSERT INTO vocabulary_entries(user_id,location_name,standard_word,local_expression,ipa) VALUES(?,?,?,?,?)',
        [(i+10,f'地点{i:04}','太陽' if i%2 else '太阳','日头','a') for i in range(520)])
    conn.commit()
    rows=conn.execute("SELECT standard_word,location_name,COUNT(*) FROM vocabulary_entries WHERE standard_word<>'' GROUP BY standard_word,location_name").fetchall()
    result=query.query_vocabulary_standard_words(session=session,limit=None)
    assert [asdict(x) for x in result.standard_words]==reference(rows)
    scoped=query.query_vocabulary_standard_words(session=session,locations=['贵州'],limit=None)
    assert scoped.total==1 and scoped.standard_words[0].entry_count==2
    assert scoped.standard_words[0].location_count==1


def test_overflow_before_known_bits_and_repeated_script_membership():
    # Earlier words consume the bit registry with Z names. Later words meet
    # unregistered A names before known Z names in SQLite's location order.
    rows=sorted([(f'AAA',f'Z{i:04}',1) for i in range(256)] + [
        ('太阳','A0',3),('太阳','A1',2),('太阳','Z0000',1),
        ('太陽','A0',4),('太陽','Z0001',5),('太陽','ZZnew',6),
        ('独有','A0',2),('独有','Z0002',3),('独有','ZZnew',4),
    ])
    result=query.query_vocabulary_standard_words(session=row_session(rows),limit=None)
    assert [asdict(x) for x in result.standard_words]==reference(rows)


def test_many_places_and_interleaved_variants_match_reference():
    import random
    rng=random.Random(20261101)
    spellings=['AAA','儿童','兒童','太阳','太陽','日头','日頭','独有','唯一']
    rows=sorted((word,f'地点{i:04}',rng.randint(1,20)) for word in spellings
        for i in rng.sample(range(1400),rng.randint(100,700)))
    result=query.query_vocabulary_standard_words(session=row_session(rows),limit=None)
    assert [asdict(x) for x in result.standard_words]==reference(rows)


def test_whitespace_variants_and_equal_rank_keep_original_spelling_and_order():
    rows=sorted([(' 太阳','甲',3),('太阳 ','乙',3),('太陽','甲',3),
        (' ','',1),('乙词','甲',1),('甲词','乙',1),('重复',' ',2)])
    expected=reference(rows)
    for limit in [1,3,None]:
        result=query.query_vocabulary_standard_words(session=row_session(rows),limit=limit)
        assert result.total==len(expected)
        assert [asdict(x) for x in result.standard_words]==expected[:limit]
