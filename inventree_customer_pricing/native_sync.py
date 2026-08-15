"""Business logic and native InvenTree pricing synchronization."""

import logging
from decimal import Decimal

from common.currency import currency_code_default
from django.db import transaction
from django.utils import timezone
from djmoney.contrib.exchange.exceptions import MissingRate
from djmoney.contrib.exchange.models import convert_money
from djmoney.money import Money
from part.models import Part, PartSellPriceBreak

from .models import CustomerPriceList, PartPricingPolicy
from .pricing import PricePoint, PriceSchedule, build_highest_price_envelope

logger = logging.getLogger("inventree")


class CustomerPricingSyncError(RuntimeError):
    """Raised when customer pricing cannot be synchronized to native pricing."""


def resolved_sync_currency(policy: PartPricingPolicy | None) -> str:
    """Return the configured sync currency or InvenTree's default currency."""

    configured = policy.sync_currency if policy else ""
    return (configured or currency_code_default()).upper()


def convert_amount(amount: Decimal, source: str, target: str) -> Decimal:
    """Convert a unit-price amount using InvenTree's configured exchange rates."""

    if source.upper() == target.upper():
        return amount

    try:
        return Decimal(convert_money(Money(amount, source.upper()), target.upper()).amount)
    except MissingRate as exc:
        raise CustomerPricingSyncError(
            f"No exchange rate is available for {source.upper()} to {target.upper()}."
        ) from exc


def _customer_schedules(part_id: int) -> list[PriceSchedule]:
    """Load active customer schedules for a part."""

    schedules: list[PriceSchedule] = []
    price_lists = CustomerPriceList.objects.filter(part_id=part_id, active=True).prefetch_related(
        "breaks"
    )

    for price_list in price_lists:
        points = tuple(
            PricePoint(quantity=price_break.quantity, price=price_break.price)
            for price_break in price_list.breaks.all()
        )
        schedules.append(PriceSchedule(currency=price_list.currency, breaks=points))

    return schedules


def sync_part_sale_prices(part_id: int, *, force: bool = False) -> dict:
    """Replace native sale breaks with the highest customer-price envelope.

    The native table is rebuilt atomically, so a conversion error never leaves a
    partially synchronized price schedule behind.
    """

    part = Part.objects.filter(pk=part_id).first()
    if part is None:
        return {"status": "missing", "breaks": 0}

    policy, _ = PartPricingPolicy.objects.get_or_create(part=part)

    # Customer pricing is always authoritative. Older releases allowed this
    # switch to be disabled; normalize any retained policy during the next sync.
    if not policy.sync_native_sale:
        policy.sync_native_sale = True
        policy.save(update_fields=["sync_native_sale"])

    target_currency = resolved_sync_currency(policy)

    try:
        envelope = build_highest_price_envelope(
            _customer_schedules(part_id), target_currency, convert_amount
        )

        with transaction.atomic():
            PartSellPriceBreak.objects.filter(part=part).delete()
            PartSellPriceBreak.objects.bulk_create(
                [
                    PartSellPriceBreak(
                        part=part,
                        quantity=point.quantity,
                        price=Money(point.price, target_currency),
                    )
                    for point in envelope
                ]
            )

            policy.last_synced = timezone.now()
            policy.last_sync_error = ""
            policy.save(update_fields=["last_synced", "last_sync_error"])
            transaction.on_commit(lambda: part.schedule_pricing_update(create=True))

        return {
            "status": "synced",
            "breaks": len(envelope),
            "currency": target_currency,
        }
    except Exception as exc:
        message = str(exc) or exc.__class__.__name__
        PartPricingPolicy.objects.filter(pk=policy.pk).update(last_sync_error=message)
        raise CustomerPricingSyncError(message) from exc


def sync_part_sale_prices_safely(part_id: int) -> None:
    """Synchronize without allowing an admin save or delete to fail afterward."""

    try:
        sync_part_sale_prices(part_id)
    except CustomerPricingSyncError:
        logger.exception("Customer pricing sync failed for part %s", part_id)
