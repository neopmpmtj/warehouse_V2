"""Project-level views (docs/user-manuals file serving)."""
from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404

MANUALS_DIR = Path(settings.BASE_DIR) / "docs" / "user-manuals"
_ALLOWED_SUFFIXES = {".pdf", ".md"}
_CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".md": "text/markdown; charset=utf-8",
}


@login_required
def user_manual_file(request, filename):
    """Serve a user-manual file (PDF preferred, MD fallback) from docs/user-manuals."""
    # Lock down: only "<NN>-<slug>.(pdf|md)" basenames, no traversal.
    if "/" in filename or "\\" in filename or filename.startswith("."):
        raise Http404
    path = MANUALS_DIR / filename
    if path.suffix.lower() not in _ALLOWED_SUFFIXES or not path.is_file():
        raise Http404
    return FileResponse(
        path.open("rb"),
        content_type=_CONTENT_TYPES[path.suffix.lower()],
        filename=path.name,
    )
