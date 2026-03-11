"""
用户管理业务逻辑层

职责：
- 用户查询和过滤
- 用户创建、更新、删除
- 权限管理
- 密码管理

注意：此模块不依赖FastAPI，可在任何地方调用
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.service.auth import models
from app.service.auth.utils import get_password_hash


def get_users_list(db: Session) -> List[models.User]:
    """
    获取用户列表（轻量级）
    仅返回用户名、邮箱和角色，适合用于下拉列表、表格等场景

    Args:
        db: 数据库会话

    Returns:
        用户列表
    """
    return db.query(models.User).all()


def get_all_users(db: Session) -> List[models.User]:
    """
    获取所有用户（完整信息）

    Args:
        db: 数据库会话

    Returns:
        用户列表
    """
    return db.query(models.User).all()


def get_user_by_query(db: Session, query: str) -> Optional[models.User]:
    """
    通过用户名或邮箱查找用户

    Args:
        db: 数据库会话
        query: 用户名或邮箱

    Returns:
        用户对象，如果未找到则返回None
    """
    if not query:
        return None

    return db.query(models.User).filter(
        (models.User.username == query) | (models.User.email == query)
    ).first()


def create_user_logic(
    db: Session,
    username: str,
    email: str,
    password: str,
    role: str
) -> Dict[str, Any]:
    """
    创建新用户

    Args:
        db: 数据库会话
        username: 用户名
        email: 邮箱
        password: 密码（明文）
        role: 角色（admin或user）

    Returns:
        结果字典，包含success和user或error
    """
    # 检查角色是否有效
    if role not in ["admin", "user"]:
        return {
            "success": False,
            "error": "Invalid role. Choose either 'admin' or 'user'."
        }

    # 检查 email 是否已经存在
    existing_user_by_email = db.query(models.User).filter(models.User.email == email).first()
    if existing_user_by_email:
        return {
            "success": False,
            "error": "該郵箱已存在"
        }

    # 检查 username 是否已经存在
    existing_user_by_username = db.query(models.User).filter(models.User.username == username).first()
    if existing_user_by_username:
        return {
            "success": False,
            "error": "該用戶名已存在"
        }

    # 对密码进行哈希处理
    hashed_password = get_password_hash(password)

    # 创建新的用户
    db_user = models.User(
        username=username,
        email=email,
        hashed_password=hashed_password,
        role=role
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return {
        "success": True,
        "user": db_user
    }


def update_user_logic(
    db: Session,
    query: str,
    username: Optional[str] = None,
    email: Optional[str] = None,
    current_user: Optional[models.User] = None
) -> Dict[str, Any]:
    """
    更新用户信息

    Args:
        db: 数据库会话
        query: 用户名或邮箱（用于查找要更新的用户）
        username: 新用户名（可选）
        email: 新邮箱（可选）
        current_user: 当前操作用户（用于权限检查）

    Returns:
        结果字典，包含success和user或error
    """
    if not query:
        return {
            "success": False,
            "error": "Query parameter is required"
        }

    # 查找用户
    db_user = db.query(models.User).filter(
        (models.User.username == query) | (models.User.email == query)
    ).first()

    if not db_user:
        return {
            "success": False,
            "error": "User not found"
        }

    # 权限检查：管理员不能编辑其他管理员
    if db_user.role == "admin":
        if current_user and db_user.username != current_user.username:
            return {
                "success": False,
                "error": "不能編輯管理員！"
            }

    # 检查是否已经有相同的用户名或邮箱
    if username:
        existing_user_by_username = db.query(models.User).filter(
            models.User.username == username,
            models.User.id != db_user.id
        ).first()
        if existing_user_by_username:
            return {
                "success": False,
                "error": "Username already exists"
            }

    if email:
        existing_user_by_email = db.query(models.User).filter(
            models.User.email == email,
            models.User.id != db_user.id
        ).first()
        if existing_user_by_email:
            return {
                "success": False,
                "error": "Email already exists"
            }

    # 更新字段
    if username:
        db_user.username = username
    if email:
        db_user.email = email

    db.commit()
    db.refresh(db_user)

    return {
        "success": True,
        "user": db_user
    }


def delete_user_logic(db: Session, query: str) -> Dict[str, Any]:
    """
    删除用户

    Args:
        db: 数据库会话
        query: 用户名或邮箱

    Returns:
        结果字典，包含success和user或error
    """
    if not query:
        return {
            "success": False,
            "error": "Query parameter is required"
        }

    # 查找用户
    db_user = db.query(models.User).filter(
        (models.User.username == query) | (models.User.email == query)
    ).first()

    if not db_user:
        return {
            "success": False,
            "error": "User not found"
        }

    # 不能删除管理员
    if db_user.role == "admin":
        return {
            "success": False,
            "error": "不能刪除管理員！"
        }

    db.delete(db_user)
    db.commit()

    return {
        "success": True,
        "user": db_user
    }


def update_password_logic(
    db: Session,
    username: str,
    password: str,
    current_user: Optional[models.User] = None
) -> Dict[str, Any]:
    """
    更新用户密码

    Args:
        db: 数据库会话
        username: 用户名
        password: 新密码（明文）
        current_user: 当前操作用户（用于权限检查）

    Returns:
        结果字典，包含success和user或error
    """
    if not username:
        return {
            "success": False,
            "error": "Username is required"
        }

    # 查找用户
    db_user = db.query(models.User).filter(models.User.username == username).first()

    if not db_user:
        return {
            "success": False,
            "error": "User not found"
        }

    # 权限检查：管理员不能更改其他管理员的密码
    if db_user.role == "admin":
        if current_user and db_user.username != current_user.username:
            return {
                "success": False,
                "error": "不能更改管理員的密碼！"
            }

    # 更新密码
    if password:
        db_user.hashed_password = get_password_hash(password)

    db.commit()
    db.refresh(db_user)

    return {
        "success": True,
        "user": db_user
    }


async def update_role_logic(
    db: Session,
    username: str,
    role: str
) -> Dict[str, Any]:
    """
    更新用户角色

    Args:
        db: 数据库会话
        username: 用户名
        role: 新角色（admin或user）

    Returns:
        结果字典，包含success和user或error
    """
    if not username:
        return {
            "success": False,
            "error": "Username is required"
        }

    # 查找用户
    db_user = db.query(models.User).filter(models.User.username == username).first()

    if not db_user:
        return {
            "success": False,
            "error": "User not found"
        }

    # 验证角色
    if role not in ["admin", "user"]:
        return {
            "success": False,
            "error": "Invalid role value. Allowed values: 'admin', 'user'"
        }

    # 记录修改前的role（用于审计）
    old_role = db_user.role

    # 更新角色
    db_user.role = role
    db.commit()

    # 清除缓存
    from app.redis_client import redis_client
    try:
        await redis_client.delete(f"user:{username}")
        print(f"[CACHE-INVALIDATE] Cleared cache for {username} after role change: {old_role} -> {role}")
    except Exception as e:
        print(f"[CACHE-INVALIDATE] Failed to clear cache: {e}")

    db.refresh(db_user)

    return {
        "success": True,
        "user": db_user
    }
