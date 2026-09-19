"""Serializers for core (cross-cutting) endpoints."""

from rest_framework import serializers

from .models import CompanyValuation


class CompanyValuationSerializer(serializers.ModelSerializer):
    value = serializers.DecimalField(max_digits=24, decimal_places=8, read_only=True)
    is_demo = serializers.BooleanField(read_only=True)

    class Meta:
        model = CompanyValuation
        fields = ['valuation_date', 'value', 'currency', 'is_demo']
        read_only_fields = fields
