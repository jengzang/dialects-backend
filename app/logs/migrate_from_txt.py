# logs/migrate_from_txt.py
"""
从 txt 文件迁移数据到 logs.db
只在首次运行时执行，之后会被标记为已迁移
"""
import os
import ast
import re
from datetime import datetime
from collections import defaultdict
from sqlalchemy import text

from app.logs.database import engine, SessionLocal
from app.logs.models import ApiKeywordLog, ApiStatistics, ApiVisitLog
from common.config import KEYWORD_LOG_FILE, API_USAGE_FILE


def migrate_keyword_log():
    """迁移 api_keywords_log.txt 到数据库"""
    if not os.path.exists(KEYWORD_LOG_FILE):
        print("[!] api_keywords_log.txt 不存在，跳过迁移")
        return 0

    print("📖 正在读取 api_keywords_log.txt...")
    db = SessionLocal()
    count = 0
    batch = []
    batch_size = 1000

    try:
        with open(KEYWORD_LOG_FILE, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                try:
                    # 格式: "2025-01-21 10:30:00 | /api/search | field: 'value'"
                    parts = line.strip().split(" | ", 2)
                    if len(parts) != 3:
                        continue

                    timestamp_str, path, rest = parts
                    field_part, value_part = rest.split(": ", 1)
                    field = field_part.strip()
                    value = ast.literal_eval(value_part.strip())

                    # 解析时间
                    timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")

                    # 创建记录
                    log = ApiKeywordLog(
                        timestamp=timestamp,
                        path=path,
                        field=field,
                        value=str(value)
                    )
                    batch.append(log)
                    count += 1

                    # 批量插入
                    if len(batch) >= batch_size:
                        try:
                            db.bulk_save_objects(batch)
                            db.commit()
                            print(f"  已导入 {count} 条记录...")
                            batch = []
                        except Exception as e:
                            print(f"  [!] 批量插入失败: {e}")
                            db.rollback()
                            batch = []
                            # 如果是权限问题，提前中断
                            if 'readonly' in str(e).lower():
                                raise

                except Exception as e:
                    print(f"  [!] 第 {line_num} 行解析失败: {e}")
                    # 如果是数据库错误，需要 rollback session
                    if 'rolled back' in str(e).lower() or 'readonly' in str(e).lower():
                        db.rollback()
                        batch = []  # 清空当前批次
                    continue

        # 插入剩余记录
        if batch:
            try:
                db.bulk_save_objects(batch)
                db.commit()
            except Exception as e:
                print(f"  [!] 批量插入失败: {e}")
                db.rollback()

        print(f"[OK] api_keywords_log.txt 迁移完成，共 {count} 条记录")
        return count

    except Exception as e:
        print(f"[X] 迁移 api_keywords_log.txt 失败: {e}")
        db.rollback()
        return 0
    finally:
        db.close()


def migrate_api_usage_stats():
    """迁移 api_usage_stats.txt 到 ApiVisitLog 表（HTML 页面访问统计）"""
    if not os.path.exists(API_USAGE_FILE):
        print("[!] api_usage_stats.txt 不存在，跳过迁移")
        return 0

    print("📖 正在读取 api_usage_stats.txt...")
    db = SessionLocal()
    count = 0

    try:
        with open(API_USAGE_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()

        section = None
        current_day = None
        batch = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if line == "=== Total Counts ===":
                section = "total"
                continue
            elif line == "=== Daily Counts ===":
                section = "daily"
                continue
            elif section == "daily" and re.match(r"\d{4}-\d{2}-\d{2}", line):
                current_day = datetime.strptime(line, "%Y-%m-%d")
                continue

            # 解析数据行
            if "\t" in line:
                path, count_str = line.split("\t", 1)
                count_val = int(count_str)

                if section == "total":
                    # 总计统计 - 存入 ApiVisitLog（date=NULL）
                    visit = ApiVisitLog(
                        path=path,
                        date=None,
                        count=count_val
                    )
                    batch.append(visit)
                    count += 1

                elif section == "daily" and current_day:
                    # 每日统计 - 存入 ApiVisitLog（date=具体日期）
                    visit = ApiVisitLog(
                        path=path,
                        date=current_day,
                        count=count_val
                    )
                    batch.append(visit)
                    count += 1

        # 批量插入
        if batch:
            try:
                db.bulk_save_objects(batch)
                db.commit()
            except Exception as e:
                print(f"  [!] 批量插入失败: {e}")
                db.rollback()

        print(f"[OK] api_usage_stats.txt 迁移完成，共 {count} 条记录")
        return count

    except Exception as e:
        print(f"[X] 迁移 api_usage_stats.txt 失败: {e}")
        db.rollback()
        return 0
    finally:
        db.close()


def aggregate_keyword_statistics():
    """从 api_keyword_log 聚合生成关键词统计"""
    print("[DB] 正在聚合关键词统计...")
    db = SessionLocal()

    try:
        # 聚合总计
        result = db.execute(text("""
            INSERT OR REPLACE INTO api_statistics (stat_type, date, category, item, count, updated_at)
            SELECT
                'keyword_total' as stat_type,
                NULL as date,
                field as category,
                value as item,
                COUNT(*) as count,
                datetime('now') as updated_at
            FROM api_keyword_log
            GROUP BY field, value
        """))
        total_count = result.rowcount
        db.commit()

        # 聚合每日统计
        result = db.execute(text("""
            INSERT OR REPLACE INTO api_statistics (stat_type, date, category, item, count, updated_at)
            SELECT
                'keyword_daily' as stat_type,
                DATE(timestamp) as date,
                field as category,
                value as item,
                COUNT(*) as count,
                datetime('now') as updated_at
            FROM api_keyword_log
            GROUP BY DATE(timestamp), field, value
        """))
        daily_count = result.rowcount
        db.commit()

        print(f"[OK] 关键词统计聚合完成: 总计 {total_count} 条, 每日 {daily_count} 条")
        return total_count + daily_count

    except Exception as e:
        print(f"[X] 聚合关键词统计失败: {e}")
        db.rollback()
        return 0
    finally:
        db.close()


def check_migration_status():
    """检查是否已经迁移过"""
    db = SessionLocal()
    try:
        # 检查是否有数据
        keyword_count = db.query(ApiKeywordLog).count()
        stats_count = db.query(ApiStatistics).count()

        # 尝试查询 ApiVisitLog，如果表结构不对就跳过
        try:
            visit_count = db.query(ApiVisitLog).count()
        except Exception as e:
            print(f"[!] 无法查询 ApiVisitLog（可能表结构不匹配）: {e}")
            visit_count = 0

        return keyword_count > 0 or stats_count > 0
    except Exception as e:
        print(f"[!] 检查迁移状态失败: {e}")
        return False
    finally:
        db.close()


def run_migration(force=False):
    """
    执行完整迁移

    Args:
        force: 是否强制重新迁移（会清空现有数据）
    """
    # 检查是否已迁移
    if not force and check_migration_status():
        print("[OK] 数据已迁移，跳过")
        return True

    if force:
        print("[!] 强制重新迁移，清空现有数据...")
        db = SessionLocal()
        try:
            db.query(ApiKeywordLog).delete()
            db.query(ApiStatistics).delete()

            # 尝试删除 ApiVisitLog，如果表结构不对就跳过
            try:
                db.query(ApiVisitLog).delete()
            except Exception as e:
                print(f"[!] 无法删除 ApiVisitLog 数据（可能表结构不匹配）: {e}")

            db.commit()
        except Exception as e:
            print(f"[!] 清空数据失败: {e}")
            db.rollback()
        finally:
            db.close()

    print("=" * 60)
    print("[RUN] 开始从 txt 文件迁移数据到 logs.db")
    print("=" * 60)

    # 执行迁移
    keyword_count = migrate_keyword_log()
    usage_count = migrate_api_usage_stats()
    agg_count = aggregate_keyword_statistics()

    print("=" * 60)
    print(f"[OK] 迁移完成！")
    print(f"   - 关键词日志: {keyword_count} 条")
    print(f"   - HTML页面访问统计: {usage_count} 条")
    print(f"   - 聚合统计: {agg_count} 条")
    print("=" * 60)

    return True


if __name__ == "__main__":
    # 可以直接运行此脚本进行迁移
    import sys
    force = "--force" in sys.argv
    run_migration(force=force)
