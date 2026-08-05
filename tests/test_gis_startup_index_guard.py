from unittest.mock import Mock, patch

from app.lifecycle import startup


def test_gis_startup_auto_build_guard_uses_sqlite_runtime_index() -> None:
    build_geo_index = Mock()
    runtime_index_path = Mock()
    runtime_index_path.exists.return_value = True

    with (
        patch.object(startup, "GEO_AUTO_BUILD_ON_STARTUP", True),
        patch.object(startup, "GEO_INDEX_SQLITE_PATH", runtime_index_path),
        patch.object(startup, "load_geo_query_engine"),
        patch.dict("sys.modules", {"scripts.geo.build_lowmem_index": Mock(main=build_geo_index)}),
    ):
        startup.initialize_geo_query_engine_strict()

    build_geo_index.assert_not_called()


def test_gis_startup_auto_builds_when_sqlite_runtime_index_is_missing() -> None:
    build_geo_index = Mock()
    runtime_index_path = Mock()
    runtime_index_path.exists.return_value = False

    with (
        patch.object(startup, "GEO_AUTO_BUILD_ON_STARTUP", True),
        patch.object(startup, "GEO_INDEX_SQLITE_PATH", runtime_index_path),
        patch.object(startup, "load_geo_query_engine"),
        patch.dict("sys.modules", {"scripts.geo.build_lowmem_index": Mock(main=build_geo_index)}),
    ):
        startup.initialize_geo_query_engine_strict()

    build_geo_index.assert_called_once_with()
