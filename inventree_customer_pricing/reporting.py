"""Public, batch-oriented reporting values for other InvenTree plugins."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class MonetaryReportingRow:
    """One source amount used by the pure reporting aggregator."""

    part_id: int
    amount: Decimal
    currency: str


@dataclass(frozen=True)
class PartReportingValues:
    """Material and sale-price values for one part in a common currency."""

    part_id: int
    currency: str
    unit_material_cost: Decimal | None
    lowest_sale_price: Decimal | None
    highest_sale_price: Decimal | None
    error: str | None = None


CurrencyConverter = Callable[[Decimal, str, str], Decimal]


def _normalized_part_ids(part_ids: Iterable[int]) -> tuple[int, ...]:
    """Return unique integer part identifiers while retaining input order."""

    return tuple(dict.fromkeys(int(part_id) for part_id in part_ids))


def _normalize_currency(currency: object) -> str:
    """Return a normalized currency code or reject an unusable value."""

    code = str(currency or "").strip().upper()
    if not code:
        raise ValueError("A target currency is required.")
    return code


def _convert_reporting_amount(
    row: MonetaryReportingRow,
    target_currency: str,
    convert: CurrencyConverter,
) -> Decimal:
    """Convert one source row and add useful context to conversion failures."""

    source_currency = _normalize_currency(row.currency)
    try:
        return Decimal(convert(Decimal(row.amount), source_currency, target_currency))
    except Exception as exc:
        detail = str(exc) or exc.__class__.__name__
        raise ValueError(
            f"could not convert {source_currency} to {target_currency}: {detail}"
        ) from exc


def _group_rows(
    rows: Iterable[MonetaryReportingRow],
) -> dict[int, list[MonetaryReportingRow]]:
    """Group monetary rows by part without requiring Django objects."""

    grouped: dict[int, list[MonetaryReportingRow]] = {}
    for row in rows:
        grouped.setdefault(int(row.part_id), []).append(row)
    return grouped


def aggregate_reporting_values(
    part_ids: Iterable[int],
    material_rows: Iterable[MonetaryReportingRow],
    sale_rows: Iterable[MonetaryReportingRow],
    target_currency: str,
    convert: CurrencyConverter,
) -> dict[int, PartReportingValues]:
    """Aggregate already-loaded rows into safe, per-part reporting values.

    Each metric fails closed. If any row required for a material total or sale
    range cannot be converted, that complete metric is returned as ``None``
    rather than a partial and potentially misleading value.
    """

    normalized_ids = _normalized_part_ids(part_ids)
    currency = _normalize_currency(target_currency)
    materials_by_part = _group_rows(material_rows)
    sales_by_part = _group_rows(sale_rows)
    result: dict[int, PartReportingValues] = {}

    for part_id in normalized_ids:
        errors: list[str] = []
        part_materials = materials_by_part.get(part_id, [])
        part_sales = sales_by_part.get(part_id, [])

        material_cost: Decimal | None = None
        if part_materials:
            try:
                material_cost = sum(
                    (
                        _convert_reporting_amount(row, currency, convert)
                        for row in part_materials
                    ),
                    Decimal("0"),
                )
            except Exception as exc:
                errors.append(f"Material cost unavailable: {exc}")
        else:
            errors.append("No active material cost entries.")

        lowest_sale_price: Decimal | None = None
        highest_sale_price: Decimal | None = None
        if part_sales:
            try:
                converted_prices = [
                    _convert_reporting_amount(row, currency, convert) for row in part_sales
                ]
                lowest_sale_price = min(converted_prices)
                highest_sale_price = max(converted_prices)
            except Exception as exc:
                errors.append(f"Sale prices unavailable: {exc}")
        else:
            errors.append("No active customer sale prices.")

        result[part_id] = PartReportingValues(
            part_id=part_id,
            currency=currency,
            unit_material_cost=material_cost,
            lowest_sale_price=lowest_sale_price,
            highest_sale_price=highest_sale_price,
            error=" ".join(errors) or None,
        )

    return result


def _material_rows_for_parts(part_ids: tuple[int, ...]) -> list[MonetaryReportingRow]:
    """Load active material inputs for every requested part in one query."""

    from .models import MaterialCostEntry

    rows = MaterialCostEntry.objects.filter(part_id__in=part_ids, active=True).values(
        "part_id", "quantity", "unit_cost", "currency"
    )
    return [
        MonetaryReportingRow(
            part_id=int(row["part_id"]),
            amount=Decimal(row["quantity"]) * Decimal(row["unit_cost"]),
            currency=str(row["currency"]),
        )
        for row in rows
    ]


def _sale_rows_for_parts(part_ids: tuple[int, ...]) -> list[MonetaryReportingRow]:
    """Load breaks from active customer price lists in one query."""

    from .models import CustomerPriceBreak

    rows = CustomerPriceBreak.objects.filter(
        price_list__part_id__in=part_ids,
        price_list__active=True,
    ).values("price_list__part_id", "price_list__currency", "price")
    return [
        MonetaryReportingRow(
            part_id=int(row["price_list__part_id"]),
            amount=Decimal(row["price"]),
            currency=str(row["price_list__currency"]),
        )
        for row in rows
    ]


def _default_currency() -> str:
    """Resolve InvenTree's default currency only after Django is initialized."""

    from common.currency import currency_code_default

    return str(currency_code_default())


def _native_currency_converter() -> CurrencyConverter:
    """Load the plugin's native converter only when reporting is requested."""

    from .native_sync import convert_amount

    return convert_amount


def reporting_values_for_parts(
    part_ids: Iterable[int], target_currency: str | None = None
) -> dict[int, PartReportingValues]:
    """Return material cost and customer sale-price extrema for many parts.

    The returned dictionary contains an entry for every requested identifier.
    All monetary values use ``target_currency`` or InvenTree's configured
    default currency. Database work remains constant at two queries regardless
    of the number of parts requested.
    """

    normalized_ids = _normalized_part_ids(part_ids)
    if not normalized_ids:
        return {}

    currency = _normalize_currency(target_currency or _default_currency())
    return aggregate_reporting_values(
        normalized_ids,
        _material_rows_for_parts(normalized_ids),
        _sale_rows_for_parts(normalized_ids),
        currency,
        _native_currency_converter(),
    )


def reporting_values_as_dict(
    values: Mapping[int, PartReportingValues],
) -> dict[int, dict[str, Any]]:
    """Convert reporting dataclasses to plain dictionaries when required."""

    return {
        part_id: {
            "part_id": value.part_id,
            "currency": value.currency,
            "unit_material_cost": value.unit_material_cost,
            "lowest_sale_price": value.lowest_sale_price,
            "highest_sale_price": value.highest_sale_price,
            "error": value.error,
        }
        for part_id, value in values.items()
    }
