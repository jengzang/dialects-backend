"""Complete JSON responses with bounded Python buffering, including limit=0."""
import asyncio
from contextlib import ExitStack
import json
from pathlib import Path
import sqlite3
import threading

import anyio
from starlette.responses import StreamingResponse

from .resources import execution_slot, QueryBusy

CHUNK_ROWS = 256
_admission_lock = threading.Lock()
_active_streams = 0


class QueryDisconnected(Exception):
    pass


class QueryStream:
    def __init__(self, path, endpoint, kwargs):
        self.path = path
        self.endpoint = endpoint
        self.kwargs = kwargs
        self.cancelled = threading.Event()
        self.stack = ExitStack()
        self.conn = None
        self.cursor = None
        self.count = 0
        self.first = True
        self.done = False
        self.on_close = None

    def start(self):
        from .repository import points_query, search_query, names_query
        try:
            self.stack.enter_context(execution_slot(self.path, "heavy"))
            # Sequential batches may run on different pool threads. No two
            # operations on this connection are allowed to overlap.
            self.conn = sqlite3.connect(Path(self.path).resolve().as_uri() + "?mode=ro",
                                        uri=True, timeout=0.1, check_same_thread=False)
            self.stack.callback(self.conn.close)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA query_only=ON")
            self.conn.execute("PRAGMA cache_size=-4096")
            self.conn.execute("PRAGMA temp_store=FILE")
            # Unlimited is a real full-result contract: no total-duration
            # deadline which would implicitly truncate a legitimate long scan.
            self.conn.set_progress_handler(self.cancelled.is_set, 1000)
            if self.endpoint == "points":
                sql, params = points_query(self.conn, **self.kwargs)
            elif self.endpoint == "search":
                sql, params = search_query(**self.kwargs)
            else:
                sql, params = names_query(**self.kwargs)
            self.cursor = self.conn.execute(sql, params)
            return self.read()
        except BaseException:
            self.close()
            raise

    def read(self):
        if self.done:
            return None
        rows = self.cursor.fetchmany(CHUNK_ROWS)
        limit = self.kwargs["limit"]
        truncated = bool(limit and self.count + len(rows) > limit)
        if truncated:
            rows = rows[:limit - self.count]
        parts = []
        for row in rows:
            if self.endpoint == "names":
                item = row["standard_name"]
            elif self.endpoint == "points":
                item = {"id": row["id"], "longitude": row["longitude"], "latitude": row["latitude"]}
            else:
                item = {"id": row["id"], "name": row["name"]}
                for key in ("area_code", "place_type_code"):
                    if self.kwargs.get("include_" + key) and row[key] is not None:
                        item[key] = row[key]
            parts.append(json.dumps(item, ensure_ascii=False, separators=(",", ":"), allow_nan=False))
        prefix = '{"items":[' if self.first else ("," if rows else "")
        self.first = False
        self.count += len(rows)
        chunk = prefix + ",".join(parts)
        if not rows or truncated:
            self.done = True
            chunk += "]"
            if self.endpoint != "names":
                chunk += ',"count":' + str(self.count) + ',"truncated":' + str(truncated).lower()
                if self.endpoint == "points":
                    chunk += ',"next":null'
            chunk += "}"
        return chunk.encode()

    def close(self):
        self.cancelled.set()
        try:
            self.stack.close()
        finally:
            callback, self.on_close = self.on_close, None
            if callback:
                callback()


async def _run(reader, operation):
    task = asyncio.create_task(asyncio.to_thread(operation))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        reader.cancelled.set()
        # Wait for SQLite to observe cancellation before closing its connection.
        with anyio.CancelScope(shield=True):
            try:
                await asyncio.shield(task)
            except Exception:
                pass
        raise


class QueryStreamingResponse(StreamingResponse):
    def __init__(self, reader, first):
        self.reader = reader
        async def chunks():
            yield first
            while not reader.done:
                chunk = await _run(reader, reader.read)
                if chunk is not None:
                    yield chunk
        super().__init__(chunks(), media_type="application/json",
                         headers={"X-Toponyms-Stream": "1", "X-Accel-Buffering": "no"})

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            with anyio.CancelScope(shield=True):
                await _run(self.reader, self.reader.close)


async def _start(reader, request):
    if request is None:
        return await _run(reader, reader.start)
    async def disconnected():
        # Actually await receive: is_disconnected()'s cancelled poll can miss
        # messages through BaseHTTPMiddleware's checkpointing receive wrapper.
        while True:
            message = await request.receive()
            if message["type"] == "http.disconnect":
                return
    task = asyncio.create_task(_run(reader, reader.start))
    monitor = asyncio.create_task(disconnected())
    try:
        completed, _ = await asyncio.wait({task, monitor}, return_when=asyncio.FIRST_COMPLETED)
        if monitor in completed:
            monitor.result()
            raise QueryDisconnected("Client disconnected")
        return task.result()
    finally:
        monitor.cancel()
        with anyio.CancelScope(shield=True):
            try:
                await monitor
            except asyncio.CancelledError:
                pass
        if not task.done():
            reader.cancelled.set()
            task.cancel()
            with anyio.CancelScope(shield=True):
                try:
                    await asyncio.shield(task)
                except (asyncio.CancelledError, Exception):
                    pass


async def stream_query(path, endpoint, kwargs, *, request=None):
    global _active_streams
    with _admission_lock:
        if _active_streams >= 2:
            raise QueryBusy("Toponym streaming slots are occupied")
        _active_streams += 1
    def release():
        global _active_streams
        with _admission_lock:
            _active_streams -= 1
    reader = QueryStream(path, endpoint, kwargs)
    reader.on_close = release
    try:
        first = await _start(reader, request)
        return QueryStreamingResponse(reader, first)
    except BaseException:
        with anyio.CancelScope(shield=True):
            await _run(reader, reader.close)
        raise
