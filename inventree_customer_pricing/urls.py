"""URL routes for the customer pricing plugin API."""

from django.urls import path
from django.views.decorators.csrf import csrf_exempt


def lazy_api_view(view_name):
    """Resolve an API view only after InvenTree has registered the plugin app."""

    @csrf_exempt
    def dispatch(request, *args, **kwargs):
        from . import views

        return getattr(views, view_name).as_view()(request, *args, **kwargs)

    return dispatch


app_name = "inventree_customer_pricing"

urlpatterns = [
    path("mobile/manifest/", lazy_api_view("MobileManifestView"), name="mobile-manifest"),
    path("mobile/dashboard/", lazy_api_view("MobileDashboardView"), name="mobile-dashboard"),
    path("part/<int:part_id>/", lazy_api_view("PricingWorkspaceView"), name="workspace"),
    path(
        "part/<int:part_id>/material-costs/",
        lazy_api_view("MaterialCostCollectionView"),
        name="material-cost-create",
    ),
    path(
        "part/<int:part_id>/material-costs/<int:pk>/",
        lazy_api_view("MaterialCostDetailView"),
        name="material-cost-detail",
    ),
    path("part/<int:part_id>/sync/", lazy_api_view("PricingSyncView"), name="sync"),
    path(
        "part/<int:part_id>/customer-lists/",
        lazy_api_view("CustomerPriceListCollectionView"),
        name="customer-list-create",
    ),
    path(
        "part/<int:part_id>/customer-lists/<int:pk>/",
        lazy_api_view("CustomerPriceListDetailView"),
        name="customer-list-detail",
    ),
    path(
        "part/<int:part_id>/customer-lists/<int:price_list_id>/breaks/",
        lazy_api_view("CustomerPriceBreakCollectionView"),
        name="customer-break-create",
    ),
    path(
        "part/<int:part_id>/customer-breaks/<int:pk>/",
        lazy_api_view("CustomerPriceBreakDetailView"),
        name="customer-break-detail",
    ),
]
