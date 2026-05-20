import requests

from app.common.wechat_mini_config import (
    WECHAT_MINI_APP_ID,
    WECHAT_MINI_APP_SECRET,
    WECHAT_MINI_CODE2SESSION_URL,
)


class WechatMiniClientError(ValueError):
    pass


def exchange_code_for_session(code: str) -> dict:
    if not WECHAT_MINI_APP_ID or not WECHAT_MINI_APP_SECRET:
        raise WechatMiniClientError("WeChat Mini appid/appsecret 未配置")

    response = None
    try:
        response = requests.get(
            WECHAT_MINI_CODE2SESSION_URL,
            params={
                "appid": WECHAT_MINI_APP_ID,
                "secret": WECHAT_MINI_APP_SECRET,
                "js_code": code,
                "grant_type": "authorization_code",
            },
            timeout=20,
        )
    except requests.RequestException as exc:
        raise WechatMiniClientError("WeChat Mini code2session 请求异常") from exc
    if response.status_code >= 300:
        raise WechatMiniClientError("WeChat Mini code2session 请求失败")

    data = response.json()
    errcode = data.get("errcode")
    if errcode not in (None, 0, "0"):
        raise WechatMiniClientError(f"WeChat Mini code2session 失败: {data.get('errmsg') or errcode}")

    openid = str(data.get("openid") or "").strip()
    if not openid:
        raise WechatMiniClientError("WeChat Mini code2session 缺少 openid")

    unionid = str(data.get("unionid") or "").strip() or openid
    session_key = str(data.get("session_key") or "").strip() or None
    return {
        **data,
        "openid": openid,
        "unionid": unionid,
        "session_key": session_key,
    }
