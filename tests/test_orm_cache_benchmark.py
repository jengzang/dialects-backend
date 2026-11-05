"""Guardrails for the standalone, local-only ORM measurements."""
import importlib.util
from pathlib import Path

import pytest
from sqlalchemy.exc import OperationalError


@pytest.fixture
def benchmark(monkeypatch):
    scripts = Path(__file__).resolve().parents[1] / 'scripts'
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location('isolated_orm_benchmark', scripts / 'benchmark_orm_cache.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('profile', ['auth', 'logs', 'supplements', 'vocabulary'])
def test_synthetic_writes_verify_commit_and_rollback(benchmark, profile):
    result = benchmark.write_run(profile, benchmark.models(profile), 2000, seed_rows=16, batches=2)
    assert result['verified_rows'] == 16 + 2 * result['batch_size']
    assert result['batch_median_ms'] > 0
    if profile == 'logs':
        assert result['diagnostics']['batch_size'] == 25


def test_source_engine_enforces_readonly_and_returns_equal_results(benchmark, monkeypatch, tmp_path):
    path = tmp_path / 'supplements.db'
    m = benchmark.models('supplements')
    create = benchmark.create_engine
    engine = create(f'sqlite:///{path}')
    m.Base.metadata.create_all(engine)
    engine.dispose()
    engines = []
    def tracked(*args, **kwargs):
        engine = create(*args, **kwargs)
        engines.append(engine)
        return engine
    monkeypatch.setattr(benchmark, 'create_engine', tracked)
    small = benchmark.read_run('supplements', m, path, 2000)
    large = benchmark.read_run('supplements', m, path, 16000)
    assert {k: v['signature'] for k, v in small['queries'].items()} == {k: v['signature'] for k, v in large['queries'].items()}
    for engine in engines:
        try:
            with engine.connect() as conn:
                assert conn.exec_driver_sql('PRAGMA query_only').scalar() == 1
                with pytest.raises(OperationalError, match='readonly'):
                    conn.exec_driver_sql('CREATE TABLE forbidden (n)')
        finally:
            engine.dispose()
