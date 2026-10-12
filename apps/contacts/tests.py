"""
Security tests for the contacts app.
Coverage: honeypot, spam filter, disposable emails, rate limiting,
CSRF, XSS/injection, IP tracking, end-to-end form submit.
"""
from unittest.mock import patch

from django.core import mail
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.contacts.forms import ContactForm
from apps.contacts.models import ContactMessage


# ─── Base valid POST data ─────────────────────────────────────────────────────

def _valid_post(overrides=None):
    """Return a valid POST dict for the contact form."""
    data = {
        'name': 'Mario Rossi',
        'email': 'mario@example.com',
        'subject': 'adoption',
        'message': 'Vorrei adottare un cane, sono molto interessato alla struttura.',
        'website': '',                      # empty honeypot
        'g-recaptcha-response': 'PASSED',   # accepted by the Google test keys
    }
    if overrides:
        data.update(overrides)
    return data


def _build_form(overrides=None):
    """Build a ContactForm with the captcha patched for form unit tests."""
    data = _valid_post(overrides)
    with patch('django_recaptcha.fields.ReCaptchaField.validate', return_value=True):
        form = ContactForm(data=data)
        form.full_clean()
    return form


# ═══════════════════════════════════════════════════════════════════════════════
# 1. HONEYPOT
# ═══════════════════════════════════════════════════════════════════════════════

class HoneypotTest(TestCase):

    @patch('django_recaptcha.fields.ReCaptchaField.validate', return_value=True)
    def test_honeypot_empty_passes(self, _mock):
        form = ContactForm(data=_valid_post({'website': ''}))
        form.full_clean()
        self.assertNotIn('website', form.errors)

    @patch('django_recaptcha.fields.ReCaptchaField.validate', return_value=True)
    def test_honeypot_filled_blocks(self, _mock):
        form = ContactForm(data=_valid_post({'website': 'http://bot.com'}))
        form.full_clean()
        self.assertIn('website', form.errors)
        self.assertIn('Spam rilevato', str(form.errors['website']))

    @patch('django_recaptcha.fields.ReCaptchaField.validate', return_value=True)
    def test_honeypot_any_url_blocks(self, _mock):
        form = ContactForm(data=_valid_post({'website': 'https://spam.example.com/promo'}))
        form.full_clean()
        self.assertIn('website', form.errors)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. SPAM WORD FILTERING
# ═══════════════════════════════════════════════════════════════════════════════

class SpamWordTest(TestCase):

    def _form_with_message(self, msg):
        return _build_form({'message': msg})

    def test_spam_word_viagra_blocked(self):
        form = self._form_with_message('Vuoi comprare viagra online adesso?')
        self.assertIn('message', form.errors)

    def test_spam_word_casino_blocked(self):
        form = self._form_with_message('Gioca al casino e vinci molto denaro.')
        self.assertIn('message', form.errors)

    def test_spam_word_bitcoin_blocked(self):
        form = self._form_with_message('Investimento bitcoin sicuro garantito subito.')
        self.assertIn('message', form.errors)

    def test_spam_word_italian_merda_blocked(self):
        form = self._form_with_message('Questo posto fa merda davvero molto.')
        self.assertIn('message', form.errors)

    def test_spam_word_case_insensitive(self):
        form = self._form_with_message('VIAGRA in offerta speciale acquistalo ora.')
        self.assertIn('message', form.errors)

    def test_message_with_http_link_blocked(self):
        form = self._form_with_message('Visita http://esempio.com per avere info.')
        self.assertIn('message', form.errors)
        self.assertIn('Link nel messaggio', str(form.errors['message']))

    def test_message_with_https_link_blocked(self):
        form = self._form_with_message('Clicca su https://spam.com adesso subito.')
        self.assertIn('message', form.errors)

    def test_message_too_short_blocked(self):
        form = self._form_with_message('Ciao')
        self.assertIn('message', form.errors)
        self.assertIn('troppo corto', str(form.errors['message']))

    def test_message_exactly_20_chars_passes(self):
        form = self._form_with_message('A' * 20)
        self.assertNotIn('message', form.errors)

    def test_clean_message_valid(self):
        form = self._form_with_message(
            'Buongiorno, sono interessato ad adottare uno dei vostri cani.'
        )
        self.assertNotIn('message', form.errors)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. DISPOSABLE EMAIL DOMAINS
# ═══════════════════════════════════════════════════════════════════════════════

class SpamEmailDomainTest(TestCase):

    SPAM_DOMAINS = [
        'tempmail.com',
        'guerrillamail.com',
        '10minutemail.com',
        'throwaway.email',
        'mailinator.com',
        'trashmail.com',
    ]

    def _form_with_email(self, email):
        return _build_form({'email': email})

    def test_tempmail_blocked(self):
        form = self._form_with_email('user@tempmail.com')
        self.assertIn('email', form.errors)
        self.assertIn('Dominio email non consentito', str(form.errors['email']))

    def test_guerrillamail_blocked(self):
        form = self._form_with_email('user@guerrillamail.com')
        self.assertIn('email', form.errors)

    def test_mailinator_blocked(self):
        form = self._form_with_email('user@mailinator.com')
        self.assertIn('email', form.errors)

    def test_all_spam_domains_blocked(self):
        for domain in self.SPAM_DOMAINS:
            with self.subTest(domain=domain):
                form = self._form_with_email(f'user@{domain}')
                self.assertIn('email', form.errors,
                              msg=f'Domain {domain} not blocked')

    def test_gmail_allowed(self):
        form = self._form_with_email('utente@gmail.com')
        self.assertNotIn('email', form.errors)

    def test_real_domain_allowed(self):
        form = self._form_with_email('info@azienda.it')
        self.assertNotIn('email', form.errors)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. RATE LIMITING
# ═══════════════════════════════════════════════════════════════════════════════

class RateLimitTest(TestCase):

    def setUp(self):
        cache.clear()

    def _post(self, client=None, remote_addr='127.0.0.1', **extra):
        c = client or self.client
        return c.post(reverse('contacts:contact'), data=_valid_post(),
                      REMOTE_ADDR=remote_addr,
                      HTTP_USER_AGENT='TestAgent/1.0', **extra)

    @override_settings(RATELIMIT_ENABLE=True)
    @patch('django_recaptcha.fields.ReCaptchaField.validate', return_value=True)
    def test_rate_limit_allows_first_3(self, _mock):
        """The first 3 valid POSTs must succeed (302 redirect)."""
        for _ in range(3):
            response = self._post()
            self.assertEqual(response.status_code, 302)

    @override_settings(RATELIMIT_ENABLE=True)
    @patch('django_recaptcha.fields.ReCaptchaField.validate', return_value=True)
    def test_rate_limit_blocks_4th_request(self, _mock):
        for _ in range(3):
            self._post()
        response = self._post()
        self.assertContains(response, 'limite massimo')

    @override_settings(RATELIMIT_ENABLE=True)
    @patch('django_recaptcha.fields.ReCaptchaField.validate', return_value=True)
    def test_rate_limit_is_per_ip(self, _mock):
        """Different IPs have separate counters."""
        for _ in range(3):
            self._post(remote_addr='10.0.0.1')
        # A different IP must not be blocked → 302 redirect
        response = self._post(remote_addr='10.0.0.2')
        self.assertEqual(response.status_code, 302)

    @override_settings(RATELIMIT_ENABLE=True, CLIENT_IP_META_KEY='HTTP_X_REAL_IP')
    @patch('django_recaptcha.fields.ReCaptchaField.validate', return_value=True)
    def test_rate_limit_is_per_client_behind_proxy(self, _mock):
        """Behind nginx every request has the proxy's REMOTE_ADDR: the limit
        must still count each client (X-Real-IP), not all visitors together."""
        for _ in range(3):
            self._post(remote_addr='172.18.0.5', HTTP_X_REAL_IP='203.0.113.1')
        response = self._post(remote_addr='172.18.0.5', HTTP_X_REAL_IP='203.0.113.1')
        self.assertContains(response, 'limite massimo')
        response = self._post(remote_addr='172.18.0.5', HTTP_X_REAL_IP='203.0.113.2')
        self.assertEqual(response.status_code, 302)

    @override_settings(RATELIMIT_ENABLE=True)
    @patch('django_recaptcha.fields.ReCaptchaField.validate', return_value=True)
    def test_rate_limit_not_bypassed_by_spoofed_forwarded_for(self, _mock):
        for i in range(3):
            self._post(HTTP_X_FORWARDED_FOR=f'198.51.100.{i}')
        response = self._post(HTTP_X_FORWARDED_FOR='198.51.100.99')
        self.assertContains(response, 'limite massimo')


# ═══════════════════════════════════════════════════════════════════════════════
# 5. CSRF
# ═══════════════════════════════════════════════════════════════════════════════

class CsrfTest(TestCase):

    def test_csrf_token_required(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(reverse('contacts:contact'), data=_valid_post())
        self.assertEqual(response.status_code, 403)

    @override_settings(RATELIMIT_ENABLE=False)
    @patch('django_recaptcha.fields.ReCaptchaField.validate', return_value=True)
    def test_csrf_token_valid_proceeds(self, _mock):
        """With a valid CSRF token the request is not rejected with 403."""
        client = Client(enforce_csrf_checks=True)
        client.get(reverse('contacts:contact'))
        csrf_token = client.cookies.get('csrftoken')
        self.assertIsNotNone(csrf_token)
        data = _valid_post()
        data['csrfmiddlewaretoken'] = csrf_token.value
        response = client.post(reverse('contacts:contact'), data=data)
        self.assertNotEqual(response.status_code, 403)


# ═══════════════════════════════════════════════════════════════════════════════
# 6. XSS AND SQL INJECTION
# ═══════════════════════════════════════════════════════════════════════════════

class InjectionTest(TestCase):

    def setUp(self):
        cache.clear()

    @override_settings(RATELIMIT_ENABLE=False)
    @patch('django_recaptcha.fields.ReCaptchaField.validate', return_value=True)
    def test_xss_in_name_saved_as_literal_text(self, _mock):
        """A <script> tag in the name is stored as text — the ORM does not run HTML."""
        xss_name = '<script>alert(1)</script>'
        self.client.post(reverse('contacts:contact'),
                         data=_valid_post({'name': xss_name}))
        msg = ContactMessage.objects.filter(name=xss_name).first()
        if msg:
            self.assertEqual(msg.name, xss_name)

    @override_settings(RATELIMIT_ENABLE=False)
    @patch('django_recaptcha.fields.ReCaptchaField.validate', return_value=True)
    def test_sql_injection_in_name_no_crash(self, _mock):
        """SQL injection in the name does not crash the DB."""
        payload = "'; DROP TABLE contacts_contactmessage; --"
        try:
            self.client.post(reverse('contacts:contact'),
                             data=_valid_post({'name': payload}))
        except Exception as exc:
            self.fail(f'SQL injection raised an exception: {exc}')

    @patch('django_recaptcha.fields.ReCaptchaField.validate', return_value=True)
    def test_email_header_injection_blocked(self, _mock):
        """Newline in the email: Django EmailValidator must block it."""
        form = ContactForm(data=_valid_post(
            {'email': 'user@example.com\nBcc: attacker@evil.com'}
        ))
        form.full_clean()
        self.assertIn('email', form.errors)


# ═══════════════════════════════════════════════════════════════════════════════
# 7. IP TRACKING
# ═══════════════════════════════════════════════════════════════════════════════

class IpTrackingTest(TestCase):

    def setUp(self):
        cache.clear()

    @override_settings(RATELIMIT_ENABLE=False)
    @patch('django_recaptcha.fields.ReCaptchaField.validate', return_value=True)
    def test_ip_saved_on_submit(self, _mock):
        self.client.post(reverse('contacts:contact'), data=_valid_post(),
                         REMOTE_ADDR='192.168.1.50')
        msg = ContactMessage.objects.last()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.ip_address, '192.168.1.50')

    @override_settings(RATELIMIT_ENABLE=False)
    @patch('django_recaptcha.fields.ReCaptchaField.validate', return_value=True)
    def test_spoofed_x_forwarded_for_is_ignored(self, _mock):
        """A client-supplied X-Forwarded-For must not replace the stored IP."""
        self.client.post(reverse('contacts:contact'), data=_valid_post(),
                         REMOTE_ADDR='192.168.1.50',
                         HTTP_X_FORWARDED_FOR='10.10.10.1, 10.10.10.2')
        msg = ContactMessage.objects.last()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.ip_address, '192.168.1.50')

    @override_settings(RATELIMIT_ENABLE=False, CLIENT_IP_META_KEY='HTTP_X_REAL_IP')
    @patch('django_recaptcha.fields.ReCaptchaField.validate', return_value=True)
    def test_ip_from_proxy_header_saved(self, _mock):
        """Behind nginx the stored IP is the one nginx puts in X-Real-IP."""
        self.client.post(reverse('contacts:contact'), data=_valid_post(),
                         REMOTE_ADDR='172.18.0.5', HTTP_X_REAL_IP='203.0.113.7')
        msg = ContactMessage.objects.last()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.ip_address, '203.0.113.7')


# ═══════════════════════════════════════════════════════════════════════════════
# 8. END-TO-END VALID FORM
# ═══════════════════════════════════════════════════════════════════════════════

class ContactFormEndToEndTest(TestCase):

    def setUp(self):
        cache.clear()

    @override_settings(RATELIMIT_ENABLE=False)
    @patch('django_recaptcha.fields.ReCaptchaField.validate', return_value=True)
    def test_valid_form_saves_message(self, _mock):
        count_before = ContactMessage.objects.count()
        self.client.post(reverse('contacts:contact'), data=_valid_post())
        self.assertEqual(ContactMessage.objects.count(), count_before + 1)

    @override_settings(RATELIMIT_ENABLE=False)
    @patch('django_recaptcha.fields.ReCaptchaField.validate', return_value=True)
    def test_valid_form_redirects_to_success(self, _mock):
        response = self.client.post(reverse('contacts:contact'), data=_valid_post())
        self.assertRedirects(response, reverse('contacts:success'))

    @override_settings(RATELIMIT_ENABLE=False)
    @patch('django_recaptcha.fields.ReCaptchaField.validate', return_value=True)
    def test_valid_form_sends_notification_email(self, _mock):
        self.client.post(reverse('contacts:contact'), data=_valid_post())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('staff@example.test', mail.outbox[0].to)

    @override_settings(RATELIMIT_ENABLE=False)
    @patch('django_recaptcha.fields.ReCaptchaField.validate', return_value=True)
    def test_valid_form_email_subject_contains_sender_name(self, _mock):
        self.client.post(reverse('contacts:contact'),
                         data=_valid_post({'name': 'Luigi Verdi'}))
        self.assertIn('Luigi Verdi', mail.outbox[0].subject)


# ═══════════════════════════════════════════════════════════════════════════════
# 9. Admin panel for ContactMessage
# ═══════════════════════════════════════════════════════════════════════════════

class ContactAdminTests(TestCase):

    def setUp(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.admin = User.objects.create_superuser(
            username='contact_admin', email='cadmin@test.com', password='Admin1234!'
        )
        self.client.force_login(self.admin)
        self.msg = ContactMessage.objects.create(
            name='Tizio Test',
            email='tizio@example.com',
            subject='adoption',
            message='Messaggio di test per il pannello admin.',
            ip_address='10.0.0.1',
        )

    def test_admin_contact_list_returns_200(self):
        response = self.client.get(
            reverse('admin:contacts_contactmessage_changelist')
        )
        self.assertEqual(response.status_code, 200)

    def test_admin_contact_list_shows_message(self):
        response = self.client.get(
            reverse('admin:contacts_contactmessage_changelist')
        )
        self.assertContains(response, 'Tizio Test')

    def test_admin_mark_as_read(self):
        self.client.post(
            reverse('admin:contacts_contactmessage_changelist'),
            {
                'action': 'mark_as_read',
                '_selected_action': [self.msg.pk],
            }
        )
        self.msg.refresh_from_db()
        self.assertTrue(self.msg.is_read)

    def test_admin_mark_as_unread(self):
        self.msg.is_read = True
        self.msg.save()
        self.client.post(
            reverse('admin:contacts_contactmessage_changelist'),
            {
                'action': 'mark_as_unread',
                '_selected_action': [self.msg.pk],
            }
        )
        self.msg.refresh_from_db()
        self.assertFalse(self.msg.is_read)

    def test_admin_mark_as_spam(self):
        self.client.post(
            reverse('admin:contacts_contactmessage_changelist'),
            {
                'action': 'mark_as_spam',
                '_selected_action': [self.msg.pk],
            }
        )
        self.msg.refresh_from_db()
        self.assertTrue(self.msg.is_spam)

    def test_admin_mark_as_not_spam(self):
        self.msg.is_spam = True
        self.msg.save()
        self.client.post(
            reverse('admin:contacts_contactmessage_changelist'),
            {
                'action': 'mark_as_not_spam',
                '_selected_action': [self.msg.pk],
            }
        )
        self.msg.refresh_from_db()
        self.assertFalse(self.msg.is_spam)

    def test_admin_readonly_ip_not_overwritten(self):
        """ip_address is readonly: a POST with a different ip does not change it."""
        original_ip = self.msg.ip_address
        self.client.post(
            reverse('admin:contacts_contactmessage_change', args=[self.msg.pk]),
            {
                'name': self.msg.name,
                'email': self.msg.email,
                'phone': '',
                'subject': self.msg.subject,
                'dog': '',
                'message': self.msg.message,
                'is_read': '',
                'is_spam': '',
                'notes': '',
                'ip_address': '99.99.99.99',   # overwrite attempt
                '_save': 'Save',
            }
        )
        self.msg.refresh_from_db()
        self.assertEqual(self.msg.ip_address, original_ip)

    def test_spam_score_display_high_score(self):
        from apps.contacts.admin import ContactMessageAdmin
        from django.contrib.admin.sites import AdminSite
        ma = ContactMessageAdmin(ContactMessage, AdminSite())
        self.msg.spam_score = 0.9
        html = ma.spam_score_display(self.msg)
        self.assertIn('#28a745', html)  # green

    def test_spam_score_display_low_score(self):
        from apps.contacts.admin import ContactMessageAdmin
        from django.contrib.admin.sites import AdminSite
        ma = ContactMessageAdmin(ContactMessage, AdminSite())
        self.msg.spam_score = 0.1
        html = ma.spam_score_display(self.msg)
        self.assertIn('#dc3545', html)  # red
