import sqlite3
import unittest
import asyncio
from unittest.mock import patch


class VillagesMLQueryShapeTests(unittest.TestCase):
    def test_village_ngram_endpoint_uses_materialized_village_id(self) -> None:
        from app.villagesML.village import data

        queries = []

        def fake_execute_single(_db, query, params=()):
            queries.append((query, params))
            if "FROM \"广东省自然村_预处理\"" in query:
                return {"village_id": "v_7", "village_name": "水口", "village_committee": "水口村委会"}
            if "FROM \"village_ngrams\"" in query:
                return {"village_name": "水口", "bigrams": "水口"}
            return None

        with patch.object(data, "execute_single", side_effect=fake_execute_single):
            result = data.get_village_ngrams(7, db=sqlite3.connect(":memory:"), dbpath="village")

        ngram_queries = [query for query, _ in queries if "FROM \"village_ngrams\"" in query]
        self.assertEqual(result["bigrams"], "水口")
        self.assertTrue(ngram_queries)
        self.assertIn('"village_id" = ?', ngram_queries[0])
        self.assertNotIn('"自然村" = ?', ngram_queries[0])
        self.assertNotIn('"村委会" = ?', ngram_queries[0])

    def test_village_complete_profile_uses_village_id_for_detail_tables(self) -> None:
        from app.villagesML.village import data

        queries = []

        def fake_execute_single(_db, query, params=()):
            queries.append((query, params))
            if "FROM \"广东省自然村_预处理\"" in query:
                return {
                    "village_id": 7,
                    "village_id_str": "v_7",
                    "village_name": "水口",
                    "village_committee": "水口村委会",
                }
            if "FROM \"village_ngrams\"" in query:
                return {"village_id": "v_7", "bigrams": "水口"}
            if "FROM \"village_semantic_structure\"" in query:
                return {"village_id": "v_7", "semantic_sequence": "water-settlement"}
            return None

        with (
            patch.object(data, "execute_single", side_effect=fake_execute_single),
            patch.object(data.get_run_id_manager("village").__class__, "get_active_run_id", return_value="run_1"),
        ):
            result = data.get_village_complete_profile(7, db=sqlite3.connect(":memory:"), dbpath="village")

        detail_queries = [
            query
            for query, _ in queries
            if "FROM \"village_ngrams\"" in query or "FROM \"village_semantic_structure\"" in query
        ]
        self.assertEqual(result["ngrams"]["village_id"], "v_7")
        self.assertEqual(result["semantic_structure"]["village_id"], "v_7")
        self.assertEqual(len(detail_queries), 2)
        for query in detail_queries:
            self.assertIn('"village_id" = ?', query)
            self.assertNotIn('"自然村" = ?', query)
            self.assertNotIn('"村委会" = ?', query)

    def test_village_search_detail_accepts_rowid_without_name_lookup_from_frontend(self) -> None:
        from app.villagesML.village import search

        queries = []
        pragma_rows = {
            "village_features": [
                {"name": "village_id"},
                {"name": "run_id"},
                {"name": "suffix_1"},
                {"name": "sem_water"},
                {"name": "sem_settlement"},
                {"name": "kmeans_cluster_id"},
            ],
            "village_spatial_features": [
                {"name": "village_id"},
                {"name": "nn_distance_5"},
                {"name": "local_density_1km"},
                {"name": "isolation_score"},
            ],
        }

        def fake_execute_single(_db, query, params=()):
            queries.append((query, params))
            if "FROM \"广东省自然村_预处理\"" in query:
                return {
                    "village_id": 7,
                    "village_id_str": "v_7",
                    "village_name": "水口",
                    "city": "广州市",
                    "county": "从化区",
                    "township": "太平镇",
                    "longitude": 113.1,
                    "latitude": 23.1,
                }
            if "FROM \"village_features\"" in query:
                return {"semantic_tags": "water,settlement", "suffix": "村", "cluster_id": 3}
            if "FROM \"village_spatial_features\"" in query:
                return {"spatial_cluster_id": 9}
            return None

        def fake_execute_query(_db, query, params=()):
            if "PRAGMA table_info" not in query:
                return []
            table_name = query.split('"')[1]
            return pragma_rows[table_name]

        with (
            patch.object(search, "execute_single", side_effect=fake_execute_single),
            patch.object(search, "execute_query", side_effect=fake_execute_query),
            patch.object(search.get_run_id_manager("village").__class__, "get_active_run_id", return_value="run_1"),
        ):
            result = search.get_village_detail(
                village_id=7,
                village_name=None,
                city=None,
                county=None,
                db=sqlite3.connect(":memory:"),
                dbpath="village",
            )

        self.assertEqual(result["basic_info"]["village_name"], "水口")
        self.assertEqual(result["semantic_tags"], ["water", "settlement"])
        feature_queries = [query for query, _ in queries if "FROM \"village_features\"" in query]
        spatial_queries = [query for query, _ in queries if "FROM \"village_spatial_features\"" in query]
        self.assertTrue(feature_queries)
        self.assertTrue(spatial_queries)
        self.assertIn('"village_id" = ?', feature_queries[0])
        self.assertIn('"suffix_1" as suffix', feature_queries[0])
        self.assertIn('"kmeans_cluster_id" as cluster_id', feature_queries[0])
        self.assertIn("CASE WHEN", feature_queries[0])
        self.assertIn('vsf."village_id" = ?', spatial_queries[0])
        self.assertIn('vsf."nn_distance_5" as knn_mean_distance', spatial_queries[0])
        self.assertIn('vsf."local_density_1km" as local_density', spatial_queries[0])

    def test_region_similarity_search_splits_or_lookup(self) -> None:
        from app.villagesML.regional import similarity

        executed = []

        def fake_execute_query(_db, query, params=()):
            executed.append((query, params))
            if "SELECT DISTINCT" in query:
                return [{"region_name": "番禺区"}]
            if "region1" in query and "region2" not in query.split("WHERE", 1)[1]:
                return [{"similar_region": "天河区", "similarity": 0.9, "common_high_tendency_chars": "[]", "distinctive_chars": "[]"}]
            if "region2" in query and "region1" not in query.split("WHERE", 1)[1]:
                return [{"similar_region": "越秀区", "similarity": 0.8, "common_high_tendency_chars": "[]", "distinctive_chars": "[]"}]
            return []

        with patch.object(similarity, "execute_query", side_effect=fake_execute_query):
            result = asyncio.run(
                similarity.search_similar_regions(
                    region_level="county",
                    region_name="番禺区",
                    top_k=10,
                    metric="cosine",
                    min_similarity=0.0,
                    db=sqlite3.connect(":memory:"),
                    dbpath="village",
                )
            )

        similarity_queries = [query for query, _ in executed if "common_high_tendency_chars" in query]
        self.assertEqual(result["count"], 2)
        self.assertEqual(len(similarity_queries), 2)
        self.assertTrue(all(" OR " not in query for query in similarity_queries))

    def test_township_ngram_regional_adds_region_lookup_when_township_is_known(self) -> None:
        from app.villagesML.ngrams import frequency

        executed = []

        def fake_execute_query(_db, query, params=()):
            executed.append((query, params))
            return [
                {
                    "region_name": "太平镇",
                    "city": "广州市",
                    "county": "从化区",
                    "township": "太平镇",
                    "ngram": "水口",
                    "frequency": 8,
                    "percentage": 1.0,
                }
            ]

        with patch.object(frequency, "execute_query", side_effect=fake_execute_query):
            result = frequency.get_regional_ngram_frequency(
                n=2,
                region_level="township",
                region_name=None,
                city="广州市",
                county="从化区",
                township="太平镇",
                top_k=50,
                return_metadata=False,
                db=sqlite3.connect(":memory:"),
                dbpath="village",
            )

        query, params = executed[0]
        self.assertEqual(result[0]["region_name"], "太平镇")
        self.assertIn('"region" = ?', query)
        self.assertIn("太平镇", params)

    def test_township_ngram_tendency_adds_region_lookup_when_township_is_known(self) -> None:
        from app.villagesML.ngrams import frequency

        executed = []

        class FakeCursor:
            def execute(self, *_args):
                return None

            def fetchall(self):
                return [("regional_total_raw", "regional_total_raw")]

        class FakeConnection:
            def cursor(self):
                return FakeCursor()

        def fake_execute_query(_db, query, params=()):
            executed.append((query, params))
            return [
                {
                    "region_level": "township",
                    "region_name": "太平镇",
                    "city": "广州市",
                    "county": "从化区",
                    "township": "太平镇",
                    "ngram": "水口",
                    "n": 2,
                    "position": "all",
                    "tendency_score": 1.2,
                    "frequency": 8,
                }
            ]

        frequency._pragma_cache.clear()
        with patch.object(frequency, "execute_query", side_effect=fake_execute_query):
            result = frequency.get_ngram_tendency(
                ngram=None,
                region_level="township",
                region_name=None,
                city="广州市",
                county="从化区",
                township="太平镇",
                min_tendency=None,
                limit=100,
                db=FakeConnection(),
                dbpath="village",
            )

        query, params = executed[0]
        self.assertEqual(result[0]["region_name"], "太平镇")
        self.assertIn('nt."region" = ?', query)
        self.assertIn("太平镇", params)


if __name__ == "__main__":
    unittest.main()
