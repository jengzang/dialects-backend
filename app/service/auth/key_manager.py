"""SECRET_KEY管理模块"""
import secrets
from datetime import datetime, timedelta
from typing import List
from app.service.auth.database import SessionLocal
from app.service.auth.models import SecretKey


def get_current_secret_key() -> str:
    """获取当前有效的SECRET_KEY（从数据库）"""
    db = SessionLocal()

    try:
        # 查找当前活跃的密钥
        key = db.query(SecretKey).filter(
            SecretKey.active == True,
            SecretKey.expires_at > datetime.utcnow()
        ).order_by(SecretKey.created_at.desc()).first()

        if not key:
            # 如果没有密钥，生成新的（首次启动）
            print("[KEY-MANAGER] No active key found, generating new key...")
            key = _generate_new_secret_key(db)

        return key.key_value
    finally:
        db.close()


def get_all_valid_keys() -> List[str]:
    """获取所有有效密钥（包括未过期的旧密钥，用于JWT解码）"""
    db = SessionLocal()

    try:
        keys = db.query(SecretKey).filter(
            SecretKey.expires_at > datetime.utcnow()
        ).order_by(SecretKey.created_at.desc()).all()

        return [k.key_value for k in keys]
    finally:
        db.close()


def _generate_new_secret_key(db) -> SecretKey:
    """生成新的SECRET_KEY（内部函数）"""

    print(f"[KEY-MANAGER] 🔑 Generating new SECRET_KEY...")
    new_key = secrets.token_urlsafe(64)
    print(f"[KEY-MANAGER] Generated key (first 20 chars): {new_key[:20]}...")

    try:
        key_obj = SecretKey(
            key_value=new_key,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=365),  # 1年后过期
            active=True
        )
        print(f"[KEY-MANAGER] Created SecretKey object, adding to database...")
        db.add(key_obj)

        print(f"[KEY-MANAGER] Committing to database...")
        db.commit()

        print(f"[KEY-MANAGER] Refreshing object...")
        db.refresh(key_obj)

        print(f"[KEY-MANAGER] ✅ SECRET_KEY saved with ID: {key_obj.id}")
        return key_obj
    except Exception as e:
        print(f"[KEY-MANAGER] ❌ Failed to save SECRET_KEY: {e}")
        db.rollback()
        raise


def rotate_secret_key(reason: str = "manual") -> str:
    """
    轮换SECRET_KEY（手动命令）
    返回: 新密钥的值
    """
    from app.common.config import ACCESS_TOKEN_EXPIRE_MINUTES

    db = SessionLocal()

    try:
        # 1. 将当前密钥标记为旧密钥（保留30分钟供access token过期）
        current_key = db.query(SecretKey).filter(SecretKey.active == True).first()
        if current_key:
            current_key.active = False
            current_key.expires_at = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
            current_key.revoked_reason = reason
            print(f"[KEY-MANAGER] Marked old key as inactive, expires in {ACCESS_TOKEN_EXPIRE_MINUTES} minutes")

        # 2. 生成新密钥
        new_key = _generate_new_secret_key(db)

        return new_key.key_value
    finally:
        db.close()


def cleanup_expired_keys():
    """
    清理过期的SECRET_KEY
    运行频率: 每天凌晨1:00 AM
    """
    db = SessionLocal()

    try:
        now = datetime.utcnow()

        deleted_count = db.query(SecretKey).filter(
            SecretKey.expires_at < now
        ).delete(synchronize_session=False)

        db.commit()
        print(f"[KEY-MANAGER] Deleted {deleted_count} expired keys")

    except Exception as e:
        print(f"[KEY-MANAGER] Cleanup failed: {e}")
        db.rollback()
    finally:
        db.close()
