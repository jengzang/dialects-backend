import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes.geo.get_partitions import router
from app.sql.db_selector import get_query_db


@pytest.fixture
def client(tmp_path):
    database = tmp_path / "query.db"
    with sqlite3.connect(database) as connection:
        connection.execute('CREATE TABLE dialects (音典分區 TEXT, 地圖集二分區 TEXT)')
        connection.executemany('INSERT INTO dialects VALUES (?, ?)', [
            ("新根-同名-三-四-五-六", "官話-片-小片-四級"),
            ("下江-通泰-南泰-口刁", "粵語-四邑片"),
            ("嶺西-同名", "吳語-太湖片"),
            ("嶺西-髙肇", "吳語-太湖片"),
            ("嶺西-高肇", "吳語-太湖片"),
            ("類閩", "方言島"),
            ("待处理-子", "歷史音-子"),
            ("歷史音", "戲劇"),
            ("戲劇", "域外方音"),
            ("域外方音", "現代標準漢語"),
            ("現代標準漢語", "待处理"),
            (None, ""),
            ("新根-同名-三-四-五-六", "官話-片-小片-四級"),
        ])
    application = FastAPI()
    application.include_router(router, prefix="/api")
    application.dependency_overrides[get_query_db] = lambda: str(database)
    with TestClient(application) as test_client:
        yield test_client, database


def flatten(nodes):
    return {node["path"]: node for node in nodes for node in [node, *flatten(node["children"]).values()]}


def test_default_tree_preserves_arbitrary_depth_identity_and_policy(client):
    response = client[0].get("/api/partitions")
    assert response.status_code == 200
    tree = response.json()
    assert tree["schema_version"] == 2
    assert tree["region_mode"] == "yindian"
    assert tree["parent"] is None
    assert tree["max_depth"] == 6
    assert [node["label"] for node in tree["nodes"]] == ["下江", "嶺西", "新根", "類閩"]
    nodes = flatten(tree["nodes"])
    assert nodes["新根-同名-三-四-五-六"]["depth"] == 6
    assert nodes["嶺西-同名"]["label"] == nodes["新根-同名"]["label"] == "同名"
    assert "嶺西-髙肇" in nodes and "嶺西-高肇" in nodes
    assert [n["label"] for n in nodes["嶺西"]["children"]] == sorted(["同名", "髙肇", "高肇"])
    assert not any(path.split("-")[0] in {"待处理", "歷史音", "戲劇", "域外方音", "現代標準漢語"} for path in nodes)


def test_map_uses_database_paths_and_existing_root_order(client):
    tree = client[0].get("/api/partitions?region_mode=map").json()
    assert tree["region_mode"] == "map"
    assert tree["max_depth"] == 4
    assert [n["path"] for n in tree["nodes"]] == ["吳語", "粵語", "官話", "方言島"]
    assert "官話-片-小片-四級" in flatten(tree["nodes"])
    assert "東北官話" not in flatten(tree["nodes"])


def test_parent_is_full_path_and_children_keep_absolute_depth(client):
    tree = client[0].get("/api/partitions", params={"parent": "新根-同名-三"}).json()
    assert tree["parent"] == "新根-同名-三"
    assert tree["nodes"][0]["path"] == "新根-同名-三-四"
    assert tree["nodes"][0]["depth"] == 4
    assert "新根-同名-三-四-五-六" in flatten(tree["nodes"])
    assert client[0].get("/api/partitions", params={"parent": "嶺西-同名"}).json()["nodes"] == []
    for parent in ["同名", "不存在", "待处理"]:
        assert client[0].get("/api/partitions", params={"parent": parent}).status_code == 404


@pytest.mark.parametrize("params", [{"region_mode": "bad"}, {"parent": ""}, {"parent": "新根--同名"}, {"parent": " 新根"}])
def test_invalid_requests_are_rejected(client, params):
    assert client[0].get("/api/partitions", params=params).status_code == 422


def test_revision_is_deterministic_and_changes_with_paths(client):
    before = client[0].get("/api/partitions").json()["revision"]
    assert before == client[0].get("/api/partitions").json()["revision"]
    assert str(client[1]) not in before
    with sqlite3.connect(client[1]) as connection:
        connection.execute('INSERT INTO dialects VALUES (?, ?)', ("新根-新增", None))
    assert before != client[0].get("/api/partitions").json()["revision"]
