"""Shared upload-file validation for user-provided images.

Screenshots (deposits) and QR images (withdrawals) are stored as private
media and served only through authenticated owner/admin views. Validation is
strict: content-type allow-list plus magic-byte sniffing via Pillow — the
declared MIME type is never trusted (§9: validate everything server-side).
"""

from __future__ import annotations

import io

from django.conf import settings
from PIL import Image
from rest_framework import serializers

# Allow-listed image types users may upload.
ALLOWED_CONTENT_TYPES = {
    'image/png': b'\x89PNG\r\n\x1a\n',
    'image/jpeg': b'\xff\xd8\xff',
    'image/webp': b'RIFF',  # RIFF container; WEBP marker checked below.
}

DEFAULT_MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB


def max_upload_bytes() -> int:
    """Configured cap for user uploads (settings override, sane default)."""
    value = getattr(settings, 'MAX_UPLOAD_BYTES', None)
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return DEFAULT_MAX_UPLOAD_BYTES
    return parsed if parsed > 0 else DEFAULT_MAX_UPLOAD_BYTES


def validate_user_image(django_file) -> None:
    """Validate an uploaded image in place; raise DRF ValidationError on failure.

    Checks: presence, size cap, declared content type allow-list, magic
    bytes, and full Pillow decode (decompression-bomb guard). The file
    position is rewound before returning so callers can save it directly.
    """
    from django.core.files.uploadedfile import UploadedFile

    if not isinstance(django_file, UploadedFile) or not django_file.name:
        raise serializers.ValidationError({'screenshot': ['A file upload is required.']})

    limit = max_upload_bytes()
    if django_file.size is None or django_file.size == 0:
        raise serializers.ValidationError({'screenshot': ['The uploaded file is empty.']})
    if django_file.size > limit:
        raise serializers.ValidationError(
            {'screenshot': [f'Image is too large. Maximum size is {limit // (1024 * 1024)} MB.']}
        )

    content_type = (getattr(django_file, 'content_type', '') or '').lower().split(';')[0].strip()
    magic = ALLOWED_CONTENT_TYPES.get(content_type)
    if magic is None:
        raise serializers.ValidationError(
            {'screenshot': ['Unsupported image type. Allowed: PNG, JPEG, or WebP.']}
        )

    head = django_file.read(len(magic) + 4)
    django_file.seek(0)
    if not head.startswith(magic):
        raise serializers.ValidationError(
            {'screenshot': ['File content does not match its declared image type.']}
        )
    if content_type == 'image/webp' and head[8:12] != b'WEBP':
        raise serializers.ValidationError(
            {'screenshot': ['File content does not match its declared image type.']}
        )

    # Full decode: rejects truncated files and decompression bombs.
    try:
        with Image.open(io.BytesIO(django_file.read())) as image:
            image.verify()
        django_file.seek(0)
        with Image.open(io.BytesIO(django_file.read())) as image:
            if image.width * image.height > 40_000_000:  # ~50 MP guard
                raise serializers.ValidationError(
                    {'screenshot': ['Image dimensions are too large.']}
                )
    except serializers.ValidationError:
        raise
    except Exception as exc:  # noqa: BLE001 — any decode failure is a reject
        raise serializers.ValidationError(
            {'screenshot': ['The image could not be processed. Please upload a valid PNG, JPEG, or WebP.']}
        ) from exc
    django_file.seek(0)
