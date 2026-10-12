"""
Custom middleware.
"""
import time
import logging

from apps.core.client_ip import get_client_ip

logger = logging.getLogger(__name__)


class ResponseTimeMiddleware:
    """Middleware that measures the response time."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.time()

        response = self.get_response(request)

        duration = time.time() - start_time

        # Add a response-time header
        response['X-Response-Time'] = f"{duration:.3f}s"

        # Log slow requests (> 1 second)
        if duration > 1.0:
            logger.warning(
                f"Slow request: {request.method} {request.path} - {duration:.3f}s"
            )

        return response


class RequestLoggingMiddleware:
    """Middleware that logs incoming requests."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Log the request
        logger.info(
            f"{request.method} {request.path} - "
            f"IP: {get_client_ip(request)}"
        )

        response = self.get_response(request)

        return response
