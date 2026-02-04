from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import HTTPException, APIRouter, Query, Depends

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.custom.database import SessionLocal as SessionLocal_info
from app.auth.database import SessionLocal as SessionLocal_user
from app.custom.models import Information
from app.custom.write_submit import get_max_value
from app.schemas.admin import EditRequest, InformationBase

router = APIRouter()
@router.delete("/delete", response_model=List[InformationBase])
async def delete_custom_by_admin(requests: List[EditRequest],
                                 current_user: Optional[User] = Depends(get_current_user),):
    session_info = SessionLocal_info()
    session_user = SessionLocal_user()

    try:
        deleted_records = []

        for request in requests:
            # 查找用户
            user = session_user.query(User).filter(User.username == request.username).first()
            if not user:
                raise HTTPException(status_code=404, detail=f"用戶 {request.username} 未找到")
            if user.role == "admin":
                if user.username == current_user.username:
                    # 管理員可以刪除自己的數據
                    pass
                else:
                    # 管理員不能刪除其他管理員的數據
                    raise HTTPException(status_code=400, detail="不能刪除管理員的數據！")

            # 查找并删除符合条件的记录
            user_data = session_info.query(Information).filter(
                Information.user_id == user.id,
                Information.created_at == request.created_at
            ).all()

            if not user_data:
                raise HTTPException(status_code=404,
                                    detail=f"未找到符合条件的数据: 用户名 {request.username}, 创建时间 {request.created_at}")

            # 删除匹配到的所有数据
            for data in user_data:
                session_info.delete(data)
                deleted_records.append(data)

        # 提交事务
        session_info.commit()

        return deleted_records
    except HTTPException:
        raise   # [OK] 让 HTTPException 保持原样传递
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        session_info.close()
        session_user.close()


# 确保从数据库获取对象时，避免 Detached 错误
@router.post("/create", response_model=List[InformationBase])
async def create_custom_by_admin(infos: List[InformationBase]):
    session_info = SessionLocal_info()
    session_user = SessionLocal_user()

    try:
        created_records = []
        # 当前时间，用于计算微小的时间差
        base_time = datetime.utcnow()

        for index, info in enumerate(infos):
            if not info.簡稱 or not info.音典分區 or not info.經緯度 or not info.特徵 or not info.值 :
                raise HTTPException(status_code=400, detail="有字段為空！")
            # 根据 username 获取对应的 user_id
            user = session_user.query(User).filter(User.username == info.username).first()
            if not user:
                raise HTTPException(status_code=404, detail=f"用戶 {info.username} 未找到")

            # 自动生成 created_at
            # created_at = datetime.utcnow()
            created_at = base_time + timedelta(milliseconds=index * 50)  # 延迟 0.1秒
            # 调用 get_max_value 函数，根据值生成 maxValue
            max_value = get_max_value(info.值)

            # 创建 Information 实例
            new_data = Information(
                簡稱=info.簡稱,
                音典分區=info.音典分區,
                經緯度=info.經緯度,
                聲韻調=info.聲韻調,
                特徵=info.特徵,
                值=info.值,
                說明=info.說明,
                username=info.username,
                user_id=user.id,  # 填充 user_id
                created_at=created_at,  # 自动填充 created_at
                maxValue=max_value  # 通过 get_max_value 生成 maxValue
            )

            session_info.add(new_data)
            created_records.append(new_data)

        # 提交事务，确保数据被保存并且对象没有分离
        session_info.commit()

        # 提交后将创建的记录转换为 Pydantic 模型返回
        return [InformationBase.from_orm(record) for record in created_records]

    except Exception as e:
        session_info.rollback()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
    finally:
        session_info.close()
        session_user.close()

@router.post("/selected", response_model=List[InformationBase])
async def selected_custom(requests: List[EditRequest]):
    session_info = SessionLocal_info()
    session_user = SessionLocal_user()

    try:
        all_user_data = []
        for request in requests:
            # 根据用户名查找用户
            user = session_user.query(User).filter(User.username == request.username).first()
            if not user:
                raise HTTPException(status_code=404, detail=f"用戶 {request.username} 未找到")

            user_data = session_info.query(Information).filter(
                Information.user_id == user.id,
                Information.created_at == request.created_at
            ).all()
            if user_data:  # 如果有符合条件的数据，则添加到结果列表中
                all_user_data.extend(user_data)

        # 返回所有符合条件的数据
        return all_user_data

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
    finally:
        session_info.close()
        session_user.close()