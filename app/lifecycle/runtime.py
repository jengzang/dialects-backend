import os


def is_gunicorn_worker_process() -> bool:
    """Return True when running inside a gunicorn worker process."""
    return os.environ.get("SERVER_SOFTWARE", "").startswith("gunicorn")
