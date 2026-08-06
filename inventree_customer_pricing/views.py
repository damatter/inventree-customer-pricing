"""Authenticated API views for the part pricing workspace."""

from decimal import Decimal

from company.models import Company
from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from djmoney.money import Money
from moneyed import CURRENCIES
from part.models import Part, PartSellPriceBreak
from rest_framework import permissions, serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView
from users.permissions import check_user_role

from .models import (
    CustomerPriceBreak,
    CustomerPriceList,
    PartPricingPolicy,
    VendorPriceBreak,
    VendorPriceList,
)
from .native_sync import (
    CustomerPricingSyncError,
    resolved_sync_currency,
    sync_part_sale_prices,
)
from .serializers import (
    CurrencyField,
    CustomerPriceBreakSerializer,
    CustomerPriceListSerializer,
    PartPricingPolicySerializer,
    VendorPriceBreakSerializer,
    VendorPriceListSerializer,
)


def _has_role(user, role: str, action: str) -> bool:
    """Check an InvenTree role while retaining superuser access."""

    return bool(user and (user.is_superuser or check_user_role(user, role, action)))


def _require_role(request, role: str, action: str) -> None:
    """Raise a standard API permission error when a role is missing."""

    if not _has_role(request.user, role, action):
        raise PermissionDenied(f"The {role}.{action} role is required for this operation.")


def _decimal(value: Decimal) -> str:
    """Return a non-exponential decimal string for API output."""

    return format(value, "f")


def _money_break(price_break) -> dict:
    """Serialize a native InvenTree price-break model."""

    return {
        "pk": price_break.pk,
        "quantity": _decimal(price_break.quantity),
        "price": _decimal(price_break.price.amount) if price_break.price is not None else None,
        "currency": price_break.price.currency.code if price_break.price is not None else "",
    }


class PricingAPIView(APIView):
    """Base class which relies on explicit InvenTree role checks."""

    permission_classes = [permissions.IsAuthenticated]


class PriceBreakInputSerializer(serializers.Serializer):
    """Validate native supplier and sale price-break input."""

    quantity = serializers.DecimalField(max_digits=15, decimal_places=5, min_value=1)
    price = serializers.DecimalField(max_digits=19, decimal_places=6, min_value=0)
    currency = CurrencyField()


class PricingWorkspaceView(PricingAPIView):
    """Return every pricing dataset needed by the part-detail tab."""

    def get(self, request, part_id: int):
        part = get_object_or_404(Part, pk=part_id)

        can_view_sales = _has_role(request.user, "sales_order", "view")
        can_change_sales = _has_role(request.user, "sales_order", "change")
        can_view_purchase = _has_role(request.user, "purchase_order", "view")
        can_change_purchase = _has_role(request.user, "purchase_order", "change")

        if not (can_view_sales or can_view_purchase):
            raise PermissionDenied("A sales-order or purchase-order role is required.")

        policy = PartPricingPolicy.objects.filter(part=part).first()
        policy_data = (
            PartPricingPolicySerializer(policy).data
            if policy
            else {
                "sync_native_sale": True,
                "sync_currency": "",
                "last_synced": None,
                "last_sync_error": "",
            }
        )
        policy_data["resolved_currency"] = resolved_sync_currency(policy)

        customer_lists = []
        customer_options = []
        native_sale_breaks = []

        if can_view_sales:
            customer_queryset = (
                CustomerPriceList.objects.filter(part=part)
                .select_related("customer")
                .prefetch_related("breaks")
            )
            customer_lists = CustomerPriceListSerializer(customer_queryset, many=True).data
            customer_options = [
                {
                    "pk": customer.pk,
                    "name": customer.name,
                    "currency": customer.currency,
                }
                for customer in Company.objects.filter(is_customer=True, active=True).order_by(
                    "name"
                )
            ]
            native_sale_breaks = [
                _money_break(price_break)
                for price_break in PartSellPriceBreak.objects.filter(part=part).order_by("quantity")
            ]

        vendor_lists = []
        if can_view_purchase:
            vendor_queryset = VendorPriceList.objects.filter(part=part).prefetch_related("breaks")
            vendor_lists = VendorPriceListSerializer(vendor_queryset, many=True).data

        return Response(
            {
                "part": {
                    "pk": part.pk,
                    "name": part.name,
                    "ipn": part.IPN,
                    "salable": part.salable,
                    "purchaseable": part.purchaseable,
                },
                "permissions": {
                    "view_sales": can_view_sales,
                    "change_sales": can_change_sales,
                    "view_purchase": can_view_purchase,
                    "change_purchase": can_change_purchase,
                },
                "policy": policy_data,
                "customer_lists": customer_lists,
                "customers": customer_options,
                "native_sale_breaks": native_sale_breaks,
                "vendor_lists": vendor_lists,
                "currencies": sorted(CURRENCIES.keys()),
            }
        )


class PricingPolicyView(PricingAPIView):
    """Update synchronization policy for a part."""

    def patch(self, request, part_id: int):
        _require_role(request, "sales_order", "change")
        part = get_object_or_404(Part, pk=part_id)
        policy, _ = PartPricingPolicy.objects.get_or_create(part=part)
        serializer = PartPricingPolicySerializer(policy, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        if policy.sync_native_sale:
            try:
                sync_part_sale_prices(part.pk)
            except CustomerPricingSyncError as exc:
                raise serializers.ValidationError({"sync": str(exc)}) from exc

        return Response(PartPricingPolicySerializer(policy).data)


class PricingSyncView(PricingAPIView):
    """Manually request native sale-price synchronization."""

    def post(self, request, part_id: int):
        _require_role(request, "sales_order", "change")
        get_object_or_404(Part, pk=part_id)

        try:
            result = sync_part_sale_prices(part_id)
        except CustomerPricingSyncError as exc:
            raise serializers.ValidationError({"sync": str(exc)}) from exc

        return Response(result)


class CustomerPriceListCollectionView(PricingAPIView):
    """Create a customer schedule for a part."""

    def post(self, request, part_id: int):
        _require_role(request, "sales_order", "change")
        part = get_object_or_404(Part, pk=part_id)
        serializer = CustomerPriceListSerializer(data=request.data, context={"part": part})
        serializer.is_valid(raise_exception=True)
        price_list = serializer.save(part=part)
        return Response(
            CustomerPriceListSerializer(price_list).data, status=status.HTTP_201_CREATED
        )


class CustomerPriceListDetailView(PricingAPIView):
    """Update or delete a customer schedule."""

    def _instance(self, part_id: int, pk: int):
        return get_object_or_404(CustomerPriceList, pk=pk, part_id=part_id)

    def patch(self, request, part_id: int, pk: int):
        _require_role(request, "sales_order", "change")
        price_list = self._instance(part_id, pk)
        serializer = CustomerPriceListSerializer(
            price_list,
            data=request.data,
            partial=True,
            context={"part": price_list.part},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, part_id: int, pk: int):
        _require_role(request, "sales_order", "change")
        self._instance(part_id, pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CustomerPriceBreakCollectionView(PricingAPIView):
    """Create a quantity tier on a customer schedule."""

    def post(self, request, part_id: int, price_list_id: int):
        _require_role(request, "sales_order", "change")
        price_list = get_object_or_404(CustomerPriceList, pk=price_list_id, part_id=part_id)
        serializer = CustomerPriceBreakSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            price_break = serializer.save(price_list=price_list)
        except IntegrityError as exc:
            raise serializers.ValidationError(
                {"quantity": "A price break already exists at this quantity."}
            ) from exc

        return Response(
            CustomerPriceBreakSerializer(price_break).data,
            status=status.HTTP_201_CREATED,
        )


class CustomerPriceBreakDetailView(PricingAPIView):
    """Update or delete a customer quantity tier."""

    def _instance(self, part_id: int, pk: int):
        return get_object_or_404(CustomerPriceBreak, pk=pk, price_list__part_id=part_id)

    def patch(self, request, part_id: int, pk: int):
        _require_role(request, "sales_order", "change")
        price_break = self._instance(part_id, pk)
        serializer = CustomerPriceBreakSerializer(price_break, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        try:
            serializer.save()
        except IntegrityError as exc:
            raise serializers.ValidationError(
                {"quantity": "A price break already exists at this quantity."}
            ) from exc

        return Response(serializer.data)

    def delete(self, request, part_id: int, pk: int):
        _require_role(request, "sales_order", "change")
        self._instance(part_id, pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def _assert_native_sale_editable(part: Part) -> None:
    policy = PartPricingPolicy.objects.filter(part=part).first()
    if policy is None or policy.sync_native_sale:
        raise serializers.ValidationError(
            {"sync": "Disable automatic native sale synchronization before editing sale breaks."}
        )


class NativeSaleBreakCollectionView(PricingAPIView):
    """Create a native sale price break while automatic sync is disabled."""

    def post(self, request, part_id: int):
        _require_role(request, "sales_order", "change")
        part = get_object_or_404(Part, pk=part_id)
        _assert_native_sale_editable(part)
        serializer = PriceBreakInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if PartSellPriceBreak.objects.filter(
            part=part, quantity=serializer.validated_data["quantity"]
        ).exists():
            raise serializers.ValidationError(
                {"quantity": "A sale price break already exists at this quantity."}
            )

        price_break = PartSellPriceBreak.objects.create(
            part=part,
            quantity=serializer.validated_data["quantity"],
            price=Money(
                serializer.validated_data["price"],
                serializer.validated_data["currency"],
            ),
        )
        return Response(_money_break(price_break), status=status.HTTP_201_CREATED)


class NativeSaleBreakDetailView(PricingAPIView):
    """Update or delete a native sale price break when unmanaged."""

    def _instance(self, part_id: int, pk: int):
        return get_object_or_404(PartSellPriceBreak, pk=pk, part_id=part_id)

    def patch(self, request, part_id: int, pk: int):
        _require_role(request, "sales_order", "change")
        price_break = self._instance(part_id, pk)
        _assert_native_sale_editable(price_break.part)
        initial = {
            "quantity": price_break.quantity,
            "price": price_break.price.amount,
            "currency": price_break.price.currency.code,
        }
        serializer = PriceBreakInputSerializer(data={**initial, **request.data})
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data

        duplicate = PartSellPriceBreak.objects.filter(
            part=price_break.part, quantity=values["quantity"]
        ).exclude(pk=price_break.pk)
        if duplicate.exists():
            raise serializers.ValidationError(
                {"quantity": "A sale price break already exists at this quantity."}
            )

        price_break.quantity = values["quantity"]
        price_break.price = Money(values["price"], values["currency"])
        price_break.save()
        return Response(_money_break(price_break))

    def delete(self, request, part_id: int, pk: int):
        _require_role(request, "sales_order", "change")
        price_break = self._instance(part_id, pk)
        _assert_native_sale_editable(price_break.part)
        price_break.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class VendorPriceListCollectionView(PricingAPIView):
    """Create a simple vendor schedule without native supplier setup."""

    def post(self, request, part_id: int):
        _require_role(request, "purchase_order", "change")
        part = get_object_or_404(Part, pk=part_id)
        serializer = VendorPriceListSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save(part=part)
        return Response(VendorPriceListSerializer(instance).data, status=status.HTTP_201_CREATED)


class VendorPriceListDetailView(PricingAPIView):
    """Update or delete a simple vendor schedule."""

    def _instance(self, part_id: int, pk: int):
        return get_object_or_404(VendorPriceList, pk=pk, part_id=part_id)

    def patch(self, request, part_id: int, pk: int):
        _require_role(request, "purchase_order", "change")
        instance = self._instance(part_id, pk)
        serializer = VendorPriceListSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(VendorPriceListSerializer(serializer.save()).data)

    def delete(self, request, part_id: int, pk: int):
        _require_role(request, "purchase_order", "change")
        self._instance(part_id, pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class VendorPriceBreakCollectionView(PricingAPIView):
    """Create a quantity break on a simple vendor schedule."""

    def post(self, request, part_id: int, price_list_id: int):
        _require_role(request, "purchase_order", "change")
        price_list = get_object_or_404(VendorPriceList, pk=price_list_id, part_id=part_id)
        serializer = VendorPriceBreakSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if VendorPriceBreak.objects.filter(
            price_list=price_list, quantity=serializer.validated_data["quantity"]
        ).exists():
            raise serializers.ValidationError(
                {"quantity": "A vendor price break already exists at this quantity."}
            )

        instance = serializer.save(price_list=price_list)
        return Response(VendorPriceBreakSerializer(instance).data, status=status.HTTP_201_CREATED)


class VendorPriceBreakDetailView(PricingAPIView):
    """Update or delete a simple vendor quantity break."""

    def _instance(self, part_id: int, pk: int):
        return get_object_or_404(VendorPriceBreak, pk=pk, price_list__part_id=part_id)

    def patch(self, request, part_id: int, pk: int):
        _require_role(request, "purchase_order", "change")
        instance = self._instance(part_id, pk)
        serializer = VendorPriceBreakSerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        quantity = serializer.validated_data.get("quantity", instance.quantity)
        if (
            VendorPriceBreak.objects.filter(price_list=instance.price_list, quantity=quantity)
            .exclude(pk=instance.pk)
            .exists()
        ):
            raise serializers.ValidationError(
                {"quantity": "A vendor price break already exists at this quantity."}
            )

        return Response(VendorPriceBreakSerializer(serializer.save()).data)

    def delete(self, request, part_id: int, pk: int):
        _require_role(request, "purchase_order", "change")
        self._instance(part_id, pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
