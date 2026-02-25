import sqlite3

db_path = "C:/Users/joengzaang/myfiles/server/fastapi/data/villages.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=== 广东省自然村 表结构 ===")
cursor.execute("PRAGMA table_info(广东省自然村)")
columns = cursor.fetchall()
print(f"总共 {len(columns)} 个字段:\n")
for row in columns:
    print(f"{row[1]:30} {row[2]:15}")

print("\n=== 检查是否有 cluster 相关字段 ===")
cluster_cols = [col[1] for col in columns if 'cluster' in col[1].lower()]
if cluster_cols:
    print(f"找到 cluster 字段: {cluster_cols}")
else:
    print("❌ 没有 cluster_id 字段")
    print("\n这意味着:")
    print("1. 村庄和聚类的关联关系没有存储在主表中")
    print("2. 需要数据分析同事添加 cluster_id 字段")
    print("3. 或者需要一个单独的关联表 (village_cluster_mapping)")

conn.close()
