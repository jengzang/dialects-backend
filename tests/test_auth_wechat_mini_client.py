import unittest
from unittest.mock import Mock, patch

import requests

from app.service.auth.core import wechat_mini_client


class WechatMiniClientTests(unittest.TestCase):
    @patch("app.service.auth.core.wechat_mini_client.WECHAT_MINI_APP_ID", "")
    @patch("app.service.auth.core.wechat_mini_client.WECHAT_MINI_APP_SECRET", "")
    def test_exchange_code_for_session_rejects_missing_config(self):
        with self.assertRaisesRegex(wechat_mini_client.WechatMiniClientError, "WeChat Mini appid/appsecret 未配置"):
            wechat_mini_client.exchange_code_for_session("mini-code-missing-config")

    @patch("app.service.auth.core.wechat_mini_client.WECHAT_MINI_APP_ID", "test-app-id")
    @patch("app.service.auth.core.wechat_mini_client.WECHAT_MINI_APP_SECRET", "test-app-secret")
    @patch("app.service.auth.core.wechat_mini_client.requests.get")
    def test_exchange_code_for_session_wraps_request_exception(self, mock_get):
        mock_get.side_effect = requests.RequestException("boom")

        with self.assertRaisesRegex(wechat_mini_client.WechatMiniClientError, "WeChat Mini code2session 请求异常"):
            wechat_mini_client.exchange_code_for_session("mini-code-request-error")

    @patch("app.service.auth.core.wechat_mini_client.WECHAT_MINI_APP_ID", "test-app-id")
    @patch("app.service.auth.core.wechat_mini_client.WECHAT_MINI_APP_SECRET", "test-app-secret")
    @patch("app.service.auth.core.wechat_mini_client.requests.get")
    def test_exchange_code_for_session_rejects_non_success_status(self, mock_get):
        response = Mock(status_code=500)
        mock_get.return_value = response

        with self.assertRaisesRegex(wechat_mini_client.WechatMiniClientError, "WeChat Mini code2session 请求失败"):
            wechat_mini_client.exchange_code_for_session("mini-code-http-error")

    @patch("app.service.auth.core.wechat_mini_client.WECHAT_MINI_APP_ID", "test-app-id")
    @patch("app.service.auth.core.wechat_mini_client.WECHAT_MINI_APP_SECRET", "test-app-secret")
    @patch("app.service.auth.core.wechat_mini_client.requests.get")
    def test_exchange_code_for_session_rejects_errcode_payload(self, mock_get):
        response = Mock(status_code=200)
        response.json.return_value = {"errcode": 40029, "errmsg": "invalid code"}
        mock_get.return_value = response

        with self.assertRaisesRegex(wechat_mini_client.WechatMiniClientError, "WeChat Mini code2session 失败: invalid code"):
            wechat_mini_client.exchange_code_for_session("mini-code-errcode")

    @patch("app.service.auth.core.wechat_mini_client.WECHAT_MINI_APP_ID", "test-app-id")
    @patch("app.service.auth.core.wechat_mini_client.WECHAT_MINI_APP_SECRET", "test-app-secret")
    @patch("app.service.auth.core.wechat_mini_client.requests.get")
    def test_exchange_code_for_session_rejects_missing_openid(self, mock_get):
        response = Mock(status_code=200)
        response.json.return_value = {"session_key": "abc"}
        mock_get.return_value = response

        with self.assertRaisesRegex(wechat_mini_client.WechatMiniClientError, "WeChat Mini code2session 缺少 openid"):
            wechat_mini_client.exchange_code_for_session("mini-code-missing-openid")

    @patch("app.service.auth.core.wechat_mini_client.WECHAT_MINI_APP_ID", "test-app-id")
    @patch("app.service.auth.core.wechat_mini_client.WECHAT_MINI_APP_SECRET", "test-app-secret")
    @patch("app.service.auth.core.wechat_mini_client.requests.get")
    def test_exchange_code_for_session_falls_back_unionid_to_openid(self, mock_get):
        response = Mock(status_code=200)
        response.json.return_value = {
            "openid": "mini-openid-fallback",
            "session_key": "session-key-123",
        }
        mock_get.return_value = response

        payload = wechat_mini_client.exchange_code_for_session("mini-code-success")

        self.assertEqual(payload["openid"], "mini-openid-fallback")
        self.assertEqual(payload["unionid"], "mini-openid-fallback")
        self.assertEqual(payload["session_key"], "session-key-123")
        mock_get.assert_called_once()
        self.assertEqual(mock_get.call_args.kwargs["timeout"], 20)
        self.assertEqual(mock_get.call_args.kwargs["params"]["js_code"], "mini-code-success")


if __name__ == "__main__":
    unittest.main()
