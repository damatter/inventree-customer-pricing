"""Database models for customer-specific part pricing."""

from company.models import Company
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from part.models import Part


class PartPricingPolicy(models.Model):
    """Native sale-pricing synchronization options for a part."""

    class Meta:
        verbose_name = _("Part Pricing Policy")
        verbose_name_plural = _("Part Pricing Policies")

    part = models.OneToOneField(
        Part,
        on_delete=models.CASCADE,
        related_name="customer_pricing_policy",
        verbose_name=_("Part"),
    )
    sync_native_sale = models.BooleanField(
        default=True,
        verbose_name=_("Synchronize native sale pricing"),
        help_text=_("Keep InvenTree sale-price breaks synchronized to customer pricing."),
    )
    sync_currency = models.CharField(
        max_length=3,
        blank=True,
        default="",
        verbose_name=_("Synchronization currency"),
        help_text=_("Leave blank to use InvenTree's default currency."),
    )
    last_synced = models.DateTimeField(null=True, blank=True, editable=False)
    last_sync_error = models.TextField(blank=True, default="", editable=False)

    def __str__(self):
        return f"Pricing policy for {self.part}"


class CustomerPriceList(models.Model):
    """A single customer's pricing schedule for a part."""

    class Meta:
        ordering = ["customer__name"]
        constraints = [
            models.UniqueConstraint(fields=["part", "customer"], name="unique_customer_price_list")
        ]
        verbose_name = _("Customer Price List")
        verbose_name_plural = _("Customer Price Lists")

    part = models.ForeignKey(
        Part,
        on_delete=models.CASCADE,
        related_name="customer_price_lists",
        verbose_name=_("Part"),
    )
    customer = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="part_price_lists",
        limit_choices_to={"is_customer": True},
        verbose_name=_("Customer"),
    )
    currency = models.CharField(max_length=3, verbose_name=_("Currency"))
    active = models.BooleanField(default=True, verbose_name=_("Active"))
    notes = models.TextField(blank=True, default="", verbose_name=_("Notes"))
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.customer} pricing for {self.part}"


class CustomerPriceBreak(models.Model):
    """A quantity break within a customer price list."""

    class Meta:
        ordering = ["quantity"]
        constraints = [
            models.UniqueConstraint(
                fields=["price_list", "quantity"], name="unique_customer_price_break"
            )
        ]
        verbose_name = _("Customer Price Break")
        verbose_name_plural = _("Customer Price Breaks")

    price_list = models.ForeignKey(
        CustomerPriceList,
        on_delete=models.CASCADE,
        related_name="breaks",
        verbose_name=_("Customer price list"),
    )
    quantity = models.DecimalField(
        max_digits=15,
        decimal_places=5,
        validators=[MinValueValidator(1)],
        verbose_name=_("Quantity"),
    )
    price = models.DecimalField(
        max_digits=19,
        decimal_places=6,
        validators=[MinValueValidator(0)],
        verbose_name=_("Unit price"),
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.price_list}: {self.price} @ {self.quantity}"


class VendorPriceList(models.Model):
    """A lightweight purchasing schedule without native supplier setup."""

    class Meta:
        ordering = ["-preferred", "vendor_name", "vendor_sku"]
        verbose_name = _("Simple Vendor Price List")
        verbose_name_plural = _("Simple Vendor Price Lists")

    part = models.ForeignKey(
        Part,
        on_delete=models.CASCADE,
        related_name="simple_vendor_price_lists",
        verbose_name=_("Part"),
    )
    vendor_name = models.CharField(max_length=255, verbose_name=_("Vendor name"))
    vendor_sku = models.CharField(
        max_length=100, blank=True, default="", verbose_name=_("Vendor SKU")
    )
    currency = models.CharField(max_length=3, verbose_name=_("Currency"))
    purchase_url = models.URLField(
        max_length=500, blank=True, default="", verbose_name=_("Purchase URL")
    )
    lead_time_days = models.PositiveIntegerField(
        null=True, blank=True, verbose_name=_("Lead time (days)")
    )
    active = models.BooleanField(default=True, verbose_name=_("Active"))
    preferred = models.BooleanField(default=False, verbose_name=_("Preferred vendor"))
    notes = models.TextField(blank=True, default="", verbose_name=_("Notes"))
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.vendor_name} pricing for {self.part}"


class VendorPriceBreak(models.Model):
    """A quantity break in a lightweight vendor schedule."""

    class Meta:
        ordering = ["quantity"]
        constraints = [
            models.UniqueConstraint(
                fields=["price_list", "quantity"], name="unique_simple_vendor_price_break"
            )
        ]
        verbose_name = _("Simple Vendor Price Break")
        verbose_name_plural = _("Simple Vendor Price Breaks")

    price_list = models.ForeignKey(
        VendorPriceList,
        on_delete=models.CASCADE,
        related_name="breaks",
        verbose_name=_("Vendor price list"),
    )
    quantity = models.DecimalField(
        max_digits=15,
        decimal_places=5,
        validators=[MinValueValidator(1)],
        verbose_name=_("Quantity"),
    )
    price = models.DecimalField(
        max_digits=19,
        decimal_places=6,
        validators=[MinValueValidator(0)],
        verbose_name=_("Unit price"),
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.price_list}: {self.price} @ {self.quantity}"
