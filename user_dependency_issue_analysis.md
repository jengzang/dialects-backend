# 緊急問題：刪除 user 依賴導致的錯誤

## 問題概述

在統一路由權限檢查時，我們刪除了路由函數內部的 user 參數，但有些函數內部仍在使用 user 對象進行業務邏輯判斷，導致 NameError。

## 影響範圍

### 1. app/routes/phonology.py:140
**函數**: `feature_counts`
**問題**: 第 140 行使用了 `user` 但函數沒有 user 參數
```python
@router.get("/feature_counts")
async def feature_counts(
    locations: List[str] = Query(...)
):
    # 根據用戶身分決定資料庫
    db_path = DIALECTS_DB_ADMIN if user and user.role == "admin" else DIALECTS_DB_USER  # ❌ user 未定義
```

### 2. app/routes/auth.py:355
**函數**: `get_leaderboard`
**問題**: 第 349-355 行使用了 `user` 但函數沒有 user 參數
```python
@router.get("/leaderboard")
def get_leaderboard(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    # ... token 解析 ...
    user = db.query(models.User).filter(models.User.username == username).first()  # ✓ 這裡定義了 user
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return get_user_leaderboard(db, user.id)  # ✓ 使用 user.id
```

**注意**: auth.py 的問題是誤報，因為函數內部自己查詢了 user。

## 修復方案

### 方案 A：恢復必要的 user 參數（推薦）

**優點**：
- 最小改動
- 保持業務邏輯不變
- 符合 FastAPI 依賴注入模式

**缺點**：
- 部分路由函數會有 user 參數（但這是必要的）

**實施**：
只恢復那些在函數內部使用 user 的參數。

### 方案 B：從 Request 對象獲取 user

**優點**：
- 函數簽名保持簡潔

**缺點**：
- 需要修改業務邏輯
- 不符合 FastAPI 最佳實踐
- 增加複雜度

### 方案 C：修改業務邏輯，不依賴 user

**優點**：
- 函數簽名簡潔

**缺點**：
- 需要大量修改業務邏輯
- 可能影響功能

## 推薦方案：方案 A

### 修復步驟

#### 1. app/routes/phonology.py:135

**當前代碼**：
```python
@router.get("/feature_counts")
async def feature_counts(
    locations: List[str] = Query(...)
):
    db_path = DIALECTS_DB_ADMIN if user and user.role == "admin" else DIALECTS_DB_USER
```

**修復後**：
```python
@router.get("/feature_counts")
async def feature_counts(
    locations: List[str] = Query(...),
    user: Optional[User] = Depends(get_current_user)  # 恢復 user 參數
):
    db_path = DIALECTS_DB_ADMIN if user and user.role == "admin" else DIALECTS_DB_USER
```

**需要添加導入**：
```python
from typing import Optional
from app.auth.models import User
from app.auth.dependencies import get_current_user
```

#### 2. app/routes/auth.py:318

**當前代碼**：
```python
@router.get("/leaderboard")
def get_leaderboard(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    # 函數內部自己查詢 user
    user = db.query(models.User).filter(models.User.username == username).first()
```

**結論**：無需修改（函數內部自己查詢了 user）

## 全面排查建議

### 1. 檢查所有被刪除 user 參數的函數

運行以下腳本檢查：
```bash
python check_user_usage.py
```

### 2. 檢查是否還有其他類似問題

搜索所有使用 `current_user` 的情況：
```bash
grep -r "current_user\." app/routes app/sql app/tools --include="*.py"
```

### 3. 運行測試

```bash
# 啟動應用測試
python -c "from app.main import app; print('OK')"

# 測試受影響的端點
curl http://localhost:5000/api/feature_counts?locations=東莞莞城
curl http://localhost:5000/auth/leaderboard
```

## 預防措施

### 1. 添加類型檢查

在 CI/CD 中添加 mypy 類型檢查：
```bash
mypy app/routes app/sql app/tools
```

### 2. 添加單元測試

為關鍵路由添加測試，確保 user 對象可用。

### 3. 代碼審查清單

在刪除依賴注入參數前，檢查：
- [ ] 函數內部是否使用該參數
- [ ] 是否有條件判斷依賴該參數
- [ ] 是否有業務邏輯需要該參數

## 總結

**立即修復**：
1. 恢復 `app/routes/phonology.py:135` 的 user 參數
2. 添加必要的導入

**後續改進**：
1. 運行全面檢查腳本
2. 添加類型檢查
3. 添加單元測試

**影響評估**：
- 嚴重程度：高（導致運行時錯誤）
- 影響範圍：小（只有 1 個函數需要修復）
- 修復難度：低（只需恢復參數）
