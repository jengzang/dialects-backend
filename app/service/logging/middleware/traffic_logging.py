import asyncio
# import gzip
# import io
import json
# import os
import threading
import multiprocessing  # [FIX] 鏀圭敤璺ㄨ繘绋嬮槦鍒?
import time
from datetime import datetime
# from collections import defaultdict
# import ast
from decimal import Decimal
# from typing import AsyncIterable, Optional

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session
# from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware
from queue import Empty, Full  # multiprocessing.Queue 婊￠槦鍒楁椂浼氭姏鍑?queue.Full
from app.service.auth.database.connection import get_db
from app.service.auth.core.dependencies import get_current_user_for_middleware
from app.service.auth.database.models import ApiUsageLog, ApiUsageSummary
from app.service.logging.core.database import SessionLocal as LogsSessionLocal
from app.service.logging.core.models import ApiKeywordLog
from app.common.api_config import RECORD_API, IGNORE_API, MAX_ANONYMOUS_SIZE, MAX_USER_SIZE
from app.common.time_utils import now_utc_naive, to_shanghai_bucket_date, to_shanghai_bucket_hour
from app.service.logging.utils.route_matcher import match_route_config, should_skip_route


# === 璺緞瑙勮寖鍖栧嚱鏁?===
def normalize_api_path(path: str) -> str:
    """
    瑙勮寖鍖?API 璺緞锛屽皢璺緞鍙傛暟鏇挎崲涓哄崰浣嶇

    鏍规嵁瀹屾暣璺緞鍓嶇紑绮剧‘鍖归厤锛岄伩鍏嶈鍒?

    绀轰緥锛?
        /admin/sessions/user/123 -> /admin/sessions/user/{user_id}
        /api/tools/check/download/abc-123 -> /api/tools/check/download/{task_id}
        /api/villages/village/features/12345 -> /api/villages/village/features/{village_id}

    Args:
        path: 鍘熷 API 璺緞

    Returns:
        瑙勮寖鍖栧悗鐨勮矾寰?
    """
    # 绮剧‘鐨勮矾寰勬ā鏉挎槧灏勶紙鏍规嵁瀹為檯璺敱瀹氫箟锛?
    # 鏍煎紡锛?鍓嶇紑, 鍙傛暟鍚?
    path_templates = [
        # Admin - Sessions
        ('/admin/sessions/user/', '{user_id}'),
        ('/admin/sessions/revoke-user/', '{user_id}'),
        ('/admin/sessions/revoke/', '{token_id}'),

        # Admin - User Sessions
        ('/admin/user-sessions/user/', '{user_id}'),
        ('/admin/user-sessions/revoke-user/', '{user_id}'),
        ('/admin/user-sessions/', '{session_id}'),  # 娉ㄦ剰锛氳繖涓鏀惧湪鏈€鍚庯紝閬垮厤璇尮閰?

        # Admin - IP
        ('/admin/ip/', '{api_name}/{ip}'),  # 鐗规畩锛氫袱涓弬鏁?

        # API - Tools (Check)
        ('/api/tools/check/download/', '{task_id}'),

        # API - Tools (Jyut2IPA)
        ('/api/tools/jyut2ipa/download/', '{task_id}'),
        ('/api/tools/jyut2ipa/progress/', '{task_id}'),

        # API - Tools (Merge)
        ('/api/tools/merge/download/', '{task_id}'),
        ('/api/tools/merge/progress/', '{task_id}'),

        # API - Tools (Praat)
        ('/api/tools/praat/jobs/progress/', '{job_id}'),
        ('/api/tools/praat/uploads/progress/', '{task_id}'),

        # API - Villages (Admin)
        ('/api/villages/admin/run-ids/active/', '{analysis_type}'),
        ('/api/villages/admin/run-ids/available/', '{analysis_type}'),
        ('/api/villages/admin/run-ids/metadata/', '{run_id}'),

        # API - Villages (Village)
        ('/api/villages/village/complete/', '{village_id}'),
        ('/api/villages/village/features/', '{village_id}'),
        ('/api/villages/village/ngrams/', '{village_id}'),
        ('/api/villages/village/semantic-structure/', '{village_id}'),
        ('/api/villages/village/spatial-features/', '{village_id}'),

        # API - Villages (Semantic)
        ('/api/villages/semantic/subcategory/chars/', '{subcategory}'),

        # API - Villages (Spatial)
        ('/api/villages/spatial/hotspots/', '{hotspot_id}'),
        ('/api/villages/spatial/integration/by-character/', '{character}'),
        ('/api/villages/spatial/integration/by-cluster/', '{cluster_id}'),

        # SQL
        # ('/sql/distinct/', '{db_key}/{table_name}/{column}'),  # 鐗规畩锛氫笁涓弬鏁?
    ]

    # 鎸夊墠缂€闀垮害闄嶅簭鎺掑簭锛岀‘淇濇洿鍏蜂綋鐨勮矾寰勫厛鍖归厤
    path_templates.sort(key=lambda x: len(x[0]), reverse=True)

    for prefix, param_name in path_templates:
        if path.startswith(prefix):
            # 鎻愬彇鍓嶇紑鍚庣殑閮ㄥ垎
            suffix = path[len(prefix):]

            # 濡傛灉鍚庨潰杩樻湁璺緞锛堝 /activity, /revoke锛夛紝淇濈暀
            if '/' in suffix:
                # 鍙浛鎹㈢涓€娈?
                parts = suffix.split('/', 1)
                return f"{prefix}{param_name}/{parts[1]}"
            else:
                # 鏁翠釜鍚庣紑閮芥槸鍙傛暟
                return f"{prefix}{param_name}"

    # 娌℃湁鍖归厤鍒帮紝杩斿洖鍘熻矾寰?
    return path


# === 闃熷垪锛堣法杩涚▼锛?===
# [FIX] 鏀圭敤 multiprocessing.Queue 浠ユ敮鎸佷富杩涚▼涓殑鍚庡彴绾跨▼
# keyword_queue = queue.Queue()  # [X] 涓嶅啀浣跨敤 txt鏂囦欢闃熷垪
log_queue = multiprocessing.Queue(maxsize=2000)  # [OK] ApiUsageLog 闃熷垪锛坅uth.db锛? 闄愬埗 2000 鏉?keyword_log_queue = multiprocessing.Queue(maxsize=5000)  # [OK] ApiKeywordLog 闃熷垪锛坙ogs.db锛? 闄愬埗 5000 鏉?statistics_queue = multiprocessing.Queue(maxsize=3000)  # [OK] ApiStatistics 闃熷垪锛坙ogs.db锛? 闄愬埗 3000 鏉★紙淇濆畧涓婅皟锛?html_visit_queue = multiprocessing.Queue(maxsize=1000)  # [OK] HTML 椤甸潰璁块棶缁熻闃熷垪锛坙ogs.db锛? 闄愬埗 1000 鏉★紙淇濆畧涓婅皟锛?summary_queue = multiprocessing.Queue(maxsize=1000)  # [NEW] ApiUsageSummary 闃熷垪锛坅uth.db锛? 闄愬埗 1000 鏉?online_time_queue = multiprocessing.Queue(maxsize=1000)  # [NEW] Online time reports 闃熷垪锛坅uth.db锛? 闄愬埗 1000 鏉?

QUEUE_PUT_TIMEOUT_SECONDS = 0.05  # 婊￠槦鍒楁椂鏈€澶氳儗鍘?50ms


def _enqueue_with_backpressure(q, item, queue_name: str) -> bool:
    """Try enqueue with short backpressure instead of immediate drop."""
    try:
        q.put(item, timeout=QUEUE_PUT_TIMEOUT_SECONDS)
        return True
    except Full:
        print(
            f"[WARN] {queue_name} is full after {int(QUEUE_PUT_TIMEOUT_SECONDS * 1000)}ms, dropping entry"
        )
        return False


# === 鍏抽敭璇嶆棩蹇楋紙鍐欏叆logs.db锛?===
async def _capture_request_body(request: Request) -> bytes:
    """Read request body and restore stream for downstream handlers."""
    body = await request.body()

    async def receive():
        return {"type": "http.request", "body": body}

    request._receive = receive
    return body


async def _log_params_if_needed(request: Request, path: str):
    """
    Keep legacy logs.db parameter logging logic:
    - route-based params/body logging
    """
    if should_skip_route(path):
        return

    config = match_route_config(path)
    if not config.get("log_params") and not config.get("log_body"):
        return

    params_to_log = {}

    if config.get("log_params") and request.query_params:
        params_to_log.update(dict(request.query_params))

    if config.get("log_body") and request.method in ["POST", "PUT", "PATCH"]:
        try:
            body = await _capture_request_body(request)
            if body:
                try:
                    body_data = json.loads(body)
                    if isinstance(body_data, dict):
                        params_to_log.update(body_data)
                    else:
                        params_to_log["_raw_body"] = body.decode("utf-8", errors="ignore")
                except json.JSONDecodeError:
                    params_to_log["_raw_body"] = body.decode("utf-8", errors="ignore")
        except Exception as e:
            print(f"[WARN] failed to read request body for params logging: {e}")

    if params_to_log:
        try:
            log_all_fields(path, params_to_log)
        except Exception as e:
            print(f"[ERROR] failed to enqueue params logs: {e}")

def log_keyword(path: str, field: str, value):
    """璁板綍 API 璋冪敤鐨勫弬鏁板叧閿瘝鍒版暟鎹簱"""
    timestamp = now_utc_naive()
    log = ApiKeywordLog(
        timestamp=timestamp,
        path=path,
        field=field,
        value=str(value)
    )
    _enqueue_with_backpressure(keyword_log_queue, log, "keyword_log_queue")


def log_all_fields(path: str, param_dict: dict):
    """Log all request fields for keyword statistics."""
    for field, value in param_dict.items():
        if value is not None and value != [] and value != "":
            log_keyword(path, field, value)


# ===鍏抽敭璇嶆棩蹇楀啓鍏ョ嚎绋嬶紙logs.db锛?==
def keyword_log_writer():
    """鍚庡彴绾跨▼锛氭壒閲忓啓鍏?ApiKeywordLog 鍒?logs.db"""
    batch = []
    batch_size = 50  # 姣?50 鏉℃壒閲忓啓鍏ヤ竴娆?

    while True:
        try:
            # 绛夊緟闃熷垪涓殑鏁版嵁锛岃秴鏃?绉?
            item = keyword_log_queue.get(timeout=1)
            if item is None:  # 鍋滄淇″彿
                break

            batch.append(item)

            # 鎵归噺鍐欏叆
            if len(batch) >= batch_size:
                db = LogsSessionLocal()
                try:
                    db.bulk_save_objects(batch)
                    db.commit()
                    # print(f"[KeywordLogWriter] 鉁?鎵归噺鍐欏叆 {len(batch)} 鏉″叧閿瘝鏃ュ織鍒版暟鎹簱")
                    batch = []
                except Exception as e:
                    print(f"[X] 鍐欏叆鍏抽敭璇嶆棩蹇楀け璐? {e}")
                    db.rollback()
                finally:
                    db.close()

        except Empty:
            # 闃熷垪绌烘椂锛屽啓鍏ュ墿浣欐暟鎹?
            if batch:
                db = LogsSessionLocal()
                try:
                    db.bulk_save_objects(batch)
                    db.commit()
                    # print(f"[KeywordLogWriter] 鉁?瓒呮椂鍐欏叆 {len(batch)} 鏉″叧閿瘝鏃ュ織鍒版暟鎹簱")
                    batch = []
                except Exception as e:
                    print(f"[X] 鍐欏叆鍏抽敭璇嶆棩蹇楀け璐? {e}")
                    db.rollback()
                finally:
                    db.close()
        except Exception as e:
            print(f"[X] 鍏抽敭璇嶆棩蹇楃嚎绋嬮敊璇? {e}")

    # 绾跨▼缁撴潫鍓嶏紝鍐欏叆鍓╀綑鏁版嵁
    if batch:
        db = LogsSessionLocal()
        try:
            db.bulk_save_objects(batch)
            db.commit()
        except Exception as e:
            print(f"[X] 鍐欏叆鍏抽敭璇嶆棩蹇楀け璐? {e}")
            db.rollback()
        finally:
            db.close()


# === API缁熻鏇存柊绾跨▼锛坙ogs.db锛?==
def statistics_writer():
    """鍚庡彴绾跨▼锛氭壒閲忔洿鏂?ApiStatistics"""
    batch = []
    batch_size = 100
    batch_timeout = 120.0

    while True:
        try:
            item = statistics_queue.get(timeout=batch_timeout)
            if item is None:  # 鍋滄淇″彿
                break

            batch.append(item)

            # 鎵规婊℃椂鍐欏叆
            if len(batch) >= batch_size:
                _process_statistics_batch(batch)
                batch = []

        except Empty:
            # 瓒呮椂鏃跺啓鍏ュ墿浣欓」
            if batch:
                _process_statistics_batch(batch)
                batch = []
        except Exception as e:
            print(f"[X] statistics_writer 閿欒: {e}")

    # 绾跨▼缁撴潫鍓嶅啓鍏ュ墿浣欐暟鎹?
    if batch:
        _process_statistics_batch(batch)


def _process_statistics_batch_legacy(batch: list):
    """鎵归噺澶勭悊缁熻鏇存柊"""
    from sqlalchemy import text

    db = LogsSessionLocal()
    try:
        for path, date_obj in batch:
            # 瑙勮寖鍖栬矾寰勶紙鏇挎崲璺緞鍙傛暟涓哄崰浣嶇锛?            normalized_path = normalize_api_path(path)

            # 鏂板锛氭洿鏂?api_usage_hourly 琛紙灏忔椂绾ф€昏皟鐢ㄧ粺璁★級
            # 浣跨敤璇锋眰鍒拌揪鏃剁殑鏃堕棿锛坉ate_obj锛夛紝鑰屼笉鏄啓鍏ユ椂鐨勬椂闂?            request_hour = to_shanghai_bucket_hour(date_obj)
            result = db.execute(
                text("""
                    UPDATE api_usage_hourly
                    SET total_calls = total_calls + 1, updated_at = datetime('now')
                    WHERE hour = :hour
                """),
                {"hour": request_hour}
            )
            if result.rowcount == 0:
                db.execute(
                    text("""
                        INSERT OR IGNORE INTO api_usage_hourly (hour, total_calls)
                        VALUES (:hour, 1)
                    """),
                    {"hour": request_hour}
                )

            # 鏂板锛氭洿鏂?api_usage_daily 琛紙姣忔棩姣廇PI璋冪敤缁熻锛?
            # 浣跨敤璇锋眰鍒拌揪鏃剁殑鏃ユ湡锛坉ate_obj锛夛紝鑰屼笉鏄啓鍏ユ椂鐨勬棩鏈?
            request_date = to_shanghai_bucket_date(date_obj)
            result = db.execute(
                text("""
                    UPDATE api_usage_daily
                    SET call_count = call_count + 1, updated_at = datetime('now')
                    WHERE date = :date AND path = :path
                """),
                {"date": request_date, "path": normalized_path}
            )
            if result.rowcount == 0:
                db.execute(
                    text("""
                        INSERT OR IGNORE INTO api_usage_daily (date, path, call_count)
                        VALUES (:date, :path, 1)
                    """),
                    {"date": request_date, "path": normalized_path}  # 淇锛氫娇鐢?normalized_path
                )

        db.commit()
        # print(f"[OK] 鎵归噺鏇存柊 {len(batch)} 鏉＄粺璁?)
    except Exception as e:
        print(f"[X] 缁熻鎵规澶辫触: {e}")
        db.rollback()
    finally:
        db.close()



# === API璋冪敤缁熻锛堝啓鍏ogs.db锛?==
def _process_statistics_batch(batch: list):
    """Batch process usage counters with in-memory aggregation."""
    from sqlalchemy import text

    db = LogsSessionLocal()
    try:
        hourly_counts = {}
        daily_counts = {}

        for path, date_obj in batch:
            request_hour = to_shanghai_bucket_hour(date_obj)
            hourly_counts[request_hour] = hourly_counts.get(request_hour, 0) + 1

            request_date = to_shanghai_bucket_date(date_obj)
            normalized_path = normalize_api_path(path)
            daily_key = (request_date, normalized_path)
            daily_counts[daily_key] = daily_counts.get(daily_key, 0) + 1

        for hour, inc in hourly_counts.items():
            db.execute(
                text("""
                    INSERT INTO api_usage_hourly (hour, total_calls, updated_at)
                    VALUES (:hour, :inc, datetime('now'))
                    ON CONFLICT(hour) DO UPDATE SET
                        total_calls = total_calls + excluded.total_calls,
                        updated_at = datetime('now')
                """),
                {"hour": hour, "inc": inc}
            )

        for (date_key, path_key), inc in daily_counts.items():
            db.execute(
                text("""
                    INSERT INTO api_usage_daily (date, path, call_count, updated_at)
                    VALUES (:date, :path, :inc, datetime('now'))
                    ON CONFLICT(date, path) DO UPDATE SET
                        call_count = call_count + excluded.call_count,
                        updated_at = datetime('now')
                """),
                {"date": date_key, "path": path_key, "inc": inc}
            )

        db.commit()
    except Exception as e:
        print(f"[X] statistics batch failed: {e}")
        db.rollback()
    finally:
        db.close()


def update_count(path: str):
    """鏇存柊 API 璋冪敤娆℃暟缁熻"""
    today = now_utc_naive()
    _enqueue_with_backpressure(statistics_queue, (path, today), "statistics_queue")


def enqueue_online_time_non_blocking(data: dict):
    """
    闈為樆濉炲叆闃熷湪绾挎椂闀挎姤鍛?

    Args:
        data: 鍖呭惈 user_id, session_id, seconds, timestamp 鐨勫瓧鍏?

    濡傛灉闃熷垪婊′簡锛岀洿鎺ュ啓鍏ユ暟鎹簱锛堝厹搴曠瓥鐣ワ級
    """
    try:
        online_time_queue.put_nowait(data)
    except Full:
        # 闃熷垪婊′簡锛岀洿鎺ュ啓鍏ユ暟鎹簱锛堝厹搴曠瓥鐣ワ級
        print(f"[!] online_time_queue 宸叉弧锛岀洿鎺ュ啓鍏ユ暟鎹簱")
        _write_online_time_batch({
            (data['user_id'], data.get('session_id')): data
        })


def update_html_visit(path: str):
    """鏇存柊 HTML 椤甸潰璁块棶娆℃暟缁熻"""
    today = now_utc_naive()
    _enqueue_with_backpressure(html_visit_queue, (path, today), "html_visit_queue")


# === HTML 椤甸潰璁块棶缁熻鍐欏叆绾跨▼锛坙ogs.db锛?==
def html_visit_writer():
    """鍚庡彴绾跨▼锛氭壒閲忔洿鏂?HTML 椤甸潰璁块棶缁熻"""
    batch = []
    batch_size = 20
    batch_timeout = 5.0

    while True:
        try:
            item = html_visit_queue.get(timeout=batch_timeout)
            if item is None:  # 鍋滄淇″彿
                break

            batch.append(item)

            # 鎵规婊℃椂鍐欏叆
            if len(batch) >= batch_size:
                _process_html_visit_batch(batch)
                batch = []

        except Empty:
            # 瓒呮椂鏃跺啓鍏ュ墿浣欓」
            if batch:
                _process_html_visit_batch(batch)
                batch = []
        except Exception as e:
            print(f"[X] html_visit_writer 閿欒: {e}")

    # 绾跨▼缁撴潫鍓嶅啓鍏ュ墿浣欐暟鎹?
    if batch:
        _process_html_visit_batch(batch)


def _process_html_visit_batch(batch: list):
    """鎵归噺澶勭悊 HTML 璁块棶缁熻"""
    db = LogsSessionLocal()
    try:
        for path, date_obj in batch:
            # 鏇存柊鎬昏
            update_html_visit_stat(db, path, None)

            # 鏇存柊姣忔棩缁熻
            update_html_visit_stat(db, path, to_shanghai_bucket_date(date_obj))

        db.commit()
        print(f"[OK] 鎵归噺鏇存柊 {len(batch)} 鏉?HTML 璁块棶缁熻")
    except Exception as e:
        print(f"[X] HTML 璁块棶缁熻鎵规澶辫触: {e}")
        db.rollback()
    finally:
        db.close()


def update_html_visit_stat(db: Session, path: str, date):
    """Upsert one HTML visit statistic row."""
    from sqlalchemy import text

    # 浣跨敤 SQLite 鐨?INSERT OR REPLACE 璇硶锛圲PSERT锛?
    # 杩欐牱鍙互閬垮厤 rollback 褰卞搷鏁翠釜 session
    try:
        # 鍏堝皾璇曟洿鏂?
        result = db.execute(
            text("""
                UPDATE api_visit_log
                SET count = count + 1, updated_at = datetime('now')
                WHERE path = :path AND (
                    (date IS NULL AND :date IS NULL) OR
                    (date = :date)
                )
            """),
            {"path": path, "date": date}
        )

        # 濡傛灉娌℃湁鏇存柊浠讳綍琛岋紙璁板綍涓嶅瓨鍦級锛屽垯鎻掑叆鏂拌褰?
        if result.rowcount == 0:
            db.execute(
                text("""
                    INSERT OR IGNORE INTO api_visit_log (path, date, count, updated_at)
                    VALUES (:path, :date, 1, datetime('now'))
                """),
                {"path": path, "date": date}
            )
    except Exception as e:
        print(f"[X] 鏇存柊 HTML 璁块棶缁熻澶辫触: path={path}, date={date}, error={e}")
        raise



def log_writer_thread():
    """Batch-write ApiUsageLog rows into auth.db."""
    from app.service.auth.database.connection import SessionLocal as AuthSessionLocal

    # 鍦ㄧ嚎绋嬪唴鍒涘缓鏁版嵁搴撹繛鎺ワ紙閬垮厤璺ㄨ繘绋嬩紶閫掞級
    db = AuthSessionLocal()

    try:
        batch = []
        batch_size = 50
        batch_timeout = 120.0

        while True:
            try:
                # 浣跨敤瓒呮椂绛夊緟锛岃€岄潪 sleep
                item = log_queue.get(timeout=batch_timeout)

                if item is None:  # 鍋滄淇″彿
                    break

                batch.append(item)

                # 鎵规婊℃椂鍐欏叆
                if len(batch) >= batch_size:
                    _write_log_batch(db, batch)
                    batch = []

            except Empty:
                # 瓒呮椂鏃跺啓鍏ュ墿浣欓」
                if batch:
                    _write_log_batch(db, batch)
                    batch = []
            except Exception as e:
                print(f"[X] log_writer_thread 閿欒: {e}")

        # 绾跨▼缁撴潫鍓嶅啓鍏ュ墿浣欐暟鎹?
        if batch:
            _write_log_batch(db, batch)
    finally:
        db.close()


def _write_log_batch(db: Session, batch: list):
    """鎵归噺鍐欏叆鏃ュ織"""
    try:
        db.bulk_save_objects(batch)
        db.commit()
        print(f"[OK] Batch wrote {len(batch)} ApiUsageLog rows")
    except Exception as e:
        print(f"[X] 鎵归噺鍐欏叆澶辫触: {e}")
        db.rollback()


# 寮傛鍐欏叆鏃ュ織鐨勫嚱鏁?
def log_detailed_api_to_db(
        path: str,
        duration: float,
        status_code: int,
        ip: str,
        user_agent: str,
        referer: str,
        user_id: int = None,
        request_size: int = 0,
        response_size: int = 0,
        start_time: float = None
):
    # Step 1: build detailed log and enqueue for background writer
    log = ApiUsageLog(
        path=path,
        duration=duration,
        status_code=status_code,
        ip=ip,
        user_agent=user_agent,
        referer=referer,
        user_id=user_id,
        request_size=request_size,
        response_size=response_size,
        # 濡傛灉浼犲叆浜?start_time锛屼娇鐢ㄥ畠锛涘惁鍒欙紝浣跨敤鏁版嵁搴撻粯璁ゆ椂闂?
        called_at=datetime.utcfromtimestamp(start_time) if start_time else None  # 鐩存帴鍦ㄥ垱寤烘椂澶勭悊
    )

    # 灏嗘棩蹇楁坊鍔犲埌闃熷垪
    _enqueue_with_backpressure(log_queue, log, "log_queue")

    # Step 2: enqueue ApiUsageSummary update
    if user_id:
        _enqueue_with_backpressure(
            summary_queue,
            {
                'user_id': user_id,
                'path': path,
                'duration': duration,
                'request_size': request_size,
                'response_size': response_size
            },
            "summary_queue"
        )


def summary_writer():
    """鎵归噺鏇存柊 ApiUsageSummary"""
    batch = []
    batch_size = 50
    batch_timeout = 60.0

    while True:
        try:
            item = summary_queue.get(timeout=batch_timeout)

            if item is None:
                break

            batch.append(item)

            if len(batch) >= batch_size:
                _process_summary_batch(batch)
                batch = []

        except Empty:
            if batch:
                _process_summary_batch(batch)
                batch = []
        except Exception as e:
            print(f"[X] summary_writer 閿欒: {e}")

    if batch:
        _process_summary_batch(batch)


def _process_summary_batch(batch: list):
    """鎵归噺澶勭悊 ApiUsageSummary 鏇存柊"""
    from app.service.auth.database.connection import SessionLocal as AuthSessionLocal
    db = AuthSessionLocal()

    try:
        # 鎸?(user_id, path) 鍒嗙粍鑱氬悎
        aggregated = {}
        for item in batch:
            key = (item['user_id'], item['path'])
            if key not in aggregated:
                aggregated[key] = {
                    'count': 0,
                    'total_duration': 0,
                    'total_upload': 0,
                    'total_download': 0
                }

            aggregated[key]['count'] += 1
            aggregated[key]['total_duration'] += item['duration']
            aggregated[key]['total_upload'] += item['request_size'] / 1024
            aggregated[key]['total_download'] += item['response_size'] / 1024

        # 鎵归噺鏇存柊
        for (user_id, path), stats in aggregated.items():
            summary = db.query(ApiUsageSummary).filter_by(
                user_id=user_id, path=path
            ).first()

            if summary:
                summary.count += stats['count']
                summary.total_duration += Decimal(round(stats['total_duration'], 2))
                summary.total_upload += Decimal(round(stats['total_upload'], 2))
                summary.total_download += Decimal(round(stats['total_download'], 2))
                summary.last_updated = datetime.utcnow()
            else:
                summary = ApiUsageSummary(
                    user_id=user_id,
                    path=path,
                    count=stats['count'],
                    total_duration=Decimal(round(stats['total_duration'], 2)),
                    total_upload=Decimal(round(stats['total_upload'], 2)),
                    total_download=Decimal(round(stats['total_download'], 2)),
                    last_updated=datetime.utcnow()
                )
                db.add(summary)

        db.commit()
        print(f"[OK] 鎵归噺鏇存柊 {len(aggregated)} 鏉?ApiUsageSummary")
    except Exception as e:
        print(f"[X] ApiUsageSummary 鎵规澶辫触: {e}")
        db.rollback()
    finally:
        db.close()


def online_time_writer():
    """
    Background thread: batch write online time updates
    Aggregates multiple reports for same user/session before writing
    """
    batch = {}  # {(user_id, session_id): total_seconds}
    last_write_time = time.time()
    batch_timeout = 30  # Write every 30 seconds

    while True:
        try:
            # Get item from queue with timeout
            item = online_time_queue.get(timeout=5)
            if item is None:  # Stop signal
                break

            # Aggregate by (user_id, session_id)
            key = (item['user_id'], item.get('session_id'))
            if key in batch:
                batch[key]['seconds'] += item['seconds']
            else:
                batch[key] = item

            # Write if batch is large or timeout reached
            current_time = time.time()
            should_write = (
                len(batch) >= 50 or  # Batch size limit
                (current_time - last_write_time) >= batch_timeout  # Time limit
            )

            if should_write:
                _write_online_time_batch(batch)
                batch = {}
                last_write_time = current_time

        except Empty:
            # Timeout - write remaining batch if any
            if batch:
                _write_online_time_batch(batch)
                batch = {}
                last_write_time = time.time()
        except Exception as e:
            print(f"[X] Online time writer error: {e}")

    # Write remaining batch on shutdown
    if batch:
        _write_online_time_batch(batch)


def _write_online_time_batch(batch: dict):
    """Write aggregated online time updates to database"""
    from app.service.auth.database.connection import SessionLocal as AuthSessionLocal
    from app.service.auth.database.models import User, Session

    db = AuthSessionLocal()
    try:
        for (user_id, session_id), item in batch.items():
            seconds = item['seconds']

            # Update user
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                user.total_online_seconds = (user.total_online_seconds or 0) + seconds
                user.last_seen = datetime.utcnow()

            # Update session if exists
            if session_id:
                session = db.query(Session).filter(
                    Session.session_id == session_id
                ).first()
                if session:
                    session.total_online_seconds = (session.total_online_seconds or 0) + seconds
                    session.last_seen = datetime.utcnow()

        db.commit()
        print(f"[OnlineTimeWriter] 鉁?Batch wrote {len(batch)} online time updates")
    except Exception as e:
        print(f"[X] Failed to write online time batch: {e}")
        db.rollback()
    finally:
        db.close()


async def log_detailed_api_to_db_async(
        path: str,
        duration: float,
        status_code: int,
        ip: str,
        user_agent: str,
        referer: str,
        user_id: int = None,
        request_size: int = 0,
        response_size: int = 0,
        start_time: float = None
):
    """寮傛鍖呰鍣細灏嗗悓姝ユ棩蹇楀叆闃熸搷浣滃紓姝ュ寲"""
    await asyncio.to_thread(
        log_detailed_api_to_db,
        path,
        duration,
        status_code,
        ip,
        user_agent,
        referer,
        user_id,
        request_size,
        response_size,
        start_time
    )


# app/service/api_logger.py
_workers_started = False
_start_lock = threading.Lock()


def start_api_logger_workers():
    """鍚姩鎵€鏈夋棩蹇楀悗鍙扮嚎绋嬶紙鍦ㄤ富杩涚▼涓級"""
    global _workers_started
    with _start_lock:
        if _workers_started:
            return

        # [OK] 鍚姩鍏抽敭璇嶆棩蹇楀啓鍏ョ嚎绋嬶紙logs.db锛?
        threading.Thread(target=keyword_log_writer, daemon=True).start()

        # [OK] 鍚姩API缁熻鏇存柊绾跨▼锛坙ogs.db锛?
        threading.Thread(target=statistics_writer, daemon=True).start()

        # [OK] 鍚姩HTML椤甸潰璁块棶缁熻绾跨▼锛坙ogs.db锛?
        threading.Thread(target=html_visit_writer, daemon=True).start()

        # [OK] 鍚姩 ApiUsageLog 鍐欏叆绾跨▼锛坅uth.db锛?
        # 娉ㄦ剰锛氫笉浼犻€抎b鍙傛暟锛岃绾跨▼鍐呴儴鍒涘缓杩炴帴
        threading.Thread(target=log_writer_thread, daemon=True).start()

        # [NEW] 鍚姩 ApiUsageSummary 鏇存柊绾跨▼锛坅uth.db锛?
        threading.Thread(target=summary_writer, daemon=True).start()

        # [NEW] 鍚姩 Online Time 鏇存柊绾跨▼锛坅uth.db锛?
        threading.Thread(target=online_time_writer, daemon=True).start()

        _workers_started = True
        print("[OK] API logger workers started")


def stop_api_logger_workers():
    """Stop all background logging workers."""
    try:
        keyword_log_queue.put_nowait(None)  # [OK] 鍋滄鍏抽敭璇嶆棩蹇楃嚎绋?
    except:
        pass

    try:
        statistics_queue.put_nowait(None)  # [OK] 鍋滄缁熻绾跨▼
    except:
        pass

    try:
        html_visit_queue.put_nowait(None)  # [OK] 鍋滄HTML璁块棶缁熻绾跨▼
    except:
        pass

    try:
        log_queue.put_nowait(None)  # 鍋滄 ApiUsageLog 绾跨▼
    except:
        pass

    try:
        summary_queue.put_nowait(None)  # [NEW] 鍋滄 ApiUsageSummary 绾跨▼
    except:
        pass

    try:
        online_time_queue.put_nowait(None)  # [NEW] 鍋滄 Online Time 绾跨▼
    except:
        pass

    print("[OK] API logger workers stopped")


class StreamingResponseWrapper:
    """娴佸紡鍝嶅簲鍖呰鍣?- 杈逛紶杈撹竟缁熻锛屼笉缂撳啿鏁翠釜鍝嶅簲"""

    def __init__(self, iterator, content_type, user_role, max_size, response, on_complete_callback=None):
        self.iterator = iterator
        self.content_type = content_type
        self.user_role = user_role
        self.max_size = max_size
        self.response = response
        self.total_size = 0
        self.on_complete_callback = on_complete_callback

    async def __aiter__(self):
        """寮傛杩唬鍣?- 娴佸紡浼犺緭鍝嶅簲"""
        try:
            async for chunk in self.iterator:
                chunk_size = len(chunk)
                self.total_size += chunk_size

                # 娓愯繘寮忓ぇ灏忔鏌?- 瓒呴檺绔嬪嵆涓柇
                if self.total_size > self.max_size:
                    raise HTTPException(
                        status_code=413,
                        detail="馃毇 鐢辨柤鏈嶅嫏鍣ㄩ檺鍒讹紝鎮ㄧ殑杩斿洖鏁告摎瓒呴亷闄愬埗锛岃珛娓涘皯璜嬫眰绡勫湇 馃洃"
                    )

                # 鐩存帴杞彂鏁版嵁锛屼笉鍋氫换浣曚慨鏀?
                yield chunk

        finally:
            # 娴佸紡浼犺緭瀹屾垚鍚庤皟鐢ㄥ洖璋?
            if self.on_complete_callback:
                await self.on_complete_callback(self)


# 杩欓噷鏄腑闂翠欢锛岃礋璐ｈ褰曡姹傚拰鍝嶅簲鐨勬祦閲忓ぇ灏?
class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()  # 璁板綍寮€濮嬫椂闂?

        # 1. 蹇€熻繃婊?
        path = request.url.path
        try:
            update_count(path)
        except Exception as e:
            print(f"[ERROR] failed to enqueue usage count: {e}")

        await _log_params_if_needed(request, path)
        if any(k in path for k in IGNORE_API) or not any(k in path for k in RECORD_API):
            return await call_next(request)

        # 2. 鐛插彇 DB Session
        # [!] 璀﹀憡锛氱洿鎺ョ敤 next(get_db()) 鏈冨皫鑷撮€ｆ帴娲╂紡锛佸繀闋堟墜鍕曢棞闁夈€?
        db = next(get_db())
        user = None
        try:
            # 3. [OK] 浣跨敤 await 瑾跨敤鐣版鍑芥暩
            user = await get_current_user_for_middleware(request, db=db)
        except Exception as e:
            print(f"Middleware Auth Error: {e}")
            # 瑾嶈瓑鍑洪尟涓嶆噳褰遍熆璜嬫眰绻肩簩锛岃鐐哄尶鍚嶇敤鎴?
            user = None
        finally:
            # 4. [OK] 蹇呴爤闂滈枆鏁告摎搴€ｆ帴锛侀€欓潪甯搁噸瑕侊紒
            db.close()

        # 5. 璁＄畻璇锋眰澶у皬
        cl = request.headers.get("Content-Length")

        if cl is not None and cl.isdigit():
            request_size = int(cl)
        else:
            # 濡傛灉鏄?GET 璇锋眰锛岃绠?URL 鍜屾煡璇㈠弬鏁扮殑澶у皬
            if request.method == "GET":
                url_size = len(request.url.path) + len(request.url.query)
                request_size = url_size
            else:
                # 鑾峰彇璇锋眰浣撳ぇ灏?
                request_body = await request.body()
                request_size = len(request_body)

        # 6. 璋冪敤涓嬫父搴旂敤锛堣鍥惧嚱鏁帮級
        response = await call_next(request)

        # 7. 纭畾鐢ㄦ埛鐨勫搷搴斿ぇ灏忛檺鍒?
        max_size = MAX_ANONYMOUS_SIZE if user is None else (
            float('inf') if user.role == "admin" else MAX_USER_SIZE
        )

        # 8. 瀹氫箟娴佸紡浼犺緭瀹屾垚鍚庣殑鍥炶皟鍑芥暟
        async def on_streaming_complete(wrapper):
            """Record logs after streaming responses finish."""
            # 璁＄畻澶勭悊鏃堕棿
            duration = time.time() - start_time

            # 鑾峰彇鏈€缁堢殑鍝嶅簲澶у皬
            # 娉ㄦ剰锛氬缁堣褰曞帇缂╁墠鐨勫ぇ灏忥紝浠ヤ繚璇佺粺璁′竴鑷存€?
            # 鍘嬬缉鏄湇鍔″櫒浼樺寲鎵嬫锛屽鐢ㄦ埛搴旇鏄€忔槑鐨?
            response_size = wrapper.total_size  # 鍘嬬缉鍓嶇殑鍘熷澶у皬

            # 寮傛璁板綍鏃ュ織
            await log_detailed_api_to_db_async(
                path=request.url.path,
                duration=duration,
                status_code=response.status_code,
                ip=request.client.host,
                user_agent=request.headers.get("User-Agent"),
                referer=request.headers.get("Referer"),
                user_id=user.id if user else None,
                request_size=request_size,
                response_size=response_size,
                start_time=start_time
            )

        # 9. 浣跨敤娴佸紡鍖呰鍣紙涓嶇紦鍐叉暣涓搷搴旓級
        wrapper = StreamingResponseWrapper(
            iterator=response.body_iterator,
            content_type=response.headers.get("Content-Type", ""),
            user_role=user.role if user else None,
            max_size=max_size,
            response=response,
            on_complete_callback=on_streaming_complete
        )

        # 10. 鏇挎崲鍝嶅簲杩唬鍣?
        response.body_iterator = wrapper

        return response

# 浠ヤ笅浠ｇ爜宸插簾寮?
# === 璇︾粏鍝嶅簲璁板綍鍏ラ槦 ===
# def log_detailed_api(path, duration, status_code, ip, user_agent, referer):
#     today = now_utc_naive().strftime("%Y-%m-%d")
#     detailed_queue.put((path, duration, status_code, ip, user_agent, referer, today))
#
# # === 鍚庡彴绾跨▼鍐欏叆璇︾粏鍝嶅簲 ===
# def detailed_writer():
#     # 鍒濆鍖栨暟鎹粨鏋?
#     def init_stats():
#         return {
#             "count": 0, "total_time": 0.0, "status_codes": defaultdict(int),
#             "ips": set(), "agents": set(), "referers": set()
#         }
#
#     # 浠?JSON 鍔犺浇鏃ф暟鎹?
#     if os.path.exists(API_DETAILED_JSON):
#         with open(API_DETAILED_JSON, "r", encoding="utf-8") as f:
#             raw = json.load(f)
#             detailed_stats = defaultdict(init_stats, {
#                 k: {
#                     "count": v["count"],
#                     "total_time": v["total_time"],
#                     "status_codes": defaultdict(int, v["status_codes"]),
#                     "ips": set(v["ips"]),
#                     "agents": set(v["agents"]),
#                     "referers": set(v["referers"]),
#                 } for k, v in raw["detailed_stats"].items()
#             })
#             daily_stats = defaultdict(lambda: defaultdict(init_stats))
#             for date, paths in raw["daily_stats"].items():
#                 for path, v in paths.items():
#                     daily_stats[date][path] = {
#                         "count": v["count"],
#                         "total_time": v["total_time"],
#                         "status_codes": defaultdict(int, v["status_codes"]),
#                         "ips": set(v["ips"]),
#                         "agents": set(v["agents"]),
#                         "referers": set(v["referers"]),
#                     }
#     else:
#         detailed_stats = defaultdict(init_stats)
#         daily_stats = defaultdict(lambda: defaultdict(init_stats))
#
#     while True:
#         item = detailed_queue.get()
#         if item is None:
#             break
#         path, duration, status, ip, agent, referer, date = item
#
#         d = detailed_stats[path]
#         d["count"] += 1
#         d["total_time"] += duration
#         d["status_codes"][status] += 1
#         d["ips"].add(ip)
#         d["agents"].add(agent)
#         if referer:
#             d["referers"].add(referer)
#
#         d_day = daily_stats[date][path]
#         d_day["count"] += 1
#         d_day["total_time"] += duration
#         d_day["status_codes"][status] += 1
#         d_day["ips"].add(ip)
#         d_day["agents"].add(agent)
#         if referer:
#             d_day["referers"].add(referer)
#
#         # 鍐欏叆缁撴瀯鍖?JSON 鏂囦欢锛堟寔涔呭寲锛?
#         with open(API_DETAILED_JSON, "w", encoding="utf-8") as f:
#             json.dump({
#                 "detailed_stats": {
#                     k: {
#                         "count": v["count"],
#                         "total_time": v["total_time"],
#                         "status_codes": dict(v["status_codes"]),
#                         "ips": list(v["ips"]),
#                         "agents": list(v["agents"]),
#                         "referers": list(v["referers"]),
#                     } for k, v in detailed_stats.items()
#                 },
#                 "daily_stats": {
#                     date: {
#                         path: {
#                             "count": v["count"],
#                             "total_time": v["total_time"],
#                             "status_codes": dict(v["status_codes"]),
#                             "ips": list(v["ips"]),
#                             "agents": list(v["agents"]),
#                             "referers": list(v["referers"]),
#                         } for path, v in paths.items()
#                     } for date, paths in daily_stats.items()
#                 }
#             }, f, ensure_ascii=False, indent=2)
#
#         # 鍐欏叆鍙姹囨€伙紙鍜屽師鏉ヤ竴鏍凤級
#         with open(API_DETAILED_FILE, "w", encoding="utf-8") as f:
#             f.write("=== Total Summary ===\n")
#             for path, d in detailed_stats.items():
#                 avg = d["total_time"] / d["count"] if d["count"] else 0
#                 f.write(f"{path}\n  Count: {d['count']}\n  Avg Response Time: {avg:.3f}s\n")
#                 f.write(f"  Status Codes: {', '.join(f'{k}:{v}' for k, v in d['status_codes'].items())}\n")
#                 f.write("  IPs:\n" + ''.join(f"    - {ip}\n" for ip in sorted(d['ips'])))
#                 f.write("  User-Agents:\n" + ''.join(f"    - {ua}\n" for ua in sorted(d['agents'])))
#                 f.write("  Referers:\n" + ''.join(f"    - {r}\n" for r in sorted(d['referers'])))
#                 f.write("\n")
#             f.write("=== Daily Summary ===\n")
#             for date in sorted(daily_stats):
#                 f.write(f"{date}\n")
#                 for path, d in daily_stats[date].items():
#                     avg = d["total_time"] / d["count"] if d["count"] else 0
#                     f.write(f"{path}\n  Count: {d['count']}\n  Avg Response Time: {avg:.3f}s\n")
#                     f.write(f"  Status Codes: {', '.join(f'{k}:{v}' for k, v in d['status_codes'].items())}\n")
#                     f.write("  IPs:\n" + ''.join(f"    - {ip}\n" for ip in sorted(d['ips'])))
#                     f.write("  User-Agents:\n" + ''.join(f"    - {ua}\n" for ua in sorted(d['agents'])))
#                     f.write("  Referers:\n" + ''.join(f"    - {r}\n" for r in sorted(d['referers'])))
#                 f.write("\n")





