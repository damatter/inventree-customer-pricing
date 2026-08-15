"""REST serializers for the customer pricing workspace."""

from company.models import Company
from moneyed import CURRENCIES
from rest_framework import serializers

from .costing import calculate_profit_margin
from .models import (
    CustomerPriceBreak,
    CustomerPriceList,
    MaterialCostEntry,
    PartPricingPolicy,
    VendorPriceBreak,
    VendorPriceList,
)


def _decimal(value):
    """Render a decimal without scientific notation."""

    return format(value, "f") if value is not None else None


def _material_cost(context: dict, currency: str):
    """Look up the converted material total supplied by the workspace view."""

    return context.get("material_cost_by_currency", {}).get(currency.upper())


def _margin_fields(selling_price, material_cost) -> dict:
    """Return consistent nullable margin fields for API serializers."""

    margin = calculate_profit_margin(selling_price, material_cost)
    return {
        "material_cost": _decimal(material_cost),
        "profit_amount": _decimal(margin.amount) if margin else None,
        "profit_margin_percent": _decimal(margin.percent) if margin else None,
    }


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
        fields = [
            "pk",
            "price_list",
            "quantity",
            "price",
            "currency",
            "material_cost",
            "profit_amount",
            "profit_margin_percent",
            "created",
            "updated",
        ]
        read_only_fields = [
            "pk",
            "price_list",
            "currency",
            "material_cost",
            "profit_amount",
            "profit_margin_percent",
            "created",
            "updated",
        ]

    currency = serializers.CharField(source="price_list.currency", read_only=True)
    material_cost = serializers.SerializerMethodField()
    profit_amount = serializers.SerializerMethodField()
    profit_margin_percent = serializers.SerializerMethodField()

    def _margin(self, obj):
        cost = _material_cost(self.context, obj.price_list.currency)
        return _margin_fields(obj.price, cost)

    def get_material_cost(self, obj):
        return self._margin(obj)["material_cost"]

    def get_profit_amount(self, obj):
        return self._margin(obj)["profit_amount"]

    def get_profit_margin_percent(self, obj):
        return self._margin(obj)["profit_margin_percent"]


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
            "material_cost",
            "base_selling_price",
            "profit_amount",
            "profit_margin_percent",
            "breaks",
            "created",
            "updated",
        ]
        read_only_fields = [
            "pk",
            "part",
            "customer_name",
            "material_cost",
            "base_selling_price",
            "profit_amount",
            "profit_margin_percent",
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
    material_cost = serializers.SerializerMethodField()
    base_selling_price = serializers.SerializerMethodField()
    profit_amount = serializers.SerializerMethodField()
    profit_margin_percent = serializers.SerializerMethodField()

    def _base_margin(self, obj):
        first_break = next(iter(obj.breaks.all()), None)
        selling_price = first_break.price if first_break else None
        cost = _material_cost(self.context, obj.currency)
        return {
            "base_selling_price": _decimal(selling_price),
            **_margin_fields(selling_price, cost),
        }

    def get_material_cost(self, obj):
        return self._base_margin(obj)["material_cost"]

    def get_base_selling_price(self, obj):
        return self._base_margin(obj)["base_selling_price"]

    def get_profit_amount(self, obj):
        return self._base_margin(obj)["profit_amount"]

    def get_profit_margin_percent(self, obj):
        return self._base_margin(obj)["profit_margin_percent"]

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


class MaterialCostEntrySerializer(serializers.ModelSerializer):
    """Serialize one durable material cost row."""

    class Meta:
        model = MaterialCostEntry
        fields = [
            "pk",
            "part",
            "name",
            "quantity",
            "unit_cost",
            "currency",
            "total_cost",
            "active",
            "notes",
            "created",
            "updated",
        ]
        read_only_fields = ["pk", "part", "total_cost", "created", "updated"]

    currency = CurrencyField()
    total_cost = serializers.SerializerMethodField()

    def get_total_cost(self, obj):
        return _decimal(obj.total_cost)


class VendorPriceBreakSerializer(serializers.ModelSerializer):
    """Serialize a lightweight vendor quantity tier."""

    class Meta:
        model = VendorPriceBreak
        fields = ["pk", "price_list", "quantity", "price", "created", "updated"]
        read_only_fields = ["pk", "price_list", "created", "updated"]


class VendorPriceListSerializer(serializers.ModelSerializer):
    """Serialize a lightweight vendor schedule and its quantity tiers."""

    class Meta:
        model = VendorPriceList
        fields = [
            "pk",
            "part",
            "vendor_name",
            "vendor_sku",
            "currency",
            "purchase_url",
            "lead_time_days",
            "active",
            "preferred",
            "notes",
            "breaks",
            "created",
            "updated",
        ]
        read_only_fields = ["pk", "part", "breaks", "created", "updated"]

    currency = CurrencyField()
    breaks = VendorPriceBreakSerializer(many=True, read_only=True)

    def _enforce_single_preferred(self, instance):
        if instance.preferred:
            VendorPriceList.objects.filter(part=instance.part).exclude(pk=instance.pk).update(
                preferred=False
            )
        return instance

    def create(self, validated_data):
        return self._enforce_single_preferred(super().create(validated_data))

    def update(self, instance, validated_data):
        return self._enforce_single_preferred(super().update(instance, validated_data))
