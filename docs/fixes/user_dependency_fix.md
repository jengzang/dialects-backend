# User Dependency Fix

## 問題描述

在統一路由權限檢查時，移除了路由函數內部的 `user` 依賴注入參數。但部分函數內部需要根據 `user` 來判斷使用哪個數據庫（admin vs user），導致這些函數報錯。

## 影響範圍

共影響 `app/routes/phonology.py` 中的 5 個路由函數：

1. `api_run_phonology_analysis` (line 30)
2. `phonology_matrix` (line 154)
3. `api_phonology_classification_matrix` (line 231)
4. `feature_stats` (line 270)
5. `feature_counts` (line 135)

## 修復方案

為所有需要根據用戶身份選擇數據庫的函數恢復 `user` 參數：

```python
from typing import Optional
from app.service.auth import User
from app.service.auth import get_current_user

@router.post("/endpoint")
async def endpoint_function(
    payload: SomeRequest,
    user: Optional[User] = Depends(get_current_user)  # 恢復此參數
):
    # 根據用戶身份決定資料庫
    db_path = DIALECTS_DB_ADMIN if user and user.role == "admin" else DIALECTS_DB_USER
    ...
```

## 修復內容

### 1. 取消註釋必要的導入 (line 14-16)

```python
from app.service.auth import get_current_user
from app.service.auth import User
```

### 2. 為 5 個函數添加 user 參數

所有函數都添加了：
```python
user: Optional[User] = Depends(get_current_user)
```

## 驗證結果

- ✅ 所有路由文件掃描完成，無其他類似問題
- ✅ `phonology.py` 導入成功，無語法錯誤
- ✅ 函數內部可以正常使用 `user` 變量判斷數據庫

## 設計原則

**統一權限檢查 vs 內部業務邏輯**

- **路由級別權限檢查**：在 `app/routes/__init__.py` 註冊時統一添加 `dependencies=[Depends(ApiLimiter)]`
- **函數級別用戶判斷**：當函數內部需要根據用戶身份做業務邏輯判斷時，仍需在函數參數中聲明 `user`

這兩者不衝突：
- `ApiLimiter` 負責限流和日誌記錄
- `get_current_user` 負責提供用戶對象供業務邏輯使用

## 日期

2026-03-05
