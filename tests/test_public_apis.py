import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class _Resp:
    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")

    def json(self):
        return self._json_data


class PublicApisTests(unittest.TestCase):
    def test_ipinfo_invalid_query(self):
        from src.utils.public_apis import ipinfo_lookup

        out = ipinfo_lookup("not a domain")
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"], "invalid_query")

    @patch("httpx.get")
    def test_ipinfo_success(self, mget):
        from src.utils.public_apis import ipinfo_lookup

        mget.return_value = _Resp({"ip": "1.2.3.4", "org": "AS123"})
        out = ipinfo_lookup("1.2.3.4")
        self.assertTrue(out["ok"])
        self.assertEqual(out["data"]["ip"], "1.2.3.4")

    def test_shodan_invalid_ip(self):
        from src.utils.public_apis import shodan_internetdb_lookup

        out = shodan_internetdb_lookup("999.999.1.1")
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"], "invalid_ip")

    @patch("httpx.get")
    def test_shodan_internetdb_success(self, mget):
        from src.utils.public_apis import shodan_internetdb_lookup

        mget.return_value = _Resp({"ip": "1.2.3.4", "ports": [22, 80]})
        out = shodan_internetdb_lookup("1.2.3.4")
        self.assertTrue(out["ok"])
        self.assertEqual(out["data"]["ports"], [22, 80])

    def test_urlhaus_invalid_kind(self):
        from src.utils.public_apis import urlhaus_lookup

        out = urlhaus_lookup("ip", "1.2.3.4")
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"], "invalid_kind")

    @patch("httpx.post")
    def test_urlhaus_host_success(self, mpost):
        from src.utils.public_apis import urlhaus_lookup

        mpost.return_value = _Resp({"query_status": "ok", "host": "example.com"})
        out = urlhaus_lookup("host", "example.com")
        self.assertTrue(out["ok"])
        self.assertEqual(out["data"]["query_status"], "ok")


if __name__ == "__main__":
    unittest.main()
