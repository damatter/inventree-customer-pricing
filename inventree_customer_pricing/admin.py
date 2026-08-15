"""Django admin registration for customer pricing data."""

from django.contrib import admin

from .models import (
    CustomerPriceBreak,
    CustomerPriceList,
    MaterialCostEntry,
    PartPricingPolicy,
    VendorPriceBreak,
    VendorPriceList,
)


class MaterialCostEntryAdmin(admin.ModelAdmin):
    """Material cost rows stored against each part."""

    list_display = ("part", "name", "quantity", "unit_cost", "currency", "active", "updated")
    list_filter = ("active", "currency")
    search_fields = ("part__name", "part__IPN", "name", "notes")


class CustomerPriceBreakInline(admin.TabularInline):
    """Edit customer price breaks inline with their price list."""

    model = CustomerPriceBreak
    extra = 0


class CustomerPriceListAdmin(admin.ModelAdmin):
    """Customer price list administration."""

    list_display = ("part", "customer", "currency", "active", "updated")
    list_filter = ("active", "currency")
    search_fields = ("part__name", "part__IPN", "customer__name")
    inlines = (CustomerPriceBreakInline,)


class PartPricingPolicyAdmin(admin.ModelAdmin):
    """Native sync policy administration."""

    list_display = ("part", "sync_native_sale", "sync_currency", "last_synced")
    list_filter = ("sync_native_sale", "sync_currency")
    search_fields = ("part__name", "part__IPN")
    readonly_fields = ("last_synced", "last_sync_error")


class VendorPriceBreakInline(admin.TabularInline):
    """Edit simple vendor breaks inline with their price list."""

    model = VendorPriceBreak
    extra = 0


class VendorPriceListAdmin(admin.ModelAdmin):
    """Simple vendor price-list administration."""

    list_display = ("part", "vendor_name", "vendor_sku", "currency", "preferred", "active")
    list_filter = ("preferred", "active", "currency")
    search_fields = ("part__name", "part__IPN", "vendor_name", "vendor_sku")
    inlines = (VendorPriceBreakInline,)


# InvenTree reloads this module when an AppMixin has only some of its models
# registered. Django's @admin.register decorator raises AlreadyRegistered for
# the models which survived that reload, so register only the missing models.
for model, model_admin in (
    (MaterialCostEntry, MaterialCostEntryAdmin),
    (CustomerPriceList, CustomerPriceListAdmin),
    (PartPricingPolicy, PartPricingPolicyAdmin),
    (VendorPriceList, VendorPriceListAdmin),
):
    if not admin.site.is_registered(model):
        admin.site.register(model, model_admin)
