"""REST serializers for the customer pricing workspace."""

from company.models import Company
from moneyed import CURRENCIES
from rest_framework import serializers

from .models import CustomerPriceBreak, CustomerPriceList, PartPricingPolicy


class CurrencyField(serializers.CharField):
    """Normalize and validate an ISO 4217 currency code."""

    def __init__(self, **kwargs):
        super().__init__(min_length=3, max_length=3, **kwargs)

    def to_internal_value(self, data):
        value = super().to_internal_value(data).upper()
        if value not in CURRENCIES:
            raise serializers.ValidationError("Enter a valid ISO 4217 currency code.")
        return value


class CustomerPriceBreakSerializer(serializers.ModelSerializer):
    """Serialize an individual customer quantity tier."""

    class Meta:
        model = CustomerPriceBreak
        fields = ["pk", "price_list", "quantity", "price", "created", "updated"]
        read_only_fields = ["pk", "price_list", "created", "updated"]


class CustomerPriceListSerializer(serializers.ModelSerializer):
    """Serialize a customer schedule and its quantity tiers."""

    class Meta:
        model = CustomerPriceList
        fields = [
            "pk",
            "part",
            "customer",
            "customer_name",
            "currency",
            "active",
            "notes",
            "breaks",
            "created",
            "updated",
        ]
        read_only_fields = [
            "pk",
            "part",
            "customer_name",
            "breaks",
            "created",
            "updated",
        ]

    customer = serializers.PrimaryKeyRelatedField(
        queryset=Company.objects.filter(is_customer=True, active=True)
    )
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    currency = CurrencyField()
    breaks = CustomerPriceBreakSerializer(many=True, read_only=True)

    def validate(self, attrs):
        """Prevent duplicate customer schedules for the scoped part."""

        part = self.context.get("part") or getattr(self.instance, "part", None)
        customer = attrs.get("customer") or getattr(self.instance, "customer", None)

        if part and customer:
            duplicate = CustomerPriceList.objects.filter(part=part, customer=customer)
            if self.instance:
                duplicate = duplicate.exclude(pk=self.instance.pk)
            if duplicate.exists():
                raise serializers.ValidationError(
                    {"customer": "This customer already has a price list for the part."}
                )

        return attrs


class PartPricingPolicySerializer(serializers.ModelSerializer):
    """Serialize per-part synchronization configuration."""

    class Meta:
        model = PartPricingPolicy
        fields = [
            "sync_native_sale",
            "sync_currency",
            "last_synced",
            "last_sync_error",
        ]
        read_only_fields = ["last_synced", "last_sync_error"]

    sync_currency = CurrencyField(required=False, allow_blank=True)
