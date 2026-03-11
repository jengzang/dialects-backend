# VillagesML 數據庫問題報告與建議

**生成時間**: 2026-02-23
**數據庫大小**: 5.32 GB
**主表記錄數**: 285,860 行
**預處理表記錄數**: 285,860 行

---

## 【嚴重問題】需要立即修復

### 問題 1: village_ngrams 和 village_semantic_structure 缺少 village_id 列

**影響**:
- 無法直接通過 ROWID 查詢，必須用 (村名, 村委會) 組合
- 村委會字段不一致導致匹配失敗
- 查詢效率低，需要字符串匹配

**建議**:
```sql
ALTER TABLE village_ngrams ADD COLUMN village_id TEXT;
ALTER TABLE village_semantic_structure ADD COLUMN village_id TEXT;

-- 填充數據（基於預處理表的 ROWID）
UPDATE village_ngrams
SET village_id = 'v_' || (
    SELECT ROWID FROM "广东省自然村_预处理"
    WHERE "自然村" = village_ngrams."自然村"
    LIMIT 1
);

UPDATE village_semantic_structure
SET village_id = 'v_' || (
    SELECT ROWID FROM "广东省自然村_预处理"
    WHERE "自然村" = village_semantic_structure."自然村"
    LIMIT 1
);
```

**優先級**: 最高 (5/5)

---

### 問題 2: village_ngrams 和 village_semantic_structure 沒有索引

**影響**:
- 查詢性能差，每次都需要全表掃描
- 對於 285K 行數據，查詢可能需要數百毫秒

**建議**:
```sql
-- 添加 village_id 後
CREATE INDEX idx_ngrams_village_id ON village_ngrams(village_id);
CREATE INDEX idx_semantic_village_id ON village_semantic_structure(village_id);

-- 如果保留村名查詢
CREATE INDEX idx_ngrams_village_name ON village_ngrams("自然村");
CREATE INDEX idx_semantic_village_name ON village_semantic_structure("自然村");
```

**優先級**: 最高 (5/5)
**預期提升**: 查詢性能提升 10-100 倍

---

### 問題 3: 預處理表的 longitude/latitude 使用 TEXT 類型

**影響**:
- 無法進行數值計算（距離、範圍查詢等）
- 浪費存儲空間
- 可能導致排序錯誤

**當前狀態**:
```
longitude: TEXT
latitude: TEXT
```

**建議**:
```sql
-- 方案 A: 添加新列（推薦，不破壞現有數據）
ALTER TABLE "广东省自然村_预处理" ADD COLUMN longitude_real REAL;
ALTER TABLE "广东省自然村_预处理" ADD COLUMN latitude_real REAL;

UPDATE "广东省自然村_预处理"
SET longitude_real = CAST(longitude AS REAL),
    latitude_real = CAST(latitude AS REAL);

-- 方案 B: 重建表（需要停機維護）
-- 創建新表 -> 遷移數據 -> 刪除舊表 -> 重命名
```

**優先級**: 高 (4/5)

---

### 問題 4: 沒有外鍵約束

**影響**:
- 無法保證數據完整性
- 可能產生孤立記錄
- 刪除預處理表數據時不會級聯刪除分析數據

**建議**:
```sql
-- 啟用外鍵
PRAGMA foreign_keys = ON;

-- 注意：SQLite 不支持 ALTER TABLE ADD FOREIGN KEY
-- 需要重建表並添加外鍵約束
```

**優先級**: 中 (3/5)
**備註**: 如果分析表是不可變快照，可能不需要外鍵

---

### 問題 5: 主表和預處理表數據冗餘

**影響**:
- 兩表都有 285,860 行，可能重複存儲
- 數據庫大小 5.32 GB，可能有優化空間

**建議**:

**選項 A**: 如果主表只是數據源
- 定期歸檔主表到外部存儲
- 只保留預處理表在生產數據庫中

**選項 B**: 如果兩表都需要
- 確認是否真的需要保留主表的所有列
- 考慮壓縮或分區

**優先級**: 低-中 (2/5)
**備註**: 需要確認業務需求

---

### 問題 6: village_ngrams 和 village_semantic_structure 缺少 run_id

**影響**:
- 無法支持版本管理
- 無法保留歷史分析結果
- 與其他分析表（spatial_features, village_features）不一致

**建議**:
```sql
ALTER TABLE village_ngrams ADD COLUMN run_id TEXT;
ALTER TABLE village_semantic_structure ADD COLUMN run_id TEXT;

-- 為現有數據設置默認 run_id
UPDATE village_ngrams SET run_id = 'ngram_001';
UPDATE village_semantic_structure SET run_id = 'semantic_001';

-- 添加到 active_run_ids 表
INSERT INTO active_run_ids (analysis_type, run_id, table_name)
VALUES
    ('ngrams', 'ngram_001', 'village_ngrams'),
    ('semantic', 'semantic_001', 'village_semantic_structure');
```

**優先級**: 中 (3/5)

---

### 問題 7: 列名不一致

**影響**:
- 主表: "村委会"
- 預處理表: "村居委"
- 導致查詢混亂，需要特殊處理

**建議**:
統一列名為 "村委会"（更常見的術語）

```sql
-- 重命名列（需要重建表）
-- 或者在查詢時使用 AS 別名
```

**優先級**: 中 (3/5)

---

## 【其他發現】

### 發現 1: 大量分析表可能未被 API 使用

以下表佔用大量空間但可能未被 API 使用：
- `pattern_frequency_regional`: 3.8M 行, ~366 MB
- `pattern_tendency`: 3.8M 行, ~366 MB
- `ngram_significance`: 3.1M 行, ~297 MB
- `ngram_tendency`: 3.1M 行, ~297 MB
- `regional_ngram_frequency`: 3.1M 行, ~297 MB

**建議**:
- 確認這些表是否被使用
- 如果只用於離線分析，考慮移到單獨的數據庫
- 如果不再需要，可以刪除以減小數據庫大小（可節省 ~1.5 GB）

---

## 【修復優先級總結】

### 第一優先級（立即修復）:
1. ✅ 添加 village_id 到 ngrams 和 semantic_structure 表
2. ✅ 為這兩個表添加索引

### 第二優先級（近期修復）:
3. 修復 longitude/latitude 數據類型
4. 統一列名（村委会 vs 村居委）
5. 添加 run_id 支持版本管理

### 第三優先級（長期優化）:
6. 評估是否需要外鍵約束
7. 清理未使用的表
8. 優化數據庫大小

---

## 【預期收益】

修復後的改進:
- ✓ 查詢性能提升 10-100 倍（添加索引）
- ✓ 數據一致性提高（統一 ID 系統）
- ✓ 支持版本管理（run_id）
- ✓ 減少數據庫大小 20-30%（清理未使用表）
- ✓ 更好的數據完整性（外鍵約束）

---

## 【實施建議】

1. **第一階段**（本週）: 添加 village_id 和索引
2. **第二階段**（下週）: 修復數據類型和列名
3. **第三階段**（下月）: 清理和優化

**注意事項**:
- 建議在測試環境先執行
- 大表修改可能需要數分鐘到數小時
- 建議在低峰期執行
- 執行前務必備份數據庫
