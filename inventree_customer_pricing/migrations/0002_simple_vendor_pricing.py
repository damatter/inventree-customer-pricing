"""Add lightweight vendor pricing independent of native supplier records."""

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Create simple vendor price-list and quantity-break tables."""

    dependencies = [("inventree_customer_pricing", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="VendorPriceList",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("vendor_name", models.CharField(max_length=255, verbose_name="Vendor name")),
                (
                    "vendor_sku",
                    models.CharField(
                        blank=True, default="", max_length=100, verbose_name="Vendor SKU"
                    ),
                ),
                ("currency", models.CharField(max_length=3, verbose_name="Currency")),
                (
                    "purchase_url",
                    models.URLField(
                        blank=True, default="", max_length=500, verbose_name="Purchase URL"
                    ),
                ),
                (
                    "lead_time_days",
                    models.PositiveIntegerField(
                        blank=True, null=True, verbose_name="Lead time (days)"
                    ),
                ),
                ("active", models.BooleanField(default=True, verbose_name="Active")),
                ("preferred", models.BooleanField(default=False, verbose_name="Preferred vendor")),
                ("notes", models.TextField(blank=True, default="", verbose_name="Notes")),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                (
                    "part",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="simple_vendor_price_lists",
                        to="part.part",
                        verbose_name="Part",
                    ),
                ),
            ],
            options={
                "verbose_name": "Simple Vendor Price List",
                "verbose_name_plural": "Simple Vendor Price Lists",
                "ordering": ["-preferred", "vendor_name", "vendor_sku"],
            },
        ),
        migrations.CreateModel(
            name="VendorPriceBreak",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "quantity",
                    models.DecimalField(
                        decimal_places=5,
                        max_digits=15,
                        validators=[django.core.validators.MinValueValidator(1)],
                        verbose_name="Quantity",
                    ),
                ),
                (
                    "price",
                    models.DecimalField(
                        decimal_places=6,
                        max_digits=19,
                        validators=[django.core.validators.MinValueValidator(0)],
                        verbose_name="Unit price",
                    ),
                ),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                (
                    "price_list",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="breaks",
                        to="inventree_customer_pricing.vendorpricelist",
                        verbose_name="Vendor price list",
                    ),
                ),
            ],
            options={
                "verbose_name": "Simple Vendor Price Break",
                "verbose_name_plural": "Simple Vendor Price Breaks",
                "ordering": ["quantity"],
            },
        ),
        migrations.AddConstraint(
            model_name="vendorpricebreak",
            constraint=models.UniqueConstraint(
                fields=("price_list", "quantity"), name="unique_simple_vendor_price_break"
            ),
        ),
    ]
