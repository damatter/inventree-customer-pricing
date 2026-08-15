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

    class UrlsMixin:
        pass

    class UserInterfaceMixin:
        pass

    plugin_module.InvenTreePlugin = InvenTreePlugin
    plugin_mixins_module.AppMixin = AppMixin
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
