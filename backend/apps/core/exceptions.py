"""Consistent API error envelope.

All error responses use::

    {"success": false, "message": "...", "errors": {...}}

Success envelopes are built by the views themselves.
"""

from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.views import Response


def _detail_to_errors(data) -> dict:
    """Flatten DRF error payloads into {field: [messages]}."""
    if isinstance(data, dict):
        errors = {}
        for key, value in data.items():
            errors[key] = value if isinstance(value, list) else [value]
        return errors
    if isinstance(data, list):
        return {'non_field_errors': data}
    return {}


def _friendly_message(errors: dict, status: int) -> str:
    if 'detail' in errors:
        return str(errors['detail'][0])
    if 'non_field_errors' in errors:
        return str(errors['non_field_errors'][0])
    if status == 400:
        return 'Please correct the highlighted fields.'
    if status == 401:
        return 'Authentication is required.'
    if status == 403:
        return 'You do not have permission to perform this action.'
    if status == 404:
        return 'Not found.'
    if status == 429:
        return 'Too many requests. Please slow down.'
    if status >= 500:
        return 'Something went wrong on our side. Please try again.'
    return 'Request failed.'


def api_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return None
    errors = _detail_to_errors(response.data)
    message = _friendly_message(errors, response.status_code)
    return Response(
        {'success': False, 'message': message, 'errors': errors},
        status=response.status_code,
    )
