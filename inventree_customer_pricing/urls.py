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
    path("part/<int:part_id>/", lazy_api_view("PricingWorkspaceView"), name="workspace"),
    path("part/<int:part_id>/policy/", lazy_api_view("PricingPolicyView"), name="policy"),
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
    path(
        "part/<int:part_id>/sale-breaks/",
        lazy_api_view("NativeSaleBreakCollectionView"),
        name="sale-break-create",
    ),
    path(
        "part/<int:part_id>/sale-breaks/<int:pk>/",
        lazy_api_view("NativeSaleBreakDetailView"),
        name="sale-break-detail",
    ),
    path(
        "part/<int:part_id>/vendor-lists/",
        lazy_api_view("VendorPriceListCollectionView"),
        name="vendor-list-create",
    ),
    path(
        "part/<int:part_id>/vendor-lists/<int:pk>/",
        lazy_api_view("VendorPriceListDetailView"),
        name="vendor-list-detail",
    ),
    path(
        "part/<int:part_id>/vendor-lists/<int:price_list_id>/breaks/",
        lazy_api_view("VendorPriceBreakCollectionView"),
        name="vendor-break-create",
    ),
    path(
        "part/<int:part_id>/vendor-breaks/<int:pk>/",
        lazy_api_view("VendorPriceBreakDetailView"),
        name="vendor-break-detail",
    ),
]
