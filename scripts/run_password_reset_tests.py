"""Run reset tests with import-time database initialization isolated from real data."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    import pytest
    import app.common.path as paths

    with tempfile.TemporaryDirectory(prefix='password-reset-tests-') as directory:
        for name in ('SUPPLE_DB', 'USER_DATABASE', 'LOGS_DATABASE', 'VOCABULARY_DB'):
            target = str(Path(directory) / f'{name.lower()}.db')
            setattr(paths, f'{name}_PATH', target)
            setattr(paths, f'{name}_URL', f'sqlite:///{target}')
        return pytest.main(sys.argv[1:] or [
            'tests/test_password_reset.py', 'tests/test_password_reset_mail.py',
            'tests/test_password_reset_mailbox.py', 'tests/test_password_reset_routes.py',
            '-q', '--disable-warnings',
        ])


if __name__ == '__main__':
    raise SystemExit(main())
