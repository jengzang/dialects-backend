import os
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(ROOT))

os.environ.setdefault("_RUN_TYPE", "WEB")
os.environ.setdefault("AUTO_MIGRATE", "false")

from app.main import create_cluster_app, create_gis_app, create_main_app


def main_app_routes() -> set[str]:
    app = create_main_app()
    return {route.path for route in app.routes}


def gis_app_routes() -> set[str]:
    app = create_gis_app()
    return {route.path for route in app.routes}


def cluster_app_routes() -> set[str]:
    app = create_cluster_app()
    return {route.path for route in app.routes}


class WorkerSplitRoutesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.main_routes = main_app_routes()
        cls.gis_routes = gis_app_routes()
        cls.cluster_routes = cluster_app_routes()

    def test_main_app_excludes_new_gis_and_cluster_routes(self) -> None:
        self.assertNotIn("/api/gis/status", self.main_routes)
        self.assertNotIn("/api/tools/cluster/jobs", self.main_routes)
        self.assertIn("/api/get_coordinates", self.main_routes)
        self.assertIn("/api/partitions", self.main_routes)

    def test_gis_app_only_mounts_new_gis_routes(self) -> None:
        self.assertIn("/api/gis/status", self.gis_routes)
        self.assertIn("/api/gis/query/point", self.gis_routes)
        self.assertIn("/api/gis/query/geometry", self.gis_routes)
        self.assertNotIn("/api/tools/cluster/jobs", self.gis_routes)
        self.assertNotIn("/api/get_coordinates", self.gis_routes)
        self.assertNotIn("/", self.gis_routes)

    def test_cluster_app_only_mounts_cluster_routes(self) -> None:
        self.assertIn("/api/tools/cluster/jobs", self.cluster_routes)
        self.assertIn("/api/tools/cluster/jobs/{task_id}", self.cluster_routes)
        self.assertIn("/api/tools/cluster/staged/preview", self.cluster_routes)
        self.assertNotIn("/api/gis/status", self.cluster_routes)
        self.assertNotIn("/api/get_coordinates", self.cluster_routes)
        self.assertNotIn("/", self.cluster_routes)

    def test_gis_route_definition_stays_available(self) -> None:
        self.assertIn("/api/gis/status", self.gis_routes)
        self.assertIn("/api/gis/search", self.gis_routes)


if __name__ == "__main__":
    unittest.main()
