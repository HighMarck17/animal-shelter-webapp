"""
Client IP resolution shared by request logging, the contact form,
django-ratelimit (RATELIMIT_IP_META_KEY) and django-axes (AXES_CLIENT_IP_CALLABLE).
"""
import ipaddress

from django.conf import settings


def get_client_ip(request):
    """Return the client IP address of *request*.

    CLIENT_IP_META_KEY names the request.META key that holds it: REMOTE_ADDR
    (default) when Gunicorn faces clients directly, or a header that the
    trusted reverse proxy always overwrites (nginx sets X-Real-IP, read as
    HTTP_X_REAL_IP). X-Forwarded-For is never used: clients can put any value
    at its start. A missing or malformed value falls back to REMOTE_ADDR.
    """
    key = getattr(settings, 'CLIENT_IP_META_KEY', 'REMOTE_ADDR')
    remote_addr = request.META.get('REMOTE_ADDR', '')
    for candidate in (request.META.get(key), remote_addr):
        if not candidate:
            continue
        try:
            return str(ipaddress.ip_address(candidate.strip()))
        except ValueError:
            continue
    return remote_addr
