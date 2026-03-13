"""
Custom数据管理员业务逻辑

职责：
- 管理员查询所有用户的custom数据
- 管理员创建、删除custom数据
- 统计用户数据数量

注意：此模块不依赖FastAPI，可在任何地方调用
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import func

from app.service.auth.database.models import User
from app.service.user.core.models import Information
from app.service.user.submission.submit import get_max_value


def get_all_custom_data(db_info: DBSession, db_user: DBSession) -> List[Dict[str, Any]]:
    """
    获取所有用户的custom数据

    Args:
        db_info: Information数据库会话
        db_user: User数据库会话

    Returns:
        包含username的数据列表
    """
    informations = db_info.query(Information).all()
    result = []

    for info in informations:
        user = db_user.query(User).filter(User.id == info.user_id).first()
        if user:
            result.append({
                "簡稱": info.簡稱,
                "音典分區": info.音典分區,
                "經緯度": info.經緯度,
                "聲韻調": info.聲韻調,
                "特徵": info.特徵,
                "值": info.值,
                "說明": info.說明,
                "username": user.username,
                "created_at": info.created_at,
            })
        else:
            result.append({
                "id": info.id,
                "error": "未找到對應的用戶"
            })

    return result


def get_user_data_count(db_info: DBSession, db_user: DBSession) -> List[Dict[str, Any]]:
    """
    获取每个用户的数据数量

    Args:
        db_info: Information数据库会话
        db_user: User数据库会话

    Returns:
        用户数据数量列表
    """
    user_data_count = db_info.query(
        Information.user_id, func.count(Information.id).label('data_count')
    ).group_by(Information.user_id).all()

    result = []

    for user_id, data_count in user_data_count:
        user = db_user.query(User).filter(User.id == user_id).first()
        if user:
            result.append({
                "username": user.username,
                "data_count": data_count
            })
        else:
            result.append({
                "user_id": user_id,
                "error": "未找到對應的用戶"
            })

    return result


def get_custom_by_username(
    db_info: DBSession,
    db_user: DBSession,
    username: str
) -> Optional[List[Information]]:
    """
    根据用户名查询用户数据

    Args:
        db_info: Information数据库会话
        db_user: User数据库会话
        username: 用户名

    Returns:
        用户数据列表，如果用户不存在则返回None
    """
    user = db_user.query(User).filter(User.username == username).first()
    if not user:
        return None

    user_data = db_info.query(Information).filter(Information.user_id == user.id).all()
    return user_data


def delete_custom_by_admin(
    db_info: DBSession,
    db_user: DBSession,
    requests: List[Dict[str, Any]],
    current_user: User
) -> Dict[str, Any]:
    """
    管理员删除custom数据

    Args:
        db_info: Information数据库会话
        db_user: User数据库会话
        requests: 删除请求列表，每个包含username和created_at
        current_user: 当前管理员用户

    Returns:
        结果字典
    """
    deleted_records = []

    for request in requests:
        username = request.get("username")
        created_at = request.get("created_at")

        # 查找用户
        user = db_user.query(User).filter(User.username == username).first()
        if not user:
            return {
                "success": False,
                "error": f"用戶 {username} 未找到"
            }

        # 权限检查：管理员不能删除其他管理员的数据
        if user.role == "admin":
            if user.username != current_user.username:
                return {
                    "success": False,
                    "error": "不能刪除管理員的數據！"
                }

        # 查找并删除符合条件的记录
        user_data = db_info.query(Information).filter(
            Information.user_id == user.id,
            Information.created_at == created_at
        ).all()

        if not user_data:
            return {
                "success": False,
                "error": f"未找到符合条件的数据: 用户名 {username}, 创建时间 {created_at}"
            }

        # 删除匹配到的所有数据
        for data in user_data:
            db_info.delete(data)
            deleted_records.append(data)

    # 提交事务
    db_info.commit()

    return {
        "success": True,
        "deleted_records": deleted_records
    }


def create_custom_by_admin(
    db_info: DBSession,
    db_user: DBSession,
    infos: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    管理员创建custom数据

    Args:
        db_info: Information数据库会话
        db_user: User数据库会话
        infos: 数据列表

    Returns:
        结果字典
    """
    created_records = []
    base_time = datetime.utcnow()

    for index, info in enumerate(infos):
        # 验证必填字段
        if not info.get("簡稱") or not info.get("音典分區") or not info.get("經緯度") or not info.get("特徵") or not info.get("值"):
            return {
                "success": False,
                "error": "有字段為空！"
            }

        # 根据 username 获取对应的 user_id
        username = info.get("username")
        user = db_user.query(User).filter(User.username == username).first()
        if not user:
            return {
                "success": False,
                "error": f"用戶 {username} 未找到"
            }

        # 自动生成 created_at（每条记录延迟50ms）
        created_at = base_time + timedelta(milliseconds=index * 50)

        # 调用 get_max_value 函数，根据值生成 maxValue
        max_value = get_max_value(info.get("值"))

        # 创建 Information 实例
        new_data = Information(
            簡稱=info.get("簡稱"),
            音典分區=info.get("音典分區"),
            經緯度=info.get("經緯度"),
            聲韻調=info.get("聲韻調"),
            特徵=info.get("特徵"),
            值=info.get("值"),
            說明=info.get("說明"),
            username=username,
            user_id=user.id,
            created_at=created_at,
            maxValue=max_value
        )

        db_info.add(new_data)
        created_records.append(new_data)

    # 提交事务
    db_info.commit()

    return {
        "success": True,
        "created_records": created_records
    }


def get_selected_custom(
    db_info: DBSession,
    db_user: DBSession,
    requests: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    根据条件查询custom数据

    Args:
        db_info: Information数据库会话
        db_user: User数据库会话
        requests: 查询请求列表，每个包含username和created_at

    Returns:
        结果字典
    """
    all_user_data = []

    for request in requests:
        username = request.get("username")
        created_at = request.get("created_at")

        # 根据用户名查找用户
        user = db_user.query(User).filter(User.username == username).first()
        if not user:
            return {
                "success": False,
                "error": f"用戶 {username} 未找到"
            }

        user_data = db_info.query(Information).filter(
            Information.user_id == user.id,
            Information.created_at == created_at
        ).all()

        if user_data:
            all_user_data.extend(user_data)

    return {
        "success": True,
        "data": all_user_data
    }
