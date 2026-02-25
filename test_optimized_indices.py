import sqlite3
import time

db_path = "C:/Users/joengzaang/myfiles/server/fastapi/data/villages.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=== Testing Optimized Query ===")

# New optimized query
query = """
SELECT
    region_level,
    region_name,
    category as semantic_category,
    raw_intensity as semantic_index,
    normalized_index,
    rank_within_province as rank_in_region,
    village_count
FROM semantic_indices
WHERE 1=1
AND village_count >= 50
ORDER BY semantic_index DESC LIMIT 100
"""

start = time.time()
cursor.execute(query)
results = cursor.fetchall()
elapsed = time.time() - start

print(f"Query returned {len(results)} rows in {elapsed:.4f}s")
print(f"Performance improvement: {21.337 / elapsed:.1f}x faster")

print("\n=== Sample Results ===")
columns = [desc[0] for desc in cursor.description]
print(columns)
for row in results[:3]:
    print(row)

print("\n=== Query Plan ===")
cursor.execute(f"EXPLAIN QUERY PLAN {query}")
for row in cursor.fetchall():
    print(row)

conn.close()
