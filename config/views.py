"""Project-level views (docs/user-manuals file serving)."""
from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404

MANUALS_DIR = Path(settings.BASE_DIR) / "docs" / "user-manuals"
_ALLOWED_LANGS = {"en", "pt"}
_ALLOWED_SUFFIXES = {".pdf", ".md"}
_CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".md": "text/markdown; charset=utf-8",
}


@login_required
def user_manual_file(request, lang, filename):
    """Serve a user-manual file from docs/user-manuals/<lang>/ (PDF or MD).

    lang is restricted to the known manual languages (en/pt); filename is
    locked down to "<NN>-<slug>.(pdf|md)" basenames — no traversal.
    """
    if lang not in _ALLOWED_LANGS:
        raise Http404
    if "/" in filename or "\\" in filename or filename.startswith("."):
        raise Http404
    path = MANUALS_DIR / lang / filename
    if path.suffix.lower() not in _ALLOWED_SUFFIXES or not path.is_file():
        raise Http404
    return FileResponse(
        path.open("rb"),
        content_type=_CONTENT_TYPES[path.suffix.lower()],
        filename=path.name,
    )
