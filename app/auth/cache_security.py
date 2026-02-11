"""
Redis缓存签名机制 - 防止缓存数据篡改
使用HMAC-SHA256对缓存数据进行签名和验证
"""
import hmac
import hashlib
import json
from typing import Optional
from common.config import get_secret_key


def sign_user_data(user_dict: dict) -> str:
    """
    使用HMAC-SHA256签名用户数据
    返回格式: {"data": {...}, "signature": "hex", "version": 1}

    Args:
        user_dict: 用户数据字典

    Returns:
        签名后的JSON字符串
    """
    # 规范化JSON（确保相同数据生成相同签名）
    canonical = json.dumps(user_dict, sort_keys=True)

    # 计算HMAC-SHA256签名
    signature = hmac.new(
        get_secret_key().encode(),
        canonical.encode(),
        hashlib.sha256
    ).hexdigest()

    # 包装数据和签名
    return json.dumps({
        "data": user_dict,
        "signature": signature,
        "version": 1
    })


def verify_user_data(signed_json: str) -> Optional[dict]:
    """
    验证并提取用户数据

    Args:
        signed_json: 签名后的JSON字符串

    Returns:
        user_dict（有效时）或 None（被篡改时）
    """
    try:
        wrapper = json.loads(signed_json)
        user_dict = wrapper["data"]
        signature = wrapper["signature"]

        # 重新计算签名
        canonical = json.dumps(user_dict, sort_keys=True)
        expected_sig = hmac.new(
            SECRET_KEY.encode(),
            canonical.encode(),
            hashlib.sha256
        ).hexdigest()

        # 恒定时间比较（防止时序攻击）
        if not hmac.compare_digest(signature, expected_sig):
            print("[SECURITY ALERT] Cache signature mismatch - possible tampering detected!")
            return None

        return user_dict

    except (KeyError, json.JSONDecodeError, TypeError) as e:
        print(f"[SECURITY] Cache verification failed: {e}")
        return None
