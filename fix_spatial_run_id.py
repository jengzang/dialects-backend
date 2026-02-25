import sqlite3

db_path = "C:/Users/joengzaang/myfiles/server/fastapi/data/villages.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 更新 spatial_hotspots 的 run_id 为最新的可用值
new_run_id = "spatial_eps_05"  # 这个有最多的记录 (12,791)

cursor.execute("""
    UPDATE active_run_ids
    SET run_id = ?,
        updated_at = ?,
        updated_by = 'manual_fix',
        notes = '修复404错误：更新为实际存在的run_id'
    WHERE analysis_type = 'spatial_hotspots'
""", (new_run_id, __import__('time').time()))

conn.commit()

print(f"Updated spatial_hotspots run_id to: {new_run_id}")

# 验证更新
cursor.execute("SELECT run_id FROM active_run_ids WHERE analysis_type = 'spatial_hotspots'")
result = cursor.fetchone()
print(f"Current run_id: {result[0]}")

conn.close()
