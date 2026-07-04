import sqlite3
from contextlib import closing
from typing import Any, Iterable, Optional

from app.common.path import DB_MAPPING


YUBAO_DB_PATH = DB_MAPPING['yubao']


class YubaoRepository:
    VOCABULARY_SORTABLE_FIELDS = {
        'id', 'no', 'province', 'city', 'county', 'village', 'location',
        'longitude', 'latitude', 'word', 'pronunciation', 'note1', 'note2',
        'lang_cat1', 'lang_cat2', 'lang_cat3'
    }
    GRAMMAR_SORTABLE_FIELDS = {
        'id', 'iid', 'city_code', 'city_name', 'form_a', 'form_b', 'form_c',
        'form_d', 'form_e', 'longitude', 'latitude', 'phonetic', 'sentence',
        'memo', 'lang_cat1', 'lang_cat2', 'lang_cat3'
    }

    VOCABULARY_COLUMNS = [
        'id', 'no', 'province', 'city', 'county', 'village', 'location',
        'longitude', 'latitude', 'word', 'pronunciation', 'note1', 'note2',
        'lang_cat1', 'lang_cat2', 'lang_cat3'
    ]
    GRAMMAR_COLUMNS = [
        'id', 'iid', 'city_code', 'city_name', 'form_a', 'form_b', 'form_c',
        'form_d', 'form_e', 'longitude', 'latitude', 'phonetic', 'sentence',
        'memo', 'lang_cat1', 'lang_cat2', 'lang_cat3'
    ]

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(YUBAO_DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _normalize_limit(limit: int, all_items: bool) -> Optional[int]:
        if all_items:
            return None
        return max(1, min(limit, 500))

    @staticmethod
    def _apply_like(sql_parts: list[str], params: list[Any], field: str, q: Optional[str]) -> None:
        if q:
            sql_parts.append(f'{field} LIKE ?')
            params.append(f'%{q}%')

    def list_distinct_words(self, q: Optional[str], limit: int, all_items: bool) -> list[str]:
        normalized_limit = self._normalize_limit(limit, all_items)
        where_parts = ["word IS NOT NULL", "TRIM(word) != ''"]
        params: list[Any] = []
        self._apply_like(where_parts, params, 'word', q)
        sql = 'SELECT DISTINCT word FROM vocabulary'
        if where_parts:
            sql += ' WHERE ' + ' AND '.join(where_parts)
        sql += ' ORDER BY word'
        if normalized_limit is not None:
            sql += ' LIMIT ?'
            params.append(normalized_limit)
        with closing(self._connect()) as conn:
            rows = conn.execute(sql, params).fetchall()
        return [row['word'] for row in rows]

    def count_distinct_words(self, q: Optional[str]) -> int:
        where_parts = ["word IS NOT NULL", "TRIM(word) != ''"]
        params: list[Any] = []
        self._apply_like(where_parts, params, 'word', q)
        sql = 'SELECT COUNT(DISTINCT word) AS total FROM vocabulary'
        if where_parts:
            sql += ' WHERE ' + ' AND '.join(where_parts)
        with closing(self._connect()) as conn:
            row = conn.execute(sql, params).fetchone()
        return int(row['total'])

    def list_distinct_sentences(self, q: Optional[str], limit: int, all_items: bool) -> list[str]:
        normalized_limit = self._normalize_limit(limit, all_items)
        where_parts = ["sentence IS NOT NULL", "TRIM(sentence) != ''"]
        params: list[Any] = []
        self._apply_like(where_parts, params, 'sentence', q)
        sql = 'SELECT DISTINCT sentence FROM grammar'
        if where_parts:
            sql += ' WHERE ' + ' AND '.join(where_parts)
        sql += ' ORDER BY sentence'
        if normalized_limit is not None:
            sql += ' LIMIT ?'
            params.append(normalized_limit)
        with closing(self._connect()) as conn:
            rows = conn.execute(sql, params).fetchall()
        return [row['sentence'] for row in rows]

    def count_distinct_sentences(self, q: Optional[str]) -> int:
        where_parts = ["sentence IS NOT NULL", "TRIM(sentence) != ''"]
        params: list[Any] = []
        self._apply_like(where_parts, params, 'sentence', q)
        sql = 'SELECT COUNT(DISTINCT sentence) AS total FROM grammar'
        if where_parts:
            sql += ' WHERE ' + ' AND '.join(where_parts)
        with closing(self._connect()) as conn:
            row = conn.execute(sql, params).fetchone()
        return int(row['total'])

    @staticmethod
    def _build_order_clause(sort_by: Optional[str], sort_desc: bool, allowed_fields: Iterable[str], default_order: str) -> str:
        if sort_by and sort_by in allowed_fields:
            direction = 'DESC' if sort_desc else 'ASC'
            return f' ORDER BY "{sort_by}" {direction}'
        return default_order

    def list_vocabulary_items(self, word: str, page: int, page_size: int, sort_by: Optional[str], sort_desc: bool) -> tuple[list[dict[str, Any]], int]:
        offset = (page - 1) * page_size
        columns = ', '.join(f'"{c}"' for c in self.VOCABULARY_COLUMNS)
        order_clause = self._build_order_clause(sort_by, sort_desc, self.VOCABULARY_SORTABLE_FIELDS, ' ORDER BY id ASC')
        base_where = ' FROM vocabulary WHERE word = ?'
        params = [word]
        data_sql = f'SELECT {columns}{base_where}{order_clause} LIMIT ? OFFSET ?'
        count_sql = 'SELECT COUNT(*) AS total' + base_where
        with closing(self._connect()) as conn:
            rows = conn.execute(data_sql, params + [page_size, offset]).fetchall()
            total_row = conn.execute(count_sql, params).fetchone()
        return [dict(row) for row in rows], int(total_row['total'])

    def list_grammar_items(self, sentence: str, page: int, page_size: int, sort_by: Optional[str], sort_desc: bool) -> tuple[list[dict[str, Any]], int]:
        offset = (page - 1) * page_size
        columns = ', '.join(f'"{c}"' for c in self.GRAMMAR_COLUMNS)
        order_clause = self._build_order_clause(sort_by, sort_desc, self.GRAMMAR_SORTABLE_FIELDS, ' ORDER BY id ASC')
        base_where = ' FROM grammar WHERE sentence = ?'
        params = [sentence]
        data_sql = f'SELECT {columns}{base_where}{order_clause} LIMIT ? OFFSET ?'
        count_sql = 'SELECT COUNT(*) AS total' + base_where
        with closing(self._connect()) as conn:
            rows = conn.execute(data_sql, params + [page_size, offset]).fetchall()
            total_row = conn.execute(count_sql, params).fetchone()
        return [dict(row) for row in rows], int(total_row['total'])
