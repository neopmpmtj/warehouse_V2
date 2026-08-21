from .services import get_active_branch


class ActiveBranchMiddleware:
    """Resolve the session's active branch onto ``request.active_branch``.

    Sets ``None`` when unset, the membership was revoked, or the branch is
    inactive (the session key is cleared in that case). Runs after
    ``AuthenticationMiddleware`` so ``request.user`` is populated.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.active_branch = get_active_branch(request)
        return self.get_response(request)
