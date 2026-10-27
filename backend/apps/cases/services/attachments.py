"""Attachment validation and storage.

The declared content type and extension are never trusted on their own: the
file's leading bytes must match the expected signature for its extension.
"""
from django.conf import settings
from django.db import transaction

from apps.cases.models import Attachment, AttachmentKind, Case

from .exceptions import ValidationFailed

# extension -> (content type, media family, signature check)
def _is_jpeg(h):
    return h.startswith(b"\xff\xd8\xff")


def _is_png(h):
    return h.startswith(b"\x89PNG\r\n\x1a\n")


def _is_webp(h):
    return h[:4] == b"RIFF" and h[8:12] == b"WEBP"


def _is_iso_media(h):  # MP4 / MOV / 3GP all use the ISO base media 'ftyp' box
    return h[4:8] == b"ftyp"


def _is_webm(h):
    return h.startswith(b"\x1a\x45\xdf\xa3")


ALLOWED_TYPES = {
    "jpg": ("image/jpeg", "image", _is_jpeg),
    "jpeg": ("image/jpeg", "image", _is_jpeg),
    "png": ("image/png", "image", _is_png),
    "webp": ("image/webp", "image", _is_webp),
    "mp4": ("video/mp4", "video", _is_iso_media),
    "mov": ("video/quicktime", "video", _is_iso_media),
    "webm": ("video/webm", "video", _is_webm),
}


def validate_upload(upload):
    """Return the canonical content type, or raise ValidationFailed."""
    name = upload.name or ""
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in ALLOWED_TYPES:
        raise ValidationFailed(
            f"“{name}” is not an allowed file type. Allowed: {', '.join(sorted(ALLOWED_TYPES))}.",
            code="unsupported_file_type",
        )
    content_type, family, signature_ok = ALLOWED_TYPES[ext]
    limit = settings.FMSC_CASES["MAX_IMAGE_BYTES" if family == "image" else "MAX_VIDEO_BYTES"]
    if upload.size > limit:
        raise ValidationFailed(
            f"“{name}” is too large. Maximum {family} size is {limit // (1024 * 1024)} MB.", code="file_too_large"
        )
    if upload.size == 0:
        raise ValidationFailed(f"“{name}” is empty.", code="empty_file")
    upload.seek(0)
    header = upload.read(16)
    upload.seek(0)
    if not signature_ok(header):
        raise ValidationFailed(f"“{name}” does not look like a valid {ext.upper()} file.", code="file_content_mismatch")
    return content_type


def save_attachments(case: Case, uploads, *, actor, kind=AttachmentKind.EVIDENCE, update=None):
    if not uploads:
        return []
    limit = settings.FMSC_CASES["MAX_ATTACHMENTS_PER_CASE"]
    content_types = [validate_upload(u) for u in uploads]  # validate all before saving any
    with transaction.atomic():
        Case.objects.select_for_update().only("pk").get(pk=case.pk)  # serialise uploads per case
        existing = Attachment.objects.filter(case=case).count()
        if existing + len(uploads) > limit:
            raise ValidationFailed(f"A case can have at most {limit} attachments.", code="too_many_attachments")
        saved = []
        for upload, content_type in zip(uploads, content_types):
            att = Attachment(
                case=case,
                update=update,
                original_name=upload.name[:255],
                content_type=content_type,
                size=upload.size,
                kind=kind,
                uploaded_by=actor,
            )
            att.file.save(upload.name, upload, save=False)
            att.save()
            saved.append(att)
    return saved
