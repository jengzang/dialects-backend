import unittest
from unittest.mock import patch

from app.tools.praat.core import job_executor


class PraatJobExecutorThreadOffloadTests(unittest.IsolatedAsyncioTestCase):
    async def test_execute_job_async_offloads_sync_executor_to_thread(self) -> None:
        calls = []

        async def fake_to_thread(func, *args, **kwargs):
            calls.append((func, args, kwargs))
            return "ok"

        with patch("app.tools.praat.core.job_executor.asyncio.to_thread", side_effect=fake_to_thread):
            await job_executor.execute_job_async("praat_task", "praat_task_job_1")

        self.assertEqual(calls, [(job_executor._execute_job_sync, ("praat_task", "praat_task_job_1"), {})])


if __name__ == "__main__":
    unittest.main()
