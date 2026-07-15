import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(ROOT))

from scripts.villagesml.benchmark_ngram_queries import (
    BenchmarkCase,
    build_default_cases,
    run_benchmark,
    run_benchmark_case,
)


def create_minimal_ngram_db(path: str) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE ngram_frequency (
            ngram TEXT,
            position TEXT,
            frequency INTEGER,
            percentage REAL,
            n INTEGER
        );
        CREATE TABLE regional_ngram_frequency (
            level TEXT,
            region TEXT,
            city TEXT,
            county TEXT,
            township TEXT,
            ngram TEXT,
            frequency INTEGER,
            percentage REAL,
            n INTEGER
        );
        CREATE TABLE ngram_tendency (
            level TEXT,
            region TEXT,
            city TEXT,
            county TEXT,
            township TEXT,
            ngram TEXT,
            n INTEGER,
            position TEXT,
            lift REAL,
            log_odds REAL,
            z_score REAL,
            regional_count INTEGER,
            regional_total INTEGER,
            regional_total_raw INTEGER,
            global_count INTEGER,
            global_total INTEGER
        );

        INSERT INTO ngram_frequency VALUES ('新村', 'all', 10, 1.0, 2);
        INSERT INTO regional_ngram_frequency VALUES ('township', '太平镇', '广州市', '从化区', '太平镇', '新村', 7, 1.0, 2);
        INSERT INTO ngram_tendency VALUES ('township', '太平镇', '广州市', '从化区', '太平镇', '新村', 2, 'all', 1.5, 0.2, 2.1, 7, 100, 100, 10, 1000);
        """
    )
    conn.commit()
    conn.close()


class VillagesMLNgramBenchmarkScriptTests(unittest.TestCase):
    def test_default_cases_include_index_aligned_and_broad_scan_cases(self) -> None:
        cases = build_default_cases(region="太平镇", ngram="新村", n=2, limit=25)
        case_names = {case.name for case in cases}

        self.assertIn("frequency_top_by_n_position", case_names)
        self.assertIn("regional_top_by_level_n_region", case_names)
        self.assertIn("tendency_top_by_level_region", case_names)
        self.assertIn("regional_broad_scan_all_townships", case_names)
        self.assertIn("tendency_broad_scan_all_townships", case_names)

        regional_case = next(case for case in cases if case.name == "regional_top_by_level_n_region")
        self.assertIn("WHERE n = ? AND level = ? AND region = ?", regional_case.sql)
        self.assertIn("ORDER BY frequency DESC", regional_case.sql)
        self.assertNotIn("ORDER BY city, county, township", regional_case.sql)

    def test_run_benchmark_case_reports_explain_rows_and_timing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "villages.db")
            create_minimal_ngram_db(db_path)
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row

            result = run_benchmark_case(
                conn,
                BenchmarkCase(
                    name="frequency_top_by_n_position",
                    sql="""
                    SELECT ngram, frequency
                    FROM ngram_frequency
                    WHERE n = ? AND position = ?
                    ORDER BY frequency DESC
                    LIMIT ?
                    """,
                    params=(2, "all", 25),
                ),
                repeats=2,
            )
            conn.close()

        self.assertEqual(result["name"], "frequency_top_by_n_position")
        self.assertEqual(result["row_count"], 1)
        self.assertGreaterEqual(result["min_ms"], 0)
        self.assertTrue(result["plan"])
        self.assertIn("uses_temp_btree", result)

    def test_run_benchmark_requires_existing_database_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_path = os.path.join(tmpdir, "missing.db")
            with self.assertRaises(FileNotFoundError):
                run_benchmark(missing_path, [])

            self.assertFalse(os.path.exists(missing_path))

    def test_run_benchmark_case_requires_positive_repeats(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "villages.db")
            create_minimal_ngram_db(db_path)
            conn = sqlite3.connect(db_path)

            with self.assertRaisesRegex(ValueError, "repeats must be positive"):
                run_benchmark_case(
                    conn,
                    BenchmarkCase(
                        name="frequency_top_by_n_position",
                        sql="SELECT ngram FROM ngram_frequency LIMIT ?",
                        params=(1,),
                    ),
                    repeats=0,
                )

            conn.close()


if __name__ == "__main__":
    unittest.main()
