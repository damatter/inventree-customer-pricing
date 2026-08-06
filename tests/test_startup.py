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
    assert "part.models" not in sys.modules
    assert "users.permissions" not in sys.modules
    assert "inventree_customer_pricing.models" not in sys.modules
    assert "inventree_customer_pricing.views" not in sys.modules

    sys.modules.pop("inventree_customer_pricing.core", None)
