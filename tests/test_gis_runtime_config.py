from app.geo_query import config


def test_gis_runtime_config_uses_data_gis_directory() -> None:
    assert config.GEO_RUNTIME_DATA_DIR.name == "gis"
    assert config.GEO_RUNTIME_DATA_DIR.parent.name == "data"
    assert config.GEO_INDEX_SQLITE_PATH.name == "gis.db"
    assert "data/geo" not in str(config.GEO_INDEX_SQLITE_PATH)


def test_gis_runtime_config_does_not_expose_build_pipeline_paths() -> None:
    assert not hasattr(config, "GEO_SOURCE_DIR")
    assert not hasattr(config, "GEO_GEOJSON_WGS84_DIR")
    assert not hasattr(config, "GEO_INDEX_JSON_PATH")
    assert not hasattr(config, "GEO_FEATURES_JSONL_PATH")
    assert not hasattr(config, "GEO_SUBGEOM_WKB_PATH")
