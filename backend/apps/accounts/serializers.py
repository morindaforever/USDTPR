"""Serializers for the authentication API."""

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import User
from .services import AuthError, validate_registration


class UserPublicSerializer(serializers.ModelSerializer):
    """Safe user representation — never includes passwords or tokens."""

    class Meta:
        model = User
        fields = [
            'user_id',
            'full_name',
            'email',
            'phone',
            'referral_code',
            'account_status',
            'is_staff',
        ]
        read_only_fields = fields


class RegisterSerializer(serializers.Serializer):
    """Signup payload; mirrors frontend validation exactly."""

    full_name = serializers.CharField(max_length=120)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=20)
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    password_confirm = serializers.CharField(write_only=True, style={'input_type': 'password'})
    referral_code = serializers.CharField(max_length=12, required=False, allow_blank=True, default='')

    def validate(self, attrs):
        try:
            validate_registration(
                full_name=attrs.get('full_name', ''),
                email=attrs.get('email', ''),
                phone=attrs.get('phone', ''),
                password=attrs.get('password', ''),
                password_confirm=attrs.get('password_confirm', ''),
                referral_code=attrs.get('referral_code', ''),
            )
        except AuthError as exc:
            raise serializers.ValidationError(exc.errors) from exc
        return attrs


class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(max_length=255)
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    token = serializers.CharField()
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    password_confirm = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate(self, attrs):
        if attrs.get('password') != attrs.get('password_confirm'):
            raise serializers.ValidationError(
                {'password_confirm': ['Passwords do not match.']}
            )
        validate_password(attrs.get('password', ''))
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    password_confirm = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate(self, attrs):
        if attrs.get('password') != attrs.get('password_confirm'):
            raise serializers.ValidationError(
                {'password_confirm': ['Passwords do not match.']}
            )
        return attrs
