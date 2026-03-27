import time
from queue import Empty

from app.service.logging.core.queues import enqueue_with_backpressure, online_time_queue


def enqueue_online_time_non_blocking(data: dict):
    """
    Enqueue an online-time payload without blocking the request path.
    """
    return enqueue_with_backpressure(online_time_queue, data, "online_time_queue")


def online_time_writer():
    """
    Background thread: batch write online time updates.
    """
    batch = {}
    last_write_time = time.time()
    batch_timeout = 30

    while True:
        try:
            item = online_time_queue.get(timeout=5)
            if item is None:
                break

            key = (item['user_id'], item.get('session_id'))
            if key in batch:
                batch[key]['seconds'] += item['seconds']
                if item.get('timestamp') and (
                    not batch[key].get('timestamp') or
                    item['timestamp'] > batch[key]['timestamp']
                ):
                    batch[key]['timestamp'] = item['timestamp']
            else:
                batch[key] = item

            current_time = time.time()
            should_write = (
                len(batch) >= 50 or
                (current_time - last_write_time) >= batch_timeout
            )

            if should_write:
                write_online_time_batch(batch)
                batch = {}
                last_write_time = current_time

        except Empty:
            if batch:
                write_online_time_batch(batch)
                batch = {}
                last_write_time = time.time()
        except Exception as e:
            print(f"[X] Online time writer error: {e}")

    if batch:
        write_online_time_batch(batch)


def write_online_time_batch(batch: dict):
    """Write aggregated online time updates to database."""
    from sqlalchemy import func

    from app.service.auth.database.connection import SessionLocal as AuthSessionLocal
    from app.service.auth.database.models import Session, User

    db = AuthSessionLocal()
    try:
        for (user_id, session_id), item in batch.items():
            seconds = item['seconds']
            last_seen_at = item.get('timestamp')

            db.query(User).filter(User.id == user_id).update(
                {
                    User.total_online_seconds: func.coalesce(User.total_online_seconds, 0) + seconds,
                    User.last_seen: last_seen_at,
                },
                synchronize_session=False,
            )

            if session_id:
                db.query(Session).filter(
                    Session.session_id == session_id
                ).update(
                    {
                        Session.total_online_seconds: func.coalesce(Session.total_online_seconds, 0) + seconds,
                        Session.last_seen: last_seen_at,
                    },
                    synchronize_session=False,
                )

        db.commit()
        print(f"[OnlineTimeWriter] Batch wrote {len(batch)} online time updates")
    except Exception as e:
        print(f"[X] Failed to write online time batch: {e}")
        db.rollback()
    finally:
        db.close()
