import sqlite3

db_path = "C:/Users/joengzaang/myfiles/server/fastapi/data/villages.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=== region_spatial_aggregates table schema ===")
cursor.execute("PRAGMA table_info(region_spatial_aggregates)")
columns = cursor.fetchall()
if columns:
    for col in columns:
        print(f"{col[1]:30} {col[2]:15}")

    print("\n=== Sample data ===")
    cursor.execute("SELECT * FROM region_spatial_aggregates LIMIT 3")
    sample = cursor.fetchall()
    col_names = [desc[0] for desc in cursor.description]
    print(f"Columns: {col_names}")
    for row in sample:
        print(row)
else:
    print("Table does not exist or is empty")

conn.close()
