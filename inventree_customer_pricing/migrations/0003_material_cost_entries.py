"""Add durable per-part material cost entries."""

import decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Create material cost rows with database-level integrity constraints."""

    dependencies = [("inventree_customer_pricing", "0002_simple_vendor_pricing")]

    operations = [
        migrations.CreateModel(
            name="MaterialCostEntry",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("name", models.CharField(max_length=255, verbose_name="Material")),
                (
                    "quantity",
                    models.DecimalField(
                        decimal_places=5,
                        default=1,
                        max_digits=15,
                        validators=[
                            django.core.validators.MinValueValidator(
                                decimal.Decimal("0.00001")
                            )
                        ],
                        verbose_name="Quantity per part",
                    ),
                ),
                (
                    "unit_cost",
                    models.DecimalField(
                        decimal_places=6,
                        max_digits=19,
                        validators=[django.core.validators.MinValueValidator(0)],
                        verbose_name="Unit cost",
                    ),
                ),
                ("currency", models.CharField(max_length=3, verbose_name="Currency")),
                ("active", models.BooleanField(default=True, verbose_name="Active")),
                ("notes", models.TextField(blank=True, default="", verbose_name="Notes")),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                (
                    "part",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="material_cost_entries",
                        to="part.part",
                        verbose_name="Part",
                    ),
                ),
            ],
            options={
                "verbose_name": "Material Cost Entry",
                "verbose_name_plural": "Material Cost Entries",
                "ordering": ["-active", "name", "pk"],
            },
        ),
        migrations.AddConstraint(
            model_name="materialcostentry",
            constraint=models.CheckConstraint(
                check=models.Q(("quantity__gt", 0)), name="material_cost_quantity_positive"
            ),
        ),
        migrations.AddConstraint(
            model_name="materialcostentry",
            constraint=models.CheckConstraint(
                check=models.Q(("unit_cost__gte", 0)),
                name="material_cost_unit_cost_nonnegative",
            ),
        ),
    ]
