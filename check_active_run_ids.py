import sqlite3

db_path = "C:/Users/joengzaang/myfiles/server/fastapi/data/villages.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=== active_run_ids table ===")
cursor.execute("SELECT * FROM active_run_ids WHERE analysis_type = 'spatial_hotspots'")
columns = [desc[0] for desc in cursor.description]
print(columns)

result = cursor.fetchone()
if result:
    print(result)
    print(f"\nConfigured run_id: {result[1]}")
    print(f"Table name: {result[2]}")
else:
    print("No entry for 'spatial_hotspots'")

print("\n=== All analysis types ===")
cursor.execute("SELECT analysis_type, run_id, table_name FROM active_run_ids")
for row in cursor.fetchall():
    print(f"{row[0]:30} -> {row[1]:30} (table: {row[2]})")

print("\n=== Available run_ids in spatial_clusters ===")
cursor.execute("SELECT DISTINCT run_id FROM spatial_clusters ORDER BY run_id DESC")
for row in cursor.fetchall():
    print(f"  - {row[0]}")

conn.close()
