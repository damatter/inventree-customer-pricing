"""Tests for the customer-price envelope calculation."""

from decimal import Decimal

from inventree_customer_pricing.costing import (
    calculate_profit_margin,
    material_line_total,
)
from inventree_customer_pricing.pricing import (
    PricePoint,
    PriceSchedule,
    build_highest_price_envelope,
)


def point(quantity: str, price: str) -> PricePoint:
    """Create a concise decimal price point for tests."""

    return PricePoint(Decimal(quantity), Decimal(price))


def identity(amount: Decimal, source: str, target: str) -> Decimal:
    """Return an unchanged amount for same-currency schedules."""

    assert source == target
    return amount


def test_highest_applicable_price_is_kept_at_every_boundary():
    schedules = [
        PriceSchedule("USD", (point("1", "10"), point("10", "8"))),
        PriceSchedule("USD", (point("1", "12"), point("5", "9"))),
    ]

    result = build_highest_price_envelope(schedules, "USD", identity)

    assert result == [point("1", "12"), point("5", "10"), point("10", "9")]


def test_schedule_is_not_applicable_before_its_first_break():
    schedules = [
        PriceSchedule("USD", (point("1", "4"), point("10", "3"))),
        PriceSchedule("USD", (point("5", "9"),)),
    ]

    result = build_highest_price_envelope(schedules, "USD", identity)

    assert result == [point("1", "4"), point("5", "9"), point("10", "9")]


def test_prices_are_compared_after_currency_conversion():
    schedules = [
        PriceSchedule("USD", (point("1", "10"),)),
        PriceSchedule("CAD", (point("1", "12"), point("10", "9"))),
    ]

    def convert(amount: Decimal, source: str, target: str) -> Decimal:
        assert target == "USD"
        return amount if source == "USD" else amount * Decimal("0.75")

    result = build_highest_price_envelope(schedules, "USD", convert)

    assert result == [point("1", "10"), point("10", "10")]


def test_unsorted_input_is_normalized():
    schedules = [PriceSchedule("USD", (point("25", "2"), point("1", "5"), point("10", "3")))]

    result = build_highest_price_envelope(schedules, "USD", identity)

    assert result == [point("1", "5"), point("10", "3"), point("25", "2")]


def test_empty_schedules_produce_empty_native_pricing():
    assert build_highest_price_envelope([], "USD", identity) == []
    assert build_highest_price_envelope([PriceSchedule("USD", ())], "USD", identity) == []


def test_multiple_material_rows_add_to_a_per_part_cost():
    totals = [
        material_line_total(Decimal("2.5"), Decimal("4.00")),
        material_line_total(Decimal("3"), Decimal("0.75")),
    ]

    assert sum(totals) == Decimal("12.25")


def test_profit_margin_uses_selling_price_as_percentage_basis():
    margin = calculate_profit_margin(Decimal("20"), Decimal("12.25"))

    assert margin is not None
    assert margin.amount == Decimal("7.75")
    assert margin.percent == Decimal("38.7500")


def test_profit_margin_can_show_a_loss():
    margin = calculate_profit_margin(Decimal("10"), Decimal("12"))

    assert margin is not None
    assert margin.amount == Decimal("-2")
    assert margin.percent == Decimal("-20.0")


def test_profit_margin_requires_a_positive_selling_price_and_material_data():
    assert calculate_profit_margin(None, Decimal("4")) is None
    assert calculate_profit_margin(Decimal("4"), None) is None
    assert calculate_profit_margin(Decimal("0"), Decimal("4")) is None
