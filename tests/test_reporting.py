"""Tests for the public batch reporting interface."""

import ast
import sys
from decimal import Decimal
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from inventree_customer_pricing.reporting import (
    MonetaryReportingRow,
    PartReportingValues,
    aggregate_reporting_values,
    reporting_values_as_dict,
    reporting_values_for_parts,
    user_can_view_reporting_values,
)


def row(part_id: int, amount: str, currency: str = "CAD") -> MonetaryReportingRow:
    """Create a concise reporting source row."""

    return MonetaryReportingRow(part_id, Decimal(amount), currency)


def identity(amount: Decimal, source: str, target: str) -> Decimal:
    """Return same-currency amounts unchanged."""

    assert source == target
    return amount


def test_aggregator_sums_materials_and_finds_sale_extrema_per_part():
    values = aggregate_reporting_values(
        [7, 8],
        [row(7, "10.50"), row(7, "2.25"), row(8, "4")],
        [row(7, "30"), row(7, "22"), row(7, "27"), row(8, "9")],
        "cad",
        identity,
    )

    assert values[7] == PartReportingValues(
        part_id=7,
        currency="CAD",
        unit_material_cost=Decimal("12.75"),
        lowest_sale_price=Decimal("22"),
        highest_sale_price=Decimal("30"),
        error=None,
    )
    assert values[8].unit_material_cost == Decimal("4")
    assert values[8].lowest_sale_price == Decimal("9")
    assert values[8].highest_sale_price == Decimal("9")


def test_aggregator_converts_every_value_before_comparing_or_adding():
    conversions: list[tuple[Decimal, str, str]] = []

    def convert(amount: Decimal, source: str, target: str) -> Decimal:
        conversions.append((amount, source, target))
        return amount if source == target else amount * Decimal("1.25")

    values = aggregate_reporting_values(
        [3],
        [row(3, "4", "USD"), row(3, "5", "CAD")],
        [row(3, "10", "USD"), row(3, "11", "CAD")],
        "CAD",
        convert,
    )

    assert values[3].unit_material_cost == Decimal("10.00")
    assert values[3].lowest_sale_price == Decimal("11")
    assert values[3].highest_sale_price == Decimal("12.50")
    assert len(conversions) == 4


def test_failed_material_conversion_never_returns_a_partial_total():
    def convert(amount: Decimal, source: str, target: str) -> Decimal:
        if source == "USD":
            raise RuntimeError("exchange rate missing")
        return amount

    value = aggregate_reporting_values(
        [4],
        [row(4, "5", "CAD"), row(4, "7", "USD")],
        [row(4, "20")],
        "CAD",
        convert,
    )[4]

    assert value.unit_material_cost is None
    assert value.lowest_sale_price == Decimal("20")
    assert value.highest_sale_price == Decimal("20")
    assert value.error is not None
    assert "Material cost unavailable" in value.error
    assert "exchange rate missing" in value.error


def test_failed_sale_conversion_never_returns_partial_extrema():
    def convert(amount: Decimal, source: str, target: str) -> Decimal:
        if source == "EUR":
            raise RuntimeError("EUR rate missing")
        return amount

    value = aggregate_reporting_values(
        [5],
        [row(5, "6")],
        [row(5, "15"), row(5, "25", "EUR")],
        "CAD",
        convert,
    )[5]

    assert value.unit_material_cost == Decimal("6")
    assert value.lowest_sale_price is None
    assert value.highest_sale_price is None
    assert value.error is not None
    assert "Sale prices unavailable" in value.error
    assert "EUR rate missing" in value.error


def test_missing_data_is_none_with_a_readable_error():
    value = aggregate_reporting_values([99], [], [], "CAD", identity)[99]

    assert value.unit_material_cost is None
    assert value.lowest_sale_price is None
    assert value.highest_sale_price is None
    assert value.error == (
        "No active material cost entries. No active customer sale prices."
    )


def test_unknown_rows_are_ignored_and_duplicate_requested_ids_are_collapsed():
    values = aggregate_reporting_values(
        [2, 2],
        [row(2, "1"), row(999, "100")],
        [row(2, "2"), row(999, "200")],
        "CAD",
        identity,
    )

    assert list(values) == [2]
    assert values[2].unit_material_cost == Decimal("1")
    assert values[2].highest_sale_price == Decimal("2")


def test_public_function_batches_loads_and_uses_requested_currency(monkeypatch):
    import inventree_customer_pricing.reporting as reporting

    loaded: list[tuple[str, tuple[int, ...]]] = []

    def materials(part_ids: tuple[int, ...]):
        loaded.append(("materials", part_ids))
        return [row(10, "3", "USD"), row(10, "4", "USD")]

    def sales(part_ids: tuple[int, ...]):
        loaded.append(("sales", part_ids))
        return [row(10, "15", "USD"), row(10, "12", "USD")]

    monkeypatch.setattr(reporting, "_material_rows_for_parts", materials)
    monkeypatch.setattr(reporting, "_sale_rows_for_parts", sales)
    monkeypatch.setattr(reporting, "_native_currency_converter", lambda: identity)

    values = reporting_values_for_parts([10, 11], target_currency="usd")

    assert loaded == [("materials", (10, 11)), ("sales", (10, 11))]
    assert values[10].unit_material_cost == Decimal("7")
    assert values[10].lowest_sale_price == Decimal("12")
    assert values[11].unit_material_cost is None


def test_public_function_uses_inventree_default_currency(monkeypatch):
    import inventree_customer_pricing.reporting as reporting

    monkeypatch.setattr(reporting, "_default_currency", lambda: "CAD")
    monkeypatch.setattr(reporting, "_material_rows_for_parts", lambda part_ids: [])
    monkeypatch.setattr(reporting, "_sale_rows_for_parts", lambda part_ids: [])
    monkeypatch.setattr(reporting, "_native_currency_converter", lambda: identity)

    values = reporting_values_for_parts([1])

    assert values[1].currency == "CAD"


def test_empty_public_request_does_not_initialize_django(monkeypatch):
    import inventree_customer_pricing.reporting as reporting

    monkeypatch.setattr(
        reporting,
        "_default_currency",
        lambda: pytest.fail("default currency should not be loaded"),
    )

    assert reporting_values_for_parts([]) == {}


def test_reporting_module_defers_django_and_model_imports_until_called():
    source = (
        Path(__file__).parents[1] / "inventree_customer_pricing" / "reporting.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    top_level_modules = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        "." * node.level + (node.module or "")
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
    }

    assert ".models" not in top_level_modules
    assert ".native_sync" not in top_level_modules
    assert "common.currency" not in top_level_modules
    assert not any(module.startswith("django") for module in top_level_modules)


def test_plain_dictionary_adapter_preserves_decimal_values():
    source = {
        1: PartReportingValues(1, "CAD", Decimal("2"), Decimal("3"), Decimal("4"))
    }

    assert reporting_values_as_dict(source) == {
        1: {
            "part_id": 1,
            "currency": "CAD",
            "unit_material_cost": Decimal("2"),
            "lowest_sale_price": Decimal("3"),
            "highest_sale_price": Decimal("4"),
            "error": None,
        }
    }


def test_reporting_access_requires_group_and_both_read_roles(monkeypatch):
    import inventree_customer_pricing.access as access

    monkeypatch.setattr(access, "user_has_pricing_access", lambda user: True)
    permissions = ModuleType("users.permissions")
    roles = {"purchase_order": True, "sales_order": True}
    permissions.check_user_role = lambda user, role, action: (
        action == "view" and roles[role]
    )
    users = ModuleType("users")
    users.__path__ = []
    users.permissions = permissions
    monkeypatch.setitem(sys.modules, "users", users)
    monkeypatch.setitem(sys.modules, "users.permissions", permissions)
    user = SimpleNamespace(is_superuser=False)

    assert user_can_view_reporting_values(user)
    roles["sales_order"] = False
    assert not user_can_view_reporting_values(user)


def test_reporting_access_fails_before_role_checks_without_group(monkeypatch):
    import inventree_customer_pricing.access as access

    monkeypatch.setattr(access, "user_has_pricing_access", lambda user: False)
    permissions = ModuleType("users.permissions")
    permissions.check_user_role = lambda *args: pytest.fail(
        "roles should not be checked before the access group"
    )
    users = ModuleType("users")
    users.__path__ = []
    users.permissions = permissions
    monkeypatch.setitem(sys.modules, "users", users)
    monkeypatch.setitem(sys.modules, "users.permissions", permissions)

    assert not user_can_view_reporting_values(SimpleNamespace(is_superuser=False))
