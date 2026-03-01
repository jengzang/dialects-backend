# 前端改動清單 - 自定義分區功能

## 快速概覽

**新增功能：** 用戶自定義地點分組（自定義分區）

**後端提供：** 3個新API接口
- `POST /api/custom_regions` - 創建/更新
- `DELETE /api/custom_regions` - 刪除
- `GET /api/custom_regions` - 查詢

**重要：** 現有API（`/api/get_coordinates`、`/api/get_locs` 等）**無需修改**

---

## 前端必須改動的地方

### ✅ 1. 分區選擇器（必改）

**位置：** 地圖頁面、查詢頁面的分區下拉框

**改動：**
```javascript
// 原有：只顯示系統分區
const systemRegions = ['嶺南', '嶺南-珠江', ...];

// 新增：同時顯示自定義分區
const customRegions = await fetch('/api/custom_regions').then(r => r.json());

// UI結構
<Select>
  <OptGroup label="系統分區">
    {systemRegions.map(...)}
  </OptGroup>
  <OptGroup label="我的自定義分區">
    {customRegions.regions.map(...)}
  </OptGroup>
</Select>
```

**處理邏輯：**
```javascript
// 用戶選擇自定義分區時
if (isCustomRegion) {
  // 1. 查詢分區內容
  const region = await fetch(`/api/custom_regions?region_name=${name}`);
  const locations = region.regions[0].locations;

  // 2. 傳給現有API（無需改API）
  await fetch('/api/get_coordinates', {
    body: JSON.stringify({
      locations: locations.join(','),  // 傳地點列表
      regions: '',  // 不用系統分區
      ...
    })
  });
}
```

---

### ✅ 2. 分區管理頁面（新增）

**位置：** 新增一個頁面或彈窗

**功能清單：**
- [ ] 列表展示所有自定義分區
- [ ] 創建新分區（輸入名稱、選擇地點、添加描述）
- [ ] 編輯分區（修改地點列表）
- [ ] 刪除分區

**參考UI：**
```
┌────────────────────────────────┐
│ 我的自定義分區          [+ 新建] │
├────────────────────────────────┤
│ 📍 我的研究區域      [編輯][刪除] │
│    廣州, 佛山, 南海 (3個地點)    │
│    珠三角核心城市                │
├────────────────────────────────┤
│ 📍 閩南方言點        [編輯][刪除] │
│    廈門, 泉州, 漳州 (3個地點)    │
└────────────────────────────────┘
```

**關鍵代碼：**
```javascript
// 創建/更新
await fetch('/api/custom_regions', {
  method: 'POST',
  body: JSON.stringify({
    region_name: '我的研究區域',
    locations: ['廣州', '佛山', '南海'],
    description: '珠三角核心城市'
  })
});

// 刪除
await fetch('/api/custom_regions?region_name=我的研究區域', {
  method: 'DELETE'
});

// 查詢列表
const data = await fetch('/api/custom_regions').then(r => r.json());
```

---

### ✅ 3. 地點選擇器（新增組件）

**位置：** 創建/編輯自定義分區時使用

**功能：**
- 多選地點（Checkbox、Tag選擇器等）
- 搜索和篩選
- 顯示已選地點數量

**示例：**
```javascript
<MultiSelect
  options={allLocations}  // 從現有數據獲取
  value={selectedLocations}
  onChange={setSelectedLocations}
  placeholder="選擇地點..."
  searchable
/>

<div>已選擇 {selectedLocations.length} 個地點</div>
```

---

## 可選改動

### 🔹 導航菜單

添加「自定義分區管理」入口

```
用戶菜單
├── 個人資料
├── 自定義分區管理  ← 新增
└── 退出登錄
```

---

### 🔹 分區標識

在UI上區分系統分區和自定義分區

```javascript
// 系統分區
<Tag color="blue">嶺南</Tag>

// 自定義分區
<Tag color="green" icon={<UserOutlined />}>我的研究區域</Tag>
```

---

## 數據流程圖

```
用戶操作                前端                    後端API
   │                     │                        │
   ├─ 查看分區列表 ────→ GET /api/custom_regions
   │                     │ ←──────────────────── regions[]
   │                     │
   ├─ 創建分區 ─────────→ POST /api/custom_regions
   │                     │   {region_name, locations}
   │                     │ ←──────────────────── {success, region}
   │                     │
   ├─ 選擇自定義分區 ───→ GET /api/custom_regions?region_name=XXX
   │                     │ ←──────────────────── {locations: [...]}
   │                     │
   │                     ├─ 提取 locations
   │                     │
   │                     ├─ POST /api/get_coordinates
   │                     │   {locations: "廣州,佛山,南海"}
   │                     │ ←──────────────────── {coordinates: [...]}
   │                     │
   └─ 顯示地圖 ←─────────┤
```

---

## 關鍵注意事項

### ⚠️ 1. 編輯是覆蓋更新

```javascript
// ❌ 錯誤：以為是增量更新
await fetch('/api/custom_regions', {
  body: JSON.stringify({
    region_name: '我的研究區域',
    locations: ['東莞']  // 只傳新增的
  })
});
// 結果：原有的廣州、佛山、南海被刪除了！

// ✅ 正確：傳完整列表
await fetch('/api/custom_regions', {
  body: JSON.stringify({
    region_name: '我的研究區域',
    locations: ['廣州', '佛山', '南海', '東莞']  // 完整列表
  })
});
```

### ⚠️ 2. 需要登錄

所有API都需要在請求頭中帶上 `Authorization: Bearer {token}`

```javascript
fetch('/api/custom_regions', {
  headers: {
    'Authorization': `Bearer ${accessToken}`
  }
})
```

### ⚠️ 3. 錯誤處理

```javascript
const response = await fetch('/api/custom_regions', {...});

if (response.status === 401) {
  // 未登錄，跳轉登錄頁
  router.push('/login');
} else if (response.status === 400) {
  // 參數錯誤，顯示錯誤信息
  const error = await response.json();
  message.error(error.detail);
} else if (response.ok) {
  // 成功
  const data = await response.json();
  // ...
}
```

---

## 測試檢查清單

開發完成後，請測試以下場景：

- [ ] 創建新的自定義分區
- [ ] 編輯已有分區（修改地點列表）
- [ ] 刪除分區
- [ ] 在分區選擇器中看到自定義分區
- [ ] 選擇自定義分區後，地圖正常顯示對應地點
- [ ] 未登錄時無法訪問自定義分區功能
- [ ] 創建同名分區時正確覆蓋更新
- [ ] 刪除不存在的分區時顯示錯誤提示

---

## 時間估算

- 分區選擇器改動：**2-3小時**
- 分區管理頁面：**1-2天**
- 地點選擇器組件：**4-6小時**
- 集成測試：**2-3小時**

**總計：約2-3天**

---

## 需要後端配合的地方

✅ **無需配合** - 所有API已經完成，前端可以直接開始開發

如有問題，請查看詳細文檔：`docs/custom_regions_frontend_guide.md`
