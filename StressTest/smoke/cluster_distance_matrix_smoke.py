from __future__ import annotations

import sys
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.tools.cluster.service.distance_service import (  # noqa: E402
    build_dimension_bucket_models,
    build_dimension_token_catalogs,
    build_group_model,
    build_total_distance_matrix,
)


def build_fixture():
    locations = ["A", "B", "C"]
    groups = [
        {
            "label": "g1",
            "source_mode": "preset",
            "table_name": "characters",
            "compare_dimension": "final",
            "group_weight": 1.0,
            "use_phonetic_values": False,
            "phonetic_value_weight": 0.0,
            "resolved_chars": ["甲", "乙", "丙"],
        },
        {
            "label": "g2",
            "source_mode": "preset",
            "table_name": "characters",
            "compare_dimension": "final",
            "group_weight": 1.0,
            "use_phonetic_values": False,
            "phonetic_value_weight": 0.0,
            "resolved_chars": ["丁", "戊", "己"],
        },
    ]
    dialect_data = {
        "A": {
            "甲": {"final": {"an"}},
            "乙": {"final": {"an"}},
            "丙": {"final": {"ia"}},
            "丁": {"final": {"uo"}},
            "戊": {"final": {"uo"}},
            "己": {"final": {"ei"}},
        },
        "B": {
            "甲": {"final": {"en"}},
            "乙": {"final": {"en"}},
            "丙": {"final": {"ie"}},
            "丁": {"final": {"ou"}},
            "戊": {"final": {"ou"}},
            "己": {"final": {"ei"}},
        },
        "C": {
            "甲": {"final": {"en"}},
            "乙": {"final": {"ie"}},
            "丙": {"final": {"en"}},
            "丁": {"final": {"ou"}},
            "戊": {"final": {"ei"}},
            "己": {"final": {"ou"}},
        },
    }
    inventory_profiles = {
        "A": {
            "final": {
                "an": {"share": 2.0 / 3.0, "rank_pct": 0.0},
                "ia": {"share": 1.0 / 3.0, "rank_pct": 1.0},
                "uo": {"share": 2.0 / 3.0, "rank_pct": 0.0},
                "ei": {"share": 1.0 / 3.0, "rank_pct": 1.0},
            }
        },
        "B": {
            "final": {
                "en": {"share": 2.0 / 3.0, "rank_pct": 0.0},
                "ie": {"share": 1.0 / 3.0, "rank_pct": 1.0},
                "ou": {"share": 2.0 / 3.0, "rank_pct": 0.0},
                "ei": {"share": 1.0 / 3.0, "rank_pct": 1.0},
            }
        },
        "C": {
            "final": {
                "en": {"share": 2.0 / 3.0, "rank_pct": 0.0},
                "ie": {"share": 1.0 / 3.0, "rank_pct": 1.0},
                "ou": {"share": 2.0 / 3.0, "rank_pct": 0.0},
                "ei": {"share": 1.0 / 3.0, "rank_pct": 1.0},
            }
        },
    }
    dimension_catalogs = build_dimension_token_catalogs(groups, dialect_data)
    group_models = [
        build_group_model(group, locations, dialect_data, dimension_catalogs[group["compare_dimension"]])
        for group in groups
    ]
    bucket_models = build_dimension_bucket_models(
        groups,
        locations,
        dialect_data,
        dimension_catalogs,
    )
    return locations, group_models, inventory_profiles, bucket_models


def assert_matrix_close(mode: str):
    locations, group_models, inventory_profiles, bucket_models = build_fixture()
    matrix_fast, params_fast = build_total_distance_matrix(
        group_models=group_models,
        locations=locations,
        phoneme_mode=mode,
        inventory_profiles=inventory_profiles,
        bucket_models=bucket_models,
    )
    matrix_python, params_python = build_total_distance_matrix(
        group_models=group_models,
        locations=locations,
        phoneme_mode=mode,
        inventory_profiles=inventory_profiles,
        bucket_models=bucket_models,
        force_python=True,
    )
    if not np.allclose(matrix_fast, matrix_python, atol=1e-9, rtol=1e-9):
        raise AssertionError(
            f"{mode} matrix mismatch\nfast=\n{matrix_fast}\npython=\n{matrix_python}"
        )
    if params_fast != params_python:
        raise AssertionError(f"{mode} params mismatch: {params_fast} != {params_python}")


def main():
    for mode in ["intra_group", "anchored_inventory", "shared_request_identity"]:
        assert_matrix_close(mode)
        print(f"{mode}: OK")


if __name__ == "__main__":
    main()
