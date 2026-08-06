"""Django admin registration for customer pricing data."""

from django.contrib import admin

from .models import CustomerPriceBreak, CustomerPriceList, PartPricingPolicy


class CustomerPriceBreakInline(admin.TabularInline):
    """Edit customer price breaks inline with their price list."""

    model = CustomerPriceBreak
    extra = 0


@admin.register(CustomerPriceList)
class CustomerPriceListAdmin(admin.ModelAdmin):
    """Customer price list administration."""

    list_display = ("part", "customer", "currency", "active", "updated")
    list_filter = ("active", "currency")
    search_fields = ("part__name", "part__IPN", "customer__name")
    inlines = (CustomerPriceBreakInline,)


@admin.register(PartPricingPolicy)
class PartPricingPolicyAdmin(admin.ModelAdmin):
    """Native sync policy administration."""

    list_display = ("part", "sync_native_sale", "sync_currency", "last_synced")
    list_filter = ("sync_native_sale", "sync_currency")
    search_fields = ("part__name", "part__IPN")
    readonly_fields = ("last_synced", "last_sync_error")
