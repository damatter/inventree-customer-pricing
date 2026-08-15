"""Django application configuration for the customer pricing plugin."""

from django.apps import AppConfig


class CustomerPricingConfig(AppConfig):
    """Register plugin models and synchronization signals."""

    default_auto_field = "django.db.models.AutoField"
    name = "inventree_customer_pricing"
    verbose_name = "Part Pricing"

    def ready(self):
        """Load model signal handlers after the app registry is ready."""
        from . import signals  # noqa: F401
