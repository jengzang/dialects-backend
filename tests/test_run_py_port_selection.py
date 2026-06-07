import socket
import unittest
from unittest.mock import patch

from run import find_available_port, build_runtime_urls


class RunPyPortSelectionTests(unittest.TestCase):
    def test_find_available_port_returns_start_port_when_free(self) -> None:
        with patch("run.is_port_available", return_value=True) as mock_available:
            port = find_available_port(5000, host="127.0.0.1", max_tries=3)

        self.assertEqual(port, 5000)
        mock_available.assert_called_once_with("127.0.0.1", 5000)

    def test_find_available_port_retries_upward_when_busy(self) -> None:
        seen = []

        def fake_available(host, port):
            seen.append((host, port))
            return port == 5002

        with patch("run.is_port_available", side_effect=fake_available):
            port = find_available_port(5000, host="0.0.0.0", max_tries=5)

        self.assertEqual(port, 5002)
        self.assertEqual(seen, [("0.0.0.0", 5000), ("0.0.0.0", 5001), ("0.0.0.0", 5002)])

    def test_find_available_port_raises_after_max_tries(self) -> None:
        with patch("run.is_port_available", return_value=False):
            with self.assertRaises(RuntimeError) as ctx:
                find_available_port(5000, host="127.0.0.1", max_tries=2)

        self.assertIn("5000-5001", str(ctx.exception))

    def test_is_port_available_detects_bound_port(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        port = sock.getsockname()[1]
        try:
            self.assertFalse(find_available_port(port, host="127.0.0.1", max_tries=1) == port)
        except RuntimeError:
            pass
        finally:
            sock.close()

    def test_build_runtime_urls_uses_final_port(self) -> None:
        urls = build_runtime_urls("MINE", 5002)

        self.assertEqual(urls["local_url"], "http://127.0.0.1:5002")
        self.assertEqual(urls["browser_url"], "http://127.0.0.1:5002")


if __name__ == "__main__":
    unittest.main()
