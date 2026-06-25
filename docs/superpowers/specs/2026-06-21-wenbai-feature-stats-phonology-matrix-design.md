# 文白讀接入 `feature_stats` 與 `phonology_matrix` 設計

## 目標

在不破壞現有前端讀取邏輯的前提下，為以下兩個 API 補充文白讀相關的可選資訊：

- `POST /api/feature_stats`
- `GET/POST /api/phonology_matrix`

本次採用「兼容優先」策略：

- 不修改既有字段語義
- 不刪除既有字段
- 新增字段均為可選附加信息
- 舊前端可完全忽略新增字段

## 現狀

### 文白讀來源

`dialects` 表中的 `多音字` 列已承載文白讀標記：

- `1`: 普通多音字
- `2`: 文讀
- `3`: 白讀

代碼中既有常量定義如下：

- `POLYPHONIC_MARKS = {"1", "2", "3"}`
- `WENDU_MARKS = {"2"}`
- `BAIDU_MARKS = {"3"}`

現有 `/api/phonology`、`/api/search_chars` 已能消費這套約定。

### 兩個目標 API 的問題

#### `feature_stats`

現有返回只包含：

- `count`
- `ratio`
- `char_indices`

缺少：

- 這一個音值桶裡有多少文讀字、白讀字、文白兼有字
- 具體是哪一些字

#### `phonology_matrix`

現有 `matrix` 末級節點為單純字列表：

```json
{
  "matrix": {
    "聲母": {
      "韻母": {
        "聲調": ["字1", "字2"]
      }
    }
  }
}
```

缺少：

- 該格中有哪些字涉及多音/文讀/白讀
- 該格裡文白讀的統計

## 設計決策

### 決策 1：兼容優先

不改動現有字段語義與主要結構：

- `feature_stats` 仍以 `count/ratio/char_indices` 為主
- `phonology_matrix` 仍保留原有 `matrix`

### 決策 2：`feature_stats` 直接內嵌附加字段

對 `feature_stats`，在每個音值節點新增 `read_stats` 字段。

原因：

- 該接口本來就是按音值桶輸出
- 其現有結構已包含 `char_indices`
- 直接內嵌最自然，也最方便前端讀取

### 決策 3：`phonology_matrix` 不改 `matrix`，旁掛 `matrix_read_stats`

不把 `matrix[聲母][韻母][聲調]` 從 `List[str]` 改成 object，而是新增並列字段 `matrix_read_stats`。

原因：

- 最大限度避免舊前端爆炸
- 現有前端如果把末級節點寫死成陣列，仍可正常工作
- 新前端如果需要文白讀能力，讀 `matrix_read_stats` 即可

### 決策 4：統計口徑按「字去重」

所有文白讀統計均按「漢字去重」計算，不按資料行數或音節數計算。

原因：

- 與 `feature_stats.count`、`phonology_matrix` 的展示語義一致
- 避免同一字多筆記錄導致統計膨脹

### 決策 5：`wenbai` 為衍生類別

當同一字在同一統計桶內同時命中 `2` 和 `3` 時，將其歸入 `wenbai`。

注意：

- `wenbai` 不是獨立原始標記
- 它是根據同桶內聚合結果推導出的衍生分類

## 返回設計

### `feature_stats`

保持原有結構，對每個 feature value 新增：

```json
{
  "count": 150,
  "ratio": 0.05,
  "char_indices": [0, 1, 2],
  "read_stats": {
    "polyphonic": {
      "count": 12,
      "char_indices": [1, 8]
    },
    "wendu": {
      "count": 5,
      "char_indices": [1, 9]
    },
    "baidu": {
      "count": 4,
      "char_indices": [8]
    },
    "wenbai": {
      "count": 2,
      "char_indices": [1]
    }
  }
}
```

字段語義：

- `polyphonic`: 同桶內命中 `1/2/3` 任一標記的字
- `wendu`: 同桶內命中 `2` 的字
- `baidu`: 同桶內命中 `3` 的字
- `wenbai`: 同桶內同時命中 `2` 和 `3` 的字

兼容性：

- 舊前端忽略 `read_stats` 即可
- 原 `count/ratio/char_indices` 不變

### `phonology_matrix`

保留原有：

```json
{
  "matrix": {
    "聲母": {
      "韻母": {
        "聲調": ["字1", "字2"]
      }
    }
  }
}
```

新增並列字段：

```json
{
  "matrix_read_stats": {
    "聲母": {
      "韻母": {
        "聲調": {
          "polyphonic": {
            "count": 1,
            "chars": ["字1"]
          },
          "wendu": {
            "count": 1,
            "chars": ["字1"]
          },
          "baidu": {
            "count": 0,
            "chars": []
          },
          "wenbai": {
            "count": 0,
            "chars": []
          }
        }
      }
    }
  }
}
```

字段語義與 `feature_stats.read_stats` 完全一致，只是使用 `chars` 而不是 `char_indices`。

原因：

- `phonology_matrix` 本身是格子展示接口
- 直接返回字列表對前端最實用

## 實現方案

### 一、`feature_stats`

修改文件：

- `app/service/core/feature_stats.py`
- 如需補充類型或文檔，再更新對應 schema / README

核心改動：

1. 在現有 `all_rows` 掃描階段，同步維護一套讀法聚合結構
2. 聚合鍵仍然是 `(location, feature_type, value)`
3. 每個鍵下維護四套字集合：
   - `polyphonic`
   - `wendu`
   - `baidu`
   - `wenbai`

建議資料結構：

```python
read_grouped = defaultdict(
    lambda: defaultdict(
        lambda: defaultdict(
            lambda: {
                "polyphonic": set(),
                "wendu": set(),
                "baidu": set(),
                "wenbai": set(),
                "_marks_by_char": defaultdict(set),
            }
        )
    )
)
```

其中：

- `_marks_by_char` 僅作中間態
- 最後輸出前轉成 `wenbai`
- 輸出時去掉 `_marks_by_char`

處理邏輯：

1. 先依 `多音字` 判斷是否命中 `polyphonic/wendu/baidu`
2. 用 `_marks_by_char[char].add(mark)` 收集同字所有標記
3. 完成聚合後，若某字同時含 `2` 與 `3`，則加入 `wenbai`
4. 轉成 `char_indices`

### 二、`phonology_matrix`

修改文件：

- `app/service/core/matrix.py`
- 可能補充 `README.md` 示例

核心改動：

1. 保留既有 `matrix` 構建流程
2. 擴展 SQL，把 `多音字` 一併查出
3. 新增 `matrix_read_stats` 聚合樹

建議查詢：

現有查詢：

```sql
SELECT 簡稱, 聲母, 韻母, 聲調, GROUP_CONCAT(漢字, '') as 漢字列表
```

本次不直接在現有 GROUP_CONCAT 查詢上做文白讀推導，原因是會丟失單字粒度的標記信息。

更穩妥方案：

- 保留原查詢用於 `matrix`
- 追加一個細粒度查詢用於 `matrix_read_stats`

新增細粒度查詢返回：

```sql
SELECT 簡稱, 聲母, 韻母, 聲調, 漢字, 多音字
FROM dialects
WHERE 簡稱 IN (...)
  AND 聲母 IS NOT NULL
  AND 韻母 IS NOT NULL
  AND 聲調 IS NOT NULL
  AND 漢字 IS NOT NULL
```

然後按 `(聲母, 韻母, 聲調)` 聚合。

建議資料結構：

```python
matrix_read_stats = defaultdict(
    lambda: defaultdict(
        lambda: defaultdict(
            lambda: {
                "polyphonic": set(),
                "wendu": set(),
                "baidu": set(),
                "wenbai": set(),
                "_marks_by_char": defaultdict(set),
            }
        )
    )
)
```

輸出前轉成：

```python
{
    "polyphonic": {"count": ..., "chars": [...]},
    "wendu": {"count": ..., "chars": [...]},
    "baidu": {"count": ..., "chars": [...]},
    "wenbai": {"count": ..., "chars": [...]},
}
```

### 三、共用判斷規則

建議把文白讀標記判斷抽成 service 內私有輔助函數，避免兩個實作再複製一套。

可抽的最小工具：

- `_mark_to_text`
- `_is_polyphonic_mark`
- `_is_wendu_mark`
- `_is_baidu_mark`
- `_finalize_read_stats_sets`

`_finalize_read_stats_sets` 的職責：

- 根據 `_marks_by_char` 補全 `wenbai`
- 排序輸出
- 刪除中間態字段

## 錯誤處理

### `feature_stats`

不新增新的業務錯誤類型。

若查無數據：

- 維持現有 404 行為

若某個音值桶沒有任何文白讀字：

- `read_stats` 仍然返回
- 四類都給出 `count=0`
- `char_indices=[]`

### `phonology_matrix`

同樣不新增新的業務錯誤類型。

若某格沒有文白讀字：

- `matrix_read_stats` 該格仍返回
- 四類都給出空結果

這比省略字段更利於前端穩定渲染。

## 測試設計

至少覆蓋以下情形：

1. `多音字=1`
   - 命中 `polyphonic`
   - 不命中 `wendu/baidu/wenbai`

2. `多音字=2`
   - 命中 `polyphonic`
   - 命中 `wendu`
   - 不命中 `baidu`

3. `多音字=3`
   - 命中 `polyphonic`
   - 命中 `baidu`
   - 不命中 `wendu`

4. 同字同桶同時存在 `2` 和 `3`
   - 命中 `wenbai`

5. 同字跨不同桶分別存在 `2` 和 `3`
   - 不應誤判為同一桶 `wenbai`

6. 舊字段回歸不變
   - `feature_stats.count/ratio/char_indices` 不變
   - `phonology_matrix.matrix` 不變

## 性能考量

### `feature_stats`

新增邏輯只是在現有 `all_rows` 單次遍歷中追加 set 聚合，時間複雜度仍與查詢結果線性相關。

內存增量主要來自：

- 每個音值桶的四類 set
- 每字的 `_marks_by_char`

在現有接口規模下可接受。

### `phonology_matrix`

由於需要保留單字級 `多音字` 標記，本次為 `matrix_read_stats` 增加一條細粒度查詢。

這會比只用 `GROUP_CONCAT` 略重，但有三個控制條件：

- 仍然只查指定 `locations`
- 只服務 `phonology_matrix`
- 原始 `matrix` 快路徑不變

若後續成為性能瓶頸，再考慮：

- 單獨緩存 `matrix_read_stats`
- 或改為一次細粒度查詢同時構造 `matrix + matrix_read_stats`

本次不提前優化。

## 不做的事

本次明確不做：

- 不修改 `/api/compare/chars`
- 不修改 `/api/phonology_classification_matrix`
- 不修改 `/api/pho_pie_by_value`
- 不修改 `/api/pho_pie_by_status`
- 不新增文白讀專用篩選參數
- 不改 `phonology_matrix.matrix` 的節點類型

## 交付標準

完成後應滿足：

1. `feature_stats` 在不破壞既有字段的前提下新增 `read_stats`
2. `phonology_matrix` 在不破壞既有 `matrix` 的前提下新增 `matrix_read_stats`
3. 單元測試或接口測試覆蓋 `1/2/3/2+3`
4. README 或 API 文檔示例同步更新
