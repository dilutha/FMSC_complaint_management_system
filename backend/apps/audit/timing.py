"""Per-request diagnostics: duration, SQL query count and time spent in the
database. Logged at INFO for API requests (WARNING when slower than
FMSC_SLOW_REQUEST_MS). Never logs request bodies, headers, passwords or tokens.

Example:  POST /api/v1/auth/token/ 200 812ms db=5q/770ms
"""
import logging
import time

from django.conf import settings
from django.db import connection

logger = logging.getLogger("apps.requests")


class _QueryTimer:
    def __init__(self):
        self.count = 0
        self.seconds = 0.0

    def __call__(self, execute, sql, params, many, context):
        start = time.perf_counter()
        try:
            return execute(sql, params, many, context)
        finally:
            self.count += 1
            self.seconds += time.perf_counter() - start


class RequestTimingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith("/api/"):
            return self.get_response(request)
        timer = _QueryTimer()
        start = time.perf_counter()
        with connection.execute_wrapper(timer):
            response = self.get_response(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        slow = elapsed_ms >= getattr(settings, "FMSC_SLOW_REQUEST_MS", 1000)
        logger.log(
            logging.WARNING if slow else logging.INFO,
            "%s %s %s %.0fms db=%dq/%.0fms%s",
            request.method, request.path, response.status_code, elapsed_ms, timer.count, timer.seconds * 1000,
            " SLOW" if slow else "",
        )
        if settings.DEBUG:  # visible in browser dev tools; not exposed in production
            response["Server-Timing"] = f"app;dur={elapsed_ms:.0f}, db;dur={timer.seconds * 1000:.0f};desc=\"{timer.count} queries\""
        return response
