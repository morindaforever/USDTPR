"""Authentication API views.

Response envelope everywhere::

    success: true/false, message: str, errors: {}, data: {...}

CSRF protection applies to the cookie-authenticated endpoints (refresh,
logout, change-password when the access token has expired) — the React dev
origin is whitelisted in settings and sends X-CSRFToken.
"""

from django.conf import settings
from django.contrib.auth import logout as django_session_logout
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from apps.core.exceptions import api_exception_handler

from .models import User
from .serializers import (
    ChangePasswordSerializer,
    ForgotPasswordSerializer,
    LoginSerializer,
    RegisterSerializer,
    ResetPasswordSerializer,
    UserPublicSerializer,
)
from .services import (
    AuthError,
    authenticate_user,
    change_password as change_password_service,
    check_login_allowed,
    clear_failed_logins,
    client_ip,
    consume_password_reset,
    find_user_by_identifier,
    issue_password_reset,
    record_failed_login,
    record_login_activity,
    register_user,
    resolve_identifier,
)
from .throttling import AuthLoginThrottle, AuthPasswordResetThrottle


class ApiViewBase(APIView):
    """Shared helpers for the envelope-style responses."""

    def ok(self, data=None, message='OK', http_status=status.HTTP_200_OK):
        body = {'success': True, 'message': message}
        if data is not None:
            body['data'] = data
        return Response(body, status=http_status)

    def fail(self, message, errors=None, http_status=status.HTTP_400_BAD_REQUEST):
        return Response(
            {'success': False, 'message': message, 'errors': errors or {}},
            status=http_status,
        )

    def handle_exception(self, exc):
        if isinstance(exc, AuthError):
            return self.fail(exc.message, exc.errors, exc.http_status)
        return api_exception_handler(exc, {'view': self, 'request': self.request, 'args': (), 'kwargs': {}})


class RegisterView(ApiViewBase):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            result = register_user(
                full_name=data['full_name'],
                email=data['email'],
                phone=data['phone'],
                password=data['password'],
                referral_code=data.get('referral_code', ''),
            )
        except AuthError as exc:
            return self.fail(exc.message, exc.errors)

        # Production conversion (§2): no automatic plan purchase or credits at
        # registration. New accounts are normal users with a zeroed wallet; a
        # VIP plan is only ever created by an explicit, paid purchase flow.

        record_login_activity(
            result.user, 'SUCCESS', request,
            identifier_used=data['email'], detail='account created',
        )

        refresh = RefreshToken.for_user(result.user)
        response = self.ok(
            data={
                'user': UserPublicSerializer(result.user).data,
                'referral_created': result.referral_created,
                'access': str(refresh.access_token),
            },
            message='Account created successfully.',
            http_status=status.HTTP_201_CREATED,
        )
        _set_refresh_cookie(response, str(refresh))
        return response


def _set_refresh_cookie(response, refresh_token: str) -> None:
    response.set_cookie(
        key='refresh_token',
        value=refresh_token,
        httponly=True,
        secure=not settings.DEBUG,  # HTTPS-only outside development
        samesite=getattr(settings, 'REFRESH_COOKIE_SAMESITE', 'Lax'),
        max_age=7 * 24 * 60 * 60,
        path='/api/auth/',
    )


class LoginView(ApiViewBase):
    permission_classes = [AllowAny]
    throttle_classes = [AuthLoginThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        identifier_raw = serializer.validated_data['identifier'].strip()
        password = serializer.validated_data['password']
        ip = client_ip(request)

        identifier = resolve_identifier(identifier_raw)
        # Rate limit key exists even for unknown identifiers, so probes of
        # random emails are throttled identically to known ones.
        check_login_allowed(identifier_raw, ip)

        if identifier is None:
            record_failed_login(identifier_raw, ip)
            if request.user.is_authenticated:
                record_login_activity(request.user, 'FAILED', request, identifier_raw, 'unknown identifier')
            return self.fail('Invalid credentials.', http_status=status.HTTP_401_UNAUTHORIZED)

        user, error = authenticate_user(identifier, password)
        if user is None:
            record_failed_login(identifier_raw, ip)
            probe = find_user_by_identifier(identifier)
            if probe is not None:
                record_login_activity(probe, 'FAILED', request, identifier_raw, error or '')
            return self.fail(error or 'Invalid credentials.', http_status=status.HTTP_401_UNAUTHORIZED)

        clear_failed_logins(identifier_raw, ip)
        record_login_activity(user, 'SUCCESS', request, identifier_raw)

        refresh = RefreshToken.for_user(user)
        response = self.ok(
            data={
                'user': UserPublicSerializer(user).data,
                'access': str(refresh.access_token),
            },
            message='Login successful.',
        )
        _set_refresh_cookie(response, str(refresh))
        return response


class LogoutView(ApiViewBase):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_cookie = request.COOKIES.get('refresh_token')
        if refresh_cookie:
            try:
                token = RefreshToken(refresh_cookie)
                token.blacklist()
            except TokenError:
                pass  # already invalid/expired — logout is still a success
        if request.auth is None:
            django_session_logout(request)  # session-authenticated fallback
        record_login_activity(request.user, 'LOGOUT', request)
        response = self.ok(message='Logged out successfully.')
        response.delete_cookie('refresh_token', path='/api/auth/')
        return response


class MeView(ApiViewBase):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return self.ok(data={'user': UserPublicSerializer(request.user).data})


class ThrottledTokenRefreshView(TokenRefreshView):
    """Reads the refresh token from the HttpOnly cookie (or body fallback)."""

    throttle_classes = [AuthLoginThrottle]

    def post(self, request, *args, **kwargs):
        if 'refresh' not in request.data:
            cookie = request.COOKIES.get('refresh_token')
            if cookie:
                request.data['refresh'] = cookie
        response = super().post(request, *args, **kwargs)
        new_refresh = response.data.get('refresh') if isinstance(response.data, dict) else None
        if new_refresh and response.status_code == 200:
            _set_refresh_cookie(response, new_refresh)
            response.data.pop('refresh', None)
        return response


class ForgotPasswordView(ApiViewBase):
    permission_classes = [AllowAny]
    throttle_classes = [AuthPasswordResetThrottle]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email'].strip().lower()

        # Never reveal whether the account exists.
        user = User.objects.filter(email__iexact=email).first()
        if user is not None:
            token = issue_password_reset(user, ip=client_ip(request))
            # Development: the email backend is console; log to server output.
            print(f'[dev] password reset for {user.email}: /reset-password/{token}')
        return self.ok(
            message='If the account exists, password reset instructions have been sent.'
        )


class ResetPasswordView(ApiViewBase):
    permission_classes = [AllowAny]
    throttle_classes = [AuthPasswordResetThrottle]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            user = consume_password_reset(data['token'], data['password'])
        except AuthError as exc:
            return self.fail(exc.message, exc.errors)
        record_login_activity(user, 'SUCCESS', request, detail='password reset completed')
        return self.ok(message='Password has been reset. You can now log in.')


class ChangePasswordView(ApiViewBase):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            change_password_service(request.user, data['current_password'], data['password'])
        except AuthError as exc:
            return self.fail(exc.message, exc.errors)
        record_login_activity(request.user, 'SUCCESS', request, detail='password changed')
        return self.ok(message='Password updated successfully.')


__all__ = [
    'ChangePasswordView',
    'ForgotPasswordView',
    'LoginView',
    'LogoutView',
    'MeView',
    'RegisterView',
    'ResetPasswordView',
    'ThrottledTokenRefreshView',
]
