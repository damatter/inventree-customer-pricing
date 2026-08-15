"""InvenTree plugin entry point for customer-specific pricing."""

from django.utils.translation import gettext_lazy as _
from plugin import InvenTreePlugin
from plugin.mixins import AppMixin, UrlsMixin, UserInterfaceMixin

from . import PLUGIN_VERSION
from .mobile import MobileAppMixin


class CustomerPricingPlugin(
    MobileAppMixin, AppMixin, UrlsMixin, UserInterfaceMixin, InvenTreePlugin
):
    """Add a unified pricing workspace to InvenTree part detail pages."""

    TITLE = "Part Pricing"
    NAME = "CustomerPricingPlugin"
    SLUG = "customer-pricing"
    DESCRIPTION = "Manage material costs, purchasing, sale pricing, and customer margins per part."
    VERSION = PLUGIN_VERSION
    AUTHOR = "Matt Dick"
    WEBSITE = "https://github.com/damatter/inventree-customer-pricing"
    LICENSE = "MIT"
    MIN_VERSION = "1.3.2"
    MAX_VERSION = "1.3.99"

    MOBILE_APP_FEATURES = (
        {
            "feature_type": "dashboard",
            "key": "part-pricing-overview",
            "title": "Part Pricing",
            "renderer": "summary-list-v1",
            "endpoint": "/plugin/customer-pricing/mobile/dashboard/",
        },
        {
            "feature_type": "model_detail",
            "model": "part",
            "key": "part-pricing-workspace",
            "title": "Part Pricing",
            "renderer": "part-pricing-v1",
            "endpoint": "/plugin/customer-pricing/part/{pk}/",
        },
    )

    def setup_urls(self):
        """Expose authenticated pricing API endpoints."""

        from .urls import urlpatterns

        return urlpatterns

    def get_ui_panels(self, request, context: dict, **kwargs):
        """Add the pricing workspace as a native part-detail tab."""

        # Keep model imports out of the package entry point. InvenTree discovers
        # plugin classes while the Django app registry is still being prepared.
        from part.models import Part
        from users.permissions import check_user_role

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
                "key": "part-pricing-workspace",
                "title": _("Part Pricing"),
                "description": _("Material costs, purchasing, sale pricing, and customer margins"),
                "icon": "ti:currency-dollar:outline",
                "source": self.plugin_static_file("Panel.js:RenderCustomerPricingPluginPanel"),
                "options": self.mobile_app_options(
                    "part-pricing-v1", "/plugin/customer-pricing/part/{pk}/"
                ),
                "context": {
                    "part_id": part.pk,
                    "part_name": part.name,
                    "part_ipn": part.IPN,
                },
            }
        ]

    def get_ui_dashboard_items(self, request, context: dict, **kwargs):
        """Expose an authenticated pricing overview to web and mobile dashboards."""

        from users.permissions import check_user_role

        user = request.user
        if not (
            user.is_superuser
            or check_user_role(user, "sales_order", "view")
            or check_user_role(user, "purchase_order", "view")
        ):
            return []

        return [
            {
                "key": "part-pricing-overview",
                "title": _("Part Pricing"),
                "description": _("Material costs, customer schedules, and vendor pricing"),
                "icon": "ti:currency-dollar:outline",
                "source": self.plugin_static_file("Panel.js:RenderPartPricingDashboard"),
                "options": {
                    "width": 3,
                    "height": 2,
                    **self.mobile_app_options(
                        "summary-list-v1", "/plugin/customer-pricing/mobile/dashboard/"
                    ),
                },
            }
        ]
