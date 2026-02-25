import sqlite3
import time

db_path = "C:/Users/joengzaang/myfiles/server/fastapi/data/villages.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=== Indexes on semantic_indices ===")
cursor.execute("SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='semantic_indices'")
for row in cursor.fetchall():
    if row[0]:
        print(row[0])

print("\n=== Indexes on 广东省自然村 ===")
cursor.execute("SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='广东省自然村'")
for row in cursor.fetchall():
    if row[0]:
        print(row[0])

print("\n=== Table row counts ===")
cursor.execute("SELECT COUNT(*) FROM semantic_indices")
print(f"semantic_indices: {cursor.fetchone()[0]:,} rows")

cursor.execute("SELECT COUNT(*) FROM 广东省自然村")
print(f"广东省自然村: {cursor.fetchone()[0]:,} rows")

print("\n=== Query Plan Analysis ===")
query = """
EXPLAIN QUERY PLAN
SELECT
    si.region_level,
    si.region_name,
    si.category as semantic_category,
    si.raw_intensity as semantic_index,
    si.normalized_index,
    si.rank_within_province as rank_in_region,
    COUNT(DISTINCT v.自然村) as village_count
FROM semantic_indices si
LEFT JOIN 广东省自然村 v ON (
    (si.region_level = 'city' AND si.region_name = v.市级) OR
    (si.region_level = 'county' AND si.region_name = v.区县级) OR
    (si.region_level = 'township' AND si.region_name = v.乡镇级)
)
WHERE 1=1
GROUP BY si.region_level, si.region_name, si.category,
         si.raw_intensity, si.normalized_index, si.rank_within_province
HAVING village_count >= 50
ORDER BY semantic_index DESC LIMIT 100
"""

cursor.execute(query)
for row in cursor.fetchall():
    print(row)

print("\n=== Actual Query Timing ===")
query_actual = """
SELECT
    si.region_level,
    si.region_name,
    si.category as semantic_category,
    si.raw_intensity as semantic_index,
    si.normalized_index,
    si.rank_within_province as rank_in_region,
    COUNT(DISTINCT v.自然村) as village_count
FROM semantic_indices si
LEFT JOIN 广东省自然村 v ON (
    (si.region_level = 'city' AND si.region_name = v.市级) OR
    (si.region_level = 'county' AND si.region_name = v.区县级) OR
    (si.region_level = 'township' AND si.region_name = v.乡镇级)
)
WHERE 1=1
GROUP BY si.region_level, si.region_name, si.category,
         si.raw_intensity, si.normalized_index, si.rank_within_province
HAVING village_count >= 50
ORDER BY semantic_index DESC LIMIT 100
"""

start = time.time()
cursor.execute(query_actual)
results = cursor.fetchall()
elapsed = time.time() - start

print(f"Query returned {len(results)} rows in {elapsed:.3f}s")

conn.close()
