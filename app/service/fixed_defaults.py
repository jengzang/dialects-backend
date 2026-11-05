"""Canonical loaders for the six fixed results, always against a fresh read-only file."""
from contextlib import contextmanager
from pathlib import Path
import sqlite3

from app.common.fixed_default_cache import key


@contextmanager
def readonly(path, expired=lambda: False):
    db = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True, timeout=0.1)
    try:
        db.row_factory = sqlite3.Row
        db.set_progress_handler(lambda: int(expired()), 1000)
        if expired():
            raise TimeoutError("Fixed default query cancelled before execution")
        yield db
    finally:
        db.set_progress_handler(None, 0)
        db.close()


def load_on_connection(slot, db, *, bounded_warmup=False):
    key(slot)  # Fixed whitelist, never interpolate arbitrary table/column inputs.
    if slot.startswith("yubao:"):
        from app.service.yubao.repository import YubaoRepository
        from app.service.yubao.service import YubaoService
        service = YubaoService(YubaoRepository(connection=db, bounded_warmup=bounded_warmup))
        method = service.get_grammar_sentences if slot == "yubao:grammar_all" else service.get_vocabulary_words
        return method(q=None, limit=50, all_items=True).model_dump(mode="json")
    if slot.startswith("sql:"):
        from app.sql.sql_routes import _count_on_connection
        column, value = ("存儲標記", "1") if slot == "sql:query_stored_count" else (None, None)
        return {"count": _count_on_connection(db, "dialects", column, value)}
    from app.villagesML.schema_config import DEFAULT_DATABASE_KEY
    from app.villagesML.schema_runtime import install_schema_views
    install_schema_views(db, DEFAULT_DATABASE_KEY)
    if slot == "villages:gd:tables":
        from app.villagesML.metadata.stats import _get_table_info_sync
        return _get_table_info_sync(DEFAULT_DATABASE_KEY, connection=db)
    from app.villagesML.statistics import _get_ngram_statistics_sync
    return _get_ngram_statistics_sync(db, DEFAULT_DATABASE_KEY)


def load(slot, path):
    # Old pooled handles can still point to an unlinked database after os.replace.
    # Opening by path here ties the result to the generation checked by the cache.
    with readonly(path) as db:
        return load_on_connection(slot, db)
