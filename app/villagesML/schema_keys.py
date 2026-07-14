"""
Symbolic keys for VillagesML schema configuration.

Routes and services import these symbols instead of spelling logical table,
column, list, variant, or region-level config keys inline.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from .schema_config import DEFAULT_DATABASE_KEY, VILLAGES_DATABASES


def _symbol_name(value: str) -> str:
    return value.upper().replace("-", "_")


def _namespace(values: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(**values)


_DEFAULT_CONFIG = VILLAGES_DATABASES[DEFAULT_DATABASE_KEY]

T = _namespace({
    _symbol_name(table_key): table_key
    for table_key in _DEFAULT_CONFIG["tables"]
})

C = _namespace({
    _symbol_name(table_key): _namespace({
        _symbol_name(column_key): column_key
        for column_key in table_config.get("columns", {})
    })
    for table_key, table_config in _DEFAULT_CONFIG["tables"].items()
})

TABLE_LISTS = _namespace({
    _symbol_name(list_key): list_key
    for list_key in _DEFAULT_CONFIG.get("table_lists", {})
})

TABLE_VARIANTS = _namespace({
    _symbol_name(variant_key): variant_key
    for variant_key in _DEFAULT_CONFIG.get("table_variants", {})
})

REGION_LEVEL_CONFIGS = _namespace({
    _symbol_name(config_key): config_key
    for config_key in _DEFAULT_CONFIG.get("region_levels", {})
})


def semantic_feature_column(category: str) -> str:
    return f"sem_{category}"


def semantic_feature_columns() -> list[str]:
    return [
        column_key
        for column_key in vars(C.VILLAGE_FEATURES).values()
        if isinstance(column_key, str) and column_key.startswith("sem_")
    ]


def semantic_feature_categories() -> set[str]:
    return {
        column_key.replace("sem_", "", 1)
        for column_key in semantic_feature_columns()
    }


SIMILARITY_METRIC_COLUMNS = _namespace({
    "cosine": C.REGION_SIMILARITY.COSINE_SIMILARITY,
    "jaccard": C.REGION_SIMILARITY.JACCARD_SIMILARITY,
})
