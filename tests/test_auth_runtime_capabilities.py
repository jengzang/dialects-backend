import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from app.lifecycle import startup


class AuthRuntimeCapabilityTests(unittest.TestCase):
    def test_print_auth_runtime_capabilities_reports_non_web_degradation(self):
        buffer = io.StringIO()
        with patch.object(startup, "_RUN_TYPE", "MINE", create=True), \
             patch.object(startup, "RESEND_API_KEY", "resend-key", create=True), \
             patch.object(startup, "RESEND_FROM_EMAIL", "", create=True), \
             patch.object(startup, "SMTP_HOST", None, create=True), \
             patch.object(startup, "SMTP_USERNAME", None, create=True), \
             patch.object(startup, "SMTP_PASSWORD", None, create=True):
            with redirect_stdout(buffer):
                startup.print_auth_runtime_capabilities()

        output = buffer.getvalue()
        self.assertIn("[AUTH] runtime_mode=MINE", output)
        self.assertIn("[AUTH] redis_enabled=false", output)
        self.assertIn("[AUTH] auth_session_store=database", output)
        self.assertIn("[AUTH] auth_user_cache=disabled", output)
        self.assertIn("[AUTH] auth_rate_limit=disabled", output)
        self.assertIn("[AUTH] auth_permission_cache=disabled", output)
        self.assertIn("[AUTH] email_delivery=console_fallback", output)


if __name__ == "__main__":
    unittest.main()
