import sqlite3

db_path = "C:/Users/joengzaang/myfiles/server/fastapi/data/villages.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=== 查找包含坐标的预处理表 ===\n")

# 查找所有表
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall()]

# 检查每个表是否有坐标字段
tables_with_coords = []
for table in tables:
    try:
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [col[1] for col in cursor.fetchall()]
        has_lon = any('lon' in col.lower() for col in columns)
        has_lat = any('lat' in col.lower() for col in columns)
        has_region = any('region' in col.lower() for col in columns)

        if has_lon and has_lat and has_region:
            tables_with_coords.append(table)
            print(f"✓ {table}")
            print(f"  Columns: {', '.join(columns)}")
            print()
    except:
        pass

if not tables_with_coords:
    print("没有找到同时包含坐标和区域信息的表")

conn.close()
