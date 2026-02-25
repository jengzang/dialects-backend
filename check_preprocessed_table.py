import sqlite3

db_path = "C:/Users/joengzaang/myfiles/server/fastapi/data/villages.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=== 广东省自然村_预处理 table schema ===")
cursor.execute("PRAGMA table_info(广东省自然村_预处理)")
columns = cursor.fetchall()
for col in columns:
    print(f"{col[1]:30} {col[2]:15}")

print("\n=== Sample data ===")
cursor.execute("SELECT * FROM 广东省自然村_预处理 LIMIT 3")
sample = cursor.fetchall()
col_names = [desc[0] for desc in cursor.description]
print(f"Columns ({len(col_names)}): {', '.join(col_names[:10])}...")
for row in sample:
    print(f"Sample: {row[:10]}...")

print("\n=== Check for region centroids ===")
cursor.execute("""
    SELECT DISTINCT 市级, AVG(CAST(longitude AS REAL)) as lon, AVG(CAST(latitude AS REAL)) as lat
    FROM 广东省自然村_预处理
    GROUP BY 市级
    LIMIT 5
""")
print("City centroids:")
for row in cursor.fetchall():
    print(f"  {row[0]}: ({row[1]:.4f}, {row[2]:.4f})")

conn.close()
