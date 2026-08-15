"""Authenticated API views for the part pricing workspace."""

from decimal import Decimal

from company.models import Company
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from djmoney.money import Money
from moneyed import CURRENCIES
from part.models import Part, PartSellPriceBreak
from rest_framework import permissions, serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView
from users.permissions import check_user_role

from .access import user_has_pricing_access
from .models import (
    CustomerPriceBreak,
    CustomerPriceList,
    MaterialCostEntry,
    PartPricingPolicy,
    VendorPriceBreak,
    VendorPriceList,
)
from .native_sync import (
    CustomerPricingSyncError,
    resolved_sync_currency,
    sync_part_sale_prices,
)

# During an in-place plugin update, an InvenTree process can retain the 0.2.x
# native_sync module in memory while loading this newer views module. Accept
# the former private name until the process has restarted.
try:
    from .native_sync import convert_amount
except ImportError:  # pragma: no cover - only reachable during a mixed hot upgrade
    from .native_sync import _convert_amount as convert_amount
from .serializers import (
    CurrencyField,
    CustomerPriceBreakSerializer,
    CustomerPriceListSerializer,
    MaterialCostEntrySerializer,
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


def _material_costs_by_currency(part: Part, currencies: set[str]) -> tuple[dict, dict]:
    """Convert all active material rows into each requested target currency."""

    entries = list(MaterialCostEntry.objects.filter(part=part, active=True))
    if not entries:
        return {}, {}

    totals = {}
    errors = {}

    for currency in sorted({code.upper() for code in currencies if code}):
        try:
            totals[currency] = sum(
                (convert_amount(entry.total_cost, entry.currency, currency) for entry in entries),
                Decimal("0"),
            )
        except CustomerPricingSyncError as exc:
            errors[currency] = str(exc)

    return totals, errors


class PricingAccessPermission(permissions.BasePermission):
    """Require membership of the configured sensitive-pricing group."""

    message = "You are not a member of the configured Part Pricing access group."

    def has_permission(self, request, view):
        return user_has_pricing_access(request.user)


class PricingAPIView(APIView):
    """Base class with both authentication and plugin-specific access checks."""

    permission_classes = [permissions.IsAuthenticated, PricingAccessPermission]


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
        policy_data["sync_native_sale"] = True
        policy_data["resolved_currency"] = resolved_sync_currency(policy)

        customer_lists = []
        customer_options = []
        customer_queryset = CustomerPriceList.objects.none()

        if can_view_sales:
            customer_queryset = (
                CustomerPriceList.objects.filter(part=part)
                .select_related("customer")
                .prefetch_related("breaks")
            )
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
        material_costs = []
        material_cost_by_currency = {}
        material_cost_errors = {}

        if can_view_purchase:
            material_queryset = MaterialCostEntry.objects.filter(part=part)
            material_costs = MaterialCostEntrySerializer(material_queryset, many=True).data

            requested_currencies = {policy_data["resolved_currency"]}
            requested_currencies.update(customer_queryset.values_list("currency", flat=True))
            material_cost_by_currency, material_cost_errors = _material_costs_by_currency(
                part, requested_currencies
            )

        if can_view_sales:
            customer_lists = CustomerPriceListSerializer(
                customer_queryset,
                many=True,
                context={"material_cost_by_currency": material_cost_by_currency},
            ).data

        material_cost_summary = [
            {"currency": currency, "total": _decimal(total)}
            for currency, total in sorted(material_cost_by_currency.items())
        ]

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
                # Retain empty compatibility keys for older mobile/web bundles
                # while sale and vendor pricing are removed from the product UI.
                "native_sale_breaks": [],
                "vendor_lists": [],
                "material_costs": material_costs,
                "material_cost_summary": material_cost_summary,
                "material_cost_errors": material_cost_errors,
                "currencies": sorted(CURRENCIES.keys()),
                "endpoints": {
                    "material_cost_collection": (
                        f"/plugin/customer-pricing/part/{part.pk}/material-costs/"
                    ),
                    "material_cost_detail": (
                        f"/plugin/customer-pricing/part/{part.pk}/material-costs/{{pk}}/"
                    ),
                    "customer_list_collection": (
                        f"/plugin/customer-pricing/part/{part.pk}/customer-lists/"
                    ),
                    "customer_list_detail": (
                        f"/plugin/customer-pricing/part/{part.pk}/customer-lists/{{pk}}/"
                    ),
                    "customer_break_collection": (
                        f"/plugin/customer-pricing/part/{part.pk}/"
                        "customer-lists/{list_pk}/breaks/"
                    ),
                    "customer_break_detail": (
                        f"/plugin/customer-pricing/part/{part.pk}/customer-breaks/{{pk}}/"
                    ),
                },
            }
        )


class MaterialCostCollectionView(PricingAPIView):
    """Create a material cost row for a part."""

    def post(self, request, part_id: int):
        _require_role(request, "purchase_order", "change")
        part = get_object_or_404(Part, pk=part_id)
        serializer = MaterialCostEntrySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save(part=part)
        return Response(
            MaterialCostEntrySerializer(instance).data,
            status=status.HTTP_201_CREATED,
        )


class MaterialCostDetailView(PricingAPIView):
    """Update or remove a material cost row."""

    def _instance(self, part_id: int, pk: int):
        return get_object_or_404(MaterialCostEntry, pk=pk, part_id=part_id)

    def patch(self, request, part_id: int, pk: int):
        _require_role(request, "purchase_order", "change")
        instance = self._instance(part_id, pk)
        serializer = MaterialCostEntrySerializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(MaterialCostEntrySerializer(serializer.save()).data)

    def delete(self, request, part_id: int, pk: int):
        _require_role(request, "purchase_order", "change")
        self._instance(part_id, pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MobileManifestView(PricingAPIView):
    """Return the versioned mobile integration contract for this plugin."""

    def get(self, request):
        from .core import CustomerPricingPlugin

        return Response(
            {
                "plugin": "customer-pricing",
                "title": "Part Pricing",
                "version": CustomerPricingPlugin.VERSION,
                **CustomerPricingPlugin.mobile_app_manifest(),
            }
        )


class MobileDashboardView(PricingAPIView):
    """Return a generic authenticated summary for native mobile dashboards."""

    def get(self, request):
        can_view_sales = _has_role(request.user, "sales_order", "view")
        can_view_purchase = _has_role(request.user, "purchase_order", "view")
        if not (can_view_sales or can_view_purchase):
            raise PermissionDenied("A sales-order or purchase-order role is required.")

        material_count = 0
        customer_count = 0
        part_ids = set()
        if can_view_purchase:
            material_count = MaterialCostEntry.objects.filter(active=True).count()
            part_ids.update(MaterialCostEntry.objects.values_list("part_id", flat=True))
        if can_view_sales:
            customer_count = CustomerPriceList.objects.filter(active=True).count()
            part_ids.update(CustomerPriceList.objects.values_list("part_id", flat=True))

        overview_items = [
            {
                "label": "Parts with pricing data",
                "value": str(len(part_ids)),
                "icon": "currency-dollar",
            }
        ]
        if can_view_purchase:
            overview_items.extend(
                [
                    {"label": "Active material entries", "value": str(material_count)},
                ]
            )
        if can_view_sales:
            overview_items.append(
                {"label": "Active customer schedules", "value": str(customer_count)}
            )

        recent_items = []
        if can_view_purchase:
            recent_entries = MaterialCostEntry.objects.select_related("part").order_by("-updated")[
                :8
            ]
            recent_items = [
                {
                    "label": entry.part.IPN or entry.part.name,
                    "value": entry.name,
                    "detail": (
                        f"{_decimal(entry.quantity)} x {_decimal(entry.unit_cost)} {entry.currency}"
                    ),
                    "action": {"type": "model_detail", "model": "part", "pk": entry.part_id},
                }
                for entry in recent_entries
            ]

        sections = [{"title": "Overview", "items": overview_items}]
        if recent_items:
            sections.append({"title": "Recently updated materials", "items": recent_items})

        return Response(
            {
                "schema_version": 1,
                "title": "Part Pricing",
                "description": "Material costs, customer margins, and purchasing by part",
                "sections": sections,
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
        try:
            with transaction.atomic():
                price_list = serializer.save(part=part)
        except IntegrityError as exc:
            raise serializers.ValidationError(
                {"customer": "This customer already has a price list for the part."}
            ) from exc
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
