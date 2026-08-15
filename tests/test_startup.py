"""Regression tests for safe plugin discovery during Django startup."""

import ast
import importlib
import sys
from pathlib import Path
from types import ModuleType

PACKAGE_ROOT = Path(__file__).parents[1] / "inventree_customer_pricing"


def top_level_imports(filename: str) -> set[str]:
    """Return modules imported directly at module scope."""

    tree = ast.parse((PACKAGE_ROOT / filename).read_text(encoding="utf-8"))
    modules: set[str] = set()

    for node in tree.body:
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.add("." * node.level + (node.module or ""))

    return modules


def test_entry_point_defers_inventree_model_imports():
    """The package entry point must load before the Django app registry is ready."""

    imports = top_level_imports("core.py")

    assert "part.models" not in imports
    assert "users.permissions" not in imports


def test_url_configuration_defers_api_view_imports():
    """API modules reference plugin models and must load only after app registration."""

    assert ".views" not in top_level_imports("urls.py")


def test_entry_point_imports_without_registered_models(monkeypatch):
    """Discovery must import the entry point before any plugin models are available."""

    django_module = ModuleType("django")
    django_module.__path__ = []
    django_utils_module = ModuleType("django.utils")
    django_utils_module.__path__ = []
    translation_module = ModuleType("django.utils.translation")
    translation_module.gettext_lazy = lambda value: value

    plugin_module = ModuleType("plugin")
    plugin_mixins_module = ModuleType("plugin.mixins")

    class InvenTreePlugin:
        pass

    class AppMixin:
        pass

    class SettingsMixin:
        pass

    class UrlsMixin:
        pass

    class UserInterfaceMixin:
        pass

    plugin_module.InvenTreePlugin = InvenTreePlugin
    plugin_mixins_module.AppMixin = AppMixin
    plugin_mixins_module.SettingsMixin = SettingsMixin
    plugin_mixins_module.UrlsMixin = UrlsMixin
    plugin_mixins_module.UserInterfaceMixin = UserInterfaceMixin

    fake_modules = {
        "django": django_module,
        "django.utils": django_utils_module,
        "django.utils.translation": translation_module,
        "plugin": plugin_module,
        "plugin.mixins": plugin_mixins_module,
    }

    for name, module in fake_modules.items():
        monkeypatch.setitem(sys.modules, name, module)

    sys.modules.pop("inventree_customer_pricing.core", None)
    imported = importlib.import_module("inventree_customer_pricing.core")

    assert imported.CustomerPricingPlugin.SLUG == "customer-pricing"
    assert imported.CustomerPricingPlugin.TITLE == "Part Pricing"
    assert "part.models" not in sys.modules
    assert "users.permissions" not in sys.modules
    assert "inventree_customer_pricing.models" not in sys.modules
    assert "inventree_customer_pricing.views" not in sys.modules

    sys.modules.pop("inventree_customer_pricing.core", None)


def test_database_identity_and_migration_chain_remain_stable():
    """Backups and upgrades rely on a stable app label and linear migrations."""

    apps_source = (PACKAGE_ROOT / "apps.py").read_text(encoding="utf-8")
    migration_source = (PACKAGE_ROOT / "migrations" / "0003_material_cost_entries.py").read_text(
        encoding="utf-8"
    )

    assert 'name = "inventree_customer_pricing"' in apps_source
    assert '("inventree_customer_pricing", "0002_simple_vendor_pricing")' in migration_source
    assert 'name="MaterialCostEntry"' in migration_source
    assert "material_cost_quantity_positive" in migration_source
    assert "material_cost_unit_cost_nonnegative" in migration_source


def test_mobile_contract_is_versioned_and_authenticated_by_plugin_routes():
    """The mobile feature convention must remain explicit and versioned."""

    from inventree_customer_pricing.mobile import MobileAppMixin

    options = MobileAppMixin.mobile_app_options("part-pricing-v1", "/plugin/test/{pk}/")

    assert options == {
        "mobile": {
            "schema_version": 1,
            "renderer": "part-pricing-v1",
            "endpoint": "/plugin/test/{pk}/",
        }
    }


def test_views_accept_the_pre_030_currency_converter_name():
    """A hot plugin update can briefly retain native_sync from version 0.2.x."""

    source = (PACKAGE_ROOT / "views.py").read_text(encoding="utf-8")

    assert "except ImportError" in source
    assert "_convert_amount as convert_amount" in source


def test_workspace_advertises_customer_write_endpoints_for_mobile_clients():
    """Native clients should not need to reconstruct customer API routes."""

    source = (PACKAGE_ROOT / "views.py").read_text(encoding="utf-8")

    assert '"customer_list_collection"' in source
    assert '"customer_list_detail"' in source
    assert '"customer_break_collection"' in source
    assert '"customer_break_detail"' in source
    assert '"customer-lists/{list_pk}/breaks/"' in source


def test_admin_registration_is_safe_to_reload(monkeypatch):
    """InvenTree can reload admin.py when only some models remain registered."""

    django_module = ModuleType("django")
    django_module.__path__ = []
    contrib_module = ModuleType("django.contrib")
    contrib_module.__path__ = []
    admin_module = ModuleType("django.contrib.admin")

    class ModelAdmin:
        pass

    class TabularInline:
        pass

    class AdminSite:
        def __init__(self):
            self.registry = {}

        def is_registered(self, model):
            return model in self.registry

        def register(self, model, model_admin):
            if self.is_registered(model):
                raise RuntimeError(f"{model.__name__} was registered twice")
            self.registry[model] = model_admin

    admin_module.ModelAdmin = ModelAdmin
    admin_module.TabularInline = TabularInline
    admin_module.site = AdminSite()
    contrib_module.admin = admin_module

    models_module = ModuleType("inventree_customer_pricing.models")
    model_names = (
        "CustomerPriceBreak",
        "CustomerPriceList",
        "MaterialCostEntry",
        "PartPricingPolicy",
        "VendorPriceBreak",
        "VendorPriceList",
    )
    for name in model_names:
        setattr(models_module, name, type(name, (), {}))

    fake_modules = {
        "django": django_module,
        "django.contrib": contrib_module,
        "django.contrib.admin": admin_module,
        "inventree_customer_pricing.models": models_module,
    }
    for name, module in fake_modules.items():
        monkeypatch.setitem(sys.modules, name, module)

    sys.modules.pop("inventree_customer_pricing.admin", None)
    imported = importlib.import_module("inventree_customer_pricing.admin")
    admin_module.site.registry.pop(models_module.MaterialCostEntry)
    importlib.reload(imported)

    assert set(admin_module.site.registry) == {
        models_module.MaterialCostEntry,
        models_module.CustomerPriceList,
        models_module.PartPricingPolicy,
        models_module.VendorPriceList,
    }

    sys.modules.pop("inventree_customer_pricing.admin", None)
