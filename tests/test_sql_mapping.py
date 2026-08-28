from pathlib import Path

from app.common.path import DB_MAPPING


def test_gis_mapping_points_to_sqlite_file() -> None:
    gis_path = Path(DB_MAPPING["gis"])

    assert gis_path.name == "gis.db"
    assert gis_path.is_file()
