import unittest
import warnings

from pa_cli import _http


class ProxySecurityTests(unittest.TestCase):
    PROXY = "http://alice:super-secret@proxy.example.test:8080"

    def test_remote_proxy_rejection_redacts_credentials(self):
        with self.assertRaises(RuntimeError) as caught:
            _http.validate_proxy_security(self.PROXY, allow_remote=False)

        message = str(caught.exception)
        self.assertNotIn("alice", message)
        self.assertNotIn("super-secret", message)
        self.assertIn("proxy.example.test", message)

    def test_local_proxy_warning_redacts_credentials(self):
        proxy = "http://alice:super-secret@127.0.0.1:7890"
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            _http.validate_proxy_security(proxy)

        message = str(caught[0].message)
        self.assertNotIn("alice", message)
        self.assertNotIn("super-secret", message)
        self.assertIn("127.0.0.1", message)


if __name__ == "__main__":
    unittest.main()
