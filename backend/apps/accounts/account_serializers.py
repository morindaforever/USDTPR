"""Account serializers (Section 11).

The public profile payload reuses ``UserPublicSerializer`` semantics: no
password fields, tokens, or internal security metadata ever serialize here.
Editable fields are limited to what §7 allows — full name and phone. Email is
read-only (no secure email-change flow exists in the auth architecture).
"""

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import User


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """PATCH /api/account/profile/ — full_name + phone only.

    Anything else in the payload (user_id, account_status, is_staff,
    referral_code, email, …) is silently ignored: DRF ModelSerializer only
    accepts declared fields, so a client cannot escalate privileges (§77).
    """

    full_name = serializers.CharField(max_length=120, required=False, allow_blank=False)
    phone = serializers.CharField(max_length=20, required=False)

    class Meta:
        model = User
        fields = ['full_name', 'phone']

    def validate_full_name(self, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError('Full name cannot be empty.')
        return cleaned

    def validate_phone(self, value: str) -> str:
        cleaned = value.strip()
        user = self.context['request'].user
        candidate = User(phone=cleaned)
        # Reuse the model validator (format) then enforce uniqueness (§8).
        for validator in User._meta.get_field('phone').validators:
            validator(cleaned)
        if User.objects.exclude(pk=user.pk).filter(phone=cleaned).exists():
            raise serializers.ValidationError('This phone number is already in use.')
        return candidate.phone

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError('Nothing to update.')
        return attrs


class PasswordChangeSerializer(serializers.Serializer):
    """POST /api/account/change-password/ (§14). Backend stays authoritative.

    The existing /api/auth/change-password/ service performs the real work;
    this serializer mirrors its payload for the account-surface endpoint.
    """

    current_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True, trim_whitespace=False)
    confirm_password = serializers.CharField(required=True, write_only=True, trim_whitespace=False)

    def validate_current_password(self, value: str) -> str:
        if not self.context['request'].user.check_password(value):
            raise serializers.ValidationError('Current password is incorrect.')
        return value

    def validate_new_password(self, value: str) -> str:
        user = self.context['request'].user
        if not value:
            raise serializers.ValidationError('New password cannot be empty.')
        try:
            validate_password(value, user=user)
        except serializers.DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError(
                {'confirm_password': ['Passwords do not match.']}
            )
        if attrs['new_password'] == attrs['current_password']:
            raise serializers.ValidationError(
                {'new_password': ['New password must be different from the current password.']}
            )
        return attrs


class AccountActivitySerializer(serializers.Serializer):
    """One entry of the safe user-facing activity feed (§19).

    Built by the view from LoginActivity / AuditLog / business rows — raw
    internal records are never exposed directly (§20).
    """

    type = serializers.CharField()
    title = serializers.CharField()
    detail = serializers.CharField(allow_blank=True)
    occurred_at = serializers.DateTimeField()
