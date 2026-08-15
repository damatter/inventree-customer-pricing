"""Tests for the fail-closed Part Pricing access policy."""

import sys
from types import ModuleType, SimpleNamespace

from inventree_customer_pricing.access import normalize_group_id, user_has_pricing_access


def test_normalize_group_id_accepts_positive_ids_and_model_instances():
    assert normalize_group_id("7") == 7
    assert normalize_group_id(type("Group", (), {"pk": 9})()) == 9


def test_normalize_group_id_fails_closed_for_missing_or_invalid_values():
    assert normalize_group_id(None) is None
    assert normalize_group_id("") is None
    assert normalize_group_id("not-a-group") is None
    assert normalize_group_id(0) is None


def test_superusers_bypass_the_configured_group_lookup():
    user = SimpleNamespace(is_authenticated=True, is_superuser=True)
    assert user_has_pricing_access(user)


def test_group_membership_is_required_for_regular_users(monkeypatch):
    registry_module = ModuleType("plugin.registry")
    plugin_module = ModuleType("plugin")
    plugin_module.__path__ = []
    configured_plugin = SimpleNamespace(
        get_setting=lambda key, backup_value=None: "7"
    )
    registry_module.registry = SimpleNamespace(
        get_plugin=lambda slug, active=True: configured_plugin
    )
    monkeypatch.setitem(sys.modules, "plugin", plugin_module)
    monkeypatch.setitem(sys.modules, "plugin.registry", registry_module)

    class Groups:
        def __init__(self, member):
            self.member = member

        def filter(self, **kwargs):
            assert kwargs == {"pk": 7}
            return SimpleNamespace(exists=lambda: self.member)

    allowed = SimpleNamespace(
        is_authenticated=True,
        is_superuser=False,
        groups=Groups(True),
    )
    denied = SimpleNamespace(
        is_authenticated=True,
        is_superuser=False,
        groups=Groups(False),
    )

    assert user_has_pricing_access(allowed)
    assert not user_has_pricing_access(denied)
