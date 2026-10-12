"""
Tests for apps/core/client_ip.py: which request value is trusted as client IP.
"""
from django.test import RequestFactory, SimpleTestCase, override_settings

from apps.core.client_ip import get_client_ip


class GetClientIpTest(SimpleTestCase):

    def _request(self, **meta):
        return RequestFactory().get('/', **meta)

    def test_default_uses_remote_addr(self):
        request = self._request(REMOTE_ADDR='5.5.5.5')
        self.assertEqual(get_client_ip(request), '5.5.5.5')

    def test_default_ignores_client_supplied_headers(self):
        """Without a configured proxy header, nothing the client sends is trusted."""
        request = self._request(REMOTE_ADDR='5.5.5.5',
                                HTTP_X_FORWARDED_FOR='1.2.3.4',
                                HTTP_X_REAL_IP='6.6.6.6')
        self.assertEqual(get_client_ip(request), '5.5.5.5')

    @override_settings(CLIENT_IP_META_KEY='HTTP_X_REAL_IP')
    def test_proxy_header_used_when_configured(self):
        request = self._request(REMOTE_ADDR='172.18.0.5', HTTP_X_REAL_IP='203.0.113.7')
        self.assertEqual(get_client_ip(request), '203.0.113.7')

    @override_settings(CLIENT_IP_META_KEY='HTTP_X_REAL_IP')
    def test_x_forwarded_for_never_used(self):
        request = self._request(REMOTE_ADDR='172.18.0.5', HTTP_X_REAL_IP='203.0.113.7',
                                HTTP_X_FORWARDED_FOR='1.2.3.4, 203.0.113.7')
        self.assertEqual(get_client_ip(request), '203.0.113.7')

    @override_settings(CLIENT_IP_META_KEY='HTTP_X_REAL_IP')
    def test_missing_proxy_header_falls_back_to_remote_addr(self):
        request = self._request(REMOTE_ADDR='127.0.0.1')
        self.assertEqual(get_client_ip(request), '127.0.0.1')

    @override_settings(CLIENT_IP_META_KEY='HTTP_X_REAL_IP')
    def test_malformed_proxy_header_falls_back_to_remote_addr(self):
        request = self._request(REMOTE_ADDR='172.18.0.5', HTTP_X_REAL_IP='not-an-ip')
        self.assertEqual(get_client_ip(request), '172.18.0.5')
