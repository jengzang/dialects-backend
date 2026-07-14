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


if __name__ == "__main__":
    unittest.main()
