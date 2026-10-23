import asyncio
import multiprocessing
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path


def try_slot(path, output):
    from app.service.toponyms.resources import execution_slot, QueryBusy
    try:
        with execution_slot(path, "heavy"):
            output.put(True)
    except QueryBusy:
        output.put(False)


class ToponymResourcesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / "names.db")
        with sqlite3.connect(self.path) as conn:
            conn.execute("CREATE TABLE records (value)")

    def tearDown(self):
        self.tmp.cleanup()

    def test_connections_are_read_only_and_close(self):
        from app.service.toponyms.resources import connection
        with connection(self.path) as conn:
            self.assertEqual(conn.execute("PRAGMA cache_size").fetchone()[0], -4096)
            with self.assertRaises(sqlite3.OperationalError):
                conn.execute("INSERT INTO records VALUES (1)")
        with self.assertRaises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")

    def test_deadline_interrupts_sql_and_next_request_is_healthy(self):
        from app.service.toponyms.resources import connection, QueryTimedOut
        with self.assertRaises(QueryTimedOut):
            with connection(self.path, timeout=0.001) as conn:
                conn.execute("""WITH RECURSIVE n(x) AS (
                    VALUES(1) UNION ALL SELECT x+1 FROM n WHERE x<100000000
                ) SELECT SUM(x) FROM n""").fetchone()
        with connection(self.path) as conn:
            self.assertEqual(conn.execute("SELECT 1").fetchone()[0], 1)

    def test_two_heavy_slots_are_shared_across_processes(self):
        from app.service.toponyms.resources import execution_slot, QueryBusy
        ctx = multiprocessing.get_context("spawn")
        output = ctx.Queue()
        with execution_slot(self.path, "heavy"), execution_slot(self.path, "heavy"):
            with self.assertRaises(QueryBusy):
                with execution_slot(self.path, "heavy"):
                    pass
            proc = ctx.Process(target=try_slot, args=(self.path, output))
            proc.start()
            self.assertFalse(output.get(timeout=10))
            proc.join(10)
            self.assertEqual(proc.exitcode, 0)
            # A reserved lightweight slot remains available.
            with execution_slot(self.path, "light"):
                pass
        with execution_slot(self.path, "heavy"):
            pass

    def test_tree_slot_is_subset_of_heavy_budget(self):
        from app.service.toponyms.resources import execution_slot, QueryBusy
        with execution_slot(self.path, "tree"):
            with self.assertRaises(QueryBusy):
                with execution_slot(self.path, "tree"):
                    pass
            with execution_slot(self.path, "heavy"):
                with self.assertRaises(QueryBusy):
                    with execution_slot(self.path, "heavy"):
                        pass

    def test_identical_requests_coalesce_and_cache_invalidates_on_database_change(self):
        from app.service.toponyms.execution import run_query
        calls = []
        def query():
            calls.append(1)
            time.sleep(0.03)
            with sqlite3.connect(self.path) as conn:
                return conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]
        async def exercise():
            results = await asyncio.gather(*[
                run_query(query, db_path=self.path) for _ in range(5)
            ])
            self.assertEqual(results, [0] * 5)
            self.assertEqual(len(calls), 1)
            self.assertEqual(await run_query(query, db_path=self.path), 0)
            self.assertEqual(len(calls), 1)
            with sqlite3.connect(self.path) as conn:
                conn.execute("INSERT INTO records VALUES (1)")
            self.assertEqual(await run_query(query, db_path=self.path), 1)
            self.assertEqual(len(calls), 2)
        asyncio.run(exercise())

    def test_cache_respects_bytes_and_does_not_cache_errors(self):
        from app.service.toponyms.execution import ResultCache, run_query
        cache = ResultCache(max_bytes=8, max_entries=2, max_item_bytes=6)
        cache.put("a", b"11111", 60)
        cache.put("b", b"22222", 60)
        self.assertIsNone(cache.get("a"))
        self.assertEqual(cache.get("b"), b"22222")
        cache.put("large", b"1234567", 60)
        self.assertIsNone(cache.get("large"))
        cache.put("expired", b"1", -1)
        self.assertIsNone(cache.get("expired"))
        calls = []
        def failing():
            calls.append(1)
            raise ValueError("failure")
        async def exercise():
            for _ in range(2):
                with self.assertRaises(ValueError):
                    await run_query(failing, db_path=self.path)
        asyncio.run(exercise())
        self.assertEqual(len(calls), 2)

    def test_cancelling_one_waiter_does_not_cancel_shared_work(self):
        import threading
        from app.service.toponyms.execution import run_query
        started = threading.Event()
        release = threading.Event()
        calls = []
        def query():
            calls.append(1)
            started.set()
            release.wait(2)
            return ["done"]
        async def exercise():
            first = asyncio.create_task(run_query(query, db_path=self.path))
            await asyncio.to_thread(started.wait, 2)
            second = asyncio.create_task(run_query(query, db_path=self.path))
            await asyncio.sleep(0)
            first.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await first
            release.set()
            self.assertEqual(await second, ["done"])
            self.assertEqual(len(calls), 1)
        asyncio.run(exercise())

    def test_unlimited_stream_keeps_buffer_bounded_and_releases_slots(self):
        from app.service.toponyms.streaming import QueryStream, CHUNK_ROWS
        from app.service.toponyms.resources import execution_slot, QueryBusy
        with sqlite3.connect(self.path) as conn:
            conn.execute("CREATE TABLE single (id TEXT,standard_name TEXT,place_type_code TEXT,"
                         "area_code TEXT,longitude REAL,latitude REAL)")
            conn.executemany("INSERT INTO single VALUES (?,?,?,?,?,?)", [
                (str(i), f"村{i:06}", "22200", "44", 113., 23.) for i in range(12001)
            ])
        stream = QueryStream(self.path, "names", {"query": "村", "match_mode": "contains", "limit": 0})
        try:
            chunk = stream.start()
            self.assertEqual(stream.count, CHUNK_ROWS)
            with execution_slot(self.path, "heavy"):
                with self.assertRaises(QueryBusy):
                    with execution_slot(self.path, "heavy"):
                        pass
            max_chunk = len(chunk)
            while not stream.done:
                max_chunk = max(max_chunk, len(stream.read()))
            self.assertEqual(stream.count, 12001)
            self.assertLess(max_chunk, 32 * 1024)
        finally:
            stream.close()
        with execution_slot(self.path, "heavy"), execution_slot(self.path, "heavy"):
            pass

    def test_disconnected_stream_releases_connection_and_execution_slot(self):
        from app.service.toponyms.streaming import stream_query
        from app.service.toponyms.resources import execution_slot
        with sqlite3.connect(self.path) as conn:
            conn.execute("CREATE TABLE single (standard_name TEXT,place_type_code TEXT)")
            conn.executemany("INSERT INTO single VALUES (?,?)",
                             [(f"村{i}", "22200") for i in range(1000)])
        async def exercise():
            response = await stream_query(self.path, "names",
                                           {"query": "村", "match_mode": "contains", "limit": 0})
            sent = asyncio.Event()
            async def receive():
                await sent.wait()
                return {"type": "http.disconnect"}
            async def send(message):
                if message["type"] == "http.response.body":
                    sent.set()
                    await asyncio.sleep(0.01)
            await response({"type": "http", "asgi": {"spec_version": "2.0"}}, receive, send)
            with self.assertRaises(sqlite3.ProgrammingError):
                response.reader.conn.execute("SELECT 1")
        asyncio.run(exercise())
        with execution_slot(self.path, "heavy"), execution_slot(self.path, "heavy"):
            pass

    def test_disconnect_interrupts_initial_unlimited_sort_before_headers(self):
        from unittest.mock import patch
        from app.service.toponyms.streaming import stream_query
        from app.service.toponyms.resources import execution_slot
        class DisconnectedRequest:
            async def receive(self):
                return {"type": "http.disconnect"}
        sql = """WITH RECURSIVE n(x) AS (
            VALUES(1) UNION ALL SELECT x+1 FROM n WHERE x<100000000
        ) SELECT CAST(SUM(x) AS TEXT) AS standard_name FROM n"""
        async def exercise():
            with patch("app.service.toponyms.repository.names_query", return_value=(sql, [])):
                start = time.monotonic()
                try:
                    response = await stream_query(
                        self.path, "names", {"query": "村", "match_mode": "contains", "limit": 0},
                        request=DisconnectedRequest(),
                    )
                except Exception as exc:
                    self.assertEqual(type(exc).__name__, "QueryDisconnected")
                else:
                    response.reader.close()
                    self.fail("Disconnected initial query continued")
                self.assertLess(time.monotonic() - start, 2)
        asyncio.run(exercise())
        with execution_slot(self.path, "heavy"), execution_slot(self.path, "heavy"):
            pass

    def test_initial_disconnect_through_http_middleware_stops_unlimited_query(self):
        from unittest.mock import patch
        from fastapi import FastAPI, Request
        from starlette.responses import Response
        from app.service.toponyms.streaming import stream_query, QueryDisconnected
        from app.service.toponyms.resources import execution_slot
        app = FastAPI()
        @app.middleware("http")
        async def passthrough(request, call_next):
            return await call_next(request)
        @app.get("/")
        async def endpoint(request: Request):
            try:
                return await stream_query(self.path, "names",
                    {"query": "村", "match_mode": "contains", "limit": 0}, request=request)
            except QueryDisconnected:
                return Response(status_code=499)
        sql = """WITH RECURSIVE n(x) AS (
            VALUES(1) UNION ALL SELECT x+1 FROM n WHERE x<100000000
        ) SELECT CAST(SUM(x) AS TEXT) AS standard_name FROM n"""
        async def exercise():
            messages = iter([{"type": "http.request", "body": b"", "more_body": False}])
            async def receive():
                await asyncio.sleep(0)
                return next(messages, {"type": "http.disconnect"})
            async def send(message):
                pass
            scope = {"type": "http", "asgi": {"version": "3.0", "spec_version": "2.0"},
                     "http_version": "1.1", "method": "GET", "scheme": "http",
                     "path": "/", "raw_path": b"/", "query_string": b"",
                     "headers": [], "server": ("test", 80), "client": ("client", 1)}
            with patch("app.service.toponyms.repository.names_query", return_value=(sql, [])):
                await asyncio.wait_for(app(scope, receive, send), timeout=0.5)
        asyncio.run(exercise())
        with execution_slot(self.path, "heavy"), execution_slot(self.path, "heavy"):
            pass
