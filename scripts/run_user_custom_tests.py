"""Run selected tests with import-time ORM initialization redirected to temp DBs."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    import pytest
    import app.common.path as paths

    with tempfile.TemporaryDirectory(prefix="custom-tests-") as directory:
        for name in ("SUPPLE_DB", "USER_DATABASE", "LOGS_DATABASE", "VOCABULARY_DB"):
            target = str(Path(directory) / f"{name.lower()}.db")
            setattr(paths, f"{name}_PATH", target)
            setattr(paths, f"{name}_URL", f"sqlite:///{target}")
        return pytest.main(sys.argv[1:] or ["tests/test_user_custom_read_apis.py", "tests/test_user_custom_delete.py", "tests/test_admin_custom_identity.py", "-q"])


if __name__ == "__main__":
    raise SystemExit(main())
