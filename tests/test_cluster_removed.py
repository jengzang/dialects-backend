"""The main app and background services must work without cluster dependencies."""

import os
from pathlib import Path
import subprocess
import sys
import textwrap


ROOT = Path(__file__).resolve().parents[1]
BLOCK_IMPORTS = """
import importlib.abc
import sys

class RejectClusterImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == name or fullname.startswith(name + '.')
               for name in ('numba', 'llvmlite', 'app.tools.cluster')):
            raise AssertionError('Removed dependency imported: ' + fullname)

sys.meta_path.insert(0, RejectClusterImports())
"""


def _run(script):
    result = subprocess.run(
        [sys.executable, "-c", BLOCK_IMPORTS + textwrap.dedent(script)],
        cwd=ROOT,
        env={**os.environ, "_RUN_TYPE": "WEB"},
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_app_retains_other_routes_without_cluster_dependencies():
    _run("""
        from serve import app
        import gunicorn_config
        paths = {getattr(route, 'path', '') for route in app.routes}
        assert not any(path.startswith('/api/tools/cluster') for path in paths)
        for prefix in ('/api/villages', '/api/tools/praat', '/api/tools/check',
                       '/api/tools/merge', '/api/tools/jyut2ipa', '/api/vocabulary'):
            assert any(path.startswith(prefix) for path in paths), prefix
    """)


def test_background_lifecycle_retains_services_without_cluster_executor():
    _run("""
        import types
        from unittest.mock import patch
        from app.lifecycle import background

        calls = []
        services = {
            'app.service.logging.core.workers':
                ('start_api_logger_workers', 'stop_api_logger_workers'),
            'app.service.logging.tasks': ('start_scheduler', 'stop_scheduler'),
            'app.service.vocabulary.backup':
                ('start_backup_scheduler', 'stop_backup_scheduler'),
        }
        modules = {}
        for module_name, functions in services.items():
            module = types.ModuleType(module_name)
            for name in functions:
                setattr(module, name, lambda name=name: calls.append(name))
            modules[module_name] = module

        with patch.dict(sys.modules, modules):
            background.start_background_services()
            try:
                assert background._cleanup_thread.is_alive()
                import threading
                assert not any(t.name == 'cluster_executor' for t in threading.enumerate())
            finally:
                background.stop_background_services()

        assert set(calls) == {name for functions in services.values() for name in functions}
        assert len(calls) == 6
        assert background._cleanup_thread is None
    """)
