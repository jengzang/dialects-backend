"""Guard the measurement harness against accidental persistent writes."""
import importlib.util
from pathlib import Path
import sqlite3

import pytest

spec = importlib.util.spec_from_file_location('cache_benchmark', Path(__file__).resolve().parents[1] / 'scripts/benchmark_db_cache.py')
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)


def create(path):
    with sqlite3.connect(path) as conn:
        conn.execute('create table items (value)')
        conn.execute('insert into items values (1)')


def test_main_database_is_readonly_but_notes_temp_work_is_allowed(tmp_path):
    path = tmp_path / 'query_user.db'
    create(path)
    before = bench.identity(path)
    conn = bench.connect(tmp_path, 'query', 2000)
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute('insert into items values (2)')
        assert conn.execute('pragma cache_size').fetchone()[0] == -2000
        assert conn.execute('pragma journal_mode').fetchone()[0] == 'delete'
        conn.execute('create temp table matches as select * from items')
        assert conn.execute('select * from matches').fetchall() == [(1,)]
        conn.execute('drop table temp.matches')
    finally:
        conn.close()
    assert bench.identity(path) == before


def test_attached_database_is_readonly_and_budget_is_independent(tmp_path):
    create(tmp_path / 'dialects_user.db')
    create(tmp_path / 'characters.db')
    conn = bench.connect(tmp_path, 'characters_attach', 4096)
    try:
        assert conn.execute('pragma main.cache_size').fetchone()[0] == -16000
        assert conn.execute('pragma chars_db.cache_size').fetchone()[0] == -4096
        with pytest.raises(sqlite3.OperationalError):
            conn.execute('insert into chars_db.items values (2)')
    finally:
        conn.close()


def test_timeout_is_recorded_and_next_case_is_healthy(tmp_path):
    create(tmp_path / 'query_user.db')
    conn = bench.connect(tmp_path, 'query', 2000)
    try:
        result = bench.run_case(conn, ('slow', [('WITH RECURSIVE n(x) AS (VALUES(0) UNION ALL SELECT x+1 FROM n WHERE x<100000000) SELECT SUM(x) FROM n', ())]), .001)
        assert 'interrupted' in result['error']
        result = bench.run_case(conn, ('healthy', [('select * from items', ())]), 1)
        assert result['rows'] == [1]
        assert 'error' not in result
        assert result['sql_ms'] <= result['ms']
    finally:
        conn.close()


def test_missing_path_is_not_created(tmp_path):
    with pytest.raises(FileNotFoundError):
        bench.connect(tmp_path, 'query', 2000)
    assert not (tmp_path / 'query_user.db').exists()


def test_parameter_sampling_closes_auxiliary_query_connection(tmp_path, monkeypatch):
    with sqlite3.connect(tmp_path/'query_user.db') as conn:
        conn.execute('create table dialects (簡稱 text)')
        conn.executemany('insert into dialects values (?)', [(str(n),) for n in range(5)])
    create(tmp_path/'dialects_user.db')
    main = bench.connect(tmp_path, 'dialects', 2000)
    connect = sqlite3.connect
    auxiliary=[]
    class Tracked(sqlite3.Connection):
        closed=False
        def close(self):
            super().close()
            self.closed=True
    def tracked(*args, **kwargs):
        conn=connect(*args, factory=Tracked, **kwargs)
        auxiliary.append(conn)
        return conn
    monkeypatch.setattr(bench, 'ROOT', tmp_path, raising=False)
    monkeypatch.setattr(bench.sqlite3,'connect',tracked)
    try:
        workload=bench.cases(main,'characters_attach')
        assert len(set(workload[0][1][0][1]))==5
        assert len(auxiliary)==1
        assert auxiliary[0].closed
    finally:
        main.close()
        for conn in auxiliary: conn.close()
