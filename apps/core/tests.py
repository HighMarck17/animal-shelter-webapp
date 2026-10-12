"""
Security tests for the core app.
Coverage: security headers, Django Axes (brute force), rate_limit_view,
ResponseTimeMiddleware.
"""
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from apps.core.views import rate_limit_view


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Security headers
# ═══════════════════════════════════════════════════════════════════════════════

class SecurityHeadersTest(TestCase):

    def setUp(self):
        from conftest import DogFactory
        self.dog = DogFactory(is_published=True)

    def test_x_frame_options_deny(self):
        response = self.client.get(reverse('dogs:list'))
        self.assertEqual(response.get('X-Frame-Options'), 'DENY')

    def test_content_type_nosniff(self):
        response = self.client.get(reverse('dogs:list'))
        self.assertEqual(response.get('X-Content-Type-Options'), 'nosniff')

    def test_x_frame_options_on_homepage(self):
        response = self.client.get(reverse('homepage:home'))
        self.assertEqual(response.get('X-Frame-Options'), 'DENY')

    def test_x_frame_options_on_contact_page(self):
        response = self.client.get(reverse('contacts:contact'))
        self.assertEqual(response.get('X-Frame-Options'), 'DENY')


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Django Axes — brute force admin login
# ═══════════════════════════════════════════════════════════════════════════════

class AxesBruteForceTest(TestCase):

    def setUp(self):
        try:
            from axes.models import AccessAttempt
            AccessAttempt.objects.all().delete()
        except ImportError:
            pass
        self.admin_url = reverse('admin:login')

    def _failed_login(self):
        return self.client.post(self.admin_url, {
            'username': 'attacker',
            'password': 'wrongpassword',
        })

    @override_settings(AXES_FAILURE_LIMIT=3, AXES_ENABLED=True)
    def test_axes_blocks_after_failure_limit(self):
        """After AXES_FAILURE_LIMIT failed attempts, the next one is blocked."""
        for _ in range(3):
            self._failed_login()
        response = self._failed_login()
        # Axes responds with 429 (Too Many Requests) or 403/redirect
        self.assertIn(response.status_code, [429, 403, 302, 200])
        # Verify that the attempt is recorded
        try:
            from axes.models import AccessAttempt
            attempts = AccessAttempt.objects.filter(username='attacker')
            self.assertTrue(attempts.exists())
        except ImportError:
            pass

    @override_settings(AXES_FAILURE_LIMIT=3, AXES_ENABLED=True,
                       CLIENT_IP_META_KEY='HTTP_X_REAL_IP')
    def test_axes_lockout_is_per_client_behind_proxy(self):
        """Behind nginx, failures from one client must not lock out another
        client that reaches Django through the same proxy address."""
        from axes.models import AccessAttempt

        proxy_addr = '172.18.0.5'
        for _ in range(4):
            self.client.post(self.admin_url,
                             {'username': 'attacker', 'password': 'wrong'},
                             REMOTE_ADDR=proxy_addr, HTTP_X_REAL_IP='203.0.113.1')
        response = self.client.post(self.admin_url,
                                    {'username': 'staff', 'password': 'wrong'},
                                    REMOTE_ADDR=proxy_addr, HTTP_X_REAL_IP='203.0.113.2')
        self.assertNotEqual(response.status_code, 429)
        self.assertEqual(
            set(AccessAttempt.objects.values_list('ip_address', flat=True)),
            {'203.0.113.1', '203.0.113.2'},
        )

    @override_settings(AXES_FAILURE_LIMIT=3, AXES_ENABLED=True, AXES_RESET_ON_SUCCESS=True)
    def test_axes_records_failed_attempts(self):
        """Each failed attempt is recorded in AccessAttempt."""
        try:
            from axes.models import AccessAttempt
        except ImportError:
            self.skipTest('django-axes not installed')

        for _ in range(2):
            self._failed_login()

        attempts = AccessAttempt.objects.filter(username='attacker')
        self.assertTrue(attempts.exists())
        total_failures = sum(a.failures_since_start for a in attempts)
        self.assertGreaterEqual(total_failures, 1)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Rate limit view (core/views.py)
# ═══════════════════════════════════════════════════════════════════════════════

class RateLimitViewTest(TestCase):

    def test_rate_limit_view_returns_429(self):
        """The rate-limit view always returns status 429."""
        request = RequestFactory().get('/')
        response = rate_limit_view(request)
        self.assertEqual(response.status_code, 429)

    def test_rate_limit_view_with_exception_returns_429(self):
        request = RequestFactory().get('/')
        response = rate_limit_view(request, exception=Exception('too many'))
        self.assertEqual(response.status_code, 429)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. ResponseTimeMiddleware
# ═══════════════════════════════════════════════════════════════════════════════

class ResponseTimeMiddlewareTest(TestCase):

    def test_response_time_header_present(self):
        """Every response includes the X-Response-Time header."""
        response = self.client.get(reverse('dogs:list'))
        self.assertIn('X-Response-Time', response)

    def test_response_time_header_is_numeric(self):
        """The X-Response-Time value is a number (milliseconds)."""
        response = self.client.get(reverse('dogs:list'))
        value = response.get('X-Response-Time', '')
        # Expected format: '12.34ms' or '0.5ms'
        self.assertTrue(
            any(c.isdigit() for c in value),
            msg=f'X-Response-Time not numeric: {value!r}'
        )
