# 自定義分區功能 - 前端集成指南

## 概述

後端新增了用戶自定義分區功能，允許用戶創建、編輯、刪除和查詢自己的地點分組。

**重要：無需修改現有API調用！** 前端只需先查詢自定義分區獲取地點列表，然後傳給現有的 `/api/get_coordinates` 等接口即可。

---

## 新增API接口

### 1. 創建/更新自定義分區

**端點：** `POST /api/custom_regions`

**需要登錄：** ✅ 是

**請求體：**
```json
{
  "region_name": "我的研究區域",
  "locations": ["廣州", "佛山", "南海"],
  "description": "珠三角核心城市"  // 可選
}
```

**響應（成功）：**
```json
{
  "success": true,
  "action": "created",  // 或 "updated"
  "region": {
    "id": 123,
    "region_name": "我的研究區域",
    "locations": ["廣州", "佛山", "南海"],
    "description": "珠三角核心城市",
    "created_at": "2026-02-17T10:30:00",
    "updated_at": "2026-02-17T10:30:00"
  }
}
```

**行為說明：**
- 如果 `region_name` 已存在 → 更新（覆蓋原有的 locations 和 description）
- 如果 `region_name` 不存在 → 創建新分區
- `locations` 數組不能為空
- `description` 為可選字段

---

### 2. 刪除自定義分區

**端點：** `DELETE /api/custom_regions?region_name=XXX`

**需要登錄：** ✅ 是

**查詢參數：**
- `region_name` (必填): 要刪除的分區名稱

**響應（成功）：**
```json
{
  "success": true,
  "deleted": true,
  "region_name": "我的研究區域"
}
```

**響應（未找到）：**
```json
{
  "success": false,
  "deleted": false,
  "error": "Region not found"
}
```

---

### 3. 查詢自定義分區

**端點：** `GET /api/custom_regions`

**需要登錄：** ✅ 是（未登錄返回空數組）

**查詢參數：**
- `region_name` (可選): 篩選特定分區

**響應（全部分區）：**
```json
{
  "success": true,
  "regions": [
    {
      "id": 123,
      "region_name": "我的研究區域",
      "locations": ["廣州", "佛山", "南海"],
      "location_count": 3,
      "description": "珠三角核心城市",
      "created_at": "2026-02-17T10:30:00",
      "updated_at": "2026-02-17T10:30:00"
    },
    {
      "id": 124,
      "region_name": "閩南方言點",
      "locations": ["廈門", "泉州", "漳州"],
      "location_count": 3,
      "description": null,
      "created_at": "2026-02-17T11:00:00",
      "updated_at": "2026-02-17T11:00:00"
    }
  ],
  "total": 2
}
```

**響應（查詢特定分區）：**
```
GET /api/custom_regions?region_name=我的研究區域
```
```json
{
  "success": true,
  "regions": [
    {
      "id": 123,
      "region_name": "我的研究區域",
      "locations": ["廣州", "佛山", "南海"],
      "location_count": 3,
      "description": "珠三角核心城市",
      "created_at": "2026-02-17T10:30:00",
      "updated_at": "2026-02-17T10:30:00"
    }
  ],
  "total": 1
}
```

---

## 前端集成流程

### 典型使用場景

用戶選擇一個自定義分區後，前端需要：

1. **查詢分區內容** → 獲取地點列表
2. **傳遞給現有API** → 使用地點列表調用 `/api/get_coordinates` 等接口

### 示例代碼

```javascript
// 1. 用戶選擇自定義分區
const selectedRegion = "我的研究區域";

// 2. 查詢該分區的地點列表
const response = await fetch(
  `/api/custom_regions?region_name=${encodeURIComponent(selectedRegion)}`,
  {
    headers: {
      'Authorization': `Bearer ${accessToken}`
    }
  }
);

const data = await response.json();

if (data.success && data.regions.length > 0) {
  const locations = data.regions[0].locations;  // ["廣州", "佛山", "南海"]

  // 3. 傳遞給現有API（無需修改現有API調用）
  const coordsResponse = await fetch('/api/get_coordinates', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${accessToken}`
    },
    body: JSON.stringify({
      locations: locations.join(','),  // "廣州,佛山,南海"
      regions: '',  // 不使用系統分區
      region_mode: 'yindian',
      flag: true
    })
  });

  const coords = await coordsResponse.json();
  // 使用坐標數據渲染地圖...
}
```

---

## 前端需要改動的地方

### 1. 分區選擇器組件

**位置：** 地圖頁面或查詢頁面的分區選擇下拉框

**改動內容：**
- 添加「自定義分區」選項卡或分組
- 調用 `GET /api/custom_regions` 獲取用戶的自定義分區列表
- 在下拉框中顯示系統分區 + 自定義分區

**示例結構：**
```
分區選擇
├── 系統分區
│   ├── 嶺南
│   ├── 嶺南-珠江
│   └── ...
└── 我的自定義分區 ⭐
    ├── 我的研究區域
    ├── 閩南方言點
    └── ...
```

### 2. 分區管理頁面（新增）

**功能：** 用戶管理自己的自定義分區

**需要實現的功能：**
- **列表展示**：顯示所有自定義分區（調用 `GET /api/custom_regions`）
- **創建分區**：表單輸入分區名稱、選擇地點、添加描述（調用 `POST /api/custom_regions`）
- **編輯分區**：修改地點列表或描述（調用 `POST /api/custom_regions`，覆蓋更新）
- **刪除分區**：刪除不需要的分區（調用 `DELETE /api/custom_regions`）

**UI建議：**
```
┌─────────────────────────────────────────┐
│ 我的自定義分區                           │
├─────────────────────────────────────────┤
│ [+ 新建分區]                             │
│                                          │
│ ┌─────────────────────────────────────┐ │
│ │ 我的研究區域                    [編輯] [刪除] │
│ │ 地點：廣州, 佛山, 南海 (3個)           │
│ │ 描述：珠三角核心城市                   │
│ │ 創建時間：2026-02-17                  │
│ └─────────────────────────────────────┘ │
│                                          │
│ ┌─────────────────────────────────────┐ │
│ │ 閩南方言點                      [編輯] [刪除] │
│ │ 地點：廈門, 泉州, 漳州 (3個)           │
│ │ 創建時間：2026-02-17                  │
│ └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

### 3. 地點選擇器組件

**位置：** 創建/編輯自定義分區時選擇地點

**改動內容：**
- 提供多選地點的UI（可以是多選下拉框、標籤選擇器等）
- 可以從現有地點列表中選擇
- 支持搜索和篩選

### 4. 查詢邏輯調整

**位置：** 地圖查詢、坐標查詢等功能

**改動內容：**
```javascript
// 原有邏輯（系統分區）
if (selectedSystemRegion) {
  params.regions = selectedSystemRegion;
  params.locations = '';
}

// 新增邏輯（自定義分區）
if (selectedCustomRegion) {
  // 先查詢自定義分區獲取地點列表
  const customRegionData = await fetchCustomRegion(selectedCustomRegion);
  params.regions = '';  // 不使用系統分區
  params.locations = customRegionData.locations.join(',');
}

// 調用現有API（無需修改）
const result = await fetch('/api/get_coordinates', {
  method: 'POST',
  body: JSON.stringify(params)
});
```

---

## 權限說明

- **創建/編輯/刪除**：需要登錄
- **查詢**：需要登錄（未登錄返回空數組）
- **數據隔離**：每個用戶只能看到和操作自己的自定義分區

---

## 錯誤處理

### 常見錯誤

**401 Unauthorized**
```json
{
  "detail": "Not authenticated"
}
```
→ 用戶未登錄，需要跳轉到登錄頁面

**400 Bad Request**
```json
{
  "detail": "locations cannot be empty"
}
```
→ 地點列表為空，提示用戶至少選擇一個地點

**404 Not Found**
```json
{
  "success": false,
  "deleted": false,
  "error": "Region not found"
}
```
→ 刪除時分區不存在，可能已被刪除

**429 Too Many Requests**
```json
{
  "detail": "Rate limit exceeded"
}
```
→ 請求過於頻繁，提示用戶稍後再試

---

## 測試建議

### 測試用例

1. **創建分區**
   - 創建新分區 → 成功
   - 創建同名分區 → 覆蓋更新
   - 創建空地點列表 → 失敗

2. **查詢分區**
   - 查詢所有分區 → 返回列表
   - 查詢特定分區 → 返回單個分區
   - 未登錄查詢 → 返回空數組

3. **編輯分區**
   - 修改地點列表 → 成功覆蓋
   - 修改描述 → 成功更新

4. **刪除分區**
   - 刪除存在的分區 → 成功
   - 刪除不存在的分區 → 404錯誤

5. **集成測試**
   - 創建自定義分區 → 選擇該分區 → 查詢坐標 → 地圖正常顯示

---

## 常見問題

**Q: 自定義分區可以和系統分區同名嗎？**
A: 可以。前端需要區分系統分區和自定義分區（例如用不同的標籤或分組）。

**Q: 地點列表中的地點必須存在於數據庫嗎？**
A: 不需要。後端不會驗證地點是否存在，允許用戶為未來的數據創建分區。

**Q: 編輯分區時是增量更新還是完全覆蓋？**
A: 完全覆蓋。前端需要在編輯時傳遞完整的地點列表。

**Q: 可以分享自定義分區給其他用戶嗎？**
A: 目前不支持。每個用戶的自定義分區是獨立的。

**Q: 有數量限制嗎？**
A: 受限於通用的API速率限制（2000請求/小時），沒有特定的分區數量限制。

---

## 聯繫方式

如有問題或需要協助，請聯繫後端開發團隊。
