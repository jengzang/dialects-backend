# User 依賴注入全面修復報告

## 問題背景

在統一路由權限檢查架構時，將所有路由的權限檢查移到了註冊層面（通過 `dependencies=[Depends(ApiLimiter)]`），並移除了路由函數內部的依賴注入參數。

但是，許多路由函數內部需要根據用戶身份（`user.role`）來決定使用哪個數據庫：
- 管理員用戶：使用 `DIALECTS_DB_ADMIN` 和 `QUERY_DB_ADMIN`
- 普通用戶：使用 `DIALECTS_DB_USER` 和 `QUERY_DB_USER`

這導致這些函數在運行時報錯：`NameError: name 'user' is not defined`

## 影響範圍

總共影響 **7 個路由文件**，**14 個路由函數**：

### 1. app/routes/phonology.py (5 個函數)
- `api_run_phonology_analysis` - 音韻分析
- `phonology_matrix` - 音韻矩陣
- `api_phonology_classification_matrix` - 分類矩陣
- `feature_stats` - 特徵統計
- `feature_counts` - 特徵計數

### 2. app/routes/compare.py (2 個函數)
- `compare_chars` - 字音比較
- `compare_tones_route` - 聲調比較

### 3. app/routes/search.py (2 個函數)
- `search_chars` - 查字
- `search_tones_o` - 查調

### 4. app/routes/new_pho.py (2 個函數)
- `analyze_zhonggu` - 中古分析
- `analyze_yinwei` - 音位分析

### 5. app/routes/geo/batch_match.py (1 個函數)
- `batch_match` - 批量匹配地點

### 6. app/routes/geo/get_locs.py (1 個函數)
- `get_all_locs` - 獲取地點列表

### 7. app/routes/geo/get_coordinates.py (1 個函數)
- `get_coordinates` - 獲取坐標

## 修復方案

### 統一修復模式

對於每個受影響的文件：

**1. 取消註釋必要的導入**

```python
from app.service.auth import get_current_user
from app.service.auth import User
```

**2. 為函數添加 user 參數**
```python
@router.get("/endpoint")
async def endpoint_function(
    # ... 其他參數 ...
    user: Optional[User] = Depends(get_current_user)  # 添加此行
):
    # 函數內部可以使用 user
    db_path = DIALECTS_DB_ADMIN if user and user.role == "admin" else DIALECTS_DB_USER
```

### 典型使用場景

函數內部使用 user 的常見模式：

```python
# 1. 選擇數據庫
db_path = DIALECTS_DB_ADMIN if user and user.role == "admin" else DIALECTS_DB_USER
query_db = QUERY_DB_ADMIN if user and user.role == "admin" else QUERY_DB_USER

# 2. 傳遞給服務層函數
locations_processed = match_locations_batch_all(
    locations or [],
    query_db=query_db,
    db=db,
    user=user  # 傳遞 user 對象
)

# 3. 判斷數據庫類型
db_type = "admin" if user and user.role == "admin" else "user"
```

## 驗證結果

### 自動化檢查
創建了 `find_all_user_issues.py` 腳本，掃描所有路由文件：
- ✅ 修復前：找到 14 個問題函數
- ✅ 修復後：0 個問題

### 導入測試

```python
from app.routes.core.compare import router
from app.routes.geo.batch_match import router
from app.routes.geo.get_locs import router
from app.routes.geo.get_coordinates import router
from app.routes.core.search import router
from app.routes.core.new_pho import router
from app.routes.core.phonology import router
```
✅ 所有文件導入成功，無語法錯誤

## 設計原則澄清

### 路由級別權限檢查 vs 函數級別用戶判斷

這兩者**不衝突**，各有用途：

**路由級別（註冊時）**：
```python
# app/routes/__init__.py
app.include_router(
    phonology_router,
    prefix="/api",
    tags=["音韻分析"],
    dependencies=[Depends(ApiLimiter)]  # 統一限流和日誌
)
```
- 作用：限流、日誌記錄、基礎權限檢查
- 由 `ApiLimiter` 依賴注入處理

**函數級別（函數參數）**：
```python
async def endpoint(
    user: Optional[User] = Depends(get_current_user)
):
    # 根據用戶身份做業務邏輯判斷
    db = choose_db_by_user_role(user)
```
- 作用：提供用戶對象供業務邏輯使用
- 由 `get_current_user` 依賴注入處理

### 何時需要函數級別的 user 參數？

當函數內部需要：
1. 根據用戶角色選擇不同的數據庫
2. 將用戶信息傳遞給服務層函數
3. 根據用戶權限返回不同的數據
4. 記錄用戶特定的操作日誌

## 預防措施

### 1. 代碼審查清單
在移除依賴注入參數前，檢查：
- [ ] 函數內部是否使用了該參數？
- [ ] 函數是否將該參數傳遞給其他函數？
- [ ] 是否有條件判斷依賴該參數？

### 2. 自動化檢測
使用 `find_all_user_issues.py` 腳本定期掃描：
```bash
python find_all_user_issues.py
```

### 3. 類型檢查
考慮啟用 mypy 進行靜態類型檢查：
```bash
mypy app/routes/
```

## 提交記錄

- **第一次提交** (d99fd9c): 修復 phonology.py (5 個函數)
- **第二次提交** (0000d1e): 修復其餘 6 個文件 (9 個函數)

## 總結

本次修復徹底解決了統一權限檢查架構重構後遺留的 user 依賴問題：
- ✅ 14 個函數全部修復
- ✅ 7 個文件全部更新
- ✅ 自動化驗證通過
- ✅ 導入測試通過

**關鍵教訓**：在進行大規模重構時，必須全面檢查變量的使用情況，不能僅依賴語法檢查，還需要運行時驗證。

---

**修復日期**: 2026-03-05
**修復人員**: Claude Sonnet 4.5
