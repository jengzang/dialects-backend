import sqlite3

db_path = "C:/Users/joengzaang/myfiles/server/fastapi/data/villages.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=== ngram_tendency table schema ===")
cursor.execute("PRAGMA table_info(ngram_tendency)")
columns = cursor.fetchall()

if columns:
    print("\nColumns:")
    for col in columns:
        print(f"  {col[1]:25} {col[2]:15} {'NOT NULL' if col[3] else 'NULL':10}")

    print("\n=== Sample data ===")
    cursor.execute("SELECT * FROM ngram_tendency LIMIT 3")
    sample = cursor.fetchall()
    col_names = [desc[0] for desc in cursor.description]
    print(f"Columns: {col_names}")
    for row in sample:
        print(row)

    print(f"\n=== Total records ===")
    cursor.execute("SELECT COUNT(*) FROM ngram_tendency")
    print(f"Total: {cursor.fetchone()[0]:,}")
else:
    print("Table does not exist!")

conn.close()
