from django.utils import timezone

from logging_utils import get_logger

logger = get_logger("centcompras.accounts")


class UserTimezoneMiddleware:
    """Activate each authenticated user's timezone for server-rendered dates.

    The staff console already renders dates in the browser's local timezone, so
    this middleware mainly matters for the Django admin and any template that
    renders dates server-side.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tz = None
        if request.user.is_authenticated:
            tz = getattr(request.user, "timezone", None)

        if tz:
            try:
                timezone.activate(tz)
            except Exception:
                logger.exception(
                    "Invalid user timezone %r for %s; falling back to UTC.",
                    tz,
                    getattr(request.user, "email", None),
                )
                timezone.deactivate()
        else:
            timezone.deactivate()

        try:
            return self.get_response(request)
        finally:
            timezone.deactivate()
