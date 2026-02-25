import sqlite3

db_path = "C:/Users/joengzaang/myfiles/server/fastapi/data/villages.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=== 测试查询 ===")

# 测试1: 查询 "村" 在 city 级别
print("\n1. 查询 '村' 在 city 级别:")
cursor.execute("""
    SELECT
        level,
        region,
        city,
        ngram,
        lift,
        regional_count
    FROM ngram_tendency
    WHERE level = 'city' AND ngram = '村'
    ORDER BY lift DESC
    LIMIT 5
""")
results = cursor.fetchall()
print(f"找到 {len(results)} 条记录")
for row in results:
    print(f"  {row}")

# 测试2: 检查 level 的可用值
print("\n2. 检查 level 字段的可用值:")
cursor.execute("SELECT DISTINCT level FROM ngram_tendency")
levels = cursor.fetchall()
print(f"可用的 level 值: {[l[0] for l in levels]}")

# 测试3: 检查是否有 "村" 这个 ngram
print("\n3. 检查是否有 '村' 这个 ngram:")
cursor.execute("SELECT COUNT(*) FROM ngram_tendency WHERE ngram = '村'")
count = cursor.fetchone()[0]
print(f"包含 '村' 的记录数: {count:,}")

# 测试4: 查看一些示例 ngrams
print("\n4. 查看一些高频 ngrams:")
cursor.execute("""
    SELECT DISTINCT ngram, COUNT(*) as cnt
    FROM ngram_tendency
    GROUP BY ngram
    ORDER BY cnt DESC
    LIMIT 10
""")
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]:,} 条记录")

# 测试5: 检查 position 字段
print("\n5. 检查 position 字段的值:")
cursor.execute("SELECT DISTINCT position FROM ngram_tendency")
positions = cursor.fetchall()
print(f"可用的 position 值: {[p[0] for p in positions]}")

# 测试6: 模拟 API 查询
print("\n6. 模拟 API 查询 (ngram=村, region_level=city):")
cursor.execute("""
    SELECT
        level as region_level,
        region as region_name,
        city,
        county,
        township,
        ngram,
        n,
        position,
        lift as tendency_score,
        regional_count as frequency
    FROM ngram_tendency
    WHERE level = ?
    AND ngram = ?
    ORDER BY lift DESC
    LIMIT 5
""", ('city', '村'))
results = cursor.fetchall()
print(f"找到 {len(results)} 条记录")
if results:
    columns = ['region_level', 'region_name', 'city', 'county', 'township', 'ngram', 'n', 'position', 'tendency_score', 'frequency']
    print(f"Columns: {columns}")
    for row in results:
        print(f"  {row}")

conn.close()
