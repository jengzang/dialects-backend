from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.auth import models
from app.auth.database import get_db
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.auth.utils import get_password_hash
from app.schemas.admin import UserUpdateSchema, AdminCreate, UpdatePassword, LetAdmin
from app.schemas.auth import UserResponse

router = APIRouter()


# 获取所有用户
@router.get("/all", response_model=List[UserResponse])  # 回應是 UserResponse 的列表
def get_users(db: Session = Depends(get_db)):
    # 查詢所有的 User 物件，並將它們轉換為 UserResponse
    users = db.query(models.User).all()
    return [UserResponse.from_orm(user) for user in users]  # 使用 from_orm() 轉換 ORM 物件


# 获取单个用户，禁用通过 user_id 查找，改为通过 username 或 email 查找
@router.get("/single", response_model=UserResponse)
def get_user(query: str, db: Session = Depends(get_db)):
    if not query:
        raise HTTPException(status_code=400, detail="Query parameter is required")

    # 查找 username 或 email
    user = db.query(models.User).filter(
        (models.User.username == query) | (models.User.email == query)
    ).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


# 创建用户
@router.post("/create", response_model=UserResponse)  # 使用 UserResponse 作为返回模型
def create_user(user: AdminCreate, db: Session = Depends(get_db)):
    # 检查角色是否有效
    if user.role not in ["admin", "user"]:
        raise HTTPException(status_code=400, detail="Invalid role. Choose either 'admin' or 'user'.")

    # 检查 email 是否已经存在
    existing_user_by_email = db.query(models.User).filter(models.User.email == user.email).first()
    if existing_user_by_email:
        raise HTTPException(status_code=400, detail="該郵箱已存在")

    # 检查 username 是否已经存在
    existing_user_by_username = db.query(models.User).filter(models.User.username == user.username).first()
    if existing_user_by_username:
        raise HTTPException(status_code=400, detail="該用戶名已存在")

    # 对密码进行哈希处理
    hashed_password = get_password_hash(user.password)

    # 创建新的用户，将哈希后的密码存储
    db_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,  # 使用 hashed_password 字段
        role=user.role
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return UserResponse.from_orm(db_user)  # 直接使用 from_orm 映射返回


# 更新用户，禁用通过 user_id 查找，改为通过 username 或 email 查找
@router.put("/update", response_model=UserUpdateSchema)
def update_user(query: str, user: UserUpdateSchema, db: Session = Depends(get_db),
                current_user: Optional[User] = Depends(get_current_user)):
    if not query:
        raise HTTPException(status_code=400, detail="Query parameter is required")

    # 查找用戶名或郵箱
    db_user = db.query(models.User).filter(
        (models.User.username == query) | (models.User.email == query)
    ).first()

    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    if db_user.role == "admin":
        if db_user.username == current_user.username:
            pass
        else:
            # 管理員不能刪除其他管理員的數據
            raise HTTPException(status_code=400, detail="不能編輯管理員！")

    # 檢查是否已經有相同的用戶名或郵箱
    if user.username:
        existing_user_by_username = db.query(models.User).filter(models.User.username == user.username).first()
        if existing_user_by_username:
            raise HTTPException(status_code=400, detail="Username already exists")

    if user.email:
        existing_user_by_email = db.query(models.User).filter(models.User.email == user.email).first()
        if existing_user_by_email:
            raise HTTPException(status_code=400, detail="Email already exists")
    # 根據傳遞的字段進行更新
    if user.username:  # 如果傳遞了新的用戶名
        db_user.username = user.username
    if user.email:  # 如果傳遞了新的郵箱
        db_user.email = user.email

    db.commit()
    db.refresh(db_user)

    return db_user


# 删除用户，禁用通过 user_id 查找，改为通过 username 或 email 查找
@router.delete("/delete", response_model=UserResponse)
def delete_user(query: str, db: Session = Depends(get_db)):
    if not query:
        raise HTTPException(status_code=400, detail="Query parameter is required")

    # 查找 username 或 email
    db_user = db.query(models.User).filter(
        (models.User.username == query) | (models.User.email == query)
    ).first()

    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    if db_user.role == "admin":
        raise HTTPException(status_code=400, detail="不能刪除管理員！")

    db.delete(db_user)
    db.commit()
    return db_user

# 更改用戶密碼
@router.put("/password", response_model=UserUpdateSchema)
def update_password(user: UpdatePassword, db: Session = Depends(get_db),
                    current_user: Optional[User] = Depends(get_current_user)):
    if not user.username:
        raise HTTPException(status_code=400, detail="Query parameter is required")
    print(user.username)
    # 查找用戶名或郵箱
    db_user = db.query(models.User).filter(
        models.User.username == user.username
    ).first()

    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    if db_user.role == "admin":
        if db_user.username == current_user.username:
            pass
        else:
            # 管理員不能刪除其他管理員的數據
            raise HTTPException(status_code=400, detail="不能更改管理員的密碼！")

    if user.password:
        db_user.hashed_password = get_password_hash(user.password)

    db.commit()
    db.refresh(db_user)

    return db_user

@router.put("/let_admin", response_model=UserUpdateSchema)
def let_admin(user: LetAdmin, db: Session = Depends(get_db)):
    if not user.username:
        raise HTTPException(status_code=400, detail="Query parameter is required")
    print(user.username)
    # 查找用戶名或郵箱
    db_user = db.query(models.User).filter(
        models.User.username == user.username
    ).first()

    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    # 確保更新角色為有效值，這裡假設角色只有 'admin' 和 'user'
    if user.role not in ["admin", "user"]:
        raise HTTPException(status_code=400, detail="Invalid role value. Allowed values: 'admin', 'user'")
    if user.role:
        db_user.role = user.role

    db.commit()
    db.refresh(db_user)

    return db_user