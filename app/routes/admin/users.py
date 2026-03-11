"""
用户管理API端点（路由层）

职责：
- HTTP请求处理
- 参数验证
- 响应格式化
- 权限检查

业务逻辑在 app.admin.user_service 中实现
"""
from typing import List
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.service.auth import models
from app.service.auth.database import get_db
from app.service.auth.dependencies import get_current_admin_user
from app.schemas.admin import UserUpdateSchema, AdminCreate, UpdatePassword, LetAdmin, UserListItem
from app.schemas.auth import UserResponse
from app.service.admin import user_service

router = APIRouter()


# 获取用户列表（轻量级，仅包含基本信息）
@router.get("/list", response_model=List[UserListItem])
def get_users_list(db: Session = Depends(get_db)):
    """
    获取用户列表（轻量级）
    仅返回用户名、邮箱和角色，适合用于下拉列表、表格等场景
    """
    users = user_service.get_users_list(db)
    return [UserListItem.from_orm(user) for user in users]


# 获取所有用户
@router.get("/all", response_model=List[UserResponse])
def get_users(db: Session = Depends(get_db)):
    """获取所有用户（完整信息）"""
    users = user_service.get_all_users(db)
    return [UserResponse.from_orm(user) for user in users]


# 获取单个用户，禁用通过 user_id 查找，改为通过 username 或 email 查找
@router.get("/single", response_model=UserResponse)
def get_user(query: str, db: Session = Depends(get_db)):
    """通过用户名或邮箱查找用户"""
    user = user_service.get_user_by_query(db, query)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# 创建用户
@router.post("/create", response_model=UserResponse)
def create_user(user: AdminCreate, db: Session = Depends(get_db)):
    """创建新用户"""
    result = user_service.create_user_logic(
        db=db,
        username=user.username,
        email=user.email,
        password=user.password,
        role=user.role
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    return UserResponse.from_orm(result["user"])


# 更新用户，禁用通过 user_id 查找，改为通过 username 或 email 查找
@router.put("/update", response_model=UserUpdateSchema)
def update_user(
    query: str,
    user: UserUpdateSchema,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_admin_user)
):
    """更新用户信息"""
    result = user_service.update_user_logic(
        db=db,
        query=query,
        username=user.username,
        email=user.email,
        current_user=current_user
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    return result["user"]


# 删除用户，禁用通过 user_id 查找，改为通过 username 或 email 查找
@router.delete("/delete", response_model=UserResponse)
def delete_user(query: str, db: Session = Depends(get_db)):
    """删除用户"""
    result = user_service.delete_user_logic(db, query)

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    return result["user"]


# 更改用戶密碼
@router.put("/password", response_model=UserUpdateSchema)
def update_password(
    user: UpdatePassword,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_admin_user)
):
    """更新用户密码"""
    result = user_service.update_password_logic(
        db=db,
        username=user.username,
        password=user.password,
        current_user=current_user
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    return result["user"]


@router.put("/let_admin", response_model=UserUpdateSchema)
async def let_admin(
    user: LetAdmin,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin_user)
):
    """更新用户角色"""
    result = await user_service.update_role_logic(
        db=db,
        username=user.username,
        role=user.role
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    return result["user"]
