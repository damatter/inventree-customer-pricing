"""URL routes for the customer pricing plugin API."""

from django.urls import path

from . import views

app_name = "inventree_customer_pricing"

urlpatterns = [
    path("part/<int:part_id>/", views.PricingWorkspaceView.as_view(), name="workspace"),
    path("part/<int:part_id>/policy/", views.PricingPolicyView.as_view(), name="policy"),
    path("part/<int:part_id>/sync/", views.PricingSyncView.as_view(), name="sync"),
    path(
        "part/<int:part_id>/customer-lists/",
        views.CustomerPriceListCollectionView.as_view(),
        name="customer-list-create",
    ),
    path(
        "part/<int:part_id>/customer-lists/<int:pk>/",
        views.CustomerPriceListDetailView.as_view(),
        name="customer-list-detail",
    ),
    path(
        "part/<int:part_id>/customer-lists/<int:price_list_id>/breaks/",
        views.CustomerPriceBreakCollectionView.as_view(),
        name="customer-break-create",
    ),
    path(
        "part/<int:part_id>/customer-breaks/<int:pk>/",
        views.CustomerPriceBreakDetailView.as_view(),
        name="customer-break-detail",
    ),
    path(
        "part/<int:part_id>/sale-breaks/",
        views.NativeSaleBreakCollectionView.as_view(),
        name="sale-break-create",
    ),
    path(
        "part/<int:part_id>/sale-breaks/<int:pk>/",
        views.NativeSaleBreakDetailView.as_view(),
        name="sale-break-detail",
    ),
    path(
        "part/<int:part_id>/supplier-parts/<int:supplier_part_id>/breaks/",
        views.SupplierBreakCollectionView.as_view(),
        name="supplier-break-create",
    ),
    path(
        "part/<int:part_id>/supplier-breaks/<int:pk>/",
        views.SupplierBreakDetailView.as_view(),
        name="supplier-break-detail",
    ),
]
