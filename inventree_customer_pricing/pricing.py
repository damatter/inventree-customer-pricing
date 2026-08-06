"""Pure pricing-envelope calculations used by the native sync service."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class PricePoint:
    """A quantity threshold and unit price."""

    quantity: Decimal
    price: Decimal


@dataclass(frozen=True)
class PriceSchedule:
    """A customer's ordered pricing schedule."""

    currency: str
    breaks: tuple[PricePoint, ...]


Converter = Callable[[Decimal, str, str], Decimal]


def build_highest_price_envelope(
    schedules: Iterable[PriceSchedule], target_currency: str, converter: Converter
) -> list[PricePoint]:
    """Return the highest applicable unit price at every schedule boundary.

    A price is applicable at a quantity when its threshold is the greatest threshold
    less than or equal to that quantity. Each distinct customer threshold is retained,
    which prevents a customer-specific break from disappearing during native sync.
    """

    normalized: list[PriceSchedule] = []

    for schedule in schedules:
        ordered = tuple(sorted(schedule.breaks, key=lambda point: point.quantity))
        if ordered:
            normalized.append(PriceSchedule(schedule.currency.upper(), ordered))

    thresholds = sorted({point.quantity for schedule in normalized for point in schedule.breaks})
    envelope: list[PricePoint] = []

    for quantity in thresholds:
        candidates: list[Decimal] = []

        for schedule in normalized:
            applicable = [point for point in schedule.breaks if point.quantity <= quantity]
            if not applicable:
                continue

            selected = applicable[-1]
            candidates.append(
                converter(selected.price, schedule.currency, target_currency.upper())
            )

        if candidates:
            envelope.append(PricePoint(quantity=quantity, price=max(candidates)))

    return envelope
