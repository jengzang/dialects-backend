"""
Comprehensive database audit for VillagesML
"""
import sqlite3
import os

db_path = "data/villages.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=" * 60)
print("VillagesML 數據庫全面審查")
print("=" * 60)

# 1. Database size
db_size = os.path.getsize(db_path) / (1024 * 1024 * 1024)
print(f"\n[1] 數據庫大小: {db_size:.2f} GB")

# 2. Table sizes
print("\n[2] 各表大小估算:")
cursor.execute("""
    SELECT name FROM sqlite_master
    WHERE type='table' AND name NOT LIKE 'sqlite_%'
    ORDER BY name
""")
tables = [row[0] for row in cursor.fetchall()]

table_sizes = []
for table in tables:
    try:
        cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
        count = cursor.fetchone()[0]
        # Rough estimate: 100 bytes per row
        size_mb = (count * 100) / (1024 * 1024)
        table_sizes.append((table, count, size_mb))
    except:
        pass

# Sort by size
table_sizes.sort(key=lambda x: x[2], reverse=True)
print("\n前10大表:")
for table, count, size in table_sizes[:10]:
    print(f"  {table}: {count:,} 行, ~{size:.1f} MB")

# 3. Check for duplicate data between main and preprocessed tables
print("\n[3] 主表 vs 預處理表:")
cursor.execute('SELECT COUNT(*) FROM "广东省自然村"')
main_count = cursor.fetchone()[0]
cursor.execute('SELECT COUNT(*) FROM "广东省自然村_预处理"')
prep_count = cursor.fetchone()[0]
print(f"  主表: {main_count:,} 行")
print(f"  預處理表: {prep_count:,} 行")
if main_count == prep_count:
    print("  [WARNING] 兩表記錄數相同，可能存在數據冗餘")

# 4. Check column name inconsistencies
print("\n[4] 列名一致性檢查:")
cursor.execute('PRAGMA table_info("广东省自然村")')
main_cols = {row[1] for row in cursor.fetchall()}
cursor.execute('PRAGMA table_info("广东省自然村_预处理")')
prep_cols = {row[1] for row in cursor.fetchall()}

common_concepts = ['市级', '区县级', '乡镇级', '自然村']
for concept in common_concepts:
    in_main = concept in main_cols
    in_prep = concept in prep_cols
    if in_main != in_prep:
        print(f"  [WARNING] '{concept}' 在主表: {in_main}, 在預處理表: {in_prep}")

# Check for village_committee naming
village_committee_main = [col for col in main_cols if '村' in col and '委' in col]
village_committee_prep = [col for col in prep_cols if '村' in col and '委' in col]
print(f"  主表村委會列: {village_committee_main}")
print(f"  預處理表村委會列: {village_committee_prep}")
if village_committee_main != village_committee_prep:
    print("  [WARNING] 村委會列名不一致！")

# 5. Check for indexes
print("\n[5] 索引檢查:")
cursor.execute("""
    SELECT name, tbl_name, sql FROM sqlite_master
    WHERE type='index' AND sql IS NOT NULL
    ORDER BY tbl_name
""")
indexes = cursor.fetchall()
print(f"  總索引數: {len(indexes)}")

# Check if analysis tables have indexes on village_id
analysis_tables = ['village_spatial_features', 'village_ngrams', 'village_semantic_structure', 'village_features']
for table in analysis_tables:
    table_indexes = [idx for idx in indexes if idx[1] == table]
    if not table_indexes:
        print(f"  [WARNING] {table} 沒有索引！")
    else:
        print(f"  {table}: {len(table_indexes)} 個索引")

# 6. Check data types
print("\n[6] 數據類型檢查:")
cursor.execute('PRAGMA table_info("广东省自然村_预处理")')
for col in cursor.fetchall():
    col_name, col_type = col[1], col[2]
    if col_name in ['longitude', 'latitude'] and col_type == 'TEXT':
        print(f"  [WARNING] {col_name} 使用 TEXT 類型，應該用 REAL")

# 7. Check for foreign keys
print("\n[7] 外鍵約束:")
cursor.execute("PRAGMA foreign_keys")
fk_enabled = cursor.fetchone()[0]
print(f"  外鍵啟用: {bool(fk_enabled)}")

for table in analysis_tables:
    cursor.execute(f'PRAGMA foreign_key_list("{table}")')
    fks = cursor.fetchall()
    if not fks:
        print(f"  [WARNING] {table} 沒有外鍵約束")

# 8. Check for village_id format consistency
print("\n[8] village_id 格式一致性:")
cursor.execute("SELECT DISTINCT village_id FROM village_spatial_features LIMIT 5")
spatial_ids = [row[0] for row in cursor.fetchall()]
print(f"  spatial_features 格式: {spatial_ids}")

# Check if other tables have village_id
for table in ['village_ngrams', 'village_semantic_structure']:
    cursor.execute(f'PRAGMA table_info("{table}")')
    cols = [row[1] for row in cursor.fetchall()]
    has_village_id = 'village_id' in cols
    print(f"  {table} 有 village_id: {has_village_id}")
    if not has_village_id:
        print(f"    [ISSUE] 應該添加 village_id 列！")

# 9. Check for run_id consistency
print("\n[9] run_id 使用情況:")
for table in analysis_tables:
    cursor.execute(f'PRAGMA table_info("{table}")')
    cols = [row[1] for row in cursor.fetchall()]
    has_run_id = 'run_id' in cols
    if has_run_id:
        cursor.execute(f'SELECT DISTINCT run_id FROM "{table}"')
        run_ids = [row[0] for row in cursor.fetchall()]
        print(f"  {table}: {len(run_ids)} 個 run_id")
    else:
        print(f"  {table}: 無 run_id 列")

# 10. Check for unused tables
print("\n[10] 可能未使用的表:")
all_tables = set(tables)
documented_tables = {
    '广东省自然村', '广东省自然村_预处理',
    'village_spatial_features', 'village_ngrams', 'village_semantic_structure', 'village_features',
    'active_run_ids', 'analysis_runs', 'embedding_runs',
    'char_embeddings', 'char_frequency_global', 'semantic_vtf_global',
    'spatial_hotspots', 'spatial_clusters'
}
potentially_unused = all_tables - documented_tables
if potentially_unused:
    print(f"  發現 {len(potentially_unused)} 個可能未使用的表:")
    for table in sorted(potentially_unused)[:10]:
        cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
        count = cursor.fetchone()[0]
        print(f"    {table}: {count:,} 行")

conn.close()

print("\n" + "=" * 60)
print("審查完成")
print("=" * 60)
