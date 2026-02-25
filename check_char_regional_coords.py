import sqlite3

db_path = "C:/Users/joengzaang/myfiles/server/fastapi/data/villages.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=== char_regional_analysis table schema ===")
cursor.execute("PRAGMA table_info(char_regional_analysis)")
columns = cursor.fetchall()
for col in columns:
    print(f"{col[1]:30} {col[2]:15}")

print("\n=== Check if coordinates exist ===")
has_coords = any('lon' in col[1].lower() or 'lat' in col[1].lower() for col in columns)
print(f"Has coordinates: {has_coords}")

if not has_coords:
    print("\n=== Need to find coordinate source ===")
    print("Checking for region coordinate tables...")

    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table'
        AND (name LIKE '%region%' OR name LIKE '%coordinate%' OR name LIKE '%location%')
    """)
    tables = cursor.fetchall()
    print("Potential tables:")
    for table in tables:
        print(f"  - {table[0]}")

print("\n=== Sample data ===")
cursor.execute("SELECT * FROM char_regional_analysis LIMIT 3")
sample = cursor.fetchall()
col_names = [desc[0] for desc in cursor.description]
print(f"Columns: {col_names}")
for row in sample:
    print(row)

conn.close()
