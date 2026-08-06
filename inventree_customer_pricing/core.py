"""InvenTree plugin entry point for customer-specific pricing."""

from django.utils.translation import gettext_lazy as _
from part.models import Part
from plugin import InvenTreePlugin
from plugin.mixins import AppMixin, UrlsMixin, UserInterfaceMixin
from users.permissions import check_user_role

from . import PLUGIN_VERSION


class CustomerPricingPlugin(AppMixin, UrlsMixin, UserInterfaceMixin, InvenTreePlugin):
    """Add a unified pricing workspace to InvenTree part detail pages."""

    TITLE = "Customer Pricing"
    NAME = "CustomerPricingPlugin"
    SLUG = "customer-pricing"
    DESCRIPTION = (
        "Manage supplier, native sale, and customer-specific price breaks from a part tab."
    )
    VERSION = PLUGIN_VERSION
    AUTHOR = "Matt Dick"
    WEBSITE = "https://github.com/damatter/inventree-customer-pricing"
    LICENSE = "MIT"
    MIN_VERSION = "1.3.2"
    MAX_VERSION = "1.3.99"

    def setup_urls(self):
        """Expose authenticated pricing API endpoints."""

        from .urls import urlpatterns

        return urlpatterns

    def get_ui_panels(self, request, context: dict, **kwargs):
        """Add the pricing workspace as a native part-detail tab."""

        if context.get("target_model") != "part":
            return []

        try:
            part = Part.objects.get(pk=context.get("target_id"))
        except (Part.DoesNotExist, TypeError, ValueError):
            return []

        user = request.user
        can_view_sales = check_user_role(user, "sales_order", "view")
        can_view_purchase = check_user_role(user, "purchase_order", "view")

        if not (can_view_sales or can_view_purchase or user.is_superuser):
            return []

        return [
            {
                "key": "customer-pricing-workspace",
                "title": _("Customer Pricing"),
                "description": _("Purchase, sale, and customer-specific price breaks"),
                "icon": "ti:currency-dollar:outline",
                "source": self.plugin_static_file(
                    "Panel.js:RenderCustomerPricingPluginPanel"
                ),
                "context": {
                    "part_id": part.pk,
                    "part_name": part.name,
                    "part_ipn": part.IPN,
                },
            }
        ]
