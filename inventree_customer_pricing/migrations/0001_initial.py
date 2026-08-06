"""Initial customer pricing database schema."""

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Create pricing policy, price list, and price break tables."""

    initial = True

    dependencies = [
        ("company", "0079_auto_20260212_1054"),
        ("part", "0147_remove_part_default_supplier"),
    ]

    operations = [
        migrations.CreateModel(
            name="PartPricingPolicy",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sync_native_sale", models.BooleanField(default=True, help_text="Keep InvenTree sale-price breaks synchronized to customer pricing.", verbose_name="Synchronize native sale pricing")),
                ("sync_currency", models.CharField(blank=True, default="", help_text="Leave blank to use InvenTree's default currency.", max_length=3, verbose_name="Synchronization currency")),
                ("last_synced", models.DateTimeField(blank=True, editable=False, null=True)),
                ("last_sync_error", models.TextField(blank=True, default="", editable=False)),
                ("part", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="customer_pricing_policy", to="part.part", verbose_name="Part")),
            ],
            options={"verbose_name": "Part Pricing Policy", "verbose_name_plural": "Part Pricing Policies"},
        ),
        migrations.CreateModel(
            name="CustomerPriceList",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("currency", models.CharField(max_length=3, verbose_name="Currency")),
                ("active", models.BooleanField(default=True, verbose_name="Active")),
                ("notes", models.TextField(blank=True, default="", verbose_name="Notes")),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                ("customer", models.ForeignKey(limit_choices_to={"is_customer": True}, on_delete=django.db.models.deletion.CASCADE, related_name="part_price_lists", to="company.company", verbose_name="Customer")),
                ("part", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="customer_price_lists", to="part.part", verbose_name="Part")),
            ],
            options={"verbose_name": "Customer Price List", "verbose_name_plural": "Customer Price Lists", "ordering": ["customer__name"]},
        ),
        migrations.CreateModel(
            name="CustomerPriceBreak",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.DecimalField(decimal_places=5, max_digits=15, validators=[django.core.validators.MinValueValidator(1)], verbose_name="Quantity")),
                ("price", models.DecimalField(decimal_places=6, max_digits=19, validators=[django.core.validators.MinValueValidator(0)], verbose_name="Unit price")),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                ("price_list", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="breaks", to="inventree_customer_pricing.customerpricelist", verbose_name="Customer price list")),
            ],
            options={"verbose_name": "Customer Price Break", "verbose_name_plural": "Customer Price Breaks", "ordering": ["quantity"]},
        ),
        migrations.AddConstraint(
            model_name="customerpricelist",
            constraint=models.UniqueConstraint(fields=("part", "customer"), name="unique_customer_price_list"),
        ),
        migrations.AddConstraint(
            model_name="customerpricebreak",
            constraint=models.UniqueConstraint(fields=("price_list", "quantity"), name="unique_customer_price_break"),
        ),
    ]
