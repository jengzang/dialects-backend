import sqlite3

db_path = "C:/Users/joengzaang/myfiles/server/fastapi/data/villages.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=== semantic_indices table schema ===")
cursor.execute("PRAGMA table_info(semantic_indices)")
for row in cursor.fetchall():
    print(f"{row[1]:25} {row[2]:15} {'NOT NULL' if row[3] else 'NULL':10} {f'DEFAULT {row[4]}' if row[4] else ''}")

print("\n=== Sample data ===")
cursor.execute("SELECT * FROM semantic_indices LIMIT 3")
columns = [desc[0] for desc in cursor.description]
print(columns)
for row in cursor.fetchall():
    print(row)

conn.close()
